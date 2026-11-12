"""Roteirista — de um briefing solto para um plano de vídeo completo.

O plano é o contrato entre a tela e a esteira: título, gancho, cenas (fala + o que se vê),
personagens com descrição visual, legenda, hashtags e chamada final. Quem escreve é a IA
de texto local do estúdio; se ela não estiver disponível, o fallback divide o briefing em
cenas aproveitáveis em vez de deixar a tela vazia.
"""
import json
import re
import unicodedata

import canais

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
    def tentar(s):
        try:
            return json.loads(s)
        except Exception:
            try:
                return json.loads(re.sub(r",\s*([}\]])", r"\1", s))
            except Exception:
                return None
    d = tentar(txt)
    if d is not None:
        return d
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
                return tentar(txt[inicio:i + 1])
    return None


def _pedido(canal, contexto, briefing, max_cenas, duracao, personagens_fixos=None,
            personagens_disponiveis=None, inspiracao=None, estilo=None,
            parte=None, total_partes=None, serie_anterior=None):
    fixos = [p for p in (personagens_fixos or []) if str(p).strip()]
    disponiveis = personagens_disponiveis or contexto.get("personagens") or []
    est = canais.estilo_de(canal, estilo)
    ctx = {
        "tema": contexto.get("tema") or "",
        "publico": contexto.get("publico") or "",
        "tom": contexto.get("tom") or "",
        "idioma": contexto.get("idioma") or "pt",
        "estilo": est.get("nome"),
        "personagens_disponiveis": disponiveis,
        "identidade_visual": contexto.get("identidade_visual") or "",
        "regras": contexto.get("regras") or [],
        "nao_fazer": contexto.get("nao_fazer") or [],
        "chamada_final": contexto.get("chamada_final") or "",
    }
    formatos = ", ".join(sorted({f"{f['proporcao']} ({f['nome']})"
                                 for f in (canal.get("formatos") or []) if f.get("ativo", True)}))
    if fixos:
        regra_personagens = ("- Use EXATAMENTE estes personagens: %s. Não crie outros. "
                             "Escreva o nome do personagem em cada cena em que ele aparece."
                             % ", ".join(fixos))
    else:
        regra_personagens = ("- Você pode usar os personagens que já existem no canal ou criar novos. "
                             "Escolha os que fizerem sentido e mantenha o MESMO personagem com a MESMA "
                             "aparência em todas as cenas em que ele aparecer.\n"
                             "- Use coadjuvantes quando a história pedir mais gente. Não deixe a cena só "
                             "nos protagonistas, principalmente em novelinha.")
    ref = ""
    if isinstance(inspiracao, dict) and (inspiracao.get("titulo") or inspiracao.get("url")):
        ref = ("\nREFERÊNCIA DE ESTILO (inspire-se no ritmo e no clima, nunca copie):\n"
               "- %s%s\n%s\n" % (
                   inspiracao.get("titulo") or inspiracao.get("url"),
                   (" de " + inspiracao["autor"]) if inspiracao.get("autor") else "",
                   inspiracao.get("descricao") or inspiracao.get("texto") or ""))
    estilo_txt = ""
    if est.get("prompt"):
        estilo_txt = ("- ESTILO VISUAL OBRIGATÓRIO: %s. Aplique em TODAS as descrições de imagem: %s.\n"
                      % (est.get("nome"), est.get("prompt")))
    parte_txt = ""
    if parte:
        parte_txt = "- Esta é a PARTE %d%s de uma série. Abra com um recap de 1 frase e termine com um gancho forte para a próxima parte.\n" % (
            int(parte), (" de %d" % int(total_partes)) if total_partes else "")
    serie_txt = ""
    if isinstance(serie_anterior, dict) and (serie_anterior.get("titulo") or serie_anterior.get("gancho")):
        serie_txt = ("\nO QUE JÁ ACONTECEU NA SÉRIE:\n- %s\n- %s\n- Não repita o vídeo anterior; continue a história.\n" % (
            serie_anterior.get("titulo") or "", serie_anterior.get("gancho") or serie_anterior.get("legenda") or ""))
    return """Você é o roteirista de um canal. Escreva UM vídeo curto a partir do briefing.

CONTEXTO FIXO DO CANAL (tudo aqui manda mais que o briefing):
%s

BRIEFING DESTE VÍDEO:
%s
%s%s%s%s
REGRAS DE SAÍDA:
- Escolha o número de cenas que a duração pedir, não um número fixo. Cada cena deve render
  de 4 a 9 segundos de fala. Use no máximo %d cenas.
- A soma das falas precisa dar PELO MENOS %d segundos. Se faltar, acrescente frases ou cenas.
- A primeira cena é o gancho: prende nos primeiros 3 segundos, sem "olá" e sem apresentação.
- Cada cena tem uma descrição visual EM INGLÊS, de um objeto, lugar ou pessoa EM AÇÃO.
  Nada de texto escrito dentro da imagem; nada de marca d'água.
- A cena é sobre a IDEIA e o que está sendo contado, não sobre o rosto do personagem.
  Varie enquadramentos: plano aberto, objeto, detalhe, silhueta, ação e lugar. Só use
  close no personagem quando ele for o foco emocional da cena.
%s
- Escolha o papel de cada personagem: principal, coadjuvante ou figurante.
- A legenda do post deve ter 1 a 2 frases e um convite claro no fim.
- Hashtags curtas, sem espaço, começando com #.

Responda SÓ com este JSON, sem explicação e sem markdown:
{"titulo":"...","gancho":"...","publico_alvo":"...","tom":"...","duracao_estimada":%d,
 "personagens":[{"nome":"...","papel":"principal","descricao":"...","visual":"..."}],
 "cenas":[{"n":1,"fala":"...","imagem":"english visual description","personagem":"Nome ou vazio"}],
 "legenda":"...","hashtags":["#..."],"cta":"...","observacoes":"..."}
""" % (json.dumps(ctx, ensure_ascii=False, indent=1), briefing, ref, estilo_txt, parte_txt, serie_txt,
       max_cenas, duracao, regra_personagens, duracao)


