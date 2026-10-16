"""Página do RoteirizaIA, com o mesmo visual do Agiliza-Zé (reaproveita o CSS de pagina_inicial.py)."""
import datetime
import html as h
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
from pagina_inicial import CSS, CSS_ABAS  # noqa: E402

CSS_EXTRA = """
.marca-topo{display:flex;justify-content:center;align-items:center;min-height:56px}
.marca-txt{font:800 30px/1 Archivo,-apple-system,sans-serif;font-stretch:125%;letter-spacing:-.01em;color:#f2f2e6!important;-webkit-text-fill-color:#f2f2e6;opacity:1!important;filter:none!important}
.marca-txt span{-webkit-text-fill-color:var(--accent)}
.marca-txt span{color:var(--accent)}
.arqs{list-style:none;margin:8px 0 0;padding:0;display:grid;gap:6px;text-transform:none;letter-spacing:0;font-weight:500}
.arqs li{display:flex;justify-content:space-between;gap:10px;align-items:center;background:var(--chip);border-radius:8px;padding:6px 10px;font-size:13px;color:var(--ink)}
.arqs li span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.arqs li button{border:0;background:transparent;color:var(--mute);cursor:pointer;font-size:14px}
.arqs li button:hover{color:#ff8552}
.escolher{display:flex;gap:10px;align-items:center;text-transform:none;letter-spacing:0;font-weight:500}
.campos .full{grid-column:1/-1}
.dl-item .nm{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.dl-item small{color:var(--mute)}
.proj{cursor:pointer}
"""

RODAPE = ('<footer class="rodape">criado por <a href="https://www.instagram.com/josechiecchi" target="_blank" rel="noopener">'
          '@josechiecchi</a><a class="ig" href="https://www.instagram.com/josechiecchi" target="_blank" rel="noopener" '
          'title="Instagram @josechiecchi"><svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" '
          'stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/>'
          '<circle cx="17.5" cy="6.5" r="0.8" fill="currentColor"/></svg></a></footer>')

PASTA_SVG = ('<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M3 6.5A1.5 1.5 0 0 1 4.5 5h4.2l2 '
             '2.2H19.5A1.5 1.5 0 0 1 21 8.7v8.8a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 17.5z" fill="currentColor"/></svg>')

ONDA_SVG = ('<svg viewBox="0 0 60 58" aria-hidden="true" fill="none" stroke="#dfe47a" stroke-width="2.4" stroke-linecap="round">'
            '<line x1="10" y1="15" x2="10" y2="43"/><line x1="18" y1="6" x2="18" y2="52"/><line x1="26" y1="11" x2="26" y2="47"/>'
            '<line x1="34" y1="3" x2="34" y2="55"/><line x1="42" y1="9" x2="42" y2="49"/><line x1="50" y1="17" x2="50" y2="41"/></svg>')


def cartoes(projetos: Path) -> str:
    """Cartões das análises prontas (mesmo formato da lista do Agiliza-Zé)."""
    pastas = []
    if projetos.exists():
        pastas = sorted((d for d in projetos.iterdir() if d.is_dir() and (d / "decupagem.html").exists()),
                        key=lambda d: (d / "decupagem.html").stat().st_mtime, reverse=True)
    out = []
    for d in pastas:
        try:
            t = json.loads((d / "transcricao.json").read_text())
            a = json.loads((d / "analise.json").read_text())
        except Exception:  # noqa: BLE001
            continue
        dur = int(t.get("duracao") or 0)
        quando = datetime.datetime.fromtimestamp((d / "decupagem.html").stat().st_mtime).strftime("%d/%m/%Y %H:%M")
        top = max(a.get("ganchos", []), key=lambda g: g.get("nota", 0), default=None)
        cenas = len((a.get("roteiro") or {}).get("cenas", []))
        frase = f"<q>“{h.escape(top['texto'])}”</q>" if top else ""
        out.append(f'<div class="proj" data-p="{h.escape(d.name)}"><div class="eyebrow">{quando}</div>'
                   f'<h2>{h.escape(a.get("titulo") or d.name)}</h2><div class="meta"><span>{dur // 3600}h{dur // 60 % 60:02d}min</span>'
                   f'<span>{len(a.get("ganchos", []))} ganchos</span><span>{cenas} cenas</span></div>{frase}</div>')
    return "".join(out) or '<div class="vazio">Nenhuma análise ainda. Escolha os arquivos acima e clique em Analisar.</div>'


