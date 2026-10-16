"""Tela inicial: lista os projetos decupados (usada pelo navegador e pelo plugin do DaVinci)."""
import datetime
import html as h
import json
from pathlib import Path

CSS = """
:root{--bg:#1f2326;--panel:#262b2f;--line:#3b4248;--ink:#f2f2e6;--mute:#9ca3a8;--accent:#dfe47a;--accent-ink:#1f2326;--red:#e4493a;--chip:#2e3439}
@media (prefers-color-scheme:light){:root{--bg:#f1f1ea;--panel:#fff;--line:#dedfd4;--ink:#1f2326;--mute:#6b7177;--accent:#d3da4a;--accent-ink:#1f2326;--red:#d13c2e;--chip:#ebebe2}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,BlinkMacSystemFont,"SF Pro Text",sans-serif;-webkit-font-smoothing:antialiased;background:radial-gradient(1000px 520px at 50% -12%,rgba(255,255,255,.035),transparent 70%),linear-gradient(180deg,#15171a 0%,#0f1113 100%);background-attachment:fixed;min-height:100vh;background-image:linear-gradient(rgba(255,255,255,.028) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.028) 1px,transparent 1px);background-size:44px 44px;background-attachment:fixed}
body::before{content:'';position:fixed;inset:0;pointer-events:none;opacity:.05;z-index:0;background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>")}
main,section,header,nav,.dl,.hist{position:relative;z-index:1}
.hero{position:relative;overflow:hidden;padding:36px 24px 22px;border-bottom:1px solid var(--line);
 background:radial-gradient(800px 260px at 8% -40%,rgba(139,123,255,.28),transparent 70%),radial-gradient(600px 220px at 95% -30%,rgba(90,209,232,.16),transparent 70%)}
.in{max-width:1100px;margin:0 auto}
.eyebrow{font:700 11px -apple-system,sans-serif;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}
.logo-topo{display:block;width:72px;height:72px;border-radius:18px;margin:0 0 12px;box-shadow:0 10px 26px -10px rgba(0,0,0,.6)}
.marca-foto{position:absolute;right:max(24px,calc(50% - 540px));top:20px;width:150px;height:200px;object-fit:cover;object-position:50% 20%;border-radius:18px;border:1px solid var(--line);box-shadow:0 10px 30px rgba(0,0,0,.35)}
@media (max-width:700px){.marca-foto{display:none}}
h1{font:800 34px/1.05 Archivo,-apple-system,"SF Pro Display",sans-serif;font-stretch:125%;letter-spacing:-.01em;margin:8px 0 4px}
.sub{color:var(--mute)}
.grid{max-width:1100px;margin:22px auto;padding:0 24px 40px;display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.proj{display:flex;flex-direction:column;gap:10px;background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:18px;
 color:inherit;text-decoration:none;transition:.15s}
.proj{position:relative}.proj:hover{border-color:var(--accent);transform:translateY(-2px)}
.acoes{position:absolute;right:12px;top:12px;display:flex;gap:6px;opacity:0;transition:.15s}.proj:hover .acoes{opacity:1}
.redo{border:1px solid var(--line);background:var(--panel);color:var(--mute);border-radius:8px;padding:3px 9px;font:600 12px -apple-system,sans-serif;cursor:pointer}
.redo:hover{border-color:var(--accent);color:var(--accent)}
.montar{border:1px solid var(--accent);background:var(--accent);color:#111;border-radius:8px;padding:3px 9px;font:700 12px -apple-system,sans-serif;cursor:pointer}
.montar:disabled{opacity:.5;cursor:default}
.del{border:1px solid var(--line);background:var(--panel);color:var(--mute);border-radius:8px;
 padding:3px 9px;font:600 12px -apple-system,sans-serif;cursor:pointer;transition:.15s}.del:hover,.del.sure{border-color:#ff8552;color:#ff8552;opacity:1}
.proj h2{margin:0;font:700 17px/1.3 -apple-system,"SF Pro Display",sans-serif;letter-spacing:-.01em}
.meta{display:flex;gap:6px;flex-wrap:wrap}.meta span{background:var(--chip);border-radius:999px;padding:2px 10px;font-size:12px;color:var(--mute)}
q{color:var(--mute);font-size:14px;line-height:1.5}
.hist{position:fixed;left:0;right:0;bottom:0;z-index:20;border-top:1px solid var(--line);background:color-mix(in srgb,var(--panel) 94%,transparent);
 backdrop-filter:blur(14px);box-shadow:0 -10px 30px rgba(0,0,0,.25)}
.hist .h-top,.hist #jobs{max-width:1100px;margin:0 auto}#jobs{max-height:45vh;overflow:auto}
body{padding-bottom:56px}
.h-top{display:flex;align-items:center;gap:10px;padding:9px 14px;cursor:pointer;user-select:none;font-size:13px;color:var(--mute)}
.h-top b{color:var(--ink);font-weight:600}.h-top .seta{transition:.2s;font-size:11px}.hist.aberto .seta{transform:rotate(90deg)}
.h-top .mini{flex:1;height:3px;border-radius:3px;background:var(--line);overflow:hidden;max-width:160px}
.h-top .mini i{display:block;height:100%;background:var(--accent);transition:width .6s}
.h-top .limpar{margin-left:auto;border:0;background:transparent;color:var(--mute);font:600 12px -apple-system,sans-serif;cursor:pointer;padding:2px 6px;border-radius:6px}
.h-top .limpar:hover{color:var(--ink);background:var(--chip)}
#jobs{display:none;border-top:1px solid var(--line)}.hist.aberto #jobs{display:block}
.job{display:grid;grid-template-columns:10px minmax(0,1fr) 110px auto;gap:10px;align-items:center;padding:8px 14px;font-size:13px;border-top:1px solid var(--line)}
.job:first-child{border-top:0}.job .pt{width:8px;height:8px;border-radius:50%;background:var(--accent)}
.job.ok .pt{background:#3ddc97}.job.erro .pt{background:#ff8552}.job.rodando .pt{animation:pulsa 1.2s infinite}
@keyframes pulsa{50%{opacity:.3}}
.job .nm{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.job .nm small{color:var(--mute);margin-left:6px}
.job .bar{height:3px;border-radius:3px;background:var(--line);overflow:hidden}.job .bar i{display:block;height:100%;background:var(--accent)}
.job a,.job button{font:600 12px -apple-system,sans-serif;color:var(--accent);text-decoration:none;border:0;background:transparent;cursor:pointer;white-space:nowrap}
.job .cancel{color:var(--mute)}.job .cancel:hover{color:#ff8552}
.vazio{grid-column:1/-1;color:var(--mute);padding:48px 0;text-align:center}
.nova{max-width:1100px;margin:22px auto 0;padding:0 24px}
.box{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:20px}
.box h2{margin:0 0 4px;font:700 18px -apple-system,"SF Pro Display",sans-serif}
.campos{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px;margin-top:14px}
label{display:flex;flex-direction:column;gap:5px;font-size:12px;font-weight:600;color:var(--mute);text-transform:uppercase;letter-spacing:.06em}
input,select,textarea{font:inherit;font-size:14px;text-transform:none;letter-spacing:0;color:var(--ink);background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:9px 11px;outline:none}
input:focus,select:focus,textarea:focus{border-color:var(--accent)}
.ditar{display:flex;gap:8px;align-items:flex-start}.ditar textarea{flex:1}
.mic{width:42px;height:42px;border-radius:50%;border:1px solid var(--line);background:var(--bg);cursor:pointer;font-size:18px;flex:none}
.mic.gravando{background:#c62828;border-color:#c62828;color:#fff;animation:pulso 1s infinite}
@keyframes pulso{50%{opacity:.55}}
textarea{min-height:60px;resize:vertical}.full{grid-column:1/-1}
.tls{display:flex;flex-wrap:wrap;gap:6px}.tls label{flex-direction:row;align-items:center;gap:6px;background:var(--chip);border-radius:999px;padding:4px 10px;text-transform:none;letter-spacing:0;font-weight:500;font-size:13px;color:var(--ink)}
.go{margin-top:14px;display:flex;gap:12px;align-items:center}
.btn{border:0;background:var(--accent);color:var(--accent-ink);border-radius:12px;padding:11px 20px;font:700 14px -apple-system,sans-serif;cursor:pointer}
.btn{box-shadow:0 8px 22px -10px rgba(223,228,122,.6);transition:transform .15s ease,filter .15s ease}
.btn:hover{transform:translateY(-1px);filter:brightness(1.05)}
.box,.proj,.dl-card,.dl-player,.cfg{background:rgba(38,43,47,.82);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);box-shadow:0 1px 0 rgba(255,255,255,.04) inset,0 18px 40px -22px rgba(0,0,0,.6)}
.btn:disabled{opacity:.5;cursor:not-allowed}
.cores{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}.cor{display:inline-flex;align-items:center;gap:6px;background:var(--chip);border-radius:999px;padding:3px 10px;font-size:12px}
.cor i{width:9px;height:9px;border-radius:3px;display:inline-block}.btn.ter{background:transparent;color:var(--mute);box-shadow:0 0 0 1px var(--line) inset}
.chk .linha{display:flex;align-items:center;gap:8px;text-transform:none;letter-spacing:0;font-weight:500;font-size:14px;color:var(--ink);padding:9px 0}.btn.sec{background:transparent;color:var(--accent);box-shadow:0 0 0 1.5px var(--accent) inset}
"""


HIST = """<div class="hist" id="hist" style="display:none"><div class="h-top" id="h-top"><span class="seta">▶</span><span id="h-txt"></span>
<span class="mini"><i id="h-bar"></i></span><button class="limpar" id="h-limpar" title="Esconde os concluídos">Limpar</button></div>
<div id="jobs"></div></div>"""

FORM = """<section class="nova"><div class="box"><h2>1 · Organizador de Momentos</h2>
<div class="sub">Com as brutas no media pool (<b>uma pasta por câmera</b>), eu olho um quadro de cada clipe, identifico os momentos do tipo de trabalho
e crio uma timeline por momento — 1080p · 24 fps · Rec.709 (Scene) — com a câmera A, depois B, depois C…, cada momento na sua cor.
<b>Identificar no media pool</b> só pinta os clipes e grava o momento nas Keywords (dá para filtrar), sem criar timelines.
As timelines vão para a pasta MOMENTOS.</div>
<div class="campos"><label>Tipo de trabalho<select id="p-tipo"></select></label>
<label class="full" id="l-mom" style="display:none">Momentos (separe por vírgula)<input id="p-mom" placeholder="Ex.: Chegada, Abertura, Palestra, Painel, Encerramento"></label></div>
<div class="cores" id="p-cores"></div>
<div class="go"><button class="btn" id="p-ir">▣ Organizar momentos</button><button class="btn ter" id="p-unica" title="Organiza tudo numa timeline só, na ordem dos momentos (os takes já organizados ficam como estão)">▤ Organizar em uma timeline</button><button class="btn ter" id="p-atualizar" title="Organiza só os takes novos; os que já estão nas timelines de momento ficam como estão">↻ Atualizar</button><button class="btn ter" id="p-teste" title="Pinta os clipes e grava o momento nas Keywords, sem criar timelines">Identificar no media pool</button>
<span class="sub" id="p-msg"></span></div></div>
<div class="box sync" style="margin-top:14px"><h2>2 · Sincronizar</h2>
<div class="sub">Coloque os clipes brutos na timeline (uma faixa por câmera) e o gravador/lapela numa faixa de áudio.
Os clipes fora de sincronia são reposicionados <b>na própria timeline</b> pela forma de onda. Um backup é salvo antes.</div>
<div class="campos"><label>Áudio de referência / voz (usado em sincronizar, áudio e análise)<select id="s-ref"></select></label></div>
<div class="go"><button class="btn sec" id="s-ir">⇄ Sincronizar esta timeline</button><button class="btn sec" id="m-ir" title="Cria um multicam com as faixas de vídeo desta timeline e uma timeline nova com ele">▦ Criar multicam + timeline</button><span class="sub" id="s-msg"></span></div></div>
</section>"""

JS = r"""<script>
const $=id=>document.getElementById(id);let INFO=null;
async function info(){try{const d=await (await fetch('/api/resolve_info')).json();if(!d.ok)throw d.msg;INFO=d;
 $('dv').innerHTML='Projeto aberto: <b>'+d.projeto+'</b>'+(d.atual?' · timeline: <b>'+d.atual+'</b>':'');
 if(!$('f-nome').dataset.mexeu)$('f-nome').value=d.projeto+(d.atual?' - '+d.atual:'');
 $('f-modo').options[0].textContent='Esta timeline: '+(d.atual||'(nenhuma aberta)');
 $('f-cor').innerHTML=Object.entries(d.cores).map(([c,n])=>'<option value="'+c+'">'+c+' ('+n+' clipes)</option>').join('')||'<option value="">nenhuma cor na timeline</option>';
 const ant=$('s-ref').value;$('s-ref').innerHTML='<option value="">Automático (faixa mais longa)</option>'+(d.faixas||[]).map(f=>
  '<option value="'+f.n+'">A'+f.n+' · '+f.nome+' — '+f.clipes+' clipe(s), '+Math.round(f.dur/60)+' min</option>').join('');$('s-ref').value=ant;
 $('f-tls').innerHTML=d.timelines.map(t=>'<label><input type="checkbox" value="'+t.replace(/"/g,'&quot;')+'">'+t+'</label>').join('');
}catch(e){$('dv').textContent='DaVinci não encontrado — abra o DaVinci com o projeto.';}}
$('f-nome').oninput=()=>{$('f-nome').dataset.mexeu=1};
$('f-modo').onchange=()=>{const m=$('f-modo').value;$('l-cor').style.display=m==='cor'?'':'none';$('l-tls').style.display=m==='timelines'?'':'none';};
let gravador=null,pedacos=[];
$('f-mic').onclick=async()=>{const b=$('f-mic'),msg=$('f-mic-msg');
 if(gravador&&gravador.state==='recording'){gravador.stop();return;}
 if(!navigator.mediaDevices||!window.MediaRecorder){msg.textContent='Este navegador não permite gravar áudio.';return;}
 let fluxo;try{fluxo=await navigator.mediaDevices.getUserMedia({audio:true});}catch(e){msg.textContent='Permita o uso do microfone para gravar.';return;}
 pedacos=[];gravador=new MediaRecorder(fluxo);
 gravador.ondataavailable=e=>{if(e.data.size)pedacos.push(e.data);};
 gravador.onstop=async()=>{fluxo.getTracks().forEach(t=>t.stop());b.classList.remove('gravando');
  const blob=new Blob(pedacos,{type:gravador.mimeType||'audio/webm'});
  msg.textContent='Transcrevendo…';b.disabled=true;
  try{const d=await (await fetch('/api/transcrever_pedido',{method:'POST',body:blob})).json();
   if(d.ok){const o=$('f-obs');o.value=(o.value?o.value.trim()+' ':'')+d.texto;msg.textContent='Texto colocado no pedido. Revise e clique em Analisar.';}
   else msg.textContent='⚠︎ '+d.msg;}
  catch(e){msg.textContent='Falha ao enviar o áudio.';}
  b.disabled=false;};
 gravador.start();b.classList.add('gravando');msg.textContent='Gravando… clique de novo para parar.';};
$('f-ir').onclick=async()=>{const m=$('f-modo').value;let alvo='';
 if(m==='cor')alvo=$('f-cor').value;
 if(m==='timelines')alvo=[...document.querySelectorAll('#f-tls input:checked')].map(x=>x.value).join(',');
 if(m==='timelines'&&!alvo){$('f-msg').textContent='Escolha ao menos uma timeline.';return;}
 $('f-ir').disabled=true;$('f-msg').textContent='Iniciando…';
 const d=await (await fetch('/api/analisar',{method:'POST',body:JSON.stringify({modo:m,alvo,nome:$('f-nome').value,
  prompt:$('f-prompt').value,duracao:$('f-dur').value,obs:$('f-obs').value,faixa:$('s-ref').value,tipo:$('p-tipo').value})})).json();
 $('f-msg').textContent=d.ok?'Análise iniciada — veja em Atividade.':'⚠︎ '+d.msg;$('f-ir').disabled=false;jobs();};
document.addEventListener('click',async e=>{const b=e.target.closest('.cancel');if(!b)return;
 if(!confirmar(b))return;b.disabled=true;b.textContent='Cancelando…';
 await fetch('/api/cancelar',{method:'POST',body:JSON.stringify({projeto:b.dataset.p})});jobs();});
function confirmar(b){if(b.dataset.ok)return true;b.dataset.ok=1;b.textContent='Clique de novo para confirmar';
 setTimeout(()=>{if(!b.disabled){delete b.dataset.ok;b.textContent='✕ Cancelar';}},4000);return false;}
document.addEventListener('click',async e=>{const b=e.target.closest('.del');if(!b)return;e.preventDefault();e.stopPropagation();
 if(!b.dataset.ok){b.dataset.ok=1;b.textContent='Confirmar?';b.classList.add('sure');
  setTimeout(()=>{delete b.dataset.ok;b.textContent='🗑 Apagar';b.classList.remove('sure');},4000);return;}
 b.textContent='Apagando…';const d=await (await fetch('/api/apagar',{method:'POST',body:JSON.stringify({projeto:b.dataset.p})})).json();
 if(d.ok){const c=b.closest('.proj');c.style.opacity=0;setTimeout(()=>c.remove(),250);}else{b.textContent='⚠︎ '+d.msg;}});
$('m-ir').onclick=async()=>{$('m-ir').disabled=true;$('s-msg').textContent='Iniciando…';
 const d=await (await fetch('/api/multicam',{method:'POST',body:JSON.stringify({})})).json();
 $('s-msg').textContent=d.ok?'Criando o multicam — veja em Atividade.':'⚠︎ '+d.msg;$('m-ir').disabled=false;jobs();};
$('s-ir').onclick=async()=>{$('s-ir').disabled=true;$('s-msg').textContent='Iniciando…';
 const d=await (await fetch('/api/sincronizar',{method:'POST',body:JSON.stringify({ref:$('s-ref').value})})).json();
 $('s-msg').textContent=d.ok?'Sincronizando — veja em Atividade.':'⚠︎ '+d.msg;$('s-ir').disabled=false;jobs();};
document.addEventListener('click',async e=>{const b=e.target.closest('.montar');if(!b)return;e.preventDefault();e.stopPropagation();
 b.disabled=true;b.textContent='Montando…';
 try{const d=await (await fetch('/api/montar_roteiro',{method:'POST',body:JSON.stringify({projeto:b.dataset.p,modo:'cortes'})})).json();
  b.textContent=d.ok?'✓ Montado no DaVinci':'⚠︎ '+d.msg;}catch(err){b.textContent='⚠︎ Sem resposta do app';}
 b.disabled=false;})
document.addEventListener('click',async e=>{const b=e.target.closest('.redo');if(!b)return;e.preventDefault();e.stopPropagation();
 b.disabled=true;b.textContent='Iniciando…';
 const d=await (await fetch('/api/reanalisar',{method:'POST',body:JSON.stringify({projeto:b.dataset.p})})).json();
 b.textContent=d.ok?'↻ Refazendo…':'⚠︎ '+d.msg;jobs();window.scrollTo({top:0,behavior:'smooth'});});
async function audio(teste){$('a-ir').disabled=$('a-teste').disabled=true;$('a-msg').textContent='Iniciando…';
 const d=await (await fetch('/api/melhorar_audio',{method:'POST',body:JSON.stringify({ref:$('s-ref').value,alvo:-16,
  cameras:$('a-cam').checked,teste,isolamento:$('a-iso').value,silencios:teste?0:$('a-sil').value,prompt:$('f-prompt').value})})).json();
 $('a-msg').textContent=d.ok?(teste?'Medindo o áudio':'Melhorando o áudio')+' — veja em Atividade.':'⚠︎ '+d.msg;
 $('a-ir').disabled=$('a-teste').disabled=false;$('hist').classList.add('aberto');jobs();}
$('a-ir').onclick=()=>audio(false);$('a-teste').onclick=()=>audio(true);
async function predec(teste,unica=false){$('p-ir').disabled=$('p-teste').disabled=$('p-unica').disabled=true;$('p-msg').textContent='Iniciando…';
 const d=await (await fetch('/api/predecupar',{method:'POST',body:JSON.stringify({identificar:teste,unica:unica,tipo:$('p-tipo').value,momentos:$('p-mom').value})})).json();
 $('p-msg').textContent=d.ok?'Organizando — veja em Atividade (leva alguns minutos).':'⚠︎ '+d.msg;
 $('p-ir').disabled=$('p-teste').disabled=$('p-unica').disabled=false;$('hist').classList.add('aberto');jobs();}
$('p-ir').onclick=()=>predec(false);$('p-atualizar').onclick=()=>predec(false);$('p-unica').onclick=()=>predec(false,true);$('p-teste').onclick=()=>predec(true);
const HEX={Yellow:'#d9b526',Pink:'#e46fa6',Green:'#3e9a5c',Apricot:'#f2a766',Blue:'#4a90d9',Teal:'#2a9a9a',Orange:'#e8862a',
 Purple:'#8e5bc7',Lime:'#9fc63f',Violet:'#c55bc1',Olive:'#6f9a3a',Tan:'#b9a27c',Navy:'#3a5ba0',Brown:'#9b6a3e'};
$('p-tipo').innerHTML=Object.entries(TIPOS).map(([k,v])=>'<option value="'+k+'">'+v.nome+'</option>').join('')+'<option value="personalizado">Personalizado…</option>';
try{const t=localStorage.getItem('dec-tipo');if(t)$('p-tipo').value=t;}catch(e){}
function legenda(){const t=$('p-tipo').value;$('l-mom').style.display=t==='personalizado'?'':'none';
 const ms=t==='personalizado'?($('p-mom').value.split(',').map(x=>x.trim()).filter(Boolean).map((n,i)=>[n,['Yellow','Pink','Green','Apricot','Blue','Teal','Orange','Purple','Lime','Violet'][i%10]])
  .concat([['Drone','Navy'],['Revisar','Brown']])):TIPOS[t].momentos;
 $('p-cores').innerHTML=ms.map(([n,c])=>'<span class="cor"><i style="background:'+HEX[c]+'"></i>'+n+'</span>').join('');
 try{localStorage.setItem('dec-tipo',t)}catch(e){}}
$('p-tipo').onchange=legenda;$('p-mom').oninput=legenda;legenda();
let vistos={};
let escondidos={};try{escondidos=JSON.parse(localStorage.getItem('dec-esc')||'{}')}catch(e){}
try{if(localStorage.getItem('dec-hist')==='1')$('hist').classList.add('aberto')}catch(e){}
$('h-top').onclick=e=>{if(e.target.id==='h-limpar')return;$('hist').classList.toggle('aberto');
 try{localStorage.setItem('dec-hist',$('hist').classList.contains('aberto')?'1':'0')}catch(e){}};
let ultimos=[];
$('h-limpar').onclick=()=>{ultimos.filter(j=>j.fim).forEach(j=>escondidos[j.projeto+j.inicio]=1);
 try{localStorage.setItem('dec-esc',JSON.stringify(escondidos))}catch(e){};jobs();};
async function jobs(){try{const d=await (await fetch('/api/jobs')).json();
 const lista=d.jobs.filter(j=>!escondidos[j.projeto+j.inicio]);ultimos=lista;
 $('hist').style.display='';
 const rod=lista.filter(j=>!j.fim);
 $('h-txt').innerHTML='<b>Atividade</b> · '+(rod.length?'em andamento · '+rod[0].etapa.toLowerCase()+' '+rod[0].pct+'%':'nenhuma em andamento');
 $('h-bar').parentNode.style.setProperty('--p',rod.length?rod[0].pct:100);$('h-bar').parentNode.dataset.p=rod.length?rod[0].pct+'%':'';$('h-bar').parentNode.style.visibility=rod.length?'':'hidden';
 $('h-limpar').style.display='none';
 $('jobs').innerHTML=rod.slice(0,1).map(j=>{const cls=j.erro?'erro':(j.fim?'ok':'rodando');
  const min=Math.max(1,Math.round(((j.fim||Date.now()/1000)-j.inicio)/60));
  const acao=!j.fim?'<button class="cancel" data-p="'+j.projeto+'">✕ Cancelar</button>':
   (j.etapa==='Concluído'&&j.tipo!=='sync'?'<a href="/'+j.projeto+'/decupagem.html">Abrir →</a>':'');
  return '<div class="job '+cls+'" title="'+(j.msg||'').replace(/"/g,'&quot;')+'"><span class="pt"></span><span class="nm">'+j.nome+
   '<small>'+(j.erro?'erro: '+j.msg:j.etapa)+' · '+min+' min</small></span><span class="bar"><i style="width:'+j.pct+'%"></i></span>'+acao+'</div>';}).join('');
 d.jobs.forEach(j=>{if(j.tipo!=='sync'&&j.etapa==='Concluído'&&vistos[j.projeto]===false)location.reload();vistos[j.projeto]=j.etapa==='Concluído';});
}catch(e){}}
info();jobs();setInterval(jobs,3000);setInterval(info,5000);  // acompanha a timeline que você abrir
</script>"""