def _normalizar(canal, contexto, bruto, briefing, max_cenas, duracao,
                personagens_fixos=None, personagens_disponiveis=None,
                estilo_prompt="", estilo_id="auto", parte=0, serie_id=""):
    d = bruto if isinstance(bruto, dict) else {}
    max_cenas = max(3, min(24, int(max_cenas or 12)))
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
        if len(cenas) >= max_cenas:
            break

    if not cenas:
        cenas = _cenas_do_briefing(contexto, briefing, duracao, max_cenas)
    if estilo_prompt:
        for c in cenas:
            if estilo_prompt.lower()[:24] not in c["imagem"].lower():
                c["imagem"] = (c["imagem"].rstrip(", ") + ", " + estilo_prompt).strip(", ")

    disponiveis = {str(p.get("nome") or "").strip().lower(): p
                   for p in (personagens_disponiveis or []) if isinstance(p, dict) and p.get("nome")}
    personagens = []
    for p in (d.get("personagens") or d.get("characters") or []):
        if isinstance(p, str):
            p = {"nome": p}
        if not isinstance(p, dict):
            continue
        nome = _limpar(p.get("nome") or p.get("name"), 60)
        if not nome:
            continue
        base = disponiveis.get(nome.lower()) or {}
        papel = _limpar(p.get("papel") or base.get("papel") or "principal", 20).lower()
        if papel not in ("principal", "coadjuvante", "figurante"):
            papel = "principal"
        personagens.append({"nome": nome,
                            "papel": papel,
                            "descricao": _limpar(p.get("descricao") or p.get("description") or base.get("descricao"), 800),
                            "visual": _limpar(p.get("visual") or p.get("aparência") or p.get("appearance") or base.get("visual"), 800)})
    if not personagens:
        personagens = [dict(p) for p in (contexto.get("personagens") or [])]

    fixos = [str(n).strip() for n in (personagens_fixos or []) if str(n).strip()]
    if fixos:
        mapa = {p["nome"].lower(): p for p in personagens}
        mapa.update({k: v for k, v in disponiveis.items() if k not in mapa})
        escolhidos = []
        for nome in fixos:
            base = mapa.get(nome.lower()) or {"nome": nome, "descricao": "", "visual": ""}
            escolhidos.append({"nome": base.get("nome") or nome,
                               "papel": base.get("papel") or "principal",
                               "descricao": _limpar(base.get("descricao"), 800),
                               "visual": _limpar(base.get("visual"), 800)})
        personagens = escolhidos
        nomes = {p["nome"].lower() for p in personagens}
        for c in cenas:
            if c.get("personagem") and c["personagem"].lower() not in nomes:
                c["personagem"] = ""

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
        "duracao_minima": duracao,
        "estilo": estilo_id,
        "parte": int(parte or 0),
        "serie_id": serie_id or "",
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


