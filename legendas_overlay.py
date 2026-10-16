#!/usr/bin/env python3
"""Legenda dinâmica em clipes com alfa: um .mov (ProRes 4444) por legenda do SRT, para pôr numa trilha do DaVinci.

Cada legenda vira um clipe do tamanho da tela (mesmo enquadramento da timeline), uma linha, centralizada:
entra com um "pop" curto (fade + cresce de 94% a 100% + sobe um pouco) e sai com fade de 2 quadros.
Gera também leg_NN_track.json (mesmo formato dos ganchos: colocar_ganchos.py --padrao "leg_*_track.json"),
e, com --video, uma prévia composta sobre o vídeo e uma folha de quadros para conferir.

Uso:
  .venv/bin/python legendas_overlay.py --srt projetos/X/legenda.srt --saida projetos/X/legendas \
      [--video projetos/X/ref.mp4] [--largura 1080 --altura 1920 --fps 24] [--tamanho 60] [--y 1460]
"""
import argparse
import json
import re
import subprocess
import unicodedata
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = Path(__file__).resolve().parent
FFMPEG = str(BASE / ".venv" / "bin" / "ffmpeg")
FONTE = str(Path.home() / "Library/Fonts/Inter-VariableFont_opsz,wght.ttf")


def ler_srt(caminho):
    blocos = Path(caminho).read_text(encoding="utf-8").strip().split("\n\n")
    seg = lambda t: int(t[:2]) * 3600 + int(t[3:5]) * 60 + int(t[6:8]) + int(t[9:12]) / 1000
    out = []
    for b in blocos:
        l = b.strip().split("\n")
        a, z = l[1].split(" --> ")
        out.append((seg(a.strip()), seg(z.strip()), " ".join(l[2:]).strip()))
    return out


def slug(txt):
    s = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:32]


def fonte(tamanho, peso):
    f = ImageFont.truetype(FONTE, tamanho)
    try:
        f.set_variation_by_axes([min(32, max(14, tamanho / 2)), peso])  # eixos do Inter: opsz, wght
    except Exception:
        pass
    return f


def camada_texto(txt, f, larg, sombra=0.45):
    """RGBA premultiplicado (float) só do tamanho do texto + margem: texto branco com sombra suave."""
    b = f.getbbox(txt)
    tw, th = b[2] - b[0], b[3] - b[1]
    m = int(f.size * 0.6)
    W, H = tw + 2 * m, th + 2 * m
    if W > larg:
        raise SystemExit(f"legenda larga demais para a tela: '{txt}'")
    letra = Image.new("L", (W, H), 0)
    ImageDraw.Draw(letra).text((m - b[0], m - b[1]), txt, font=f, fill=255)
    a_txt = np.asarray(letra, np.float32) / 255
    a_sh = np.asarray(letra.filter(ImageFilter.GaussianBlur(f.size * 0.14)), np.float32) / 255
    a_sh = np.roll(a_sh, int(f.size * 0.06), axis=0) * sombra
    alfa = a_txt + a_sh * (1 - a_txt)
    cor = a_txt  # premultiplicado: branco nas letras, preto na sombra
    return np.dstack([cor, cor, cor, alfa])


