#!/usr/bin/env python3
"""Servidor local da decupagem: serve as páginas, deixa o player pular no vídeo
e executa os cortes pedidos pela página (baixar trecho ou mandar pro DaVinci).

Uso: ./abrir [Nome_do_Projeto]      (sobe o servidor se preciso e abre no Chrome)
     .venv/bin/python servidor.py   (só o servidor, porta 8792)
"""
import json
import os as _os
_os.environ.setdefault("PYTHONUTF8", "1")
_os.environ.setdefault("LANG", "pt_BR.UTF-8")
_os.environ.setdefault("LC_ALL", "pt_BR.UTF-8")
import os
import re
import subprocess
import sys
import unicodedata
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).resolve().parent
PROJETOS = BASE / "projetos"
PORTA = int(os.environ.get("PORTA", 8792))
FFMPEG = str(BASE / ".venv" / "bin" / "ffmpeg")

RESOLVE_API = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
os.environ.setdefault("RESOLVE_SCRIPT_API", RESOLVE_API)
os.environ.setdefault("RESOLVE_SCRIPT_LIB",
                      "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so")
sys.path.append(RESOLVE_API + "/Modules")
sys.path.insert(0, str(BASE))


def slug(txt, limite=40):
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", txt).strip("_")[:limite] or "corte"


def dados_projeto(nome):
    pasta = (PROJETOS / nome).resolve()
    if PROJETOS not in pasta.parents:
        raise ValueError("projeto inválido")
    t = json.loads((pasta / "transcricao.json").read_text())
    arquivos = t.get("arquivos") or [{"caminho": t["arquivo"]}]
    return pasta, t, arquivos


def cortar(p):
    pasta, t, arquivos = dados_projeto(p["projeto"])
    fonte = arquivos[int(p.get("arq", 0))]
    origem = fonte["caminho"]
    ini, fim = float(p["inicio"]), float(p["fim"])
    if fim - ini < 0.2:
        raise ValueError("trecho curto demais")
    if fonte.get("itens"):
        # áudio montado de uma timeline: corta do vídeo original da câmera naquele ponto
        meio = (ini + fim) / 2
        it = next((x for x in fonte["itens"] if x["ini"] <= meio < x["fim"]), None)
        if it:
            base = it["src_in"] / it["fps"] - it["ini"]
            origem = it["arquivo"]
            ini = max(it["src_in"] / it["fps"], base + ini)
            fim = min(it["src_out"] / it["fps"], base + fim)
    saida_dir = pasta / "cortes"
    saida_dir.mkdir(exist_ok=True)
    sonda = subprocess.run([FFMPEG, "-hide_banner", "-i", origem], capture_output=True, text=True).stderr
    tem_video = "Video:" in sonda
    n = len(list(saida_dir.glob("*.*"))) + 1
    nome = f"{n:02d}_{slug(p.get('nome') or 'corte')}." + ("mp4" if tem_video else "wav")
    saida = saida_dir / nome
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{ini:.3f}", "-i", origem, "-t", f"{fim - ini:.3f}"]
    if tem_video:
        cmd += ["-map", "0:v:0", "-map", "0:a:0?", "-c:v", "h264_videotoolbox", "-b:v", "80M", "-tag:v", "avc1",
                "-c:a", "aac", "-b:a", "320k", "-movflags", "+faststart", str(saida)]
    else:  # fonte só de áudio (gravador): trecho em WAV sem perda
        cmd += ["-map", "0:a:0", "-c:a", "pcm_s24le", str(saida)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[-400:] or "ffmpeg falhou")
    return {"ok": True, "arquivo": str(saida), "url": f"/{pasta.name}/cortes/{nome}",
            "msg": f"Corte salvo: cortes/{nome}"}


def resolve():
    import DaVinciResolveScript as d  # noqa: N813
    r = d.scriptapp("Resolve")
    if not r:
        raise RuntimeError("DaVinci Resolve não está aberto (ou o script externo está desligado).")
    return r


CONFIG_DOWNLOADS = PROJETOS / "_config_downloads.json"


def pasta_downloads():
    """Pasta onde os downloads são salvos: a escolhida pelo usuário, ou projetos/_downloads se ela não existir mais."""
    try:
        escolhida = Path(json.loads(CONFIG_DOWNLOADS.read_text())["destino"])
        if escolhida.is_dir():
            return escolhida
    except (OSError, ValueError, KeyError):
        pass
    padrao = PROJETOS / "_downloads"
    padrao.mkdir(parents=True, exist_ok=True)
    return padrao


