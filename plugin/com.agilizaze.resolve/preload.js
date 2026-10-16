// Ponte mínima entre a página e o plugin: só deixa a página iniciar arrastar de um arquivo baixado.
const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('agilizaZe', {
    arrastar: (nome) => ipcRenderer.send('arrastar', nome),
    onArrastou: (cb) => ipcRenderer.on('arrastou', () => cb())
});