def easeout(x):
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def quadros_legenda(camada, n, w, h, cy, fps):
    """Gera os n quadros RGBA (uint8, alfa reto) da legenda centralizada em (w/2, cy)."""
    ch, cw = camada.shape[:2]
    entra, sai = max(3, round(0.2 * fps)), 2
    sobe = camada.shape[0] * 0.10
    for k in range(n):
        t = easeout((k + 1) / entra)
        op = t * min(1.0, (n - k) / (sai + 1))
        esc = 0.94 + 0.06 * t
        dy = sobe * (1 - t)
        M = np.float32([[esc, 0, w / 2 - esc * cw / 2], [0, esc, cy + dy - esc * ch / 2]])
        q = cv2.warpAffine(camada, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0)) * op
        a = q[..., 3:4]
        cor = np.where(a > 1e-4, q[..., :3] / np.maximum(a, 1e-4), 0)
        yield (np.clip(np.dstack([cor, a]), 0, 1) * 255 + 0.5).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--srt", required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--video", help="vídeo da timeline (mesmo tamanho/fps), para a prévia")
    ap.add_argument("--largura", type=int, default=1080)
    ap.add_argument("--altura", type=int, default=1920)
    ap.add_argument("--fps", type=float, default=24)
    ap.add_argument("--tamanho", type=int, default=60)
    ap.add_argument("--peso", type=int, default=600)
    ap.add_argument("--y", type=int, default=1460, help="centro vertical da linha (px)")
    a = ap.parse_args()
    w, h, fps = a.largura, a.altura, a.fps
    saida = Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)
    f = fonte(a.tamanho, a.peso)
    legs = ler_srt(a.srt)
    faixa = []  # (quadro inicial, n quadros, arquivo) para a prévia
    for i, (ini, fim, txt) in enumerate(legs, 1):
        q0, q1 = round(ini * fps), round(fim * fps)
        n = max(1, q1 - q0)
        nome = f"leg_{i:02d}_{slug(txt)}.mov"
        camada = camada_texto(txt, f, w)
        p = subprocess.Popen([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba",
                              "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-c:v", "prores_ks", "-profile:v", "4444",
                              "-pix_fmt", "yuva444p10le", "-alpha_bits", "16", "-vendor", "apl0", str(saida / nome)],
                             stdin=subprocess.PIPE)
        for fr in quadros_legenda(camada, n, w, h, a.y, fps):
            p.stdin.write(fr.tobytes())
        p.stdin.close()
        p.wait()
        (saida / f"leg_{i:02d}_track.json").write_text(json.dumps(
            {"id": i, "texto": txt, "quadros": n, "inicio_quadro": q0, "inicio_s": round(q0 / fps, 3),
             "fim_s": round(q1 / fps, 3), "arquivos": {"alfa": nome}}, ensure_ascii=False, indent=1), encoding="utf-8")
        faixa.append((q0, n, camada))
    print(f"{len(legs)} legendas em {saida}")
    if a.video:
        previa(a.video, faixa, saida, w, h, a.y, fps)


def previa(video, faixa, saida, w, h, cy, fps):
    """Prévia composta (metade da resolução) e folha com um quadro do meio de cada legenda."""
    pw, ph = w // 2, h // 2
    dec = subprocess.Popen([FFMPEG, "-hide_banner", "-loglevel", "error", "-i", str(video), "-f", "rawvideo",
                            "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
                            "-s", f"{pw}x{ph}", "-r", str(fps), "-i", "-", "-i", str(video), "-map", "0:v", "-map", "1:a?",
                            "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                            str(saida / "previa_legendas.mp4")], stdin=subprocess.PIPE)
    por_quadro = {q0 + k: (q0, n, camada) for q0, n, camada in faixa for k in range(n)}
    meio = {q0 + n // 2 for q0, n, _ in faixa}
    folha, f = [], 0
    cache = {}
    while True:
        raw = dec.stdout.read(w * h * 3)
        if len(raw) < w * h * 3:
            break
        img = np.frombuffer(raw, np.uint8).reshape(h, w, 3).astype(np.float32) / 255
        if f in por_quadro:
            q0, n, camada = por_quadro[f]
            if q0 not in cache:
                cache.clear()
                cache[q0] = list(quadros_legenda(camada, n, w, h, cy, fps))
            fr = cache[q0][f - q0].astype(np.float32) / 255
            al = fr[..., 3:4]
            img = img * (1 - al) + fr[..., 2::-1][..., :3] * al
        pq = cv2.resize((img * 255).astype(np.uint8), (pw, ph), interpolation=cv2.INTER_AREA)
        enc.stdin.write(pq.tobytes())
        if f in meio:
            folha.append(cv2.resize(pq, (270, 480), interpolation=cv2.INTER_AREA))
        f += 1
    enc.stdin.close()
    enc.wait()
    dec.wait()
    linhas = [np.hstack(folha[i:i + 10] + [np.zeros_like(folha[0])] * (10 - len(folha[i:i + 10])))
              for i in range(0, len(folha), 10)]
    cv2.imwrite(str(saida / "folha_legendas.jpg"), np.vstack(linhas), [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"prévia: {saida / 'previa_legendas.mp4'} | folha: {saida / 'folha_legendas.jpg'}")


if __name__ == "__main__":
    main()
