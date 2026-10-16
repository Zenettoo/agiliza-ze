#!/usr/bin/env python3
"""Sincroniza pela forma de onda os clipes da timeline aberta no DaVinci.

Você monta os clipes brutos numa timeline (uma faixa por câmera) e o gravador/lapela numa faixa de áudio.
O script compara o áudio de cada clipe com o da referência e corrige a posição NA PRÓPRIA timeline: só os clipes
fora de sincronia são retirados e recolocados no ponto certo (mesma faixa, vídeo e áudio ligados). Antes, salva um
backup .drt em projetos/_sync/backups (7 dias). Clipes com confiança baixa não se movem e ficam em vermelho.

Uso:
  .venv/bin/python sincronizar.py [--ref N] [--teste] [--status projetos/_sync/x.json]
    --ref N   faixa de áudio de referência (padrão: a de maior duração total)
    --teste   não cria nada: só mede o erro contra as posições atuais (para validar numa timeline já sincronizada)
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTHONUTF8", "1")
import numpy as np  # noqa: E402

BASE = Path(__file__).resolve().parent
FFMPEG = str(BASE / ".venv" / "bin" / "ffmpeg")
SR = 4000            # 4 kHz basta para alinhar com precisão de ~1 ms
CONF_MIN = 1.8       # pico/segundo pico abaixo disso = sincronização duvidosa
sys.path.append("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules")
os.environ.setdefault("RESOLVE_SCRIPT_LIB",
                      "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so")


class Status:
    def __init__(self, arq):
        self.arq = Path(arq) if arq else None
        self.d = {"nome": "Sincronização", "projeto": "_sync", "tipo": "sync", "inicio": time.time(), "pid": os.getpid(),
                  "etapa": "", "msg": "", "pct": 0, "erro": None, "fim": None}

    def __call__(self, etapa, msg, pct, **kw):
        self.d.update(etapa=etapa, msg=msg, pct=pct, **kw)
        if self.arq:
            self.arq.parent.mkdir(parents=True, exist_ok=True)
            self.arq.write_text(json.dumps(self.d, ensure_ascii=False))
        print(f"[{pct:3d}%] {etapa}: {msg}", flush=True)


def audio(arquivo, ini, dur):
    r = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-ss", f"{max(0, ini):.3f}", "-i", arquivo,
                        "-t", f"{dur:.3f}", "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32) if r.returncode == 0 else np.zeros(0, np.float32)


def item_info(it, tl, tfps):
    m = it.GetMediaPoolItem()
    if not m or not m.GetClipProperty("File Path"):
        return None
    cfps = float(m.GetClipProperty("FPS") or tfps)
    return {"it": it, "m": m, "arquivo": m.GetClipProperty("File Path"), "cfps": cfps,
            "src_in": it.GetSourceStartFrame(), "src_out": it.GetSourceEndFrame(),
            "ini": (it.GetStart() - tl.GetStartFrame()) / tfps, "fim": (it.GetEnd() - tl.GetStartFrame()) / tfps,
            "nome": it.GetName()}


class Referencia:
    """Áudio da faixa de referência posto no tempo da timeline, já no domínio da frequência (GCC-PHAT)."""

    def __init__(self, itens, dur):
        n = int(dur * SR) + SR
        sinal = np.zeros(n, np.float32)
        for x in itens:
            a = audio(x["arquivo"], x["src_in"] / x["cfps"], x["fim"] - x["ini"])
            p = int(x["ini"] * SR)
            sinal[p:p + len(a)] = a[: n - p]
        self.n = n
        self.sinal = sinal

    def alinhar(self, clipe):
        """Devolve (atraso em segundos na timeline, confiança)."""
        if len(clipe) < SR:  # menos de 1 s de áudio
            return None, 0.0
        nfft = 1 << int(np.ceil(np.log2(self.n + len(clipe))))
        if getattr(self, "_nfft", None) != nfft:  # espectro da referência calculado uma vez por tamanho
            self._nfft, self._R = nfft, np.fft.rfft(self.sinal, nfft).astype(np.complex64)
        R = self._R
        C = np.fft.rfft(clipe, nfft).astype(np.complex64)
        X = R * np.conj(C)
        X /= np.abs(X) + 1e-9                     # PHAT: só a fase, robusto a microfones diferentes
        cc = np.fft.irfft(X, nfft)[: self.n]      # atrasos positivos: o clipe começa depois do início da timeline
        k = int(np.argmax(cc))
        # confiança = pico / segundo melhor pico fora de ±0,5 s (encaixe falso fica perto de 1)
        viz = int(0.5 * SR)
        resto = np.concatenate([cc[:max(0, k - viz)], cc[k + viz:]])
        segundo = float(resto.max()) if len(resto) else 0.0
        return k / SR, float(cc[k] / max(segundo, 1e-12))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", type=int)
    ap.add_argument("--teste", action="store_true")
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
        st.d["nome"] = f"Sincronizar · {tl.GetName()}"
        st("Lendo", f"Lendo a timeline '{tl.GetName()}'…", 2)

        faixas_a = {i: [x for x in (item_info(it, tl, tfps) for it in tl.GetItemListInTrack("audio", i) or []) if x]
                    for i in range(1, tl.GetTrackCount("audio") + 1)}
        faixas_v = {i: [x for x in (item_info(it, tl, tfps) for it in tl.GetItemListInTrack("video", i) or []) if x]
                    for i in range(1, tl.GetTrackCount("video") + 1)}
        ref_n = args.ref or max(faixas_a, key=lambda i: sum(x["fim"] - x["ini"] for x in faixas_a[i]))
        ref_itens = faixas_a[ref_n]
        if not ref_itens:
            raise RuntimeError(f"A faixa de áudio A{ref_n} (referência) está vazia.")
        dur = (tl.GetEndFrame() - tl.GetStartFrame()) / tfps
        st("Referência", f"Montando o áudio de referência (A{ref_n}, {len(ref_itens)} clipe(s))…", 8)
        ref = Referencia(ref_itens, dur)

        # Clipes a alinhar: cada clipe de vídeo (com o próprio áudio) e os de áudio fora da referência sem vídeo par
        com_video = {(x["arquivo"], x["src_in"]) for i in faixas_v for x in faixas_v[i]}
        alvos = [("video", i, x) for i in faixas_v for x in faixas_v[i]]
        alvos += [("audio", i, x) for i in faixas_a if i != ref_n for x in faixas_a[i]
                  if (x["arquivo"], x["src_in"]) not in com_video]
        res = []
        for k, (tipo, faixa, x) in enumerate(alvos, 1):
            st("Sincronizando", f"Clipe {k} de {len(alvos)}: {x['nome']}", 10 + int(75 * k / max(1, len(alvos))))
            a = audio(x["arquivo"], x["src_in"] / x["cfps"], (x["src_out"] - x["src_in"]) / x["cfps"])
            ini, conf = ref.alinhar(a)
            res.append({"tipo": tipo, "faixa": faixa, "x": x, "ini": ini, "conf": conf,
                        "ok": ini is not None and conf >= CONF_MIN})

        ref_ids = {(x["arquivo"], x["src_in"]) for x in ref_itens}
        ok = sum(1 for z in res if z["ok"] and (z["x"]["arquivo"], z["x"]["src_in"]) not in ref_ids)
        total = sum(1 for z in res if (z["x"]["arquivo"], z["x"]["src_in"]) not in ref_ids)
        if args.teste:
            res = [z for z in res if z["faixa"] != ref_n]  # o que está na referência casaria consigo mesmo
            ok = sum(1 for z in res if z["ok"])
            erros = [abs(z["ini"] - z["x"]["ini"]) for z in res if z["ok"]]
            bons = sum(1 for e in erros if e <= 1.0 / tfps)
            print(json.dumps({"clipes": len(res), "confiantes": ok, "erro_mediano_ms": round(1000 * float(np.median(erros)), 1)
                              if erros else None, "dentro_de_1_frame": bons,
                              "piores": sorted([(round(abs(z['ini'] - z['x']['ini']), 3), z['x']['nome'], round(z['conf'], 1))
                                                for z in res if z['ok']], reverse=True)[:5],
                              "duvidosos": [(z['x']['nome'], round(z['conf'], 1)) for z in res if not z['ok']][:10]},
                             ensure_ascii=False, indent=1))
            st("Concluído", "Teste concluído (nada foi criado).", 100, fim=time.time())
            return

        # ---- aplica NA PRÓPRIA timeline: só os clipes fora de sincronia são retirados e recolocados ----
        mover = [z for z in res if z["ok"] and (z["x"]["arquivo"], z["x"]["src_in"]) not in ref_ids
                 and abs(z["ini"] - z["x"]["ini"]) * tfps >= 0.5]
        duvid = [z for z in res if not z["ok"]]
        if mover:
            st("Backup", "Salvando uma cópia de segurança da timeline (.drt)…", 88)
            bk = BASE / "projetos" / "_sync" / "backups"
            bk.mkdir(parents=True, exist_ok=True)
            for f in bk.glob("*.drt"):  # guarda só 7 dias
                if time.time() - f.stat().st_mtime > 7 * 86400:
                    f.unlink()
            arq_bk = bk / f"{''.join(c if c.isalnum() else '_' for c in tl.GetName())}_{time.strftime('%Y%m%d_%H%M%S')}.drt"
            if not tl.Export(str(arq_bk), r.EXPORT_DRT, r.EXPORT_NONE) or not arq_bk.exists():
                raise RuntimeError("Não consegui salvar o backup da timeline; nada foi alterado.")
            st("Sincronizando", f"Reposicionando {len(mover)} clipe(s) na timeline…", 92)
            mp = proj.GetMediaPool()
            t0 = tl.GetStartFrame()
            planos = []
            for z in mover:
                pecas = [z["x"]["it"]] + [li for li in (z["x"]["it"].GetLinkedItems() or [])]
                vistos, lista = set(), []
                for it in pecas:
                    uid = it.GetUniqueId()
                    if uid in vistos:
                        continue
                    vistos.add(uid)
                    tipo, faixa = it.GetTrackTypeAndIndex()
                    lista.append({"it": it, "tipo": tipo, "faixa": faixa, "m": it.GetMediaPoolItem(),
                                  "a": it.GetSourceStartFrame(), "b": it.GetSourceEndFrame(),
                                  "desloc": (it.GetStart() - z["x"]["it"].GetStart())})
                planos.append((z, lista))
            tl.DeleteClips([pc["it"] for _, lista in planos for pc in lista], False)
            for z, lista in planos:
                destino = t0 + int(round(z["ini"] * tfps))
                novos = []
                for pc in lista:
                    novos += mp.AppendToTimeline([{"mediaPoolItem": pc["m"], "startFrame": pc["a"], "endFrame": pc["b"],
                                                   "trackIndex": pc["faixa"], "recordFrame": destino + pc["desloc"],
                                                   "mediaType": 1 if pc["tipo"] == "video" else 2}]) or []
                if len(novos) > 1:
                    tl.SetClipsLinked(novos, True)
        for z in duvid:  # duvidosos ficam onde estão, marcados em vermelho
            z["x"]["it"].SetClipColor("Red")
            for li in z["x"]["it"].GetLinkedItems() or []:
                li.SetClipColor("Red")
        msg = (f"'{tl.GetName()}': {ok} de {total} clipes conferidos com a referência"
               f" · {len(mover)} reposicionado(s)" + (f" · {len(duvid)} em vermelho para conferir" if duvid else ""))
        st("Concluído", msg, 100, fim=time.time(), timeline=tl.GetName())
    except Exception as e:  # noqa: BLE001
        st("Erro", str(e), st.d["pct"], erro=str(e), fim=time.time())
        sys.exit(1)


if __name__ == "__main__":
    main()
