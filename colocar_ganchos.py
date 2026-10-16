#!/usr/bin/env python3
"""Coloca os ganchos 3D renderizados (gancho_NN.mov com alfa) na timeline aberta do DaVinci.

Importa os .mov numa pasta "Ganchos 3D" do Media Pool, cria uma trilha de vídeo nova no topo ("GANCHOS 3D")
e põe cada gancho no quadro exato em que foi rastreado (inicio_quadro do gancho_NN_track.json).
Não mexe nos clipes que já estão na timeline.

Uso:
  .venv/bin/python colocar_ganchos.py --render projetos/PASTA/render --timeline "02" [--ids 1 2 3]
  legendas (legendas_overlay.py):
  .venv/bin/python colocar_ganchos.py --render projetos/PASTA/legendas --timeline "02" --padrao "leg_*_track.json" \
      --trilha LEGENDAS --pasta Legendas
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.append("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", required=True)
    ap.add_argument("--timeline", required=True)
    ap.add_argument("--ids", type=int, nargs="*")
    ap.add_argument("--pasta", default="Ganchos 3D", help="bin do Media Pool onde os .mov entram")
    ap.add_argument("--trilha", default="GANCHOS 3D", help="nome da trilha de vídeo")
    ap.add_argument("--padrao", default="gancho_*_track.json", help="arquivos de posição (legendas: leg_*_track.json)")
    a = ap.parse_args()
    import DaVinciResolveScript as d  # noqa: N813
    r = d.scriptapp("Resolve")
    proj = r.GetProjectManager().GetCurrentProject()
    tl = next((proj.GetTimelineByIndex(i) for i in range(1, proj.GetTimelineCount() + 1)
               if proj.GetTimelineByIndex(i).GetName() == a.timeline), None)
    if not tl:
        raise SystemExit(f"timeline '{a.timeline}' não está no projeto {proj.GetName()}")
    proj.SetCurrentTimeline(tl)
    pasta = Path(a.render).resolve()
    tracks = sorted(pasta.glob(a.padrao))
    ganchos = [json.loads(t.read_text(encoding="utf-8")) for t in tracks]
    if a.ids:
        ganchos = [g for g in ganchos if g["id"] in a.ids]
    if not ganchos:
        raise SystemExit("nenhum gancho renderizado encontrado")
    mp = proj.GetMediaPool()
    raiz = mp.GetRootFolder()
    bin_g = next((f for f in raiz.GetSubFolderList() or [] if f.GetName() == a.pasta), None) or mp.AddSubFolder(raiz, a.pasta)
    mp.SetCurrentFolder(bin_g)
    clipes = mp.ImportMedia([str(pasta / g["arquivos"]["alfa"]) for g in ganchos]) or []
    mp.SetCurrentFolder(raiz)
    por_nome = {c.GetClipProperty("File Name"): c for c in clipes}
    # reaproveita uma trilha vazia com esse nome; senão cria uma nova no topo
    trilha = next((i for i in range(1, tl.GetTrackCount("video") + 1)
                   if tl.GetTrackName("video", i) == a.trilha and not tl.GetItemListInTrack("video", i)), None)
    if not trilha:
        tl.AddTrack("video")
        trilha = tl.GetTrackCount("video")
        tl.SetTrackName("video", trilha, a.trilha)
    s0 = tl.GetStartFrame()
    ok = 0
    for g in ganchos:
        c = por_nome.get(g["arquivos"]["alfa"])
        if not c:
            print(f"gancho {g['id']}: não importou")
            continue
        c.SetClipProperty("Alpha mode", "Straight")
        n = g["quadros"]
        res = mp.AppendToTimeline([{"mediaPoolItem": c, "startFrame": 0, "endFrame": n,
                                    "recordFrame": s0 + g["inicio_quadro"], "trackIndex": trilha, "mediaType": 1}])
        ok += 1 if res else 0
    itens = tl.GetItemListInTrack("video", trilha) or []
    fps = float(tl.GetSetting("timelineFrameRate"))
    print(f"trilha V{trilha} '{a.trilha}': {len(itens)} clipe(s) colocados ({ok} de {len(ganchos)})")
    for it in itens:
        print(f"  {it.GetName()}  {(it.GetStart() - s0) / fps:.2f}s  dur {(it.GetEnd() - it.GetStart()) / fps:.2f}s")


if __name__ == "__main__":
    main()
