#!/usr/bin/env python3
"""Analisa e melhora o áudio de voz da timeline aberta no DaVinci (na própria timeline, com recursos nativos).

Para cada clipe da faixa de voz (gravador/lapela): mede loudness (LUFS), pico, variação e ruído de fundo;
liga Voice Isolation na dose certa, Dialogue Leveler quando a fala oscila e normaliza para o alvo.
Opcionalmente abaixa o áudio das outras faixas (câmeras). Antes de mexer salva um backup .drt.

Uso:
  .venv/bin/python melhorar_audio.py [--ref N] [--alvo -16] [--cameras manter|abaixar] [--teste] [--status arq.json]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTHONUTF8", "1")
import numpy as np  # noqa: E402

BASE = Path(__file__).resolve().parent
FFMPEG = str(BASE / ".venv" / "bin" / "ffmpeg")
sys.path.append("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules")
os.environ.setdefault("RESOLVE_SCRIPT_LIB",
                      "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so")


class Status:
    def __init__(self, arq):
        self.arq = Path(arq) if arq else None
        self.d = {"nome": "Melhorar áudio", "projeto": "_sync", "tipo": "sync", "inicio": time.time(), "pid": os.getpid(),
                  "etapa": "", "msg": "", "pct": 0, "erro": None, "fim": None}

    def __call__(self, etapa, msg, pct, **kw):
        self.d.update(etapa=etapa, msg=msg, pct=pct, **kw)
        if self.arq:
            self.arq.parent.mkdir(parents=True, exist_ok=True)
            self.arq.write_text(json.dumps(self.d, ensure_ascii=False))
        print(f"[{pct:3d}%] {etapa}: {msg}", flush=True)


def medir(arquivo, ini, dur):
    """Loudness integrada (LUFS), faixa de loudness (LRA), pico e ruído (relação fala/ruído em dB)."""
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostats", "-ss", f"{max(0, ini):.3f}", "-i", arquivo, "-t", f"{dur:.3f}",
                        "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True)
    txt = r.stderr[r.stderr.rfind("Summary:"):]
    g = lambda pat: float(m[1]) if (m := re.search(pat, txt)) else None  # noqa: E731
    lufs, lra, pico = g(r"I:\s+(-?[\d.]+) LUFS"), g(r"LRA:\s+(-?[\d.]+) LU"), g(r"Peak:\s+(-?[\d.]+) dBFS")
    a = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-ss", f"{max(0, ini):.3f}", "-i", arquivo,
                        "-t", f"{dur:.3f}", "-vn", "-ac", "1", "-ar", "8000", "-f", "f32le", "-"], capture_output=True).stdout
    x = np.frombuffer(a, dtype=np.float32)
    snr = None
    if len(x) > 8000:
        w = 400  # janelas de 50 ms
        k = len(x) // w
        rms = np.sqrt((x[:k * w].reshape(k, w) ** 2).mean(1) + 1e-12)
        db = 20 * np.log10(rms)
        snr = float(np.percentile(db, 90) - np.percentile(db, 10))  # fala (alto) vs. fundo (baixo)
    return {"lufs": lufs, "lra": lra, "pico": pico, "snr": snr}


def decidir(m):
    """Dose de cada ferramenta a partir das medidas."""
    snr = m["snr"] if m["snr"] is not None else 25
    vi = 80 if snr < 15 else 60 if snr < 22 else 40 if snr < 30 else 20
    nivelar = (m["lra"] or 0) > 9 or (m["lufs"] or -20) < -30
    return {"voz_isolada": vi, "nivelar": nivelar}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", type=int)
    ap.add_argument("--alvo", type=float, default=-16.0, help="loudness alvo em LUFS (−14 YouTube, −16 internet, −23 TV)")
    ap.add_argument("--cameras", choices=["manter", "abaixar"], default="manter")
    ap.add_argument("--teste", action="store_true")
    ap.add_argument("--isolamento", default="auto", help="auto | off | 10..100 (%% de Voice Isolation)")
    ap.add_argument("--silencios", type=float, default=0.0, help="remove pausas sem fala maiores que N segundos (0 = não)")
    ap.add_argument("--prompt", default="", help="nomes, ajudam o Whisper a reconhecer a fala")
    ap.add_argument("--status")
    args = ap.parse_args()
    st = Status(args.status)
    try:
        import DaVinciResolveScript as d  # noqa: N813
        r = d.scriptapp("Resolve")
        proj = r.GetProjectManager().GetCurrentProject()
        tl = proj.GetCurrentTimeline()
        if not tl:
            raise RuntimeError("Nenhuma timeline aberta.")
        tfps = float(tl.GetSetting("timelineFrameRate"))
        st.d["nome"] = f"Melhorar áudio · {tl.GetName()}"
        faixas = {i: [it for it in (tl.GetItemListInTrack("audio", i) or []) if it.GetMediaPoolItem()]
                  for i in range(1, tl.GetTrackCount("audio") + 1)}
        ref_n = args.ref or max(faixas, key=lambda i: sum(it.GetEnd() - it.GetStart() for it in faixas[i]))
        itens = faixas[ref_n]
        if not itens:
            raise RuntimeError(f"A faixa A{ref_n} está vazia.")

        medidas = []
        for k, it in enumerate(itens, 1):
            st("Analisando", f"Medindo o áudio do clipe {k} de {len(itens)}…", 5 + int(60 * k / len(itens)))
            m = it.GetMediaPoolItem()
            cfps = float(m.GetClipProperty("FPS") or tfps)
            med = medir(m.GetClipProperty("File Path"), it.GetSourceStartFrame() / cfps, (it.GetEnd() - it.GetStart()) / tfps)
            medidas.append((it, med, decidir(med)))

        vals = [mm["lufs"] for _, mm, _ in medidas if mm["lufs"] is not None and mm["lufs"] > -70]
        snrs = [mm["snr"] for _, mm, _ in medidas if mm["snr"] is not None]
        media = float(np.mean(vals)) if vals else None
        resumo = (f"A{ref_n}: nível médio {media:.0f} LUFS → alvo {args.alvo:.0f}" if media is not None else f"A{ref_n}")
        if snrs:
            s = float(np.median(snrs))
            resumo += f" · ruído {'alto' if s < 18 else 'médio' if s < 26 else 'baixo'}"
        if args.teste:
            print(json.dumps([{"clipe": it.GetName(), **mm, **dd} for it, mm, dd in medidas], ensure_ascii=False, indent=1))
            st("Concluído", "Teste: " + resumo + " (nada foi alterado)", 100, fim=time.time())
            return

        st("Backup", "Salvando uma cópia de segurança da timeline (.drt)…", 70)
        bk = BASE / "projetos" / "_sync" / "backups"
        bk.mkdir(parents=True, exist_ok=True)
        arq_bk = bk / f"{''.join(c if c.isalnum() else '_' for c in tl.GetName())}_audio_{time.strftime('%Y%m%d_%H%M%S')}.drt"
        if not tl.Export(str(arq_bk), r.EXPORT_DRT, r.EXPORT_NONE) or not arq_bk.exists():
            raise RuntimeError("Não consegui salvar o backup da timeline; nada foi alterado.")

        corte = ""
        if args.silencios > 0:
            sys.path.insert(0, str(BASE))
            import silencios as SIL
            st("Silêncios", "Ouvindo a faixa de voz com o Whisper para achar as pausas…", 72)
            fs, dur = SIL.falas(tl, itens, tfps, args.prompt)
            if not fs:
                raise RuntimeError("Não encontrei fala na faixa de voz; nada foi cortado.")
            keep = SIL.manter(fs, dur, args.silencios)
            st("Silêncios", f"Removendo {max(0, len(keep) - 1)} pausa(s) de todas as faixas…", 78)
            novos, antes, depois = SIL.remontar(tl, proj.GetMediaPool(), keep, tfps)
            corte = f" · silêncios: {antes / 60:.1f} → {depois / 60:.1f} min"
            decisao = {it.GetUniqueId(): (mm, dd) for it, mm, dd in medidas}
            medidas = [(n, mm, dd) for uid, (mm, dd) in decisao.items() for n in novos.get(uid, [])]
            itens = [n for n, _, _ in medidas]
            faixas = {i: [it for it in (tl.GetItemListInTrack("audio", i) or []) if it.GetMediaPoolItem()]
                      for i in range(1, tl.GetTrackCount("audio") + 1)}

        st("Aplicando", "Ligando Voice Isolation e Dialogue Leveler…", 85)
        n_vi = n_lev = 0
        for it, mm, dd in medidas:
            if args.isolamento == "off":
                it.SetVoiceIsolationState({"isEnabled": False, "amount": 0})
            else:
                quanto = dd["voz_isolada"] if args.isolamento == "auto" else max(0, min(100, int(args.isolamento)))
                if it.SetVoiceIsolationState({"isEnabled": True, "amount": quanto}):
                    n_vi += 1
            if dd["nivelar"]:
                ok = it.SetProperty("AudioDialogueLevelerEnabled", True)
                it.SetProperty("AudioDialogueLevelerMode", r.DIALOGUE_LEVELER_MODE_OPTIMIZE_MODERATE_LEVELS)
                it.SetProperty("AudioDialogueLevelerLiftSoftDialogue", True)
                n_lev += 1 if ok else 0

        st("Normalizando", f"Normalizando a voz para {args.alvo:.0f} LUFS…", 90)
        tl.NormalizeAudioLevel(itens, {"normalizationMode": "ITU-R BS.1770-4", "targetLoudness": args.alvo,
                                       "setLevelMode": r.NORMALIZE_AUDIO_SET_LEVEL_INDEPENDENT})
        n_cam = 0
        if args.cameras == "abaixar":
            for i, lst in faixas.items():
                if i == ref_n:
                    continue
                for it in lst:
                    if it.SetProperty("AudioVolume", -15.0):
                        n_cam += 1
        vi_txt = ("Voice Isolation desligado" if args.isolamento == "off" else
                  f"Voice Isolation {'automático' if args.isolamento == 'auto' else args.isolamento + '%'} em {n_vi} clipe(s)")
        msg = (f"{resumo} · {vi_txt}" + (f" · nivelador em {n_lev}" if n_lev else "") + corte
               + (f" · câmeras −15 dB ({n_cam})" if n_cam else ""))
        st("Concluído", msg, 100, fim=time.time())
    except Exception as e:  # noqa: BLE001
        st("Erro", str(e), st.d["pct"], erro=str(e), fim=time.time())
        sys.exit(1)


if __name__ == "__main__":
    main()
