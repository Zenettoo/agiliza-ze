"""Tipos de trabalho e seus momentos (Organizador de Momentos e análise).

Cada momento: (nome, cor de clipe do DaVinci, descrição para o Claude reconhecer pelas imagens).
"Drone" e "Revisar" entram em todos os tipos.
"""

FINAIS = [
    ("Drone", "Navy", "imagens aéreas"),
    ("Revisar", "Brown", "tela preta, tampa na lente, desfocado, teste ou impossível de identificar"),
]
CORES_LIVRES = ["Yellow", "Pink", "Green", "Apricot", "Blue", "Teal", "Orange", "Purple", "Lime", "Violet", "Olive", "Tan"]

TIPOS = {
    "casamento": ("Casamento", [
        ("Decoração", "Yellow", "detalhes do espaço, mesas, flores, igreja ou salão vazios, convites, alianças em detalhe"),
        ("Making of noiva", "Pink", "preparação da noiva: maquiagem, cabelo, vestido, sapatos, família e madrinhas com ela"),
        ("Making of noivo", "Green", "preparação do noivo: terno, gravata, relógio, abotoaduras, padrinhos com ele"),
        ("Pré-cerimônia", "Apricot", "chegada de convidados, noivo no altar esperando, cortejo, entrada"),
        ("Cerimônia", "Blue", "celebração: celebrante, votos, alianças, beijo, assinaturas, saída dos noivos"),
        ("Pós-cerimônia", "Teal", "cumprimentos, fotos com família, ensaio do casal"),
        ("Pré-festa", "Orange", "recepção, coquetel, entrada no salão"),
        ("Festa", "Purple", "pista de dança, discursos na festa, bolo, buquê, gravata, brindes"),
    ]),
    "corporativo": ("Evento corporativo", [
        ("Credenciamento e chegada", "Yellow", "recepção, credenciamento, crachás, chegada do público, fachada"),
        ("Ambientação", "Apricot", "espaço vazio, palco, estandes, logos, sinalização, detalhes de montagem"),
        ("Palestras e painéis", "Blue", "palestrante no palco, painel com debatedores, telão, plateia assistindo a fala"),
        ("Entrevistas e depoimentos", "Pink", "pessoa falando para a câmera em plano fechado, fundo desfocado"),
        ("Plateia e networking", "Green", "público conversando, trocando contatos, aplaudindo, circulando"),
        ("Coffee break", "Orange", "café, comida, mesas de apoio, intervalo"),
        ("Premiação e homenagens", "Purple", "entrega de troféus, placas, homenageados no palco, fotos oficiais"),
        ("Show e confraternização", "Violet", "show, banda, DJ, jantar, festa de encerramento"),
    ]),
    "institucional": ("Vídeo institucional", [
        ("Entrevistas e depoimentos", "Pink", "pessoa falando para a câmera, entrevista sentada, plano fechado"),
        ("Equipe trabalhando", "Green", "colaboradores em ação, reuniões, operação, produção, escritório em uso"),
        ("Estrutura externa", "Yellow", "fachada, prédio, logotipo externo, estacionamento, entorno"),
        ("Ambientes internos", "Apricot", "salas, recepção, linha de produção, laboratório, espaços vazios"),
        ("Produtos e detalhes", "Orange", "produtos, máquinas, telas, detalhes em close, embalagens"),
        ("Atendimento e clientes", "Blue", "atendimento, clientes, pacientes, alunos, interação com o público"),
        ("Cenas de apoio", "Teal", "imagens de cobertura sem foco específico, lifestyle, timelapses"),
    ]),
    "aniversario": ("15 anos / aniversário", [
        ("Decoração", "Yellow", "mesas, bolo, painel, flores, espaço vazio"),
        ("Making of", "Pink", "preparação: maquiagem, cabelo, vestido"),
        ("Recepção", "Apricot", "chegada de convidados, coquetel"),
        ("Cerimonial e valsa", "Blue", "entrada, valsa, troca do sapato, velas, cerimonial"),
        ("Homenagens e discursos", "Purple", "discursos, homenagens da família, vídeo de homenagem"),
        ("Festa", "Orange", "pista de dança, brincadeiras, parabéns, bolo"),
    ]),
    "formatura": ("Formatura", [
        ("Decoração", "Yellow", "palco, salão, mesas, detalhes"),
        ("Making of", "Pink", "preparação dos formandos"),
        ("Colação e cerimônia", "Blue", "beca, entrada dos formandos, mesa de autoridades, entrega de diplomas"),
        ("Discursos e juramento", "Purple", "orador, juramento, paraninfo, discursos"),
        ("Homenagens", "Teal", "homenagens a pais e professores, abraços, fotos de turma"),
        ("Baile", "Orange", "festa, pista, valsa com os pais, show"),
    ]),
    "show": ("Show / música", [
        ("Bastidores", "Green", "camarim, preparação, equipe técnica"),
        ("Passagem de som", "Yellow", "ensaio, palco sem público, ajustes técnicos"),
        ("Público", "Apricot", "plateia, fãs, chegada, reações"),
        ("Show", "Purple", "artista no palco, apresentação, luzes"),
        ("Detalhes do palco", "Teal", "instrumentos, equipamentos, luzes em close"),
    ]),
    "estetica_odonto": ("Estética / Odonto", [
        ("Recepção e chegada", "Yellow", "paciente chegando, recepção, fachada, sala de espera, cadeira vazia"),
        ("Consulta e avaliação", "Blue", "conversa com o profissional, explicação do tratamento, análise do sorriso"),
        ("Procedimento", "Pink", "mãos do profissional em ação, equipamentos, detalhes técnicos, close controlado"),
        ("Antes e depois", "Green", "resultado comparado, close do sorriso ou do rosto, luz de estúdio"),
        ("Depoimento do paciente", "Orange", "paciente falando para a câmera, fundo desfocado, emoção e confiança"),
        ("Ambiente e equipe", "Teal", "consultório, equipe trabalhando, instrumentos organizados, planos de apoio"),
    ]),
    "imobiliario": ("Imobiliário", [
        ("Fachada e externa", "Yellow", "fachada, entrada, área externa, entorno"),
        ("Áreas comuns", "Green", "piscina, academia, salão de festas, lazer"),
        ("Interiores", "Blue", "sala, quartos, cozinha, banheiros"),
        ("Detalhes e acabamentos", "Apricot", "acabamentos, metais, iluminação, detalhes em close"),
    ]),
}


def momentos(tipo, personalizados=""):
    """Lista [(nome, cor, descrição)] do tipo, com Drone e Revisar no fim. 'personalizado' usa a lista digitada."""
    if tipo == "personalizado" and personalizados.strip():
        nomes = [n.strip() for n in personalizados.replace(";", ",").split(",") if n.strip()]
        base = [(n, CORES_LIVRES[i % len(CORES_LIVRES)], "") for i, n in enumerate(nomes)]
    else:
        base = TIPOS.get(tipo, TIPOS["casamento"])[1]
    return base + [m for m in FINAIS if m[0] not in {b[0] for b in base}]


def nome_tipo(tipo):
    return "Personalizado" if tipo == "personalizado" else TIPOS.get(tipo, TIPOS["casamento"])[0]
