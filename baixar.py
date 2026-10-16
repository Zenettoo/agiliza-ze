#!/usr/bin/env python3
"""Baixa um vídeo ou só o áudio por link (YouTube, Instagram…) para projetos/_downloads.

Spotify não é aceito: o áudio de lá é protegido e não há como baixar direto. Use música licenciada
ou material que você tem direito de usar. Só o primeiro item é baixado, mesmo se o link for de playlist.

Uso:
  .venv/bin/python baixar.py --url https://… [--formato video|audio] [--status projetos/_sync/x.json]
"""
import argparse
import os
import re
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTHONUTF8", "1")
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from sincronizar import Status  # noqa: E402

DESTINO = BASE / "projetos" / "_downloads"
FFMPEG = str(BASE / ".venv" / "bin" / "ffmpeg")


def verificar(url):
    if not re.match(r"^https?://\S+$", url):
        raise RuntimeError("Cole um link completo, começando com https://")
    if "spotify.com" in url or url.startswith("spotify:"):
        raise RuntimeError("O Spotify não deixa baixar o áudio (é protegido). Use música licenciada "
                           "ou material que você tem direito de usar.")


def importar_no_davinci(arq):
    """Mesmo destino do botão → DaVinci: pasta Trilhas do media pool, sem mexer na timeline."""
    import DaVinciResolveScript as d  # noqa: N813
    r = d.scriptapp("Resolve")
    if not r:
        raise RuntimeError("DaVinci fechado")
    proj = r.GetProjectManager().GetCurrentProject()
    if not proj:
        raise RuntimeError("nenhum projeto aberto")
    mp = proj.GetMediaPool()
    raiz = mp.GetRootFolder()
    trilhas = next((f for f in raiz.GetSubFolderList() or [] if f.GetName() == "Trilhas"), None) or mp.AddSubFolder(raiz, "Trilhas")
    mp.SetCurrentFolder(trilhas)
    if not mp.ImportMedia([str(arq)]):
        raise RuntimeError("o DaVinci não aceitou o arquivo")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--formato", choices=("video", "audio"), default="video")
    ap.add_argument("--status")
    ap.add_argument("--audio-format", choices=("mp3", "wav"), default="mp3")
    ap.add_argument("--qualidade", choices=("best", "1080", "720", "480"), default="best")
    ap.add_argument("--importar", action="store_true", help="importa o arquivo para a pasta Trilhas do DaVinci")
    ap.add_argument("--destino", help="pasta onde salvar (padrão: projetos/_downloads)")
    args = ap.parse_args()
    st = Status(args.status)
    st.d.update(nome="Download", tipo="sync")
    try:
        verificar(args.url)
        import yt_dlp
        destino = Path(args.destino) if args.destino else DESTINO
        destino.mkdir(parents=True, exist_ok=True)
        st.d["nome"] = f"Download · {args.url[:60]}"
        st("Consultando", "Lendo o link…", 3)

        ultimo = {"pct": -1}

        def gancho(d):
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                pct = int(100 * d["downloaded_bytes"] / total) if total else 0
                if pct != ultimo["pct"]:  # não grava o status a cada pedaço
                    ultimo["pct"] = pct
                    st("Baixando", f"{pct}%", 5 + int(pct * 0.9))
            elif d["status"] == "finished":
                st("Processando", "Juntando áudio e vídeo…", 96)

        opts = {"outtmpl": str(destino / "%(title).80s [%(id)s].%(ext)s"), "noplaylist": True,
                "quiet": True, "no_warnings": True, "progress_hooks": [gancho], "ffmpeg_location": FFMPEG,
                "extractor_args": {"youtube": {"player_client": ["android"]}}}
        if args.formato == "audio":
            opts.update(format="bestaudio/best",
                        postprocessors=[{"key": "FFmpegExtractAudio", "preferredcodec": args.audio_format, "preferredquality": "192"}])
        else:
            alt = "" if args.qualidade == "best" else f"[height<={args.qualidade}]"
            opts.update(format=f"bv*{alt}[ext=mp4]+ba[ext=m4a]/b{alt}[ext=mp4]/bv*{alt}+ba/b{alt}", merge_output_format="mp4")
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(args.url, download=True)
            arq = Path(ydl.prepare_filename(info))
        if args.formato == "audio":
            arq = arq.with_suffix("." + args.audio_format)
        nota = ""
        if args.importar:
            try:
                importar_no_davinci(arq)
                nota = " · importado na pasta Trilhas do DaVinci"
            except Exception as e:  # noqa: BLE001
                nota = f" · não consegui importar no DaVinci ({e})"
        st("Concluído", f"Salvo em {destino}: {arq.name}{nota}", 100, fim=time.time(), arquivo=arq.name)
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if "not a bot" in msg or "Sign in to confirm" in msg:
            msg = ("O YouTube pediu confirmação de que não é robô e bloqueou o acesso. "
                   "Nada foi baixado. Tente de novo mais tarde.")
        st("Erro", msg, st.d["pct"], erro=msg, fim=time.time())
        sys.exit(1)


if __name__ == "__main__":
    main()