def _cenas_do_briefing(contexto, briefing, duracao, max_cenas=24):
    texto = _limpar(briefing, 20000)
    partes = [p.strip() for p in re.split(r"(?<=[.!?;])\s+|\n+", texto) if p.strip()]
    if not partes:
        partes = [texto or "Uma ideia em uma cena."]
    alvo = max(3, min(int(max_cenas or 24), int(duracao / 6) or 3))
    if len(partes) > alvo:
        passo = len(partes) / alvo
        partes = [partes[int(i * passo)] for i in range(alvo)]
    while len(partes) < alvo:
        idx = max(range(len(partes)), key=lambda i: len(partes[i]))
        corte = re.split(r"(?<=[,:])\s+|\s+(?=e\s|mas\s|porque\s)", partes[idx], maxsplit=1)
        if len(corte) < 2:
            break
        partes[idx:idx + 1] = [x.strip() for x in corte if x.strip()]
    cenas = []
    for i, fala in enumerate(partes, 1):
        cenas.append({"n": i, "fala": _limpar(fala, 500),
                      "imagem": _imagem_de_apoio(contexto, fala), "personagem": ""})
    return cenas


async def gerar_plano(pedir_texto, canal, contexto, briefing, quantas=None, duracao=45,
                      personagens_fixos=None, personagens_disponiveis=None, inspiracao=None,
                      estilo=None, parte=0, total_partes=None, serie_anterior=None, serie_id=""):
    briefing = _limpar(briefing, 12000)
    if not briefing:
        raise ValueError("Escreva o que você quer postar.")
    duracao = max(15, min(180, int(duracao or 45)))
    if quantas:
        max_cenas = max(3, min(24, int(quantas)))
    else:
        max_cenas = max(3, min(24, int(duracao / 5) + 1))
    est = canais.estilo_de(canal, estilo)
    aviso = ""
    bruto = None
    try:
        res = await pedir_texto("canal_roteiro", _pedido(canal, contexto, briefing, max_cenas, duracao,
                                                   personagens_fixos, personagens_disponiveis, inspiracao,
                                                   est.get("id"), parte, total_partes, serie_anterior))
        txt = (res or {}).get("texto") if isinstance(res, dict) else str(res or "")
        bruto = _json_do_texto(txt)
        if bruto is None:
            aviso = "A IA não devolveu um JSON limpo; usei o briefing para montar as cenas."
    except Exception as e:
        aviso = "A IA de texto não respondeu (%s). Montei as cenas a partir do briefing." % str(e)[:120]
    plano = _normalizar(canal, contexto, bruto, briefing, max_cenas, duracao,
                        personagens_fixos, personagens_disponiveis,
                        estilo_prompt=est.get("prompt") or "", estilo_id=est.get("id") or "auto",
                        parte=parte, serie_id=serie_id)
    if parte and ("parte %d" % int(parte)).lower() not in str(plano.get("titulo") or "").lower():
        plano["titulo"] = "%s · Parte %d" % (plano.get("titulo") or "Vídeo", int(parte))
    if isinstance(inspiracao, dict) and (inspiracao.get("titulo") or inspiracao.get("url")):
        plano["inspiracao"] = {k: inspiracao.get(k) for k in ("url", "plataforma", "titulo", "autor", "descricao")}
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


# ------------------------------------------------------------------ contexto do canal com IA
CAMPOS_TEXTO = {
    "tema": "o tema e a descrição do canal, em 2 a 4 frases",
    "publico": "o público do canal, em 1 frase",
    "tom": "o tom de voz dos vídeos, em 1 frase",
    "identidade_visual": "a identidade visual para os prompts de imagem, em 1 a 2 frases",
    "regras": "as regras do canal, uma por linha",
    "nao_fazer": "o que o canal não deve fazer, uma por linha",
    "referencias": "as referências de estilo do canal, uma por linha",
    "chamada_final": "a chamada final dos vídeos, em 1 frase",
    "hashtags": "as hashtags padrão, separadas por espaço",
}


