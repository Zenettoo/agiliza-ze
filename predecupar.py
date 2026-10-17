#!/usr/bin/env python3
"""Pré-decupagem automática do projeto aberto no DaVinci.

Parte do media pool com as brutas separadas por câmera (uma pasta por câmera). Para cada clipe pega um quadro,
monta folhas de miniaturas por câmera (em ordem de gravação) e pede ao Claude para identificar os momentos
(decoração, making of, cerimônia, festa…). Depois cria uma timeline por momento — 1080p, 24 fps, Rec.709 (Scene) —
com a câmera A inteira, depois a B, depois a C…, e pinta os clipes com a cor do momento.

Uso: .venv/bin/python predecupar.py [--status arq.json] [--teste]   (--teste: classifica mas não cria nada)
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

os.environ.setdefault("PYTHONUTF8", "1")
BASE = Path(__file__).resolve().parent
FFMPEG = str(BASE / ".venv" / "bin" / "ffmpeg")
CLAUDE = next((str(c) for c in [Path.home() / ".local" / "bin" / "claude"] if c.exists()), "claude")
sys.path.append("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules")
os.environ.setdefault("RESOLVE_SCRIPT_LIB",
                      "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so")

sys.path.insert(0, str(BASE))
from tipos import momentos as lista_momentos, nome_tipo  # noqa: E402

MOMENTOS = []  # preenchido em main() conforme o tipo de trabalho
COR = {}
POR_FOLHA, COLS, TW, TH = 24, 6, 360, 203


class Status:
    def __init__(self, arq):
        self.arq = Path(arq) if arq else None
        self.d = {"nome": "Organizador de Momentos", "projeto": "_sync", "tipo": "sync", "inicio": time.time(), "pid": os.getpid(),
                  "etapa": "", "msg": "", "pct": 0, "erro": None, "fim": None}

    def __call__(self, etapa, msg, pct, **kw):
        self.d.update(etapa=etapa, msg=msg, pct=pct, **kw)
        if self.arq:
            self.arq.parent.mkdir(parents=True, exist_ok=True)
            self.arq.write_text(json.dumps(self.d, ensure_ascii=False))
        print(f"[{pct:3d}%] {etapa}: {msg}", flush=True)


def ler_json_tolerante(arq):
    """Lê o primeiro objeto JSON do arquivo, ignorando texto ou colchetes sobrando depois dele (o Claude às vezes deixa)."""
    texto = Path(arq).read_text(encoding="utf-8")
    obj, _ = json.JSONDecoder().raw_decode(texto[texto.index("{"):])
    return obj


def data(c):
    for k in ("Date Created", "Date Modified"):
        v = c.GetClipProperty(k) or ""
        for fmt in ("%a %b %d %Y %H:%M:%S", "%a %b %d %H:%M:%S %Y"):
            try:
                return datetime.strptime(v.strip(), fmt)
            except ValueError:
                pass
    return None


def segundos(tc, fps):
    try:
        h, m, s, f = [int(x) for x in re.split(r"[:;]", tc)]
        return h * 3600 + m * 60 + s + f / max(1, round(fps))
    except Exception:
        return 0.0


def cameras(mp):
    """Pastas do media pool que têm vídeo (cada uma = uma câmera), na ordem em que aparecem."""
    out = []

    def varrer(f, caminho):
        clips = [c for c in (f.GetClipList() or []) if "Video" in (c.GetClipProperty("Type") or "")
                 and c.GetClipProperty("File Path")]
        if clips and "(Claude)" not in caminho and "MOMENTOS" not in caminho:
            out.append((f.GetName(), clips))
        for s in f.GetSubFolderList() or []:
            varrer(s, caminho + "/" + s.GetName())
    varrer(mp.GetRootFolder(), "")
    return out


def eh_drone(nome_pasta, clips):
    if "drone" in nome_pasta.lower() or "dji" in nome_pasta.lower():
        return True
    nomes = [c.GetName().upper() for c in clips]
    return bool(nomes) and sum(n.startswith("DJI") for n in nomes) > len(nomes) / 2


def miniatura(arq, meio, destino):
    if destino.exists() and destino.stat().st_size > 0:
        return destino
    vf = f"scale={TW - 2}:{TH - 2}:force_original_aspect_ratio=decrease,pad={TW}:{TH}:(ow-iw)/2:(oh-ih)/2"
    for ss in (meio, 0.0):  # se o quadro do meio falhar, tenta o primeiro
        subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{ss:.2f}", "-i", arq,
                        "-frames:v", "1", "-vf", vf, "-q:v", "5", str(destino)], capture_output=True)
        if destino.exists() and destino.stat().st_size > 0:
            break
    return destino


def folhas(cam, itens, pasta):
    from PIL import Image, ImageDraw, ImageFont
    try:
        fonte = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 22)
    except Exception:
        fonte = ImageFont.load_default()
    caminhos = []
    for k in range(0, len(itens), POR_FOLHA):
        lote = itens[k:k + POR_FOLHA]
        linhas = (len(lote) + COLS - 1) // COLS
        img = Image.new("RGB", (COLS * TW, linhas * TH), (20, 20, 20))
        d = ImageDraw.Draw(img)
        for j, x in enumerate(lote):
            pos = ((j % COLS) * TW, (j // COLS) * TH)
            try:
                img.paste(Image.open(x["thumb"]).convert("RGB"), pos)
            except Exception:
                pass
            rot = f"{x['cam_id']}"
            d.rectangle([pos[0], pos[1], pos[0] + 14 * len(rot) + 10, pos[1] + 30], fill=(0, 0, 0))
            d.text((pos[0] + 5, pos[1] + 3), rot, fill=(255, 220, 0), font=fonte)
        f = pasta / f"{re.sub(r'[^A-Za-z0-9]+', '_', cam)}_{k // POR_FOLHA + 1:02d}.jpg"
        img.save(f, quality=80)
        caminhos.append(f)
    return caminhos


def ja_organizados(proj):
    """Timelines de momento que já existem no projeto e os clipes que já estão nelas (pelo id do media pool)."""
    nomes = {m.upper(): m for m, _ in MOMENTOS}
    tls, usados = {}, set()
    for i in range(1, proj.GetTimelineCount() + 1):
        t = proj.GetTimelineByIndex(i)
        mm = re.match(r"^(\d{2}) (.+)$", t.GetName() or "")
        if mm and mm.group(2).startswith("DECUPAGEM"):  # timeline única de decupagem: também conta como já organizada
            tls.setdefault("__unica__", t)
        elif not mm or mm.group(2) not in nomes:
            continue
        else:
            tls[nomes[mm.group(2)]] = t
        for k in range(1, t.GetTrackCount("video") + 1):
            for it in t.GetItemListInTrack("video", k) or []:
                m = it.GetMediaPoolItem()
                if m:
                    usados.add(m.GetUniqueId())
    return tls, usados


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status")
    ap.add_argument("--teste", action="store_true")
    ap.add_argument("--identificar", action="store_true", help="só pinta e marca os clipes no media pool, sem timelines")
    ap.add_argument("--unica", action="store_true", help="coloca tudo numa timeline só, na ordem dos momentos")
    ap.add_argument("--tipo", default="casamento")
    ap.add_argument("--momentos", default="", help="tipo personalizado: momentos separados por vírgula")
    args = ap.parse_args()
    global MOMENTOS, COR
    m3 = lista_momentos(args.tipo, args.momentos)
    MOMENTOS = [(n, c) for n, c, _ in m3]
    COR = dict(MOMENTOS)
    DESCR = "\n".join(f"  - {n}: {d}" if d else f"  - {n}" for n, _, d in m3)
    st = Status(args.status)
    try:
        import DaVinciResolveScript as d  # noqa: N813
        r = d.scriptapp("Resolve")
        proj = r.GetProjectManager().GetCurrentProject()
        mp = proj.GetMediaPool()
        st.d["nome"] = f"Organizador de Momentos · {proj.GetName()} · {nome_tipo(args.tipo)}"
        st("Lendo", "Lendo as pastas de câmera do media pool…", 2)
        cams = cameras(mp)
        if not cams:
            raise RuntimeError("Não achei pastas com vídeo no media pool. Crie uma pasta por câmera e importe as brutas.")

        pasta = BASE / "projetos" / "_predec" / re.sub(r"[^A-Za-z0-9]+", "_", proj.GetName())
        (pasta / "thumbs").mkdir(parents=True, exist_ok=True)
        itens, por_id = [], {}
        drones = [(cam, clips) for cam, clips in cams if eh_drone(cam, clips)]
        cams = [(cam, clips) for cam, clips in cams if not eh_drone(cam, clips)] + drones  # drone sempre por último
        n_cam = 0
        for cam, clips in cams:
            drone = eh_drone(cam, clips)
            if drone:
                n_drone = locals().get("n_drone", 0) + 1
                letra = f"DRONE{n_drone}"
            else:
                letra = chr(ord("A") + n_cam)
                n_cam += 1
            lista = []
            for c in clips:
                fps = float(c.GetClipProperty("FPS") or 24)
                dur = segundos(c.GetClipProperty("Duration") or "0:0:0:0", fps)
                lista.append({"m": c, "cam": cam, "letra": letra, "arq": c.GetClipProperty("File Path"),
                              "nome": c.GetName(), "data": data(c), "dur": dur, "drone": drone})
            lista.sort(key=lambda x: (x["data"] or datetime.min, x["nome"]))
            for k, x in enumerate(lista, 1):
                x["cam_id"] = f"{letra}{k}" if not drone else f"{letra}-{k}"
                x["thumb"] = pasta / "thumbs" / f"{x['cam_id']}.jpg"
                por_id[x["cam_id"]] = x
            itens.append((cam, letra, lista))
        tls_existentes, ja_na_timeline = ja_organizados(proj)
        itens = [(cam, letra, [x for x in lst if x["m"].GetUniqueId() not in ja_na_timeline]) for cam, letra, lst in itens]
        por_id = {k: v for k, v in por_id.items() if v["m"].GetUniqueId() not in ja_na_timeline}
        novos = sum(len(lst) for _, _, lst in itens)
        if novos == 0:
            st("Concluído", f"Nada novo para organizar: os {len(ja_na_timeline)} take(s) já estão nas timelines de momento.",
               100, fim=time.time())
            return
        cam_itens = [t for t in itens if not t[2] or not t[2][0]["drone"]]
        total = max(1, sum(len(lst) for _, _, lst in itens if lst and not lst[0]["drone"]))

        st("Quadros", f"Tirando um quadro de cada um dos {total} clipes…", 5)
        feitos = 0
        with ThreadPoolExecutor(6) as ex:
            futs = [ex.submit(miniatura, x["arq"], max(0.5, x["dur"] * 0.4), x["thumb"]) for _, _, lst in cam_itens for x in lst]
            for _ in futs:
                _.result()
                feitos += 1
                if feitos % 20 == 0:
                    st("Quadros", f"Quadros: {feitos} de {total}…", 5 + int(35 * feitos / total))
        todas = []
        for cam, letra, lst in cam_itens:
            todas += folhas(cam, lst, pasta)

        st("Identificando", f"O Claude está olhando {len(todas)} folhas de miniaturas e separando os momentos…", 45)
        linhas = []
        for cam, letra, lst in cam_itens:
            linhas.append(f"\n## Câmera {letra} = pasta '{cam}' ({len(lst)} clipes, em ordem de gravação)")
            for x in lst:
                h = x["data"].strftime("%H:%M:%S") if x["data"] else "?"
                linhas.append(f"{x['cam_id']} · {h} · {x['dur']:.0f}s · {x['nome']}")
        txt_clipes = "\n".join(linhas) + f"\n# tipo: {args.tipo} {args.momentos}"
        reaproveita = ((pasta / "clipes.txt").exists() and (pasta / "clipes.txt").read_text() == txt_clipes
                       and (pasta / "classificacao.json").exists())
        (pasta / "clipes.txt").write_text(txt_clipes)
        nomes = ", ".join(m for m, _ in MOMENTOS)
        prompt = f"""Você faz a pré-decupagem de um trabalho do tipo "{nome_tipo(args.tipo)}". Responda em português.
