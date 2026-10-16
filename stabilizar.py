#!/usr/bin/env python3
"""Stabilizer: mede o tremor de cada clipe da timeline aberta e estabiliza só os que tremem.

O tremor é medido pela variação rápida do movimento (vidstab), então um pan ou um movimento lento e intencional
não conta. Clipes firmes ficam intactos. A estabilização é a do próprio DaVinci (Stabilize), sem mudar o modo.

Uso:
  .venv/bin/python stabilizar.py --modo analisar|aplicar [--sensibilidade leve|medio|forte] [--status x.json]
"""
import argparse
import os
import re
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("PYTHONUTF8", "1")
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
sys.path.append("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules")
from sincronizar import Status  # noqa: E402

FFMPEG = str(BASE / ".venv" / "bin" / "ffmpeg")
LIMITE = {"leve": 2.0, "medio": 1.2, "forte": 0.7}  # tremor (px, entre quadros) acima do qual o clipe é estabilizado
TRECHO_S = 4.0


def tremor(arquivo, inicio, dur=TRECHO_S):
    """Tremor de um trecho do clipe: variação rápida do deslocamento entre quadros (px, na imagem reduzida)."""
    import numpy as np
    L, A = 160, 90  # quadro reduzido para medir o movimento rápido
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-ss", f"{inicio:.3f}", "-i", arquivo, "-t", f"{dur:.3f}",
           "-vf", f"scale={L}:{A},format=gray", "-an", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    n = len(raw) // (L * A)
    if n < 12:
        return None
    quadros = np.frombuffer(raw[: n * L * A], dtype=np.uint8).reshape(n, A, L).astype(np.float32)
    quadros = quadros - quadros.mean(axis=(1, 2), keepdims=True)
    dxs, dys = [], []
    for a, b in zip(quadros, quadros[1:]):
        R = np.fft.rfft2(b) * np.conj(np.fft.rfft2(a))
        R /= np.abs(R) + 1e-9
        c = np.fft.irfft2(R, s=(A, L))
        iy, ix = np.unravel_index(np.argmax(c), c.shape)
        dys.append(iy - A if iy > A // 2 else iy)
        dxs.append(ix - L if ix > L // 2 else ix)
    dx, dy = np.array(dxs, float), np.array(dys, float)
    # tremor = variação rápida do movimento (um pan constante não conta)
    hf = np.abs(np.diff(dx)) + np.abs(np.diff(dy))
    return round(float(np.mean(hf)), 2) if hf.size else None


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
        tremidos, firmes, sem_leitura = [], 0, 0
        vistos = set()
        for n, (it, m) in enumerate(itens, 1):
            uid = it.GetUniqueId()
            if uid in vistos:
                continue
            vistos.add(uid)
            nome = it.GetName()
            st("Medindo", f"Clipe {n} de {len(itens)}: {nome}", 5 + int(80 * n / len(itens)))
            cfps = float(m.GetClipProperty("FPS") or fps)
            inicio = it.GetSourceStartFrame() / cfps
            valor = tremor(m.GetClipProperty("File Path"), inicio)
            if valor is None and not args.forcar:
                sem_leitura += 1
            elif valor is None or valor > limite or args.forcar:
                tremidos.append((nome, valor, it))
            else:
                firmes += 1
        aplicados = 0
        if args.modo == "aplicar":
            for nome, valor, it in tremidos:
                st("Estabilizando", f"Estabilizando {nome} (tremor {valor})…", 90)
                if it.Stabilize():
                    aplicados += 1
        resumo = (f"{len(tremidos)} clipe(s) tremendo (limite {limite}), {firmes} firme(s)"
                  + (f", {sem_leitura} sem leitura" if sem_leitura else ""))
        escopo = f"{len(itens)} clipe(s) selecionado(s)" if args.so_selecionados else f"{len(itens)} clipe(s) da timeline"
        if not tremidos:
            msg = (f"Nada a estabilizar: nenhum dos {escopo} tremeu acima do limite ({args.sensibilidade}). "
                   "Nada foi alterado. Para estabilizar mais, use Forte.")
        elif args.modo == "aplicar":
            msg = f"Estabilizados {aplicados} de {len(tremidos)} clipe(s) tremidos ({escopo}) · {firmes} firme(s) intactos"
        else:
            msg = f"Só análise (nada alterado): {len(tremidos)} de {escopo} tremem acima do limite · {firmes} firme(s)"
        st("Concluído", msg, 100, fim=time.time(), timeline=tl.GetName())
    except Exception as e:  # noqa: BLE001
        st("Erro", str(e), st.d["pct"], erro=str(e), fim=time.time())
        sys.exit(1)


if __name__ == "__main__":
    main()
