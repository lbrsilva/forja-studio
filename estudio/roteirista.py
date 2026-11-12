"""Roteirista — de um briefing solto para um plano de vídeo completo.

O plano é o contrato entre a tela e a esteira: título, gancho, cenas (fala + o que se vê),
personagens com descrição visual, legenda, hashtags e chamada final. Quem escreve é a IA
de texto local do estúdio; se ela não estiver disponível, o fallback divide o briefing em
cenas aproveitáveis em vez de deixar a tela vazia.
"""
import json
import re
import unicodedata

PALAVRAS_SEG = 2.4
PAUSA = 0.35


def _sem_acento(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c))


def _limpar(s, limite=1200):
    return re.sub(r"\s+", " ", str(s or "")).strip()[:limite]


def _json_do_texto(txt):
    txt = str(txt or "").strip()
    txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", txt, flags=re.I | re.M).strip()
    try:
        return json.loads(txt)
    except Exception:
        pass
    inicio = txt.find("{")
    if inicio < 0:
        return None
    profundidade, dentro_string, escape = 0, False, False
    for i, ch in enumerate(txt[inicio:], inicio):
        if dentro_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                dentro_string = False
            continue
        if ch == '"':
            dentro_string = True
        elif ch == "{":
            profundidade += 1
        elif ch == "}":
            profundidade -= 1
            if profundidade == 0:
                try:
                    return json.loads(txt[inicio:i + 1])
                except Exception:
                    return None
    return None


def _pedido(canal, contexto, briefing, quantas, duracao):
    ctx = {
        "tema": contexto.get("tema") or "",
        "publico": contexto.get("publico") or "",
        "tom": contexto.get("tom") or "",
        "idioma": contexto.get("idioma") or "pt",
        "personagens": contexto.get("personagens") or [],
        "identidade_visual": contexto.get("identidade_visual") or "",
        "regras": contexto.get("regras") or [],
        "nao_fazer": contexto.get("nao_fazer") or [],
        "chamada_final": contexto.get("chamada_final") or "",
    }
    formatos = ", ".join(sorted({f"{f['proporcao']} ({f['nome']})"
                                 for f in (canal.get("formatos") or []) if f.get("ativo", True)}))
    return """Você é o roteirista de um canal. Escreva UM vídeo curto a partir do briefing.

CONTEXTO FIXO DO CANAL (tudo aqui manda mais que o briefing):
%s

BRIEFING DESTE VÍDEO:
%s

REGRAS DE SAÍDA:
- %d cenas, cada uma com uma fala curta (1 a 2 frases, até 30 palavras).
- A primeira cena é o gancho: prende nos primeiros 3 segundos, sem "olá" e sem apresentação.
- Cada cena tem uma descrição visual EM INGLÊS, de um objeto, lugar ou pessoa EM AÇÃO.
  Nada de texto escrito dentro da imagem; nada de marca d'água.
- Se houver personagens no contexto, use os mesmos nomes e mantenha a aparência descrita.
- Duração alvo: cerca de %d segundos no total.
- Formatos de destino: %s.
- A legenda do post deve ter 1 a 2 frases e um convite claro no fim.
- Hashtags curtas, sem espaço, começando com #.

Responda SÓ com este JSON, sem explicação e sem markdown:
{"titulo":"...","gancho":"...","publico_alvo":"...","tom":"...","duracao_estimada":%d,
 "personagens":[{"nome":"...","descricao":"...","visual":"..."}],
 "cenas":[{"n":1,"fala":"...","imagem":"english visual description","personagem":"Nome ou vazio"}],
 "legenda":"...","hashtags":["#..."],"cta":"...","observacoes":"..."}
""" % (json.dumps(ctx, ensure_ascii=False, indent=1), briefing, quantas, duracao, formatos or "9:16",
       duracao)


