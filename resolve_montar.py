# Script para a ferramenta run_script do DaVinci Resolve (MCP).
# O sandbox não lê arquivos: o Claude cola o conteúdo de roteiro_resolve.json em DADOS.
# Faz: importa (ou reaproveita) o clipe, marca capítulos e ganchos no clipe de origem
# e cria uma timeline nova com as cenas do roteiro na ordem, com marcador em cada cena
# e a cor de clipe de quem está falando.
DADOS = {}  # <- conteúdo de projetos/<nome>/roteiro_resolve.json

CORES = {"capitulo": "Blue", "gancho": "Red"}
FUNCAO_COR = {"Abertura": "Yellow", "Fechamento": "Purple"}

mp = project.GetMediaPool()


def achar_clipe(pasta, caminho, nome=None):
    for c in pasta.GetClipList() or []:
        if (nome and c.GetName() == nome) or (not nome and c.GetClipProperty("File Path") == caminho):
            return c
    for sub in pasta.GetSubFolderList() or []:
        c = achar_clipe(sub, caminho, nome)
        if c:
            return c
    return None


clipes = {}
for caminho in DADOS["arquivos"]:
    # multicam: o áudio transcrito é o do gravador, mas o corte vai no clipe multicam (mesmos segundos)
    nome_mc = DADOS.get("clipes_resolve", {}).get(caminho)
    c = achar_clipe(mp.GetRootFolder(), caminho, nome_mc)
    if not c and nome_mc:
        raise RuntimeError("Clipe multicam não encontrado: " + nome_mc)
    if not c:
        importados = mp.ImportMedia([caminho])
        c = importados[0] if importados else None
    if not c:
        raise RuntimeError("Não consegui importar " + caminho)
    clipes[caminho] = c


def fr(clipe, s):
    fps = float(clipe.GetClipProperty("FPS") or project.GetSetting("timelineFrameRate"))
    return int(round(s * fps))


# Marcadores no clipe de origem (aparecem em qualquer timeline que use o clipe)
marcados = 0
for m in DADOS.get("marcadores", []):
    clipe = clipes[m["arquivo"]]
    f = fr(clipe, m["inicio"])
    existentes = clipe.GetMarkers() or {}
    if any(x.get("name") == m["nome"][:60] for x in existentes.values()):
        continue  # já marcado numa rodada anterior
    while f in existentes:  # capítulo e gancho no mesmo frame: desloca 1 frame
        f += 1
    dur = max(1, fr(clipe, m["fim"]) - f)
    if clipe.AddMarker(f, CORES.get(m["tipo"], "Cyan"), m["nome"][:60], m.get("nota", "")[:500], dur):
        marcados += 1

# Timeline do roteiro
nome_tl = "Roteiro · " + DADOS["titulo"]
nomes = {project.GetTimelineByIndex(i + 1).GetName() for i in range(project.GetTimelineCount())}
n = 2
base = nome_tl
while nome_tl in nomes:
    nome_tl = f"{base} v{n}"
    n += 1

tl = mp.CreateEmptyTimeline(nome_tl)
project.SetCurrentTimeline(tl)
infos = []
for c in DADOS["cenas"]:
    clipe = clipes[c["arquivo"]]
    infos.append({"mediaPoolItem": clipe, "startFrame": fr(clipe, c["inicio"]), "endFrame": fr(clipe, c["fim"])})
itens = mp.AppendToTimeline(infos) or []

# Cor de cada pessoa nos clipes do roteiro (vídeo e áudio)
for tipo in ("video", "audio"):
    itens_faixa = sorted(tl.GetItemListInTrack(tipo, 1) or [], key=lambda it: it.GetStart())
    for c, item in zip(DADOS["cenas"], itens_faixa):
        if c.get("cor"):
            item.SetClipColor(c["cor"])

inicio_tl = tl.GetStartFrame()
# AppendToTimeline devolve vídeo e áudio; os marcadores seguem os clipes da V1
v1 = sorted(tl.GetItemListInTrack("video", 1) or [], key=lambda it: it.GetStart())
for c, item in zip(DADOS["cenas"], v1):
    tl.AddMarker(item.GetStart() - inicio_tl, FUNCAO_COR.get(c["funcao"], "Green"),
                 f'{c["ordem"]:02d} · {c["funcao"]}', f'{c["falante"]}: {c["texto"]}'[:500], 1)

result = {"timeline": nome_tl, "cenas": len(v1), "marcadores_nos_clipes": marcados, "cores": DADOS.get("cores")}
