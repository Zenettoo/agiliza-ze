#!/usr/bin/env python3
"""Cria um multicam a partir da timeline aberta e uma timeline nova com ele, num clique.

Cada faixa de vídeo da timeline vira um ângulo (câmera) do multicam. A timeline original não é alterada.
A nova timeline "<nome> - MULTICAM" tem 1080p / 24 fps / Rec.709 Scene, igual às demais do projeto.

Uso:
  .venv/bin/python multicam.py [--status projetos/_sync/x.json]
"""
import argparse
import os
import sys
import time

os.environ.setdefault("PYTHONUTF8", "1")
sys.path.append("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules")
os.environ.setdefault("RESOLVE_SCRIPT_LIB",
                      "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sincronizar import Status  # noqa: E402


def faixas_de_video(tl):
    """[(nome da faixa, [(MediaPoolItem, item da timeline)])] só com clipes que têm arquivo de origem."""
    out = []
    for i in range(1, tl.GetTrackCount("video") + 1):
        nome = tl.GetTrackName("video", i) or f"V{i}"
        clipes = []
        for it in tl.GetItemListInTrack("video", i) or []:
            m = it.GetMediaPoolItem()
            if m and m.GetClipProperty("File Path"):
                clipes.append((m, it))
        if clipes:
            out.append((nome, clipes))
    return out


def nome_livre(proj, base):
    """'base', ou 'base 2', 'base 3'… se já existir timeline com esse nome (o DaVinci recusa nomes repetidos)."""
    usados = {proj.GetTimelineByIndex(i).GetName() for i in range(1, proj.GetTimelineCount() + 1)}
    nome, n = base, 1
    while nome in usados:
        n += 1
        nome = f"{base} {n}"
    return nome


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status")
    args = ap.parse_args()
    st = Status(args.status)
    st.d.update(nome="Multicam", tipo="sync")
    try:
        import DaVinciResolveScript as d  # noqa: N813
        r = d.scriptapp("Resolve")
        proj = r.GetProjectManager().GetCurrentProject()
        tl = proj.GetCurrentTimeline()
        if not tl:
            raise RuntimeError("Nenhuma timeline aberta.")
        st.d["nome"] = f"Multicam · {tl.GetName()}"
        st("Lendo", f"Lendo as faixas de vídeo de '{tl.GetName()}'…", 5)
        faixas = faixas_de_video(tl)
        if len(faixas) < 2:
            raise RuntimeError("Um multicam precisa de pelo menos 2 faixas de vídeo com clipes.")

        mp = proj.GetMediaPool()
        # cada arquivo entra uma vez; a faixa de origem vira o nome do ângulo
        vistos, clipes, angulo_de = set(), [], {}
        for nome, lst in faixas:
            for m, _ in lst:
                uid = m.GetUniqueId()
                if uid in angulo_de:
                    continue
                angulo_de[uid] = nome
                clipes.append(m)
                m.SetMetadata("Angle", nome)
        st("Multicam", f"Criando o multicam com {len(clipes)} ângulo(s) ({', '.join(f for f, _ in faixas)})…", 25)

        nome_mc = nome_livre(proj, f"{tl.GetName()} - MULTICAM")
        base = {"name": nome_mc, "frameRate": float(tl.GetSetting("timelineFrameRate") or 24),
                "angleNameMode": r.MULTICAM_ANGLE_NAME_ANGLE,
                "detectSameCameraClipsMode": r.MULTICAM_DETECT_BY_ANGLE,
                "createBinForSourceClips": True}
        # alinhamento pelo áudio das próprias câmeras; se não houver áudio útil, pelo timecode
        mc = mp.CreateMulticamClip(clipes, {**base, "angleSyncMode": r.MULTICAM_ANGLE_SYNC_AUDIO})
        if not mc:
            st("Multicam", "Alinhamento pelo áudio falhou; tentando pelo timecode…", 50)
            mc = mp.CreateMulticamClip(clipes, {**base, "angleSyncMode": r.MULTICAM_ANGLE_SYNC_TIMECODE})
        if not mc:
            raise RuntimeError("O DaVinci não conseguiu criar o multicam. A timeline original não foi alterada.")

        st("Timeline", "Criando a timeline do multicam…", 75)
        nova = mp.CreateEmptyTimeline(nome_livre(proj, f"{tl.GetName()} - MULTICAM"))
        if not nova:
            raise RuntimeError("Não consegui criar a timeline nova.")
        nova.SetSetting("useCustomSettings", "1")
        for kk, vv in (("timelineResolutionWidth", "1920"), ("timelineResolutionHeight", "1080"),
                       ("timelineFrameRate", "24"), ("colorScienceMode", "davinciYRGB"),
                       ("colorSpaceTimeline", "Rec.709 (Scene)")):
            nova.SetSetting(kk, vv)
        proj.SetCurrentTimeline(nova)
        mp.AppendToTimeline(mc)
        msg = f"Multicam '{nome_mc}' criado com {len(clipes)} ângulo(s) e timeline nova."
        st("Concluído", msg, 100, fim=time.time(), timeline=nova.GetName())
    except Exception as e:  # noqa: BLE001
        st("Erro", str(e), st.d["pct"], erro=str(e), fim=time.time())
        sys.exit(1)


if __name__ == "__main__":
    main()
