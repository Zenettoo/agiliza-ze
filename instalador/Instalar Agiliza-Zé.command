#!/bin/zsh
# Instalador do Agiliza-Zé — dê dois cliques (na primeira vez: botão direito › Abrir).
cd "$(dirname "$0")"
ORIGEM="$PWD/app"
DEST="$HOME/Documents/Agiliza-Ze"
PLUGINS="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins"
ok(){ print -P "%F{green}✓%f $1"; }
passo(){ print -P "\n%F{magenta}▸ $1%f"; }
erro(){ print -P "\n%F{red}✗ $1%f"; read -k1 "?Aperte qualquer tecla para fechar."; exit 1; }

clear
print -P "%B%F{magenta}Agiliza-Zé%f%b — instalador"
print "Organizador de momentos · sincronia · áudio · transcrição · ganchos e roteiro, dentro do DaVinci Resolve.\n"

passo "Conferindo o Mac"
[[ "$(uname -m)" == "arm64" ]] || erro "O Agiliza-Zé precisa de um Mac com chip Apple (M1, M2, M3, M4…)."
ok "Mac com chip Apple"
APP_RESOLVE="/Applications/DaVinci Resolve/DaVinci Resolve.app"
[[ -d "$APP_RESOLVE" ]] || erro "Não encontrei o DaVinci Resolve em /Applications. Instale o DaVinci Resolve Studio e rode de novo."
if /usr/libexec/PlistBuddy -c "Print CFBundleName" "$APP_RESOLVE/Contents/Info.plist" 2>/dev/null | grep -qi studio || \
   [[ -d "/Applications/DaVinci Resolve/DaVinci Resolve Studio.app" ]] || ls "$APP_RESOLVE/Contents/Libraries" 2>/dev/null | grep -qi studio; then
  ok "DaVinci Resolve encontrado"
else
  ok "DaVinci Resolve encontrado (o plugin exige a versão Studio)"
fi
LIVRE=$(df -g "$HOME" | awk 'NR==2{print $4}')
(( LIVRE >= 5 )) || erro "Pouco espaço livre (${LIVRE} GB). Libere pelo menos 5 GB e rode de novo."

passo "Copiando o Agiliza-Zé para Documentos/Agiliza-Ze"
mkdir -p "$DEST/projetos" || erro "Não consegui criar $DEST"
rsync -a "$ORIGEM/" "$DEST/" --exclude projetos || erro "Falha ao copiar os arquivos."
chmod +x "$DEST"/decupar "$DEST"/de_davinci "$DEST"/abrir "$DEST"/limpar "$DEST"/instalar_plugin 2>/dev/null
ok "Arquivos copiados (seus projetos, se houver, foram mantidos)"

passo "Instalando o Python e as bibliotecas (alguns minutos na primeira vez)"
if [[ ! -x "$DEST/.bin/uv" ]]; then
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$DEST/.bin" UV_NO_MODIFY_PATH=1 sh >/dev/null 2>&1 || erro "Falha ao baixar o instalador do Python (uv). Confira a internet."
fi
[[ -x "$DEST/.venv/bin/python" ]] || "$DEST/.bin/uv" venv --python 3.12 "$DEST/.venv" >/dev/null 2>&1 || erro "Falha ao criar o ambiente Python."
"$DEST/.bin/uv" pip install --python "$DEST/.venv/bin/python" mlx-whisper imageio-ffmpeg numpy pillow yt-dlp deno librosa >/dev/null 2>&1 || erro "Falha ao instalar as bibliotecas."
FF=$("$DEST/.venv/bin/python" -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())") && ln -sf "$FF" "$DEST/.venv/bin/ffmpeg"
"$DEST/.bin/uv" cache clean >/dev/null 2>&1
ok "Python, Whisper e ffmpeg prontos"

passo "Baixando o modelo de transcrição (~1,6 GB, só na primeira vez)"
HF_HOME="$DEST/.modelos" "$DEST/.venv/bin/python" -c "from huggingface_hub import snapshot_download; snapshot_download('mlx-community/whisper-large-v3-turbo')" >/dev/null 2>&1 \
  || erro "Falha ao baixar o modelo. Confira a internet e rode de novo."
ok "Modelo de transcrição pronto"

passo "Instalando o plugin no DaVinci (vai pedir a senha do Mac)"
sudo mkdir -p "$PLUGINS" && sudo rm -rf "$PLUGINS/com.agilizaze.resolve" "$PLUGINS/com.decupagem.resolve" && \
sudo cp -R "$DEST/plugin/com.agilizaze.resolve" "$PLUGINS/com.agilizaze.resolve" || erro "Falha ao instalar o plugin."
ok "Plugin instalado"

if [[ -f "$ORIGEM/skill/SKILL.md" ]]; then
  mkdir -p "$HOME/.claude/skills/decupar-casamento" && cp "$ORIGEM/skill/SKILL.md" "$HOME/.claude/skills/decupar-casamento/SKILL.md"
  ok "Atalhos do chat do Claude instalados (\"faz um script desse projeto\")"
fi

passo "Claude Code (usado no Organizador de Momentos e na Análise)"
if [[ ! -x "$HOME/.local/bin/claude" ]]; then
  read -q "R?Instalar o Claude Code agora? Precisa de uma assinatura do Claude. [s/N] " ; print
  if [[ "$R" == "s" ]]; then
    curl -fsSL https://claude.ai/install.sh | bash >/dev/null 2>&1 && ok "Claude Code instalado" || print "⚠︎ Não consegui instalar o Claude Code agora; as etapas 1 e 4 vão pedir isso depois."
  fi
fi
if [[ -x "$HOME/.local/bin/claude" ]]; then
  if "$HOME/.local/bin/claude" auth status 2>/dev/null | grep -q '"loggedIn": true'; then
    ok "Claude Code já está logado"
  else
    print "Vou abrir o login do Claude no navegador. Entre com a sua conta e cole o código aqui quando pedir."
    "$HOME/.local/bin/claude" auth login
  fi
fi

print -P "\n%B%F{green}Pronto!%f%b Abra (ou reabra) o DaVinci Resolve Studio e vá em:"
print -P "%BWorkspace › Workflow Integrations › Agiliza-Zé%b\n"
read -k1 "?Aperte qualquer tecla para fechar."
