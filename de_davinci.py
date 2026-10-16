#!/usr/bin/env python3
"""Prepara e transcreve material direto do projeto aberto no DaVinci Resolve (só leitura).

Uso:
  ./de_davinci cor Orange --nome "Cliente X - takes"          takes de uma cor na timeline atual
  ./de_davinci timelines "01 MAKING,04 CERIMONIA" --nome "..."  um áudio por timeline (tempo = posição na timeline)
  ./de_davinci timelines --todas --nome "..."                    todas as timelines do projeto
  ./de_davinci atual --nome "..."                                 só a timeline aberta agora
  (aceita também --prompt "nomes...")

O áudio montado fica em projetos/<Nome>/_fonte/ — sai junto quando o projeto é limpo.
"""
import argparse
import json
import os as _os
_os.environ.setdefault("PYTHONUTF8", "1")
_os.environ.setdefault("LANG", "pt_BR.UTF-8")
_os.environ.setdefault("LC_ALL", "pt_BR.UTF-8")
import re
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent
FFMPEG = str(BASE / ".venv" / "bin" / "ffmpeg")
PY = str(BASE / ".venv" / "bin" / "python")
SR = 24000
sys.path.append("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules")


def slug(txt):
    import unicodedata
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", txt).strip("_") or "projeto"


def projeto_aberto():
    import os
    os.environ.setdefault("RESOLVE_SCRIPT_LIB",
                          "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so")
    import DaVinciResolveScript as d  # noqa: N813
    r = d.scriptapp("Resolve")
    if not r:
        sys.exit("DaVinci Resolve não está aberto.")
    return r.GetProjectManager().GetCurrentProject()


FAIXA = None  # --faixa N: usa só essa faixa de áudio (ex.: o gravador)


def itens_audio(tl):
    fps = float(tl.GetSetting("timelineFrameRate"))
    t0 = tl.GetStartFrame()
    out = []
    trilhas = [i for i in range(1, tl.GetTrackCount("audio") + 1) if tl.GetIsTrackEnabled("audio", i)] or [1]
    if FAIXA and FAIXA <= tl.GetTrackCount("audio"):
        trilhas = [FAIXA]
    for it in (x for i in trilhas for x in (tl.GetItemListInTrack("audio", i) or [])):
        m = it.GetMediaPoolItem()
        if not m or not m.GetClipProperty("File Path"):
            continue
        out.append({"ini": (it.GetStart() - t0) / fps, "fim": (it.GetEnd() - t0) / fps,
                    "src_in": it.GetSourceStartFrame(), "src_out": it.GetSourceEndFrame(),
                    "arquivo": m.GetClipProperty("File Path"), "fps": float(m.GetClipProperty("FPS") or fps),
                    "cor": it.GetClipColor(), "nome": it.GetName()})
    return out, (tl.GetEndFrame() - t0) / fps


def montar_audio(itens, dur, saida):
    buf = np.zeros(int(dur * SR) + SR, dtype=np.float32)
    for it in itens:
        ini_src = it["src_in"] / it["fps"]
        d = min(it["fim"] - it["ini"], (it["src_out"] - it["src_in"]) / it["fps"])
        if d <= 0:
            continue
        r = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-ss", f"{ini_src:.3f}", "-i", it["arquivo"],
                            "-t", f"{d:.3f}", "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"], capture_output=True)
        if r.returncode or not r.stdout:
            continue
        a = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32)
        p = int(it["ini"] * SR)
        buf[p:p + len(a)] += a[: len(buf) - p]
    with wave.open(str(saida), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(np.clip(buf, -32768, 32767).astype(np.int16).tobytes())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modo", choices=["cor", "timelines", "atual"])
    ap.add_argument("alvo", nargs="?", help="cor (Orange, Blue…) ou nomes das timelines separados por vírgula")
    ap.add_argument("--todas", action="store_true", help="timelines: usar todas do projeto")
    ap.add_argument("--nome", required=True)
    ap.add_argument("--prompt")
    ap.add_argument("--faixa", type=int, help="usar só esta faixa de áudio (ex.: gravador)")
    args = ap.parse_args()
    global FAIXA
    FAIXA = args.faixa

    proj = projeto_aberto()
    pasta = BASE / "projetos" / slug(args.nome)
    extra = ["--prompt", args.prompt] if args.prompt else []

    if args.modo == "cor":
        tl = proj.GetCurrentTimeline()
        itens = [it for it in itens_audio(tl)[0] if it["cor"] == args.alvo]
        if not itens:
            sys.exit(f"Nenhum clipe com a cor {args.alvo} na timeline '{tl.GetName()}'.")
        lista = [{"arquivo": it["arquivo"], "inicio": round(max(0, it["src_in"] / it["fps"] - 0.2), 3),
                  "fim": round(it["src_out"] / it["fps"] + 0.2, 3)} for it in itens]
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "_trechos.json").write_text(json.dumps(lista, ensure_ascii=False, indent=1))
        print(f"{len(lista)} takes {args.alvo} em '{tl.GetName()}' ({proj.GetName()})", flush=True)
        subprocess.run([PY, str(BASE / "transcrever.py"), "--lista", str(pasta / "_trechos.json"),
                        "--nome", args.nome] + extra, check=True)
        return

    todas = [proj.GetTimelineByIndex(i) for i in range(1, proj.GetTimelineCount() + 1)]
    if args.modo == "atual":
        escolhidas = [proj.GetCurrentTimeline()]
    elif args.todas:
        escolhidas = todas
    else:
        nomes = [n.strip() for n in (args.alvo or "").split(",") if n.strip()]
        escolhidas = [t for n in nomes for t in todas if t.GetName() == n]
        faltando = set(nomes) - {t.GetName() for t in escolhidas}
        if faltando:
            sys.exit(f"Timelines não encontradas: {', '.join(faltando)}")
    fonte = pasta / "_fonte"
    fonte.mkdir(parents=True, exist_ok=True)
    wavs, meta = [], []
    for tl in escolhidas:
        itens, dur = itens_audio(tl)
        saida = fonte / (slug(tl.GetName()) + ".wav")
        print(f"→ Montando áudio de '{tl.GetName()}' ({len(itens)} clipes, {dur / 60:.1f} min)…", flush=True)
        montar_audio(itens, dur, saida)
        wavs.append(str(saida))
        meta.append((tl.GetName(), itens))
    subprocess.run([PY, str(BASE / "transcrever.py"), *wavs, "--nome", args.nome] + extra, check=True)
    # liga cada áudio à sua timeline: o corte e o envio pro DaVinci acham o clipe original
    t = json.loads((pasta / "transcricao.json").read_text())
    for a, (nome_tl, itens) in zip(t["arquivos"], meta):
        a["resolve_timeline"] = nome_tl
        a["nome"] = slug(nome_tl)
        a["itens"] = [{k: it[k] for k in ("ini", "fim", "src_in", "src_out", "arquivo", "fps")} for it in itens]
    (pasta / "transcricao.json").write_text(json.dumps(t, ensure_ascii=False, indent=1))
    print("✓ Áudios ligados às timelines do DaVinci")


if __name__ == "__main__":
    main()