def pagina(projetos: Path) -> str:
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>RoteirizaIA</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..900&display=swap">
<style>{CSS}{CSS_ABAS}{CSS_EXTRA}</style></head><body>
<header class="hero"><div class="in marca-topo"><div class="marca-txt">Roteiriza<span>IA</span></div>
<button class="atualizar-topo" onclick="location.reload()" title="Atualizar">↻</button></div></header>
<nav class="tabs"><button class="tab on" data-t="r">Roteiro</button><button class="tab" data-t="t">Trilhas</button></nav>

<section class="nova" id="tr"><div class="box"><h2>Analisar</h2>
<div class="sub">Exporte o áudio (ou o vídeo) da timeline no seu editor e escolha aqui. Pode ser WAV, MP3, M4A, MOV ou MP4.</div>
<div class="campos">
<label>Nome do projeto<input id="f-nome" placeholder="Ex.: Ana e Pedro - Cerimônia"></label>
<label>Motor da análise<select id="f-motor"><option value="gemini">Gemini (não usa créditos do Claude)</option>
<option value="claude">Claude Code</option></select></label>
<label>Duração do roteiro<select id="f-dur"><option>30 a 60 segundos (Reels/teaser)</option><option>1 a 2 minutos</option>
<option selected>3 a 5 minutos (filme curto)</option><option>6 a 8 minutos</option></select></label>
<label class="full">Arquivos de áudio ou vídeo<div class="escolher"><button class="btn sec" id="f-escolher" type="button">Escolher arquivos…</button>
<span class="sub" id="f-qtd">nenhum escolhido</span></div><ul class="arqs" id="f-lista"></ul></label>
<label class="full">Nomes (ajuda a transcrição e a análise)<input id="f-prompt" placeholder="Ex.: Noivos Ana e Pedro, padre João, filha Laura"></label>
<label class="full">Pedido extra (opcional)<textarea id="f-obs" placeholder="Ex.: foque nos votos e no discurso do pai; roteiro emocionante"></textarea></label>
</div>
<div class="go"><button class="btn" id="f-ir">▶ Analisar</button><span class="sub" id="f-msg"></span></div></div>
<div class="box" id="g-box" style="margin-top:14px"><h2>⚙ Gemini</h2>
<div class="sub">A análise pelo Gemini usa a sua chave da API do Google. Crie a chave em
<a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener" style="color:var(--accent)">aistudio.google.com/apikey</a>
e cole abaixo. Ela fica guardada nas Chaves do macOS, não em arquivo.</div>
<div class="campos">
<label class="full">Chave da API<div class="escolher"><input id="g-chave" type="password" autocomplete="off" placeholder="Cole a chave aqui" style="flex:1">
<button class="btn sec" id="g-salvar" type="button">Salvar e testar</button></div></label>
<label>Modelo<select id="g-modelo"><option>—</option></select></label>
<label>Status<div class="sub" id="g-status" style="text-transform:none;letter-spacing:0;font-weight:500">Verificando…</div></label>
</div></div>
<main class="grid" id="cartoes">{cartoes(projetos)}</main></section>

<div class="dl" id="tt" hidden>
<div class="dl-top"><button class="ic" id="d-pasta" title="Abrir a pasta de downloads">{PASTA_SVG}</button><button class="ic" id="d-atual" title="Atualizar">↻</button></div>
<div class="dl-entrada"><input id="d-url" placeholder="Cole o link do YouTube ou Instagram e aperte Enter" autocomplete="off">
<select id="d-formato"><option value="audio">Áudio (MP3)</option><option value="video">Vídeo (MP4)</option></select>
<button class="btn" id="d-ir">Baixar</button></div>
<div class="dl-msg" id="d-msg"></div>
<div class="dl-vazio" id="d-vazio"><div class="dl-icone">{ONDA_SVG}</div><div class="dl-titulo">Cole um link</div>
<div class="dl-dica">Baixe só trilhas licenciadas ou conteúdo seu.</div></div>
<div id="d-lista"></div></div>

