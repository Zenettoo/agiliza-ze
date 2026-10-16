#!/usr/bin/env python3
"""Análise completa sem passar pelo chat: DaVinci → transcrição → Claude (ganchos, roteiro) → página.

Uso (o plugin chama isto pelo servidor):
  .venv/bin/python pipeline.py --modo atual|cor|timelines|todas [--alvo ...] --nome "..." \
      [--prompt "nomes"] [--duracao "3 a 4 minutos"] [--obs "pedido extra"]

O andamento fica em projetos/<Nome>/_status.json (lido pela tela inicial).
"""
import argparse
import json
import os as _os
_os.environ.setdefault("PYTHONUTF8", "1")
_os.environ.setdefault("LANG", "pt_BR.UTF-8")
_os.environ.setdefault("LC_ALL", "pt_BR.UTF-8")
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parent
PY = str(BASE / ".venv" / "bin" / "python")
SKILL = Path.home() / ".claude" / "skills" / "decupar-casamento" / "SKILL.md"
CLAUDE = next((str(c) for c in [Path.home() / ".local" / "bin" / "claude", Path("/opt/homebrew/bin/claude"),
                                 Path("/usr/local/bin/claude")] if c.exists()), "claude")


def slug(txt):
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", txt).strip("_") or "projeto"


class Status:
    def __init__(self, pasta: Path, nome: str):
        self.arq = pasta / "_status.json"
        self.d = {"nome": nome, "projeto": pasta.name, "inicio": time.time(), "etapa": "", "msg": "", "pct": 0,
                  "pid": os.getpid(),
                  "erro": None, "fim": None}
        pasta.mkdir(parents=True, exist_ok=True)

    def __call__(self, etapa, msg, pct, **kw):
        self.d.update(etapa=etapa, msg=msg, pct=pct, **kw)
        self.arq.write_text(json.dumps(self.d, ensure_ascii=False))
        print(f"[{pct:3d}%] {etapa}: {msg}", flush=True)


def regras_analise():
    """Pega da skill a seção 'Analisar' (formato do analise.json e regras), para o Claude seguir igual ao chat."""
    if not SKILL.exists():
        return ""
    s = SKILL.read_text()
    m = re.search(r"### 3\. Analisar.*?(?=\n### 4\.)", s, re.S)
    return m.group(0) if m else ""


