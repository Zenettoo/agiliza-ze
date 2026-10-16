#!/usr/bin/env python3
"""RoteirizaIA — app enxuto: análise de roteiro a partir de arquivos de áudio ou vídeo e download de trilha por link.

Independente de editor (DaVinci, Premiere, Final Cut): basta exportar o áudio ou o vídeo. Não usa o DaVinci. Reaproveita o pipeline (transcrição Whisper local + análise pelo Claude Code)
e o baixar.py do Agiliza-Zé. Roda em http://127.0.0.1:8793.
"""
import json
import os
import signal
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PY = str(BASE / ".venv" / "bin" / "python")
PROJETOS = BASE / "projetos"
PORTA = 8793


def _status(p):
    """Análises e downloads em andamento (ou concluídos há pouco)."""
    out = []
    for f in list(PROJETOS.glob("*/_status.json")) + list(PROJETOS.glob("_sync/dl_*.json")):
        try:
            d = json.loads(f.read_text())
        except Exception:  # noqa: BLE001
            continue
        if not d.get("fim") or time.time() - d["fim"] < 3600:
            d["_arquivo"] = str(f.relative_to(PROJETOS))
            out.append(d)
    return {"ok": True, "jobs": sorted(out, key=lambda d: -d.get("inicio", 0))}


def analisar(p):
    nome = (p.get("nome") or "").strip()
    arquivos = [a.strip() for a in (p.get("arquivos") or []) if a and a.strip()]
    if not nome:
        raise ValueError("Dê um nome ao projeto.")
    if not arquivos:
        raise ValueError("Escolha pelo menos um arquivo de áudio ou vídeo.")
    for a in arquivos:
        if not Path(a).expanduser().exists():
            raise ValueError(f"Arquivo não encontrado: {a}")
    cmd = [PY, str(BASE / "pipeline.py"), "--modo", "arquivo", "--alvo", "|".join(str(Path(a).expanduser()) for a in arquivos),
           "--nome", nome]
    for k in ("prompt", "duracao", "obs", "tipo"):
        if p.get(k):
            cmd += [f"--{k}", str(p[k])]
    subprocess.Popen(cmd, cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return {"ok": True, "msg": "Análise iniciada. Acompanhe no painel."}


def cancelar(p):
    arq = PROJETOS / p.get("arquivo", "")
    if not arq.exists() or arq.name != "_status.json" and not arq.name.startswith("dl_"):
        raise ValueError("Tarefa não encontrada.")
    d = json.loads(arq.read_text())
    pid = d.get("pid")
    if pid and not d.get("fim"):
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    d.update(fim=time.time(), erro="cancelado", etapa="Cancelado", msg="Cancelado pelo usuário.")
    arq.write_text(json.dumps(d, ensure_ascii=False))
    return {"ok": True, "msg": "Cancelado."}


def baixar(p):
    url = (p.get("url") or "").strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError("Cole um link completo (começando com https://).")
    formato = "audio" if p.get("formato") == "audio" else "video"
    sync = PROJETOS / "_sync"
    sync.mkdir(parents=True, exist_ok=True)
    arq = sync / f"dl_{int(time.time() * 1000)}.json"
    subprocess.Popen([PY, str(BASE / "baixar.py"), "--url", url, "--formato", formato, "--status", str(arq)],
                     cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return {"ok": True, "msg": "Download iniciado. Acompanhe no painel."}


def abrir_resultado(p):
    html = PROJETOS / p.get("projeto", "") / "decupagem.html"
    if not html.exists():
        raise ValueError("Página da análise ainda não existe.")
    subprocess.Popen(["open", str(html)])
    return {"ok": True, "msg": "Aberto."}


def downloads(_p):
    pasta = PROJETOS / "_downloads"
    arqs = sorted((f for f in pasta.glob("*") if f.is_file() and not f.name.startswith(".")), key=lambda f: -f.stat().st_mtime) if pasta.exists() else []
    return {"ok": True, "arquivos": [{"nome": f.name, "tamanho": f.stat().st_size} for f in arqs[:50]]}


def abrir_pasta(_p):
    pasta = PROJETOS / "_downloads"
    pasta.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(["open", str(pasta)])
    return {"ok": True, "msg": "Pasta aberta."}


def escolher(_p):
    """Abre o seletor de arquivos do macOS e devolve os caminhos escolhidos."""
    roteiro = ('set arqs to choose file with prompt "Escolha o áudio ou os vídeos do projeto (WAV, MP3, M4A, MOV, MP4…)" with multiple selections allowed\n'
               'set saida to ""\nrepeat with a in arqs\nset saida to saida & POSIX path of a & linefeed\nend repeat\nreturn saida')
    r = subprocess.run(["osascript", "-e", roteiro], capture_output=True, text=True)
    if r.returncode != 0:
        return {"ok": True, "arquivos": []}  # cancelado pelo usuário
    return {"ok": True, "arquivos": [l for l in r.stdout.splitlines() if l.strip()]}


ROTAS = {"/api/escolher": escolher, "/api/analisar": analisar, "/api/cancelar": cancelar, "/api/baixar": baixar, "/api/jobs": _status,
         "/api/resultado": abrir_resultado, "/api/downloads": downloads, "/api/abrir_pasta": abrir_pasta}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, dados):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import importlib
            import pagina
            importlib.reload(pagina)
            corpo = pagina.pagina(PROJETOS).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
            return
        rota = ROTAS.get(self.path.split("?")[0])
        self._json(rota({}) if rota else {"ok": False, "msg": "rota desconhecida"})

    def do_POST(self):
        rota = ROTAS.get(self.path)
        if not rota:
            return self._json({"ok": False, "msg": "rota desconhecida"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            self._json(rota(json.loads(self.rfile.read(n) or b"{}")))
        except Exception as e:  # noqa: BLE001
            self._json({"ok": False, "msg": str(e)})


if __name__ == "__main__":
    print(f"RoteirizaIA em http://127.0.0.1:{PORTA}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORTA), Handler).serve_forever()