<div class="hist" id="hist"><div class="h-top" id="h-top"><span class="seta">▶</span><span id="h-txt"></span>
<span class="mini"><i id="h-bar"></i></span><button class="limpar" id="h-limpar" title="Esconde os concluídos">Limpar</button></div>
<div id="jobs"></div></div>
{RODAPE}
<script>
const $=id=>document.getElementById(id);
const post=(url,dados)=>fetch(url,{{method:'POST',body:JSON.stringify(dados||{{}})}}).then(r=>r.json());
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{{document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('on',x===b));
  $('tr').hidden=b.dataset.t!=='r';$('tt').hidden=b.dataset.t!=='t';if(b.dataset.t==='t')downloads();}});
let ARQS=[];
function desenhar(){{$('f-qtd').textContent=ARQS.length?ARQS.length+(ARQS.length>1?' arquivos':' arquivo'):'nenhum escolhido';
  $('f-lista').innerHTML=ARQS.map((a,i)=>`<li><span title="${{esc(a)}}">${{esc(a.split('/').pop())}}</span><button data-i="${{i}}" title="Tirar">✕</button></li>`).join('');}}
$('f-lista').onclick=e=>{{const b=e.target.closest('button');if(!b)return;e.preventDefault();ARQS.splice(+b.dataset.i,1);desenhar();}};
$('f-escolher').onclick=async()=>{{const d=await post('/api/escolher');
  if(d.arquivos&&d.arquivos.length){{ARQS=ARQS.concat(d.arquivos.filter(a=>!ARQS.includes(a)));desenhar();}}}};
$('f-ir').onclick=async()=>{{$('f-msg').textContent='';
  if(!$('f-nome').value.trim()){{$('f-msg').textContent='Dê um nome ao projeto.';return;}}
  if(!ARQS.length){{$('f-msg').textContent='Escolha ao menos um arquivo.';return;}}
  $('f-ir').disabled=true;
  const d=await post('/api/analisar',{{nome:$('f-nome').value,arquivos:ARQS,duracao:$('f-dur').value,prompt:$('f-prompt').value,obs:$('f-obs').value,motor:$('f-motor').value}});
  $('f-msg').textContent=d.ok?'Análise iniciada — veja em Atividade.':'⚠︎ '+d.msg;$('f-ir').disabled=false;jobs();}};
$('cartoes').onclick=e=>{{const c=e.target.closest('.proj');if(c)post('/api/resultado',{{projeto:c.dataset.p}});}};
async function baixar(){{const url=$('d-url').value.trim();if(!url){{$('d-msg').textContent='Cole um link.';return;}}
  const d=await post('/api/baixar',{{url,formato:$('d-formato').value}});
  $('d-msg').textContent=d.ok?'Baixando — veja em Atividade.':'⚠︎ '+d.msg;if(d.ok)$('d-url').value='';jobs();}}
$('d-ir').onclick=baixar;$('d-url').onkeydown=e=>{{if(e.key==='Enter')baixar();}};
$('d-pasta').onclick=()=>post('/api/abrir_pasta');$('d-atual').onclick=downloads;
async function downloads(){{const d=await post('/api/downloads');const tem=d.arquivos&&d.arquivos.length;
  $('d-vazio').hidden=!!tem;
  $('d-lista').innerHTML=tem?d.arquivos.map(a=>`<div class="dl-item"><span class="nm">${{esc(a.nome)}}</span><small>${{(a.tamanho/1048576).toFixed(1)}} MB</small></div>`).join(''):'';}}