def analisar(pasta: Path, args, st: Status, tentativa_msg=""):
    t = json.loads((pasta / "transcricao.json").read_text())
    tipo_txt = ""
    if args.tipo:
        sys.path.insert(0, str(BASE))
        from tipos import nome_tipo
        tipo_txt = f"Tipo de trabalho: {nome_tipo(args.tipo)} — use capítulos, emoções e ganchos adequados a esse tipo (não force termos de casamento).\n"
    prompt = f"""Você é o agente de decupagem do usuário (videomaker de casamentos/eventos). Responda em português.
{tipo_txt}
Na pasta atual há `transcricao.txt` ({len(t['segmentos'])} segmentos). Leia o arquivo INTEIRO (use offset/limit se for longo)
e escreva `analise.json` nesta pasta, seguindo exatamente as regras abaixo.

Contexto do projeto: {args.nome}.
Nomes e pessoas: {args.prompt or 'não informados — deduza pelo conteúdo'}.
Duração desejada do roteiro: {args.duracao or '3 a 5 minutos (filme curto)'}.
{('Pedido extra do usuário: ' + args.obs) if args.obs else ''}
Se o material não for casamento (depoimento, institucional, evento), adapte capítulos e ganchos ao tipo de vídeo.
{tentativa_msg}

{regras_analise()}

Importante: o arquivo deve ser JSON válido (sem comentários). `texto` de ganchos e cenas copiado literalmente da transcrição.
Não crie outros arquivos. Ao terminar, responda só "pronto"."""
    cmd = [CLAUDE, "-p", prompt, "--allowedTools", "Read,Write,Edit", "--permission-mode", "acceptEdits",
           "--output-format", "text"]
    st("Analisando", "O Claude está lendo a transcrição e escrevendo ganchos e roteiro…", 70)
    r = subprocess.run(cmd, cwd=pasta, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
    if "Not logged in" in (r.stdout + r.stderr):
        raise RuntimeError("O Claude Code não está logado. No Terminal, rode: ~/.local/bin/claude auth login")
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[-400:] or "o Claude não respondeu")
    json.loads((pasta / "analise.json").read_text())  # valida


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modo", default="atual", choices=["atual", "cor", "timelines", "todas", "arquivo"])
    ap.add_argument("--reanalisar", action="store_true", help="reaproveita a transcrição: só refaz a análise e a página")
    ap.add_argument("--alvo", default="")
    ap.add_argument("--nome", required=True)
    ap.add_argument("--prompt", default="")
    ap.add_argument("--duracao", default="")
    ap.add_argument("--obs", default="")
    ap.add_argument("--faixa", default="")
    ap.add_argument("--tipo", default="")
    args = ap.parse_args()

    pasta = BASE / "projetos" / slug(args.nome)
    pedido = pasta / "_pedido.json"
    if args.reanalisar and pedido.exists():  # mantém duração/nomes/pedido extra da primeira vez, salvo se vierem novos
        antigo = json.loads(pedido.read_text())
        for k in ("prompt", "duracao", "obs", "tipo"):
            if not getattr(args, k):
                setattr(args, k, antigo.get(k, ""))
    st = Status(pasta, args.nome)
    pedido.write_text(json.dumps({k: getattr(args, k) for k in ("modo", "alvo", "prompt", "duracao", "obs", "faixa", "tipo")},
                                 ensure_ascii=False))
    try:
        if args.reanalisar:
            if not (pasta / "transcricao.txt").exists():
                raise RuntimeError("Esse projeto não tem transcrição para reaproveitar.")
            st("Analisando", "Reaproveitando a transcrição…", 60)
            anterior = pasta / "analise_anterior.json"
            if (pasta / "analise.json").exists():
                (pasta / "analise.json").replace(anterior)  # a versão antiga continua aparecendo até a nova ficar pronta
            try:
                analisar(pasta, args, st)
            except Exception:
                if anterior.exists() and not (pasta / "analise.json").exists():
                    anterior.replace(pasta / "analise.json")
                raise
            anterior.unlink(missing_ok=True)
            st("Gerando página", "Montando a página da decupagem…", 95)
            r = subprocess.run([PY, str(BASE / "gerar_entregas.py"), str(pasta)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            if r.returncode != 0:
                raise RuntimeError(r.stderr.strip()[-400:])
            st("Concluído", "Análise refeita! Clique para abrir.", 100, fim=time.time())
            return
        st("Transcrevendo", "Lendo o DaVinci e transcrevendo o áudio (pode levar alguns minutos)…", 5)
        if args.modo == "arquivo":  # sem DaVinci: transcreve os arquivos que o usuário escolheu (--alvo = caminhos separados por |)
            arquivos = [a for a in args.alvo.split("|") if a]
            cmd = [PY, str(BASE / "transcrever.py"), *arquivos, "--nome", args.nome] + (["--prompt", args.prompt] if args.prompt else [])
        else:
            cmd = [PY, str(BASE / "de_davinci.py")]
        if args.modo == "arquivo":
            pass
        elif args.modo == "atual":
            cmd += ["atual"]
        elif args.modo == "cor":
            cmd += ["cor", args.alvo]
        elif args.modo == "todas":
            cmd += ["timelines", "--todas"]
        else:
            cmd += ["timelines", args.alvo]
        if args.modo != "arquivo":
            cmd += ["--nome", args.nome] + (["--prompt", args.prompt] if args.prompt else [])
            cmd += ["--faixa", args.faixa] if args.faixa and args.modo != "cor" else []
        proc = subprocess.Popen(cmd, cwd=BASE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        log = []
        for linha in proc.stdout:
            log.append(linha)
            m = re.match(r"\[(\d+)/(\d+)\]", linha)
            if m:
                k, n = int(m[1]), int(m[2])
                st("Transcrevendo", f"Transcrevendo parte {k} de {n}…", 5 + int(60 * (k - 1) / n))
            elif linha.startswith("→ Montando"):
                st("Transcrevendo", linha.strip("→ \n"), 5)
            elif "Transcrevendo (Whisper" in linha and st.d["pct"] < 15:
                st("Transcrevendo", "Transcrevendo o áudio com o Whisper…", 15)
            elif "pronto em" in linha:
                st("Transcrevendo", "Transcrição pronta.", max(st.d["pct"], 60))
        if proc.wait() != 0:
            raise RuntimeError("Falha na transcrição: " + "".join(log[-5:]).strip()[-300:])

        try:
            analisar(pasta, args, st)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            analisar(pasta, args, st, f"ATENÇÃO: a tentativa anterior gerou um analise.json inválido ({e}). Refaça.")

        st("Gerando página", "Montando a página da decupagem…", 95)
        r = subprocess.run([PY, str(BASE / "gerar_entregas.py"), str(pasta)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip()[-400:])
        st("Concluído", "Pronto! Clique para abrir.", 100, fim=time.time())
    except Exception as e:  # noqa: BLE001
        st("Erro", str(e), st.d["pct"], erro=str(e), fim=time.time())
        sys.exit(1)


if __name__ == "__main__":
    main()
