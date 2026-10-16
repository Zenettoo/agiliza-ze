#!/bin/zsh
# Instalador do RoteirizaIA — dê dois cliques (na primeira vez: botão direito › Abrir).
cd "$(dirname "$0")"
ORIGEM="$PWD/app"
DEST="${ROTEIRIZAIA_DEST:-$HOME/Documents/RoteirizaIA}"
ok(){ print -P "%F{green}✓%f $1"; }
passo(){ print -P "\n%F{yellow}▸ $1%f"; }
erro(){ print -P "\n%F{red}✗ $1%f"; read -k1 "?Aperte qualquer tecla para fechar."; exit 1; }

clear
print -P "%B%F{yellow}RoteirizaIA%f%b — instalador"
print "Transcreve no seu Mac e entrega ganchos, capítulos e roteiro. Funciona com DaVinci, Premiere e Final Cut.\n"

passo "Conferindo o Mac"
[[ "$(uname -m)" == "arm64" ]] || erro "O RoteirizaIA precisa de um Mac com chip Apple (M1, M2, M3, M4…)."
ok "Mac com chip Apple"
LIVRE=$(df -g "$HOME" | awk 'NR==2{print $4}')
(( LIVRE >= 4 )) || erro "Pouco espaço livre (${LIVRE} GB). Libere pelo menos 4 GB e rode de novo."

passo "Copiando o RoteirizaIA para $DEST"
mkdir -p "$DEST/projetos" || erro "Não consegui criar $DEST"
rsync -a "$ORIGEM/" "$DEST/" --exclude projetos || erro "Falha ao copiar os arquivos."
ok "Arquivos copiados (suas análises, se houver, foram mantidas)"

passo "Instalando o Python e as bibliotecas (alguns minutos na primeira vez)"
if [[ ! -x "$DEST/.bin/uv" ]]; then
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$DEST/.bin" UV_NO_MODIFY_PATH=1 sh >/dev/null 2>&1 || erro "Falha ao baixar o instalador do Python (uv). Confira a internet."
fi
[[ -x "$DEST/.venv/bin/python" ]] || "$DEST/.bin/uv" venv --python 3.12 "$DEST/.venv" >/dev/null 2>&1 || erro "Falha ao criar o ambiente Python."
"$DEST/.bin/uv" pip install --python "$DEST/.venv/bin/python" mlx-whisper imageio-ffmpeg numpy yt-dlp deno >/dev/null 2>&1 || erro "Falha ao instalar as bibliotecas."
FF=$("$DEST/.venv/bin/python" -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())") && ln -sf "$FF" "$DEST/.venv/bin/ffmpeg"
"$DEST/.bin/uv" cache clean >/dev/null 2>&1
ok "Python, Whisper e ffmpeg prontos"

passo "Modelo de transcrição (~1,6 GB, só na primeira vez)"
AGZ="$HOME/Documents/Agiliza-Ze/.modelos"
if [[ ! -d "$DEST/.modelos/hub" && -d "$AGZ/hub" ]]; then
  cp -Rc "$AGZ" "$DEST/.modelos" 2>/dev/null && ok "Reaproveitado do Agiliza-Zé (sem baixar de novo)"
fi
HF_HOME="$DEST/.modelos" "$DEST/.venv/bin/python" -c "from huggingface_hub import snapshot_download; snapshot_download('mlx-community/whisper-large-v3-turbo')" >/dev/null 2>&1 \
  || erro "Falha ao baixar o modelo. Confira a internet e rode de novo."
ok "Modelo de transcrição pronto"

passo "Criando o app RoteirizaIA"
APPS="$HOME/Applications"; [[ -n "$ROTEIRIZAIA_DEST" ]] && APPS="$DEST"  # teste: não mexe em ~/Applications
mkdir -p "$APPS"
osacompile -o "$APPS/RoteirizaIA.app" -e "do shell script \"cd \" & quoted form of \"$DEST\" & \" && (curl -s -m 1 -o /dev/null http://127.0.0.1:8793/ || (nohup .venv/bin/python roteirizaia/servidor.py > roteirizaia/servidor.log 2>&1 &)); sleep 2\"" \
  -e 'open location "http://127.0.0.1:8793/"' >/dev/null 2>&1 || erro "Falha ao criar o app."
if [[ -f "$DEST/roteirizaia/icone.icns" ]]; then  # ícone do RoteirizaIA no lugar do ícone padrão de script
  cp "$DEST/roteirizaia/icone.icns" "$APPS/RoteirizaIA.app/Contents/Resources/applet.icns"
  rm -f "$APPS/RoteirizaIA.app/Contents/Resources/Assets.car"
  /usr/libexec/PlistBuddy -c "Delete :CFBundleIconName" "$APPS/RoteirizaIA.app/Contents/Info.plist" >/dev/null 2>&1
  touch "$APPS/RoteirizaIA.app"
fi
[[ -z "$ROTEIRIZAIA_DEST" ]] && ln -sfn "$APPS/RoteirizaIA.app" "$HOME/Desktop/RoteirizaIA"
ok "App em ~/Applications/RoteirizaIA (atalho na Mesa)"

print -P "\n%B%F{green}Pronto!%f%b Abra o %BRoteirizaIA%b pela Mesa."
print "Na primeira vez, cole a sua chave do Gemini na caixa ⚙ Gemini (crie em aistudio.google.com/apikey)."
[[ -z "$ROTEIRIZAIA_DEST" ]] && open "$APPS/RoteirizaIA.app"
[[ -z "$ROTEIRIZAIA_DEST" ]] && read -k1 "?Aperte qualquer tecla para fechar."
