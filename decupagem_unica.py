#!/usr/bin/env python3
"""Decupagem completa numa timeline só: momentos em ordem, takes limpos, trechos tremidos separados no fim.

Etapas (cada uma grava em projetos/_predec/<Projeto>/decupagem/):
  preparar  lê as pastas de câmera do media pool do projeto aberto, tira um quadro por clipe e monta folhas de
            miniaturas por câmera (em ordem de gravação) -> clipes.json, folhas/*.jpg
  tremor    mede o tremor de cada clipe, segundo a segundo (movimento rápido e irregular da câmera; pan, tilt e
            movimentos suaves e intencionais não contam) -> tremor.jsonl   (retoma de onde parou)
  montar    lê classificacao.json (momento de cada clipe, por blocos) e tremor.jsonl e cria a timeline
            "01 DECUPAGEM <Projeto>": cada momento em sequência (câmera A, depois B…), clipes com a cor do momento e
            marcador no início de cada momento; os trechos tremidos de todos os clipes vão cortados para o fim, na
            mesma ordem de momentos, com a cor Chocolate. Não altera nenhuma outra timeline.

Uso: .venv/bin/python decupagem_unica.py preparar|tremor|montar [--limite 6] [--trabalhos 6]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import numpy as np

os.environ.setdefault("PYTHONUTF8", "1")
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
sys.path.append("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules")
import predecupar as pd  # noqa: E402  (cameras, data, segundos, miniatura, folhas)

FFMPEG = str(BASE / ".venv" / "bin" / "ffmpeg")

# ordem na timeline e cor de cada momento
MOMENTOS = [
    ("Decoração", "Yellow"),
    ("Making of noiva", "Pink"),
    ("Making of noivo", "Green"),
    ("Pré-cerimônia", "Apricot"),
    ("Cerimônia", "Blue"),
    ("Reações de convidados", "Lime"),
    ("Celebrante", "Navy"),
    ("Pós-cerimônia", "Teal"),
    ("Pré-festa", "Orange"),
    ("Festa", "Purple"),
    ("Drone", "Tan"),
    ("Revisar", "Beige"),
]
COR_TREMIDO = "Chocolate"
MIN_LIMPO_S = 1.5    # trecho limpo menor que isso (entre tremidas) não vale como take: vai junto com o tremido
MIN_TREMIDO_S = 1.0  # tremida mais curta que isso é tolerada dentro do take limpo


def resolve():
    import DaVinciResolveScript as d  # noqa: N813
    r = d.scriptapp("Resolve")
    if not r:
        raise SystemExit("DaVinci Resolve não está aberto.")
    return r, r.GetProjectManager().GetCurrentProject()


def pasta_projeto(proj):
    p = BASE / "projetos" / "_predec" / re.sub(r"[^A-Za-z0-9]+", "_", proj.GetName()) / "decupagem"
    (p / "thumbs").mkdir(parents=True, exist_ok=True)
    (p / "folhas").mkdir(parents=True, exist_ok=True)
    return p


# ------------------------------------------------------------------ preparar

def cmd_preparar(a):
    r, proj = resolve()
    pasta = pasta_projeto(proj)
    cams = pd.cameras(proj.GetMediaPool())
    drones = [c for c in cams if pd.eh_drone(*c)]
    cams = [c for c in cams if not pd.eh_drone(*c)] + drones
    clipes, n_cam, n_drone = [], 0, 0
    for cam, clips in cams:
        drone = pd.eh_drone(cam, clips)
        if drone:
            n_drone += 1
            letra = f"DRONE{n_drone}-" if n_drone > 1 else "DRONE-"
        else:
            letra = chr(ord("A") + n_cam)
            n_cam += 1
        lista = []
        for c in clips:
            fps = float(c.GetClipProperty("FPS") or 24)
            res = (c.GetClipProperty("Resolution") or "1920x1080").lower().split("x")
            lista.append({"uid": c.GetUniqueId(), "nome": c.GetName(), "arq": c.GetClipProperty("File Path"),
                          "cam": cam, "letra": letra, "fps": fps, "drone": drone,
                          "quadros": int(c.GetClipProperty("Frames") or 0),
                          "dur": pd.segundos(c.GetClipProperty("Duration") or "0:0:0:0", fps),
                          "w": int(res[0]), "h": int(res[1]), "_data": pd.data(c)})
        lista.sort(key=lambda x: (x["_data"] or datetime.min, x["nome"]))
        for k, x in enumerate(lista, 1):
            x["id"] = f"{letra}{k}"
            x["hora"] = x["_data"].strftime("%H:%M:%S") if x["_data"] else "?"
            x["thumb"] = str(pasta / "thumbs" / f"{x['id']}.jpg")
            x.pop("_data")
        clipes += lista
    print(f"{len(clipes)} clipes em {n_cam} câmera(s) + {n_drone} drone(s). Tirando quadros…", flush=True)
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda x: pd.miniatura(x["arq"], max(0.5, x["dur"] * 0.4), Path(x["thumb"])), clipes))
    folhas = []
    for cam, letra in dict.fromkeys((x["cam"], x["letra"]) for x in clipes):
        itens = [dict(x, cam_id=x["id"]) for x in clipes if x["letra"] == letra]
        folhas += pd.folhas(f"{letra}_{cam}", itens, pasta / "folhas")
    (pasta / "clipes.json").write_text(json.dumps(clipes, ensure_ascii=False, indent=1), encoding="utf-8")
    linhas = []
    for x in clipes:
        orient = "vertical" if x["h"] > x["w"] else ""
        linhas.append(f"{x['id']} · {x['cam']} · {x['hora']} · {x['dur']:.0f}s · {x['nome']} {orient}".rstrip())
    (pasta / "clipes.txt").write_text("\n".join(linhas), encoding="utf-8")
    print(f"pronto: {len(folhas)} folhas em {pasta / 'folhas'}")


# ------------------------------------------------------------------ tremor

def medir_tremor(x):
    """Tremor por segundo do clipe (px numa imagem de 1080 no lado menor).

    Lê só os quadros de referência (bem mais rápido em H.264 de câmera; dá 15–30 quadros/s espaçados por igual) numa
    imagem pequena, mede o deslocamento entre quadros (correlação de fase, subpixel) e separa o movimento suave (média
    móvel de 0,3 s: pan, tilt, travelling) do irregular, normalizado para intervalos de 1/30 s. O tremor de cada
    segundo é a média do movimento irregular nele. Quadros com correlação fraca (corte, desfoque, flash) não contam."""
    import cv2
    vertical = x["h"] > x["w"]
    L, A = (144, 256) if vertical else (256, 144)

    def ler(rapido):
        pre = ["-skip_frame", "noref"] if rapido else []
        vf = f"scale={L}:{A}:flags=fast_bilinear,format=gray" if rapido else f"fps=30,scale={L}:{A}:flags=fast_bilinear,format=gray"
        cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", *pre, "-threads", "3", "-i", x["arq"], "-an",
               "-fps_mode", "passthrough", "-vf", vf, "-f", "rawvideo", "-pix_fmt", "gray", "-"]
        raw = subprocess.run(cmd, capture_output=True).stdout
        return raw, len(raw) // (L * A)

    raw, n = ler(True)
    eff = n / max(0.1, x["dur"])
    if eff < 12:  # câmera com poucos quadros de referência: lê tudo a 30 q/s
        raw, n = ler(False)
        eff = 30.0
    if n < 10:
        return {"id": x["id"], "seg": [], "erro": "não consegui ler o vídeo"}
    q = np.frombuffer(raw[: n * L * A], np.uint8).reshape(n, A, L).astype(np.float32)
    jan = cv2.createHanningWindow((L, A), cv2.CV_32F)
    dx, dy, ok = np.zeros(n - 1), np.zeros(n - 1), np.zeros(n - 1, bool)
    for i in range(n - 1):
        (sx, sy), resp = cv2.phaseCorrelate(q[i], q[i + 1], jan)
        dx[i], dy[i], ok[i] = sx, sy, resp > 0.08
    k = max(3, int(round(0.3 * eff)) | 1)
    ker = np.ones(k) / k
    sxm = np.convolve(np.pad(dx, k // 2, mode="edge"), ker, "valid")
    sym = np.convolve(np.pad(dy, k // 2, mode="edge"), ker, "valid")
    irreg = np.hypot(dx - sxm, dy - sym) * (1080 / min(L, A)) * (30 / eff)
    irreg[~ok] = np.nan
    passo = max(1, int(round(eff)))
    seg = []
    for s in range(0, n - 1, passo):
        v = irreg[s:s + passo]
        v = v[~np.isnan(v)]
        seg.append(round(float(np.mean(v)), 2) if v.size >= passo // 3 else None)
    return {"id": x["id"], "seg": seg, "qps": round(eff, 1)}


def cmd_tremor(a):
    r, proj = resolve()
    pasta = pasta_projeto(proj)
    clipes = json.loads((pasta / "clipes.json").read_text(encoding="utf-8"))
    saida = pasta / "tremor.jsonl"
    feitos = set()
    if saida.exists():
        linhas = [json.loads(l) for l in saida.read_text(encoding="utf-8").splitlines() if l.strip()]
        if a.medir:  # pastas que devem ser medidas mesmo sendo "tripé" (ex.: tomadas de decoração em movimento)
            alvo = {x["id"] for x in clipes if x["letra"] in a.medir and x["dur"] <= a.max_dur}
            linhas = [j for j in linhas if not (j["id"] in alvo and j.get("estavel"))]
            saida.write_text("".join(json.dumps(j, ensure_ascii=False) + "\n" for j in linhas), encoding="utf-8")
        feitos = {j["id"] for j in linhas}
    # tripé e drone não tremem: entram inteiros como estáveis, sem gastar tempo decodificando
    fixos = [x for x in clipes if x["id"] not in feitos and (x["drone"] or re.search(r"trip[eé]|tripod", x["cam"], re.I))
             and not (x["letra"] in (a.medir or []) and x["dur"] <= a.max_dur)]
    if fixos:
        with saida.open("a", encoding="utf-8") as f:
            for x in fixos:
                f.write(json.dumps({"id": x["id"], "seg": [], "estavel": True}, ensure_ascii=False) + "\n")
        feitos |= {x["id"] for x in fixos}
        print(f"{len(fixos)} clipe(s) de tripé/drone marcados como estáveis", flush=True)
    falta = [x for x in clipes if x["id"] not in feitos]
    total_s = sum(x["dur"] for x in falta)
    print(f"{len(falta)} clipe(s) para medir ({total_s / 60:.0f} min de material)", flush=True)
    t0, feito_s = time.time(), 0.0
    with ThreadPoolExecutor(a.trabalhos) as ex, saida.open("a", encoding="utf-8") as f:
        futs = {ex.submit(medir_tremor, x): x for x in falta}
        for i, fu in enumerate(as_completed(futs), 1):
            x = futs[fu]
            try:
                res = fu.result()
            except Exception as e:  # noqa: BLE001
                res = {"id": x["id"], "seg": [], "erro": str(e)[:200]}
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
            f.flush()
            feito_s += x["dur"]
            if i % 10 == 0 or i == len(falta):
                vel = feito_s / max(1, time.time() - t0)
                print(f"{i}/{len(falta)} clipes · {feito_s / 60:.0f}/{total_s / 60:.0f} min · "
                      f"faltam ~{(total_s - feito_s) / max(vel, 0.01) / 60:.0f} min", flush=True)


# ------------------------------------------------------------------ montar

def trechos(seg, dur, limite):
    """Divide o clipe em trechos [(ini_s, fim_s, tremido)] a partir do tremor por segundo."""
    if not seg:
        return [(0.0, dur, False)]
    marca = [v is not None and v > limite for v in seg]
    # tremida curta isolada é tolerada; segundo sem medida herda o vizinho
    runs = []
    for i, m in enumerate(marca):
        if runs and runs[-1][2] == m:
            runs[-1][1] = i + 1
        else:
            runs.append([i, i + 1, m])
    for r_ in runs:
        if r_[2] and (r_[1] - r_[0]) < MIN_TREMIDO_S:
            r_[2] = False
    junt = []
    for r_ in runs:
        if junt and junt[-1][2] == r_[2]:
            junt[-1][1] = r_[1]
        else:
            junt.append(list(r_))
    # trecho limpo curto demais entre tremidas não é take: vira tremido
    if any(r_[2] for r_ in junt):
        for r_ in junt:
            if not r_[2] and (r_[1] - r_[0]) < MIN_LIMPO_S:
                r_[2] = True
    out = []
    for i0, i1, m in junt:
        ini, fim = float(i0), min(float(i1), dur)
        if out and out[-1][2] == m:
            out[-1] = (out[-1][0], fim, m)
        elif fim - ini > 0.05:
            out.append((ini, fim, m))
    if out:
        out[-1] = (out[-1][0], dur, out[-1][2])
    return out


def cmd_montar(a):
    r, proj = resolve()
    pasta = pasta_projeto(proj)
    mp = proj.GetMediaPool()
    clipes = json.loads((pasta / "clipes.json").read_text(encoding="utf-8"))
    cl = json.loads((pasta / "classificacao.json").read_text(encoding="utf-8"))
    cor = dict(MOMENTOS)
    por_id = {x["id"]: x for x in clipes}
    ordem = {x["id"]: i for i, x in enumerate(clipes)}
    for b in cl["blocos"]:
        ids = [x["id"] for x in clipes if x["letra"] == re.match(r"^(.*?)(\d+)$", b["de"]).group(1)]
        i0, i1 = ids.index(b["de"]), ids.index(b["ate"])
        for i in ids[i0:i1 + 1]:
            por_id[i]["momento"] = b["momento"] if b["momento"] in cor else "Revisar"
    for x in clipes:
        x.setdefault("momento", "Drone" if x["drone"] else "Revisar")
    tremor = {}
    if (pasta / "tremor.jsonl").exists():
        for l in (pasta / "tremor.jsonl").read_text(encoding="utf-8").splitlines():
            if l.strip():
                j = json.loads(l)
                # lidos a ~20 q/s (só quadros de referência) medem ~2,5x mais que os lidos a 30 q/s: mesma escala
                esc = 2.5 if (j.get("qps") or 30) < 25 else 1.0
                tremor[j["id"]] = [None if v is None else v / esc for v in (j.get("seg") or [])]
    sem_medida = [x["id"] for x in clipes if x["id"] not in tremor]

    itens = {uid.GetUniqueId(): uid for _, clips in pd.cameras(mp) for uid in clips}
    raiz = mp.GetRootFolder()
    destino = next((f for f in raiz.GetSubFolderList() or [] if f.GetName() == "MOMENTOS"), None) or mp.AddSubFolder(raiz, "MOMENTOS")
    mp.SetCurrentFolder(destino)
    nome = f"01 DECUPAGEM {proj.GetName()}".strip()
    if any(proj.GetTimelineByIndex(i).GetName() == nome for i in range(1, proj.GetTimelineCount() + 1)):
        nome += time.strftime(" %H%M")
    tl = mp.CreateEmptyTimeline(nome)
    mp.SetCurrentFolder(raiz)
    tl.SetSetting("useCustomSettings", "1")
    for kk, vv in (("timelineResolutionWidth", "1920"), ("timelineResolutionHeight", "1080"), ("timelineFrameRate", "24"),
                   ("colorScienceMode", "davinciYRGB"), ("colorSpaceTimeline", "Rec.709 (Scene)")):
        tl.SetSetting(kk, vv)
    proj.SetCurrentTimeline(tl)
    fps_tl = 24.0
    pos = tl.GetStartFrame()
    limpos, tremidos, resumo = [], [], {}
    for momento, _ in MOMENTOS:
        for x in sorted((x for x in clipes if x["momento"] == momento), key=lambda x: ordem[x["id"]]):
            for ini, fim, trem in trechos(tremor.get(x["id"]), x["dur"], a.limite):
                (tremidos if trem else limpos).append((x, ini, fim, momento))
    blocos = [("limpo", limpos), ("tremido", tremidos)]
    for tipo, lista in blocos:
        atual = None
        if tipo == "tremido" and lista:
            pos += int(2 * fps_tl)  # 2 s de respiro antes da área de tremidos
            tl.AddMarker(pos - int(fps_tl) - tl.GetStartFrame(), "Red", "TREMIDOS",
                         f"{len(lista)} trechos com muita tremida, separados por momento", 1)
        for x, ini, fim, momento in lista:
            m = itens.get(x["uid"])
            if not m:
                continue
            q0, q1 = int(round(ini * x["fps"])), int(round(fim * x["fps"]))
            q1 = min(q1, x["quadros"] or q1)
            if q1 - q0 < 2:
                continue
            res = mp.AppendToTimeline([{"mediaPoolItem": m, "startFrame": q0, "endFrame": q1, "recordFrame": pos}]) or []
            if not res:
                continue
            for it in res:
                it.SetClipColor(COR_TREMIDO if tipo == "tremido" else cor[momento])
            if momento != atual:
                n_mom = sum(1 for y in lista if y[3] == momento)
                titulo = momento if tipo == "limpo" else f"Tremidos · {momento}"
                tl.AddMarker(pos - tl.GetStartFrame(), "Red" if tipo == "tremido" else "Blue", titulo,
                             f"{n_mom} trecho(s)", 1)
                atual = momento
            pos = max(it.GetEnd() for it in res)
            k = (momento, tipo)
            resumo[k] = resumo.get(k, 0) + (fim - ini)
    (pasta / "montagem.json").write_text(json.dumps(
        {"timeline": nome, "limite": a.limite, "sem_medida": sem_medida,
         "segundos": {f"{m} · {t}": round(v, 1) for (m, t), v in resumo.items()}}, ensure_ascii=False, indent=1))
    print(f"timeline '{nome}' criada")
    for momento, _ in MOMENTOS:
        lim, tre = resumo.get((momento, "limpo"), 0), resumo.get((momento, "tremido"), 0)
        if lim or tre:
            print(f"  {momento:24s} limpo {lim / 60:5.1f} min · tremido {tre / 60:4.1f} min")
    if sem_medida:
        print(f"  sem medida de tremor (entraram inteiros como limpos): {len(sem_medida)}")


def classificar(pasta):
    """Clipes do clipes.json com o campo 'momento' preenchido a partir de classificacao.json."""
    clipes = json.loads((pasta / "clipes.json").read_text(encoding="utf-8"))
    cl = json.loads((pasta / "classificacao.json").read_text(encoding="utf-8"))
    por_id = {x["id"]: x for x in clipes}
    for b in cl["blocos"]:
        ids = [x["id"] for x in clipes if x["letra"] == re.match(r"^(.*?)(\d+)$", b["de"]).group(1)]
        for i in ids[ids.index(b["de"]):ids.index(b["ate"]) + 1]:
            por_id[i]["momento"] = b["momento"]
    for x in clipes:
        x.setdefault("momento", "Drone" if x["drone"] else "Revisar")
    return clipes


def cmd_momentos(a):
    """Timeline com os clipes inteiros agrupados nos momentos pedidos (sem separar tremidos), mantendo a cor que
    cada clipe tem na timeline de referência (ex.: cor por câmera) e um marcador no início de cada momento."""
    r, proj = resolve()
    pasta = pasta_projeto(proj)
    mp = proj.GetMediaPool()
    clipes = classificar(pasta)
    ordem_orig = [m for m, _ in MOMENTOS]
    juntar = dict(p.split("=") for p in (a.juntar or "").split(";") if "=" in p)
    alvo = [m.strip() for m in a.ordem.split(",")]
    cores = {}
    ref = next((proj.GetTimelineByIndex(i) for i in range(1, proj.GetTimelineCount() + 1)
                if proj.GetTimelineByIndex(i).GetName() == a.cores_da), None)
    if ref:
        for k in range(1, ref.GetTrackCount("video") + 1):
            for it in ref.GetItemListInTrack("video", k) or []:
                m = it.GetMediaPoolItem()
                if m and it.GetClipColor():
                    cores[m.GetUniqueId()] = it.GetClipColor()
    itens = {c.GetUniqueId(): c for _, clips in pd.cameras(mp) for c in clips}
    raiz = mp.GetRootFolder()
    destino = next((f for f in raiz.GetSubFolderList() or [] if f.GetName() == "MOMENTOS"), None) or mp.AddSubFolder(raiz, "MOMENTOS")
    mp.SetCurrentFolder(destino)
    tl = mp.CreateEmptyTimeline(a.nome)
    mp.SetCurrentFolder(raiz)
    if not tl:
        raise SystemExit(f"não consegui criar a timeline '{a.nome}' (já existe?)")
    tl.SetSetting("useCustomSettings", "1")
    for kk, vv in (("timelineResolutionWidth", "1920"), ("timelineResolutionHeight", "1080"), ("timelineFrameRate", "24"),
                   ("colorScienceMode", "davinciYRGB"), ("colorSpaceTimeline", "Rec.709 (Scene)")):
        tl.SetSetting(kk, vv)
    proj.SetCurrentTimeline(tl)
    s0 = tl.GetStartFrame()
    resumo = []
    for i_m, momento in enumerate(alvo + ["Revisar"]):
        fontes = [m for m in ordem_orig if juntar.get(m, m) == momento]
        lista = [x for f in fontes for x in clipes if x["momento"] == f and x["uid"] in itens]
        if not lista:
            continue
        pos = tl.GetEndFrame() if tl.GetItemListInTrack("video", 1) else s0
        novos = mp.AppendToTimeline([itens[x["uid"]] for x in lista]) or []
        for it in novos:
            c = cores.get(it.GetMediaPoolItem().GetUniqueId()) if it.GetMediaPoolItem() else None
            if c:
                it.SetClipColor(c)
        dur = sum(x["dur"] for x in lista)
        cor_m = ["Blue", "Pink", "Green", "Yellow", "Cyan", "Purple", "Red", "Sand"][i_m % 8]
        tl.AddMarker(pos - s0, cor_m, momento, f"{len(lista)} clipe(s) · {dur / 60:.1f} min · " + ", ".join(fontes), 1)
        resumo.append((momento, len(lista), dur))
    print(f"timeline '{a.nome}' criada")
    for m, n, d in resumo:
        print(f"  {m:20s} {n:4d} clipes  {d / 60:6.1f} min")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("etapa", choices=["preparar", "tremor", "montar", "momentos"])
    ap.add_argument("--limite", type=float, default=6.0, help="tremor (px em 1080) acima do qual o segundo é tremido")
    ap.add_argument("--trabalhos", type=int, default=6)
    ap.add_argument("--medir", nargs="*", help="letras de câmeras de tripé que devem ser medidas assim mesmo (ex.: C)")
    ap.add_argument("--max-dur", type=float, default=600, help="com --medir: só clipes até essa duração (s)")
    ap.add_argument("--ordem", default="Making of noiva,Making of noivo,Decoração,Drone,Cerimônia,Pré-festa,Festa",
                    help="momentos: ordem dos grupos na timeline")
    ap.add_argument("--juntar", default="Pré-cerimônia=Cerimônia;Reações de convidados=Cerimônia;Celebrante=Cerimônia;"
                                        "Pós-cerimônia=Pré-festa", help="momentos: origem=destino;…")
    ap.add_argument("--cores-da", default="Timeline 1", help="momentos: timeline de onde copiar a cor de cada clipe")
    ap.add_argument("--nome", default="02 MOMENTOS", help="momentos: nome da timeline nova")
    a = ap.parse_args()
    ap_vals = {"preparar": cmd_preparar, "tremor": cmd_tremor, "montar": cmd_montar, "momentos": cmd_momentos}
    ap_vals[a.etapa](a)


if __name__ == "__main__":
    main()
