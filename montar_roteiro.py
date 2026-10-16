#!/usr/bin/env python3
"""Monta uma timeline nova na ordem das cenas do roteiro (roteiro_resolve.json), a partir de uma timeline de origem.

Modo "cortes" (padrão): cada cena vira os trechos de vídeo e áudio dessa faixa de tempo (início e fim em segundos,
na timeline de origem), colocados um depois do outro na ordem do roteiro.
Modo "takes": cada cena usa o take inteiro (da origem) que tem mais tempo dentro dela, sem cortar nos limites da cena.
Modo "takes_unicos": igual a "takes", mas cada take entra uma vez só, na primeira cena em que aparece.

A timeline de origem não é alterada. Uso pela linha de comando:
  .venv/bin/python montar_roteiro.py --roteiro projetos/PASTA/roteiro_resolve.json --nome "Roteiro · Lash 360"
"""
import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONUTF8", "1")
sys.path.append("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules")


def montar(roteiro_path, nome, modo="cortes", origem=None):
    """Cria a timeline no DaVinci aberto e devolve a mensagem para o app. Levanta RuntimeError se não der."""
    import DaVinciResolveScript as d  # noqa: N813
    dados = json.loads(Path(roteiro_path).read_text(encoding="utf-8"))
    origem = origem or dados.get("origem")
    if not origem:
        raise RuntimeError("O roteiro não diz de qual timeline montar (campo 'origem').")
    r = d.scriptapp("Resolve")
    if not r:
        raise RuntimeError("DaVinci Resolve não está aberto (ou o script externo está desligado).")
    proj = r.GetProjectManager().GetCurrentProject()
    mp = proj.GetMediaPool()
    tl_origem = next((proj.GetTimelineByIndex(i) for i in range(1, proj.GetTimelineCount() + 1)
                      if proj.GetTimelineByIndex(i).GetName() == origem), None)
    if not tl_origem:
        raise RuntimeError(f"A timeline '{origem}' não está no projeto '{proj.GetName()}'.")
    fps = float(tl_origem.GetSetting("timelineFrameRate") or 24)
    t0 = tl_origem.GetStartFrame()
    cenas = sorted(dados.get("cenas") or [], key=lambda c: c["ordem"])
    # clipes de vídeo da origem, com o trecho que cada um ocupa na timeline (em segundos)
    clipes = []
    for i in range(1, tl_origem.GetTrackCount("video") + 1):
        for it in tl_origem.GetItemListInTrack("video", i) or []:
            m = it.GetMediaPoolItem()
            if not m:
                continue
            clipes.append({"m": m, "a": (it.GetStart() - t0) / fps, "b": (it.GetEnd() - t0) / fps,
                           "src": it.GetSourceStartFrame(), "cfps": float(m.GetClipProperty("FPS") or fps), "faixa": i})
    # nova timeline na pasta Timelines
    raiz = mp.GetRootFolder()
    pasta = next((f for f in raiz.GetSubFolderList() or [] if f.GetName() == "Timelines"), None) or mp.AddSubFolder(raiz, "Timelines")
    mp.SetCurrentFolder(pasta)
    nova = mp.CreateEmptyTimeline(nome)
    mp.SetCurrentFolder(raiz)
    if not nova:
        raise RuntimeError("Não consegui criar a timeline nova (talvez já exista uma com esse nome).")
    nova.SetSetting("useCustomSettings", "1")
    for kk, vv in (("timelineResolutionWidth", tl_origem.GetSetting("timelineResolutionWidth") or "1920"),
                   ("timelineResolutionHeight", tl_origem.GetSetting("timelineResolutionHeight") or "1080"),
                   ("timelineFrameRate", str(int(fps))), ("colorScienceMode", "davinciYRGB"),
                   ("colorSpaceTimeline", "Rec.709 (Scene)")):
        nova.SetSetting(kk, vv)
    proj.SetCurrentTimeline(nova)
    # a timeline nova começa em 01:00:00 (frame 86400): os trechos entram a partir daí, não do frame 0
    pos, pedacos, total, usados = nova.GetStartFrame(), 0, 0.0, set()
    for c in cenas:
        a, b = float(c["inicio"]), float(c["fim"])
        if modo in ("takes", "takes_unicos"):
            cl = max(clipes, key=lambda k: min(b, k["b"]) - max(a, k["a"]), default=None)
            if not cl or min(b, cl["b"]) - max(a, cl["a"]) <= 0:
                continue
            if modo == "takes_unicos" and id(cl["m"]) in usados:
                continue
            usados.add(id(cl["m"]))
            src_b = round(cl["src"] + (cl["b"] - cl["a"]) * cl["cfps"])
            info = {"mediaPoolItem": cl["m"], "startFrame": round(cl["src"]), "endFrame": src_b, "recordFrame": pos}
            if mp.AppendToTimeline([info]):
                pedacos += 1
                dur = cl["b"] - cl["a"]
                pos += round(dur * fps)
                total += dur
            continue
        for cl in clipes:
            x1, x2 = max(a, cl["a"]), min(b, cl["b"])
            if x2 - x1 < 0.05:
                continue
            src_a = round(cl["src"] + (x1 - cl["a"]) * cl["cfps"])
            src_b = round(cl["src"] + (x2 - cl["a"]) * cl["cfps"])
            if src_b <= src_a:
                continue
            info = {"mediaPoolItem": cl["m"], "startFrame": src_a, "endFrame": src_b, "recordFrame": pos}
            if mp.AppendToTimeline([info]):
                pedacos += 1
                dur = x2 - x1
                pos += round(dur * fps)
                total += dur
    if not pedacos:
        raise RuntimeError("O DaVinci não aceitou nenhum trecho do roteiro.")
    return {"ok": True, "msg": f"Timeline '{nova.GetName()}' criada: {pedacos} trecho(s), {total:.1f} s, "
                               f"{len(cenas)} cena(s), no projeto {proj.GetName()}."}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roteiro", required=True)
    ap.add_argument("--origem")
    ap.add_argument("--nome", required=True)
    ap.add_argument("--modo", default="cortes", choices=["cortes", "takes", "takes_unicos"])
    args = ap.parse_args()
    print(montar(args.roteiro, args.nome, args.modo, args.origem)["msg"])


if __name__ == "__main__":
    main()