CSS_ABAS = """
.tabs{display:flex;gap:8px;padding:14px 24px 0;max-width:1200px;margin:0 auto}
.tab{border:1px solid var(--line);background:transparent;color:var(--mute);border-radius:999px;padding:8px 16px;font:600 13px -apple-system,sans-serif;cursor:pointer}
.tab.on{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}
[hidden]{display:none!important}
.dl{max-width:900px;margin:16px auto 0;padding:22px 26px 30px;min-height:62vh;display:flex;flex-direction:column;background:rgba(31,35,38,.42);backdrop-filter:blur(20px) saturate(150%);-webkit-backdrop-filter:blur(20px) saturate(150%);border:1px solid rgba(255,255,255,.14);border-radius:24px;box-shadow:0 30px 70px -25px rgba(0,0,0,.6),inset 0 1px 0 rgba(255,255,255,.1)}
.dl-top{display:flex;justify-content:flex-end;gap:6px}
.ic{border:0;background:transparent;color:var(--mute);width:36px;height:36px;border-radius:10px;cursor:pointer;font-size:17px;display:grid;place-items:center}
.ic:hover{color:var(--ink);background:var(--chip)}
.dl-vazio{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;gap:14px;padding:40px 0}
.dl-icone{width:104px;height:104px;border-radius:24px;background:rgba(223,228,122,.04);border:1px solid rgba(223,228,122,.35);box-shadow:0 0 28px -6px rgba(223,228,122,.45),inset 0 0 22px -10px rgba(223,228,122,.5);display:grid;place-items:center}
.dl-icone svg{width:62px;height:62px;filter:drop-shadow(0 0 4px rgba(223,228,122,.8)) drop-shadow(0 0 12px rgba(223,228,122,.5))}
.dl-titulo{font-weight:700;font-size:17px;margin-top:8px}
.dl-dica{color:var(--mute);font-size:14px}
.dl-entrada{display:flex;gap:8px;align-items:center;margin-top:18px;background:rgba(255,255,255,.07);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border:1px solid var(--line);border-radius:16px;padding:6px}
.dl-entrada input{flex:1;min-width:0;background:transparent;color:var(--ink);border:0;outline:0;padding:8px 10px;font:14px -apple-system,sans-serif}
.dl-entrada select{background:transparent;color:var(--mute);border:0;outline:0;font:13px -apple-system,sans-serif;cursor:pointer}
.dl-entrada .btn{padding:8px 16px}
.dl-msg{color:var(--mute);font-size:12px;margin-top:8px;text-align:center;min-height:16px}
#d-lista{margin-top:12px}
.dl-item{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px 6px;border-bottom:1px solid var(--line);cursor:grab}
.dl-item:hover .nm{color:var(--accent)}
.dl-dir{display:flex;gap:10px;align-items:center;flex-shrink:0}
.dl-btn{border:1px solid var(--line);background:var(--chip);color:var(--ink);border-radius:8px;padding:4px 10px;font:600 12px -apple-system,sans-serif;cursor:pointer}
.dl-pasta{display:flex;justify-content:center;align-items:center;gap:10px;margin-top:10px;color:var(--mute);font-size:12px;min-width:0}
#d-pasta-txt{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:70%}
.dl-nada{color:var(--mute);text-align:center;padding:24px 0;font-size:14px}
.dl-player{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:14px 16px;margin-top:14px}
.dl-ptop{display:flex;align-items:center;gap:12px;margin-bottom:12px}
.dl-ptop .dl-info{flex:1}
#p-dur{color:var(--mute);font-size:14px;font-variant-numeric:tabular-nums;flex-shrink:0}
.dl-onda{position:relative}
#p-cv{width:100%;height:96px;display:block;cursor:pointer;border-radius:8px}
.dl-ctl{display:flex;align-items:center;gap:12px;margin-top:10px}
#p-play{width:38px;height:38px;border-radius:50%;border:1px solid var(--line);background:var(--chip);color:var(--ink);cursor:pointer;font-size:14px;display:grid;place-items:center;flex-shrink:0}
#p-tempo{color:var(--mute);font-size:13px;font-variant-numeric:tabular-nums;flex:1}
#p-vol{width:110px}
.dl-item.sel{background:var(--chip)}
#p-cv{cursor:grab}
#p-vinci:disabled{opacity:.45;cursor:default}
.toast{position:fixed;left:50%;transform:translateX(-50%);bottom:64px;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px 16px;font:13px -apple-system,sans-serif;color:var(--ink);box-shadow:0 8px 24px rgba(0,0,0,.25);z-index:60;max-width:90vw;text-align:center}
.cfg-fundo{position:fixed;inset:0;background:rgba(0,0,0,.55);display:grid;place-items:center;z-index:50;padding:16px}
.cfg{background:var(--panel);border:1px solid var(--line);border-radius:16px;width:min(520px,100%);max-height:88vh;overflow:auto;padding:18px 20px}
.cfg-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
.cfg-top h2{margin:0;font-size:17px}
.cfg h3{font:700 11px -apple-system,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:var(--mute);margin:18px 0 8px}
.cfg-linha{display:flex;gap:8px;align-items:center}
.cfg-linha input,.cfg select{flex:1;min-width:0;background:var(--chip);color:var(--ink);border:1px solid var(--line);border-radius:10px;padding:9px 12px;font:14px -apple-system,sans-serif}
.cfg label.chk{display:flex;gap:10px;align-items:flex-start;font-size:14px;cursor:pointer;text-transform:none;letter-spacing:normal;font-weight:400;color:var(--ink)}
.cfg label.chk span{text-transform:none;letter-spacing:normal}
.cfg label.chk small{display:block;color:var(--mute);font-size:12px;margin-top:2px;text-transform:none;letter-spacing:normal;font-weight:400}
.cfg-cores{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.cfg-cores button{border:1px solid var(--line);background:var(--chip);color:var(--ink);border-radius:10px;padding:9px;font:600 13px -apple-system,sans-serif;cursor:pointer;display:flex;gap:8px;align-items:center;justify-content:center}
.cfg-cores button.on{border-color:var(--ink)}
.cfg-cores i{width:16px;height:16px;border-radius:4px;display:inline-block}
.cfg-acao{margin-top:8px}

.dl-card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:16px;margin-top:14px;display:flex;flex-direction:column;gap:16px}
.dl-linha{display:flex;align-items:center;gap:14px}
.dl-capa{width:128px;height:72px;border-radius:8px;overflow:hidden;background:var(--chip);flex-shrink:0}
.dl-capa img{width:100%;height:100%;object-fit:cover;display:block}
.dl-info{min-width:0;flex:1}
.dl-tit{font-weight:700;font-size:15px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.dl-can{color:var(--mute);font-size:13px;margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#d-dur{color:var(--mute);font-size:14px;font-variant-numeric:tabular-nums;flex-shrink:0}
.dl-acao{display:flex;gap:10px;align-items:center}
.seg{display:inline-flex;background:var(--chip);border-radius:12px;padding:3px;flex-shrink:0}
.seg button{border:0;background:transparent;color:var(--mute);padding:8px 16px;border-radius:9px;font:600 13px -apple-system,sans-serif;cursor:pointer}
.seg button.on{background:var(--panel);color:var(--ink)}
.dl-go{flex:1;display:flex;align-items:center;justify-content:center;gap:10px;background:var(--chip);color:var(--ink);border:1px solid var(--line);border-radius:12px;padding:11px;font:700 13px -apple-system,sans-serif;letter-spacing:.1em;cursor:pointer}
.dl-go:hover{border-color:var(--mute)}
.dl-quad{width:44px;height:44px;flex-shrink:0;border:1px solid var(--line);background:var(--chip);border-radius:12px;color:var(--ink);display:grid;place-items:center;cursor:pointer}
@media (max-width:560px){.dl-linha{align-items:flex-start}.dl-capa{width:96px;height:54px}}

/* estilo técnico: linhas finas, guias de centro, fonte mono em metadados */
.hero{overflow:hidden}
.eyebrow,#p-tempo,#p-dur,#d-pasta-txt,.dl-pasta span,.dl-dica,.sub small{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.02em}
.tab{background:rgba(255,255,255,.04);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,.16)}
.tab.on{border-color:var(--accent)}
.box,.proj,.dl-card,.dl-player,.cfg{border-color:rgba(255,255,255,.12)}

/* cards técnicos: cantos retos, marcas nos cantos, títulos mono */

.box,.proj,.dl-card,.dl-player,.cfg{border-radius:6px;position:relative;border-color:rgba(255,255,255,.14);background:rgba(24,27,30,.78)}
.box::before,.box::after,.dl-card::before,.dl-card::after,.dl-player::before,.dl-player::after{content:'';position:absolute;width:14px;height:14px;border:0;pointer-events:none}
.box::before,.dl-card::before,.dl-player::before{top:-1px;left:-1px;border-top:2px solid var(--accent);border-left:2px solid var(--accent)}
.box::after,.dl-card::after,.dl-player::after{bottom:-1px;right:-1px;border-bottom:2px solid var(--accent);border-right:2px solid var(--accent)}
.box h2,.dl-top h2{font:700 12px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}
.box h2{margin-bottom:6px}
.box h3,.cfg h3{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.1em}
.btn,.dl-go,.dl-btn,.seg button,.tab{border-radius:4px}
.tab{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase;letter-spacing:.06em;font-size:12px}
.dl-acao .seg{border-radius:4px}
.seg button{border-radius:3px}
.dl-capa,.dl-capa img{border-radius:4px}
.dl-entrada{border-radius:4px}
.dl-entrada input{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px}
.sub{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;letter-spacing:.02em}

/* topo só com a logo; barra lateral com o mesmo acabamento dos cards */
.hero{position:fixed;top:0;left:0;right:0;height:104px;margin:0;padding:0 24px;display:flex;align-items:center;background:rgba(14,16,18,.72);backdrop-filter:blur(18px) saturate(140%);-webkit-backdrop-filter:blur(18px) saturate(140%);border-bottom:1px solid rgba(255,255,255,.1);z-index:45;overflow:visible}
.hero .in{display:flex;align-items:center;min-height:0}
.logo-topo{margin:0 !important;width:56px;height:56px;border-radius:14px}
body{padding-top:104px;padding-left:212px}
.tabs{position:fixed;left:12px;top:116px;bottom:12px;width:188px;max-width:none;margin:0;padding:20px 12px;flex-direction:column;gap:6px;z-index:40;border-radius:6px;position:fixed;
 background:rgba(24,27,30,.78);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,.14);box-shadow:0 18px 40px -22px rgba(0,0,0,.6)}
.tabs::before,.tabs::after{content:'';position:absolute;width:14px;height:14px;pointer-events:none}
.tabs::before{top:-1px;left:-1px;border-top:2px solid var(--accent);border-left:2px solid var(--accent);border-top-left-radius:6px}
.tabs::after{bottom:-1px;right:-1px;border-bottom:2px solid var(--accent);border-right:2px solid var(--accent);border-bottom-right-radius:6px}
.tabs .tab{width:100%;text-align:left;padding:11px 12px;border-radius:4px;border:1px solid transparent;background:transparent;font:600 12px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.12em;text-transform:uppercase}
.tabs .tab:hover{border-color:rgba(255,255,255,.12);color:var(--ink)}
.tabs .tab.on{background:rgba(223,228,122,.08);color:var(--ink);border-color:rgba(223,228,122,.35);box-shadow:inset 3px 0 0 var(--accent),0 0 18px -8px rgba(223,228,122,.5)}
.hist{left:212px}
@media (max-width:760px){body{padding:0}.hero{position:static;height:auto;padding:16px}.tabs{position:static;width:auto;flex-direction:row;margin:12px 16px;border-radius:6px}.tabs::before,.tabs::after{display:none}.tabs .tab{width:auto}.hist{left:0}}

.rodape{margin:24px 0 0;padding:12px 24px 44px;text-align:center;font:12px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.06em;color:var(--mute);display:flex;justify-content:center;align-items:center;gap:10px;flex-wrap:wrap}
.rodape a{color:var(--ink);text-decoration:none;border-bottom:1px solid rgba(223,228,122,.35)}
.rodape a:hover{color:var(--accent)}
.rodape .ig{display:inline-grid;place-items:center;width:30px;height:30px;border:1px solid rgba(255,255,255,.16);border-radius:6px;color:var(--ink);border-bottom:1px solid rgba(255,255,255,.16)}
.rodape .ig:hover{border-color:var(--accent);color:var(--accent)}

/* atividade: pequena, no rodapé da barra lateral */
.hist{left:12px;right:auto;bottom:12px;width:188px;border:1px solid rgba(255,255,255,.14);border-radius:6px;background:rgba(24,27,30,.82);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);box-shadow:0 14px 30px -18px rgba(0,0,0,.7);border-top:1px solid rgba(255,255,255,.14)}
.hist .h-top{padding:7px 10px;font:500 11px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.04em;gap:8px}
.hist .h-top .mini{max-width:none;flex:1;height:2px}
.hist .h-top b{font-weight:600}
.hist .h-top .limpar{font-size:10px;padding:1px 4px}
.hist .h-top .seta{font-size:9px}
.hist .h-top,.hist #jobs{max-width:none;margin:0}
#jobs{position:absolute;left:0;bottom:calc(100% + 8px);width:340px;max-height:45vh;overflow:auto;background:rgba(24,27,30,.94);border:1px solid rgba(255,255,255,.14);border-radius:6px;box-shadow:0 18px 40px -18px rgba(0,0,0,.7)}
.tabs{bottom:66px}
@media (max-width:760px){.hist{left:12px;right:12px;width:auto}}

/* crédito fixo no rodapé da barra lateral, acima da atividade */
.rodape{position:fixed;left:12px;bottom:12px;width:188px;margin:0;padding:8px 10px;border:1px solid rgba(255,255,255,.14);border-radius:6px;background:rgba(24,27,30,.82);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);box-shadow:0 14px 30px -18px rgba(0,0,0,.7);z-index:30;justify-content:space-between;flex-wrap:nowrap;font-size:11px;letter-spacing:.03em;text-align:left;gap:8px}
.rodape .ig{width:26px;height:26px;flex-shrink:0}
.hist{bottom:60px}
.tabs{bottom:112px}
@media (max-width:760px){.rodape{position:static;width:auto;margin:16px;padding:12px}.hist{bottom:12px}}

/* lista de atividade dentro do widget da barra lateral (empilhada) */
#jobs{position:static;width:auto;max-height:40vh;overflow:auto;background:transparent;border:0;border-top:1px solid rgba(255,255,255,.1);border-radius:0;box-shadow:none}
.hist .job{display:flex;flex-wrap:wrap;align-items:center;gap:4px 8px;padding:7px 10px;font-size:11px;border-top:1px solid rgba(255,255,255,.08)}
.hist .job .pt{flex:0 0 auto}
.hist .job .nm{flex:1 1 0;min-width:0;white-space:normal;word-break:break-all;font-size:11px;line-height:1.35}
.hist .job .nm small{display:block;margin:2px 0 0;font-size:10px}
.hist .job .bar{flex:1 1 100%;order:5;width:100%;height:2px}
.hist .job a,.hist .job button{font-size:10px}

/* crédito de volta ao rodapé principal (fim da página); atividade fica na barra lateral */
.rodape{position:static;left:auto;bottom:auto;width:auto;margin:24px 0 0;padding:14px 24px 22px;border:0;border-radius:0;background:none;backdrop-filter:none;-webkit-backdrop-filter:none;box-shadow:none;justify-content:center;font-size:12px;text-align:center;gap:10px}
.rodape .ig{width:30px;height:30px}
.hist{bottom:12px}
.tabs{bottom:82px}

/* espaçamento do fim da página: menos vão entre o último card, o crédito e o fim da tela */
.grid{margin:22px auto 0;padding:0 24px 0}
.rodape{margin:6px 0 0;padding:6px 24px 14px}

/* barra lateral com a altura do conteúdo (não estica até o pé); widget de atividade opaco */
.tabs{bottom:auto;height:auto;align-self:flex-start}
.hist{background:rgba(22,25,28,.98);backdrop-filter:none;-webkit-backdrop-filter:none;bottom:12px}
.hist #jobs{background:rgba(22,25,28,.98);border-top:1px solid rgba(255,255,255,.1)}


/* rodapé colado no fim da página, sem espaço extra */
.rodape{margin:0;padding:0 24px 6px;line-height:1}
.grid{margin-bottom:0;padding-bottom:0}
#ta{margin:0;padding:0}
body{min-height:0}

/* crédito fixo no pé da tela (como a barra de progresso antes), ao lado do menu */
body{padding-bottom:40px}
.rodape{position:fixed;left:212px;right:0;bottom:0;margin:0;padding:8px 24px;line-height:1.2;z-index:25;justify-content:center;background:rgba(14,16,18,.78);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);border-top:1px solid rgba(255,255,255,.1);box-shadow:none;border-radius:0;font-size:11px;gap:10px}
.rodape .ig{width:24px;height:24px}
@media (max-width:760px){body{padding-bottom:0}.rodape{position:static;left:auto;right:auto;margin:16px;background:none;border:0;padding:0}}

/* ícone do Instagram flutuando no canto direito */
.rodape{backdrop-filter:none;-webkit-backdrop-filter:none;background:rgba(18,20,23,.94)}
.rodape .ig{position:fixed;right:20px;bottom:20px;width:48px;height:48px;border-radius:16px;background:rgba(24,27,30,.94);border:1px solid rgba(255,255,255,.16);box-shadow:0 12px 30px -10px rgba(0,0,0,.7);display:grid;place-items:center;z-index:40;color:var(--ink)}
.rodape .ig:hover{border-color:var(--accent);color:var(--accent);transform:translateY(-2px)}
.rodape .ig svg{width:22px;height:22px}
@media (max-width:760px){.rodape .ig{position:fixed;right:16px;bottom:16px}}

/* progresso (atividade) logo acima da faixa do crédito, alinhado ao conteúdo */
.hist{left:212px;right:auto;bottom:46px;width:300px}

/* ícone do Instagram um pouco mais alto */
.rodape .ig{bottom:64px}
@media (max-width:760px){.rodape .ig{bottom:16px}}

/* cards de vidro: menos opacos, com brilho e algo "atrás" (blur + saturação) */
.box,.proj,.dl-card,.dl-player,.cfg{background:rgba(30,34,38,.42);backdrop-filter:blur(20px) saturate(170%);-webkit-backdrop-filter:blur(20px) saturate(170%);border:1px solid rgba(255,255,255,.18);box-shadow:inset 0 1px 0 rgba(255,255,255,.14),inset 0 0 30px -18px rgba(223,228,122,.25),0 0 36px -10px rgba(223,228,122,.22),0 24px 50px -22px rgba(0,0,0,.65)}

/* progresso (atividade) travado no canto inferior esquerdo */
.hist{position:fixed;left:12px;right:auto;bottom:56px;width:188px}

/* progresso em roda (anel) no lugar da barra */
.hist .h-top .mini{flex:0 0 26px;width:26px;height:26px;max-width:none;border-radius:50%;background:conic-gradient(var(--accent) calc(var(--p,0) * 1%),rgba(255,255,255,.1) 0);position:relative;overflow:visible;margin:0 2px}
.hist .h-top .mini i{display:none}
.hist .h-top .mini::after{content:'';position:absolute;inset:4px;border-radius:50%;background:rgba(22,25,28,.98)}
.hist .h-top .mini::before{content:attr(data-p);position:absolute;inset:0;display:grid;place-items:center;font:600 7px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--ink);z-index:1}

/* rodapé ocupa a largura inteira da tela */
.rodape{position:fixed;left:0;right:0;bottom:0;width:auto;justify-content:center;padding:8px 24px}
@media (max-width:760px){.rodape{position:static}}

/* botão de atualizar a tela (recarrega sem fechar o plugin) */
.atualizar{margin-top:10px;width:100%;text-align:left;padding:8px 12px;border-radius:4px;border:1px dashed rgba(223,228,122,.45);background:transparent;color:var(--accent);font:600 11px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.1em;text-transform:uppercase;cursor:pointer}
.atualizar:hover{background:rgba(223,228,122,.08)}

/* botão de atualizar só com o ícone, no canto direito do topo */
.atualizar{display:none}
.atualizar-topo{position:absolute;right:24px;top:50%;transform:translateY(-50%);width:36px;height:36px;border-radius:10px;border:1px solid rgba(255,255,255,.16);background:rgba(24,27,30,.8);color:var(--ink);font-size:18px;line-height:1;cursor:pointer;display:grid;place-items:center;z-index:2}
.atualizar-topo:hover{border-color:var(--accent);color:var(--accent)}

/* barra lateral mais larga; o conteúdo começa com o mesmo espaço que existe entre os cards */
.tabs{width:260px}
body{padding-left:284px}
.hist{left:12px;width:260px}
.rodape{left:0}
@media (max-width:760px){body{padding-left:0}.hist{width:auto}}

/* barra lateral vai até quase encostar na atividade (com o mesmo espaço entre cards) */

/* a barra lateral acompanha a altura do widget de atividade (aberto ou fechado) */
:root{--hist-h:40px}
.tabs{bottom:auto;height:calc(100vh - var(--hist-h) - 184px)}

/* barras de rolagem e barras do tema escuro (sem branco) */
:root{color-scheme:dark}
*{scrollbar-width:thin;scrollbar-color:rgba(255,255,255,.18) transparent}
::-webkit-scrollbar{width:8px;height:8px;background:transparent}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,.18);border-radius:8px}
::-webkit-scrollbar-thumb:hover{background:rgba(223,228,122,.4)}
::-webkit-scrollbar-track{background:transparent}

/* controles de volume e marcações no tom do tema (sem azul/branco padrão) */
input[type=range]{accent-color:#dfe47a;background:transparent;height:18px;cursor:pointer}
input[type=checkbox]{accent-color:#dfe47a}
select{color-scheme:dark}

/* atividade: no máximo 2 itens visíveis, a barra fica sempre no lugar */
.hist #jobs{max-height:none;overflow:hidden}
.hist{min-height:42px}

/* aba Base (em branco por enquanto) */
.base{max-width:900px;margin:16px auto 0;padding:22px 26px 30px;min-height:62vh;display:flex;flex-direction:column;background:rgba(30,34,38,.42);backdrop-filter:blur(20px) saturate(170%);-webkit-backdrop-filter:blur(20px) saturate(170%);border:1px solid rgba(255,255,255,.18);border-radius:6px;box-shadow:inset 0 1px 0 rgba(255,255,255,.14),0 0 36px -10px rgba(223,228,122,.22),0 24px 50px -22px rgba(0,0,0,.65)}
.base-vazio{flex:1;display:grid;place-items:center;color:var(--mute);font:600 12px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.14em;text-transform:uppercase}

.base-titulo{font:700 12px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--accent);margin-bottom:14px}
.base-grade{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}
.modelo{position:relative;border:1px solid rgba(255,255,255,.14);border-radius:6px;padding:18px;background:rgba(24,27,30,.5);display:flex;flex-direction:column;gap:8px}
.modelo::before,.modelo::after{content:'';position:absolute;width:12px;height:12px}
.modelo::before{top:-1px;left:-1px;border-top:2px solid var(--accent);border-left:2px solid var(--accent)}
.modelo::after{bottom:-1px;right:-1px;border-bottom:2px solid var(--accent);border-right:2px solid var(--accent)}
.mol{width:100%;max-width:120px;height:auto;fill:none;stroke:var(--accent);stroke-width:1.6;margin:4px 0 6px}
.mol-v{max-width:70px;height:auto;margin:4px 0 6px}
.mol-t{font:700 15px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.04em}
.mol-s{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--mute)}
.modelo .btn{margin-top:auto;align-self:flex-start}

.nome-tl{width:100%;background:rgba(255,255,255,.04);color:var(--ink);border:1px solid rgba(255,255,255,.16);border-radius:4px;padding:8px 10px;font:13px ui-monospace,SFMono-Regular,Menlo,monospace;outline:0}
.nome-tl:focus{border-color:var(--accent)}
.nome-tl::placeholder{color:var(--mute);opacity:.7}

/* cards de modelo alinhados: mesma linha, mesma altura de miniatura */
.base-grade{grid-template-columns:repeat(3,minmax(0,1fr))}
.mol-box{height:96px;display:flex;align-items:center;justify-content:center;margin-bottom:6px}
.mol{width:auto;max-width:none;height:56px;margin:0}
.mol-v{width:auto;max-width:none;height:84px;margin:0}
.mol-box:has(.mol-v){height:96px}
@media (max-width:760px){.base-grade{grid-template-columns:1fr}}

/* ícones de modelo: visor técnico com brilho neon */
.mol{height:56px;width:auto;color:var(--accent);filter:drop-shadow(0 0 4px rgba(223,228,122,.7)) drop-shadow(0 0 14px rgba(223,228,122,.35))}
.mol-v{height:84px;width:auto}
.modelo:hover .mol{filter:drop-shadow(0 0 6px rgba(223,228,122,.9)) drop-shadow(0 0 20px rgba(223,228,122,.5))}

/* configurações do modelo organizadas em linhas rótulo/valor */
.mol-specs{margin:6px 0 4px;display:grid;gap:0}
.mol-specs div{display:flex;justify-content:space-between;align-items:baseline;gap:10px;padding:6px 0;border-top:1px solid rgba(255,255,255,.08);font:11px ui-monospace,SFMono-Regular,Menlo,monospace}
.mol-specs dt{color:var(--mute);letter-spacing:.06em;text-transform:uppercase}
.mol-specs dd{margin:0;color:var(--ink)}

/* menus de espaço de cor dentro de cada card */
.cor-sel{background:var(--chip);color:var(--ink);border:1px solid rgba(255,255,255,.14);border-radius:3px;padding:2px 6px;font:11px ui-monospace,SFMono-Regular,Menlo,monospace;cursor:pointer;max-width:150px}
.cor-sel:focus{outline:0;border-color:var(--accent)}
.mol-specs dd{display:flex;justify-content:flex-end}

/* cards com espaço suficiente para resolução e menus de cor */
.modelo{padding:14px}
.mol-specs div{gap:6px}
.mol-specs dt{font-size:10px;letter-spacing:.04em}
.mol-specs dd{min-width:0;margin:0}
.cor-sel{max-width:138px;width:138px;font-size:10px;padding:2px 4px}
.mol-specs div{flex-wrap:nowrap}

input.cor-sel::-webkit-calendar-picker-indicator{opacity:.7;cursor:pointer}

/* botão + e presets */
.modelo.mais{cursor:pointer;align-items:center;justify-content:center;text-align:center;border-style:dashed;border-color:rgba(223,228,122,.45);background:rgba(223,228,122,.03);min-height:260px}
.modelo.mais:hover{border-color:var(--accent);background:rgba(223,228,122,.07)}
.mais-sinal{font:300 56px/1 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--accent);text-shadow:0 0 18px rgba(223,228,122,.6);margin-bottom:10px}
.pr-campo{width:100%;background:var(--chip);color:var(--ink);border:1px solid rgba(255,255,255,.14);border-radius:4px;padding:8px 10px;font:13px ui-monospace,SFMono-Regular,Menlo,monospace;margin-top:4px}
#pr-w,#pr-h{width:45%}
#pr-form{max-width:460px}
#pr-form h3{margin-top:14px}
.cfg-linha .sub{padding:0 6px}

/* lixeira no canto superior direito do preset */
.pr-topo{display:flex;justify-content:space-between;align-items:center;gap:8px}
.pr-lixo{width:24px;height:24px;flex-shrink:0;display:grid;place-items:center;border:0;background:transparent;color:#e4493a;cursor:pointer;padding:0;filter:drop-shadow(0 0 4px rgba(228,73,58,.9)) drop-shadow(0 0 10px rgba(228,73,58,.5));transition:filter .15s ease,transform .15s ease}
.pr-lixo:hover{filter:drop-shadow(0 0 6px rgba(228,73,58,1)) drop-shadow(0 0 16px rgba(228,73,58,.8));transform:scale(1.08)}

/* modelos fixos na primeira linha; presets e o + numa linha menor embaixo */
.pr-linha{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin-top:14px;align-items:start}
.pr-linha .modelo{padding:10px;gap:5px;min-height:0}
.pr-linha .modelo::before,.pr-linha .modelo::after{width:9px;height:9px}
.pr-linha .mol-t{font-size:12px}
.pr-linha .mol-specs div{padding:3px 0;font-size:10px}
.pr-linha .mol-specs{margin:2px 0}
.pr-linha .nome-tl{font-size:11px;padding:5px 6px}
.pr-linha .btn{padding:6px 10px;font-size:11px}
.pr-linha .pr-lixo{width:22px;height:22px}
.pr-linha .modelo.mais{min-height:0;padding:10px;flex-direction:row;justify-content:center;align-items:center;gap:6px}
.pr-linha .modelo.mais .mol-s{display:none}
.pr-linha .mais-sinal{font-size:20px;margin:0}
.pr-linha .modelo.mais .mol-t{font-size:11px}

/* título centralizado; + Novo preset no canto inferior direito da linha */
.base-titulo{text-align:center}
.pr-linha{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end}
.pr-linha .preset{flex:0 0 200px}
.pr-linha #pr-abrir{margin-left:auto;margin-top:6px;flex:0 0 auto;width:auto}

/* nome do preset em uma linha e lixeirinha centralizada nela */
.pr-topo{align-items:center;min-height:30px}
.pr-topo .mol-t{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.3}
.pr-topo .pr-lixo{margin:0}

/* isolamento e silêncios lado a lado, em uma linha só */
.linha-campos{display:flex;flex-wrap:wrap;align-items:flex-end;gap:12px 16px;margin-top:12px}
.linha-campos label{flex:0 1 230px;font-size:11px;letter-spacing:.02em}
.linha-campos select{font-size:12px;padding:6px 8px}
.linha-campos label.chk{flex:0 1 260px;display:flex;flex-direction:column;gap:6px}
.linha-campos label.chk .linha{font-size:12px;color:var(--mute);text-transform:none;letter-spacing:0}

/* bloco de áudio no mesmo formato dos cards da guia */
.aud-grade{margin-top:14px}
.aud-campo select{width:100%;background:var(--chip);color:var(--ink);border:1px solid rgba(255,255,255,.14);border-radius:4px;padding:7px 9px;font:12px ui-monospace,SFMono-Regular,Menlo,monospace;margin-top:6px}
.aud-chk{display:flex;gap:8px;align-items:flex-start;font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--ink);margin-top:6px;line-height:1.4}
.aud-chk{text-transform:none;letter-spacing:0;font-weight:400}
.aud-chk input{accent-color:#dfe47a;margin-top:2px}
.aud-grade .mol{height:56px;width:auto;color:var(--accent);filter:drop-shadow(0 0 4px rgba(223,228,122,.7)) drop-shadow(0 0 14px rgba(223,228,122,.35))}
.aud-grade .modelo .mol-s{white-space:normal}

/* HackEdit: referências por projeto */
.hack-projeto{color:var(--mute);font:12px ui-monospace,SFMono-Regular,Menlo,monospace;text-align:center;margin:-6px 0 14px}
.hack-form{max-width:460px;margin:14px auto 0;display:grid;gap:8px}
.hack-ref{position:relative}
.hack-ref .hack-data{color:var(--mute);font:11px ui-monospace,SFMono-Regular,Menlo,monospace}
.hack-ref .hack-link{color:var(--accent);font:11px ui-monospace,SFMono-Regular,Menlo,monospace;word-break:break-all}
.hack-mais{cursor:pointer;align-items:center;justify-content:center;text-align:center;border-style:dashed;border-color:rgba(223,228,122,.45);background:rgba(223,228,122,.03);min-height:120px}

.hack-up{display:flex;flex-direction:column;gap:6px;font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--mute)}
.hack-up input[type=file]{color:var(--ink);font:12px ui-monospace,SFMono-Regular,Menlo,monospace}

.hack-acoes{display:flex;gap:8px;flex-wrap:wrap;margin-top:6px}
.hack-acoes .btn,.hack-acoes .dl-btn{padding:6px 10px;font-size:11px}

#hack-grade{grid-template-columns:repeat(auto-fill,minmax(380px,1fr))}
.hack-acoes{flex-wrap:nowrap}
.hack-acoes .btn,.hack-acoes .dl-btn{white-space:nowrap}

#tf .go{margin-top:12px;display:flex;gap:10px}
"""

