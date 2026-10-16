#!/usr/bin/env python3
"""Gera as entregas da decupagem a partir de transcricao.json + analise.json.

Uso: .venv/bin/python gerar_entregas.py projetos/<nome>

Saídas na pasta do projeto:
  decupagem.html        página com player, sinopse, capítulos, ganchos, roteiro e transcrição
  capitulos_youtube.txt capítulos no formato da descrição do YouTube
  falas_por_pessoa.txt  votos/discursos por falante (presente para o casal)
  roteiro.txt           roteiro com minutagem para o editor
  legenda_falantes.srt  legenda com o nome de quem fala
  roteiro_resolve.json  trechos exatos (segundos) para montar a timeline no DaVinci
"""
import html
import json
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import quote

RESPIRO = 0.25  # segundos de folga antes/depois de cada trecho do roteiro

# Cores de clipe do DaVinci Resolve (nome → tom aproximado para a página)
CORES_RESOLVE = {
    "Orange": "#e8862a", "Apricot": "#f2a766", "Yellow": "#d9b526", "Lime": "#9fc63f",
    "Olive": "#6f9a3a", "Green": "#3e9a5c", "Teal": "#2a9a9a", "Navy": "#3a5ba0",
    "Blue": "#4a90d9", "Purple": "#8e5bc7", "Violet": "#c55bc1", "Pink": "#e46fa6",
    "Tan": "#b9a27c", "Beige": "#c9bba0", "Brown": "#9b6a3e", "Chocolate": "#7a5238",
}
# Cor automática por papel; o resto recebe as cores livres, em ordem
PAPEIS = [("noiva", "Pink"), ("noivo", "Blue"), ("celebrante", "Yellow"), ("padre", "Yellow"),
          ("pastor", "Yellow"), ("juiz", "Yellow"), ("madrinha", "Violet"), ("padrinho", "Teal")]
SEQUENCIA = ["Orange", "Teal", "Purple", "Lime", "Apricot", "Violet", "Olive", "Navy", "Tan", "Brown"]


