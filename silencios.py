"""Remoção de silêncios/ruídos na própria timeline do DaVinci.

A fala é detectada pelo Whisper (palavra por palavra) na faixa de voz — música e ruído de fundo não contam como fala.
Os trechos sem fala maiores que `pausa_min` são retirados de TODAS as faixas ao mesmo tempo (a sincronia se mantém):
a timeline é remontada só com os trechos mantidos, encostados uns nos outros, mesma faixa, vídeo e áudio religados.
"""
import os
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent
os.environ.setdefault("HF_HOME", str(BASE / ".modelos"))
os.environ["PATH"] = str(BASE / ".venv" / "bin") + os.pathsep + os.environ.get("PATH", "")
MODELO = "mlx-community/whisper-large-v3-turbo"


def falas(tl, ref_itens, tfps, prompt=""):
    """Intervalos de fala [(ini, fim)] em segundos da timeline, a partir das palavras do Whisper."""
    import mlx_whisper
    from de_davinci import montar_audio
    t0 = tl.GetStartFrame()
    dur = (tl.GetEndFrame() - t0) / tfps
    itens = []
    for it in ref_itens:
        m = it.GetMediaPoolItem()
        cfps = float(m.GetClipProperty("FPS") or tfps)
        itens.append({"ini": (it.GetStart() - t0) / tfps, "fim": (it.GetEnd() - t0) / tfps, "src_in": it.GetSourceStartFrame(),
                      "src_out": it.GetSourceEndFrame(), "arquivo": m.GetClipProperty("File Path"), "fps": cfps})
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "voz.wav"
        montar_audio(itens, dur, wav)
        res = mlx_whisper.transcribe(str(wav), path_or_hf_repo=MODELO, language="pt", word_timestamps=True,
                                     condition_on_previous_text=False, initial_prompt=prompt or None,
                                     hallucination_silence_threshold=2.0, verbose=None)
    out = []
    for s in res["segments"]:
        ws = [w for w in s.get("words", []) if w.get("probability", 1) >= 0.35]
        conf = sum(w.get("probability", 1) for w in s.get("words", [])) / max(1, len(s.get("words", [])))
        if conf < 0.6:  # segmento duvidoso = provável música/ruído interpretado como fala
            continue
        out += [(w["start"], w["end"]) for w in ws]
    return sorted(out), dur


def manter(falas_seg, dur, pausa_min, folga=0.15):
    """Trechos a manter: fala + folga, juntando pausas menores que pausa_min."""
    blocos = []
    for a, b in falas_seg:
        a, b = max(0.0, a - folga), min(dur, b + folga)
        if blocos and a - blocos[-1][1] < pausa_min:
            blocos[-1][1] = max(blocos[-1][1], b)
        else:
            blocos.append([a, b])
    return [(a, b) for a, b in blocos if b - a > 0.05]


def remontar(tl, mp, manter_seg, tfps):
    """Remonta a timeline só com os trechos mantidos. Devolve {uid_original: [novos TimelineItem]}."""
    t0 = tl.GetStartFrame()
    todos = []
    for tipo in ("video", "audio"):
        for i in range(1, tl.GetTrackCount(tipo) + 1):
            for it in tl.GetItemListInTrack(tipo, i) or []:
                m = it.GetMediaPoolItem()
                if not m:
                    raise RuntimeError("A timeline tem títulos, geradores ou efeitos sem mídia — "
                                       "tire-os antes de remover silêncios (ou desmarque essa opção).")
                todos.append({"it": it, "uid": it.GetUniqueId(), "tipo": tipo, "faixa": i, "m": m,
                              "cfps": float(m.GetClipProperty("FPS") or tfps), "src_in": it.GetSourceStartFrame(),
                              "ini": it.GetStart(), "fim": it.GetEnd(), "cor": it.GetClipColor()})
    # grupos ligados (vídeo + áudio do mesmo clipe)
    grupo = {x["uid"]: x["uid"] for x in todos}
    for x in todos:
        for li in x["it"].GetLinkedItems() or []:
            grupo[li.GetUniqueId()] = grupo.get(x["uid"], x["uid"])
    K = [(t0 + int(round(a * tfps)), t0 + int(round(b * tfps))) for a, b in manter_seg]
    pos, acum = [], 0
    for a, b in K:
        pos.append(acum)
        acum += b - a
    pecas = {}
    for x in todos:
        for k, (a, b) in enumerate(K):
            s, e = max(x["ini"], a), min(x["fim"], b)
            if e - s < 1:
                continue
            src_a = x["src_in"] + (s - x["ini"]) * x["cfps"] / tfps
            pecas.setdefault((grupo[x["uid"]], k), []).append(
                (x, {"mediaPoolItem": x["m"], "startFrame": src_a, "endFrame": src_a + (e - s) * x["cfps"] / tfps,
                     "trackIndex": x["faixa"], "recordFrame": t0 + pos[k] + (s - a),
                     "mediaType": 1 if x["tipo"] == "video" else 2}))
    tl.DeleteClips([x["it"] for x in todos], False)
    novos = {}
    for (_, _k), lista in sorted(pecas.items(), key=lambda kv: kv[0][1]):
        criados = []
        for x, info in lista:
            r = mp.AppendToTimeline([info]) or []
            for it in r:
                if x["cor"]:
                    it.SetClipColor(x["cor"])
                novos.setdefault(x["uid"], []).append(it)
            criados += r
        if len(criados) > 1:
            tl.SetClipsLinked(criados, True)
    antes = (max(x["fim"] for x in todos) - t0) / tfps if todos else 0
    return novos, antes, acum / tfps