BAIXAR = """<div class="dl" id="tb" hidden>
<div class="dl-top"><button class="ic" id="d-pasta" title="Abrir a pasta de downloads"><svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M3 6.5A1.5 1.5 0 0 1 4.5 5h4.2l2 2.2H19.5A1.5 1.5 0 0 1 21 8.7v8.8a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 17.5z" fill="currentColor"/></svg></button><button class="ic" id="d-config" title="Configurações" style="font-size:19px">⚙</button><button class="ic" id="d-atual" title="Atualizar">↻</button></div>
<div class="dl-entrada"><input id="d-url" placeholder="Cole o link do YouTube ou Instagram e aperte Enter" autocomplete="off"></div>
<div class="dl-vazio" id="d-vazio">
<div class="dl-icone"><svg viewBox="0 0 60 58" aria-hidden="true" fill="none" stroke="#dfe47a" stroke-width="2.4" stroke-linecap="round"><line x1="10" y1="15.0" x2="10" y2="43.0"/><line x1="18" y1="6.0" x2="18" y2="52.0"/><line x1="26" y1="11.0" x2="26" y2="47.0"/><line x1="34" y1="3.0" x2="34" y2="55.0"/><line x1="42" y1="9.0" x2="42" y2="49.0"/><line x1="50" y1="17.0" x2="50" y2="41.0"/></svg></div>
<div class="dl-titulo">Cole um link</div>
<div class="dl-dica">⌘ +V para começar</div></div>
<div class="dl-card" id="d-card" hidden>
<div class="dl-linha"><div class="dl-capa"><img id="d-img" alt="" referrerpolicy="no-referrer"></div><div class="dl-info"><div class="dl-tit" id="d-tit"></div><div class="dl-can" id="d-can"></div></div><span id="d-dur"></span></div>
<div class="dl-acao"><div class="seg"><button class="on" data-f="audio">Áudio</button><button data-f="video">Vídeo</button></div><button class="dl-go" id="d-ir"><svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M12 3v12m0 0l-5-5m5 5l5-5M4 19h16" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>DOWNLOAD</button><button class="dl-quad" id="d-pasta2" title="Abrir a pasta de downloads"><svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M3 6.5A1.5 1.5 0 0 1 4.5 5h4.2l2 2.2H19.5A1.5 1.5 0 0 1 21 8.7v8.8a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 17.5z" fill="currentColor"/></svg></button></div></div>
<div class="toast" id="d-toast" hidden></div>
<div class="dl-pasta"><span id="d-pasta-txt" title="Pasta onde os downloads são salvos"></span><button class="dl-btn" id="d-trocar">Trocar pasta</button></div>
<div class="dl-player" id="d-player" hidden>
<div class="dl-ptop"><div class="dl-info"><div class="dl-tit" id="p-tit"></div><div class="dl-can" id="p-can"></div></div><span id="p-dur"></span></div>
<div class="dl-onda"><canvas id="p-cv" draggable="true" title="Clique para pular · arraste para a timeline"></canvas></div>
<div class="dl-ctl"><button id="p-play" title="Tocar / pausar">▶</button><span id="p-tempo">00:00 / 00:00</span><input type="range" id="p-vol" min="0" max="1" step="0.05" value="1" title="Volume"><button class="dl-btn" id="p-bpm" title="Identifica o BPM (andamento) da música" disabled>BPM</button><button class="dl-btn" id="p-tom" title="Identifica o tom da música" disabled>TOM</button><button class="dl-btn" id="p-vinci" title="Importa para a pasta Trilhas do media pool" disabled>→ DaVinci</button></div>
<audio id="p-audio" preload="metadata"></audio></div>
<div class="cfg-fundo" id="d-cfg" hidden><div class="cfg">
<div class="cfg-top"><h2>Configurações</h2><button class="ic" id="c-fechar" title="Fechar">✕</button></div>
<h3>Onde salvar</h3>
<div class="cfg-linha"><input id="c-pasta" readonly><button class="dl-btn" id="c-trocar">Trocar</button></div>
<h3>Comportamento</h3>
<div style="display:grid;gap:14px">
<label class="chk"><input type="checkbox" id="c-tocar"><span>Tocar ao abrir<small>Quando a onda estiver pronta, o áudio começa a tocar.</small></span></label>
<label class="chk"><input type="checkbox" id="c-importar"><span>Inserir no DaVinci<small>Cada download entra na pasta Trilhas do media pool, sem mexer na timeline.</small></span></label>
</div>
<h3>Formato</h3>
<select id="c-formato" style="width:100%"><option value="mp3">MP3 (arquivo leve)</option><option value="wav">WAV (sem perda, para editar)</option></select>
<h3>Qualidade do vídeo</h3>
<select id="c-qual" style="width:100%"><option value="best">Melhor disponível</option><option value="1080">Até 1080p</option><option value="720">Até 720p</option><option value="480">Até 480p</option></select>
<h3>Cor da onda</h3>
<div class="cfg-cores"><button data-cor="mono"><i style="background:#e8e8ee"></i>Mono</button><button data-cor="azul"><i style="background:#2f80c4"></i>Azul</button><button data-cor="verde"><i style="background:#3fae6a"></i>Verde</button></div>
<h3>Atalho na Mesa</h3>
<label class="chk"><input type="checkbox" id="c-atalho"><span>Mostrar na Mesa<small>Cria o app "Abrir Agiliza-Zé" na Mesa. Ele abre o plugin pelo menu do DaVinci.</small></span></label>
<h3>Conexão com o DaVinci</h3>
<div id="c-resolve" class="sub">Verificando…</div>
<div class="cfg-acao"><button class="dl-btn" id="c-tentar">Tentar de novo</button></div>
<h3>Motor de download</h3>
<div class="sub">O YouTube muda com frequência. Atualize o motor se os downloads começarem a falhar.</div>
<div class="cfg-acao"><button class="dl-btn" id="c-motor">Atualizar motor</button> <span class="sub" id="c-motor-msg"></span></div>
</div></div>
</div>"""

