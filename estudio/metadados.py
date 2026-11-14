"""Título, descrição e hashtags por plataforma, a partir do roteiro."""

import json
import re

import roteirista

PLATAFORMAS = ("youtube", "tiktok", "instagram", "facebook")
LIMITES = {
    "youtube": {"titulo": 100, "descricao": 4900},
    "tiktok": {"titulo": 2200, "descricao": 2200},
    "instagram": {"titulo": 2200, "descricao": 2200},
    "facebook": {"titulo": 200, "descricao": 5000},
}
_PEDIDO = """Você escreve metadados de publicação de vídeo curto.
Responda SÓ com JSON, sem markdown e sem explicação, neste formato:
{"youtube":{"titulo":"...","descricao":"...","hashtags":["#..."]},
 "tiktok":{"titulo":"...","descricao":"...","hashtags":["#..."]},
 "instagram":{"titulo":"...","descricao":"...","hashtags":["#..."]},
 "facebook":{"titulo":"...","descricao":"...","hashtags":["#..."]}}

Regras:
- título do YouTube com no máximo 100 caracteres; os outros podem ser mais diretos;
- descrição com 1 a 2 frases e um convite claro no fim;
- 3 a 6 hashtags por plataforma, curtas, começando com #;
- TikTok e Instagram mais conversacionais; YouTube mais buscável;
- não invente fato, número, prêmio ou promessa;
- use o idioma do roteiro.

VÍDEO: %s
GANCHO: %s
ROTEIRO: %s
PLATAFORMAS: %s
"""


def _texto(v, limite):
    return str(v or "").strip()[:limite]


def _tags(v):
    itens = v if isinstance(v, list) else str(v or "").split()
    saida = []
    for x in itens:
        t = re.sub(r"[^\w#]", "", str(x or "").strip())
        if not t:
            continue
        if not t.startswith("#"):
            t = "#" + t
        if t.lower() not in {y.lower() for y in saida}:
            saida.append(t)
    return saida[:6]


def _fallback(plano, plataforma):
    return {
        "titulo": _texto(plano.get("titulo") or "Vídeo", LIMITES[plataforma]["titulo"]),
        "descricao": _texto(roteirista.texto_legenda(plano), LIMITES[plataforma]["descricao"]),
        "hashtags": _tags(plano.get("hashtags") or []),
    }


def _normalizar(bruto, plano, plataformas):
    d = bruto if isinstance(bruto, dict) else {}
    saida = {}
    for p in plataformas:
        item = d.get(p) if isinstance(d.get(p), dict) else {}
        base = _fallback(plano, p)
        saida[p] = {
            "titulo": _texto(item.get("titulo") or base["titulo"], LIMITES[p]["titulo"]),
            "descricao": _texto(item.get("descricao") or base["descricao"], LIMITES[p]["descricao"]),
            "hashtags": _tags(item.get("hashtags") or base["hashtags"]),
        }
    return saida


async def gerar(pedir, plano, canal, plataformas=None):
    plataformas = [p for p in (plataformas or PLATAFORMAS) if p in LIMITES] or list(PLATAFORMAS)
    falas = " ".join(str(c.get("fala") or "") for c in (plano.get("cenas") or []) if c.get("fala"))
    prompt = _PEDIDO % (
        _texto(plano.get("titulo") or "", 200),
        _texto(plano.get("gancho") or "", 300),
        _texto(falas, 5000),
        ", ".join(plataformas),
    )
    try:
        res = await pedir(prompt)
        texto = (res or {}).get("texto") if isinstance(res, dict) else str(res or "")
        m = re.search(r"\{.*\}", texto or "", re.S)
        bruto = json.loads(m.group(0)) if m else {}
    except Exception:
        bruto = {}
    return _normalizar(bruto, plano, plataformas)
