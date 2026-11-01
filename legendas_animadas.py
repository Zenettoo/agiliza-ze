#!/usr/bin/env python3
"""Legendas animadas estilo reels/UGC: palavra por palavra, com a palavra falada em destaque.

Transcreve o vídeo (Whisper local, com tempo de cada palavra), junta as palavras em blocos curtos
(1 a 3 por tela) e anima: o bloco entra com um "pop" e a palavra que está sendo dita muda de cor
e cresce um pouco. Estilos:
  destaque  branco com contorno; palavra falada em cor e maior
  caixa     palavra falada dentro de uma caixa colorida
  karaoke   as palavras já ditas ficam coloridas (enche conforme fala)
  palavra   uma palavra por vez, grande, com pop em cada uma

Gera em projetos/_legendas/<video>/:
  <video>_legendado.mp4  vídeo final com as legendas gravadas (pronto para postar)
  legendas_alfa.mov      só as legendas, com alfa (ProRes 4444), para pôr numa trilha do DaVinci
  palavras.json          as palavras com tempo: corrija o texto aqui e rode de novo (não transcreve outra vez)
  legendas.srt           os blocos como legenda comum
  amostra.jpg            alguns quadros para conferir o estilo

Uso:
  .venv/bin/python legendas_animadas.py --video ugc.mp4 [--estilo destaque|caixa|karaoke|palavra]
      [--cor "#FFFFFF" --cor-ativa "#FFE14D" --cor-caixa "#7C3AED"] [--tamanho 88] [--posicao baixo|meio|alto]
      [--max-palavras 3] [--minusculas] [--fonte arquivo.ttf] [--palavras palavras.json | --srt x.srt]
      [--transcrever-de-novo] [--saida pasta] [--status x.json]
"""
import argparse
import bisect
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
import unicodedata
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = Path(__file__).resolve().parent
FFMPEG = str(BASE / ".venv" / "bin" / "ffmpeg") if (BASE / ".venv" / "bin" / "ffmpeg").exists() else shutil.which("ffmpeg") or "ffmpeg"
MODELO = "mlx-community/whisper-large-v3-turbo"

# Fontes grossas, na ordem de preferência (a primeira que existir)
FONTES = [
    Path.home() / "Library/Fonts/Montserrat-Black.ttf",
    Path.home() / "Library/Fonts/Montserrat-ExtraBold.ttf",
    Path.home() / "Library/Fonts/Inter-VariableFont_opsz,wght.ttf",
    Path("/System/Library/Fonts/Supplemental/Arial Black.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    Path("/usr/share/fonts/opentype/inter/Inter-Black.otf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]

ESTILOS = {
    "destaque": {"cor": "#FFFFFF", "cor_ativa": "#FFE14D", "max_palavras": 3, "escala_ativa": 1.14},
    "caixa": {"cor": "#FFFFFF", "cor_ativa": "#FFFFFF", "cor_caixa": "#7C3AED", "max_palavras": 3, "escala_ativa": 1.06},
    "karaoke": {"cor": "#FFFFFF", "cor_ativa": "#4ADE80", "max_palavras": 4, "escala_ativa": 1.0},
    "palavra": {"cor": "#FFFFFF", "cor_ativa": "#FFFFFF", "max_palavras": 1, "escala_ativa": 1.0, "tamanho": 1.4},
}
POSICOES = {"alto": 0.24, "meio": 0.5, "baixo": 0.70}


class Status:
    def __init__(self, arq):
        self.arq = Path(arq) if arq else None
        self.d = {"nome": "Legendas animadas", "projeto": "_sync", "tipo": "sync", "inicio": time.time(), "pid": os.getpid(),
                  "etapa": "", "msg": "", "pct": 0, "erro": None, "fim": None}

    def __call__(self, etapa, msg, pct, **kw):
        self.d.update(etapa=etapa, msg=msg, pct=pct, **kw)
        if self.arq:
            self.arq.parent.mkdir(parents=True, exist_ok=True)
            self.arq.write_text(json.dumps(self.d, ensure_ascii=False))
        print(f"[{pct:3d}%] {etapa}: {msg}", flush=True)


def slug(txt):
    s = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")[:50] or "video"


def rgb(hexa):
    h = hexa.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def info_video(video):
    """Largura, altura (já como aparece na tela), fps e duração, lidos da saída do ffmpeg."""
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", str(video)], capture_output=True, text=True).stderr
    v = re.search(r"Stream #.*?Video:.*?(\d{2,5})x(\d{2,5})", r)
    if not v:
        raise SystemExit(f"não achei vídeo em {video}")
    w, h = int(v[1]), int(v[2])
    rot = re.search(r"rotation of (-?[\d.]+) degrees", r) or re.search(r"rotate\s*:\s*(-?\d+)", r)
    if rot and round(abs(float(rot[1]))) % 180 == 90:
        w, h = h, w
    fps = re.search(r"Video:.*?([\d.]+) fps", r) or re.search(r"Video:.*?([\d.]+) tbr", r)
    d = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r)
    dur = int(d[1]) * 3600 + int(d[2]) * 60 + float(d[3]) if d else 0.0
    return w, h, float(fps[1]) if fps else 30.0, dur, "Audio:" in r


