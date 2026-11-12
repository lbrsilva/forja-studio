"""Canais — cada canal com o seu mundo, a sua voz e a sua esteira.

O que muda em relacao ao canal.py antigo: la a pasta vinha de uma preferencia global e
todo video era do mesmo canal. Aqui cada canal tem contexto proprio (tema, personagens,
regras, identidade visual), formatos proprios (16:9 do YouTube, 9:16 de Stories/TikTok)
e producoes guardadas dentro da pasta dele. O historico do estudio nao e tocado: as
producoes deste modulo vivem em DADOS/canais/<id>/producoes/.
"""
import json
import os
import re
import shutil
import time
import unicodedata
import uuid
from pathlib import Path

AQUI = Path(__file__).resolve().parent
DADOS = Path(os.environ["ESTUDIO_DADOS"]) if os.environ.get("ESTUDIO_DADOS") else AQUI
RAIZ = DADOS / "canais"
ARQ_CANAIS = RAIZ / "canais.json"
ARQ_SEGREDOS = RAIZ / "segredos.json"
ARQ_AGENDA = RAIZ / "agenda.json"
LIXEIRA = RAIZ / "_arquivados"

PLATAFORMAS = {
    "youtube": "YouTube",
    "tiktok": "TikTok",
    "instagram": "Instagram",
    "facebook": "Facebook",
}

ESTILOS = [
    {"id": "auto", "nome": "Automático", "instrucao": "", "prompt": ""},
    {"id": "papel", "nome": "Papel", "instrucao": "estética de recorte de papel",
     "prompt": "paper cutout collage, layered textured paper, soft shadows, handmade look"},
    {"id": "lapis", "nome": "Lápis", "instrucao": "desenho a lápis",
     "prompt": "hand-drawn graphite pencil sketch, cross-hatching, white paper, detailed linework"},
    {"id": "pixel", "nome": "Pixel", "instrucao": "pixel art",
     "prompt": "pixel art, 16-bit, crisp pixels, limited palette, retro game look"},
    {"id": "pincel", "nome": "Pincel", "instrucao": "pintura a pincel",
     "prompt": "expressive brush painting, visible strokes, textured canvas, rich color"},
    {"id": "palavra", "nome": "Palavra animada", "instrucao": "palavras animadas em destaque",
     "prompt": "kinetic typography, bold animated words, clean background, graphic design, strong contrast"},
    {"id": "3d", "nome": "3D", "instrucao": "3D estilizado",
     "prompt": "3D render, cinematic lighting, stylized characters, depth of field, polished materials"},
    {"id": "e_se", "nome": "E se...", "instrucao": "gancho 'E se...' com clima de documentário",
     "prompt": "documentary what-if visual, dramatic reenactment, cinematic realism, archival feeling"},
    {"id": "novelinha", "nome": "Novelinha", "instrucao": "novelinha com ganchos e coadjuvantes",
     "prompt": "telenovela still, dramatic lighting, expressive characters, colorful set, cliffhanger mood"},
    {"id": "anime", "nome": "Anime", "instrucao": "anime",
     "prompt": "anime style, expressive eyes, dynamic pose, cel shading, detailed background"},
    {"id": "manga", "nome": "Mangá", "instrucao": "mangá em preto e branco",
     "prompt": "manga style, black and white inking, screentone, dramatic panel composition"},
    {"id": "aquarela", "nome": "Aquarela", "instrucao": "aquarela",
     "prompt": "watercolor painting, soft washes, paper texture, delicate color bleeding"},
    {"id": "grafite", "nome": "Grafite", "instrucao": "grafite urbano",
     "prompt": "urban graffiti art, spray paint, bold outlines, street wall texture"},
    {"id": "quadrinhos", "nome": "Quadrinhos", "instrucao": "quadrinhos",
     "prompt": "comic book illustration, bold ink outlines, halftone dots, dynamic action"},
    {"id": "cyberpunk", "nome": "Cyberpunk", "instrucao": "cyberpunk",
     "prompt": "cyberpunk, neon city, rain reflections, futuristic technology, dramatic contrast"},
    {"id": "vintage", "nome": "Vintage", "instrucao": "vintage",
     "prompt": "vintage photography, faded film grain, warm sepia tones, retro atmosphere"},
    {"id": "noir", "nome": "Noir", "instrucao": "cinema noir",
     "prompt": "film noir, black and white, hard shadows, venetian blind light, moody mystery"},
    {"id": "stop_motion", "nome": "Stop motion", "instrucao": "stop motion",
     "prompt": "stop motion animation still, handmade miniature set, clay textures, tiny scale"},
    {"id": "neon", "nome": "Neon", "instrucao": "neon",
     "prompt": "neon lights, glowing outlines, dark background, vivid magenta and cyan palette"},
    {"id": "origami", "nome": "Origami", "instrucao": "origami",
     "prompt": "origami paper art, folded geometric shapes, clean background, soft studio light"},
    {"id": "colagem", "nome": "Colagem", "instrucao": "colagem",
     "prompt": "mixed media collage, torn paper, magazine cutouts, layered textures"},
    {"id": "minimalista", "nome": "Minimalista", "instrucao": "minimalista",
     "prompt": "minimalist illustration, flat shapes, limited palette, generous negative space"},
    {"id": "terror", "nome": "Terror", "instrucao": "terror",
     "prompt": "horror atmosphere, low key lighting, unsettling shadows, suspenseful composition"},
    {"id": "comedia", "nome": "Comédia", "instrucao": "comédia",
     "prompt": "comedic illustration, exaggerated expressions, bright colors, playful energy"},
    {"id": "epico", "nome": "Épico", "instrucao": "épico",
     "prompt": "epic cinematic scale, dramatic sky, vast landscape, heroic composition"},
    {"id": "documentario", "nome": "Documentário", "instrucao": "documentário",
     "prompt": "documentary photography, natural light, candid framing, realistic texture"},
    {"id": "adulto", "nome": "Adulto (18+)", "instrucao": "drama adulto, sensual e elegante, sem nudez explícita",
     "prompt": "mature adult drama, sensual elegant atmosphere, cinematic lighting, adults only, no explicit nudity"},
]


