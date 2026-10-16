"""Ducking da trilha: a música abaixa enquanto há fala, com transições suaves, na própria timeline do DaVinci.

A fala vem do Whisper (faixa de voz). A trilha é cortada nos pontos de mudança e cada pedaço recebe o seu volume:
- a música abaixa um pouco depois que a fala começa;
- volta um pouco antes de a fala terminar;
- as transições são degraus de volume (fade in/out), para não soar brusco.

Uso:
  .venv/bin/python ducking.py --musica 2 [--voz 1] [--nivel -12] [--status projetos/_sync/x.json]
"""
import argparse
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTHONUTF8", "1")
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from sincronizar import Status  # noqa: E402
import silencios as SIL  # noqa: E402


def blocos_de_fala(falas_seg, dur, pre=0.2, volta_antes=0.4, junta=0.6):
    """Janelas em que a música fica baixa: começa um pouco antes da fala e volta um pouco antes de ela terminar."""
    blocos = []
    for a, b in falas_seg:
        a, b = max(0.0, a - pre), min(dur, b)
        if blocos and a - blocos[-1][1] < junta:
            blocos[-1][1] = max(blocos[-1][1], b)
        else:
            blocos.append([a, b])
    out = []
    for a, b in blocos:
        b = max(a + 0.2, b - volta_antes)
        if b > a:
            out.append((a, min(b, dur)))
    return out