JS_ABAS = r"""<script>
document.querySelectorAll('[data-modelo]').forEach(b=>b.onclick=async()=>{b.disabled=true;const nome=b.parentElement.querySelector('.nome-tl').value.trim();
 const cores={};b.closest('.modelo').querySelectorAll('.cor-sel').forEach(x=>cores[x.dataset.k]=x.value);
 const d=await (await fetch('/api/criar_timeline',{method:'POST',body:JSON.stringify({modelo:b.dataset.modelo,nome,cores})})).json();
 avisar(d.ok?d.msg:'⚠︎ '+d.msg);b.disabled=false;});
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let ARQUIVOS=[],INFO_URL=null,INFO_DADOS=null,FORMATO='audio';
function avisar(t){const el=$('d-toast');el.textContent=t;el.hidden=false;clearTimeout(avisar.t);avisar.t=setTimeout(()=>{el.hidden=true;},4500);}
function abas(t){if(t!=='b')AUDIO.pause();$('ta').hidden=t!=='a';$('tb').hidden=t!=='b';$('tc').hidden=t!=='c';$('td').hidden=t!=='d';$('te').hidden=t!=='e';$('tf').hidden=t!=='f';if(t==='e')listarHack();
 document.querySelectorAll('.tab').forEach(b=>b.classList.toggle('on',b.dataset.t===t));if(t==='b')listarDownloads();}
document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>abas(b.dataset.t));
function tamanho(n){return n>1e9?(n/1e9).toFixed(1)+' GB':n>1e6?(n/1e6).toFixed(1)+' MB':Math.max(1,Math.round(n/1e3))+' KB';}
function fmtDur(s){s=Math.round(s||0);const h=Math.floor(s/3600),m=Math.floor(s/60)%60,x=s%60;const p=n=>String(n).padStart(2,'0');return h?`${h}:${p(m)}:${p(x)}`:`${m}:${p(x)}`;}
function atualizarVazio(){$('d-vazio').hidden=!$('d-card').hidden;}
function desenhar(){atualizarVazio();}
async function mostrarPasta(){const d=await (await fetch('/api/ver_pasta',{method:'POST',body:'{}'})).json();$('d-pasta-txt').textContent='Salvar em: '+d.pasta;}
async function listarDownloads(){mostrarPasta();const d=await (await fetch('/api/downloads',{method:'POST',body:'{}'})).json();
 ARQUIVOS=d.arquivos||[];desenhar();
}
$('d-atual').onclick=listarDownloads;
$('d-pasta').onclick=()=>fetch('/api/abrir_pasta',{method:'POST',body:'{}'});
async function salvarCfg(dados){const d=await (await fetch('/api/salvar_config',{method:'POST',body:JSON.stringify(dados)})).json();
 if(d.ok){CFG={...CFG,...d.config};desenharOnda();}else{avisar('⚠︎ '+d.msg);}}
function marcarCor(){document.querySelectorAll('.cfg-cores button').forEach(b=>b.classList.toggle('on',b.dataset.cor===CFG.cor_onda));}
async function verResolve(){$('c-resolve').textContent='Verificando…';
 try{const d=await (await fetch('/api/status')).json();
  $('c-resolve').textContent=d.resolve?'Conectado — projeto: '+d.projeto:'Não conectado — abra o DaVinci e o plugin Agiliza-Zé.';
 }catch(e){$('c-resolve').textContent='Não consegui verificar agora.';}}
async function abrirConfig(){const d=await (await fetch('/api/ver_config',{method:'POST',body:'{}'})).json();
 if(d.ok){CFG={...CFG,...d.config};$('c-pasta').value=d.config.pasta;$('c-tocar').checked=!!d.config.tocar_ao_abrir;
  $('c-importar').checked=!!d.config.importar_auto;$('c-formato').value=d.config.formato_audio;$('c-qual').value=d.config.qualidade;marcarCor();}
 $('c-atalho').checked=!!d.config.atalho_mesa;$('c-motor-msg').textContent='';$('d-cfg').hidden=false;verResolve();}
$('d-config').onclick=abrirConfig;
$('c-fechar').onclick=()=>{$('d-cfg').hidden=true;};
$('d-cfg').onclick=e=>{if(e.target.id==='d-cfg')$('d-cfg').hidden=true;};
$('c-tocar').onchange=e=>salvarCfg({tocar_ao_abrir:e.target.checked});
$('c-importar').onchange=e=>salvarCfg({importar_auto:e.target.checked});
$('c-formato').onchange=e=>salvarCfg({formato_audio:e.target.value});
$('c-qual').onchange=e=>salvarCfg({qualidade:e.target.value});
document.querySelectorAll('.cfg-cores button').forEach(b=>b.onclick=()=>{salvarCfg({cor_onda:b.dataset.cor}).then(marcarCor);});
$('c-trocar').onclick=async()=>{const d=await (await fetch('/api/trocar_pasta',{method:'POST',body:'{}'})).json();
 if(d.ok){$('c-pasta').value=d.pasta;$('d-pasta-txt').textContent='Salvar em: '+d.pasta;listarDownloads();}else{$('c-motor-msg').textContent=d.msg;}};
$('c-tentar').onclick=verResolve;
$('c-atalho').onchange=async e=>{const d=await (await fetch('/api/atalho_mesa',{method:'POST',body:JSON.stringify({ligar:e.target.checked})})).json();
 if(!d.ok){avisar('⚠︎ '+d.msg);e.target.checked=false;}else{e.target.checked=d.ligado;}};
$('c-motor').onclick=async()=>{$('c-motor').disabled=true;$('c-motor-msg').textContent='Atualizando…';
 const d=await (await fetch('/api/atualizar_motor',{method:'POST',body:'{}'})).json();
 $('c-motor-msg').textContent=d.msg;$('c-motor').disabled=false;};
fetch('/api/ver_config',{method:'POST',body:'{}'}).then(r=>r.json()).then(d=>{if(d.ok)CFG={...CFG,...d.config};});
$('d-pasta2').onclick=()=>fetch('/api/abrir_pasta',{method:'POST',body:'{}'});
$('d-trocar').onclick=async()=>{const d=await (await fetch('/api/trocar_pasta',{method:'POST',body:'{}'})).json();
 if(d.ok){$('d-pasta-txt').textContent='Salvar em: '+d.pasta;listarDownloads();}else{avisar(d.msg);}};
document.querySelectorAll('.seg button').forEach(b=>b.onclick=()=>{FORMATO=b.dataset.f;
 document.querySelectorAll('.seg button').forEach(x=>x.classList.toggle('on',x===b));});
async function carregarInfo(url){url=(url||'').trim();if(!url)return;
 const d=await (await fetch('/api/info_link',{method:'POST',body:JSON.stringify({url})})).json();
 if(!d.ok){INFO_URL=null;$('d-card').hidden=true;avisar('⚠︎ '+d.msg);atualizarVazio();return;}
 INFO_URL=url;INFO_DADOS=d;$('d-img').src=d.miniatura||'';$('d-tit').textContent=d.titulo||'';$('d-can').textContent=d.canal||'';
 $('d-dur').textContent=fmtDur(d.duracao);$('d-card').hidden=false;
 atualizarVazio();}
$('d-url').onkeydown=e=>{if(e.key==='Enter')carregarInfo($('d-url').value);};
$('d-url').addEventListener('paste',()=>setTimeout(()=>carregarInfo($('d-url').value),0));
document.addEventListener('paste',e=>{if($('tb').hidden||document.activeElement===$('d-url'))return;
 const t=(e.clipboardData||window.clipboardData).getData('text').trim();if(!t)return;
 $('d-url').value=t;carregarInfo(t);});
$('d-ir').onclick=async()=>{if(!INFO_URL){avisar('Cole um link primeiro.');return;}
 const url=INFO_URL,info=INFO_DADOS,inicio=Date.now()/1000;
 $('d-ir').disabled=true;
 const d=await (await fetch('/api/baixar',{method:'POST',body:JSON.stringify({url,formato:FORMATO})})).json();
 $('d-ir').disabled=false;
 if(!d.ok){avisar('⚠︎ '+d.msg);return;}
 abrirEspera(info);acompanharDownload(url,inicio);};
function abrirEspera(info){ARQ_ATUAL=null;ONDA=Array(500).fill(0.06);ONDA_DUR=info.duracao||0;
 $('d-player').hidden=false;$('p-tit').textContent=info.titulo||'';$('p-can').textContent='Baixando…';
 $('p-dur').textContent=hmsCurto(ONDA_DUR);AUDIO.pause();AUDIO.removeAttribute('src');AUDIO.load();
 $('p-vinci').disabled=true;$('p-bpm').disabled=true;$('p-tom').disabled=true;ANALISE={bpm:null,tom:null};$('p-tempo').textContent='00:00 / '+hmsCurto(ONDA_DUR);desenharOnda();}
function acompanharDownload(url,inicio){const chave='Download · '+url.slice(0,60);let n=0;
 const t=setInterval(async()=>{if(++n>1500){clearInterval(t);return;}
  const d=await (await fetch('/api/jobs')).json();
  const j=(d.jobs||[]).find(x=>(x.nome||'').startsWith(chave)&&(x.inicio||0)>=inicio-5);
  if(!j)return;
  if(!j.fim){$('p-can').textContent=j.msg||'Baixando…';return;}
  clearInterval(t);
  if(j.erro){$('p-can').textContent='Não consegui baixar';avisar('⚠︎ '+j.erro);return;}
  listarDownloads();abrirPlayer(j.arquivo,true);},1500);}
let ANALISE={bpm:null,tom:null};
let ONDA=[],ONDA_DUR=0,ARQ_ATUAL=null,RAF=null,CFG={tocar_ao_abrir:true,cor_onda:'mono'};
const CORES_ONDA={mono:null,azul:'#2f80c4',verde:'#3fae6a'};
const AUDIO=$('p-audio');
function hmsCurto(s){s=Math.round(s||0);const p=n=>String(n).padStart(2,'0');const h=Math.floor(s/3600),m=Math.floor(s/60)%60;return h?`${h}:${p(m)}:${p(s%60)}`:`${p(m)}:${p(s%60)}`;}
function desenharOnda(){const c=$('p-cv');if(!ONDA.length)return;const r=c.getBoundingClientRect(),dpr=window.devicePixelRatio||1;
 c.width=r.width*dpr;c.height=r.height*dpr;const g=c.getContext('2d');g.setTransform(dpr,0,0,dpr,0,0);
 const W=r.width,H=r.height,n=ONDA.length,px=W/n,cs=getComputedStyle(document.documentElement);
 const cinza=cs.getPropertyValue('--line').trim()||'#444',tocado=CORES_ONDA[CFG.cor_onda]||cs.getPropertyValue('--ink').trim()||'#eee';
 const dur=AUDIO.duration||ONDA_DUR||1,prog=Math.min(1,AUDIO.currentTime/dur);g.clearRect(0,0,W,H);
 for(let i=0;i<n;i++){const h=Math.max(2,ONDA[i]*H*0.92);g.fillStyle=(i/n)<=prog?tocado:cinza;g.fillRect(i*px,(H-h)/2,Math.max(1,px*0.7),h);}
 const xh=prog*W;g.fillStyle='#e5484d';g.fillRect(xh-1,0,2,H);g.beginPath();g.moveTo(xh-6,0);g.lineTo(xh+6,0);g.lineTo(xh,9);g.closePath();g.fill();
 $('p-tempo').textContent=hmsCurto(AUDIO.currentTime)+' / '+hmsCurto(dur);}
function lacoOnda(){desenharOnda();if(!AUDIO.paused){RAF=requestAnimationFrame(lacoOnda);}}
AUDIO.onplay=()=>{$('p-play').textContent='❚❚';cancelAnimationFrame(RAF);lacoOnda();};
AUDIO.onpause=()=>{$('p-play').textContent='▶';desenharOnda();};
AUDIO.onended=()=>{$('p-play').textContent='▶';desenharOnda();};
AUDIO.onloadedmetadata=desenharOnda;
$('p-play').onclick=()=>{if(!ARQ_ATUAL)return;AUDIO.paused?AUDIO.play():AUDIO.pause();};
$('p-vol').oninput=e=>{AUDIO.volume=parseFloat(e.target.value);};
$('p-cv').onclick=e=>{const r=e.target.getBoundingClientRect();const f=(e.clientX-r.left)/r.width;
 AUDIO.currentTime=f*(AUDIO.duration||ONDA_DUR||0);desenharOnda();};
$('p-bpm').onclick=async()=>{if(!ARQ_ATUAL)return;const b=$('p-bpm');b.disabled=true;b.textContent='…';
 const d=await (await fetch('/api/bpm',{method:'POST',body:JSON.stringify({nome:ARQ_ATUAL})})).json();
 b.disabled=false;b.textContent='BPM';
 if(d.ok){ANALISE.bpm=d;mostrarAnalise();}else{avisar('⚠︎ '+d.msg);}};
$('p-tom').onclick=async()=>{if(!ARQ_ATUAL)return;const b=$('p-tom');b.disabled=true;b.textContent='…';
 const d=await (await fetch('/api/tom',{method:'POST',body:JSON.stringify({nome:ARQ_ATUAL})})).json();
 b.disabled=false;b.textContent='TOM';
 if(d.ok){ANALISE.tom=d;mostrarAnalise();}else{avisar('⚠︎ '+d.msg);}};
function mostrarAnalise(){const partes=[];
 if(ANALISE.bpm)partes.push('BPM '+ANALISE.bpm.bpm+' (confiança '+Math.round(ANALISE.bpm.confianca*100)+'%)');
 if(ANALISE.tom)partes.push('Tom '+ANALISE.tom.tom+' (confiança '+Math.round(ANALISE.tom.confianca*100)+'%)');
 $('p-can').textContent=partes.join(' · ')||'Download';}
$('p-vinci').onclick=async()=>{if(!ARQ_ATUAL)return;const b=$('p-vinci');b.disabled=true;b.textContent='Importando…';
 const d=await (await fetch('/api/importar_trilha',{method:'POST',body:JSON.stringify({nome:ARQ_ATUAL})})).json();
 avisar(d.ok?d.msg:'⚠︎ '+d.msg);b.disabled=false;b.textContent='→ DaVinci';if(d.ok)resetarBaixar();};
function resetarBaixar(){AUDIO.pause();AUDIO.removeAttribute('src');AUDIO.load();ARQ_ATUAL=null;ONDA=[];INFO_URL=null;INFO_DADOS=null;
 $('d-player').hidden=true;$('d-card').hidden=true;$('d-url').value='';atualizarVazio();}
$('p-cv').addEventListener('dragstart',e=>{if(!ARQ_ATUAL){e.preventDefault();return;}
 if(!window.agilizaZe){e.preventDefault();avisar('Arrastar só funciona dentro do DaVinci (plugin).');return;}
 e.preventDefault();window.agilizaZe.arrastar(ARQ_ATUAL);});
window.addEventListener('resize',desenharOnda);
if(window.agilizaZe&&window.agilizaZe.onArrastou)window.agilizaZe.onArrastou(()=>{if(ARQ_ATUAL)resetarBaixar();});
async function abrirPlayer(nome,tocar=true){
 ARQ_ATUAL=nome;document.querySelectorAll('.dl-item').forEach(i=>i.classList.toggle('sel',i.dataset.n===nome));
 $('d-player').hidden=false;$('p-tit').textContent=nome.replace(/\.[^.]+$/,'');$('p-can').textContent='Lendo o áudio…';$('p-dur').textContent='';$('p-vinci').disabled=false;$('p-bpm').disabled=false;$('p-tom').disabled=false;ANALISE={bpm:null,tom:null};
 AUDIO.pause();ONDA=[];
 const d=await (await fetch('/api/forma_onda',{method:'POST',body:JSON.stringify({nome})})).json();
 if(!d.ok){$('p-can').textContent='⚠︎ '+d.msg;return;}
 ONDA=d.picos;ONDA_DUR=d.duracao;$('p-can').textContent='Download';$('p-dur').textContent=hmsCurto(d.duracao)+' · '+tamanho(d.tamanho);
 AUDIO.src='/api/arquivo?nome='+encodeURIComponent(nome);AUDIO.volume=parseFloat($('p-vol').value);desenharOnda();
 if(tocar&&CFG.tocar_ao_abrir)AUDIO.play().catch(()=>{});}
if(window.ResizeObserver){new ResizeObserver(()=>document.documentElement.style.setProperty('--hist-h',document.getElementById('hist').offsetHeight+'px')).observe(document.getElementById('hist'));}

function abrirPresetForm(){$('pr-tl').innerHTML=document.querySelector('.cor-sel[data-k="timeline"]').innerHTML;
 $('pr-out').innerHTML=document.querySelector('.cor-sel[data-k="saida"]').innerHTML;
 $('pr-tl').value='Rec.709 (Scene)';$('pr-out').value='Same as Timeline';$('pr-nome').value='';$('pr-fundo').hidden=false;$('pr-nome').focus();}
$('pr-abrir').onclick=abrirPresetForm;
$('pr-fechar').onclick=()=>{$('pr-fundo').hidden=true;};
$('pr-cancelar').onclick=()=>{$('pr-fundo').hidden=true;};
$('pr-fundo').onclick=e=>{if(e.target.id==='pr-fundo')$('pr-fundo').hidden=true;};
$('pr-salvar').onclick=async()=>{const dados={nome:$('pr-nome').value,largura:$('pr-w').value,altura:$('pr-h').value,fps:$('pr-fps').value,timeline:$('pr-tl').value,saida:$('pr-out').value};
 const d=await (await fetch('/api/salvar_preset',{method:'POST',body:JSON.stringify(dados)})).json();
 if(d.ok){$('pr-fundo').hidden=true;avisar(d.msg);carregarPresets();}else{avisar('⚠︎ '+d.msg);}};
async function carregarPresets(){const d=await (await fetch('/api/presets',{method:'POST',body:'{}'})).json();
 let linha=$('pr-linha');if(!linha){linha=document.createElement('div');linha.id='pr-linha';linha.className='pr-linha';$('pr-grade').after(linha);}
 linha.querySelectorAll('.preset').forEach(x=>x.remove());linha.appendChild($('pr-abrir'));
 (d.presets||[]).forEach(pr=>{const c=document.createElement('div');c.className='modelo preset';
  c.innerHTML='<div class="pr-topo"><div class="mol-t">'+esc(pr.nome)+'</div><button class="pr-lixo" data-excluir="'+pr.id+'" title="Excluir preset" aria-label="Excluir preset"><svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/></svg></button></div><dl class="mol-specs">'+
   '<div><dt>Resolução</dt><dd>'+pr.largura+' × '+pr.altura+'</dd></div>'+
   '<div><dt>Frame rate</dt><dd>'+esc(pr.fps)+' fps</dd></div>'+
   '<div><dt>Timeline</dt><dd>'+esc(pr.timeline)+'</dd></div>'+
   '<div><dt>Output</dt><dd>'+esc(pr.saida)+'</dd></div></dl>'+
   '<input class="nome-tl" placeholder="Nome da timeline" maxlength="80">'+
   '<button class="btn" data-preset="'+pr.id+'">Criar timeline</button>';
  linha.insertBefore(c,$('pr-abrir'));});
 linha.appendChild($('pr-abrir'));}
$('tc').addEventListener('click',async e=>{const b=e.target.closest('button');if(!b)return;
 if(b.dataset.preset){const nome=b.parentElement.querySelector('.nome-tl').value.trim();b.disabled=true;
  const d=await (await fetch('/api/criar_timeline',{method:'POST',body:JSON.stringify({modelo:'p:'+b.dataset.preset,nome})})).json();
  b.disabled=false;avisar(d.ok?d.msg:'⚠︎ '+d.msg);}
 if(b.dataset.excluir){if(!confirm('Excluir este preset?'))return;
  const d=await (await fetch('/api/excluir_preset',{method:'POST',body:JSON.stringify({id:b.dataset.excluir})})).json();
  avisar(d.msg);carregarPresets();}});
carregarPresets();

let HACK_PROJETO='';
async function listarHack(){const d=await (await fetch('/api/hackedit',{method:'POST',body:'{}'})).json();
 HACK_PROJETO=d.projeto||'';$('hack-projeto').textContent=HACK_PROJETO?'Projeto aberto no DaVinci: '+HACK_PROJETO:'Nenhum projeto aberto no DaVinci';
 const g=$('hack-grade');g.innerHTML='';
 (d.referencias||[]).forEach(r=>{const c=document.createElement('div');c.className='modelo hack-ref';
  c.innerHTML='<div class="pr-topo"><div class="mol-t">'+esc(r.nome)+'</div><button class="pr-lixo" data-hexcluir="'+r.id+'" title="Excluir referência" aria-label="Excluir referência"><svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/></svg></button></div>'+
   '<div class="hack-data">'+esc(r.projeto||'sem projeto')+' · '+esc(r.criado)+'</div>'+
   (r.analise?'<div class="hack-data">Ritmo: '+r.analise.planos+' plano(s) · média '+r.analise.media+' s · '+r.analise.cortes_por_min+' cortes/min · curtos '+r.analise.curtos+' · longos '+r.analise.longos+'</div>':'')+
   (r.inventario?'<div class="hack-data">Lido de '+esc(r.inventario.timeline)+': '+r.inventario.planos+' plano(s) · '+esc(Object.entries(r.inventario.momentos).map(([k,v])=>k+' ('+v+')').join(', '))+'</div>':'')+
   '<div class="hack-acoes"><button class="btn" data-hanalisar="'+r.id+'">Analisar referência</button><button class="btn" data-hmodo="nova" data-hid="'+r.id+'">Nova timeline</button><button class="dl-btn" data-hmodo="premontar" data-hid="'+r.id+'">Pré-montagem nessa timeline</button></div>'+
   (r.link?'<div class="hack-link">'+esc(r.link)+'</div>':(r.arquivo?'<div class="hack-data">vídeo: '+esc(r.arquivo_nome||'arquivo')+'</div>':'<div class="hack-data">sem link</div>'));
  g.appendChild(c);});
 const m=document.createElement('div');m.className='modelo hack-mais';m.id='hack-abrir';m.innerHTML='<div class="mais-sinal">+</div><div class="mol-t">Nova referência</div>';
 g.appendChild(m);}
document.addEventListener('click',async e=>{
 const an=e.target.closest('[data-hanalisar]');if(an){an.disabled=true;
  const d=await (await fetch('/api/analisar_hackedit',{method:'POST',body:JSON.stringify({id:an.dataset.hanalisar})})).json();
  an.disabled=false;avisar(d.ok?d.msg:'⚠︎ '+d.msg);jobs();return;}
 const ac=e.target.closest('[data-hmodo]');if(ac){ac.disabled=true;
  const d=await (await fetch('/api/acao_hackedit',{method:'POST',body:JSON.stringify({id:ac.dataset.hid,modo:ac.dataset.hmodo})})).json();
  ac.disabled=false;avisar(d.ok?d.msg:'⚠︎ '+d.msg);listarHack();return;}
 if(e.target.closest('#hack-abrir')){$('hack-form').hidden=false;$('hack-nome').value='';$('hack-link').value='';$('hack-nome').focus();return;}
 const x=e.target.closest('[data-hexcluir]');if(x){if(!confirm('Excluir esta referência?'))return;
  const d=await (await fetch('/api/excluir_hackedit',{method:'POST',body:JSON.stringify({id:x.dataset.hexcluir})})).json();avisar(d.msg);listarHack();}});
$('hack-cancelar').onclick=()=>{$('hack-form').hidden=true;};
async function rodarStab(modo){$('st-analisar').disabled=$('st-aplicar').disabled=true;
 const d=await (await fetch('/api/stabilizar',{method:'POST',body:JSON.stringify({modo:modo,sensibilidade:$('st-sens').value,selecionados:$('st-sel').checked,forcar:$('st-forca').checked})})).json();
 avisar(d.ok?d.msg:'⚠︎ '+d.msg);$('st-analisar').disabled=$('st-aplicar').disabled=false;jobs();}
$('st-analisar').onclick=()=>rodarStab('analisar');
$('st-aplicar').onclick=()=>rodarStab('aplicar');
$('hack-salvar').onclick=async()=>{const arq=$('hack-arquivo').files[0];let d;
 if(arq){$('hack-salvar').disabled=true;avisar('Enviando o vídeo…');
  d=await (await fetch('/api/upload_hackedit?nome='+encodeURIComponent($('hack-nome').value)+'&arquivo='+encodeURIComponent(arq.name),{method:'POST',body:arq,headers:{'Content-Type':'application/octet-stream'}})).json();
  $('hack-salvar').disabled=false;}
 else{d=await (await fetch('/api/salvar_hackedit',{method:'POST',body:JSON.stringify({nome:$('hack-nome').value,link:$('hack-link').value})})).json();}
 if(d.ok){$('hack-form').hidden=true;avisar(d.msg);listarHack();}else{avisar('⚠︎ '+d.msg);}};
</script>"""