def _limpar_ia(txt, limite=2000):
    txt = str(txt or "").strip()
    txt = re.sub(r"^```(?:[a-z]+)?\s*|\s*```$", "", txt, flags=re.I | re.M).strip()
    txt = re.sub(r"^(?:texto|resposta|resultado)\s*:\s*", "", txt, flags=re.I).strip()
    return txt.strip('"').strip("'").strip()[:limite]


def _nome_generico(nome):
    base = re.sub(r"[^a-z]", "", _sem_acento(nome).lower())
    return base in ("", "canal", "meucanal", "novocanal", "teste", "canal1", "canal2", "canal3")


async def sugerir_descricao(pedir_texto, nome, texto=""):
    nome = _limpar(nome, 80)
    texto = _limpar(texto, 2000)
    if not nome:
        raise ValueError("Dê um nome ao canal.")
    if _nome_generico(nome) and len(texto) < 12:
        raise ValueError("O nome não diz do que o canal trata. Escreva uma descrição curta e tente de novo.")
    pedido = """Você descreve canais de vídeo curto.

Nome do canal: %s
Descrição atual: %s

Escreva a descrição do canal em 2 a 4 frases, no português do Brasil. Diga o que ele conta,
para quem, com que tom e o que diferencia esse canal. Se a descrição atual já existir,
melhore sem mudar a ideia. Não invente fatos externos: nada de números, prêmios, tecnologias,
parcerias, nomes de igrejas, canais ou empresas. Responda só com o texto, sem título e sem explicação.
""" % (nome, texto or "(vazia)")
    res = await pedir_texto("livre", pedido)
    saida = _limpar_ia((res or {}).get("texto") if isinstance(res, dict) else res, 2000)
    if not saida:
        raise ValueError("A IA não devolveu uma descrição.")
    return saida


async def melhorar_campo(pedir_texto, canal, contexto, campo, texto=""):
    if campo not in CAMPOS_TEXTO:
        raise ValueError("Campo desconhecido.")
    texto = _limpar(texto, 3000)
    limite = 160 if campo in ("publico", "tom", "chamada_final") else 900
    pedido = """Você melhora a configuração de um canal de vídeos curtos.

Canal: %s
Campo: %s
Texto atual: %s
Contexto já definido: %s

Reescreva o campo no português do Brasil, direto e concreto, sem explicação e sem markdown.
Se o texto atual estiver vazio, crie do zero a partir do nome e do contexto do canal.
%s
Responda só com o texto final.
""" % (canal.get("nome") or "canal", CAMPOS_TEXTO[campo], texto or "(vazio)",
       json.dumps({k: contexto.get(k) for k in ("tema", "publico", "tom", "identidade_visual",
                                                "regras", "nao_fazer", "referencias", "chamada_final")},
                  ensure_ascii=False),
       "Uma linha por item." if campo in ("regras", "nao_fazer", "referencias") else
       ("Separe as hashtags por espaço, cada uma começando com #." if campo == "hashtags" else ""))
    res = await pedir_texto("livre", pedido)
    saida = _limpar_ia((res or {}).get("texto") if isinstance(res, dict) else res, limite + 400)
    if not saida:
        raise ValueError("A IA não devolveu texto para este campo.")
    if campo == "hashtags":
        itens = []
        for x in re.split(r"[\s,]+", saida):
            x = re.sub(r"[^#\wÀ-ÿ-]", "", x).strip()
            if x:
                itens.append(x if x.startswith("#") else "#" + x)
        saida = " ".join(dict.fromkeys(itens))[:limite]
    elif campo in ("regras", "nao_fazer", "referencias"):
        saida = "\n".join(x.strip(" -•") for x in saida.splitlines() if x.strip())[:limite]
    else:
        saida = re.sub(r"\s+", " ", saida).strip()[:limite]
    return saida