Nesta pasta: `clipes.txt` (lista dos clipes por câmera, em ordem de gravação: id · hora · duração · arquivo) e
{len(todas)} folhas de miniaturas `*.jpg` (um quadro por clipe, com o id em amarelo no canto). Leia o clipes.txt e
TODAS as folhas (Read em cada .jpg).

Classifique cada clipe em UM destes momentos (use exatamente estes nomes):
{DESCR}
- Os relógios das câmeras NÃO batem entre si; dentro de cada câmera a ordem é cronológica e os momentos vêm em blocos.
  Use a sequência para decidir casos ambíguos (um clipe isolado no meio de um bloco quase sempre é do mesmo momento).
- Pasta chamada Drone/DJI → Drone.

Escreva `classificacao.json` nesta pasta, por blocos contínuos de cada câmera (ids da mesma câmera):
{{"blocos": [{{"de": "A1", "ate": "A57", "momento": "{MOMENTOS[0][0]}"}}, {{"de": "A58", "ate": "A60", "momento": "{MOMENTOS[1][0]}"}}, ...],
 "resumo": "2–3 frases sobre o que você viu"}}
Cubra TODOS os ids de todas as câmeras. JSON válido, sem comentários. Ao terminar responda só "pronto"."""
        if reaproveita:
            st("Identificando", "Reaproveitando a classificação já feita para este projeto…", 70)
            rr = None
        else:
          rr = subprocess.run([CLAUDE, "-p", prompt, "--allowedTools", "Read,Write", "--permission-mode", "acceptEdits",
                             "--output-format", "text"], cwd=pasta, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=5400)
        if rr is not None and "Not logged in" in (rr.stdout + rr.stderr):
            raise RuntimeError("O Claude Code não está logado. No Terminal: ~/.local/bin/claude auth login")
        cl = ler_json_tolerante(pasta / "classificacao.json")

        def chave(i):
            return i[0], int(i[1:])
        for b in cl.get("blocos", []):
            if b.get("momento") not in COR:
                b["momento"] = "Revisar"
            l1, n1 = chave(b["de"])
            l2, n2 = chave(b["ate"])
            for n in range(n1, n2 + 1):
                x = por_id.get(f"{l1}{n}")
                if x:
                    x["momento"] = b["momento"]
        for x in por_id.values():
            if x["drone"]:
                x["momento"] = "Drone"
            x.setdefault("momento", "Revisar")
        contagem = {}
        for x in por_id.values():
            contagem[x["momento"]] = contagem.get(x["momento"], 0) + 1
        resumo = " · ".join(f"{m} {contagem[m]}" for m, _ in MOMENTOS if m in contagem)
        if args.teste:
            print(json.dumps({"contagem": contagem, "resumo": cl.get("resumo")}, ensure_ascii=False, indent=1))
            st("Concluído", "Teste: " + resumo + " (nada foi criado)", 100, fim=time.time())
            return
        st("Marcando", "Pintando os clipes no media pool e gravando o momento nas Keywords…", 75)
        for x in por_id.values():
            x["m"].SetClipColor(COR[x["momento"]])
            kw = [k.strip() for k in (x["m"].GetMetadata("Keywords") or "").split(",") if k.strip()]
            kw = [k for k in kw if k not in COR] + [x["momento"]]  # troca o momento antigo, mantém as suas keywords
            x["m"].SetMetadata("Keywords", ", ".join(kw))
        if args.identificar:
            st("Concluído", "Clipes marcados no media pool · " + resumo, 100, fim=time.time())
            return

        st("Montando", "Colocando os takes novos nas timelines de momento…", 80)
        raiz = mp.GetRootFolder()
        nome_pasta = "MOMENTOS"
        destino = next((f for f in raiz.GetSubFolderList() or [] if f.GetName() == nome_pasta), None)
        if destino is None:
            destino = mp.AddSubFolder(raiz, nome_pasta)
        mp.SetCurrentFolder(destino)
        criadas, acrescentadas = [], []
        n = len(tls_existentes)
        tl_unica = None
        if args.unica:  # uma timeline só: a existente (se houver) ou uma nova, com todos os momentos em ordem
            tl_unica = tls_existentes.get("__unica__")
            if tl_unica is None:
                tl_unica = mp.CreateEmptyTimeline(f"01 DECUPAGEM {proj.GetName()}".strip())
                tl_unica.SetSetting("useCustomSettings", "1")
                for kk, vv in (("timelineResolutionWidth", "1920"), ("timelineResolutionHeight", "1080"),
                               ("timelineFrameRate", "24"), ("colorScienceMode", "davinciYRGB"),
                               ("colorSpaceTimeline", "Rec.709 (Scene)")):
                    tl_unica.SetSetting(kk, vv)
                criadas.append(tl_unica.GetName())
            else:
                acrescentadas.append(tl_unica.GetName())
            tls_existentes = {}  # na timeline única, cada momento vai para a mesma timeline
        for momento, cor in MOMENTOS:
            sel = [(letra, [x for x in lst if x["momento"] == momento]) for _, letra, lst in itens]
            if not any(lst for _, lst in sel):
                continue
            if args.unica:
                tl = tl_unica
                proj.SetCurrentTimeline(tl)
            elif momento in tls_existentes:  # já existe: acrescenta os takes novos no fim
                tl = tls_existentes[momento]
                proj.SetCurrentTimeline(tl)
                acrescentadas.append(tl.GetName())
            else:
                n += 1
                tl = mp.CreateEmptyTimeline(f"{n:02d} {momento.upper()}")
                tl.SetSetting("useCustomSettings", "1")
                for kk, vv in (("timelineResolutionWidth", "1920"), ("timelineResolutionHeight", "1080"),
                               ("timelineFrameRate", "24"), ("colorScienceMode", "davinciYRGB"),
                               ("colorSpaceTimeline", "Rec.709 (Scene)")):
                    tl.SetSetting(kk, vv)
                proj.SetCurrentTimeline(tl)
                criadas.append(tl.GetName())
            for letra, lst in sel:  # câmera A inteira, depois B, depois C…
                if lst:
                    novos_itens = mp.AppendToTimeline([x["m"] for x in lst]) or []
                    for it in novos_itens:
                        it.SetClipColor(cor)
            for _, lst in sel:
                for x in lst:
                    x["m"].SetClipColor(cor)
            st("Montando", f"Timeline '{tl.GetName()}' atualizada…", 80 + int(18 * (n or 1) / max(1, len(MOMENTOS))))
        msg = f"{novos} take(s) novo(s) organizados · {len(ja_na_timeline)} já estavam nas timelines"
        if criadas:
            msg += f" · criadas: {len(criadas)}"
        if acrescentadas:
            msg += f" · acrescentados em: {len(acrescentadas)}"
        st("Concluído", msg + " · " + resumo, 100, fim=time.time())
    except Exception as e:  # noqa: BLE001
        st("Erro", str(e), st.d["pct"], erro=str(e), fim=time.time())
        sys.exit(1)


if __name__ == "__main__":
    main()