def _normalizar(canal, contexto, bruto, briefing, quantas, duracao):
    d = bruto if isinstance(bruto, dict) else {}
    cenas_brutas = d.get("cenas") or d.get("scenes") or d.get("roteiro") or []
    cenas = []
    for i, c in enumerate(cenas_brutas if isinstance(cenas_brutas, list) else [], 1):
        if isinstance(c, str):
            c = {"fala": c}
        if not isinstance(c, dict):
            continue
        fala = _limpar(c.get("fala") or c.get("texto") or c.get("narracao") or c.get("line"), 500)
        imagem = _limpar(c.get("imagem") or c.get("prompt") or c.get("visual") or c.get("image"), 600)
        if not fala:
            continue
        if not imagem:
            imagem = _imagem_de_apoio(contexto, fala)
        cenas.append({"n": len(cenas) + 1, "fala": fala, "imagem": imagem,
                      "personagem": _limpar(c.get("personagem") or c.get("character"), 60)})
        if len(cenas) >= max(3, min(12, quantas)):
            break

    if not cenas:
        cenas = _cenas_do_briefing(contexto, briefing, quantas)

    personagens = []
    for p in (d.get("personagens") or d.get("characters") or []):
        if isinstance(p, str):
            p = {"nome": p}
        if not isinstance(p, dict):
            continue
        nome = _limpar(p.get("nome") or p.get("name"), 60)
        if not nome:
            continue
        personagens.append({"nome": nome,
                            "descricao": _limpar(p.get("descricao") or p.get("description"), 800),
                            "visual": _limpar(p.get("visual") or p.get("aparência") or p.get("appearance"), 800)})
    if not personagens:
        personagens = [dict(p) for p in (contexto.get("personagens") or [])]

    hashtags = []
    for h in (d.get("hashtags") or []):
        h = _limpar(h, 40).replace(" ", "")
        if h and not h.startswith("#"):
            h = "#" + h
        if h and h not in hashtags:
            hashtags.append(h)
    if not hashtags:
        hashtags = [h for h in (contexto.get("hashtags") or []) if h]

    total = sum(_segundos(c["fala"]) for c in cenas)
    return {
        "titulo": _limpar(d.get("titulo") or d.get("title") or briefing, 100) or "Vídeo novo",
        "gancho": _limpar(d.get("gancho") or d.get("hook") or (cenas[0]["fala"] if cenas else ""), 300),
        "publico_alvo": _limpar(d.get("publico_alvo") or contexto.get("publico"), 300),
        "tom": _limpar(d.get("tom") or contexto.get("tom"), 200),
        "duracao_estimada": round(total, 1),
        "duracao_alvo": duracao,
        "personagens": personagens,
        "cenas": cenas,
        "legenda": _limpar(d.get("legenda") or d.get("caption") or d.get("descricao"), 2000),
        "hashtags": hashtags[:20],
        "cta": _limpar(d.get("cta") or contexto.get("chamada_final"), 300),
        "observacoes": _limpar(d.get("observacoes") or d.get("notes"), 600),
        "motor": "ia-local",
        "canal_id": canal.get("id"),
        "criado": __import__("time").time(),
    }


def _segundos(fala):
    palavras = len(str(fala or "").split())
    return round(palavras / PALAVRAS_SEG + PAUSA, 2)


def _imagem_de_apoio(contexto, fala):
    base = contexto.get("identidade_visual") or contexto.get("tema") or "editorial illustration"
    return ("%s, %s, cinematic composition, concrete subject, no text, no watermark, high detail"
            % (base, fala[:180])).strip(", ")


def _cenas_do_briefing(contexto, briefing, quantas):
    texto = _limpar(briefing, 20000)
    partes = [p.strip() for p in re.split(r"(?<=[.!?;])\s+|\n+", texto) if p.strip()]
    if not partes:
        partes = [texto or "Uma ideia em uma cena."]
    alvo = max(3, min(12, int(quantas or 6)))
    if len(partes) > alvo:
        passo = len(partes) / alvo
        partes = [partes[int(i * passo)] for i in range(alvo)]
    elif len(partes) < 3:
        while len(partes) < 3:
            partes.append(partes[-1] if partes else texto or "Uma ideia em uma cena.")
    cenas = []
    for i, fala in enumerate(partes, 1):
        cenas.append({"n": i, "fala": _limpar(fala, 500),
                      "imagem": _imagem_de_apoio(contexto, fala), "personagem": ""})
    return cenas


async def gerar_plano(pedir_texto, canal, contexto, briefing, quantas=6, duracao=45):
    briefing = _limpar(briefing, 12000)
    if not briefing:
        raise ValueError("Escreva o que você quer postar.")
    quantas = max(3, min(12, int(quantas or 6)))
    duracao = max(15, min(180, int(duracao or 45)))
    aviso = ""
    bruto = None
    try:
        res = await pedir_texto("roteiro", _pedido(canal, contexto, briefing, quantas, duracao))
        txt = (res or {}).get("texto") if isinstance(res, dict) else str(res or "")
        bruto = _json_do_texto(txt)
        if bruto is None:
            aviso = "A IA não devolveu um JSON limpo; usei o briefing para montar as cenas."
    except Exception as e:
        aviso = "A IA de texto não respondeu (%s). Montei as cenas a partir do briefing." % str(e)[:120]
    plano = _normalizar(canal, contexto, bruto, briefing, quantas, duracao)
    if aviso:
        plano["motor"] = "fallback"
        plano["observacoes"] = (plano.get("observacoes") + " " + aviso).strip()
    return plano


def roteiro_voz(plano):
    return "\n".join(c.get("fala") or "" for c in plano.get("cenas") or [] if c.get("fala"))


def cenas_prompts(plano):
    return "\n".join(c.get("imagem") or "" for c in plano.get("cenas") or [] if c.get("imagem"))


def legendas(plano):
    return "\n".join(c.get("fala") or "" for c in plano.get("cenas") or [] if c.get("fala"))


def texto_legenda(plano):
    partes = [plano.get("legenda") or ""]
    if plano.get("cta"):
        partes.append(plano["cta"])
    tags = " ".join(plano.get("hashtags") or [])
    return "\n\n".join(p for p in partes if p) + (("\n\n" + tags) if tags else "")