def _normalizar_contexto(bruto):
    saida = {}
    for k in ("tema", "publico", "tom", "identidade_visual", "chamada_final"):
        if isinstance(bruto.get(k), str):
            saida[k] = _limpar(bruto[k], 1200)
    for k in ("regras", "nao_fazer", "referencias"):
        v = bruto.get(k)
        if isinstance(v, str):
            v = v.splitlines()
        if isinstance(v, list):
            saida[k] = [_limpar(x, 220) for x in v if str(x).strip()][:12]
    v = bruto.get("hashtags")
    if isinstance(v, str):
        v = re.split(r"[\s,]+", v)
    if isinstance(v, list):
        tags = []
        for x in v:
            x = _limpar(x, 40).replace(" ", "")
            if x:
                tags.append(x if x.startswith("#") else "#" + x)
        saida["hashtags"] = tags[:20]
    v = bruto.get("personagens")
    if isinstance(v, list):
        personagens = []
        for p in v[:8]:
            if isinstance(p, str):
                p = {"nome": p}
            if not isinstance(p, dict):
                continue
            nome_p = _limpar(p.get("nome") or p.get("name"), 60)
            if not nome_p:
                continue
            personagens.append({"nome": nome_p,
                                "papel": _limpar(p.get("papel") or "principal", 20).lower(),
                                "descricao": _limpar(p.get("descricao") or p.get("description"), 800),
                                "visual": _limpar(p.get("visual") or p.get("appearance"), 800)})
        if personagens:
            saida["personagens"] = personagens
    return saida


def _contexto_em_linhas(txt):
    """Fallback quando o modelo não fecha o JSON: lê prefixos simples, um por linha."""
    saida = {}
    for linha in str(txt or "").splitlines():
        m = re.match(r"^\s*([A-Za-zÀ-ÿ_ ]{3,32})\s*:\s*(.+)$", linha)
        if not m:
            continue
        chave = re.sub(r"\s+", "_", _sem_acento(m.group(1)).strip().upper())
        valor = m.group(2).strip()
        if not valor:
            continue
        if chave in ("TEMA", "PUBLICO", "TOM", "VISUAL", "IDENTIDADE_VISUAL", "CHAMADA", "CHAMADA_FINAL"):
            alvo = {"TEMA": "tema", "PUBLICO": "publico", "TOM": "tom", "VISUAL": "identidade_visual",
                    "IDENTIDADE_VISUAL": "identidade_visual", "CHAMADA": "chamada_final",
                    "CHAMADA_FINAL": "chamada_final"}[chave]
            saida[alvo] = _limpar(valor, 1200)
        elif chave in ("REGRA", "REGRAS"):
            saida.setdefault("regras", []).append(_limpar(valor, 220))
        elif chave in ("NAO_FAZER", "NAO_FAZER_"):
            saida.setdefault("nao_fazer", []).append(_limpar(valor, 220))
        elif chave in ("REFERENCIA", "REFERENCIAS"):
            saida.setdefault("referencias", []).append(_limpar(valor, 220))
        elif chave in ("HASHTAG", "HASHTAGS"):
            x = _limpar(valor, 40).replace(" ", "")
            saida.setdefault("hashtags", []).append(x if x.startswith("#") else "#" + x)
        elif chave in ("PERSONAGEM", "PERSONAGENS"):
            partes = [x.strip() for x in re.split(r"\s*\|\s*", valor)]
            if partes and partes[0]:
                saida.setdefault("personagens", []).append({
                    "nome": _limpar(partes[0], 60),
                    "descricao": _limpar(partes[1] if len(partes) > 1 else "", 800),
                    "visual": _limpar(partes[2] if len(partes) > 2 else "", 800),
                })
    for k in ("regras", "nao_fazer", "referencias", "hashtags", "personagens"):
        if k in saida:
            saida[k] = saida[k][:20]
    return saida