def _tipos_js():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from tipos import TIPOS, momentos
    return json.dumps({k: {"nome": v[0], "momentos": [[n, c] for n, c, _ in momentos(k)]} for k, v in TIPOS.items()},
                      ensure_ascii=False)


ROTEIRISTA = """<section class="nova" id="td" hidden><div class="box" style="margin-top:14px"><h2>1 · Melhorar áudio</h2>
<div class="sub">Mede a faixa de voz (volume, variação e ruído) e aplica na própria timeline, com os recursos do DaVinci:
<b>Voice Isolation</b> (automático ou de 10% a 100%), <b>Dialogue Leveler</b> quando a fala oscila e normalização de volume.
Opcional: <b>remover silêncios e ruídos</b> — o Whisper acha onde há fala e as pausas saem de todas as faixas juntas (sincronia mantida).
Tudo fica visível e editável no Inspector. Um backup é salvo antes.</div>
<div class="base-grade aud-grade"><div class="modelo"><div class="mol-box"><svg class="mol" viewBox="0 0 96 56" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="14" y1="22.0" x2="14" y2="34.0"/><line x1="24" y1="15.0" x2="24" y2="41.0"/><line x1="34" y1="8.0" x2="34" y2="48.0"/><line x1="48" y1="13.0" x2="48" y2="43.0"/><line x1="62" y1="6.0" x2="62" y2="50.0"/><line x1="72" y1="19.0" x2="72" y2="37.0"/><line x1="82" y1="23.0" x2="82" y2="33.0"/></svg></div><div class="mol-t">Isolamento de voz</div><div class="mol-s">Voice Isolation do DaVinci</div><div class="aud-campo"><select id="a-iso"><option value="auto" selected>Automático (pelo ruído medido)</option><option value="10">10%</option><option value="20">20%</option><option value="30">30%</option><option value="40">40%</option><option value="50">50%</option><option value="60">60%</option><option value="70">70%</option><option value="80">80%</option><option value="90">90%</option><option value="100">100%</option>
<option value="off">Desligado</option></select></div></div><div class="modelo"><div class="mol-box"><svg class="mol" viewBox="0 0 96 56" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="12" y1="21.0" x2="12" y2="35.0"/><line x1="22" y1="13.0" x2="22" y2="43.0"/><line x1="32" y1="17.0" x2="32" y2="39.0"/><line x1="46" y1="24.0" x2="46" y2="32.0" opacity=".35"/><line x1="58" y1="15.0" x2="58" y2="41.0"/><line x1="70" y1="8.0" x2="70" y2="48.0"/><line x1="82" y1="20.0" x2="82" y2="36.0"/></svg></div><div class="mol-t">Silêncios e ruídos</div><div class="mol-s">Remove as pausas de todas as faixas</div><div class="aud-campo"><select id="a-sil"><option value="0" selected>Não remover</option>
<option value="0.5">Pausas maiores que 0,5 s</option><option value="1">Pausas maiores que 1 s</option>
<option value="2">Pausas maiores que 2 s</option><option value="3">Pausas maiores que 3 s</option></select></div></div><div class="modelo"><div class="mol-box"><svg class="mol" viewBox="0 0 96 56" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="20" y1="20.0" x2="20" y2="36.0"/><line x1="32" y1="11.0" x2="32" y2="45.0"/><line x1="44" y1="17.0" x2="44" y2="39.0"/><line x1="56" y1="6.0" x2="56" y2="50.0"/><line x1="68" y1="14.0" x2="68" y2="42.0"/><line x1="80" y1="22.0" x2="80" y2="34.0"/></svg></div><div class="mol-t">Câmeras</div><div class="mol-s">Ajusta as outras faixas</div><label class="aud-chk"><input type="checkbox" id="a-cam"> Abaixar o áudio das outras faixas (−15 dB)</label></div></div><div class="go"><button class="btn sec" id="a-ir">✦ Analisar e melhorar o áudio</button><button class="btn ter" id="a-teste">Só analisar</button>
<span class="sub" id="a-msg"></span></div></div>
<div class="box" style="margin-top:14px"><h2>2 · Analisar</h2>
<div class="sub" id="dv">Procurando o DaVinci…</div>
<div class="campos">
<label>Nome do projeto<input id="f-nome" placeholder="Ex.: Ana e Pedro - Cerimônia"></label>
<label>O que analisar<select id="f-modo"><option value="atual">Timeline aberta no DaVinci</option><option value="cor">Takes de uma cor</option>
<option value="timelines">Timelines escolhidas</option><option value="todas">Todas as timelines</option></select></label>
<label id="l-cor" style="display:none">Cor dos takes<select id="f-cor"></select></label>
<label>Duração do roteiro<select id="f-dur"><option>30 a 60 segundos (Reels/teaser)</option><option>1 a 2 minutos</option>
<option selected>3 a 5 minutos (filme curto)</option><option>6 a 8 minutos</option></select></label>
<div class="full" id="l-tls" style="display:none"><label>Timelines</label><div class="tls" id="f-tls"></div></div>
<label class="full">Nomes (ajuda a transcrição e a análise)<input id="f-prompt" placeholder="Ex.: Noivos Ana e Pedro, padre João, filha Laura"></label>
<label class="full">Pedido extra (opcional)<div class="ditar"><textarea id="f-obs" placeholder="Ex.: foque nos votos e no discurso do pai; roteiro emocionante"></textarea><button type="button" class="mic" id="f-mic" title="Gravar pedido por voz">🎙</button></div><span class="sub" id="f-mic-msg"></span></label>
</div>
<div class="go"><button class="btn" id="f-ir">▶ Analisar</button><span class="sub" id="f-msg"></span></div></div>
</section>"""


