#!/bin/zsh
# Gera o instalador para compartilhar: Agiliza-Ze-Instalador.dmg na Mesa.
# Leva só o código (nada de projetos, transcrições, modelo ou Python — o instalador baixa na outra máquina).
set -e
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
TMP=$(mktemp -d)
PACOTE="$TMP/Agiliza-Zé"
mkdir -p "$PACOTE/app/skill"
rsync -a "$RAIZ/" "$PACOTE/app/" --exclude .venv --exclude .modelos --exclude .bin --exclude projetos \
  --exclude instalador --exclude __pycache__ --exclude .claude --exclude "*.pyc" --exclude .DS_Store
# skill do chat, com caminhos genéricos (sem o nome de usuário desta máquina)
sed "s#$HOME#~#g" "$HOME/.claude/skills/decupar-casamento/SKILL.md" > "$PACOTE/app/skill/SKILL.md"
cp "$RAIZ/instalador/Instalar Agiliza-Zé.command" "$RAIZ/instalador/LEIA-ME.txt" "$PACOTE/"
chmod +x "$PACOTE/Instalar Agiliza-Zé.command"
DMG="$HOME/Desktop/Agiliza-Ze-Instalador.dmg"
rm -f "$DMG"
hdiutil create -volname "Agiliza-Zé" -srcfolder "$PACOTE" -ov -format UDZO "$DMG" >/dev/null
rm -rf "$TMP"
echo "✓ $DMG ($(du -h "$DMG" | cut -f1))"