def estilo_de(canal, escolhido=None):
    eid = escolhido or ((canal or {}).get("producao") or {}).get("estilo") or "auto"
    for e in ESTILOS:
        if e["id"] == eid:
            return e
    return ESTILOS[0]


FORMATOS_PADRAO = [
    {"id": "youtube-horizontal", "nome": "YouTube horizontal", "plataforma": "youtube",
     "proporcao": "16:9", "largura": 1920, "altura": 1080, "legendas": False},
    {"id": "youtube-shorts", "nome": "YouTube Shorts", "plataforma": "youtube",
     "proporcao": "9:16", "largura": 1080, "altura": 1920, "legendas": True},
    {"id": "instagram-reels", "nome": "Instagram Reels", "plataforma": "instagram",
     "proporcao": "9:16", "largura": 1080, "altura": 1920, "legendas": True},
    {"id": "instagram-stories", "nome": "Instagram Stories", "plataforma": "instagram",
     "proporcao": "9:16", "largura": 1080, "altura": 1920, "legendas": True},
    {"id": "tiktok", "nome": "TikTok", "plataforma": "tiktok",
     "proporcao": "9:16", "largura": 1080, "altura": 1920, "legendas": True},
    {"id": "facebook-video", "nome": "Facebook Reels", "plataforma": "facebook",
     "proporcao": "9:16", "largura": 1080, "altura": 1920, "legendas": True},
]

CONTEXTO_PADRAO = {
    "tema": "",
    "publico": "",
    "tom": "",
    "idioma": "pt",
    "personagens": [],
    "identidade_visual": "",
    "regras": [],
    "nao_fazer": [],
    "referencias": [],
    "chamada_final": "",
    "hashtags": [],
    "atualizado": 0,
}


def _agora():
    return int(time.time())


def _slug(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:48] or "canal"


def _id():
    return "c" + uuid.uuid4().hex[:8]


def _ler(arq, padrao):
    try:
        d = json.loads(arq.read_text(encoding="utf-8"))
        return d
    except (OSError, ValueError):
        return padrao() if callable(padrao) else padrao


