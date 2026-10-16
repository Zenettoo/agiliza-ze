// Plugin "Agiliza-Zé" para o DaVinci Resolve Studio (Workspace > Workflow Integrations > Agiliza-Zé).
// Abre a interface da decupagem numa janela do DaVinci. O servidor local (~/Documents/Agiliza-Ze/servidor.py)
// é quem conversa com o Resolve; aqui só garantimos que ele está rodando e mostramos a página.
const { app, BrowserWindow, shell, ipcMain, nativeImage } = require('electron');
const { spawn } = require('child_process');
const http = require('http');
const path = require('path');
const os = require('os');
const fs = require('fs');

const BASE = path.join(os.homedir(), 'Documents', 'Agiliza-Ze');
const PORTA = 8792;
const URL_BASE = `http://localhost:${PORTA}/`;

function servidorNoAr() {
    return new Promise((ok) => {
        const req = http.get(URL_BASE + 'api/status', (res) => { res.resume(); ok(res.statusCode === 200); });
        req.on('error', () => ok(false));
        req.setTimeout(1500, () => { req.destroy(); ok(false); });
    });
}

async function garantirServidor() {
    if (await servidorNoAr()) return true;
    const py = path.join(BASE, '.venv', 'bin', 'python');
    if (!fs.existsSync(py)) return false;
    const filho = spawn(py, [path.join(BASE, 'servidor.py')], { cwd: BASE, detached: true, stdio: 'ignore' });
    filho.unref();
    for (let i = 0; i < 40; i++) {
        await new Promise((r) => setTimeout(r, 250));
        if (await servidorNoAr()) return true;
    }
    return false;
}

function paginaErro() {
    const html = `<html><body style="background:#0d0e11;color:#eceef3;font:15px -apple-system,sans-serif;padding:40px">
      <h2>Agiliza-Zé não encontrado</h2>
      <p>Não consegui iniciar a ferramenta em <code>${BASE}</code>.</p>
      <p>Rode o instalador do Agiliza-Zé de novo e abra esta janela de novo.</p></body></html>`;
    return 'data:text/html;charset=utf-8,' + encodeURIComponent(html);
}

async function criarJanela() {
    const janela = new BrowserWindow({
        width: 1360, height: 920, minWidth: 720, minHeight: 500,
        title: 'Agiliza-Zé', backgroundColor: '#0d0e11', icon: path.join(__dirname, 'logo.png'),
        webPreferences: { contextIsolation: true, sandbox: true, nodeIntegration: false,
                         preload: path.join(__dirname, 'preload.js') }
    });
    janela.setMenu(null);
    janela.on('close', () => app.quit());
    // links para fora (não-localhost) abrem no navegador do sistema
    janela.webContents.setWindowOpenHandler(({ url }) => {
        if (!url.startsWith(URL_BASE)) { shell.openExternal(url); return { action: 'deny' }; }
        return { action: 'allow' };
    });
    // cortes baixados vão para Downloads
    janela.webContents.session.on('will-download', (_e, item) => {
        item.setSavePath(path.join(os.homedir(), 'Downloads', item.getFilename()));
    });
    const ok = await garantirServidor();
    janela.loadURL(ok ? URL_BASE : paginaErro());
}

// arrastar um download da lista para fora da janela (ex.: para dentro do DaVinci)
// a pasta de downloads é a escolhida na aba (guardada em projetos/_config_downloads.json)
function pastaDownloads() {
    try {
        const destino = JSON.parse(fs.readFileSync(path.join(BASE, 'projetos', '_config_downloads.json'), 'utf8')).destino;
        if (destino && fs.statSync(destino).isDirectory()) return destino;
    } catch (_) { /* sem configuração: usa a padrão */ }
    return path.join(BASE, 'projetos', '_downloads');
}
ipcMain.on('arrastar', (e, nome) => {
    const pasta = pastaDownloads();
    const arq = path.resolve(pasta, String(nome));
    if (!arq.startsWith(pasta + path.sep) || !fs.existsSync(arq)) return;
    e.sender.startDrag({ file: arq, icon: nativeImage.createFromPath(path.join(__dirname, 'icone.png')) });
    e.sender.send('arrastou');  // o arrasto terminou (soltou ou cancelou)
});

app.whenReady().then(criarJanela);
app.on('window-all-closed', () => app.quit());
