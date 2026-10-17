#!/usr/bin/env python3
"""Stabilizer: mede o tremor de cada clipe da timeline aberta e estabiliza só os que tremem.

Não usa o Stabilize do DaVinci: o modo automático dele (Perspective) rastreia o quadro inteiro, inclusive pessoas
e primeiro plano desfocado, e deforma a imagem (efeito gelatina). Aqui o movimento da câmera é medido só pelos
pontos que se movem juntos (RANSAC descarta quem se mexe sozinho) e a correção é só deslocamento + rotação,
num Transform animado na composição Fusion do clipe. O balanço lento (andar, flutuar) é preservado; sai só o
tremor rápido. Clipes firmes ficam intactos.

Uso:
  .venv/bin/python stabilizar.py --modo analisar|aplicar [--sensibilidade leve|medio|forte] [--status x.json]
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

os.environ.setdefault("PYTHONUTF8", "1")
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
sys.path.append("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules")
from sincronizar import Status  # noqa: E402

FFMPEG = str(BASE / ".venv" / "bin" / "ffmpeg")
# tremor (px em 1080p, faixa acima de 1 Hz) acima do qual o clipe é estabilizado
LIMITE = {"leve": 4.0, "medio": 2.5, "forte": 1.5}
# suavização do caminho da câmera (s): quanto maior, mais firme (e mais zoom)
SUAVE = {"leve": 0.35, "medio": 0.6, "forte": 1.0}
ZOOM_MAX = 1.12  # nunca corta mais que isso; se precisar, a correção é limitada
NOME_TOOL = "Estabilizar_AgilizaZe"
W, H = 960, 540  # quadro reduzido para medir


def trajetoria(arquivo, inicio_s, n, fps):
    """Movimento da câmera entre quadros consecutivos: [(dx, dy) em fração do quadro, ângulo em graus]."""
    import cv2
    raw = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-ss", f"{inicio_s:.4f}", "-i", arquivo,
                          "-vf", f"scale={W}:{H},format=gray", "-frames:v", str(n), "-an", "-f", "rawvideo", "-"],
                         capture_output=True).stdout
    k = len(raw) // (W * H)
    if k < 12:
        return None
    q = np.frombuffer(raw[:k * W * H], np.uint8).reshape(k, H, W)
    c = np.array([W / 2, H / 2])
    passos = [(0.0, 0.0, 0.0)]
    for a, b in zip(q, q[1:]):
        p = (0.0, 0.0, 0.0)
        pa = cv2.goodFeaturesToTrack(a, 400, 0.01, 12, blockSize=7)
        if pa is not None and len(pa) >= 12:
            pb, ok, _ = cv2.calcOpticalFlowPyrLK(a, b, pa, None, winSize=(21, 21), maxLevel=3)
            ok = ok.ravel() == 1
            if ok.sum() >= 12:
                M, _ = cv2.estimateAffinePartial2D(pa[ok], pb[ok], method=cv2.RANSAC, ransacReprojThreshold=1.5)
                if M is not None:
                    t = M[:, 2] + M[:, :2] @ c - c  # deslocamento do centro do quadro
                    p = (t[0] / W, t[1] / H, float(np.degrees(np.arctan2(M[1, 0], M[0, 0]))))
        passos.append(p)
    return np.cumsum(np.array(passos), axis=0)  # caminho da câmera, quadro a quadro


def tremor_1080(cam, fps):
    """Tremor rápido (acima de ~1 Hz) em px de 1080p: o que sobra tirando o caminho suave."""
    from scipy.ndimage import gaussian_filter1d
    xy = cam[:, :2] * [1920, 1080]
    rapido = xy - gaussian_filter1d(xy, 0.15 * fps, axis=0, mode="nearest")
    return round(float(np.sqrt((rapido ** 2).sum(1).mean())), 2)


def correcao(cam, fps, suave):
    """Quanto mover/girar cada quadro para seguir o caminho suave, e o zoom que esconde as bordas."""
    from scipy.ndimage import gaussian_filter1d
    j = cam - gaussian_filter1d(cam, suave * fps, axis=0, mode="nearest")
    precisa = 1 + 2 * max(np.abs(j[:, 0]).max(), np.abs(j[:, 1]).max()) + 2 * np.radians(np.abs(j[:, 2]).max()) + 0.005
    if precisa > ZOOM_MAX:  # tremor grande demais: corrige o que cabe no zoom máximo
        j *= (ZOOM_MAX - 1) / (precisa - 1)
        precisa = ZOOM_MAX
    return j, round(float(precisa), 4)


def comp_do_clipe(it):
    """Composição onde fica o nosso Transform: a que já o tem, ou uma nova se o clipe não tiver Fusion."""
    for i in range(1, (it.GetFusionCompCount() or 0) + 1):
        comp = it.GetFusionCompByIndex(i)
        if comp and comp.FindTool(NOME_TOOL):
            return comp
    if it.GetFusionCompCount():
        return None  # o clipe já tem um Fusion feito à mão: não mexe
    return it.AddFusionComp()


def aplicar(it, j, zoom):
    comp = comp_do_clipe(it)
    if not comp:
        return False
    a = comp.GetAttrs()
    f0 = int(a["COMPN_RenderStart"])
    mi, mo = comp.FindTool("MediaIn1"), comp.FindTool("MediaOut1")
    if not mi or not mo:
        return False
    comp.Lock()
    try:
        velho = comp.FindTool(NOME_TOOL)
        if velho:
            velho.Delete()
        tr = comp.AddTool("Transform", 1, 0)
        tr.SetAttrs({"TOOLS_Name": NOME_TOOL})
        tr.Input = mi.Output
        mo.Input = tr.Output
        tr.Center = comp.XYPath()
        xy = tr.Center.GetConnectedOutput().GetTool()
        tr.Angle = comp.BezierSpline()
        # quadro k da composição = quadro k da câmera a partir do início usado do clipe
        for k in range(len(j)):
            xy.X[f0 + k] = 0.5 - j[k, 0]
            xy.Y[f0 + k] = 0.5 + j[k, 1]  # no Fusion o Y cresce para cima
            tr.Angle[f0 + k] = j[k, 2]
    finally:
        comp.Unlock()
    tr.Size = zoom  # fora do Lock: avisa a timeline que a composição mudou (senão o DaVinci usa o cache antigo)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modo", choices=("analisar", "aplicar"), default="analisar")
    ap.add_argument("--sensibilidade", choices=tuple(LIMITE), default="medio")
    ap.add_argument("--status")
    ap.add_argument("--so-selecionados", action="store_true", help="só os clipes selecionados na timeline")
    ap.add_argument("--forcar", action="store_true", help="estabiliza mesmo os clipes que estão firmes")
    args = ap.parse_args()
    st = Status(args.status)
    st.d.update(nome="Stabilizer", tipo="sync")
    try:
        import DaVinciResolveScript as d  # noqa: N813
        r = d.scriptapp("Resolve")
        proj = r.GetProjectManager().GetCurrentProject()
        tl = proj.GetCurrentTimeline()
        if not tl:
            raise RuntimeError("Nenhuma timeline aberta.")
        st.d["nome"] = f"Stabilizer · {tl.GetName()}"
        fps = float(tl.GetSetting("timelineFrameRate") or 24)
        itens = []
        for i in range(1, tl.GetTrackCount("video") + 1):
            for it in tl.GetItemListInTrack("video", i) or []:
                m = it.GetMediaPoolItem()
                if m and m.GetClipProperty("File Path"):
                    itens.append((it, m))
        if args.so_selecionados:
            escolhidos = {c.GetUniqueId() for c in (tl.GetSelectedClips() or [])}
            itens = [(it, m) for it, m in itens if it.GetUniqueId() in escolhidos]
            if not itens:
                raise RuntimeError("Nenhum clipe de vídeo selecionado na timeline. Selecione os clipes e tente de novo.")
            st.d["nome"] = f"Stabilizer · {len(itens)} clipe(s) selecionado(s) · {tl.GetName()}"
        if not itens:
            raise RuntimeError("Não há clipes de vídeo com arquivo na timeline.")
        if args.modo == "aplicar":
            st("Backup", "Salvando uma cópia de segurança da timeline (.drt)…", 3)
            bk = BASE / "projetos" / "_sync" / "backups"
            bk.mkdir(parents=True, exist_ok=True)
            arq_bk = bk / f"{''.join(c if c.isalnum() else '_' for c in tl.GetName())}_stabilizer_{time.strftime('%Y%m%d_%H%M%S')}.drt"
            if not tl.Export(str(arq_bk), r.EXPORT_DRT, r.EXPORT_NONE) or not arq_bk.exists():
                raise RuntimeError("Não consegui salvar o backup da timeline; nada foi alterado.")
        limite = LIMITE[args.sensibilidade]
        tremidos, firmes, sem_leitura, com_fusion = [], 0, 0, 0
        vistos = set()
        for n, (it, m) in enumerate(itens, 1):
            uid = it.GetUniqueId()
            if uid in vistos:
                continue
            vistos.add(uid)
            nome = it.GetName()
            st("Medindo", f"Clipe {n} de {len(itens)}: {nome} (rastreando o movimento da câmera)…", 5 + int(80 * (n - 1) / len(itens)))
            cfps = float(m.GetClipProperty("FPS") or fps)
            s0, s1 = it.GetSourceStartFrame(), it.GetSourceEndFrame()
            cam = trajetoria(m.GetClipProperty("File Path"), s0 / cfps, s1 - s0 + 1, cfps)
            valor = tremor_1080(cam, cfps) if cam is not None else None
            if valor is None:
                sem_leitura += 1
            elif valor > limite or args.forcar:
                tremidos.append((nome, valor, it, cam, cfps))
            else:
                firmes += 1
        aplicados, zooms = 0, []
        if args.modo == "aplicar":
            for k, (nome, valor, it, cam, cfps) in enumerate(tremidos, 1):
                st("Estabilizando", f"Estabilizando {nome} (tremor {valor} px)…", 85 + int(14 * k / len(tremidos)))
                j, zoom = correcao(cam, cfps, SUAVE[args.sensibilidade])
                if aplicar(it, j, zoom):
                    aplicados += 1
                    zooms.append(zoom)
                else:
                    com_fusion += 1
        resumo_zoom = f" · zoom de {100 * (min(zooms) - 1):.0f}–{100 * (max(zooms) - 1):.0f}%" if zooms else ""
        escopo = f"{len(itens)} clipe(s) selecionado(s)" if args.so_selecionados else f"{len(itens)} clipe(s) da timeline"
        extra = (f" · {sem_leitura} sem leitura" if sem_leitura else "") + \
                (f" · {com_fusion} já tinham Fusion próprio (não mexi)" if com_fusion else "")
        if not tremidos:
            msg = (f"Nada a estabilizar: nenhum dos {escopo} tremeu acima de {limite} px ({args.sensibilidade}). "
                   "Nada foi alterado. Para estabilizar mais, use Forte." + extra)
        elif args.modo == "aplicar":
            msg = (f"Estabilizados {aplicados} de {len(tremidos)} clipe(s) (só deslocamento e rotação, sem gelatina)"
                   f"{resumo_zoom} · {firmes} firme(s) intactos{extra}")
        else:
            detalhe = ", ".join(f"{nm} {v} px" for nm, v, *_ in tremidos[:6])
            msg = (f"Só análise (nada alterado): {len(tremidos)} de {escopo} tremem acima de {limite} px ({detalhe})"
                   f" · {firmes} firme(s){extra}")
        st("Concluído", msg, 100, fim=time.time(), timeline=tl.GetName())
    except Exception as e:  # noqa: BLE001
        st("Erro", str(e), st.d["pct"], erro=str(e), fim=time.time())
        sys.exit(1)


if __name__ == "__main__":
    main()
