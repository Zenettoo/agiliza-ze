#!/usr/bin/env python3
"""Ganchos 3D: frases de destaque presas numa superfície do vídeo (parede, vidro, piso), estilo Reels imobiliário.

O texto é desenhado num plano e acompanha a câmera por rastreamento planar (pontos de canto + homografia),
como o Planar Tracker / Camera Tracker: a frase parece pintada na parede e se move com ela.

Trabalha sobre uma cópia renderizada da timeline (mesmo tamanho e fps da timeline), então o resultado bate
quadro a quadro com o que está no DaVinci. Gera, por gancho:
  gancho_NN.mov          ProRes 4444 com alfa, para pôr numa trilha acima do vídeo
  gancho_NN_preview.mp4  o gancho já composto sobre o vídeo (para conferir)
  gancho_NN_folha.jpg    6 quadros do preview lado a lado
  gancho_NN_track.json   qualidade do rastreamento por quadro

Uso:
  ganchos3d.py planos  --config ganchos.json                 # folhas de quadros de cada plano (para escolher onde pôr)
  ganchos3d.py grade   --config ganchos.json --t 12.5        # um quadro com grade de pixels (para marcar o quad)
  ganchos3d.py render  --config ganchos.json --id 3          # renderiza um gancho

ganchos.json:
  {"video": "02_referencia.mp4", "fps": 24, "saida": "render",
   "fonte": "/System/Library/Fonts/Avenir Next Condensed.ttc", "fonte_indice": 9,
   "planos": [[ini, fim], ...],                               # cortes da timeline em segundos
   "ganchos": [{"id": 1, "linhas": ["LIBERDADE", "PARA A FAMÍLIA"], "inicio": 1.0, "fim": 4.5,
                "ancora": 2.0, "quad": [[x,y] TL, TR, BR, BL], "regiao": [[x,y], ...] (opcional),
                "alinhar": "esquerda|centro|direita", "opacidade": 0.95}]}
Caminhos relativos são resolvidos a partir da pasta do ganchos.json. Tempos em segundos da timeline.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).resolve().parent
FFMPEG = str(BASE / ".venv" / "bin" / "ffmpeg")


# ---------------------------------------------------------------- vídeo

def ler_quadros(video, f0, n, w, h, fps):
    """Lê n quadros BGR a partir do quadro f0 (exato: ffmpeg decodifica do keyframe e descarta)."""
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-ss", f"{f0 / fps:.6f}", "-i", str(video),
           "-frames:v", str(n), "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    k = len(raw) // (w * h * 3)
    return np.frombuffer(raw[:k * w * h * 3], np.uint8).reshape(k, h, w, 3)


def info_video(video):
    c = cv2.VideoCapture(str(video))
    w, h, n = int(c.get(3)), int(c.get(4)), int(c.get(cv2.CAP_PROP_FRAME_COUNT))
    c.release()
    return w, h, n


# ---------------------------------------------------------------- rastreamento planar

def rastrear(cinzas, a, mascara):
    """Homografias H[t] (coordenadas do quadro-âncora a -> quadro t) para todos os quadros.

    Pontos de canto dentro da máscara são seguidos com Lucas-Kanade (com checagem ida-e-volta);
    cada quadro estima H direto da âncora (não acumula erro quadro a quadro). Repõe pontos quando
    poucos sobram. Devolve também, por quadro, quantos pontos sustentam a homografia."""
    n = len(cinzas)
    H = [None] * n
    apoio = [0] * n
    H[a] = np.eye(3)
    lk = dict(winSize=(25, 25), maxLevel=4, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
    feat = dict(maxCorners=600, qualityLevel=0.005, minDistance=8, blockSize=7)
    p0 = cv2.goodFeaturesToTrack(cinzas[a], mask=mascara, **feat)
    if p0 is None or len(p0) < 8:
        raise RuntimeError("Poucos pontos na superfície escolhida para rastrear (região lisa demais).")
    apoio[a] = len(p0)
    hm, wm = mascara.shape
    for passo in (1, -1):
        anc = p0.reshape(-1, 2).copy()
        cur = anc.copy()
        Hc = np.eye(3)
        t = a
        while 0 <= t + passo < n:
            u = t + passo
            nxt, st, _ = cv2.calcOpticalFlowPyrLK(cinzas[t], cinzas[u], cur.reshape(-1, 1, 2).astype(np.float32), None, **lk)
            back, st2, _ = cv2.calcOpticalFlowPyrLK(cinzas[u], cinzas[t], nxt, None, **lk)
            nxt, back = nxt.reshape(-1, 2), back.reshape(-1, 2)
            ok = (st.ravel() == 1) & (st2.ravel() == 1) & (np.linalg.norm(back - cur, axis=1) < 1.0)
            anc, cur = anc[ok], nxt[ok]
            if len(anc) >= 8:
                Hn, inl = cv2.findHomography(anc, cur, cv2.RANSAC, 2.5)
                if Hn is not None and inl is not None and inl.sum() >= 8:
                    inl = inl.ravel().astype(bool)
                    anc, cur, Hc = anc[inl], cur[inl], Hn
            H[u] = Hc
            apoio[u] = len(anc)
            # repõe pontos dentro da região (projetada no quadro atual)
            if len(anc) < 150:
                mproj = cv2.warpPerspective(mascara, Hc, (wm, hm), flags=cv2.INTER_NEAREST)
                for q in cur:
                    cv2.circle(mproj, (int(q[0]), int(q[1])), 8, 0, -1)
                novos = cv2.goodFeaturesToTrack(cinzas[u], mask=mproj, **feat)
                if novos is not None:
                    novos = novos.reshape(-1, 2)
                    na = cv2.perspectiveTransform(novos.reshape(-1, 1, 2), np.linalg.inv(Hc)).reshape(-1, 2)
                    anc = np.vstack([anc, na])
                    cur = np.vstack([cur, novos])
            t = u
    return H, apoio


def suavizar_cantos(cantos, sigma):
    """Suaviza as trajetórias dos 4 cantos (n,4,2) no tempo, sem atraso (filtro centrado)."""
    if sigma <= 0 or len(cantos) < 3:
        return cantos
    r = int(3 * sigma + 0.5)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    pad = np.concatenate([np.repeat(cantos[:1], r, 0), cantos, np.repeat(cantos[-1:], r, 0)])
    out = np.empty_like(cantos)
    for i in range(len(cantos)):
        out[i] = np.tensordot(k, pad[i:i + 2 * r + 1], axes=(0, 0))
    return out


# ---------------------------------------------------------------- texto

def _caixa(f, texto, esp):
    """Caixa (x0, y0, x1, y1) do texto com espaçamento extra 'esp' (px) entre as letras."""
    if not esp:
        return f.getbbox(texto)
    b = f.getbbox(texto)
    return (b[0], b[1], b[2] + esp * max(0, len(texto) - 1), b[3])


def _escrever(draw, x, y, texto, f, esp):
    if not esp:
        draw.text((x, y), texto, font=f, fill=255)
        return
    for ch_ in texto:
        draw.text((x, y), ch_, font=f, fill=255)
        x += f.getlength(ch_) + esp


def camadas_texto(linhas, fonte, indice, cw, ch, alinhar, tracking=0.0, entre=0.92):
    """Uma imagem de alfa por linha, todas do tamanho da tela do texto (cw x ch).
    tracking: espaço extra entre letras, em fração do tamanho da fonte. entre: entrelinha."""
    def medir(tam):
        f = ImageFont.truetype(fonte, tam, index=indice)
        esp = tam * tracking
        caixas = [_caixa(f, l, esp) for l in linhas]
        larg = max(b[2] - b[0] for b in caixas)
        alt = tam * entre * (len(linhas) - 1) + (caixas[-1][3] - caixas[-1][1]) + tam * 0.1
        return f, esp, caixas, larg, alt
    tam = 400
    _, _, _, larg, alt = medir(tam)
    tam = int(tam * min(cw * 0.98 / larg, ch * 0.98 / alt))
    f, esp, caixas, larg, alt = medir(tam)
    y0 = (ch - alt) / 2
    camadas = []
    for i, (l, b) in enumerate(zip(linhas, caixas)):
        lw = b[2] - b[0]
        x = {"esquerda": 0, "centro": (cw - lw) / 2, "direita": cw - lw}[alinhar] - b[0]
        y = y0 - caixas[0][1] + i * tam * entre  # mesma distância entre as linhas de base
        img = Image.new("L", (cw, ch), 0)
        _escrever(ImageDraw.Draw(img), x, y, l, f, esp)
        a = np.asarray(img, np.float32) / 255.0
        x0 = max(0, int(x + b[0]) - 4)
        x1 = min(cw, int(x + b[2]) + 4)
        camadas.append((a, x0, x1))
    return camadas


def suave(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def quadro_texto(camadas, f, nf, fps, opacidade, animacao="varredura"):
    """Alfa do bloco de texto no quadro f (0..nf-1). Some no fim.
    "varredura": cada linha entra com uma varredura da esquerda, escalonada.
    "fade": cada linha aparece com fade curto subindo um pouco (minimalista)."""
    if animacao == "fade":
        dur_in, escal, dur_out = int(0.40 * fps), int(0.10 * fps), int(0.25 * fps)
        alfa = np.zeros_like(camadas[0][0])
        sai = suave((nf - 1 - f) / max(1, dur_out))
        sobe = int(camadas[0][0].shape[0] * 0.06)  # quanto a linha sobe ao entrar (px da tela do texto)
        for i, (a, _, _) in enumerate(camadas):
            p = suave((f - i * escal) / max(1, dur_in))
            if p <= 0:
                continue
            dy = int(round((1 - p) * sobe))  # começa um pouco abaixo e sobe até o lugar
            a2 = np.roll(a, dy, axis=0) if dy else a
            alfa = np.maximum(alfa, a2 * p)
        return alfa * sai * opacidade
    dur_in, escal, dur_out = int(0.42 * fps), int(0.16 * fps), int(0.30 * fps)
    alfa = np.zeros_like(camadas[0][0])
    sai = suave((nf - 1 - f) / max(1, dur_out))
    for i, (a, x0, x1) in enumerate(camadas):
        p = suave((f - i * escal) / max(1, dur_in))
        if p <= 0:
            continue
        borda = 0.18 * (x1 - x0)
        frente = x0 + p * (x1 - x0 + borda)
        xs = np.arange(a.shape[1], dtype=np.float32)
        mascara = np.clip((frente - xs) / borda, 0, 1)[None, :]
        alfa = np.maximum(alfa, a * mascara * p ** 0.5)
    return alfa * sai * opacidade


# ---------------------------------------------------------------- comandos

def carregar(cfg_path):
    cfg_path = Path(cfg_path).resolve()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    raiz = cfg_path.parent
    cfg["_video"] = (raiz / cfg["video"]).resolve()
    cfg["_saida"] = (raiz / cfg.get("saida", "render")).resolve()
    cfg["_saida"].mkdir(parents=True, exist_ok=True)
    return cfg


def cmd_planos(cfg):
    """Folha com 4 quadros de cada plano da timeline, com o tempo de cada quadro."""
    fps = cfg.get("fps", 24)
    w, h, _ = info_video(cfg["_video"])
    pasta = cfg["_saida"] / "planos"
    pasta.mkdir(exist_ok=True)
    for i, (a, b) in enumerate(cfg["planos"], 1):
        tempos = np.linspace(a + 0.05, b - 0.05, 4)
        fotos = []
        for t in tempos:
            q = ler_quadros(cfg["_video"], int(round(t * fps)), 1, w, h, fps)[0]
            q = cv2.resize(q, (360, 640), interpolation=cv2.INTER_AREA)
            cv2.rectangle(q, (0, 0), (150, 34), (0, 0, 0), -1)
            cv2.putText(q, f"{t:.2f}s", (6, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            fotos.append(q)
        cv2.imwrite(str(pasta / f"plano_{i:02d}_{a:.2f}-{b:.2f}.jpg"), np.hstack(fotos), [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"{len(cfg['planos'])} folhas em {pasta}")


def cmd_grade(cfg, t):
    """Quadro inteiro (1080x1920) com grade a cada 100 px e coordenadas, para marcar o quad."""
    fps = cfg.get("fps", 24)
    w, h, _ = info_video(cfg["_video"])
    q = ler_quadros(cfg["_video"], int(round(t * fps)), 1, w, h, fps)[0].copy()
    for x in range(0, w, 100):
        cv2.line(q, (x, 0), (x, h), (0, 255, 255), 1)
        cv2.putText(q, str(x), (x + 3, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    for y in range(0, h, 100):
        cv2.line(q, (0, y), (w, y), (0, 255, 255), 1)
        cv2.putText(q, str(y), (3, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    out = cfg["_saida"] / f"grade_{t:.2f}.jpg"
    cv2.imwrite(str(out), q, [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(out)


def cmd_render(cfg, gid):
    fps = cfg.get("fps", 24)
    g = next(x for x in cfg["ganchos"] if x["id"] == gid)
    w, h, ntot = info_video(cfg["_video"])
    f0, f1 = int(round(g["inicio"] * fps)), int(round(g["fim"] * fps))
    fa = int(round(g.get("ancora", g["inicio"]) * fps))
    if not (f0 <= fa < f1):
        raise SystemExit("A âncora precisa estar entre início e fim do gancho.")
    # o gancho não pode atravessar um corte: o rastreamento vale só dentro do plano
    for a, b in cfg.get("planos", []):
        if a - 1e-3 <= g["inicio"] < b and g["fim"] > b + 1.0 / fps:
            raise SystemExit(f"O gancho {gid} atravessa o corte em {b:.2f}s; termine-o até lá.")
    nf = f1 - f0
    quadros = ler_quadros(cfg["_video"], f0, nf, w, h, fps)
    nf = len(quadros)
    cinzas = [cv2.cvtColor(q, cv2.COLOR_BGR2GRAY) for q in quadros]
    quad = np.array(g["quad"], np.float32)
    regiao = np.array(g.get("regiao") or [], np.float32)
    mascara = np.zeros((h, w), np.uint8)
    if len(regiao) >= 3:
        cv2.fillPoly(mascara, [regiao.astype(np.int32)], 255)
    else:
        c = quad.mean(0)
        cv2.fillPoly(mascara, [((quad - c) * 1.7 + c).astype(np.int32)], 255)
    H, apoio = rastrear(cinzas, fa - f0, mascara)
    # pontas com rastreamento fraco (poucos pontos) saem do gancho, em vez de deixar o texto derivar
    # fica só o trecho contínuo de rastreamento firme em volta da âncora
    MIN = 12
    ia = fa - f0
    fracos = [k for k, s in enumerate(apoio) if s < MIN]
    a0 = max([k + 1 for k in fracos if k < ia], default=0)
    a1 = min([k for k in fracos if k > ia], default=nf)
    if (a0, a1) != (0, nf):
        print(f"aviso: rastreamento fraco nas pontas; gancho encurtado para {(f0 + a0) / fps:.2f}-{(f0 + a1) / fps:.2f}s")
    quadros, cinzas, H, apoio = quadros[a0:a1], cinzas[a0:a1], H[a0:a1], apoio[a0:a1]
    f0, nf = f0 + a0, a1 - a0
    cantos = np.array([cv2.perspectiveTransform(quad.reshape(-1, 1, 2), Hk).reshape(4, 2) for Hk in H])
    cantos = suavizar_cantos(cantos, g.get("suavizar", 1.2))

    # tela do texto no tamanho aproximado do quad na tela (x1.5 para nitidez)
    larg = (np.linalg.norm(quad[1] - quad[0]) + np.linalg.norm(quad[2] - quad[3])) / 2
    alt = (np.linalg.norm(quad[3] - quad[0]) + np.linalg.norm(quad[2] - quad[1])) / 2
    S = 1.5
    cw, ch = int(larg * S), int(alt * S)
    fonte = g.get("fonte", cfg.get("fonte", "/System/Library/Fonts/Avenir Next Condensed.ttc"))
    indice = g.get("fonte_indice", cfg.get("fonte_indice", 9))
    camadas = camadas_texto(g["linhas"], fonte, indice, cw, ch, g.get("alinhar", "esquerda"),
                            g.get("tracking", cfg.get("tracking", 0.0)), g.get("entrelinha", cfg.get("entrelinha", 0.92)))
    animacao = g.get("animacao", cfg.get("animacao", "varredura"))
    ret = np.array([[0, 0], [cw, 0], [cw, ch], [0, ch]], np.float32)
    # margem: menor distância entre as letras e a borda da tela, ao longo do gancho (enquadramento)
    tinta = np.max([a for a, _, _ in camadas], axis=0)
    ys, xs = np.nonzero(tinta > 0.05)
    caixa_t = np.array([[xs.min(), ys.min()], [xs.max(), ys.min()], [xs.max(), ys.max()], [xs.min(), ys.max()]], np.float32)
    margens = []
    for k in range(nf):
        Hk = cv2.getPerspectiveTransform(ret, cantos[k].astype(np.float32))
        p = cv2.perspectiveTransform(caixa_t.reshape(-1, 1, 2), Hk).reshape(-1, 2)
        margens.append(min(p[:, 0].min(), w - p[:, 0].max(), p[:, 1].min(), h - p[:, 1].max()))
    margem_min = float(min(margens))
    if margem_min < 0.06 * w:
        print(f"aviso: o texto chega a {margem_min:.0f}px da borda (ideal >= {0.06 * w:.0f}px)")

    nome = f"gancho_{gid:02d}"
    out = cfg["_saida"]
    alfa_mov = subprocess.Popen([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba",
                                 "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-c:v", "prores_ks", "-profile:v", "4444",
                                 "-pix_fmt", "yuva444p10le", "-alpha_bits", "16", "-vendor", "apl0", str(out / f"{nome}.mov")],
                                stdin=subprocess.PIPE)
    pw, ph = w // 2, h // 2
    prev = subprocess.Popen([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
                             "-s", f"{pw}x{ph}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
                             str(out / f"{nome}_preview.mp4")], stdin=subprocess.PIPE)
    folha_idx = set(np.linspace(0, nf - 1, 8).round().astype(int).tolist())
    folha = []
    sombra_k = max(3, int(min(cw, ch) * 0.012) | 1)
    op = g.get("opacidade", 0.95)
    for k in range(nf):
        a_txt = quadro_texto(camadas, k, nf, fps, op, animacao)
        # sombra suave deslocada, para assentar o texto na superfície
        sombra = cv2.GaussianBlur(a_txt, (0, 0), sombra_k)
        sombra = np.roll(sombra, (int(ch * 0.012), int(cw * 0.006)), axis=(0, 1)) * 0.35
        Hk = cv2.getPerspectiveTransform(ret, cantos[k].astype(np.float32))
        a_t = cv2.warpPerspective(a_txt, Hk, (w, h), flags=cv2.INTER_LINEAR)
        a_s = cv2.warpPerspective(sombra, Hk, (w, h), flags=cv2.INTER_LINEAR)
        alfa = a_t + a_s * (1 - a_t)
        cor = np.where(alfa > 1e-4, a_t / np.maximum(alfa, 1e-4), 0)  # branco nas letras, preto na sombra
        rgba = np.dstack([cor, cor, cor, alfa])
        alfa_mov.stdin.write((np.clip(rgba, 0, 1) * 255 + 0.5).astype(np.uint8).tobytes())
        comp = quadros[k].astype(np.float32) / 255.0
        comp = comp * (1 - alfa[..., None]) + (cor * alfa)[..., None]
        pq = cv2.resize((comp * 255).astype(np.uint8), (pw, ph), interpolation=cv2.INTER_AREA)
        prev.stdin.write(pq.tobytes())
        if k in folha_idx:
            pf = pq.copy()
            cv2.putText(pf, f"{(f0 + k) / fps:.2f}s", (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            folha.append(pf)
    for p in (alfa_mov, prev):
        p.stdin.close()
        p.wait()
    cv2.imwrite(str(out / f"{nome}_folha.jpg"), np.hstack(folha), [cv2.IMWRITE_JPEG_QUALITY, 88])
    perdidos = [k for k, s in enumerate(apoio) if s < MIN]
    rel = {"id": gid, "quadros": nf, "inicio_quadro": f0, "ancora_quadro": fa,
           "inicio_s": round(f0 / fps, 3), "fim_s": round((f0 + nf) / fps, 3),
           "pontos_min": int(min(apoio)), "pontos_med": int(np.median(apoio)), "quadros_fracos": len(perdidos),
           "margem_min_px": round(margem_min),
           "pontos_por_quadro": [int(x) for x in apoio],
           "arquivos": {"alfa": f"{nome}.mov", "preview": f"{nome}_preview.mp4", "folha": f"{nome}_folha.jpg"}}
    (out / f"{nome}_track.json").write_text(json.dumps(rel, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in rel.items() if k != 'pontos_por_quadro'}, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comando", choices=["planos", "grade", "render"])
    ap.add_argument("--config", required=True)
    ap.add_argument("--id", type=int)
    ap.add_argument("--t", type=float)
    a = ap.parse_args()
    cfg = carregar(a.config)
    if a.comando == "planos":
        cmd_planos(cfg)
    elif a.comando == "grade":
        cmd_grade(cfg, a.t)
    else:
        cmd_render(cfg, a.id)


if __name__ == "__main__":
    sys.exit(main())
