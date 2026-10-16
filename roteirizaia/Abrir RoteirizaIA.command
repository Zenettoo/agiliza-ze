#!/bin/zsh
# Abre o RoteirizaIA no navegador (sobe o servidor local se ainda não estiver rodando).
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
if ! curl -s -m 2 http://127.0.0.1:8793/ >/dev/null; then
  nohup "$DIR/../.venv/bin/python" "$DIR/servidor.py" > "$DIR/servidor.log" 2>&1 &
  sleep 2
fi
open "http://127.0.0.1:8793/"