# ---------- palavras com tempo ----------

def transcrever(video, idioma, prompt):
    import mlx_whisper  # só no Mac (Whisper no chip Apple)
    os.environ.setdefault("HF_HOME", str(BASE / ".modelos"))
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"
        subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", str(video), "-vn", "-ac", "1",
                        "-ar", "16000", "-c:a", "pcm_s16le", str(wav)], check=True)
        res = mlx_whisper.transcribe(str(wav), path_or_hf_repo=MODELO, language=idioma, word_timestamps=True,
                                     condition_on_previous_text=False, initial_prompt=prompt or None,
                                     hallucination_silence_threshold=2.0, verbose=False)
    return [{"p": w["word"].strip(), "i": round(w["start"], 2), "f": round(w["end"], 2)}
            for s in res["segments"] for w in s.get("words", []) if w["word"].strip()]


def de_transcricao(caminho):
    """Palavras de um transcricao.json de projeto (tempos dentro de cada arquivo + base da sequência)."""
    t = json.loads(Path(caminho).read_text())
    bases = [a.get("base", 0) for a in t.get("arquivos") or [{}]]
    return [{"p": w["p"], "i": round(w["i"] + bases[s.get("arq", 0)], 2), "f": round(w["f"] + bases[s.get("arq", 0)], 2)}
            for s in t["segmentos"] for w in s["palavras"] if w["p"].strip()]


def de_srt(caminho):
    """Sem tempo por palavra: reparte cada legenda entre as palavras, proporcional ao tamanho delas."""
    seg = lambda x: int(x[:2]) * 3600 + int(x[3:5]) * 60 + int(x[6:8]) + int(x[9:12]) / 1000  # noqa: E731
    out = []
    for b in Path(caminho).read_text(encoding="utf-8").strip().split("\n\n"):
        l = b.strip().split("\n")
        if len(l) < 3 or " --> " not in l[1]:
            continue
        a, z = (seg(x.strip()) for x in l[1].split(" --> "))
        pals = " ".join(l[2:]).split()
        pesos = [len(p) + 2 for p in pals]
        t = a
        for p, pe in zip(pals, pesos):
            d = (z - a) * pe / sum(pesos)
            out.append({"p": p, "i": round(t, 2), "f": round(t + d, 2)})
            t += d
    return out


# ---------- blocos ----------

def limpar(p, maiusculas):
    t = re.sub(r"[.,;:…\"“”]+", "", p).strip()
    return t.upper() if maiusculas else t