def pagina_inicial(projetos: Path) -> str:
    pastas = []
    if projetos.exists():
        pastas = sorted((d for d in projetos.iterdir() if d.is_dir() and (d / "decupagem.html").exists()),
                        key=lambda d: (d / "decupagem.html").stat().st_mtime, reverse=True)
    cards = []
    for d in pastas:
        try:
            t = json.loads((d / "transcricao.json").read_text())
            arq_a = d / "analise.json" if (d / "analise.json").exists() else d / "analise_anterior.json"
            a = json.loads(arq_a.read_text())
        except Exception:
            continue
        dur = int(t.get("duracao") or 0)
        quando = datetime.datetime.fromtimestamp((d / "decupagem.html").stat().st_mtime).strftime("%d/%m/%Y %H:%M")
        top = max(a.get("ganchos", []), key=lambda g: g["nota"], default=None)
        titulo = a.get("titulo") or t.get("projeto", d.name)
        cenas = len((a.get("roteiro") or {}).get("cenas", []))
        frase = f"<q>“{h.escape(top['texto'])}”</q>" if top else ""
        mont = (f'<button class="montar" data-p="{h.escape(d.name)}" title="Cria no DaVinci a timeline com as cenas do roteiro, na ordem">▶ Montar roteiro no DaVinci</button>'
                if (d / "roteiro_resolve.json").exists() else "")
        cards.append(
            f'<a class="proj" href="/{h.escape(d.name)}/decupagem.html"><div class="eyebrow">{quando}</div>'
            f"<h2>{h.escape(titulo)}</h2><div class=\"meta\"><span>{dur // 3600}h{dur // 60 % 60:02d}min</span>"
            f"<span>{len(a.get('ganchos', []))} ganchos</span><span>{cenas} cenas</span></div>{frase}"
            f'<div class="acoes">{mont}<button class="redo" data-p="{h.escape(d.name)}" title="Reaproveita a transcrição">↻ Refazer análise</button>'
            f'<button class="del" data-p="{h.escape(d.name)}" title="Mandar para a Lixeira">🗑 Apagar</button></div></a>')
    vazio = ('<div class="vazio">Nenhum projeto ainda. No chat, com a timeline aberta no DaVinci, peça '
             '<b>“faz um script desse projeto”</b>.</div>')
    rot_html = ROTEIRISTA.replace('</section>', '<main class="grid">' + ''.join(cards or [vazio]) + '</main></section>')
    return (f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>Agiliza-Zé</title><link rel="icon" href="/_marca/logo.png">'
            f'<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..900&display=swap">'
            f'<style>{CSS}{CSS_ABAS}</style></head><body><header class="hero"><div class="in"><img class="logo-topo" src="/_marca/logo.png" alt="Agiliza-Zé">'
            '<button class="atualizar-topo" onclick="location.reload()" title="Atualizar">↻</button></div></header>'
            f'<nav class="tabs"><button class="tab on" data-t="c">Timeline</button><button class="tab" data-t="a">Decupagem</button><button class="tab" data-t="d">Roteirista</button><button class="tab" data-t="b">Trilhas</button><button class="tab" data-t="e">HackEdit</button><button class="tab" data-t="f">Stabilizer</button></nav>'
            f'<div id="ta" hidden>{FORM}</div>{BAIXAR}{rot_html}<div class="base" id="tf" hidden><div class="base-titulo">Stabilizer · tira só o tremor</div><div class="aud-grade"><div class="modelo"><div class="mol-t">Clipes da timeline aberta</div><div class="mol-s">Mede o tremor de cada clipe. Pan e movimento lento não contam, então clipe firme fica intacto.</div><label class="aud-chk" style="margin:4px 0 10px"><input type="checkbox" id="st-sel"> Só os clipes selecionados na timeline</label><label class="aud-chk" style="margin:4px 0 10px"><input type="checkbox" id="st-forca"> Estabilizar mesmo se estiver firme</label><div class="aud-campo"><select id="st-sens"><option value="leve">Leve (só tremor forte)</option><option value="medio" selected>Médio</option><option value="forte">Forte (qualquer tremor)</option></select></div><div class="go"><button class="btn ter" id="st-analisar">Só analisar</button> <button class="btn" id="st-aplicar">Analisar e estabilizar</button></div></div></div></div><div class="base" id="te" hidden><div class="base-titulo">HackEdit · referências por projeto</div><div class="hack-projeto" id="hack-projeto"></div><div class="base-grade" id="hack-grade"></div><div class="hack-form" id="hack-form" hidden><input id="hack-nome" placeholder="Nome da referência" maxlength="60" class="pr-campo"><input id="hack-link" placeholder="Link do Instagram (https://…)" maxlength="400" class="pr-campo"><label class="hack-up">ou envie um vídeo seu <input type="file" id="hack-arquivo" accept="video/*"></label><div class="cfg-acao"><button class="btn" id="hack-salvar">Salvar referência</button> <button class="dl-btn" id="hack-cancelar">Cancelar</button></div></div></div><div class="base" id="tc"><div class="base-titulo">Guia base timeline</div><div class="base-grade" id="pr-grade"><div class="modelo mais" id="pr-abrir" title="Criar um preset"><div class="mais-sinal">+</div><div class="mol-t">Novo preset</div><div class="mol-s">Nome, resolução, frame rate e cores</div></div><div class="cfg-fundo" id="pr-fundo" hidden><div class="cfg" id="pr-form"><div class="cfg-top"><h2>Novo preset</h2><button class="ic" id="pr-fechar" title="Fechar">✕</button></div><h3>Nome</h3><input id="pr-nome" maxlength="40" placeholder="Ex.: Vertical Reels 1080p" class="pr-campo"><h3>Resolução</h3><div class="cfg-linha"><input id="pr-w" type="number" min="320" max="7680" value="1920" class="pr-campo"><span class="sub">×</span><input id="pr-h" type="number" min="240" max="4320" value="1080" class="pr-campo"></div><h3>Frame rate</h3><select id="pr-fps" class="pr-campo"><option>23.976</option><option selected>24</option><option>25</option><option>29.97</option><option>30</option><option>50</option><option>60</option></select><h3>Timeline color space</h3><select id="pr-tl" class="pr-campo"></select><h3>Output color space</h3><select id="pr-out" class="pr-campo"></select><div class="cfg-acao"><button class="btn" id="pr-salvar">Salvar preset</button> <button class="dl-btn" id="pr-cancelar">Cancelar</button></div></div></div><div class="modelo"><div class="mol-box"><svg class="mol" viewBox="0 0 96 56" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M4 13V4H13"/><path d="M83 4H92V13"/><path d="M92 43V52H83"/><path d="M13 52H4V43"/><rect x="21.1" y="12.3" width="53.8" height="31.4" rx="2" stroke-dasharray="2 3" opacity=".55"/><circle cx="48.0" cy="28.0" r="2.6" fill="currentColor" stroke="none"/><path d="M48.0 22.0V24.5M48.0 31.5V34.0M42.0 28.0H44.5M51.5 28.0H54.0" opacity=".7"/><path d="M6 28.0H90" stroke-dasharray="1 3" opacity=".35"/></svg></div><div class="mol-t">Ultra HD (4K)</div><dl class="mol-specs"><div><dt>Resolução</dt><dd>3840 × 2160</dd></div><div><dt>Frame rate</dt><dd>24 fps</dd></div><div><dt>Timeline</dt><dd><select class="cor-sel" data-k="timeline"><option value="ACES">ACES</option><option value="ACEScc">ACEScc</option><option value="ACEScct">ACEScct</option><option value="ACEScg">ACEScg</option><option value="Adobe RGB">Adobe RGB</option><option value="Apple Log">Apple Log</option><option value="Apple Log 2">Apple Log 2</option><option value="ARRI LogC3">ARRI LogC3</option><option value="ARRI LogC4">ARRI LogC4</option><option value="AstroDesign A-Log">AstroDesign A-Log</option><option value="Blackmagic Design 4.6K Film Gen 1">Blackmagic Design 4.6K Film Gen 1</option><option value="Blackmagic Design 4.6K Film Gen 3">Blackmagic Design 4.6K Film Gen 3</option><option value="Blackmagic Design 4.6K Video Gen 1">Blackmagic Design 4.6K Video Gen 1</option><option value="Blackmagic Design 4.6K Video Gen 3">Blackmagic Design 4.6K Video Gen 3</option><option value="Blackmagic Design 4K Film Gen 1">Blackmagic Design 4K Film Gen 1</option><option value="Blackmagic Design 4K Film Gen 3">Blackmagic Design 4K Film Gen 3</option><option value="Blackmagic Design 4K Video Gen 3">Blackmagic Design 4K Video Gen 3</option><option value="Blackmagic Design Broadcast Film Gen 4">Blackmagic Design Broadcast Film Gen 4</option><option value="Blackmagic Design Extended Video Gen 4">Blackmagic Design Extended Video Gen 4</option><option value="Blackmagic Design Extended Video Gen 5">Blackmagic Design Extended Video Gen 5</option><option value="Blackmagic Design Film Gen 1">Blackmagic Design Film Gen 1</option><option value="Blackmagic Design Film Gen 5">Blackmagic Design Film Gen 5</option><option value="Blackmagic Design Pocket 4K Film Gen 4">Blackmagic Design Pocket 4K Film Gen 4</option><option value="Blackmagic Design Pocket 6K Film Gen 4">Blackmagic Design Pocket 6K Film Gen 4</option><option value="Blackmagic Design Video Gen 4">Blackmagic Design Video Gen 4</option><option value="Blackmagic Design Video Gen 5">Blackmagic Design Video Gen 5</option><option value="Canon Cinema Gamut/Canon Log">Canon Cinema Gamut/Canon Log</option><option value="Canon Cinema Gamut/Canon Log 2">Canon Cinema Gamut/Canon Log 2</option><option value="Canon Cinema Gamut/Canon Log 3">Canon Cinema Gamut/Canon Log 3</option><option value="Cineon Film Log">Cineon Film Log</option><option value="DaVinci WG/Intermediate">DaVinci WG/Intermediate</option><option value="DCI-XYZ">DCI-XYZ</option><option value="DJI D-Gamut/D-Log">DJI D-Gamut/D-Log</option><option value="DJI D-Gamut2/D-Log2">DJI D-Gamut2/D-Log2</option><option value="DRAGONcolor/REDgamma3">DRAGONcolor/REDgamma3</option><option value="DRAGONcolor/REDgamma4">DRAGONcolor/REDgamma4</option><option value="DRAGONcolor/REDlogFilm">DRAGONcolor/REDlogFilm</option><option value="DRAGONcolor2/REDgamma3">DRAGONcolor2/REDgamma3</option><option value="DRAGONcolor2/REDgamma4">DRAGONcolor2/REDgamma4</option><option value="DRAGONcolor2/REDlogFilm">DRAGONcolor2/REDlogFilm</option><option value="Fujifilm F-Log">Fujifilm F-Log</option><option value="Fujifilm F-Log2">Fujifilm F-Log2</option><option value="Fujifilm F-Log2 C">Fujifilm F-Log2 C</option><option value="GoPro GP-Log2">GoPro GP-Log2</option><option value="HSL">HSL</option><option value="HSV">HSV</option><option value="Insta360 I-Log">Insta360 I-Log</option><option value="Lab (CIE)">Lab (CIE)</option><option value="Leica L-Log">Leica L-Log</option><option value="Linear">Linear</option><option value="Nikon N-Log">Nikon N-Log</option><option value="P3-D60">P3-D60</option><option value="P3-D65">P3-D65</option><option value="P3-D65 (Scene)">P3-D65 (Scene)</option><option value="P3-D65 HLG 1000 nits">P3-D65 HLG 1000 nits</option><option value="P3-D65 Intermediate">P3-D65 Intermediate</option><option value="P3-D65 ST2084 1000 nits">P3-D65 ST2084 1000 nits</option><option value="P3-D65 ST2084 2000 nits">P3-D65 ST2084 2000 nits</option><option value="P3-D65 ST2084 4000 nits">P3-D65 ST2084 4000 nits</option><option value="P3-DCI">P3-DCI</option><option value="Panasonic V-Gamut/V-Log">Panasonic V-Gamut/V-Log</option><option value="Rec.709 (Scene)" selected>Rec.709 (Scene)</option><option value="Rec.709 Gamma 2.2">Rec.709 Gamma 2.2</option><option value="Rec.709 Gamma 2.4">Rec.709 Gamma 2.4</option><option value="Rec.709 HLG ARIB STD-B67">Rec.709 HLG ARIB STD-B67</option><option value="Rec.709-A">Rec.709-A</option><option value="Rec.2020 (Scene)">Rec.2020 (Scene)</option><option value="Rec.2020 Gamma 2.4">Rec.2020 Gamma 2.4</option><option value="Rec.2020 HLG ARIB STD-B67">Rec.2020 HLG ARIB STD-B67</option><option value="Rec.2020 Intermediate">Rec.2020 Intermediate</option><option value="Rec.2020 ST2084 1000 nits">Rec.2020 ST2084 1000 nits</option><option value="Rec.2020 ST2084 2000 nits">Rec.2020 ST2084 2000 nits</option><option value="Rec.2020 ST2084 4000 nits">Rec.2020 ST2084 4000 nits</option><option value="Rec.2100 HLG">Rec.2100 HLG</option><option value="Rec.2100 HLG (Scene)">Rec.2100 HLG (Scene)</option><option value="Rec.2100 ST2084">Rec.2100 ST2084</option><option value="Rec.2100 ST2084 (Scene)">Rec.2100 ST2084 (Scene)</option><option value="REDcolor2/REDgamma3">REDcolor2/REDgamma3</option><option value="REDcolor2/REDgamma4">REDcolor2/REDgamma4</option><option value="REDcolor2/REDlogFilm">REDcolor2/REDlogFilm</option><option value="REDcolor3/REDgamma3">REDcolor3/REDgamma3</option><option value="REDcolor3/REDgamma4">REDcolor3/REDgamma4</option><option value="REDcolor3/REDlogFilm">REDcolor3/REDlogFilm</option><option value="REDcolor4/REDgamma3">REDcolor4/REDgamma3</option><option value="REDcolor4/REDgamma4">REDcolor4/REDgamma4</option><option value="REDcolor4/REDlogFilm">REDcolor4/REDlogFilm</option><option value="REDWideGamutRGB/Log3G10">REDWideGamutRGB/Log3G10</option><option value="S-Gamut/S-Log">S-Gamut/S-Log</option><option value="S-Gamut/S-Log2">S-Gamut/S-Log2</option><option value="S-Gamut3.Cine/S-Log3">S-Gamut3.Cine/S-Log3</option><option value="S-Gamut3/S-Log3">S-Gamut3/S-Log3</option><option value="Samsung Log">Samsung Log</option><option value="SMPTE-C">SMPTE-C</option><option value="sRGB">sRGB</option><option value="Vivo Wide Gamut/Vivo Log">Vivo Wide Gamut/Vivo Log</option><option value="XYZ (CIE)">XYZ (CIE)</option><option value="YUV">YUV</option></select></dd></div><div><dt>Output</dt><dd><select class="cor-sel" data-k="saida"><option value="Same as Timeline" selected>Same as Timeline</option><option value="ACES">ACES</option><option value="ACEScc">ACEScc</option><option value="ACEScct">ACEScct</option><option value="ACEScg">ACEScg</option><option value="Adobe RGB">Adobe RGB</option><option value="Apple Log">Apple Log</option><option value="Apple Log 2">Apple Log 2</option><option value="ARRI LogC3">ARRI LogC3</option><option value="ARRI LogC4">ARRI LogC4</option><option value="AstroDesign A-Log">AstroDesign A-Log</option><option value="Blackmagic Design 4.6K Film Gen 1">Blackmagic Design 4.6K Film Gen 1</option><option value="Blackmagic Design 4.6K Film Gen 3">Blackmagic Design 4.6K Film Gen 3</option><option value="Blackmagic Design 4.6K Video Gen 1">Blackmagic Design 4.6K Video Gen 1</option><option value="Blackmagic Design 4.6K Video Gen 3">Blackmagic Design 4.6K Video Gen 3</option><option value="Blackmagic Design 4K Film Gen 1">Blackmagic Design 4K Film Gen 1</option><option value="Blackmagic Design 4K Film Gen 3">Blackmagic Design 4K Film Gen 3</option><option value="Blackmagic Design 4K Video Gen 3">Blackmagic Design 4K Video Gen 3</option><option value="Blackmagic Design Broadcast Film Gen 4">Blackmagic Design Broadcast Film Gen 4</option><option value="Blackmagic Design Extended Video Gen 4">Blackmagic Design Extended Video Gen 4</option><option value="Blackmagic Design Extended Video Gen 5">Blackmagic Design Extended Video Gen 5</option><option value="Blackmagic Design Film Gen 1">Blackmagic Design Film Gen 1</option><option value="Blackmagic Design Film Gen 5">Blackmagic Design Film Gen 5</option><option value="Blackmagic Design Pocket 4K Film Gen 4">Blackmagic Design Pocket 4K Film Gen 4</option><option value="Blackmagic Design Pocket 6K Film Gen 4">Blackmagic Design Pocket 6K Film Gen 4</option><option value="Blackmagic Design Video Gen 4">Blackmagic Design Video Gen 4</option><option value="Blackmagic Design Video Gen 5">Blackmagic Design Video Gen 5</option><option value="Canon Cinema Gamut/Canon Log">Canon Cinema Gamut/Canon Log</option><option value="Canon Cinema Gamut/Canon Log 2">Canon Cinema Gamut/Canon Log 2</option><option value="Canon Cinema Gamut/Canon Log 3">Canon Cinema Gamut/Canon Log 3</option><option value="Cineon Film Log">Cineon Film Log</option><option value="DaVinci WG/Intermediate">DaVinci WG/Intermediate</option><option value="DCI-XYZ">DCI-XYZ</option><option value="DJI D-Gamut/D-Log">DJI D-Gamut/D-Log</option><option value="DJI D-Gamut2/D-Log2">DJI D-Gamut2/D-Log2</option><option value="DRAGONcolor/REDgamma3">DRAGONcolor/REDgamma3</option><option value="DRAGONcolor/REDgamma4">DRAGONcolor/REDgamma4</option><option value="DRAGONcolor/REDlogFilm">DRAGONcolor/REDlogFilm</option><option value="DRAGONcolor2/REDgamma3">DRAGONcolor2/REDgamma3</option><option value="DRAGONcolor2/REDgamma4">DRAGONcolor2/REDgamma4</option><option value="DRAGONcolor2/REDlogFilm">DRAGONcolor2/REDlogFilm</option><option value="Fujifilm F-Log">Fujifilm F-Log</option><option value="Fujifilm F-Log2">Fujifilm F-Log2</option><option value="Fujifilm F-Log2 C">Fujifilm F-Log2 C</option><option value="GoPro GP-Log2">GoPro GP-Log2</option><option value="Insta360 I-Log">Insta360 I-Log</option><option value="Leica L-Log">Leica L-Log</option><option value="Linear">Linear</option><option value="Nikon N-Log">Nikon N-Log</option><option value="P3-D60">P3-D60</option><option value="P3-D65">P3-D65</option><option value="P3-D65 (Scene)">P3-D65 (Scene)</option><option value="P3-D65 HLG 1000 nits">P3-D65 HLG 1000 nits</option><option value="P3-D65 ST2084 1000 nits">P3-D65 ST2084 1000 nits</option><option value="P3-D65 ST2084 2000 nits">P3-D65 ST2084 2000 nits</option><option value="P3-D65 ST2084 4000 nits">P3-D65 ST2084 4000 nits</option><option value="P3-DCI">P3-DCI</option><option value="Panasonic V-Gamut/V-Log">Panasonic V-Gamut/V-Log</option><option value="Rec.709 (Scene)">Rec.709 (Scene)</option><option value="Rec.709 Gamma 2.2">Rec.709 Gamma 2.2</option><option value="Rec.709 Gamma 2.4">Rec.709 Gamma 2.4</option><option value="Rec.709 HLG ARIB STD-B67">Rec.709 HLG ARIB STD-B67</option><option value="Rec.709-A">Rec.709-A</option><option value="Rec.2020 (Scene)">Rec.2020 (Scene)</option><option value="Rec.2020 Gamma 2.4">Rec.2020 Gamma 2.4</option><option value="Rec.2020 HLG ARIB STD-B67">Rec.2020 HLG ARIB STD-B67</option><option value="Rec.2020 ST2084 1000 nits">Rec.2020 ST2084 1000 nits</option><option value="Rec.2020 ST2084 2000 nits">Rec.2020 ST2084 2000 nits</option><option value="Rec.2020 ST2084 4000 nits">Rec.2020 ST2084 4000 nits</option><option value="Rec.2100 HLG">Rec.2100 HLG</option><option value="Rec.2100 HLG (Scene)">Rec.2100 HLG (Scene)</option><option value="Rec.2100 ST2084">Rec.2100 ST2084</option><option value="Rec.2100 ST2084 (Scene)">Rec.2100 ST2084 (Scene)</option><option value="REDcolor2/REDgamma3">REDcolor2/REDgamma3</option><option value="REDcolor2/REDgamma4">REDcolor2/REDgamma4</option><option value="REDcolor2/REDlogFilm">REDcolor2/REDlogFilm</option><option value="REDcolor3/REDgamma3">REDcolor3/REDgamma3</option><option value="REDcolor3/REDgamma4">REDcolor3/REDgamma4</option><option value="REDcolor3/REDlogFilm">REDcolor3/REDlogFilm</option><option value="REDcolor4/REDgamma3">REDcolor4/REDgamma3</option><option value="REDcolor4/REDgamma4">REDcolor4/REDgamma4</option><option value="REDcolor4/REDlogFilm">REDcolor4/REDlogFilm</option><option value="REDWideGamutRGB/Log3G10">REDWideGamutRGB/Log3G10</option><option value="S-Gamut/S-Log">S-Gamut/S-Log</option><option value="S-Gamut/S-Log2">S-Gamut/S-Log2</option><option value="S-Gamut3.Cine/S-Log3">S-Gamut3.Cine/S-Log3</option><option value="S-Gamut3/S-Log3">S-Gamut3/S-Log3</option><option value="Samsung Log">Samsung Log</option><option value="SMPTE-C">SMPTE-C</option><option value="sRGB">sRGB</option><option value="ST2084">ST2084</option><option value="ST2084 300 nit">ST2084 300 nit</option><option value="ST2084 500 nit">ST2084 500 nit</option><option value="ST2084 800 nit">ST2084 800 nit</option><option value="ST2084 1000 nit">ST2084 1000 nit</option><option value="ST2084 2000 nit">ST2084 2000 nit</option><option value="ST2084 3000 nit">ST2084 3000 nit</option><option value="ST2084 4000 nit">ST2084 4000 nit</option><option value="Vivo Wide Gamut/Vivo Log">Vivo Wide Gamut/Vivo Log</option><option value="XYZ (CIE)">XYZ (CIE)</option></select></dd></div></dl><input class="nome-tl" placeholder="Nome da timeline" maxlength="80" aria-label="Nome da timeline"><button class="btn" data-modelo="4k">Criar timeline</button></div><div class="modelo"><div class="mol-box"><svg class="mol" viewBox="0 0 96 56" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M4 13V4H13"/><path d="M83 4H92V13"/><path d="M92 43V52H83"/><path d="M13 52H4V43"/><rect x="21.1" y="12.3" width="53.8" height="31.4" rx="2" stroke-dasharray="2 3" opacity=".55"/><circle cx="48.0" cy="28.0" r="2.6" fill="currentColor" stroke="none"/><path d="M48.0 22.0V24.5M48.0 31.5V34.0M42.0 28.0H44.5M51.5 28.0H54.0" opacity=".7"/><path d="M6 28.0H90" stroke-dasharray="1 3" opacity=".35"/></svg></div><div class="mol-t">Full HD (1080p)</div><dl class="mol-specs"><div><dt>Resolução</dt><dd>1920 × 1080</dd></div><div><dt>Frame rate</dt><dd>24 fps</dd></div><div><dt>Timeline</dt><dd><select class="cor-sel" data-k="timeline"><option value="ACES">ACES</option><option value="ACEScc">ACEScc</option><option value="ACEScct">ACEScct</option><option value="ACEScg">ACEScg</option><option value="Adobe RGB">Adobe RGB</option><option value="Apple Log">Apple Log</option><option value="Apple Log 2">Apple Log 2</option><option value="ARRI LogC3">ARRI LogC3</option><option value="ARRI LogC4">ARRI LogC4</option><option value="AstroDesign A-Log">AstroDesign A-Log</option><option value="Blackmagic Design 4.6K Film Gen 1">Blackmagic Design 4.6K Film Gen 1</option><option value="Blackmagic Design 4.6K Film Gen 3">Blackmagic Design 4.6K Film Gen 3</option><option value="Blackmagic Design 4.6K Video Gen 1">Blackmagic Design 4.6K Video Gen 1</option><option value="Blackmagic Design 4.6K Video Gen 3">Blackmagic Design 4.6K Video Gen 3</option><option value="Blackmagic Design 4K Film Gen 1">Blackmagic Design 4K Film Gen 1</option><option value="Blackmagic Design 4K Film Gen 3">Blackmagic Design 4K Film Gen 3</option><option value="Blackmagic Design 4K Video Gen 3">Blackmagic Design 4K Video Gen 3</option><option value="Blackmagic Design Broadcast Film Gen 4">Blackmagic Design Broadcast Film Gen 4</option><option value="Blackmagic Design Extended Video Gen 4">Blackmagic Design Extended Video Gen 4</option><option value="Blackmagic Design Extended Video Gen 5">Blackmagic Design Extended Video Gen 5</option><option value="Blackmagic Design Film Gen 1">Blackmagic Design Film Gen 1</option><option value="Blackmagic Design Film Gen 5">Blackmagic Design Film Gen 5</option><option value="Blackmagic Design Pocket 4K Film Gen 4">Blackmagic Design Pocket 4K Film Gen 4</option><option value="Blackmagic Design Pocket 6K Film Gen 4">Blackmagic Design Pocket 6K Film Gen 4</option><option value="Blackmagic Design Video Gen 4">Blackmagic Design Video Gen 4</option><option value="Blackmagic Design Video Gen 5">Blackmagic Design Video Gen 5</option><option value="Canon Cinema Gamut/Canon Log">Canon Cinema Gamut/Canon Log</option><option value="Canon Cinema Gamut/Canon Log 2">Canon Cinema Gamut/Canon Log 2</option><option value="Canon Cinema Gamut/Canon Log 3">Canon Cinema Gamut/Canon Log 3</option><option value="Cineon Film Log">Cineon Film Log</option><option value="DaVinci WG/Intermediate">DaVinci WG/Intermediate</option><option value="DCI-XYZ">DCI-XYZ</option><option value="DJI D-Gamut/D-Log">DJI D-Gamut/D-Log</option><option value="DJI D-Gamut2/D-Log2">DJI D-Gamut2/D-Log2</option><option value="DRAGONcolor/REDgamma3">DRAGONcolor/REDgamma3</option><option value="DRAGONcolor/REDgamma4">DRAGONcolor/REDgamma4</option><option value="DRAGONcolor/REDlogFilm">DRAGONcolor/REDlogFilm</option><option value="DRAGONcolor2/REDgamma3">DRAGONcolor2/REDgamma3</option><option value="DRAGONcolor2/REDgamma4">DRAGONcolor2/REDgamma4</option><option value="DRAGONcolor2/REDlogFilm">DRAGONcolor2/REDlogFilm</option><option value="Fujifilm F-Log">Fujifilm F-Log</option><option value="Fujifilm F-Log2">Fujifilm F-Log2</option><option value="Fujifilm F-Log2 C">Fujifilm F-Log2 C</option><option value="GoPro GP-Log2">GoPro GP-Log2</option><option value="HSL">HSL</option><option value="HSV">HSV</option><option value="Insta360 I-Log">Insta360 I-Log</option><option value="Lab (CIE)">Lab (CIE)</option><option value="Leica L-Log">Leica L-Log</option><option value="Linear">Linear</option><option value="Nikon N-Log">Nikon N-Log</option><option value="P3-D60">P3-D60</option><option value="P3-D65">P3-D65</option><option value="P3-D65 (Scene)">P3-D65 (Scene)</option><option value="P3-D65 HLG 1000 nits">P3-D65 HLG 1000 nits</option><option value="P3-D65 Intermediate">P3-D65 Intermediate</option><option value="P3-D65 ST2084 1000 nits">P3-D65 ST2084 1000 nits</option><option value="P3-D65 ST2084 2000 nits">P3-D65 ST2084 2000 nits</option><option value="P3-D65 ST2084 4000 nits">P3-D65 ST2084 4000 nits</option><option value="P3-DCI">P3-DCI</option><option value="Panasonic V-Gamut/V-Log">Panasonic V-Gamut/V-Log</option><option value="Rec.709 (Scene)" selected>Rec.709 (Scene)</option><option value="Rec.709 Gamma 2.2">Rec.709 Gamma 2.2</option><option value="Rec.709 Gamma 2.4">Rec.709 Gamma 2.4</option><option value="Rec.709 HLG ARIB STD-B67">Rec.709 HLG ARIB STD-B67</option><option value="Rec.709-A">Rec.709-A</option><option value="Rec.2020 (Scene)">Rec.2020 (Scene)</option><option value="Rec.2020 Gamma 2.4">Rec.2020 Gamma 2.4</option><option value="Rec.2020 HLG ARIB STD-B67">Rec.2020 HLG ARIB STD-B67</option><option value="Rec.2020 Intermediate">Rec.2020 Intermediate</option><option value="Rec.2020 ST2084 1000 nits">Rec.2020 ST2084 1000 nits</option><option value="Rec.2020 ST2084 2000 nits">Rec.2020 ST2084 2000 nits</option><option value="Rec.2020 ST2084 4000 nits">Rec.2020 ST2084 4000 nits</option><option value="Rec.2100 HLG">Rec.2100 HLG</option><option value="Rec.2100 HLG (Scene)">Rec.2100 HLG (Scene)</option><option value="Rec.2100 ST2084">Rec.2100 ST2084</option><option value="Rec.2100 ST2084 (Scene)">Rec.2100 ST2084 (Scene)</option><option value="REDcolor2/REDgamma3">REDcolor2/REDgamma3</option><option value="REDcolor2/REDgamma4">REDcolor2/REDgamma4</option><option value="REDcolor2/REDlogFilm">REDcolor2/REDlogFilm</option><option value="REDcolor3/REDgamma3">REDcolor3/REDgamma3</option><option value="REDcolor3/REDgamma4">REDcolor3/REDgamma4</option><option value="REDcolor3/REDlogFilm">REDcolor3/REDlogFilm</option><option value="REDcolor4/REDgamma3">REDcolor4/REDgamma3</option><option value="REDcolor4/REDgamma4">REDcolor4/REDgamma4</option><option value="REDcolor4/REDlogFilm">REDcolor4/REDlogFilm</option><option value="REDWideGamutRGB/Log3G10">REDWideGamutRGB/Log3G10</option><option value="S-Gamut/S-Log">S-Gamut/S-Log</option><option value="S-Gamut/S-Log2">S-Gamut/S-Log2</option><option value="S-Gamut3.Cine/S-Log3">S-Gamut3.Cine/S-Log3</option><option value="S-Gamut3/S-Log3">S-Gamut3/S-Log3</option><option value="Samsung Log">Samsung Log</option><option value="SMPTE-C">SMPTE-C</option><option value="sRGB">sRGB</option><option value="Vivo Wide Gamut/Vivo Log">Vivo Wide Gamut/Vivo Log</option><option value="XYZ (CIE)">XYZ (CIE)</option><option value="YUV">YUV</option></select></dd></div><div><dt>Output</dt><dd><select class="cor-sel" data-k="saida"><option value="Same as Timeline" selected>Same as Timeline</option><option value="ACES">ACES</option><option value="ACEScc">ACEScc</option><option value="ACEScct">ACEScct</option><option value="ACEScg">ACEScg</option><option value="Adobe RGB">Adobe RGB</option><option value="Apple Log">Apple Log</option><option value="Apple Log 2">Apple Log 2</option><option value="ARRI LogC3">ARRI LogC3</option><option value="ARRI LogC4">ARRI LogC4</option><option value="AstroDesign A-Log">AstroDesign A-Log</option><option value="Blackmagic Design 4.6K Film Gen 1">Blackmagic Design 4.6K Film Gen 1</option><option value="Blackmagic Design 4.6K Film Gen 3">Blackmagic Design 4.6K Film Gen 3</option><option value="Blackmagic Design 4.6K Video Gen 1">Blackmagic Design 4.6K Video Gen 1</option><option value="Blackmagic Design 4.6K Video Gen 3">Blackmagic Design 4.6K Video Gen 3</option><option value="Blackmagic Design 4K Film Gen 1">Blackmagic Design 4K Film Gen 1</option><option value="Blackmagic Design 4K Film Gen 3">Blackmagic Design 4K Film Gen 3</option><option value="Blackmagic Design 4K Video Gen 3">Blackmagic Design 4K Video Gen 3</option><option value="Blackmagic Design Broadcast Film Gen 4">Blackmagic Design Broadcast Film Gen 4</option><option value="Blackmagic Design Extended Video Gen 4">Blackmagic Design Extended Video Gen 4</option><option value="Blackmagic Design Extended Video Gen 5">Blackmagic Design Extended Video Gen 5</option><option value="Blackmagic Design Film Gen 1">Blackmagic Design Film Gen 1</option><option value="Blackmagic Design Film Gen 5">Blackmagic Design Film Gen 5</option><option value="Blackmagic Design Pocket 4K Film Gen 4">Blackmagic Design Pocket 4K Film Gen 4</option><option value="Blackmagic Design Pocket 6K Film Gen 4">Blackmagic Design Pocket 6K Film Gen 4</option><option value="Blackmagic Design Video Gen 4">Blackmagic Design Video Gen 4</option><option value="Blackmagic Design Video Gen 5">Blackmagic Design Video Gen 5</option><option value="Canon Cinema Gamut/Canon Log">Canon Cinema Gamut/Canon Log</option><option value="Canon Cinema Gamut/Canon Log 2">Canon Cinema Gamut/Canon Log 2</option><option value="Canon Cinema Gamut/Canon Log 3">Canon Cinema Gamut/Canon Log 3</option><option value="Cineon Film Log">Cineon Film Log</option><option value="DaVinci WG/Intermediate">DaVinci WG/Intermediate</option><option value="DCI-XYZ">DCI-XYZ</option><option value="DJI D-Gamut/D-Log">DJI D-Gamut/D-Log</option><option value="DJI D-Gamut2/D-Log2">DJI D-Gamut2/D-Log2</option><option value="DRAGONcolor/REDgamma3">DRAGONcolor/REDgamma3</option><option value="DRAGONcolor/REDgamma4">DRAGONcolor/REDgamma4</option><option value="DRAGONcolor/REDlogFilm">DRAGONcolor/REDlogFilm</option><option value="DRAGONcolor2/REDgamma3">DRAGONcolor2/REDgamma3</option><option value="DRAGONcolor2/REDgamma4">DRAGONcolor2/REDgamma4</option><option value="DRAGONcolor2/REDlogFilm">DRAGONcolor2/REDlogFilm</option><option value="Fujifilm F-Log">Fujifilm F-Log</option><option value="Fujifilm F-Log2">Fujifilm F-Log2</option><option value="Fujifilm F-Log2 C">Fujifilm F-Log2 C</option><option value="GoPro GP-Log2">GoPro GP-Log2</option><option value="Insta360 I-Log">Insta360 I-Log</option><option value="Leica L-Log">Leica L-Log</option><option value="Linear">Linear</option><option value="Nikon N-Log">Nikon N-Log</option><option value="P3-D60">P3-D60</option><option value="P3-D65">P3-D65</option><option value="P3-D65 (Scene)">P3-D65 (Scene)</option><option value="P3-D65 HLG 1000 nits">P3-D65 HLG 1000 nits</option><option value="P3-D65 ST2084 1000 nits">P3-D65 ST2084 1000 nits</option><option value="P3-D65 ST2084 2000 nits">P3-D65 ST2084 2000 nits</option><option value="P3-D65 ST2084 4000 nits">P3-D65 ST2084 4000 nits</option><option value="P3-DCI">P3-DCI</option><option value="Panasonic V-Gamut/V-Log">Panasonic V-Gamut/V-Log</option><option value="Rec.709 (Scene)">Rec.709 (Scene)</option><option value="Rec.709 Gamma 2.2">Rec.709 Gamma 2.2</option><option value="Rec.709 Gamma 2.4">Rec.709 Gamma 2.4</option><option value="Rec.709 HLG ARIB STD-B67">Rec.709 HLG ARIB STD-B67</option><option value="Rec.709-A">Rec.709-A</option><option value="Rec.2020 (Scene)">Rec.2020 (Scene)</option><option value="Rec.2020 Gamma 2.4">Rec.2020 Gamma 2.4</option><option value="Rec.2020 HLG ARIB STD-B67">Rec.2020 HLG ARIB STD-B67</option><option value="Rec.2020 ST2084 1000 nits">Rec.2020 ST2084 1000 nits</option><option value="Rec.2020 ST2084 2000 nits">Rec.2020 ST2084 2000 nits</option><option value="Rec.2020 ST2084 4000 nits">Rec.2020 ST2084 4000 nits</option><option value="Rec.2100 HLG">Rec.2100 HLG</option><option value="Rec.2100 HLG (Scene)">Rec.2100 HLG (Scene)</option><option value="Rec.2100 ST2084">Rec.2100 ST2084</option><option value="Rec.2100 ST2084 (Scene)">Rec.2100 ST2084 (Scene)</option><option value="REDcolor2/REDgamma3">REDcolor2/REDgamma3</option><option value="REDcolor2/REDgamma4">REDcolor2/REDgamma4</option><option value="REDcolor2/REDlogFilm">REDcolor2/REDlogFilm</option><option value="REDcolor3/REDgamma3">REDcolor3/REDgamma3</option><option value="REDcolor3/REDgamma4">REDcolor3/REDgamma4</option><option value="REDcolor3/REDlogFilm">REDcolor3/REDlogFilm</option><option value="REDcolor4/REDgamma3">REDcolor4/REDgamma3</option><option value="REDcolor4/REDgamma4">REDcolor4/REDgamma4</option><option value="REDcolor4/REDlogFilm">REDcolor4/REDlogFilm</option><option value="REDWideGamutRGB/Log3G10">REDWideGamutRGB/Log3G10</option><option value="S-Gamut/S-Log">S-Gamut/S-Log</option><option value="S-Gamut/S-Log2">S-Gamut/S-Log2</option><option value="S-Gamut3.Cine/S-Log3">S-Gamut3.Cine/S-Log3</option><option value="S-Gamut3/S-Log3">S-Gamut3/S-Log3</option><option value="Samsung Log">Samsung Log</option><option value="SMPTE-C">SMPTE-C</option><option value="sRGB">sRGB</option><option value="ST2084">ST2084</option><option value="ST2084 300 nit">ST2084 300 nit</option><option value="ST2084 500 nit">ST2084 500 nit</option><option value="ST2084 800 nit">ST2084 800 nit</option><option value="ST2084 1000 nit">ST2084 1000 nit</option><option value="ST2084 2000 nit">ST2084 2000 nit</option><option value="ST2084 3000 nit">ST2084 3000 nit</option><option value="ST2084 4000 nit">ST2084 4000 nit</option><option value="Vivo Wide Gamut/Vivo Log">Vivo Wide Gamut/Vivo Log</option><option value="XYZ (CIE)">XYZ (CIE)</option></select></dd></div></dl><input class="nome-tl" placeholder="Nome da timeline" maxlength="80" aria-label="Nome da timeline"><button class="btn" data-modelo="1080">Criar timeline</button></div><div class="modelo"><div class="mol-box"><svg class="mol mol-v" viewBox="0 0 56 96" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M4 13V4H13"/><path d="M43 4H52V13"/><path d="M52 83V92H43"/><path d="M13 92H4V83"/><rect x="12.3" y="21.1" width="31.4" height="53.8" rx="2" stroke-dasharray="2 3" opacity=".55"/><circle cx="28.0" cy="48.0" r="2.6" fill="currentColor" stroke="none"/><path d="M28.0 42.0V44.5M28.0 51.5V54.0M22.0 48.0H24.5M31.5 48.0H34.0" opacity=".7"/><path d="M6 48.0H50" stroke-dasharray="1 3" opacity=".35"/></svg></div><div class="mol-t">Vertical Full HD</div><dl class="mol-specs"><div><dt>Resolução</dt><dd>1080 × 1920</dd></div><div><dt>Frame rate</dt><dd>24 fps</dd></div><div><dt>Timeline</dt><dd><select class="cor-sel" data-k="timeline"><option value="ACES">ACES</option><option value="ACEScc">ACEScc</option><option value="ACEScct">ACEScct</option><option value="ACEScg">ACEScg</option><option value="Adobe RGB">Adobe RGB</option><option value="Apple Log">Apple Log</option><option value="Apple Log 2">Apple Log 2</option><option value="ARRI LogC3">ARRI LogC3</option><option value="ARRI LogC4">ARRI LogC4</option><option value="AstroDesign A-Log">AstroDesign A-Log</option><option value="Blackmagic Design 4.6K Film Gen 1">Blackmagic Design 4.6K Film Gen 1</option><option value="Blackmagic Design 4.6K Film Gen 3">Blackmagic Design 4.6K Film Gen 3</option><option value="Blackmagic Design 4.6K Video Gen 1">Blackmagic Design 4.6K Video Gen 1</option><option value="Blackmagic Design 4.6K Video Gen 3">Blackmagic Design 4.6K Video Gen 3</option><option value="Blackmagic Design 4K Film Gen 1">Blackmagic Design 4K Film Gen 1</option><option value="Blackmagic Design 4K Film Gen 3">Blackmagic Design 4K Film Gen 3</option><option value="Blackmagic Design 4K Video Gen 3">Blackmagic Design 4K Video Gen 3</option><option value="Blackmagic Design Broadcast Film Gen 4">Blackmagic Design Broadcast Film Gen 4</option><option value="Blackmagic Design Extended Video Gen 4">Blackmagic Design Extended Video Gen 4</option><option value="Blackmagic Design Extended Video Gen 5">Blackmagic Design Extended Video Gen 5</option><option value="Blackmagic Design Film Gen 1">Blackmagic Design Film Gen 1</option><option value="Blackmagic Design Film Gen 5">Blackmagic Design Film Gen 5</option><option value="Blackmagic Design Pocket 4K Film Gen 4">Blackmagic Design Pocket 4K Film Gen 4</option><option value="Blackmagic Design Pocket 6K Film Gen 4">Blackmagic Design Pocket 6K Film Gen 4</option><option value="Blackmagic Design Video Gen 4">Blackmagic Design Video Gen 4</option><option value="Blackmagic Design Video Gen 5">Blackmagic Design Video Gen 5</option><option value="Canon Cinema Gamut/Canon Log">Canon Cinema Gamut/Canon Log</option><option value="Canon Cinema Gamut/Canon Log 2">Canon Cinema Gamut/Canon Log 2</option><option value="Canon Cinema Gamut/Canon Log 3">Canon Cinema Gamut/Canon Log 3</option><option value="Cineon Film Log">Cineon Film Log</option><option value="DaVinci WG/Intermediate">DaVinci WG/Intermediate</option><option value="DCI-XYZ">DCI-XYZ</option><option value="DJI D-Gamut/D-Log">DJI D-Gamut/D-Log</option><option value="DJI D-Gamut2/D-Log2">DJI D-Gamut2/D-Log2</option><option value="DRAGONcolor/REDgamma3">DRAGONcolor/REDgamma3</option><option value="DRAGONcolor/REDgamma4">DRAGONcolor/REDgamma4</option><option value="DRAGONcolor/REDlogFilm">DRAGONcolor/REDlogFilm</option><option value="DRAGONcolor2/REDgamma3">DRAGONcolor2/REDgamma3</option><option value="DRAGONcolor2/REDgamma4">DRAGONcolor2/REDgamma4</option><option value="DRAGONcolor2/REDlogFilm">DRAGONcolor2/REDlogFilm</option><option value="Fujifilm F-Log">Fujifilm F-Log</option><option value="Fujifilm F-Log2">Fujifilm F-Log2</option><option value="Fujifilm F-Log2 C">Fujifilm F-Log2 C</option><option value="GoPro GP-Log2">GoPro GP-Log2</option><option value="HSL">HSL</option><option value="HSV">HSV</option><option value="Insta360 I-Log">Insta360 I-Log</option><option value="Lab (CIE)">Lab (CIE)</option><option value="Leica L-Log">Leica L-Log</option><option value="Linear">Linear</option><option value="Nikon N-Log">Nikon N-Log</option><option value="P3-D60">P3-D60</option><option value="P3-D65">P3-D65</option><option value="P3-D65 (Scene)">P3-D65 (Scene)</option><option value="P3-D65 HLG 1000 nits">P3-D65 HLG 1000 nits</option><option value="P3-D65 Intermediate">P3-D65 Intermediate</option><option value="P3-D65 ST2084 1000 nits">P3-D65 ST2084 1000 nits</option><option value="P3-D65 ST2084 2000 nits">P3-D65 ST2084 2000 nits</option><option value="P3-D65 ST2084 4000 nits">P3-D65 ST2084 4000 nits</option><option value="P3-DCI">P3-DCI</option><option value="Panasonic V-Gamut/V-Log">Panasonic V-Gamut/V-Log</option><option value="Rec.709 (Scene)" selected>Rec.709 (Scene)</option><option value="Rec.709 Gamma 2.2">Rec.709 Gamma 2.2</option><option value="Rec.709 Gamma 2.4">Rec.709 Gamma 2.4</option><option value="Rec.709 HLG ARIB STD-B67">Rec.709 HLG ARIB STD-B67</option><option value="Rec.709-A">Rec.709-A</option><option value="Rec.2020 (Scene)">Rec.2020 (Scene)</option><option value="Rec.2020 Gamma 2.4">Rec.2020 Gamma 2.4</option><option value="Rec.2020 HLG ARIB STD-B67">Rec.2020 HLG ARIB STD-B67</option><option value="Rec.2020 Intermediate">Rec.2020 Intermediate</option><option value="Rec.2020 ST2084 1000 nits">Rec.2020 ST2084 1000 nits</option><option value="Rec.2020 ST2084 2000 nits">Rec.2020 ST2084 2000 nits</option><option value="Rec.2020 ST2084 4000 nits">Rec.2020 ST2084 4000 nits</option><option value="Rec.2100 HLG">Rec.2100 HLG</option><option value="Rec.2100 HLG (Scene)">Rec.2100 HLG (Scene)</option><option value="Rec.2100 ST2084">Rec.2100 ST2084</option><option value="Rec.2100 ST2084 (Scene)">Rec.2100 ST2084 (Scene)</option><option value="REDcolor2/REDgamma3">REDcolor2/REDgamma3</option><option value="REDcolor2/REDgamma4">REDcolor2/REDgamma4</option><option value="REDcolor2/REDlogFilm">REDcolor2/REDlogFilm</option><option value="REDcolor3/REDgamma3">REDcolor3/REDgamma3</option><option value="REDcolor3/REDgamma4">REDcolor3/REDgamma4</option><option value="REDcolor3/REDlogFilm">REDcolor3/REDlogFilm</option><option value="REDcolor4/REDgamma3">REDcolor4/REDgamma3</option><option value="REDcolor4/REDgamma4">REDcolor4/REDgamma4</option><option value="REDcolor4/REDlogFilm">REDcolor4/REDlogFilm</option><option value="REDWideGamutRGB/Log3G10">REDWideGamutRGB/Log3G10</option><option value="S-Gamut/S-Log">S-Gamut/S-Log</option><option value="S-Gamut/S-Log2">S-Gamut/S-Log2</option><option value="S-Gamut3.Cine/S-Log3">S-Gamut3.Cine/S-Log3</option><option value="S-Gamut3/S-Log3">S-Gamut3/S-Log3</option><option value="Samsung Log">Samsung Log</option><option value="SMPTE-C">SMPTE-C</option><option value="sRGB">sRGB</option><option value="Vivo Wide Gamut/Vivo Log">Vivo Wide Gamut/Vivo Log</option><option value="XYZ (CIE)">XYZ (CIE)</option><option value="YUV">YUV</option></select></dd></div><div><dt>Output</dt><dd><select class="cor-sel" data-k="saida"><option value="Same as Timeline" selected>Same as Timeline</option><option value="ACES">ACES</option><option value="ACEScc">ACEScc</option><option value="ACEScct">ACEScct</option><option value="ACEScg">ACEScg</option><option value="Adobe RGB">Adobe RGB</option><option value="Apple Log">Apple Log</option><option value="Apple Log 2">Apple Log 2</option><option value="ARRI LogC3">ARRI LogC3</option><option value="ARRI LogC4">ARRI LogC4</option><option value="AstroDesign A-Log">AstroDesign A-Log</option><option value="Blackmagic Design 4.6K Film Gen 1">Blackmagic Design 4.6K Film Gen 1</option><option value="Blackmagic Design 4.6K Film Gen 3">Blackmagic Design 4.6K Film Gen 3</option><option value="Blackmagic Design 4.6K Video Gen 1">Blackmagic Design 4.6K Video Gen 1</option><option value="Blackmagic Design 4.6K Video Gen 3">Blackmagic Design 4.6K Video Gen 3</option><option value="Blackmagic Design 4K Film Gen 1">Blackmagic Design 4K Film Gen 1</option><option value="Blackmagic Design 4K Film Gen 3">Blackmagic Design 4K Film Gen 3</option><option value="Blackmagic Design 4K Video Gen 3">Blackmagic Design 4K Video Gen 3</option><option value="Blackmagic Design Broadcast Film Gen 4">Blackmagic Design Broadcast Film Gen 4</option><option value="Blackmagic Design Extended Video Gen 4">Blackmagic Design Extended Video Gen 4</option><option value="Blackmagic Design Extended Video Gen 5">Blackmagic Design Extended Video Gen 5</option><option value="Blackmagic Design Film Gen 1">Blackmagic Design Film Gen 1</option><option value="Blackmagic Design Film Gen 5">Blackmagic Design Film Gen 5</option><option value="Blackmagic Design Pocket 4K Film Gen 4">Blackmagic Design Pocket 4K Film Gen 4</option><option value="Blackmagic Design Pocket 6K Film Gen 4">Blackmagic Design Pocket 6K Film Gen 4</option><option value="Blackmagic Design Video Gen 4">Blackmagic Design Video Gen 4</option><option value="Blackmagic Design Video Gen 5">Blackmagic Design Video Gen 5</option><option value="Canon Cinema Gamut/Canon Log">Canon Cinema Gamut/Canon Log</option><option value="Canon Cinema Gamut/Canon Log 2">Canon Cinema Gamut/Canon Log 2</option><option value="Canon Cinema Gamut/Canon Log 3">Canon Cinema Gamut/Canon Log 3</option><option value="Cineon Film Log">Cineon Film Log</option><option value="DaVinci WG/Intermediate">DaVinci WG/Intermediate</option><option value="DCI-XYZ">DCI-XYZ</option><option value="DJI D-Gamut/D-Log">DJI D-Gamut/D-Log</option><option value="DJI D-Gamut2/D-Log2">DJI D-Gamut2/D-Log2</option><option value="DRAGONcolor/REDgamma3">DRAGONcolor/REDgamma3</option><option value="DRAGONcolor/REDgamma4">DRAGONcolor/REDgamma4</option><option value="DRAGONcolor/REDlogFilm">DRAGONcolor/REDlogFilm</option><option value="DRAGONcolor2/REDgamma3">DRAGONcolor2/REDgamma3</option><option value="DRAGONcolor2/REDgamma4">DRAGONcolor2/REDgamma4</option><option value="DRAGONcolor2/REDlogFilm">DRAGONcolor2/REDlogFilm</option><option value="Fujifilm F-Log">Fujifilm F-Log</option><option value="Fujifilm F-Log2">Fujifilm F-Log2</option><option value="Fujifilm F-Log2 C">Fujifilm F-Log2 C</option><option value="GoPro GP-Log2">GoPro GP-Log2</option><option value="Insta360 I-Log">Insta360 I-Log</option><option value="Leica L-Log">Leica L-Log</option><option value="Linear">Linear</option><option value="Nikon N-Log">Nikon N-Log</option><option value="P3-D60">P3-D60</option><option value="P3-D65">P3-D65</option><option value="P3-D65 (Scene)">P3-D65 (Scene)</option><option value="P3-D65 HLG 1000 nits">P3-D65 HLG 1000 nits</option><option value="P3-D65 ST2084 1000 nits">P3-D65 ST2084 1000 nits</option><option value="P3-D65 ST2084 2000 nits">P3-D65 ST2084 2000 nits</option><option value="P3-D65 ST2084 4000 nits">P3-D65 ST2084 4000 nits</option><option value="P3-DCI">P3-DCI</option><option value="Panasonic V-Gamut/V-Log">Panasonic V-Gamut/V-Log</option><option value="Rec.709 (Scene)">Rec.709 (Scene)</option><option value="Rec.709 Gamma 2.2">Rec.709 Gamma 2.2</option><option value="Rec.709 Gamma 2.4">Rec.709 Gamma 2.4</option><option value="Rec.709 HLG ARIB STD-B67">Rec.709 HLG ARIB STD-B67</option><option value="Rec.709-A">Rec.709-A</option><option value="Rec.2020 (Scene)">Rec.2020 (Scene)</option><option value="Rec.2020 Gamma 2.4">Rec.2020 Gamma 2.4</option><option value="Rec.2020 HLG ARIB STD-B67">Rec.2020 HLG ARIB STD-B67</option><option value="Rec.2020 ST2084 1000 nits">Rec.2020 ST2084 1000 nits</option><option value="Rec.2020 ST2084 2000 nits">Rec.2020 ST2084 2000 nits</option><option value="Rec.2020 ST2084 4000 nits">Rec.2020 ST2084 4000 nits</option><option value="Rec.2100 HLG">Rec.2100 HLG</option><option value="Rec.2100 HLG (Scene)">Rec.2100 HLG (Scene)</option><option value="Rec.2100 ST2084">Rec.2100 ST2084</option><option value="Rec.2100 ST2084 (Scene)">Rec.2100 ST2084 (Scene)</option><option value="REDcolor2/REDgamma3">REDcolor2/REDgamma3</option><option value="REDcolor2/REDgamma4">REDcolor2/REDgamma4</option><option value="REDcolor2/REDlogFilm">REDcolor2/REDlogFilm</option><option value="REDcolor3/REDgamma3">REDcolor3/REDgamma3</option><option value="REDcolor3/REDgamma4">REDcolor3/REDgamma4</option><option value="REDcolor3/REDlogFilm">REDcolor3/REDlogFilm</option><option value="REDcolor4/REDgamma3">REDcolor4/REDgamma3</option><option value="REDcolor4/REDgamma4">REDcolor4/REDgamma4</option><option value="REDcolor4/REDlogFilm">REDcolor4/REDlogFilm</option><option value="REDWideGamutRGB/Log3G10">REDWideGamutRGB/Log3G10</option><option value="S-Gamut/S-Log">S-Gamut/S-Log</option><option value="S-Gamut/S-Log2">S-Gamut/S-Log2</option><option value="S-Gamut3.Cine/S-Log3">S-Gamut3.Cine/S-Log3</option><option value="S-Gamut3/S-Log3">S-Gamut3/S-Log3</option><option value="Samsung Log">Samsung Log</option><option value="SMPTE-C">SMPTE-C</option><option value="sRGB">sRGB</option><option value="ST2084">ST2084</option><option value="ST2084 300 nit">ST2084 300 nit</option><option value="ST2084 500 nit">ST2084 500 nit</option><option value="ST2084 800 nit">ST2084 800 nit</option><option value="ST2084 1000 nit">ST2084 1000 nit</option><option value="ST2084 2000 nit">ST2084 2000 nit</option><option value="ST2084 3000 nit">ST2084 3000 nit</option><option value="ST2084 4000 nit">ST2084 4000 nit</option><option value="Vivo Wide Gamut/Vivo Log">Vivo Wide Gamut/Vivo Log</option><option value="XYZ (CIE)">XYZ (CIE)</option></select></dd></div></dl><input class="nome-tl" placeholder="Nome da timeline" maxlength="80" aria-label="Nome da timeline"><button class="btn" data-modelo="1080v">Criar timeline</button></div></div></div>{HIST}'
            f'<footer class="rodape">criado por <a href="https://www.instagram.com/josechiecchi" target="_blank" rel="noopener">@josechiecchi</a><a class="ig" href="https://www.instagram.com/josechiecchi" target="_blank" rel="noopener" title="Instagram @josechiecchi"><svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="0.8" fill="currentColor"/></svg></a></footer>'
            f'<script>const TIPOS={_tipos_js()};</script>{JS}{JS_ABAS}</body></html>')
