#!/bin/zsh
# Gera ~/Desktop/RoteirizaIA-Instalador.dmg: só os arquivos que o RoteirizaIA usa (sem Python, modelo nem análises).
set -e
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
TMP=$(mktemp -d)
PACOTE="$TMP/RoteirizaIA"
APP="$PACOTE/app"
mkdir -p "$APP/roteirizaia" "$APP/skill"
for f in pipeline.py transcrever.py gerar_entregas.py gemini.py baixar.py sincronizar.py tipos.py pagina_inicial.py; do
  cp "$RAIZ/$f" "$APP/"
done
cp "$RAIZ/roteirizaia/servidor.py" "$RAIZ/roteirizaia/pagina.py" "$APP/roteirizaia/"
[[ -f "$RAIZ/roteirizaia/icone.icns" ]] && cp "$RAIZ/roteirizaia/icone.icns" "$APP/roteirizaia/"
# regras da análise, sem caminhos desta máquina
sed "s#$HOME#~#g" "$HOME/.claude/skills/decupar-casamento/SKILL.md" > "$APP/skill/SKILL.md"
cp "$RAIZ/roteirizaia/instalador/Instalar RoteirizaIA.command" "$RAIZ/roteirizaia/instalador/LEIA-ME.txt" "$PACOTE/"
chmod +x "$PACOTE/Instalar RoteirizaIA.command"
DMG="$HOME/Desktop/RoteirizaIA-Instalador.dmg"
rm -f "$DMG"
hdiutil create -volname "RoteirizaIA" -srcfolder "$PACOTE" -ov -format UDZO "$DMG" >/dev/null
rm -rf "$TMP"
echo "✓ $DMG ($(du -h "$DMG" | cut -f1))"
