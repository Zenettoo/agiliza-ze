#!/usr/bin/env python3
"""Transcreve vídeo/áudio localmente (Whisper no chip Apple) para a decupagem.

Uso:
  ./decupar "cerimonia.mov" ["parte2.mov" ...] [--nome "Ana e Pedro - cerimonia"]
            [--inicio 00:03:20] [--fim 00:45:00] [--prompt "nomes..."]
  ./decupar --lista trechos.json --nome "..."     (trechos: [{arquivo, inicio, fim}] em segundos)

Gera em projetos/<nome>/:
  transcricao.json  segmentos e palavras com tempo (segundos dentro de cada arquivo)
  transcricao.txt   versão compacta para leitura: [#id ARQUIVO mm:ss-mm:ss] texto
  transcricao.srt   legenda bruta (arquivos em fila)
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parent
FFMPEG = str(BASE / ".venv" / "bin" / "ffmpeg")
os.environ.setdefault("HF_HOME", str(BASE / ".modelos"))
os.environ["PATH"] = str(BASE / ".venv" / "bin") + os.pathsep + os.environ["PATH"]

import mlx_whisper  # noqa: E402

MODELO = "mlx-community/whisper-large-v3-turbo"

# Frases que o Whisper "inventa" em trechos de música/silêncio
ALUCINACOES = [
    "amara.org", "legendas pela comunidade", "obrigado por assistir",
    "inscreva-se", "legendado por", "transcrição e legendas",
    "e aí, pessoal", "tchau, tchau",
]

# Só nomes e vocabulário: frases esperadas no prompt fazem o Whisper inventar fala
PROMPT_PADRAO = "Casamento. Celebrante, padre, noivo, noiva, padrinhos, madrinhas, leitura, homilia, alianças."


def tc(seg: float) -> str:
    seg = max(0, seg)
    h, r = divmod(int(seg), 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def srt_tc(seg: float) -> str:
    ms = int(round(max(0, seg) * 1000))
    h, r = divmod(ms, 3_600_000)
    m, r = divmod(r, 60_000)
    s, ms = divmod(r, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def para_segundos(txt):
    if not txt:
        return None
    total = 0.0
    for p in txt.split(":"):
        total = total * 60 + float(p)
    return total


def slug(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", txt).strip("_") or "projeto"


def eh_alucinacao(texto: str) -> bool:
    t = texto.lower().strip()
    return not t or any(a in t for a in ALUCINACOES)


def duracao_arquivo(caminho: Path) -> float:
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", str(caminho)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0


def transcrever(origem: Path, inicio: float, fim, args, tmp: str):
    wav = Path(tmp) / "audio.wav"
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y"]
    if inicio:
        cmd += ["-ss", str(inicio)]
    if fim:
        cmd += ["-to", str(fim)]
    # -ss/-to antes do -i: busca rápida; tempos ficam relativos ao arquivo
    cmd += ["-i", str(origem), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav)]
    print(f"→ Extraindo áudio de {origem.name}…", flush=True)
    subprocess.run(cmd, check=True)
    print("→ Transcrevendo (Whisper large-v3-turbo no M4)…", flush=True)
    t0 = time.time()
    res = mlx_whisper.transcribe(
        str(wav), path_or_hf_repo=MODELO, language=args.idioma, word_timestamps=True,
        condition_on_previous_text=False, initial_prompt=args.prompt,
        hallucination_silence_threshold=2.0, verbose=False,
    )
    print(f"   pronto em {time.time() - t0:.0f}s", flush=True)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("arquivos", nargs="*", help="um ou mais arquivos, na ordem cronológica")
    ap.add_argument("--lista", help="JSON com trechos [{arquivo, inicio, fim}] (segundos)")
    ap.add_argument("--nome", help="nome do projeto (padrão: nome do primeiro arquivo)")
    ap.add_argument("--inicio", help="começo do trecho, ex. 00:03:20 (só com um arquivo)")
    ap.add_argument("--fim", help="fim do trecho, ex. 00:45:00 (só com um arquivo)")
    ap.add_argument("--idioma", default="pt")
    ap.add_argument("--prompt", default=PROMPT_PADRAO, help="contexto para o Whisper: SÓ nomes e vocabulário")
    args = ap.parse_args()

    if args.lista:
        trechos = json.loads(Path(args.lista).expanduser().read_text())
        jobs = [(Path(t["arquivo"]).expanduser().resolve(), float(t["inicio"]), float(t["fim"])) for t in trechos]
    else:
        if not args.arquivos:
            sys.exit("Informe arquivos ou --lista.")
        if len(args.arquivos) > 1 and (args.inicio or args.fim):
            sys.exit("--inicio/--fim só funcionam com um arquivo.")
        ini0, fim0 = para_segundos(args.inicio) or 0.0, para_segundos(args.fim)
        jobs = [(Path(a).expanduser().resolve(), ini0, fim0) for a in args.arquivos]
    for o, _, _ in jobs:
        if not o.exists():
            sys.exit(f"Arquivo não encontrado: {o}")

    nome = args.nome or jobs[0][0].stem
    pasta = BASE / "projetos" / slug(nome)
    pasta.mkdir(parents=True, exist_ok=True)

    segmentos, arquivos, base = [], [], 0.0
    idioma = args.idioma
    with tempfile.TemporaryDirectory() as tmp:
        for k, (origem, inicio, fim) in enumerate(jobs):
            if len(jobs) > 1:
                print(f"[{k + 1}/{len(jobs)}] {origem.name} {tc(inicio)}", flush=True)
            res = transcrever(origem, inicio, fim, args, tmp)
            idioma = res.get("language", idioma)
            dur = (fim or duracao_arquivo(origem)) - inicio
            # base: soma-se ao tempo dentro do arquivo para dar a posição na sequência
            arquivos.append({"caminho": str(origem), "nome": origem.stem, "duracao": round(dur, 2),
                             "inicio": round(inicio, 3), "base": round(base - inicio, 3)})
            for s in res["segments"]:
                texto = s["text"].strip()
                if eh_alucinacao(texto):
                    continue
                palavras = [{"p": w["word"].strip(), "i": round(w["start"] + inicio, 2),
                             "f": round(w["end"] + inicio, 2), "c": round(w.get("probability", 1.0), 2)}
                            for w in s.get("words", [])]
                conf = sum(w["c"] for w in palavras) / len(palavras) if palavras else 0
                segmentos.append({
                    "id": len(segmentos), "arq": k,
                    "duvidoso": conf < 0.75,  # provável música/ruído interpretado como fala
                    "inicio": round(s["start"] + inicio, 2),  # segundos dentro do arquivo
                    "fim": round(s["end"] + inicio, 2),
                    "texto": texto, "palavras": palavras,
                })
            base += dur

    confs = [w["c"] for s in segmentos for w in s["palavras"]]
    dados = {
        "projeto": nome, "arquivo": str(jobs[0][0]), "arquivos": arquivos,
        "trecho": {"inicio": 0, "fim": None},  # deslocamentos ficam em arquivos[].base
        "duracao": round(base, 2), "idioma": idioma,
        "confianca_media": round(sum(confs) / len(confs), 3) if confs else None,
        "segmentos": segmentos,
    }
    (pasta / "transcricao.json").write_text(json.dumps(dados, ensure_ascii=False, indent=1))

    multi = len(arquivos) > 1
    linhas = [f"# {nome} — {len(segmentos)} segmentos — duração {tc(base)}"]
    if multi:
        linhas += [f"# trecho {k}: {a['nome']} {tc(a['inicio'])} ({a['duracao']:.1f}s)" for k, a in enumerate(arquivos)]
        linhas.append("# minutagem = tempo dentro de cada arquivo")
    for s in segmentos:
        rot = f"{arquivos[s['arq']]['nome']} " if multi else ""
        linhas.append(f"[#{s['id']} {rot}{tc(s['inicio'])}-{tc(s['fim'])}]{' ?' if s['duvidoso'] else ''} {s['texto']}")
    (pasta / "transcricao.txt").write_text("\n".join(linhas) + "\n")

    srt = []
    for n, s in enumerate(segmentos, 1):
        b = arquivos[s["arq"]]["base"]
        srt.append(f"{n}\n{srt_tc(s['inicio'] + b)} --> {srt_tc(s['fim'] + b)}\n{s['texto']}\n")
    (pasta / "transcricao.srt").write_text("\n".join(srt))

    print(f"✓ {len(segmentos)} segmentos · confiança média {dados['confianca_media']}")
    print(f"✓ Projeto: {pasta}")


if __name__ == "__main__":
    main()