def agrupar(palavras, max_pal, max_car, maiusculas):
    """Blocos curtos: quebra no máximo de palavras/letras, em pausa na fala ou depois de pontuação."""
    grupos, atual = [], []
    for w in palavras:
        txt = limpar(w["p"], maiusculas)
        if not txt:
            continue
        if atual:
            letras = sum(len(x["t"]) + 1 for x in atual) + len(txt)
            if (len(atual) >= max_pal or letras > max_car or w["i"] - atual[-1]["f"] > 0.45
                    or re.search(r"[.,;:!?…]$", atual[-1]["orig"])):
                grupos.append(atual)
                atual = []
        atual.append({"t": txt, "orig": w["p"], "i": float(w["i"]), "f": max(float(w["f"]), float(w["i"]) + 0.05)})
    if atual:
        grupos.append(atual)
    blocos = []
    for k, g in enumerate(grupos):
        ini, fim = g[0]["i"], g[-1]["f"] + 0.12
        if k + 1 < len(grupos):
            prox = grupos[k + 1][0]["i"]
            fim = prox if prox - fim < 0.6 else min(fim, prox)  # emenda se a pausa for curta (sem piscar)
        blocos.append({"ini": ini, "fim": max(fim, ini + 0.25), "palavras": g})
    return blocos


# ---------- desenho ----------

class Fontes:
    def __init__(self, caminho):
        self.caminho, self.cache = caminho, {}

    def __call__(self, tam):
        tam = max(8, int(round(tam)))
        if tam not in self.cache:
            f = ImageFont.truetype(self.caminho, tam)
            try:  # Inter variável: eixos opsz, wght
                f.set_variation_by_axes([32, 900])
            except Exception:  # noqa: BLE001
                pass
            self.cache[tam] = f
        return self.cache[tam]


def escolher_fonte(pedida):
    if pedida:
        if not Path(pedida).expanduser().exists():
            raise SystemExit(f"fonte não encontrada: {pedida}")
        return str(Path(pedida).expanduser())
    for f in FONTES:
        if f.exists():
            return str(f)
    raise SystemExit("nenhuma fonte grossa encontrada; use --fonte")


def ease_back(x):
    """Passa um pouco do ponto e volta: o 'pop'."""
    x = min(1.0, max(0.0, x))
    c = 1.9
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def montar_linhas(palavras, fontes, tam, larg_max):
    """Mede as palavras e quebra em até 2 linhas equilibradas; diminui a letra se ainda não couber."""
    esp = 0.28
    for _ in range(12):
        f = fontes(tam)
        lw = [f.getlength(p["t"]) for p in palavras]
        larg = lambda a, b: sum(lw[a:b]) + esp * tam * (b - a - 1)  # noqa: E731
        n = len(palavras)
        cortes = [(max(larg(0, n), 0), n)]
        cortes += [(max(larg(0, k), larg(k, n)), k) for k in range(1, n)]
        melhor, k = min(cortes[:1] if larg(0, n) <= larg_max else cortes)
        if melhor <= larg_max or tam < 20:
            linhas = [(0, n)] if k == n else [(0, k), (k, n)]
            return tam, lw, [(a, b, larg(a, b)) for a, b in linhas]
        tam *= 0.92
    return tam, lw, [(0, len(palavras), larg(0, len(palavras)))]


