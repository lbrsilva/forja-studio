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
}

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
        "cor": "#5B8DEF",
        "voz": {"voz_id": "", "idioma": "pt", "velocidade": 1.0, "pausa": 0.35},
        "producao": {
            "duracao_alvo": 45,
            "cenas": 6,
            "legendas": True,
            "preset_imagem": "z_image_turbo",
            "qualidade": "Normal",
            "estilo": "",
            "formato_base": "9:16",
            "falar_cenas": True,
        },
        "formatos": [dict(f, ativo=True) for f in FORMATOS_PADRAO],
        "publicacao": {
            "automatico": False,
            "horarios": ["06:00"],
            "plataformas": ["youtube", "tiktok", "instagram"],
            "visibilidade": "public",
            "hashtags": [],
        },
        "analytics": {"moeda": "BRL", "meta_receita": 0},
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


def _canais_brutos():
    d = _ler(ARQ_CANAIS, [])
    return d if isinstance(d, list) else []


def listar(incluir_arquivados=False):
    canais = [c for c in _canais_brutos() if incluir_arquivados or not c.get("arquivado")]
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
    for c in _canais_brutos():
        if c.get("id") == cid:
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
    """Um arquivo por tamanho/legenda, nao um por plataforma: Stories e Reels usam o mesmo 9:16."""
    vistos, saida = set(), []
    for f in formatos_ativos(canal):
        chave = (int(f.get("largura") or 1080), int(f.get("altura") or 1920), bool(f.get("legendas", True)))
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append(dict(f))
    return saida


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
        saida.append({"nome": nome,
                      "descricao": str(p.get("descricao") or "").strip()[:800],
                      "visual": str(p.get("visual") or "").strip()[:800]})
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
