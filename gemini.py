"""Análise pelo Gemini (API do Google AI Studio), alternativa ao Claude Code.

A chave fica nas Chaves do macOS (Keychain), serviço "RoteirizaIA-Gemini"; a variável de ambiente GEMINI_API_KEY
também vale. O modelo escolhido fica em ~/Library/Application Support/RoteirizaIA/config.json.
"""
import json
import re
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://generativelanguage.googleapis.com/v1beta"
SERVICO, CONTA = "RoteirizaIA-Gemini", "api_key"
CONFIG = Path.home() / "Library" / "Application Support" / "RoteirizaIA" / "config.json"


def chave():
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"].strip()
    r = subprocess.run(["security", "find-generic-password", "-s", SERVICO, "-a", CONTA, "-w"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def salvar_chave(valor):
    valor = (valor or "").strip()
    if not valor:
        subprocess.run(["security", "delete-generic-password", "-s", SERVICO, "-a", CONTA], capture_output=True)
        return
    r = subprocess.run(["security", "add-generic-password", "-U", "-s", SERVICO, "-a", CONTA, "-w", valor],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("Não consegui guardar a chave nas Chaves do macOS.")


def ler_config():
    try:
        return json.loads(CONFIG.read_text())
    except Exception:  # noqa: BLE001
        return {}


def salvar_config(**kw):
    c = ler_config()
    c.update({k: v for k, v in kw.items() if v is not None})
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(c, ensure_ascii=False, indent=1))
    return c


def _pedido(url, corpo=None, timeout=60, esperas=(5, 15, 30, 60)):
    """Chamada à API; em sobrecarga momentânea do Google (429/500/503) espera e tenta de novo."""
    for i in range(len(esperas) + 1):
        try:
            return _pedido_uma_vez(url, corpo, timeout)
        except _Temporario as e:
            if i == len(esperas):
                raise RuntimeError(str(e)) from None
            time.sleep(esperas[i])


class _Temporario(Exception):
    pass


def _pedido_uma_vez(url, corpo=None, timeout=60):
    k = chave()
    if not k:
        raise RuntimeError("Falta a chave do Gemini. Cole a sua chave em Configurações do Gemini.")
    req = urllib.request.Request(url, data=json.dumps(corpo).encode() if corpo is not None else None,
                                 headers={"x-goog-api-key": k, "Content-Type": "application/json"},
                                 method="POST" if corpo is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode()).get("error", {}).get("message", "")
        except Exception:  # noqa: BLE001
            msg = ""
        if e.code in (400, 401, 403) and ("API key" in msg or "API_KEY" in msg or e.code in (401, 403)):
            raise RuntimeError("A chave do Gemini foi recusada. Confira a chave em Configurações do Gemini.") from None
        if e.code == 429:
            raise _Temporario("Limite de uso do Gemini atingido. Espere um pouco ou troque o modelo.") from None
        if e.code in (500, 502, 503, 504):
            raise _Temporario("O Gemini está sobrecarregado agora. Tente de novo em alguns minutos.") from None
        raise RuntimeError(f"Gemini respondeu erro {e.code}: {msg[:200]}") from None
    except urllib.error.URLError:
        raise RuntimeError("Sem conexão com o Gemini. Confira a internet.") from None


def modelos():
    """Modelos Gemini disponíveis para essa chave que geram texto."""
    d = _pedido(f"{API}/models?pageSize=200")
    out = []
    for m in d.get("models", []):
        nome = m.get("name", "").replace("models/", "")
        if "generateContent" in m.get("supportedGenerationMethods", []) and nome.startswith("gemini") \
                and not any(x in nome for x in ("embedding", "image", "tts", "audio", "live", "robotics", "banana", "veo", "imagen")):
            out.append(nome)
    return sorted(set(out), reverse=True)


def melhor_modelo(lista):
    """O Flash estável mais novo (ex.: gemini-3.8-flash); se não houver, o Gemini mais novo da lista."""
    def versao(n):
        m = re.match(r"^gemini-(\d+(?:\.\d+)?)-", n)
        return float(m.group(1)) if m else 0.0
    estaveis = [n for n in lista if re.fullmatch(r"gemini-\d+(?:\.\d+)?-flash", n)]
    candidatos = estaveis or [n for n in lista if "flash" in n and "lite" not in n] or lista
    if not candidatos:
        raise RuntimeError("Essa chave não tem nenhum modelo Gemini disponível.")
    return max(candidatos, key=versao)


def modelo_escolhido():
    m = ler_config().get("modelo")
    if not m:
        m = melhor_modelo(modelos())
        salvar_config(modelo=m)
    return m


def gerar_json(prompt, modelo=None):
    """Manda o prompt e devolve o texto da resposta, pedido em JSON."""
    corpo = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
             "generationConfig": {"temperature": 0.4, "responseMimeType": "application/json"}}
    modelo = modelo or modelo_escolhido()
    lista = None
    try:
        d = _pedido(f"{API}/models/{modelo}:generateContent", corpo, timeout=900, esperas=(5, 15, 30))
    except RuntimeError as e:
        if "erro 404" not in str(e) and "sobrecarregado" not in str(e) and "Limite" not in str(e):
            raise
        # o modelo saiu do ar ou está sobrecarregado: tenta os outros Flash, do mais novo para o mais antigo
        lista = modelos()
        alternativas = [m for m in sorted((n for n in lista if re.fullmatch(r"gemini-\d+(?:\.\d+)?-flash", n)),
                                          key=lambda n: float(re.match(r"gemini-(\d+(?:\.\d+)?)", n).group(1)), reverse=True)
                        if m != modelo] + [m for m in ("gemini-flash-latest", "gemini-pro-latest") if m in lista]
        d, ultimo = None, e
        for alt in alternativas:  # todos os Flash disponíveis, do mais novo para o mais antigo
            try:
                d = _pedido(f"{API}/models/{alt}:generateContent", corpo, timeout=900, esperas=(3,))
                salvar_config(modelo=alt)  # fica o modelo que respondeu
                break
            except RuntimeError as e2:
                ultimo = e2
        if d is None:
            raise RuntimeError(f"{ultimo} (tentei também: {', '.join(alternativas) or 'nenhum outro modelo'})")
    try:
        partes = d["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError):
        motivo = (d.get("promptFeedback") or {}).get("blockReason") or (d.get("candidates") or [{}])[0].get("finishReason")
        raise RuntimeError(f"O Gemini não devolveu resposta ({motivo or 'sem motivo informado'}).") from None
    return "".join(p.get("text", "") for p in partes)