class Desenhista:
    def __init__(self, a, w, h, fps):
        est = ESTILOS[a.estilo]
        self.estilo, self.w, self.fps = a.estilo, w, fps
        self.cor = rgb(a.cor or est["cor"])
        self.cor_ativa = rgb(a.cor_ativa or est["cor_ativa"])
        self.cor_caixa = rgb(a.cor_caixa or est.get("cor_caixa", "#7C3AED"))
        self.escala_ativa = est["escala_ativa"]
        self.tam = a.tamanho * w / 1080 * est.get("tamanho", 1.0)
        self.fontes = Fontes(escolher_fonte(a.fonte))
        self.alt = int(self.tam * 3.9) // 2 * 2  # faixa com espaço para 2 linhas + crescimento + sombra
        cy = h * POSICOES[a.posicao]
        self.y = int(min(max(0, cy - self.alt / 2), h - self.alt)) // 2 * 2
        self.layouts = {}

    def layout(self, k, bloco):
        if k not in self.layouts:
            self.layouts[k] = montar_linhas(bloco["palavras"], self.fontes, self.tam, self.w * 0.86)
        return self.layouts[k]

    def quadro(self, k, bloco, ativa, tb, tp):
        """Desenha a faixa RGBA do bloco k: ativa = índice da palavra falada, tb/tp = tempo desde o início do bloco/palavra."""
        tam, lw, linhas = self.layout(k, bloco)
        sg = 0.55 + 0.45 * ease_back(tb / 0.2)  # pop de entrada do bloco
        op = min(1.0, tb / 0.07)
        cx, cy = self.w / 2, self.alt / 2
        alt_linha = tam * 1.12
        img = Image.new("RGBA", (self.w, self.alt), (0, 0, 0, 0))
        sombra = Image.new("L", (self.w, self.alt), 0)
        dr, ds = ImageDraw.Draw(img), ImageDraw.Draw(sombra)
        caixa_pad = 0.16 if self.estilo == "caixa" else 0.0
        for li, (a, b, _) in enumerate(linhas):
            y0 = cy + (li - (len(linhas) - 1) / 2) * alt_linha
            # a palavra falada cresce e as vizinhas abrem espaço para ela
            esc = [1 + (self.escala_ativa - 1) * ease_back(tp / 0.14) if j == ativa else 1.0 for j in range(a, b)]
            larguras = [lw[j] * esc[j - a] + (2 * caixa_pad * tam if j == ativa else 0) for j in range(a, b)]
            x = cx - (sum(larguras) + 0.28 * tam * (b - a - 1)) / 2
            for j in range(a, b):
                xm = x + larguras[j - a] / 2
                x += larguras[j - a] + 0.28 * tam
                e_ativa = j == ativa
                s = sg * esc[j - a]
                f = self.fontes(tam * s)
                px, py = cx + (xm - cx) * sg, cy + (y0 - cy) * sg
                if self.estilo == "karaoke":
                    cor = self.cor_ativa if j <= ativa else self.cor
                else:
                    cor = self.cor_ativa if e_ativa else self.cor
                contorno = max(2, round(f.size * 0.09))
                if self.estilo == "caixa" and e_ativa:
                    pad = f.size * caixa_pad
                    x0, y0b, x1, y1 = dr.textbbox((px, py), bloco["palavras"][j]["t"], font=f, anchor="mm")
                    caixa = (x0 - pad, y0b - pad * 0.8, x1 + pad, y1 + pad * 0.8)
                    ds.rounded_rectangle(caixa, radius=f.size * 0.2, fill=200)
                    dr.rounded_rectangle(caixa, radius=f.size * 0.2, fill=self.cor_caixa + (255,))
                    contorno = 0
                ds.text((px, py + f.size * 0.06), bloco["palavras"][j]["t"], font=f, anchor="mm", fill=255,
                        stroke_width=contorno, stroke_fill=255)
                dr.text((px, py), bloco["palavras"][j]["t"], font=f, anchor="mm", fill=cor + (255,),
                        stroke_width=contorno, stroke_fill=(0, 0, 0, 255))
        sombra = sombra.filter(ImageFilter.GaussianBlur(tam * 0.09))
        fundo = Image.new("RGBA", img.size, (0, 0, 0, 0))
        fundo.putalpha(sombra.point(lambda v: int(v * 0.55)))
        fundo.alpha_composite(img)
        if op < 1:
            al = np.asarray(fundo).copy()
            al[..., 3] = (al[..., 3] * op).astype(np.uint8)
            return al.tobytes()
        return fundo.tobytes()