let ESCONDER=new Set(),ABERTO=false,CONC=0;
$('h-top').onclick=e=>{{if(e.target.id==='h-limpar')return;ABERTO=!ABERTO;$('hist').classList.toggle('aberto',ABERTO);}};
$('h-limpar').onclick=()=>{{document.querySelectorAll('#jobs .job.ok,#jobs .job.erro').forEach(j=>ESCONDER.add(j.dataset.a));jobs();}};
$('jobs').onclick=async e=>{{const b=e.target.closest('button');if(!b)return;
  if(b.dataset.acao==='abrir')await post('/api/resultado',{{projeto:b.dataset.p}});
  if(b.dataset.acao==='cancelar'){{b.disabled=true;b.textContent='Cancelando…';await post('/api/cancelar',{{arquivo:b.dataset.a}});}}
  jobs();}};
async function jobs(){{let d;try{{d=await post('/api/jobs');}}catch(e){{return;}}
  const lista=d.jobs.filter(j=>!ESCONDER.has(j._arquivo));
  const rod=lista.filter(j=>!j.fim);
  $('h-txt').innerHTML='<b>Atividade</b> · '+(rod.length?'em andamento · '+esc((rod[0].etapa||'').toLowerCase())+' '+(rod[0].pct||0)+'%':'nenhuma em andamento');
  $('h-bar').style.width=(rod.length?rod[0].pct||0:100)+'%';
  $('jobs').innerHTML=lista.map(j=>{{const pronto=j.fim&&!j.erro,erro=j.erro&&j.erro!=='cancelado';
    const pasta=(j._arquivo||'').split('/')[0],dl=(j._arquivo||'').startsWith('_sync/');
    const cls=pronto?'ok':(j.fim?'erro':'rodando');
    const acao=!j.fim?`<button class="cancel" data-acao="cancelar" data-a="${{esc(j._arquivo)}}">Cancelar</button>`
      :(pronto&&!dl?`<button data-acao="abrir" data-p="${{esc(pasta)}}">Abrir</button>`:'');
    return `<div class="job ${{cls}}" data-a="${{esc(j._arquivo)}}"><span class="pt"></span><span class="nm">${{esc(j.nome||'Tarefa')}}<small>${{esc(j.msg||'')}}${{erro?' — '+esc(j.erro):''}}</small></span>`+
      `<span class="bar"><i style="width:${{pronto?100:(j.pct||0)}}%"></i></span>${{acao}}</div>`;}}).join('');
  const conc=lista.filter(j=>j.fim&&!j.erro&&!(j._arquivo||'').startsWith('_sync/')).length;
  if(conc>CONC&&CONC!==0)location.reload();CONC=conc;
  if(!$('tt').hidden)downloads();}}
async function carregarModelos(atual){{try{{const d=await post('/api/modelos');
  if(d.ok){{$('g-modelo').innerHTML=d.modelos.map(m=>`<option ${{m===(atual||d.modelo)?'selected':''}}>${{esc(m)}}</option>`).join('');}}
  else $('g-status').textContent='⚠︎ '+d.msg;}}catch(e){{}}}}
async function config(){{const c=await post('/api/config');$('f-motor').value=c.motor;
  $('g-status').textContent=c.chave_salva?'Chave salva · modelo '+c.modelo:'Sem chave. Cole a sua chave para usar o Gemini.';
  $('g-chave').placeholder=c.chave_salva?'•••••••• (salva — cole outra para trocar)':'Cole a chave aqui';
  if(c.chave_salva)carregarModelos(c.modelo);}}
$('g-salvar').onclick=async()=>{{const k=$('g-chave').value.trim();if(!k){{$('g-status').textContent='Cole a chave primeiro.';return;}}
  $('g-salvar').disabled=true;$('g-status').textContent='Testando a chave…';
  const d=await post('/api/salvar_chave',{{chave:k}});$('g-salvar').disabled=false;$('g-chave').value='';
  $('g-status').textContent=d.ok?d.msg:'⚠︎ '+d.msg;if(d.ok)config();}};
$('g-modelo').onchange=async()=>{{await post('/api/salvar_config',{{modelo:$('g-modelo').value}});$('g-status').textContent='Modelo: '+$('g-modelo').value;}};
$('f-motor').onchange=()=>post('/api/salvar_config',{{motor:$('f-motor').value}});
config();jobs();setInterval(jobs,2500);
</script></body></html>"""