def tc(seg):
    seg = max(0, seg)
    h, r = divmod(int(seg), 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def srt_tc(seg):
    ms = int(round(max(0, seg) * 1000))
    h, r = divmod(ms, 3_600_000)
    m, r = divmod(r, 60_000)
    s, ms = divmod(r, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def norm(t):
    t = unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", t)


def cores_falantes(nomes, escolhidas):
    """escolhidas: dict nome → cor do Resolve (de analise.json 'cores'), tem prioridade."""
    cores, usadas = {}, set()
    for n in nomes:
        if escolhidas.get(n) in CORES_RESOLVE:
            cores[n] = escolhidas[n]
            usadas.add(cores[n])
    for n in nomes:
        if n in cores:
            continue
        papel = next((c for chave, c in PAPEIS if chave in n.lower() and c not in usadas), None)
        if papel:
            cores[n] = papel
            usadas.add(papel)
    livres = [c for c in SEQUENCIA if c not in usadas]
    for n in nomes:
        if n not in cores:
            cores[n] = livres.pop(0) if livres else "Beige"
    return cores


class Projeto:
    def __init__(self, pasta: Path):
        self.pasta = pasta
        self.t = json.loads((pasta / "transcricao.json").read_text())
        self.a = json.loads((pasta / "analise.json").read_text())
        self.segs = self.t["segmentos"]
        self.offset = self.t["trecho"]["inicio"] or 0
        self.arquivos = self.t.get("arquivos") or [
            {"caminho": self.t["arquivo"], "nome": Path(self.t["arquivo"]).stem, "base": 0}]
        self.multi = len(self.arquivos) > 1
        self.falante = {}
        for f in self.a.get("falantes", []):
            for i in range(f["de"], f["ate"] + 1):
                self.falante[i] = f["nome"]
        ordem = list(dict.fromkeys(f["nome"] for f in self.a.get("falantes", [])))
        self.cores = cores_falantes(ordem, self.a.get("cores", {}))

    def seg(self, i):
        return self.segs[max(0, min(i, len(self.segs) - 1))]

    def janela(self, item):
        """Tempo (início, fim) de um item com de_seg/ate_seg; se houver 'texto',
        acha a citação exata palavra por palavra para cortar justo."""
        a, b = item["de_seg"], item.get("ate_seg", item["de_seg"])
        ini, fim = self.seg(a)["inicio"], self.seg(b)["fim"]
        citacao = item.get("texto")
        if not citacao:
            return ini, fim
        alvo = [norm(w) for w in citacao.split() if norm(w)]
        palavras = [w for s in self.segs[a:b + 1] for w in s["palavras"] if norm(w["p"])]
        chaves = [norm(w["p"]) for w in palavras]
        n = len(alvo)
        if not n:
            return ini, fim
        melhor, pos = 0, None
        for k in range(0, max(1, len(chaves) - n + 1)):
            acertos = sum(1 for x, y in zip(chaves[k:k + n], alvo) if x == y)
            if acertos > melhor:
                melhor, pos = acertos, k
            if acertos == n:
                break
        if pos is not None and melhor >= max(2, int(n * 0.6)):
            return palavras[pos]["i"], palavras[min(pos + n, len(palavras)) - 1]["f"]
        return ini, fim

    def nome_falante(self, i):
        return self.falante.get(i, "")

    def cor(self, nome, hexa=False):
        c = self.cores.get(nome)
        if not c:
            return "#999" if hexa else None
        return CORES_RESOLVE.get(c, "#999") if hexa else c

    def arq(self, i):
        return self.seg(i).get("arq", 0)

    def seq(self, i, segundos):
        """Tempo na sequência (arquivos em fila)."""
        return self.arquivos[self.arq(i)]["base"] + segundos - self.offset

    def rotulo(self, i, segundos):
        """Minutagem para o editor: com nome do arquivo quando há vários."""
        return (f"{self.arquivos[self.arq(i)]['nome']} " if self.multi else "") + tc(segundos)


def escrever_txts(p: Projeto):
    a, pasta = p.a, p.pasta

    linhas = [f"{tc(p.seq(c['de_seg'], p.seg(c['de_seg'])['inicio']))} {c['titulo']}" for c in a.get("capitulos", [])]
    if linhas and not linhas[0].startswith("00:00"):
        linhas[0] = "00:00" + linhas[0][5:]
    (pasta / "capitulos_youtube.txt").write_text("\n".join(linhas) + "\n")

    blocos, atual, buf = [], None, []
    for s in p.segs:
        f = p.nome_falante(s["id"]) or "—"
        if f != atual and buf:
            blocos.append((atual, buf))
            buf = []
        atual = f
        buf.append(s)
    if buf:
        blocos.append((atual, buf))
    out = [f"{a.get('titulo', p.t['projeto'])}\n"]
    for f, ss in blocos:
        out.append(f"{f} [{p.rotulo(ss[0]['id'], ss[0]['inicio'])}]\n" + " ".join(s["texto"] for s in ss) + "\n")
    (pasta / "falas_por_pessoa.txt").write_text("\n".join(out))

    srt = []
    for n, s in enumerate(p.segs, 1):
        f = p.nome_falante(s["id"])
        txt = f"[{f}] {s['texto']}" if f else s["texto"]
        srt.append(f"{n}\n{srt_tc(p.seq(s['id'], s['inicio']))} --> {srt_tc(p.seq(s['id'], s['fim']))}\n{txt}\n")
    (pasta / "legenda_falantes.srt").write_text("\n".join(srt))

    rot = a.get("roteiro") or {}
    cenas, total, out = [], 0.0, [f"ROTEIRO — {rot.get('titulo', '')}\n"]
    for n, c in enumerate(rot.get("cenas", []), 1):
        i, f = p.janela(c)
        i, f = max(0, i - RESPIRO), f + RESPIRO
        total += f - i
        falante = c.get("falante") or p.nome_falante(c["de_seg"])
        cenas.append({"ordem": n, "funcao": c.get("funcao", ""), "falante": falante, "cor": p.cor(falante),
                      "arquivo": p.arquivos[p.arq(c["de_seg"])]["caminho"],
                      "inicio": round(i, 3), "fim": round(f, 3), "texto": c.get("texto", "")})
        out.append(f"{n:02d}. [{c.get('funcao', '')}] {p.rotulo(c['de_seg'], i)}–{tc(f)} ({f - i:.1f}s) {falante}\n"
                   f"    “{c.get('texto') or p.seg(c['de_seg'])['texto']}”"
                   + (f"\n    ✎ {c['nota_de_edicao']}" if c.get("nota_de_edicao") else "") + "\n")
    out.append(f"Duração total: {tc(total)} ({total:.0f}s)")
    (pasta / "roteiro.txt").write_text("\n".join(out) + "\n")

    marcadores = []
    for c in a.get("capitulos", []):
        marcadores.append({"tipo": "capitulo", "nome": c["titulo"], "nota": c.get("resumo", ""),
                           "arquivo": p.arquivos[p.arq(c["de_seg"])]["caminho"],
                           "inicio": p.seg(c["de_seg"])["inicio"], "fim": p.seg(c["ate_seg"])["fim"]})
    for g in a.get("ganchos", []):
        i, f = p.janela(g)
        marcadores.append({"tipo": "gancho", "nome": f"{g['nota']} · {g.get('tipo', '')}",
                           "arquivo": p.arquivos[p.arq(g["de_seg"])]["caminho"],
                           "nota": g.get("texto", ""), "inicio": i, "fim": f})
    (pasta / "roteiro_resolve.json").write_text(json.dumps({
        "arquivos": list(dict.fromkeys(x["caminho"] for x in p.arquivos)),
        "clipes_resolve": {x["caminho"]: x["resolve_clipe"] for x in p.arquivos if x.get("resolve_clipe")},
        "titulo": rot.get("titulo") or p.t["projeto"], "cores": p.cores,
        "cenas": cenas, "marcadores": marcadores}, ensure_ascii=False, indent=1))
    return total


CSS = """
:root{--bg:#0d0e11;--panel:#15171c;--panel2:#1b1e25;--line:#262a33;--ink:#eceef3;--mute:#8a90a0;--soft:#b9bfcc;
--accent:#8b7bff;--accent-2:#5ad1e8;--accent-soft:rgba(139,123,255,.14);--hot:#ff8552;--good:#3ddc97;--warn:#f7c948;--chip:#20232b;
--shadow:0 1px 0 rgba(255,255,255,.03) inset,0 10px 30px rgba(0,0,0,.35);--r:16px}
@media (prefers-color-scheme:light){:root{--bg:#f4f4f7;--panel:#ffffff;--panel2:#f8f8fb;--line:#e6e6ec;--ink:#17181c;--mute:#6c7080;--soft:#3d4150;
--accent:#5b4bdb;--accent-2:#0e9fbd;--accent-soft:rgba(91,75,219,.10);--chip:#f0f0f4;--shadow:0 1px 2px rgba(20,20,40,.05),0 8px 24px rgba(20,20,40,.06)}}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,BlinkMacSystemFont,"SF Pro Text","Inter",sans-serif;-webkit-font-smoothing:antialiased}
.hero{position:relative;overflow:hidden;padding:36px 16px 26px;border-bottom:1px solid var(--line);
 background:radial-gradient(900px 300px at 10% -40%,rgba(139,123,255,.28),transparent 70%),radial-gradient(700px 260px at 95% -30%,rgba(90,209,232,.18),transparent 70%)}
.hero-in{max-width:1240px;margin:0 auto}
.eyebrow{font:700 11px/1 -apple-system,sans-serif;letter-spacing:.16em;text-transform:uppercase;color:var(--accent)}
h1{font:700 34px/1.15 -apple-system,"SF Pro Display",sans-serif;letter-spacing:-.025em;margin:8px 0 6px}
.files{color:var(--mute);font-size:13px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-top:20px}
.stat{background:color-mix(in srgb,var(--panel) 85%,transparent);border:1px solid var(--line);border-radius:14px;padding:12px 14px;backdrop-filter:blur(8px)}
.stat b{display:block;font:700 22px/1.2 -apple-system,"SF Pro Display",sans-serif;letter-spacing:-.02em}
.stat span{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--mute)}
.tabs{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--bg) 82%,transparent);backdrop-filter:blur(14px);border-bottom:1px solid var(--line)}
.tabs-in{max-width:1240px;margin:0 auto;padding:10px 16px;display:flex;gap:6px;overflow-x:auto}
.tabs button{border:0;background:transparent;color:var(--mute);border-radius:10px;padding:8px 14px;cursor:pointer;font:600 13px -apple-system,sans-serif;white-space:nowrap}
.tabs button:hover{color:var(--ink);background:var(--chip)}
.tabs button.on{background:var(--accent);color:#fff}
.tabs button i{font-style:normal;opacity:.75;margin-left:6px;font-weight:500}
.wrap{max-width:1240px;margin:0 auto;padding:22px 16px 140px;display:grid;grid-template-columns:minmax(0,1fr) 400px;gap:22px}
@media (max-width:1000px){.wrap{grid-template-columns:1fr}.side{position:static!important}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:20px;margin-bottom:18px;box-shadow:var(--shadow)}
.card-h{display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin-bottom:14px}
h2{font:700 17px/1.2 -apple-system,"SF Pro Display",sans-serif;margin:0;letter-spacing:-.01em}
.sub{color:var(--mute)}.small{font-size:13px}
.sinopse{font-size:15.5px;line-height:1.7;color:var(--soft)}
.t{font:600 12px ui-monospace,"SF Mono",Menlo,monospace;color:var(--accent);background:var(--accent-soft);border:0;border-radius:8px;padding:4px 8px;cursor:pointer;white-space:nowrap;transition:.15s}
.t:hover{filter:brightness(1.15)}
.t em{font:600 10px -apple-system,sans-serif;font-style:normal;opacity:.7;margin-right:6px;text-transform:uppercase;letter-spacing:.04em}
.t::before{content:"▶ ";font-size:9px;opacity:.8}
.t.tocando{background:var(--accent);color:#fff}.t.tocando::before{content:"❚❚ "}
.t.tocando.pausado{background:var(--accent-soft);color:var(--accent);box-shadow:0 0 0 1.5px var(--accent) inset}.t.tocando.pausado::before{content:"▶ "}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px;align-items:center}
.chip{background:var(--chip);border-radius:999px;padding:3px 10px;font-size:12px;color:var(--mute)}
.chip.e{color:var(--accent-2)}
.pessoa{display:inline-flex;align-items:center;gap:7px;background:var(--chip);border-radius:999px;padding:3px 11px 3px 4px;font-size:12px;font-weight:600}
.av{width:20px;height:20px;border-radius:50%;background:var(--cor);color:#fff;display:inline-grid;place-items:center;font:700 10px -apple-system,sans-serif;flex:none;text-shadow:0 1px 1px rgba(0,0,0,.25)}
.legenda{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.mom{display:grid;grid-template-columns:auto 1fr;gap:12px;align-items:center;padding:9px 0;border-top:1px solid var(--line)}.mom:first-child{border-top:0}
.cap{display:grid;grid-template-columns:96px 1fr;gap:16px;padding:16px 0;border-top:1px solid var(--line)}.cap:first-child{border-top:0;padding-top:4px}
.cap .when{display:flex;flex-direction:column;gap:6px;align-items:flex-start}.cap .when small{color:var(--mute);font-size:12px;padding-left:2px}
.cap h3{margin:0 0 4px;font-size:15.5px;letter-spacing:-.01em}.cap p{margin:0;color:var(--soft);font-size:14px}
.ganchos{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.gancho{background:var(--panel2);border:1px solid var(--line);border-radius:14px;padding:16px;display:flex;flex-direction:column;gap:10px;transition:.15s}
.gancho:hover{border-color:color-mix(in srgb,var(--accent) 50%,var(--line));transform:translateY(-1px)}
.g-top{display:flex;align-items:center;gap:12px}
.ring{--c:var(--good);width:48px;height:48px;border-radius:50%;flex:none;display:grid;place-items:center;
 background:conic-gradient(var(--c) calc(var(--p)*1%),var(--line) 0)}
.ring span{width:38px;height:38px;border-radius:50%;background:var(--panel2);display:grid;place-items:center;font:800 15px -apple-system,"SF Pro Display",sans-serif}
.tipo{font:700 11px -apple-system,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--mute)}
q{font-size:16.5px;line-height:1.5;font-weight:600;letter-spacing:-.005em;quotes:"“" "”"}
.why{color:var(--mute);font-size:13px}
.g-foot{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:auto}
.btn-x{margin-left:auto;border:1px solid var(--line);background:transparent;color:var(--soft);border-radius:8px;padding:4px 10px;cursor:pointer;font:600 12px -apple-system,sans-serif}
.btn-x:hover{border-color:var(--accent);color:var(--accent);background:var(--accent-soft)}
.rot{position:relative;padding-left:4px}
.cena{position:relative;display:grid;grid-template-columns:34px 1fr;gap:14px;padding:0 0 18px}
.cena::before{content:"";position:absolute;left:16px;top:34px;bottom:0;width:2px;background:var(--line)}.cena:last-child::before{display:none}
.no{width:34px;height:34px;border-radius:50%;background:var(--cor,var(--accent));color:#fff;display:grid;place-items:center;font:800 13px -apple-system,sans-serif;box-shadow:0 0 0 4px var(--panel)}
.fn{font:700 11px -apple-system,sans-serif;letter-spacing:.1em;text-transform:uppercase;color:var(--accent-2)}
.cena .fala{font-size:15px;margin:3px 0 0;color:var(--ink)}
.dur{height:4px;border-radius:4px;background:var(--line);margin-top:10px;overflow:hidden}.dur i{display:block;height:100%;background:var(--cor,var(--accent));opacity:.8}
.nota-ed{font-size:13px;color:var(--mute);margin-top:6px}
.busca{position:relative;margin-bottom:12px}
#busca{width:100%;padding:11px 14px 11px 38px;border:1px solid var(--line);border-radius:12px;background:var(--panel2);color:var(--ink);font:inherit;outline:none}
#busca:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.busca::before{content:"⌕";position:absolute;left:13px;top:8px;font-size:18px;color:var(--mute)}
#busca-n{position:absolute;right:12px;top:11px;font-size:12px;color:var(--mute)}
.seg{display:grid;grid-template-columns:80px 1fr 30px;gap:12px;padding:9px 8px;border-radius:12px;align-items:start}
.seg:hover{background:var(--panel2)}
body.multi .seg{grid-template-columns:172px 1fr 30px}.seg>.t{justify-self:start}
.seg .corpo{display:grid;grid-template-columns:22px 1fr;gap:10px}
.seg .who{font-size:12px;font-weight:700;color:var(--cor,var(--accent));margin-bottom:1px}
.seg .txt{color:var(--soft)}
.seg.agora{background:var(--accent-soft);box-shadow:0 0 0 1px color-mix(in srgb,var(--accent) 45%,transparent) inset}
.seg.agora .txt{color:var(--ink)}
.seg.duv .txt{opacity:.55}
mark{background:#ffd84d;color:#111;border-radius:4px;padding:0 2px}
.x{border:0;background:transparent;cursor:pointer;font-size:14px;padding:4px 6px;border-radius:8px;color:var(--mute);opacity:0}
.seg:hover .x{opacity:1}.x:hover{background:var(--accent-soft);color:var(--accent)}
.side{position:sticky;top:64px;align-self:start}
.player{padding:12px}
audio{width:100%;display:block;height:44px;border-radius:999px}
.agora{margin-top:10px;padding:12px 14px;border-radius:12px;background:var(--panel2);border:1px solid var(--line);min-height:76px}
.agora small{font:700 10.5px -apple-system,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:var(--mute)}
#agora-quem{font-size:12.5px;font-weight:700;margin:4px 0 2px}
#agora-txt{font-size:14px;color:var(--soft)}
.acao-p{margin-top:10px;width:100%;border:0;background:var(--accent);color:#fff;border-radius:12px;padding:11px;cursor:pointer;font:700 14px -apple-system,sans-serif}
.acao-p:hover{filter:brightness(1.1)}
.dicas{font-size:12px;color:var(--mute);margin-top:10px;line-height:1.7}
kbd{font:600 11px ui-monospace,Menlo,monospace;background:var(--chip);border:1px solid var(--line);border-bottom-width:2px;border-radius:6px;padding:1px 6px;color:var(--soft)}
#barra{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);width:min(780px,calc(100% - 32px));
 background:color-mix(in srgb,var(--panel) 92%,transparent);backdrop-filter:blur(16px);border:1px solid var(--line);border-radius:18px;
 box-shadow:0 24px 60px rgba(0,0,0,.45);padding:16px 18px;display:none;z-index:9}
#barra.on{display:block;animation:sobe .18s ease-out}@keyframes sobe{from{opacity:0;transform:translate(-50%,10px)}}
#barra .txt-c{font-weight:650;margin:4px 0 12px;max-height:3.2em;overflow:hidden;font-size:15px}
#barra .lin{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
#barra .tc{display:inline-flex;align-items:center;gap:6px;background:var(--chip);border-radius:10px;padding:4px 6px 4px 10px;font:600 13px ui-monospace,Menlo,monospace}
#barra .tc em{font:700 10px -apple-system,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--mute);font-style:normal}
#barra .tc button,#barra .acao{border:1px solid var(--line);background:var(--panel2);color:var(--ink);border-radius:8px;padding:5px 10px;cursor:pointer;font:600 13px -apple-system,sans-serif}
#barra .tc button{padding:2px 8px}
#barra .acao.pri{background:var(--accent);border-color:var(--accent);color:#fff}
#barra .acao:disabled{opacity:.4;cursor:not-allowed}#barra select{font:inherit;font-size:13px;border-radius:8px;padding:3px;background:var(--panel2);color:var(--ink);border:1px solid var(--line)}
#barra .msg{font-size:13px;color:var(--mute);margin-top:10px;min-height:1.2em}#barra .msg a{color:var(--accent)}
#barra .fechar{position:absolute;right:12px;top:10px;border:0;background:transparent;color:var(--mute);cursor:pointer;font-size:16px}
@media print{.side,.tabs,.busca,#barra,.x,.btn-x{display:none}.wrap{display:block}.card{break-inside:avoid;box-shadow:none}}
"""


JS = r"""
const v=document.querySelector('audio');
const fontes=v?JSON.parse(v.dataset.fontes||'[]'):[];
function ir(arq,t){if(v.dataset.v!==arq&&fontes[+arq]){v.dataset.v=arq;v.src=fontes[+arq];
  v.addEventListener('loadedmetadata',()=>{v.currentTime=t;v.play();},{once:true});}else{v.currentTime=t;v.play();}}
let ativo=null;
document.addEventListener('click',e=>{const b=e.target.closest('[data-t]');if(!b)return;
 if(v&&ativo===b){if(v.paused)v.play();else v.pause();return;}  // mesma minutagem: pausa / continua
 document.querySelectorAll('.t.tocando').forEach(x=>x.classList.remove('tocando'));ativo=b;b.classList.add('tocando');
 if(v)ir(b.dataset.v||'0',parseFloat(b.dataset.t));
 const id=b.dataset.seg;if(id){const el=document.getElementById('s'+id);el&&el.scrollIntoView({block:'center'});}});
if(v){v.addEventListener('timeupdate',()=>{const t=v.currentTime;let cur=null;
 document.querySelectorAll('.seg').forEach(s=>{if(s.dataset.v===v.dataset.v&&+s.dataset.i<=t&&t<=+s.dataset.f)cur=s;s.classList.remove('agora')});
 cur&&cur.classList.add('agora');});}
const busca=document.getElementById('busca');
busca&&busca.addEventListener('input',()=>{const q=busca.value.trim().toLowerCase();
 document.querySelectorAll('.seg').forEach(s=>{const p=s.querySelector('.txt');p.innerHTML=p.dataset.raw;
  if(!q){s.style.display='';s.classList.remove('hit');return;}
  const ok=p.dataset.raw.toLowerCase().includes(q);s.style.display=ok?'':'none';
  if(ok){p.innerHTML=p.dataset.raw.replace(new RegExp('('+q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+')','ig'),'<mark>$1</mark>');}});});
// ---------- tocar / pausar ----------
const btnPausa=document.getElementById('pausa');
function estado(){const tocando=v&&!v.paused;if(btnPausa)btnPausa.textContent=tocando?'⏸ Pausar':'▶ Continuar';
 document.querySelectorAll('.t.tocando').forEach(x=>x.classList.toggle('pausado',!tocando));
 const o=document.querySelector('#barra [data-acao=ouvir]');if(o&&!tocando)o.textContent='▶ Ouvir';}
if(v){['play','pause','ended'].forEach(ev=>v.addEventListener(ev,estado));}
btnPausa&&btnPausa.addEventListener('click',()=>{if(!v)return;if(v.paused)v.play();else v.pause();});
document.addEventListener('keydown',e=>{if(!v)return;const alvo=e.target.tagName;
 if(alvo==='INPUT'||alvo==='TEXTAREA'||alvo==='SELECT'||e.target.isContentEditable)return;
 if(e.code==='Space'){e.preventDefault();if(v.paused)v.play();else v.pause();}
 else if(e.key==='Escape'){v.pause();}});
// ---------- corte ----------
const barra=document.getElementById('barra');let C=null,parar=null,servidor=false;
const $=id=>document.getElementById(id);
const fmt=t=>{t=Math.max(0,t);const m=Math.floor(t/60),s=(t%60).toFixed(2).padStart(5,'0');return m+':'+s;};
fetch('/api/status').then(r=>r.json()).then(d=>{servidor=true;INFO.resolve=d.resolve;INFO.projResolve=d.projeto;}).catch(()=>{});
function folga(){return parseFloat($('b-folga').value);}
function janela(){const g=folga();return [Math.max(0,C.i-g),C.f+g];}
function desenhar(){$('b-i').textContent=fmt(C.i);$('b-f').textContent=fmt(C.f);const [a,b]=janela();
 $('b-dur').textContent=(b-a).toFixed(1)+' s no corte';$('b-texto').textContent='“'+C.texto+'”';
 $('b-quem').innerHTML=(C.quem?'<b>'+C.quem+'</b> · ':'')+(INFO.arquivos[+C.v]||'');
 const off=!servidor;barra.querySelector('[data-acao=cortar]').disabled=off;barra.querySelectorAll('[data-acao=localizar],[data-acao=davinci]').forEach(x=>x.disabled=off);
 if(off)$('b-msg').innerHTML='Para baixar ou usar o DaVinci, abra esta página pelo plugin Agiliza-Zé no DaVinci (ou pelo atalho <b>abrir</b>).';}
function abrirCorte(d){C=Object.assign({},d);$('b-msg').textContent='';barra.classList.add('on');desenhar();}
document.addEventListener('click',e=>{const b=e.target.closest('[data-corte]');if(!b)return;e.stopPropagation();
 abrirCorte(JSON.parse(b.dataset.corte));});
barra.addEventListener('click',async e=>{const n=e.target.closest('[data-n]');
 if(n){const [k,d]=n.dataset.n.split(',');C[k]=Math.round((C[k]+parseFloat(d))*100)/100;if(C.f<=C.i+0.2)C.f=C.i+0.2;desenhar();return;}
 const a=e.target.closest('[data-acao]');if(!a)return;const acao=a.dataset.acao;
 if(acao==='fechar'){barra.classList.remove('on');clearInterval(parar);if(v)v.pause();return;}
 const [ini,fim]=janela();
 if(acao==='ouvir'){if(!v)return;clearInterval(parar);
  if(!v.paused&&a.textContent.includes('Parar')){v.pause();return;}
  ir(String(C.v),ini);a.textContent='⏸ Parar';
  parar=setInterval(()=>{if(v.currentTime>=fim){v.pause();clearInterval(parar);}},50);return;}
 const corpo={projeto:INFO.projeto,titulo:INFO.titulo,arq:C.v,inicio:ini,fim:fim,ponto:C.i,nome:C.nome,quem:C.quem,cor:C.cor,texto:C.texto};
 a.disabled=true;$('b-msg').textContent={cortar:'Cortando…',localizar:'Procurando no DaVinci…',davinci:'Enviando pro DaVinci…'}[acao];
 try{const r=await fetch('/api/'+acao,{method:'POST',body:JSON.stringify(corpo)});const d=await r.json();
  $('b-msg').innerHTML=(d.ok?'✓ ':'⚠︎ ')+d.msg+(d.url?' · <a href="'+d.url+'" download>baixar</a>':'');}
 catch(err){$('b-msg').textContent='⚠︎ Servidor não respondeu.';}
 a.disabled=false;});
$('b-folga').addEventListener('change',()=>C&&desenhar());
// seleção de texto na transcrição → corte palavra por palavra
function spans(segId,texto){const ws=INFO.palavras[segId]||[];let pos=0;
 return ws.map(w=>{let k=texto.indexOf(w[2],pos);if(k<0)k=pos;const r={i:w[0],f:w[1],a:k,b:k+w[2].length};pos=r.b;return r;});}
function offset(txt,node,off){const r=document.createRange();r.setStart(txt,0);r.setEnd(node,off);return r.toString().length;}
document.addEventListener('mouseup',()=>{const sel=getSelection();if(!sel||sel.isCollapsed)return;
 const rg=sel.getRangeAt(0);const ea=rg.startContainer.parentElement&&rg.startContainer.parentElement.closest('.seg');
 const eb=rg.endContainer.parentElement&&rg.endContainer.parentElement.closest('.seg');
 if(!ea||!eb||ea.dataset.v!==eb.dataset.v)return;
 const ta=ea.querySelector('.txt'),tb=eb.querySelector('.txt');if(!ta.contains(rg.startContainer)||!tb.contains(rg.endContainer))return;
 const oa=offset(ta,rg.startContainer,rg.startOffset),ob=offset(tb,rg.endContainer,rg.endOffset);
 const wa=spans(ea.id.slice(1),ta.textContent).find(w=>w.b>oa),wb=spans(eb.id.slice(1),tb.textContent).filter(w=>w.a<ob).pop();
 if(!wa||!wb)return;const texto=sel.toString().trim().replace(/\s+/g,' ');
 abrirCorte({i:wa.i,f:wb.f,v:+ea.dataset.v,quem:ea.dataset.quem,cor:INFO.cores[ea.dataset.quem]||'',texto:texto,nome:texto.slice(0,40)});});
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{
 document.querySelectorAll('.tabs button').forEach(x=>x.classList.toggle('on',x===b));
 document.querySelectorAll('[data-aba]').forEach(s=>s.style.display=(b.dataset.ir==='tudo'||s.dataset.aba===b.dataset.ir)?'':'none');});
"""


JS_EXTRA = r"""
// ---------- tocando agora + contador da busca ----------
if(v){v.addEventListener('timeupdate',()=>{const s=document.querySelector('.seg.agora');if(!s)return;
 $('agora-quem').textContent=s.dataset.quem||'';$('agora-quem').style.color=getComputedStyle(s).getPropertyValue('--cor')||'';
 $('agora-txt').textContent=s.querySelector('.txt').dataset.raw.replace(/&quot;/g,'"').replace(/&amp;/g,'&').replace(/&#x27;/g,"'");});}
busca&&busca.addEventListener('input',()=>{const q=busca.value.trim();const n=q?document.querySelectorAll('.seg:not([style*="display: none"])').length:0;
 $('busca-n').textContent=q?(n+(n===1?' fala':' falas')):'';});
"""


def escrever_html(p: Projeto, total_roteiro):
    a, e = p.a, html.escape

    def T(s, seg):
        marca = ""
        if p.multi:  # nome do arquivo/timeline curto, discreto, antes do tempo
            nome = p.arquivos[p.arq(seg)]["nome"].replace("_", " ")
            marca = f'<em>{e(nome if len(nome) <= 14 else nome[:13] + "…")}</em>'
        return (f'<button class="t" data-t="{s:.2f}" data-v="{p.arq(seg)}" data-seg="{seg}" '
                f'title="{e(p.rotulo(seg, s))}">{marca}{tc(s)}</button>')

    def X(i, f, seg, nome, quem, texto, rotulo=None):
        dados = {"i": round(i, 3), "f": round(f, 3), "v": p.arq(seg), "nome": nome, "quem": quem,
                 "cor": p.cor(quem) or "", "texto": texto}
        cls, txt = ("btn-x", rotulo) if rotulo else ("x", "✂")
        return f'<button class="{cls}" title="Cortar este trecho" data-corte="{e(json.dumps(dados, ensure_ascii=False))}">{txt}</button>'

    chips = lambda xs, cls="": "".join(f'<span class="chip {cls}">{e(x)}</span>' for x in xs or [])
    inicial = lambda nome: e((re.sub(r"[^A-Za-zÀ-ÿ]", "", nome) or "?")[0].upper())

    def av(nome):
        return f'<span class="av" style="--cor:{p.cor(nome, True)}">{inicial(nome)}</span>'

    def pessoa(nome, extra=""):
        if not nome:
            return ""
        return f'<span class="pessoa" style="--cor:{p.cor(nome, True)}">{av(nome)}{e(nome)}{extra}</span>'

    caps = []
    for c in a.get("capitulos", []):
        i, f = p.seg(c["de_seg"])["inicio"], p.seg(c["ate_seg"])["fim"]
        caps.append(f'<div class="cap"><div class="when">{T(i, c["de_seg"])}<small>{tc(f - i)}</small></div><div>'
                    f'<h3>{e(c["titulo"])}</h3><p>{e(c.get("resumo", ""))}</p>'
                    f'<div class="chips">{"".join(pessoa(x) for x in c.get("falantes") or [])}'
                    f'{chips(c.get("emocoes"), "e")}{chips(c.get("tags"))}</div></div></div>')

    gs = []
    for g in sorted(a.get("ganchos", []), key=lambda g: -g["nota"]):
        i, f = p.janela(g)
        quem = g.get("falante") or p.nome_falante(g["de_seg"])
        cor = "var(--good)" if g["nota"] >= 90 else "var(--warn)" if g["nota"] >= 80 else "var(--hot)"
        gs.append(f'<div class="gancho"><div class="g-top"><div class="ring" style="--p:{g["nota"]};--c:{cor}"><span>{g["nota"]}</span></div>'
                  f'<div><div class="tipo">{e(g.get("tipo", ""))}</div>{pessoa(quem)}</div></div>'
                  f'<q>{e(g.get("texto", ""))}</q><div class="why">{e(g.get("por_que", ""))}</div>'
                  f'<div class="g-foot">{T(i, g["de_seg"])}<span class="chip">{f - i:.1f}s</span>'
                  f'{X(i, f, g["de_seg"], "Gancho " + str(g["nota"]) + " - " + g.get("texto", "")[:40], quem, g.get("texto", ""), "✂ Cortar")}'
                  f'</div></div>')

    rot = a.get("roteiro") or {}
    janelas = [p.janela(c) for c in rot.get("cenas", [])]
    maior = max([f - i for i, f in janelas] or [1])
    cenas = []
    for n, (c, (i, f)) in enumerate(zip(rot.get("cenas", []), janelas), 1):
        quem = c.get("falante") or p.nome_falante(c["de_seg"])
        texto = c.get("texto") or p.seg(c["de_seg"])["texto"]
        cenas.append(f'<div class="cena" style="--cor:{p.cor(quem, True)}"><div class="no">{n:02d}</div><div>'
                     f'<div class="fn">{e(c.get("funcao", ""))}</div><div class="fala">“{e(texto)}”</div>'
                     f'<div class="chips">{T(i, c["de_seg"])}{pessoa(quem)}<span class="chip">{f - i:.1f}s</span>'
                     f'{X(i, f, c["de_seg"], f"Cena {n:02d} " + c.get("funcao", ""), quem, texto, "✂ Cortar")}</div>'
                     + (f'<div class="nota-ed">✎ {e(c["nota_de_edicao"])}</div>' if c.get("nota_de_edicao") else "")
                     + f'<div class="dur"><i style="width:{(f - i) / maior * 100:.0f}%"></i></div></div></div>')

    mom = []
    for m in a.get("momentos", []):
        i = p.seg(m["de_seg"])["inicio"]
        mom.append(f'<div class="mom">{T(i, m["de_seg"])}<div><b>{e(m["tipo"])}</b>'
                   + (f' <span class="sub small">· {e(m["nota"])}</span>' if m.get("nota") else "") + '</div></div>')

    segs = []
    for s in p.segs:
        quem = p.nome_falante(s["id"])
        raw = e(s["texto"])
        estilo = f' style="--cor:{p.cor(quem, True)}"' if quem else ""
        segs.append(f'<div class="seg{" duv" if s.get("duvidoso") else ""}"{estilo} data-quem="{e(quem)}" id="s{s["id"]}" '
                    f'data-v="{s.get("arq", 0)}" data-i="{s["inicio"]}" data-f="{s["fim"]}">{T(s["inicio"], s["id"])}'
                    f'<div class="corpo">{av(quem) if quem else "<span></span>"}<div>'
                    f'{f"<div class=who>{e(quem)}</div>" if quem else ""}<div class="txt" data-raw="{raw}">{raw}</div></div></div>'
                    f'{X(s["inicio"], s["fim"], s["id"], s["texto"][:40], quem, s["texto"])}</div>')

    # atalhos para os arquivos de mídia (não duplica o vídeo, só aponta para ele)
    fontes = []
    for k, arq in enumerate(p.arquivos):
        origem = Path(arq["caminho"])
        atalho = p.pasta / (f"video{k if p.multi else ''}" + origem.suffix.lower())
        if not atalho.is_symlink() and not atalho.exists():
            atalho.symlink_to(origem)
        fontes.append(quote(atalho.name))
    falantes = list(p.cores)
    titulo = a.get("titulo") or p.t["projeto"]
    info = {"projeto": p.pasta.name, "titulo": titulo, "cores": p.cores,
            "arquivos": [x.get("resolve_timeline") or Path(x["caminho"]).name for x in p.arquivos],
            "palavras": {s["id"]: [[w["i"], w["f"], w["p"]] for w in s["palavras"]] for s in p.segs}}
    stat = lambda v, rot_: f'<div class="stat"><b>{v}</b><span>{rot_}</span></div>'
    nc, ng, nr = len(a.get("capitulos", [])), len(a.get("ganchos", [])), len(rot.get("cenas", []))
    pagina = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Agiliza-Zé · {e(titulo)}</title>
<style>{CSS}</style></head><body class="{'multi' if p.multi else ''}">
<header class="hero"><div class="hero-in"><div class="eyebrow"><a href="/" style="color:inherit;text-decoration:none">← Projetos</a> · Agiliza-Zé</div><h1>{e(titulo)}</h1>
<div class="files">{e(" · ".join(info["arquivos"]))}</div>
<div class="stats">{stat(tc(p.t['duracao']), 'duração')}{stat(nc, 'capítulos')}{stat(ng, 'ganchos')}
{stat(len(falantes), 'falantes')}{stat(tc(total_roteiro), 'roteiro')}{stat(str(round((p.t.get('confianca_media') or 0) * 100)) + '%', 'confiança')}</div></div></header>
<nav class="tabs"><div class="tabs-in"><button class="on" data-ir="tudo">Visão geral</button>
<button data-ir="cap">Capítulos<i>{nc}</i></button><button data-ir="gan">Ganchos<i>{ng}</i></button>
<button data-ir="rot">Roteiro<i>{nr}</i></button><button data-ir="tra">Transcrição<i>{len(p.segs)}</i></button></div></nav>
<div class="wrap"><main>
<section class="card" data-aba="cap"><div class="card-h"><h2>Sinopse</h2></div><div class="sinopse">{e(a.get('sinopse', ''))}</div>
<div class="legenda">{"".join(pessoa(f) for f in falantes)}</div></section>
{f'<section class="card" data-aba="cap"><div class="card-h"><h2>Momentos-chave</h2></div>{"".join(mom)}</section>' if mom else ''}
<section class="card" data-aba="gan"><div class="card-h"><h2>Ganchos</h2><span class="sub small">nota de impacto · do maior para o menor</span></div><div class="ganchos">{''.join(gs)}</div></section>
<section class="card" data-aba="rot"><div class="card-h"><h2>Roteiro · {e(rot.get('titulo', ''))}</h2><span class="sub small">{nr} cenas · {tc(total_roteiro)}</span></div><div class="rot">{''.join(cenas)}</div></section>
<section class="card" data-aba="cap"><div class="card-h"><h2>Capítulos</h2><span class="sub small">{nc} partes</span></div>{''.join(caps)}</section>
<section class="card" data-aba="tra"><div class="card-h"><h2>Transcrição</h2><span class="sub small">selecione palavras para cortar</span></div>
<div class="busca"><input id="busca" placeholder="Buscar: prometo, aliança, amor…"><span id="busca-n"></span></div>{''.join(segs)}</section>
</main>
<aside class="side"><div class="card player"><audio controls preload="metadata" src="{fontes[0]}" data-fontes='{json.dumps(fontes)}' data-v="0"></audio>
<div class="agora"><small>Tocando agora</small><div id="agora-quem"></div><div id="agora-txt" class="sub">Clique numa minutagem para ouvir.</div></div>
<button id="pausa" class="acao-p">▶ Continuar</button>
<div class="dicas">Clique na minutagem para tocar e de novo para pausar · <kbd>espaço</kbd> toca/pausa · <kbd>Esc</kbd> pausa<br>
<b>✂</b> corta o trecho · selecione palavras na transcrição para um corte exato</div></div></aside>
</div>
<div id="barra"><button class="fechar" data-acao="fechar">✕</button>
<div class="sub small" id="b-quem"></div><div class="txt-c" id="b-texto"></div>
<div class="lin"><span class="tc"><em>Início</em><span id="b-i"></span><button data-n="i,-0.1">−</button><button data-n="i,0.1">+</button></span>
<span class="tc"><em>Fim</em><span id="b-f"></span><button data-n="f,-0.1">−</button><button data-n="f,0.1">+</button></span>
<label class="sub small">Folga <select id="b-folga"><option value="0">0</option><option value="0.15">0,15 s</option>
<option value="0.3" selected>0,3 s</option><option value="0.5">0,5 s</option><option value="1">1 s</option></select></label>
<span class="sub small" id="b-dur"></span></div>
<div class="lin" style="margin-top:12px"><button class="acao" data-acao="ouvir">▶ Ouvir</button>
<button class="acao" data-acao="cortar">⬇ Baixar trecho</button><button class="acao" data-acao="localizar">📍 Mostrar no DaVinci</button><button class="acao pri" data-acao="davinci">➜ Mandar pro DaVinci</button></div>
<div class="msg" id="b-msg"></div></div>
<script>const INFO={json.dumps(info, ensure_ascii=False)};</script>
<script>{JS}{JS_EXTRA}</script></body></html>"""
    (p.pasta / "decupagem.html").write_text(pagina)



def main():
    pasta = Path(sys.argv[1]).expanduser().resolve()
    p = Projeto(pasta)
    total = escrever_txts(p)
    escrever_html(p, total)
    print(f"✓ Entregas geradas em {pasta}  (roteiro: {tc(total)})")


if __name__ == "__main__":
    main()