async def gerar_personagens(pedir_texto, canal, contexto, existentes=None):
    nomes = [str((p or {}).get("nome") or "").strip() for p in (existentes or []) if isinstance(p, dict)]
    nomes = [n for n in nomes if n]
    pedido = """Você cria personagens para um canal de vídeos curtos.

Canal: %s
Tema: %s
Público: %s
Tom/estilo: %s
Identidade visual: %s
Personagens que já existem (NÃO repita estes nomes): %s

Crie de 1 a 3 personagens NOVOS que combinem com o canal e conversem com os existentes.
Inclua pelo menos um coadjuvante quando o canal contar histórias ou novelinha, para a
cena não ficar só nos protagonistas.
Cada um precisa de:
- nome curto;
- papel: principal, coadjuvante ou figurante;
- descrição de quem é e como fala;
- aparência visual EM INGLÊS, concreta o suficiente para repetir nas imagens.
Não invente marcas, números ou prêmios. Responda SÓ com um JSON, sem markdown:
[{"nome":"...","papel":"coadjuvante","descricao":"...","visual":"english appearance"}]
""" % (canal.get("nome") or "canal", contexto.get("tema") or "", contexto.get("publico") or "",
       contexto.get("tom") or "", contexto.get("identidade_visual") or "", ", ".join(nomes) or "(nenhum)")
    res = await pedir_texto("canal_personagens", pedido)
    bruto = _json_do_texto((res or {}).get("texto") if isinstance(res, dict) else res)
    if isinstance(bruto, dict):
        bruto = bruto.get("personagens") or []
    if not isinstance(bruto, list):
        raise ValueError("A IA não devolveu personagens. Tente de novo.")
    vistos = {n.lower() for n in nomes}
    saida = []
    for p in bruto:
        if isinstance(p, str):
            p = {"nome": p}
        if not isinstance(p, dict):
            continue
        nome = _limpar(p.get("nome") or p.get("name"), 60)
        if not nome or nome.lower() in vistos:
            continue
        vistos.add(nome.lower())
        papel = _limpar(p.get("papel") or p.get("role") or "principal", 20).lower()
        if papel not in ("principal", "coadjuvante", "figurante"):
            papel = "principal"
        saida.append({"nome": nome, "papel": papel,
                      "descricao": _limpar(p.get("descricao") or p.get("description"), 800),
                      "visual": _limpar(p.get("visual") or p.get("appearance"), 800)})
        if len(saida) >= 3:
            break
    if not saida:
        raise ValueError("A IA não criou personagens novos. Tente de novo.")
    return saida


async def gerar_contexto(pedir_texto, canal, contexto):
    nome = _limpar(canal.get("nome"), 80)
    tema_atual = _limpar(contexto.get("tema"), 2000)
    if _nome_generico(nome) and len(tema_atual) < 12:
        raise ValueError("O nome não diz do que o canal trata. Escreva o tema/descrição antes de gerar.")
    base = """Você monta a configuração de um canal de vídeos curtos.

Nome do canal: %s
Tema/descrição atual: %s
Contexto atual: %s

Preencha TODOS os campos abaixo, no português do Brasil, coerentes com o nome e o tema.
Não invente fatos externos: nada de números, prêmios, tecnologias, parcerias ou nomes de
canais, igrejas e empresas. Em "referencias", descreva estilos (ex.: documentário histórico,
narrativa curta com gancho) em vez de citar marcas.
Mantenha os textos curtos para o JSON caber inteiro.
""" % (nome, tema_atual or "(vazia)", json.dumps({k: contexto.get(k) for k in ("tema", "publico", "tom")},
                                                ensure_ascii=False))
    pedido_json = base + """
Responda SÓ com este JSON, sem markdown, sem nada antes ou depois:
{"tema":"2 a 3 frases","publico":"1 frase","tom":"1 frase",
 "identidade_visual":"1 a 2 frases para prompts de imagem em inglês",
 "personagens":[{"nome":"Nome","papel":"principal","descricao":"quem é e como fala","visual":"aparência em inglês"}],
 "regras":["regra curta"],"nao_fazer":["o que evitar"],
 "referencias":["referência de estilo"],
 "chamada_final":"1 frase","hashtags":["#exemplo"]}
"""
    for tentativa in range(2):
        res = await pedir_texto("contexto", pedido_json if tentativa == 0 else
                                pedido_json + "\nATENÇÃO: a resposta anterior veio quebrada. Responda APENAS o JSON completo.")
        bruto = _json_do_texto((res or {}).get("texto") if isinstance(res, dict) else res)
        if isinstance(bruto, dict):
            saida = _normalizar_contexto(bruto)
            if saida:
                return saida
    pedido_linhas = base + """
A resposta em JSON não funcionou. Responda em LINHAS, uma por item, exatamente com estes prefixos:
TEMA: ...
PUBLICO: ...
TOM: ...
VISUAL: ...
PERSONAGEM: Nome | quem é e como fala | aparência em inglês
REGRA: ...
NAO_FAZER: ...
REFERENCIA: ...
CHAMADA: ...
HASHTAG: #exemplo
"""
    res = await pedir_texto("contexto", pedido_linhas)
    saida = _contexto_em_linhas((res or {}).get("texto") if isinstance(res, dict) else res)
    if any(saida.values()):
        return saida
    raise ValueError("A IA não devolveu a configuração em JSON. Tente de novo.")