def envelope(blocos, dur, nivel_db, fade=0.4, degraus=2):
    """Lista de pedaços (inicio, fim, dB) cobrindo 0..dur. Transições viram degraus de volume."""
    pontos = {0.0, dur}
    for a, b in blocos:
        for t in (a - fade, a, b, b + fade):
            if 0 < t < dur:
                pontos.add(max(0.0, t))
    pontos = sorted(pontos)
    pedacos = []
    for i in range(len(pontos) - 1):
        t1, t2 = pontos[i], pontos[i + 1]
        meio = (t1 + t2) / 2
        db = 0.0
        for a, b in blocos:
            if a <= meio <= b:
                db = nivel_db
                break
            if a - fade <= meio < a:  # descendo
                db = nivel_db * (meio - (a - fade)) / fade
                break
            if b < meio <= b + fade:  # subindo
                db = nivel_db * (1 - (meio - b) / fade)
                break
        if db == 0.0 or abs(nivel_db) < 0.01:
            pedacos.append((t1, t2, db))
            continue
        # transição: divide em degraus de volume
        if (t2 - t1) > fade / degraus:
            n = max(1, int(round((t2 - t1) / (fade / degraus))))
            for k in range(n):
                s1 = t1 + (t2 - t1) * k / n
                s2 = t1 + (t2 - t1) * (k + 1) / n
                pedacos.append((s1, s2, db))
        else:
            pedacos.append((t1, t2, db))
    return pedacos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--musica", type=int, required=True, help="número da faixa de áudio da trilha")
    ap.add_argument("--voz", type=int, help="faixa de voz (padrão: a com mais fala, exceto a música)")
    ap.add_argument("--nivel", type=float, default=-12.0, help="quanto a música abaixa durante a fala, em dB")
    ap.add_argument("--status")
    args = ap.parse_args()
    st = Status(args.status)
    st.d.update(nome="Ducking", tipo="sync")
    try:
        import DaVinciResolveScript as d  # noqa: N813
        r = d.scriptapp("Resolve")
        proj = r.GetProjectManager().GetCurrentProject()
        tl = proj.GetCurrentTimeline()
        if not tl:
            raise RuntimeError("Nenhuma timeline aberta.")
        tfps = float(tl.GetSetting("timelineFrameRate"))
        t0 = tl.GetStartFrame()
        st.d["nome"] = f"Ducking · {tl.GetName()}"
        st("Lendo", f"Lendo as faixas de '{tl.GetName()}'…", 3)
        n_a = tl.GetTrackCount("audio")
        musica = args.musica
        if not (1 <= musica <= n_a):
            raise RuntimeError(f"A faixa A{musica} não existe nesta timeline.")
        itens_musica = tl.GetItemListInTrack("audio", musica) or []
        if not itens_musica:
            raise RuntimeError(f"A faixa A{musica} está vazia.")
        for it in itens_musica:
            if any(True for _ in (it.GetLinkedItems() or [])):
                raise RuntimeError(f"A faixa A{musica} tem clipes ligados a vídeo. Use uma faixa de música só de áudio.")
        if args.voz is None:
            candidatas = [i for i in range(1, n_a + 1) if i != musica and tl.GetItemListInTrack("audio", i)]
            if not candidatas:
                raise RuntimeError("Não encontrei uma faixa de voz além da música.")
            args.voz = max(candidatas, key=lambda i: sum(x.GetDuration() for x in tl.GetItemListInTrack("audio", i)))
        itens_voz = tl.GetItemListInTrack("audio", args.voz) or []
        dur = (tl.GetEndFrame() - t0) / tfps
        st("Fala", f"Ouvindo a faixa A{args.voz} com o Whisper para achar a fala…", 10)
        fs, _ = SIL.falas(tl, itens_voz, tfps)
        if not fs:
            raise RuntimeError("Não encontrei fala na faixa de voz; nada foi alterado.")
        blocos = blocos_de_fala(fs, dur)
        st("Ducking", f"{len(blocos)} trecho(s) de fala — música em {args.nivel:g} dB", 40)
        pedacos = envelope(blocos, dur, args.nivel)

        # cada clipe da música é partido nos pedaços do envelope
        mp = proj.GetMediaPool()
        planos = []
        for it in itens_musica:
            m = it.GetMediaPoolItem()
            if not m:
                raise RuntimeError("A faixa da música tem clipes sem mídia; nada foi alterado.")
            cfps = float(m.GetClipProperty("FPS") or tfps)
            s = (it.GetStart() - t0) / tfps
            e = (it.GetEnd() - t0) / tfps
            src_in = it.GetSourceStartFrame()
            for a, b, db in pedacos:
                x1, x2 = max(a, s), min(b, e)
                if x2 - x1 < 0.02:
                    continue
                sa = round(src_in + (x1 - s) * cfps / tfps)
                sb = round(src_in + (x2 - s) * cfps / tfps)
                if sb <= sa:  # pedaço menor que um quadro: não dá para colocar
                    continue
                planos.append({"m": m, "src_a": sa, "src_b": sb,
                               "rec": t0 + round(x1 * tfps), "db": db, "cfps": cfps})
        if not planos:
            raise RuntimeError("Nada a aplicar.")

        st("Backup", "Salvando uma cópia de segurança da timeline (.drt)…", 60)
        bk = BASE / "projetos" / "_sync" / "backups"
        bk.mkdir(parents=True, exist_ok=True)
        arq_bk = bk / f"{''.join(c if c.isalnum() else '_' for c in tl.GetName())}_ducking_{time.strftime('%Y%m%d_%H%M%S')}.drt"
        if not tl.Export(str(arq_bk), r.EXPORT_DRT, r.EXPORT_NONE) or not arq_bk.exists():
            raise RuntimeError("Não consegui salvar o backup da timeline; nada foi alterado.")

        st("Trilha", f"Recortando a trilha em {len(planos)} pedaço(s)…", 75)
        tl.DeleteClips(itens_musica, False)
        recusados = 0
        for pl in planos:
            info = {"mediaPoolItem": pl["m"], "startFrame": pl["src_a"], "endFrame": pl["src_b"],
                    "trackIndex": musica, "recordFrame": pl["rec"], "mediaType": 2}
            novos = mp.AppendToTimeline([info]) or []
            if not novos:
                recusados += 1
                continue
            if abs(pl["db"]) > 0.01:
                novos[0].SetProperty("AudioVolume", pl["db"])
        msg = (f"Ducking aplicado em A{musica}: {len(blocos)} trecho(s) de fala, {len(planos)} pedaço(s), "
               f"{args.nivel:g} dB durante a fala.")
        if recusados:
            msg += f" {recusados} pedaço(s) não couberam e ficaram de fora."
        st("Concluído", msg, 100, fim=time.time(), timeline=tl.GetName())
    except Exception as e:  # noqa: BLE001
        st("Erro", str(e), st.d["pct"], erro=str(e), fim=time.time())
        sys.exit(1)


if __name__ == "__main__":
    main()