def estado(blocos, inicios, t, fps):
    """Qual bloco está na tela no tempo t, qual palavra está sendo dita, e há quanto tempo (em quadros)."""
    k = bisect.bisect_right(inicios, t) - 1
    if k < 0 or t >= blocos[k]["fim"]:
        return None
    b = blocos[k]
    ativa = 0
    for j, p in enumerate(b["palavras"]):
        if p["i"] <= t + 0.5 / fps:
            ativa = j
    q = lambda s, lim: min(int((t - s) * fps), int(lim * fps) + 1)  # noqa: E731  (anima só no começo)
    return k, ativa, q(b["ini"], 0.25), q(b["palavras"][ativa]["i"], 0.2)


def gravar_srt(blocos, caminho):
    def tc(s):
        ms = int(round(s * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    caminho.write_text("\n".join(f"{n}\n{tc(b['ini'])} --> {tc(b['fim'])}\n{' '.join(p['t'] for p in b['palavras'])}\n"
                                 for n, b in enumerate(blocos, 1)), encoding="utf-8")


def amostra(video, saida, blocos, n=6):
    """Folha com alguns quadros do vídeo legendado, para conferir o estilo sem abrir o vídeo."""
    if not blocos:
        return
    ts = [b["palavras"][len(b["palavras"]) // 2]["i"] + 0.12 for b in blocos[:: max(1, len(blocos) // n)][:n]]
    quadros = []
    for t in ts:
        r = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(video),
                            "-frames:v", "1", "-vf", "scale=360:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
                           capture_output=True)
        if r.stdout:
            from io import BytesIO
            quadros.append(Image.open(BytesIO(r.stdout)).convert("RGB"))
    if quadros:
        folha = Image.new("RGB", (sum(q.width for q in quadros), max(q.height for q in quadros)))
        x = 0
        for q in quadros:
            folha.paste(q, (x, 0))
            x += q.width
        folha.save(saida / "amostra.jpg", quality=85)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--estilo", choices=list(ESTILOS), default="destaque")
    ap.add_argument("--cor", help="cor do texto (#RRGGBB)")
    ap.add_argument("--cor-ativa", help="cor da palavra falada")
    ap.add_argument("--cor-caixa", help="cor da caixa (estilo caixa)")
    ap.add_argument("--tamanho", type=float, default=88, help="tamanho da letra num vídeo de 1080 de largura")
    ap.add_argument("--posicao", choices=list(POSICOES), default="baixo")
    ap.add_argument("--max-palavras", type=int, help="palavras por tela (padrão do estilo)")
    ap.add_argument("--minusculas", action="store_true", help="não passar para MAIÚSCULAS")
    ap.add_argument("--fonte", help="arquivo .ttf/.otf (padrão: Montserrat Black, Inter, Arial Black)")
    ap.add_argument("--palavras", help="palavras.json já corrigido (pula a transcrição)")
    ap.add_argument("--srt", help="legenda .srt no lugar da transcrição (tempo por palavra estimado)")
    ap.add_argument("--transcricao", help="transcricao.json de um projeto (com tempo por palavra)")
    ap.add_argument("--transcrever-de-novo", action="store_true", help="ignora o palavras.json que já estiver na pasta")
    ap.add_argument("--idioma", default="pt")
    ap.add_argument("--prompt", default="", help="nomes e vocabulário para o Whisper (marca, produtos)")
    ap.add_argument("--saida", help="pasta de saída (padrão: projetos/_legendas/<video>)")
    ap.add_argument("--sem-alfa", action="store_true", help="não gerar o .mov com alfa")
    ap.add_argument("--status")
    a = ap.parse_args()
    st = Status(a.status)
    try:
        rodar(a, st)
    except BaseException as e:  # noqa: BLE001
        st("Erro", str(e) or e.__class__.__name__, st.d["pct"], erro=True, fim=time.time())
        raise


def rodar(a, st):
    video = Path(a.video).expanduser().resolve()
    if not video.exists():
        raise SystemExit(f"vídeo não encontrado: {video}")
    saida = Path(a.saida).expanduser() if a.saida else BASE / "projetos" / "_legendas" / slug(video.stem)
    saida.mkdir(parents=True, exist_ok=True)
    w, h, fps, dur, tem_audio = info_video(video)
    arq_palavras = saida / "palavras.json"

    st("Palavras", "lendo a fala", 2)
    if a.palavras:
        palavras = json.loads(Path(a.palavras).expanduser().read_text())
    elif a.srt:
        palavras = de_srt(a.srt)
    elif a.transcricao:
        palavras = de_transcricao(a.transcricao)
    elif arq_palavras.exists() and not a.transcrever_de_novo:
        palavras = json.loads(arq_palavras.read_text())
        st("Palavras", "usando o palavras.json já corrigido", 5)
    else:
        if not tem_audio:
            raise SystemExit("o vídeo não tem áudio para transcrever")
        st("Transcrição", "Whisper local, palavra por palavra", 5)
        palavras = transcrever(video, a.idioma, a.prompt)
    if not palavras:
        raise SystemExit("nenhuma fala encontrada")
    arq_palavras.write_text(json.dumps(palavras, ensure_ascii=False, indent=0), encoding="utf-8")

    est = ESTILOS[a.estilo]
    max_pal = a.max_palavras or est["max_palavras"]
    blocos = agrupar(palavras, max_pal, 18 if max_pal > 1 else 40, not a.minusculas)
    gravar_srt(blocos, saida / "legendas.srt")
    des = Desenhista(a, w, h, fps)
    inicios = [b["ini"] for b in blocos]

    final = saida / f"{slug(video.stem)}_legendado.mp4"
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
           "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{des.alt}", "-r", f"{fps}", "-i", "-"]
    grafo = f"[1:v]format=rgba,split[a][b];[0:v][a]overlay=0:{des.y}:shortest=1,format=yuv420p[v]"
    if not a.sem_alfa:
        grafo += f";[b]pad={w}:{h}:0:{des.y}:color=black@0[al]"
    else:
        grafo = grafo.replace(",split[a][b]", "[a]")
    cmd += ["-filter_complex", grafo, "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final)]
    if not a.sem_alfa:
        cmd += ["-map", "[al]", "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
                "-alpha_bits", "16", "-vendor", "apl0", str(saida / "legendas_alfa.mov")]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    n = int(math.ceil(dur * fps)) + 1
    vazio = bytes(w * des.alt * 4)
    cache = {}
    st("Animando", f"{len(blocos)} telas de legenda · estilo {a.estilo}", 10)
    try:
        for q in range(n):
            e = estado(blocos, inicios, q / fps, fps)
            if e is None:
                fr = vazio
            else:
                if e not in cache:
                    if len(cache) > 400:
                        cache.clear()
                    k, ativa, qb, qp = e
                    cache[e] = des.quadro(k, blocos[k], ativa, qb / fps, qp / fps)
                fr = cache[e]
            enc.stdin.write(fr)
            if q % max(1, n // 40) == 0:
                st("Animando", f"quadro {q}/{n}", 10 + int(85 * q / n))
        enc.stdin.close()
    except BrokenPipeError:
        pass
    if enc.wait() != 0:
        raise SystemExit("o ffmpeg falhou ao gravar o vídeo")
    amostra(final, saida, blocos)
    projetos = (BASE / "projetos").resolve()
    url = "/" + final.resolve().relative_to(projetos).as_posix() if projetos in final.resolve().parents else ""
    st("Concluído", f"{final.name} em {saida}", 100, fim=time.time(), pasta=str(saida), arquivo=str(final), url=url)


if __name__ == "__main__":
    main()