def _gravar(arq, dados, privado=False):
    arq.parent.mkdir(parents=True, exist_ok=True)
    tmp = arq.with_name(arq.name + ".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, arq)
    if privado:
        try:
            os.chmod(arq, 0o600)
        except OSError:
            pass


def _canal_padrao(nome, **extra):
    c = {
        "id": _id(),
        "nome": (nome or "Canal sem nome").strip()[:80],
        "slug": _slug(nome),
        "criado": _agora(),
        "atualizado": _agora(),
        "arquivado": False,
        "_migracao_facebook": True,
        "cor": "#5B8DEF",
        "voz": {"voz_id": "", "idioma": "pt", "velocidade": 1.0, "pausa": 0.35},
        "producao": {
            "duracao_alvo": 45,
            "cenas": 6,
            "legendas": True,
            "preset_imagem": "z_image_turbo",
            "qualidade": "Normal",
            "estilo": "auto",
            "formato_base": "9:16",
            "imagens_por_formato": "auto",
            "falar_cenas": True,
        },
        "formatos": [dict(f, ativo=True) for f in FORMATOS_PADRAO],
        "publicacao": {
            "automatico": False,
            "horarios": ["06:00"],
            "plataformas": ["youtube", "tiktok", "instagram", "facebook"],
            "visibilidade": "public",
            "aprovacao_obrigatoria": True,
            "hashtags": [],
        },
        "analytics": {"moeda": "BRL", "meta_receita": 0, "automatico": True},
    }
    c.update(extra)
    return c


def pasta_canal(cid):
    return RAIZ / re.sub(r"[^a-zA-Z0-9_-]", "", cid)


def _pasta_canal(cid):
    return pasta_canal(cid)


def _contexto_arq(cid):
    return _pasta_canal(cid) / "contexto.json"


def _producoes_dir(cid):
    return _pasta_canal(cid) / "producoes"


def pasta_producao(cid, pid):
    return _producoes_dir(cid) / re.sub(r"[^a-zA-Z0-9_-]", "", pid)


def pasta_retratos(cid):
    return pasta_canal(cid) / "personagens"


def retratos(cid):
    d = _ler(pasta_retratos(cid) / "retratos.json", {})
    if not isinstance(d, dict):
        return {}
    pasta = pasta_retratos(cid)
    return {nome: arq for nome, arq in d.items()
            if isinstance(arq, str) and (pasta / Path(arq).name).is_file()}


def salvar_retrato(cid, nome, arquivo):
    pasta = pasta_retratos(cid)
    pasta.mkdir(parents=True, exist_ok=True)
    d = retratos(cid)
    d[str(nome)] = Path(arquivo).name
    _gravar(pasta / "retratos.json", d)
    return d


def _canais_brutos():
    d = _ler(ARQ_CANAIS, [])
    return d if isinstance(d, list) else []


def _migrar_facebook(c):
    """Canais antigos ganham o formato e a plataforma Facebook uma vez só."""
    if c.get("_migracao_facebook"):
        return False
    mudou = False
    formatos = c.get("formatos") or []
    if not any(f.get("plataforma") == "facebook" for f in formatos):
        modelo = next((f for f in FORMATOS_PADRAO if f["id"] == "facebook-video"), None)
        if modelo:
            formatos.append(dict(modelo, ativo=True))
            c["formatos"] = formatos
            mudou = True
    pub = c.setdefault("publicacao", {})
    plataformas = pub.setdefault("plataformas", [])
    if "facebook" not in plataformas:
        plataformas.append("facebook")
        mudou = True
    pub["aprovacao_obrigatoria"] = True
    c["_migracao_facebook"] = True
    return True


def listar(incluir_arquivados=False):
    todos = _canais_brutos()
    mudou = False
    for c in todos:
        mudou = _migrar_facebook(c) or mudou
    if mudou:
        _gravar(ARQ_CANAIS, todos)
    canais = [c for c in todos if incluir_arquivados or not c.get("arquivado")]
    for c in canais:
        pasta = _pasta_canal(c["id"])
        c["_pasta"] = str(pasta)
        try:
            c["_producoes"] = sum(1 for d in _producoes_dir(c["id"]).iterdir()
                                  if d.is_dir() and (d / "producao.json").is_file())
        except OSError:
            c["_producoes"] = 0
        c["_personagens"] = len((_ler(_contexto_arq(c["id"]), CONTEXTO_PADRAO.copy())
                                 or {}).get("personagens") or [])
    return canais


def obter(cid):
    todos = _canais_brutos()
    for c in todos:
        if c.get("id") == cid:
            if _migrar_facebook(c):
                _gravar(ARQ_CANAIS, todos)
            return c
    return None


def criar(nome, **extra):
    c = _canal_padrao(nome, **extra)
    canais = _canais_brutos()
    if any(x.get("id") == c["id"] for x in canais):
        c["id"] = _id()
    canais.append(c)
    _gravar(ARQ_CANAIS, canais)
    _pasta_canal(c["id"]).mkdir(parents=True, exist_ok=True)
    _producoes_dir(c["id"]).mkdir(parents=True, exist_ok=True)
    _gravar(_contexto_arq(c["id"]), dict(CONTEXTO_PADRAO, atualizado=_agora()))
    return c


_CAMPOS = {"nome", "slug", "cor", "voz", "producao", "formatos", "publicacao", "analytics", "arquivado"}


def atualizar(cid, campos):
    canais = _canais_brutos()
    for i, c in enumerate(canais):
        if c.get("id") != cid:
            continue
        for k, v in (campos or {}).items():
            if k not in _CAMPOS:
                continue
            if isinstance(v, dict) and isinstance(c.get(k), dict):
                c[k] = {**c[k], **v}
            else:
                c[k] = v
        if isinstance(c.get("nome"), str):
            c["nome"] = c["nome"].strip()[:80]
            c["slug"] = _slug(c["nome"])
        c["atualizado"] = _agora()
        canais[i] = c
        _gravar(ARQ_CANAIS, canais)
        return c
    raise KeyError("Canal não encontrado.")


def arquivar(cid):
    canais = _canais_brutos()
    for c in canais:
        if c.get("id") == cid:
            c["arquivado"] = True
            c["atualizado"] = _agora()
            _gravar(ARQ_CANAIS, canais)
            return {"arquivado": True, "id": cid}
    raise KeyError("Canal não encontrado.")


def formatos_ativos(canal):
    lista = [f for f in (canal.get("formatos") or []) if f.get("ativo", True)]
    return lista or [dict(f, ativo=True) for f in FORMATOS_PADRAO if f["id"] == "tiktok"]


def formato_por_id(canal, fid):
    for f in canal.get("formatos") or []:
        if f.get("id") == fid:
            return f
    return None


def formatos_distintos(canal):
    """Um arquivo por proporção e decisão de legenda. Mesma proporção em tamanhos diferentes
    vira o MAIOR tamanho: não faz sentido renderizar 720x1280 e 1080x1920 do mesmo vídeo."""
    return list(formatos_representantes(canal).values())


def chave_formato(f):
    try:
        razao = round(float(f.get("largura") or 1080) / float(f.get("altura") or 1920), 4)
    except (TypeError, ValueError, ZeroDivisionError):
        razao = round(1080 / 1920, 4)
    return (razao, bool(f.get("legendas", True)))


def _area(f):
    try:
        return int(f.get("largura") or 0) * int(f.get("altura") or 0)
    except (TypeError, ValueError):
        return 0


def formatos_representantes(canal):
    reps = {}
    for f in formatos_ativos(canal):
        k = chave_formato(f)
        if k not in reps or _area(f) > _area(reps[k]):
            reps[k] = dict(f)
    return reps


def proporcao_de(f):
    try:
        w = float(f.get("largura") or 1080)
        h = float(f.get("altura") or 1920)
    except (TypeError, ValueError):
        return "9:16"
    r = w / h
    for nome, alvo in (("16:9", 16 / 9), ("9:16", 9 / 16), ("1:1", 1.0)):
        if abs(r - alvo) < 0.03:
            return nome
    return "9:16" if h >= w else "16:9"


def grupos_de_imagem(canal, formatos, modo=None):
    """Agrupa os formatos pela proporção em que a imagem precisa ser gerada.

    modo:
      auto   -> uma imagem por proporção ativa (padrão)
      unico  -> uma imagem só, reaproveitada com fundo desfocado
      9:16, 16:9, 1:1 -> força uma proporção
    """
    modo = modo or ((canal.get("producao") or {}).get("imagens_por_formato") or "auto")
    escolhidos = list(formatos or [])
    if not escolhidos:
        escolhidos = formatos_ativos(canal)
    if modo == "unico":
        contagem = {}
        for f in escolhidos:
            p = proporcao_de(f)
            contagem[p] = contagem.get(p, 0) + 1
        base = max(contagem, key=lambda p: (contagem[p], 1 if p == "9:16" else 0))
        return {base: escolhidos}
    if modo in ("9:16", "16:9", "1:1"):
        return {modo: escolhidos}
    grupos = {}
    for f in escolhidos:
        grupos.setdefault(proporcao_de(f), []).append(f)
    return grupos


def personagens_disponiveis(cid, limite=40):
    """Personagens do contexto + os que já apareceram em produções deste canal."""
    saida, vistos = [], set()

    def add(p, origem="canal", producao_id=""):
        if isinstance(p, str):
            p = {"nome": p}
        if not isinstance(p, dict):
            return
        nome = str(p.get("nome") or "").strip()[:60]
        chave = nome.lower()
        if not nome or chave in vistos:
            return
        vistos.add(chave)
        saida.append({"nome": nome,
                      "descricao": str(p.get("descricao") or "").strip()[:800],
                      "visual": str(p.get("visual") or "").strip()[:800],
                      "papel": str(p.get("papel") or "principal").strip().lower(),
                      "origem": origem, "producao_id": producao_id})

    for p in contexto(cid).get("personagens") or []:
        add(p, "contexto do canal")
    for prod in lista_producoes(cid):
        for p in (prod.get("plano") or {}).get("personagens") or []:
            add(p, prod.get("titulo") or "vídeo", prod.get("id") or "")
        if len(saida) >= limite:
            break
    return saida[:limite]


def contexto(cid):
    d = _ler(_contexto_arq(cid), None)
    if not isinstance(d, dict):
        d = dict(CONTEXTO_PADRAO)
    return {**CONTEXTO_PADRAO, **d}


def gravar_contexto(cid, novos):
    atual = contexto(cid)
    for k, v in (novos or {}).items():
        if k not in CONTEXTO_PADRAO:
            continue
        if k == "personagens":
            atual[k] = personagens_validos(v)
            continue
        if isinstance(CONTEXTO_PADRAO[k], list) and not isinstance(v, list):
            continue
        if isinstance(CONTEXTO_PADRAO[k], str) and not isinstance(v, str):
            continue
        atual[k] = v
    atual["atualizado"] = _agora()
    _gravar(_contexto_arq(cid), atual)
    return atual


def personagens_validos(lista):
    saida, vistos = [], set()
    for p in lista or []:
        if isinstance(p, str):
            p = {"nome": p, "descricao": "", "visual": ""}
        if not isinstance(p, dict):
            continue
        nome = str(p.get("nome") or "").strip()[:60]
        if not nome or nome.lower() in vistos:
            continue
        vistos.add(nome.lower())
        papel = str(p.get("papel") or "principal").strip().lower()
        if papel not in ("principal", "coadjuvante", "figurante"):
            papel = "principal"
        saida.append({"nome": nome,
                      "descricao": str(p.get("descricao") or "").strip()[:800],
                      "visual": str(p.get("visual") or "").strip()[:800],
                      "papel": papel})
    return saida


def _segredos():
    d = _ler(ARQ_SEGREDOS, {})
    return d if isinstance(d, dict) else {}


def segredos():
    return _segredos()


def credenciais(cid, plataforma=None):
    d = _segredos().get(cid) or {}
    if plataforma:
        return d.get(plataforma) or {}
    return d


def gravar_credenciais(cid, plataforma, campos):
    if plataforma not in PLATAFORMAS:
        raise ValueError("Plataforma desconhecida.")
    todos = _segredos()
    atual = todos.setdefault(cid, {})
    p = atual.setdefault(plataforma, {})
    for k, v in (campos or {}).items():
        if v is None:
            continue
        p[str(k)] = str(v).strip()
    _gravar(ARQ_SEGREDOS, todos, privado=True)
    return _mascarar(p)


def estado_credenciais(cid):
    d = credenciais(cid)
    res = {}
    for pid, rotulo in PLATAFORMAS.items():
        p = d.get(pid) or {}
        if pid == "youtube":
            ok = bool(p.get("client_id") and p.get("client_secret") and p.get("refresh_token"))
        elif pid == "tiktok":
            ok = bool(p.get("access_token"))
        elif pid == "facebook":
            ok = bool(p.get("page_id") and p.get("access_token"))
        else:
            ok = bool(p.get("access_token") and p.get("ig_user_id"))
        res[pid] = {"rotulo": rotulo, "configurado": ok,
                    "detalhe": _mascarar(p)}
    return res


def _mascarar(p):
    if not isinstance(p, dict):
        return {}
    saida = {}
    for k, v in p.items():
        s = str(v or "")
        if any(x in k.lower() for x in ("token", "secret", "key", "password")):
            saida[k] = ("•" * min(8, len(s))) if s else ""
        else:
            saida[k] = s
    return saida


# ------------------------------------------------------------------ agenda de publicação
def _agenda_bruta():
    d = _ler(ARQ_AGENDA, [])
    return d if isinstance(d, list) else []


def _agenda_gravar(lista):
    _gravar(ARQ_AGENDA, lista)


def agenda_listar(cid=None):
    lista = _agenda_bruta()
    if cid:
        lista = [a for a in lista if a.get("canal_id") == cid]
    return sorted(lista, key=lambda a: (a.get("quando") or 0))


def agendar(cid, producao_id, formato_id, video, plataformas, quando, meta):
    item = {
        "id": "a" + uuid.uuid4().hex[:8],
        "canal_id": cid,
        "producao_id": producao_id,
        "formato_id": formato_id,
        "video": str(video),
        "plataformas": [p for p in (plataformas or []) if p in PLATAFORMAS],
        "quando": int(quando),
        "titulo": str((meta or {}).get("titulo") or "")[:100],
        "descricao": str((meta or {}).get("descricao") or "")[:5000],
        "hashtags": [str(h) for h in ((meta or {}).get("hashtags") or [])][:30],
        "visibilidade": str((meta or {}).get("visibilidade") or "public"),
        "estado": "agendado",
        "tentativas": 0,
        "criado": _agora(),
        "ultima_tentativa": 0,
        "resultados": {},
    }
    lista = _agenda_bruta()
    lista.append(item)
    _agenda_gravar(lista)
    return item


def agenda_obter(aid):
    for a in _agenda_bruta():
        if a.get("id") == aid:
            return a
    return None


def agenda_atualizar(aid, campos):
    lista = _agenda_bruta()
    for i, a in enumerate(lista):
        if a.get("id") == aid:
            a.update(campos or {})
            lista[i] = a
            _agenda_gravar(lista)
            return a
    raise KeyError("Agendamento não encontrado.")


def agenda_remover(aid):
    lista = [a for a in _agenda_bruta() if a.get("id") != aid]
    _agenda_gravar(lista)
    return {"removido": aid}


def agenda_devidos(agora=None, intervalo_retry=600):
    agora = int(agora or time.time())
    saida = []
    for a in _agenda_bruta():
        if a.get("estado") not in ("agendado", "parcial"):
            continue
        if int(a.get("quando") or 0) > agora:
            continue
        if a.get("estado") == "parcial" and agora - int(a.get("ultima_tentativa") or 0) < intervalo_retry:
            continue
        saida.append(a)
    return saida


def recuperar_agenda(limite=1800):
    """Publicação interrompida no meio (o estúdio caiu) volta para a fila em vez de ficar presa."""
    agora = int(time.time())
    lista = _agenda_bruta()
    mudou = False
    for a in lista:
        if a.get("estado") == "executando" and agora - int(a.get("ultima_tentativa") or 0) > limite:
            a["estado"] = "agendado"
            mudou = True
    if mudou:
        _agenda_gravar(lista)
    return mudou


# ------------------------------------------------------------------ produções
def lista_producoes(cid):
    pasta = _producoes_dir(cid)
    if not pasta.is_dir():
        return []
    itens = []
    for d in pasta.iterdir():
        arq = d / "producao.json"
        if d.is_dir() and arq.is_file():
            p = _ler(arq, None)
            if isinstance(p, dict):
                itens.append(p)
    itens.sort(key=lambda p: p.get("criado") or 0, reverse=True)
    return itens


def ler_producao(cid, pid):
    arq = pasta_producao(cid, pid) / "producao.json"
    p = _ler(arq, None)
    if not isinstance(p, dict):
        raise KeyError("Produção não encontrada.")
    return p


def gravar_producao(cid, pid, producao):
    arq = pasta_producao(cid, pid) / "producao.json"
    if not arq.parent.is_dir():
        raise KeyError("Produção não encontrada.")
    _gravar(arq, producao)
    return producao