def trocar_pasta_downloads(_p):
    """Abre a janela do macOS para escolher a pasta de downloads e guarda a escolha."""
    r = subprocess.run(["osascript", "-e", 'POSIX path of (choose folder with prompt "Escolha onde salvar os downloads")'],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return {"ok": False, "msg": "Escolha cancelada."}
    escolhida = r.stdout.strip().rstrip("/")
    PROJETOS.mkdir(parents=True, exist_ok=True)
    CONFIG_DOWNLOADS.write_text(json.dumps({"destino": escolhida}, ensure_ascii=False))
    return {"ok": True, "pasta": escolhida, "msg": f"Downloads serão salvos em {escolhida}."}


def ver_pasta_downloads(_p):
    return {"ok": True, "pasta": str(pasta_downloads())}


def achar_clipe(pasta, caminho, nome=None):
    for c in pasta.GetClipList() or []:
        if (nome and c.GetName() == nome) or (not nome and c.GetClipProperty("File Path") == caminho):
            return c
    for sub in pasta.GetSubFolderList() or []:
        c = achar_clipe(sub, caminho, nome)
        if c:
            return c
    return None


def clipe_na_timeline(projeto, nome_tl, ini, fim):
    """Converte um trecho (segundos na timeline) no clipe de origem + frames de origem."""
    tl = next((projeto.GetTimelineByIndex(i) for i in range(1, projeto.GetTimelineCount() + 1)
               if projeto.GetTimelineByIndex(i).GetName() == nome_tl), None)
    if not tl:
        raise RuntimeError(f"A timeline '{nome_tl}' não está no projeto aberto ('{projeto.GetName()}').")
    tfps = float(tl.GetSetting("timelineFrameRate"))
    meio = tl.GetStartFrame() + (ini + fim) / 2 * tfps
    for it in tl.GetItemListInTrack("audio", 1) or []:
        if it.GetStart() <= meio < it.GetEnd() and it.GetMediaPoolItem():
            m = it.GetMediaPoolItem()
            cfps = float(m.GetClipProperty("FPS") or tfps)
            base = it.GetSourceStartFrame() - (it.GetStart() - tl.GetStartFrame()) / tfps * cfps
            a, b = int(round(base + ini * cfps)), int(round(base + fim * cfps))
            return m, max(a, it.GetSourceStartFrame()), min(b, it.GetSourceEndFrame())
    raise RuntimeError("Não achei clipe nesse ponto da timeline.")


def montar_roteiro_davinci(p):
    """Monta no DaVinci a timeline do roteiro do projeto (projetos/<p>/roteiro_resolve.json), na ordem das cenas."""
    from montar_roteiro import montar
    pasta = (PROJETOS / p["projeto"]).resolve()
    if PROJETOS not in pasta.parents:
        raise ValueError("projeto inválido")
    roteiro = pasta / "roteiro_resolve.json"
    if not roteiro.exists():
        return {"ok": False, "msg": "Esse projeto ainda não tem roteiro montável (roteiro_resolve.json)."}
    dados = json.loads(roteiro.read_text(encoding="utf-8"))
    # timeline de onde o roteiro foi tirado: a que estava aberta na análise (guardada na transcrição)
    origem = dados.get("origem")
    if not origem:
        t = json.loads((pasta / "transcricao.json").read_text(encoding="utf-8"))
        origem = next((a.get("resolve_timeline") for a in t.get("arquivos") or [] if a.get("resolve_timeline")), None)
    if not origem:
        return {"ok": False, "msg": "Não sei de qual timeline do DaVinci esse roteiro foi tirado. Refaça a análise com a timeline aberta."}
    nome = "Roteiro · " + (dados.get("titulo") or p["projeto"])
    try:
        return montar(roteiro, nome, p.get("modo") or "cortes", origem)
    except Exception as e:
        return {"ok": False, "msg": str(e)}


def para_davinci(p):
    _, t, arquivos = dados_projeto(p["projeto"])
    fonte = arquivos[int(p.get("arq", 0))]
    origem = fonte["caminho"]
    projeto = resolve().GetProjectManager().GetCurrentProject()
    mp = projeto.GetMediaPool()
    ini, fim = float(p["inicio"]), float(p["fim"])
    trecho_src = None
    if fonte.get("resolve_timeline"):
        # áudio montado a partir de uma timeline: acha o clipe que está naquele ponto
        trecho_src = clipe_na_timeline(projeto, fonte["resolve_timeline"], ini, fim)
        clipe = trecho_src[0]
    else:
        # multicam: corta no clipe multicam sincronizado pelo gravador (mesmos segundos)
        clipe = achar_clipe(mp.GetRootFolder(), origem, fonte.get("resolve_clipe"))
    if not clipe:
        # Segurança: nunca importa mídia em outro projeto (ex.: de cliente)
        raise RuntimeError(f"O projeto aberto no DaVinci ('{projeto.GetName()}') não tem o clipe "
                           f"{Path(origem).name}. Abra o projeto deste trabalho e tente de novo.")
    fps = float(clipe.GetClipProperty("FPS") or projeto.GetSetting("timelineFrameRate"))
    if trecho_src:
        _, f_ini, f_fim = trecho_src
    else:
        f_ini, f_fim = int(round(ini * fps)), int(round(fim * fps))

    titulo = p.get("titulo") or t.get("projeto", "Agiliza-Zé")
    nome_tl = f"Destaques · {titulo}"
    tl = next((projeto.GetTimelineByIndex(i) for i in range(1, projeto.GetTimelineCount() + 1)
               if projeto.GetTimelineByIndex(i).GetName() == nome_tl), None) or mp.CreateEmptyTimeline(nome_tl)
    projeto.SetCurrentTimeline(tl)

    antes = {it.GetUniqueId() for k in ("video", "audio") for it in (tl.GetItemListInTrack(k, 1) or [])}
    mp.AppendToTimeline([{"mediaPoolItem": clipe, "startFrame": f_ini, "endFrame": f_fim}])
    novos = [it for k in ("video", "audio") for it in (tl.GetItemListInTrack(k, 1) or [])
             if it.GetUniqueId() not in antes]
    if not novos:
        raise RuntimeError("O DaVinci não aceitou o trecho.")
    for it in novos:
        if p.get("cor"):
            it.SetClipColor(p["cor"])
    v = min((it for it in novos if it.GetTrackTypeAndIndex()[0] == "video"),
            key=lambda it: it.GetStart(), default=novos[0])
    texto = (p.get("texto") or "")[:500]
    tl.AddMarker(v.GetStart() - tl.GetStartFrame(), "Red", (p.get("nome") or "Destaque")[:60],
                 f'{p.get("quem", "")}: {texto}'.strip(": "), 1)
    total = len(tl.GetItemListInTrack("video", 1) or [])
    return {"ok": True, "msg": f"Enviado para a timeline '{nome_tl}' ({total} trechos) no projeto {projeto.GetName()}."}


def _tc(frame, fps):
    base = int(round(fps))  # 23.976 → 24, 29.97 → 30, 59.94 → 60 (timecode sem drop-frame)
    f = int(round(frame))
    return f"{f // (3600 * base):02d}:{f // (60 * base) % 60:02d}:{f // base % 60:02d}:{f % base:02d}"


def localizar(p):
    """Só leva o cursor do DaVinci até o trecho: abre a timeline certa e posiciona o playhead. Não altera nada."""
    _, t, arquivos = dados_projeto(p["projeto"])
    fonte = arquivos[int(p.get("arq", 0))]
    origem = fonte["caminho"]
    r = resolve()
    projeto = r.GetProjectManager().GetCurrentProject()
    ini = float(p.get("ponto", p["inicio"]))
    timelines = [projeto.GetTimelineByIndex(i) for i in range(1, projeto.GetTimelineCount() + 1)]
    alvo = None
    if fonte.get("resolve_timeline"):
        tl = next((x for x in timelines if x.GetName() == fonte["resolve_timeline"]), None)
        if tl:
            alvo = (tl, tl.GetStartFrame() + ini * float(tl.GetSetting("timelineFrameRate")))
    else:
        atual = projeto.GetCurrentTimeline()
        ordem = ([atual] if atual else []) + [x for x in timelines if not atual or x.GetUniqueId() != atual.GetUniqueId()]
        for tl in ordem:
            tfps = float(tl.GetSetting("timelineFrameRate"))
            for tipo in ("video", "audio"):
                for i in range(1, tl.GetTrackCount(tipo) + 1):
                    for it in tl.GetItemListInTrack(tipo, i) or []:
                        m = it.GetMediaPoolItem()
                        if not m:
                            continue
                        if fonte.get("resolve_clipe"):
                            if m.GetName() != fonte["resolve_clipe"]:
                                continue
                        elif m.GetClipProperty("File Path") != origem:
                            continue
                        cfps = float(m.GetClipProperty("FPS") or tfps)
                        src = ini * cfps
                        if it.GetSourceStartFrame() <= src <= it.GetSourceEndFrame():
                            alvo = (tl, it.GetStart() + (src - it.GetSourceStartFrame()) * tfps / cfps)
                            break
                    if alvo:
                        break
                if alvo:
                    break
            if alvo:
                break
    if not alvo:
        raise RuntimeError(f"Não achei esse trecho em nenhuma timeline do projeto aberto ('{projeto.GetName()}').")
    tl, frame = alvo
    projeto.SetCurrentTimeline(tl)
    r.OpenPage("edit")
    tc = _tc(frame, float(tl.GetSetting("timelineFrameRate")))
    tl.SetCurrentTimecode(tc)
    return {"ok": True, "msg": f"Cursor posicionado em '{tl.GetName()}' · {tc}"}


def resolve_info(_p):
    """Projeto e timelines abertos no DaVinci, para o formulário de análise."""
    proj = resolve().GetProjectManager().GetCurrentProject()
    atual = proj.GetCurrentTimeline()
    cores = {}
    if atual:
        for tipo in ("video", "audio"):
            for i in range(1, atual.GetTrackCount(tipo) + 1):
                for it in atual.GetItemListInTrack(tipo, i) or []:
                    c = it.GetClipColor()
                    if c and tipo == "audio":
                        cores[c] = cores.get(c, 0) + 1
    faixas = []
    if atual:
        fps = float(atual.GetSetting("timelineFrameRate"))
        for i in range(1, atual.GetTrackCount("audio") + 1):
            its = atual.GetItemListInTrack("audio", i) or []
            faixas.append({"n": i, "nome": atual.GetTrackName("audio", i), "clipes": len(its),
                           "dur": round(sum(it.GetEnd() - it.GetStart() for it in its) / fps)})
    return {"ok": True, "projeto": proj.GetName(), "atual": atual.GetName() if atual else None, "faixas": faixas,
            "timelines": [proj.GetTimelineByIndex(i).GetName() for i in range(1, proj.GetTimelineCount() + 1)],
            "cores": cores}


def analisar(p):
    """Dispara a análise completa em segundo plano (pipeline.py)."""
    nome = (p.get("nome") or "").strip()
    if not nome:
        raise ValueError("Dê um nome ao projeto.")
    cmd = [str(BASE / ".venv" / "bin" / "python"), str(BASE / "pipeline.py"), "--modo", p.get("modo", "atual"),
           "--nome", nome]
    for k in ("alvo", "prompt", "duracao", "obs", "faixa", "tipo"):
        if p.get(k):
            cmd += [f"--{k}", str(p[k])]
    subprocess.Popen(cmd, cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return {"ok": True, "msg": "Análise iniciada."}


def cancelar(p):
    """Para a análise em andamento (transcrição, Claude e tudo que ela abriu) e manda a pasta parcial para a Lixeira."""
    import signal
    import time
    alvo = (PROJETOS / p.get("projeto", "")).resolve()
    if PROJETOS not in alvo.parents:
        raise ValueError("análise não encontrada")
    if alvo.suffix == ".json" and alvo.parent.name == "_sync":  # sincronização
        d = json.loads(alvo.read_text())
        if d.get("pid") and not d.get("fim"):
            try:
                os.killpg(os.getpgid(d["pid"]), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        alvo.unlink(missing_ok=True)
        return {"ok": True, "msg": "Sincronização cancelada."}
    pasta = alvo
    if not (pasta / "_status.json").exists():
        raise ValueError("análise não encontrada")
    d = json.loads((pasta / "_status.json").read_text())
    pid = d.get("pid")
    if pid and not d.get("fim"):
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    lixo = Path.home() / ".Trash" / f"AgilizaZe_cancelado_{time.strftime('%Y-%m-%d_%H%M%S')}"
    lixo.mkdir(parents=True, exist_ok=True)
    pasta.rename(lixo / pasta.name)
    return {"ok": True, "msg": "Análise cancelada."}


def apagar(p):
    """Manda um projeto finalizado para a Lixeira (os vídeos originais não são tocados)."""
    import time
    pasta = (PROJETOS / p.get("projeto", "")).resolve()
    if PROJETOS not in pasta.parents or not pasta.is_dir():
        raise ValueError("projeto não encontrado")
    st = pasta / "_status.json"
    if st.exists() and not json.loads(st.read_text()).get("fim"):
        raise ValueError("Esse projeto ainda está sendo analisado — use Cancelar.")
    lixo = Path.home() / ".Trash" / f"AgilizaZe_limpeza_{time.strftime('%Y-%m-%d_%H%M%S')}"
    lixo.mkdir(parents=True, exist_ok=True)
    pasta.rename(lixo / pasta.name)
    return {"ok": True, "msg": "Projeto enviado para a Lixeira."}


def sincronizar(p):
    """Sincroniza pela forma de onda os clipes da timeline aberta, na própria timeline (sincronizar.py)."""
    import time
    pasta = PROJETOS / "_sync"
    pasta.mkdir(parents=True, exist_ok=True)
    st = pasta / f"{time.strftime('%Y%m%d_%H%M%S')}.json"
    cmd = [str(BASE / ".venv" / "bin" / "python"), str(BASE / "sincronizar.py"), "--status", str(st)]
    if p.get("ref"):
        cmd += ["--ref", str(int(p["ref"]))]
    subprocess.Popen(cmd, cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return {"ok": True, "msg": "Sincronização iniciada."}


def multicam(p):
    """Cria um multicam com as faixas de vídeo da timeline aberta e uma timeline nova com ele (multicam.py)."""
    import time
    pasta = PROJETOS / "_sync"
    pasta.mkdir(parents=True, exist_ok=True)
    st = pasta / f"{time.strftime('%Y%m%d_%H%M%S')}_multicam.json"
    cmd = [str(BASE / ".venv" / "bin" / "python"), str(BASE / "multicam.py"), "--status", str(st)]
    subprocess.Popen(cmd, cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return {"ok": True, "msg": "Criando o multicam."}


def baixar(p):
    """Baixa vídeo ou áudio por link para projetos/_downloads (baixar.py). Aparece em Atividade e pode ser cancelado."""
    import time
    url = (p.get("url") or "").strip()
    if not url:
        raise ValueError("cole um link")
    pasta = PROJETOS / "_sync"
    pasta.mkdir(parents=True, exist_ok=True)
    st = pasta / f"{time.strftime('%Y%m%d_%H%M%S')}_download.json"
    cmd = [str(BASE / ".venv" / "bin" / "python"), str(BASE / "baixar.py"), "--url", url,
           "--formato", "audio" if p.get("formato") == "audio" else "video", "--status", str(st)]
    cmd += ["--destino", str(pasta_downloads())]
    cfg = ler_config_app()
    cmd += ["--audio-format", cfg["formato_audio"], "--qualidade", cfg["qualidade"]]
    if cfg["importar_auto"]:
        cmd.append("--importar")
    subprocess.Popen(cmd, cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return {"ok": True, "msg": "Download iniciado."}


def downloads(_p):
    """Arquivos já baixados, do mais novo para o mais antigo."""
    pasta = pasta_downloads()
    pasta.mkdir(parents=True, exist_ok=True)
    arqs = sorted((f for f in pasta.iterdir() if f.is_file() and not f.name.startswith(".")),
                  key=lambda f: f.stat().st_mtime, reverse=True)[:300]
    return {"ok": True, "arquivos": [{"nome": f.name, "tamanho": f.stat().st_size, "quando": f.stat().st_mtime} for f in arqs]}


def abrir_pasta(p):
    """Abre a pasta de downloads no Finder, ou seleciona um arquivo dentro dela."""
    pasta = pasta_downloads().resolve()
    pasta.mkdir(parents=True, exist_ok=True)
    nome = p.get("nome")
    if nome:
        alvo = (pasta / nome).resolve()
        if pasta not in alvo.parents or not alvo.is_file():
            raise ValueError("arquivo não encontrado")
        subprocess.run(["open", "-R", str(alvo)])
    else:
        subprocess.run(["open", str(pasta)])
    return {"ok": True}


MODELOS_TIMELINE = {
    "4k": ("4K 24 fps", 3840, 2160),
    "1080": ("1080p 24 fps", 1920, 1080),
    "1080v": ("1080p vertical 24 fps", 1080, 1920),
}


PRESETS_ARQ = PROJETOS / "_presets.json"
FPS_OK = ("23.976", "24", "25", "29.97", "30", "50", "60")


def ler_presets():
    try:
        dados = json.loads(PRESETS_ARQ.read_text())
        return dados if isinstance(dados, list) else []
    except (OSError, ValueError):
        return []


def listar_presets(_p):
    return {"ok": True, "presets": ler_presets()}


def salvar_preset(p):
    """Guarda um preset criado pelo usuário: nome, resolução, frame rate e espaços de cor."""
    import uuid
    nome = (p.get("nome") or "").strip()[:40]
    if not nome:
        raise ValueError("Dê um nome ao preset.")
    try:
        largura, altura = int(p.get("largura")), int(p.get("altura"))
    except (TypeError, ValueError):
        raise ValueError("Largura e altura precisam ser números.")
    if not (320 <= largura <= 7680 and 240 <= altura <= 4320):
        raise ValueError("Resolução fora do limite (320 a 7680 de largura, 240 a 4320 de altura).")
    fps = str(p.get("fps") or "24")
    if fps not in FPS_OK:
        raise ValueError("Frame rate não reconhecido.")
    lista = ler_presets()
    novo = {"id": uuid.uuid4().hex[:8], "nome": nome, "largura": largura, "altura": altura, "fps": fps,
            "timeline": str(p.get("timeline") or "Rec.709 (Scene)")[:80],
            "saida": str(p.get("saida") or "Same as Timeline")[:80]}
    lista.append(novo)
    PROJETOS.mkdir(parents=True, exist_ok=True)
    PRESETS_ARQ.write_text(json.dumps(lista, ensure_ascii=False))
    return {"ok": True, "msg": f"Preset '{nome}' salvo."}


def excluir_preset(p):
    lista = [x for x in ler_presets() if x.get("id") != p.get("id")]
    PRESETS_ARQ.write_text(json.dumps(lista, ensure_ascii=False))
    return {"ok": True, "msg": "Preset excluído."}


HACKEDIT_ARQ = PROJETOS / "_hackedit.json"


def ler_hackedit():
    try:
        dados = json.loads(HACKEDIT_ARQ.read_text())
        return dados if isinstance(dados, list) else []
    except (OSError, ValueError):
        return []


def listar_hackedit(_p):
    projeto = ""
    try:
        projeto = resolve().GetProjectManager().GetCurrentProject().GetName()
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "referencias": ler_hackedit(), "projeto": projeto}


def salvar_hackedit(p):
    import time
    import uuid
    nome = (p.get("nome") or "").strip()[:60]
    link = (p.get("link") or "").strip()[:400]
    if not nome:
        raise ValueError("Dê um nome à referência.")
    if link and not link.startswith(("http://", "https://")):
        raise ValueError("O link precisa começar com https://")
    projeto = ""
    try:
        projeto = resolve().GetProjectManager().GetCurrentProject().GetName()
    except Exception:  # noqa: BLE001
        pass
    lista = ler_hackedit()
    lista.append({"id": uuid.uuid4().hex[:8], "nome": nome, "link": link, "projeto": projeto,
                  "criado": time.strftime("%d/%m/%Y %H:%M")})
    PROJETOS.mkdir(parents=True, exist_ok=True)
    HACKEDIT_ARQ.write_text(json.dumps(lista, ensure_ascii=False))
    return {"ok": True, "msg": f"Referência '{nome}' guardada."}


def inventario_timeline(tl):
    """Planos que já estão na timeline, com o momento que o Organizador gravou nas Keywords de cada um."""
    import time
    fps = float(tl.GetSetting("timelineFrameRate") or 24)
    planos, momentos = [], {}
    for i in range(1, tl.GetTrackCount("video") + 1):
        for it in tl.GetItemListInTrack("video", i) or []:
            m = it.GetMediaPoolItem()
            kw = (m.GetMetadata("Keywords") if m else "") or ""
            mos = [k.strip() for k in kw.split(",") if k.strip()]
            chave = mos[0] if mos else "sem momento"
            momentos[chave] = momentos.get(chave, 0) + 1
            planos.append({"nome": it.GetName(), "faixa": i, "inicio": round((it.GetStart() - tl.GetStartFrame()) / fps, 2),
                           "duracao": round((it.GetEnd() - it.GetStart()) / fps, 2), "momento": chave})
    return {"timeline": tl.GetName(), "planos": len(planos), "momentos": momentos, "lista": planos[:400],
            "quando": time.strftime("%d/%m/%Y %H:%M")}


def analisar_referencia(p):
    """Inicia a análise do ritmo em segundo plano (analise_referencia.py); o andamento aparece em Atividade."""
    import time
    ref = next((x for x in ler_hackedit() if x.get("id") == p.get("id")), None)
    if not ref:
        raise ValueError("referência não encontrada")
    if not ref.get("arquivo"):
        raise ValueError("Essa referência é um link. Por enquanto a análise funciona com o arquivo de vídeo enviado.")
    arq = (PROJETOS / ref["arquivo"]).resolve()
    if not arq.is_file():
        raise ValueError("arquivo da referência não encontrado")
    pasta = PROJETOS / "_sync"
    pasta.mkdir(parents=True, exist_ok=True)
    st = pasta / f"{time.strftime('%Y%m%d_%H%M%S')}_analise.json"
    cmd = [str(BASE / ".venv" / "bin" / "python"), str(BASE / "analise_referencia.py"), "--id", ref["id"],
           "--arquivo", str(arq), "--status", str(st)]
    subprocess.Popen(cmd, cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return {"ok": True, "msg": "Análise iniciada — acompanhe o andamento em Atividade."}


def premontar_hackedit(ref, p):
    import time
    """Pré-montagem na timeline aberta: mantém o que já está feito até o corte e refaz o resto com os brutos,
    cortados no ritmo da referência (durações dos planos medidas na análise)."""
    import re
    lista_planos = (ref.get("analise") or {}).get("planos_lista") or []
    if not lista_planos:
        raise ValueError("Rode 'Analisar referência' antes da pré-montagem.")
    proj = resolve().GetProjectManager().GetCurrentProject()
    tl = proj.GetCurrentTimeline() if proj else None
    if not tl:
        raise ValueError("Nenhuma timeline aberta no DaVinci.")
    fps = float(tl.GetSetting("timelineFrameRate") or 24)
    t0 = tl.GetStartFrame()
    corte = float(p.get("corte") or 30)
    # backup da timeline antes de mexer
    bk = PROJETOS / "_sync" / "backups"
    bk.mkdir(parents=True, exist_ok=True)
    nome_bk = "".join(c if c.isalnum() else "_" for c in tl.GetName())
    arq_bk = bk / f"{nome_bk}_premontagem_{time.strftime('%Y%m%d_%H%M%S')}.drt"
    if not tl.Export(str(arq_bk), resolve().EXPORT_DRT, resolve().EXPORT_NONE) or not arq_bk.exists():
        raise ValueError("Não consegui salvar o backup da timeline; nada foi alterado.")
    # brutos: clipes de vídeo a partir do corte (e os áudios ligados a eles)
    brutos, para_apagar = [], []
    for i in range(1, tl.GetTrackCount("video") + 1):
        for it in tl.GetItemListInTrack("video", i) or []:
            ini = (it.GetStart() - t0) / fps
            if ini < corte - 0.01:
                continue
            m = it.GetMediaPoolItem()
            if not m:
                continue
            brutos.append({"m": m, "a": it.GetSourceStartFrame(), "b": it.GetSourceEndFrame(),
                           "cfps": float(m.GetClipProperty("FPS") or fps)})
            para_apagar.append(it)
            para_apagar += [li for li in (it.GetLinkedItems() or [])]
    if not brutos:
        raise ValueError("Não encontrei brutos depois do corte. Coloque os brutos na timeline.")
    brutos.sort(key=lambda x: (x["m"].GetClipProperty("File Path") or "", x["a"]))
    tl.DeleteClips(list({x.GetUniqueId(): x for x in para_apagar}.values()), False)
    mp = proj.GetMediaPool()
    pos = t0 + round(corte * fps)
    usados, k, total = 0, 0, 0.0
    for b in brutos:
        cur = b["a"]
        while cur < b["b"]:
            d = lista_planos[k % len(lista_planos)]
            k += 1
            frames = max(1, round(d * fps * (b["cfps"] / fps)))
            fim = min(b["b"], cur + frames)
            if (fim - cur) / b["cfps"] < 0.25:
                break
            info = {"mediaPoolItem": b["m"], "startFrame": cur, "endFrame": fim, "recordFrame": pos}
            novos = mp.AppendToTimeline([info]) or []
            if novos:
                usados += 1
                dur_tl = round((fim - cur) * fps / b["cfps"])
                pos += dur_tl
                total += dur_tl / fps
            cur = fim
    return {"ok": True, "msg": f"Pré-montagem: {usados} plano(s), {total:.0f} s, a partir de {corte:g} s."}


def acao_hackedit(p):
    """Nova timeline (com o nome da referência) ou continuar na timeline aberta."""
    ref = next((x for x in ler_hackedit() if x.get("id") == p.get("id")), None)
    if not ref:
        raise ValueError("referência não encontrada")
    if p.get("modo") == "nova":
        return criar_timeline({"modelo": "1080", "nome": ref["nome"]})
    if p.get("modo") == "premontar":
        return premontar_hackedit(ref, p)
    if p.get("modo") == "continuar":
        proj = resolve().GetProjectManager().GetCurrentProject()
        tl = proj.GetCurrentTimeline() if proj else None
        if not tl:
            raise ValueError("Nenhuma timeline aberta no DaVinci.")
        inv = inventario_timeline(tl)
        lista = ler_hackedit()
        for x in lista:
            if x.get("id") == ref["id"]:
                x["inventario"] = inv
        HACKEDIT_ARQ.write_text(json.dumps(lista, ensure_ascii=False))
        resumo = ", ".join(f"{k} ({v})" for k, v in inv["momentos"].items()) or "nenhum momento marcado"
        return {"ok": True, "msg": f"Lidos {inv['planos']} plano(s) em '{tl.GetName()}': {resumo}."}
    raise ValueError("ação desconhecida")


def excluir_hackedit(p):
    for x in ler_hackedit():
        if x.get("id") == p.get("id") and x.get("arquivo"):
            arq = (PROJETOS / x["arquivo"]).resolve()
            if (PROJETOS / "_hackedit" / "arquivos") in arq.parents:
                arq.unlink(missing_ok=True)
    lista = [x for x in ler_hackedit() if x.get("id") != p.get("id")]
    HACKEDIT_ARQ.write_text(json.dumps(lista, ensure_ascii=False))
    return {"ok": True, "msg": "Referência removida."}


def criar_timeline(p):
    """Cria uma timeline com um dos modelos da aba Base e a deixa aberta no DaVinci."""
    fps, cores_preset = "24", {}
    if str(p.get("modelo", "")).startswith("p:"):
        pid = str(p["modelo"])[2:]
        pr = next((x for x in ler_presets() if x.get("id") == pid), None)
        if not pr:
            raise ValueError("preset não encontrado")
        modelo = (pr["nome"], pr["largura"], pr["altura"])
        fps = pr["fps"]
        cores_preset = {"timeline": pr["timeline"], "saida": pr["saida"]}
    else:
        modelo = MODELOS_TIMELINE.get(p.get("modelo"))
        if not modelo:
            raise ValueError("modelo desconhecido")
    base, largura, altura = modelo
    base = (p.get("nome") or "").strip()[:80] or base
    proj = resolve().GetProjectManager().GetCurrentProject()
    if not proj:
        raise ValueError("Nenhum projeto aberto no DaVinci.")
    usados = {proj.GetTimelineByIndex(i).GetName() for i in range(1, proj.GetTimelineCount() + 1)}
    nome, n = base, 1
    while nome in usados:  # o DaVinci recusa nomes repetidos
        n += 1
        nome = f"{base} {n}"
    mp = proj.GetMediaPool()
    raiz = mp.GetRootFolder()
    pasta = next((f for f in raiz.GetSubFolderList() or [] if f.GetName() == "Timelines"), None) or mp.AddSubFolder(raiz, "Timelines")
    mp.SetCurrentFolder(pasta)  # a timeline nova entra direto nesta pasta do media pool
    tl = mp.CreateEmptyTimeline(nome)
    mp.SetCurrentFolder(raiz)
    if not tl:
        raise ValueError("Não consegui criar a timeline.")
    tl.SetSetting("useCustomSettings", "1")
    for kk, vv in (("timelineResolutionWidth", str(largura)), ("timelineResolutionHeight", str(altura)),
                   ("timelineFrameRate", fps), ("colorScienceMode", "davinciYRGB")):
        tl.SetSetting(kk, vv)
    cores = p.get("cores") or cores_preset
    campos = {"timeline": "colorSpaceTimeline", "saida": "colorSpaceOutput"}
    recusadas = []
    for chave, config in campos.items():
        valor = cores.get(chave) or {"timeline": "Rec.709 (Scene)", "saida": "Same as Timeline"}.get(chave, "Rec.709")
        if not tl.SetSetting(config, valor):
            recusadas.append(valor)
    proj.SetCurrentTimeline(tl)
    msg = f"Timeline '{nome}' criada na pasta Timelines e aberta no DaVinci."
    if recusadas:
        msg += f" O DaVinci não aceitou estes espaços de cor: {', '.join(recusadas)}."
    return {"ok": True, "msg": msg}


def importar_trilha(p):
    """Traz um arquivo baixado para a pasta Trilhas do media pool do DaVinci (sem mexer na timeline)."""
    pasta = pasta_downloads().resolve()
    alvo = (pasta / (p.get("nome") or "")).resolve()
    if pasta not in alvo.parents or not alvo.is_file():
        raise ValueError("arquivo não encontrado")
    proj = resolve().GetProjectManager().GetCurrentProject()
    if not proj:
        raise ValueError("Nenhum projeto aberto no DaVinci.")
    mp = proj.GetMediaPool()
    raiz = mp.GetRootFolder()
    trilhas = next((f for f in raiz.GetSubFolderList() or [] if f.GetName() == "Trilhas"), None)
    if not trilhas:
        trilhas = mp.AddSubFolder(raiz, "Trilhas")
    mp.SetCurrentFolder(trilhas)
    if not mp.ImportMedia([str(alvo)]):
        raise ValueError("O DaVinci não conseguiu importar esse arquivo.")
    return {"ok": True, "msg": f"'{alvo.name}' importado na pasta Trilhas do media pool."}


def info_link(p):
    """Lê título, canal, duração e capa de um link. Não baixa nada."""
    from baixar import verificar
    url = (p.get("url") or "").strip()
    try:
        verificar(url)
    except RuntimeError as e:
        return {"ok": False, "msg": str(e)}
    import yt_dlp
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "noplaylist": True,
                               "extractor_args": {"youtube": {"player_client": ["android"]}}}) as y:
            i = y.extract_info(url, download=False)
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if "not a bot" in msg or "Sign in" in msg:
            msg = "O YouTube bloqueou a leitura deste link. Tente de novo mais tarde."
        return {"ok": False, "msg": msg[:200]}
    return {"ok": True, "titulo": i.get("title"), "canal": i.get("channel") or i.get("uploader"),
            "duracao": i.get("duration"), "miniatura": i.get("thumbnail")}


CONFIG_APP = PROJETOS / "_config_app.json"
PADROES_APP = {"formato_audio": "mp3", "qualidade": "best", "tocar_ao_abrir": True, "importar_auto": False, "cor_onda": "mono"}
OPCOES_APP = {"formato_audio": ("mp3", "wav"), "qualidade": ("best", "1080", "720", "480"), "cor_onda": ("mono", "azul", "verde")}


def ler_config_app():
    try:
        dados = json.loads(CONFIG_APP.read_text())
    except (OSError, ValueError):
        dados = {}
    return {**PADROES_APP, **{k: v for k, v in dados.items() if k in PADROES_APP}}


APP_ATALHO = Path.home() / "Desktop" / "Abrir Agiliza-Zé.app"


def atalho_mesa(p):
    """Liga ou desliga o app 'Abrir Agiliza-Zé' na Mesa (abre o plugin pelo menu do DaVinci)."""
    import shutil
    if p.get("ligar"):
        if not APP_ATALHO.exists():
            r = subprocess.run(["osacompile", "-o", str(APP_ATALHO), str(BASE / "atalho" / "abrir_agiliza.applescript")],
                               capture_output=True, text=True)
            if r.returncode != 0:
                return {"ok": False, "msg": "Não consegui criar o atalho na Mesa."}
    elif APP_ATALHO.exists():
        shutil.rmtree(APP_ATALHO)
    return {"ok": True, "ligado": APP_ATALHO.exists()}


def ver_config(_p):
    return {"ok": True, "config": {**ler_config_app(), "pasta": str(pasta_downloads()), "atalho_mesa": APP_ATALHO.exists()}}


def salvar_config(p):
    cfg = ler_config_app()
    for k, v in p.items():
        if k not in PADROES_APP:
            continue
        if k in OPCOES_APP:
            if v not in OPCOES_APP[k]:
                raise ValueError(f"valor inválido para {k}")
        elif not isinstance(v, bool):
            raise ValueError(f"valor inválido para {k}")
        cfg[k] = v
    PROJETOS.mkdir(parents=True, exist_ok=True)
    CONFIG_APP.write_text(json.dumps(cfg, ensure_ascii=False))
    return {"ok": True, "config": cfg}


def atualizar_motor(_p):
    """Atualiza o yt-dlp do projeto (o YouTube muda com frequência e o motor precisa acompanhar)."""
    py = str(BASE / ".venv" / "bin" / "python")
    r = subprocess.run([py, "-m", "pip", "install", "-U", "-q", "yt-dlp"], capture_output=True, text=True, timeout=240)
    if r.returncode != 0:
        return {"ok": False, "msg": "Não consegui atualizar o motor agora. Tente de novo mais tarde."}
    v = subprocess.run([py, "-c", "import yt_dlp; print(yt_dlp.version.__version__)"], capture_output=True, text=True)
    return {"ok": True, "msg": f"Motor atualizado (yt-dlp {v.stdout.strip()})."}


def bpm(p):
    """Estima o BPM de um download pelo pulso do áudio (lê o arquivo local, não baixa nada)."""
    import numpy as np
    pasta = pasta_downloads().resolve()
    alvo = (pasta / (p.get("nome") or "")).resolve()
    if pasta not in alvo.parents or not alvo.is_file():
        raise ValueError("arquivo não encontrado")
    r = subprocess.run([str(BASE / ".venv" / "bin" / "ffmpeg"), "-hide_banner", "-loglevel", "error", "-i", str(alvo),
                        "-vn", "-ac", "1", "-ar", "8000", "-f", "f32le", "-"], capture_output=True)
    x = np.frombuffer(r.stdout, dtype=np.float32)
    if r.returncode != 0 or x.size < 8000 * 5:
        raise ValueError("áudio curto demais para medir o BPM")
    win, hop = 320, 80                     # 40 ms de janela, 10 ms de passo: 100 quadros por segundo
    n = (x.size - win) // hop
    quadros = x[np.arange(win)[None, :] + hop * np.arange(n)[:, None]]
    e = np.log1p(np.sqrt((quadros ** 2).mean(axis=1)) * 100)
    pulso = np.maximum(np.diff(e), 0)      # subidas de energia = ataques da música
    pulso = pulso - pulso.mean()
    if not np.any(pulso):
        raise ValueError("não encontrei pulso nesse áudio")
    f = np.fft.rfft(pulso, 2 * pulso.size)
    ac = np.fft.irfft(f * np.conj(f))[: pulso.size]
    fr = 100
    lags = np.arange(int(fr * 60 / 200), int(fr * 60 / 60) + 1)   # de 200 a 60 BPM
    notas = ac[lags] / ac[0]
    bpms = 60 * fr / lags
    prior = np.exp(-0.5 * ((np.log2(bpms) - np.log2(120)) / 0.9) ** 2)  # prefere a faixa usual de música
    i = int(np.argmax(notas * prior))
    return {"ok": True, "bpm": round(float(bpms[i]), 1), "confianca": round(float(max(0, min(1, notas[i]))), 2)}


NOTAS_PT = ["Dó", "Dó#", "Ré", "Ré#", "Mi", "Fá", "Fá#", "Sol", "Sol#", "Lá", "Lá#", "Si"]
PERFIL_MAIOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]   # Krumhansl-Kessler
PERFIL_MENOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]


def tom_do_audio(y, sr):
    """Tom mais provável (ex.: 'Mi maior') a partir do cromagrama CQT (librosa) e dos perfis de Krumhansl."""
    import numpy as np
    import librosa
    cromo = librosa.feature.chroma_cqt(y=y, sr=sr).mean(axis=1)
    if not np.any(cromo):
        raise ValueError("não encontrei notas nesse áudio")
    cromo = cromo / cromo.sum()
    melhores = []
    for t in range(12):
        for nome, perfil in (("maior", PERFIL_MAIOR), ("menor", PERFIL_MENOR)):
            p = np.roll(np.array(perfil), t)
            melhores.append((float(np.corrcoef(cromo, p)[0, 1]), f"{NOTAS_PT[t]} {nome}"))
    melhores.sort(reverse=True)
    return melhores[0][1], round(max(0.0, min(1.0, melhores[0][0])), 2)


def tom(p):
    """Estima o tom da música de um download (lê o arquivo local, não baixa nada)."""
    import numpy as np
    pasta = pasta_downloads().resolve()
    alvo = (pasta / (p.get("nome") or "")).resolve()
    if pasta not in alvo.parents or not alvo.is_file():
        raise ValueError("arquivo não encontrado")
    r = subprocess.run([str(BASE / ".venv" / "bin" / "ffmpeg"), "-hide_banner", "-loglevel", "error", "-i", str(alvo),
                        "-vn", "-ac", "1", "-ar", "22050", "-f", "f32le", "-"], capture_output=True)
    x = np.frombuffer(r.stdout, dtype=np.float32)
    if r.returncode != 0 or x.size < 22050 * 5:
        raise ValueError("áudio curto demais para medir o tom")
    nome_tom, conf = tom_do_audio(x, 22050)
    return {"ok": True, "tom": nome_tom, "confianca": conf}


def forma_onda(p):
    """Picos do áudio de um download, para desenhar a onda no player (lê o arquivo local, não baixa nada)."""
    import numpy as np
    pasta = pasta_downloads().resolve()
    alvo = (pasta / (p.get("nome") or "")).resolve()
    if pasta not in alvo.parents or not alvo.is_file():
        raise ValueError("arquivo não encontrado")
    r = subprocess.run([str(BASE / ".venv" / "bin" / "ffmpeg"), "-hide_banner", "-loglevel", "error", "-i", str(alvo),
                        "-vn", "-ac", "1", "-ar", "8000", "-f", "f32le", "-"], capture_output=True)
    x = np.frombuffer(r.stdout, dtype=np.float32)
    if r.returncode != 0 or x.size == 0:
        raise ValueError("não consegui ler o áudio desse arquivo")
    bins = 500
    seg = max(1, x.size // bins)
    picos = np.abs(x[: seg * bins]).reshape(bins, seg).max(axis=1)
    if picos.max() > 0:
        picos = picos / picos.max()
    return {"ok": True, "picos": [round(float(v), 3) for v in picos], "duracao": round(x.size / 8000, 2), "tamanho": alvo.stat().st_size}


def reanalisar(p):
    """Refaz só a análise (ganchos, roteiro) reaproveitando a transcrição do projeto."""
    pasta = (PROJETOS / p.get("projeto", "")).resolve()
    if PROJETOS not in pasta.parents or not (pasta / "transcricao.json").exists():
        raise ValueError("projeto não encontrado")
    nome = json.loads((pasta / "transcricao.json").read_text()).get("projeto") or pasta.name
    cmd = [str(BASE / ".venv" / "bin" / "python"), str(BASE / "pipeline.py"), "--reanalisar", "--nome", nome]
    if p.get("obs"):
        cmd += ["--obs", p["obs"]]
    subprocess.Popen(cmd, cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return {"ok": True, "msg": "Refazendo a análise."}


def melhorar_audio(p):
    """Analisa e melhora o áudio de voz da timeline aberta (melhorar_audio.py), na própria timeline."""
    import time
    pasta = PROJETOS / "_sync"
    pasta.mkdir(parents=True, exist_ok=True)
    st = pasta / f"audio_{time.strftime('%Y%m%d_%H%M%S')}.json"
    cmd = [str(BASE / ".venv" / "bin" / "python"), str(BASE / "melhorar_audio.py"), "--status", str(st),
           "--alvo", str(float(p.get("alvo") or -16)), "--cameras", "abaixar" if p.get("cameras") else "manter",
           "--isolamento", str(p.get("isolamento") or "auto"), "--silencios", str(float(p.get("silencios") or 0))]
    if p.get("prompt"):
        cmd += ["--prompt", p["prompt"]]
    if p.get("ref"):
        cmd += ["--ref", str(int(p["ref"]))]
    if p.get("teste"):
        cmd += ["--teste"]
    subprocess.Popen(cmd, cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return {"ok": True, "msg": "Análise de áudio iniciada."}


def stabilizar(p):
    """Stabilizer: mede o tremor dos clipes da timeline aberta e, se pedido, estabiliza os que tremem (stabilizar.py)."""
    import time
    pasta = PROJETOS / "_sync"
    pasta.mkdir(parents=True, exist_ok=True)
    st = pasta / f"{time.strftime('%Y%m%d_%H%M%S')}_stabilizer.json"
    modo = "aplicar" if p.get("modo") == "aplicar" else "analisar"
    sens = p.get("sensibilidade") if p.get("sensibilidade") in ("leve", "medio", "forte") else "medio"
    cmd = [str(BASE / ".venv" / "bin" / "python"), str(BASE / "stabilizar.py"), "--modo", modo,
           "--sensibilidade", sens, "--status", str(st)] + ["--so-selecionados"] + (["--forcar"] if p.get("forcar") else [])  # sempre só o que está selecionado
    subprocess.Popen(cmd, cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return {"ok": True, "msg": ("Estabilizando" if modo == "aplicar" else "Analisando") + " — acompanhe em Atividade."}


def predecupar(p):
    """Pré-decupagem: identifica os momentos pelas imagens e cria uma timeline por momento (predecupar.py)."""
    import time
    pasta = PROJETOS / "_sync"
    pasta.mkdir(parents=True, exist_ok=True)
    st = pasta / f"predec_{time.strftime('%Y%m%d_%H%M%S')}.json"
    cmd = [str(BASE / ".venv" / "bin" / "python"), str(BASE / "predecupar.py"), "--status", str(st),
           "--tipo", p.get("tipo") or "casamento"]
    if p.get("momentos"):
        cmd += ["--momentos", p["momentos"]]
    if p.get("identificar"):
        cmd += ["--identificar"]
    if p.get("unica"):
        cmd += ["--unica"]
    subprocess.Popen(cmd, cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return {"ok": True, "msg": "Organizador de Momentos iniciado."}


def jobs(_p):
    """Análises em andamento ou concluídas há pouco."""
    import time
    out = []
    for f in list(PROJETOS.glob("*/_status.json")) + list(PROJETOS.glob("_sync/*.json")):
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        if not d.get("fim") or time.time() - d["fim"] < 3600:
            if d.get("tipo") == "sync":
                d["projeto"] = "_sync/" + f.name
            out.append(d)
    return {"ok": True, "jobs": sorted(out, key=lambda d: -d.get("inicio", 0))}


def status(_p):
    try:
        proj = resolve().GetProjectManager().GetCurrentProject()
        return {"ok": True, "resolve": True, "projeto": proj.GetName()}
    except Exception:
        return {"ok": True, "resolve": False}


ROTAS = {"/api/predecupar": predecupar, "/api/melhorar_audio": melhorar_audio, "/api/reanalisar": reanalisar, "/api/sincronizar": sincronizar, "/api/multicam": multicam, "/api/baixar": baixar, "/api/downloads": downloads, "/api/abrir_pasta": abrir_pasta, "/api/importar_trilha": importar_trilha, "/api/criar_timeline": criar_timeline, "/api/presets": listar_presets, "/api/stabilizar": stabilizar, "/api/hackedit": listar_hackedit, "/api/salvar_hackedit": salvar_hackedit, "/api/excluir_hackedit": excluir_hackedit, "/api/acao_hackedit": acao_hackedit, "/api/analisar_hackedit": analisar_referencia, "/api/salvar_preset": salvar_preset, "/api/excluir_preset": excluir_preset, "/api/trocar_pasta": trocar_pasta_downloads, "/api/ver_pasta": ver_pasta_downloads, "/api/info_link": info_link, "/api/forma_onda": forma_onda, "/api/bpm": bpm, "/api/tom": tom, "/api/ver_config": ver_config, "/api/salvar_config": salvar_config, "/api/atalho_mesa": atalho_mesa, "/api/atualizar_motor": atualizar_motor, "/api/apagar": apagar, "/api/analisar": analisar, "/api/cancelar": cancelar, "/api/jobs": jobs, "/api/resolve_info": resolve_info, "/api/cortar": cortar, "/api/davinci": para_davinci, "/api/montar_roteiro": montar_roteiro_davinci, "/api/localizar": localizar, "/api/status": status}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(PROJETOS), **kw)

    def log_message(self, *a):
        pass

    def _json(self, codigo, dados):
        corpo = json.dumps(dados, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_POST(self):
        if self.path.startswith("/api/upload_hackedit"):
            return self._upload_hackedit()
        if self.path.startswith("/api/transcrever_pedido"):
            return self._transcrever_pedido()
        rota = ROTAS.get(self.path)
        if not rota:
            return self._json(404, {"ok": False, "msg": "rota desconhecida"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            self._json(200, rota(json.loads(self.rfile.read(n) or b"{}")))
        except Exception as e:  # noqa: BLE001
            self._json(200, {"ok": False, "msg": str(e)})

    def _transcrever_pedido(self):
        """Recebe um trecho de voz gravado no navegador (corpo bruto, webm/ogg/mp4) e devolve o texto (Whisper local)."""
        import tempfile
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return self._json(200, {"ok": False, "msg": "Nenhum áudio foi gravado."})
        corpo = self.rfile.read(n)
        with tempfile.TemporaryDirectory() as tmp:
            bruto = Path(tmp) / "gravacao.webm"
            bruto.write_bytes(corpo)
            wav = Path(tmp) / "fala.wav"
            r = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", str(bruto),
                                "-vn", "-ac", "1", "-ar", "16000", str(wav)], capture_output=True, text=True)
            if r.returncode or not wav.exists():
                return self._json(200, {"ok": False, "msg": "Não consegui ler a gravação."})
            try:
                import mlx_whisper
                res = mlx_whisper.transcribe(str(wav), path_or_hf_repo="mlx-community/whisper-large-v3-turbo",
                                             language="pt", condition_on_previous_text=False, verbose=False)
            except Exception as e:  # noqa: BLE001
                return self._json(200, {"ok": False, "msg": f"Transcrição falhou: {e}"})
        texto = " ".join((res.get("text") or "").split())
        if not texto:
            return self._json(200, {"ok": False, "msg": "Não ouvi fala nessa gravação."})
        self._json(200, {"ok": True, "texto": texto})

    def _upload_hackedit(self):
        """Recebe um vídeo seu (corpo bruto) e guarda como referência do HackEdit."""
        import re as _re
        import time as _time
        import uuid as _uuid
        from urllib.parse import parse_qs, unquote, urlparse
        q = parse_qs(urlparse(self.path).query)
        nome = unquote(q.get("nome", [""])[0]).strip()[:60]
        arq_nome = unquote(q.get("arquivo", ["video"])[0])
        n = int(self.headers.get("Content-Length") or 0)
        if not nome:
            return self._json(200, {"ok": False, "msg": "Dê um nome à referência."})
        if n <= 0:
            return self._json(200, {"ok": False, "msg": "Arquivo vazio."})
        pasta = PROJETOS / "_hackedit" / "arquivos"
        pasta.mkdir(parents=True, exist_ok=True)
        uid = _uuid.uuid4().hex[:8]
        seguro = _re.sub(r"[^\w.\- ]", "_", arq_nome)[-120:] or "video"
        destino = pasta / f"{uid}_{seguro}"
        restante = n
        with open(destino, "wb") as f:
            while restante > 0:
                bloco = self.rfile.read(min(1 << 20, restante))
                if not bloco:
                    break
                f.write(bloco)
                restante -= len(bloco)
        if restante > 0:
            destino.unlink(missing_ok=True)
            return self._json(200, {"ok": False, "msg": "O envio foi interrompido. Tente de novo."})
        projeto = ""
        try:
            projeto = resolve().GetProjectManager().GetCurrentProject().GetName()
        except Exception:  # noqa: BLE001
            pass
        lista = ler_hackedit()
        lista.append({"id": uid, "nome": nome, "link": "", "arquivo": str(destino.relative_to(PROJETOS)),
                      "arquivo_nome": seguro, "projeto": projeto, "criado": _time.strftime("%d/%m/%Y %H:%M")})
        HACKEDIT_ARQ.write_text(json.dumps(lista, ensure_ascii=False))
        self._json(200, {"ok": True, "msg": f"Vídeo '{nome}' guardado como referência."})

    def do_GET(self):
        if self.path == "/api/status":
            return self._json(200, status({}))
        if self.path in ("/api/jobs", "/api/resolve_info"):
            try:
                return self._json(200, ROTAS[self.path]({}))
            except Exception as e:  # noqa: BLE001
                return self._json(200, {"ok": False, "msg": str(e)})
        if self.path in ("/", "/index.html"):
            import importlib
            import pagina_inicial
            importlib.reload(pagina_inicial)  # relê a tela a cada carregamento: mudanças entram com o Atualizar
            corpo = pagina_inicial.pagina_inicial(PROJETOS).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            return self.wfile.write(corpo)
        if self.path.startswith("/api/arquivo?"):
            from urllib.parse import parse_qs, urlparse
            nome = parse_qs(urlparse(self.path).query).get("nome", [""])[0]
            pasta = pasta_downloads().resolve()
            alvo = (pasta / nome).resolve()
            if pasta not in alvo.parents or not alvo.is_file():
                return self.send_error(404)
            return self._parcial(alvo, self.headers.get("Range") or "bytes=0-")
        caminho = Path(self.translate_path(self.path))
        rng = self.headers.get("Range")
        if rng and caminho.is_file():
            return self._parcial(caminho, rng)
        return super().do_GET()

    def _parcial(self, caminho, rng):
        """Suporte a Range: o player do navegador precisa disso para pular no vídeo."""
        tam = caminho.stat().st_size
        m = re.match(r"bytes=(\d*)-(\d*)", rng)
        ini = int(m[1]) if m and m[1] else 0
        fim = int(m[2]) if m and m[2] else tam - 1
        fim = min(fim, tam - 1, ini + 8 * 1024 * 1024 - 1)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(str(caminho)))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {ini}-{fim}/{tam}")
        self.send_header("Content-Length", str(fim - ini + 1))
        self.end_headers()
        with open(caminho, "rb") as f:
            f.seek(ini)
            restante = fim - ini + 1
            while restante > 0:
                bloco = f.read(min(1024 * 1024, restante))
                if not bloco:
                    break
                try:
                    self.wfile.write(bloco)
                except (BrokenPipeError, ConnectionResetError):
                    return
                restante -= len(bloco)


if __name__ == "__main__":
    print(f"Agiliza-Zé rodando em http://localhost:{PORTA}  (Ctrl+C para parar)")
    ThreadingHTTPServer(("127.0.0.1", PORTA), Handler).serve_forever()
