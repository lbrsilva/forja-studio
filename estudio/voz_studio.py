"""VoiceStudio (voz local, de graça) como fonte de narração do estúdio.

O VoiceStudio é um aplicativo separado (https://github.com/debpalash/VoiceStudio, AGPL-3.0).
NÓS NÃO COPIAMOS CÓDIGO DELE: falamos pela rede, com o servidor MCP que ele publica em
http://127.0.0.1:3900/mcp/. Isso mantém o estúdio sendo nosso — copiar um arquivo que fosse
obrigaria o estúdio inteiro a virar AGPL. Chamar, nunca copiar.

Com ele desligado tudo aqui degrada em silêncio: `estado()` devolve no_ar=False e a tela
mostra o cartão de "ligar", igual ao painel de música.

AS FERRAMENTAS QUE ELE EXPÕE (docs/mcp.md do projeto):
  generate_speech(text, profile_id?, language?, format?)  -> áudio (base64 embutido, por padrão)
  clone_voice(ref_audio_path | ref_audio_base64, ...)     -> profile_id
  design_voice(description)                               -> profile_id
  describe_voice(description)   -> o que ele entendeu e o que NÃO entendeu da descrição
  list_voices / list_languages / check_health

⚠️ LICENÇA DOS MODELOS: o motor que vem de fábrica (OmniVoice) tem pesos CC-BY-NC, ou seja,
NÃO pode ser usado em vídeo monetizado. O VoxCPM 2 é Apache-2.0 (pesos e código) e é o alvo.
Por isso `vozes()` devolve um selo de licença em cada voz: é ele que a tela mostra, para
ninguém publicar sem querer com um motor proibido.
"""
import asyncio
import base64
import binascii
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import aiohttp

import plataforma

URL = os.environ.get("ESTUDIO_VOZ_URL") or "http://127.0.0.1:3900"
MCP = URL.rstrip("/") + "/mcp/"
PROTOCOLO = "2025-06-18"
# A primeira geração depois de ligar é sempre a mais lenta (carrega os pesos e compila os
# kernels da CUDA). A documentação deles fala em ~8 s só de carga, e o tempo de espera aqui
# tem de caber uma narração inteira de 40 s, não só uma frase.
TEMPO_RAPIDO, TEMPO_FALA = 30, 600

_sessao = {"id": None, "ate": 0.0}        # id da sessão MCP (vem no cabeçalho mcp-session-id)
_cache = {"vozes": None, "ate": 0.0, "idiomas": None, "idiomas_ate": 0.0}
_vez = asyncio.Lock()                      # UMA geração por vez: a regra da casa vale aqui também

# ----------------------------------------------------------------- licença dos motores
# Medido em 30/10/2026 lendo os cards dos modelos. O que não estiver nesta lista entra como
# "não conferida" — que na tela é amarelo, nunca verde. Verde só com licença lida.
LICENCAS = {
    "voxcpm":     ("ok",       "Apache-2.0 — pode publicar e monetizar"),
    "mosstts":    ("ok",       "Apache-2.0 — pode publicar e monetizar"),
    "gptsovits":  ("ok",       "MIT — pode publicar e monetizar"),
    "pockettts":  ("ok",       "MIT / CC-BY-4.0 — pode publicar, com crédito"),
    "supertonic": ("duvida",   "Licença não conferida — olhe o card antes de publicar"),
    "cosyvoice":  ("ok",       "Apache-2.0 — mas NÃO fala português"),
    "omnivoice":  ("proibido", "CC-BY-NC — só rascunho, não pode monetizar"),
    "kitten":     ("limite",   "Licença com teto de US$ 1 milhão de faturamento"),
    "indextts":   ("duvida",   "Licença da bilibili, contestada — evitar"),
    "whisper":    ("ok",       "MIT — transcrição"),
}


# nomes em português dos idiomas que ele devolve como código solto ("en", "es"...)
NOMES_IDIOMA = {
    "en": "Inglês", "es": "Espanhol", "fr": "Francês", "de": "Alemão", "it": "Italiano",
    "ru": "Russo", "ja": "Japonês", "ko": "Coreano", "zh": "Chinês", "ar": "Árabe",
    "hi": "Híndi", "tr": "Turco", "nl": "Holandês", "pl": "Polonês", "sv": "Sueco",
    "da": "Dinamarquês", "fi": "Finlandês", "no": "Norueguês", "el": "Grego",
}


def _python_do_backend(proj):
    return proj / ".venv" / ("Scripts/python.exe" if plataforma.WIN else "bin/python")


def achar_backend():
    """A pasta do motor do VoiceStudio instalado, ou None.

    Procura nos dois lugares: o que o instalador usa por padrão (via %APPDATA%, que aqui é
    uma junção para o E:) e a pasta do E: direto, para o caso de a junção não existir na
    máquina de quem baixar o estúdio.
    """
    tentativas = []
    ap = os.environ.get("APPDATA")
    if ap:
        tentativas.append(Path(ap) / "VoiceStudio" / "runtime" / "project")
    dados_do_app = (Path.home() / "Library" / "Application Support" / "VoiceStudio" if plataforma.MAC
                    else Path.home() / ".config" / "VoiceStudio" if not plataforma.WIN else None)
    if dados_do_app:
        tentativas.append(dados_do_app / "runtime" / "project")
        try:
            raiz = json.loads((dados_do_app / "runtime-location.json").read_text(encoding="utf-8")).get("root")
            if raiz:
                tentativas.append(Path(raiz) / "project")
        except (OSError, ValueError, AttributeError):
            pass
    # instalado AO LADO do projeto -- e onde ele costuma estar
    _irmao = Path(__file__).resolve().parent.parent.parent / "VoiceStudio"
    tentativas.append(_irmao / "runtime" / "project")
    if os.environ.get("ESTUDIO_VOZ_DIR"):
        tentativas.insert(0, Path(os.environ["ESTUDIO_VOZ_DIR"]))
    for p in tentativas:
        if _python_do_backend(p).is_file() and (p / "backend" / "main.py").is_file():
            return p
    return None


def ligar(saida_audio=None):
    """Sobe o motor SEM JANELA. Devolve (ok, recado).

    Por que sem janela: ele fechou o aplicativo e a aba caiu junto. Uma esteira que roda de
    madrugada não pode depender de alguém ter deixado um programa aberto.
    As variáveis de ambiente não são decoração: sem VOICESTUDIO_URL ele monta a própria URL
    SEM a porta ("http://127.0.0.1/transcribe") e devolve 403 na transcrição.
    """
    proj = achar_backend()
    if not proj:
        return False, ("Não achei o VoiceStudio instalado. Baixe o instalador da página de "
                       "releases e rode o assistente uma vez. Sem ele, a narração local usa o Chatterbox da ComfyUI.")
    porta = URL.rsplit(":", 1)[-1]
    amb = dict(os.environ,
               OMNIVOICE_PORT=porta, VOICESTUDIO_URL=URL, OMNIVOICE_HOST="127.0.0.1",
               OMNIVOICE_MCP_BASE_PATH=str(saida_audio or Path.cwd()))
    try:
        subprocess.Popen([str(_python_do_backend(proj)), "-u",
                          str(proj / "backend" / "main.py")],
                         cwd=str(proj / "backend"), env=amb,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as e:
        return False, "Não consegui ligar o motor de voz: %s" % str(e)[:200]
    return True, "Ligando o motor de voz. Leva uns 30 segundos na primeira vez."


def licenca_de(nome):
    """(selo, explicação) a partir do nome do motor/voz. Sem certeza, nunca diz 'pode'."""
    n = re.sub(r"[^a-z0-9]", "", (nome or "").lower())
    for chave, (selo, txt) in LICENCAS.items():
        if chave in n:
            return selo, txt
    return "duvida", "Licença não conferida — não publique sem olhar o card do modelo"


# ----------------------------------------------------------------- conversa com o MCP
def _texto_do(res):
    """Junta os pedaços de texto de uma resposta do MCP num string só."""
    partes = []
    for c in (res or {}).get("content") or []:
        if isinstance(c, dict) and c.get("type") == "text" and c.get("text"):
            partes.append(str(c["text"]))
    return "\n".join(partes).strip()


def _talvez_json(v):
    """Ele devolve JSON DENTRO de texto, às vezes com duas camadas (medido em 30/10: o
    check_health voltou como a string '{"status": "ok", ...}' dentro de structuredContent.result).
    Desembrulha enquanto for string que parece JSON — no máximo 3 vezes, para não girar à toa."""
    for _ in range(3):
        if not isinstance(v, str):
            break
        t = v.strip()
        if not t or t[0] not in "[{\"":
            break
        try:
            v = json.loads(t)
        except Exception:
            break
    return v


def _json_do(res):
    """O que vier estruturado; senão tenta ler o texto como JSON; senão devolve o texto cru."""
    if isinstance(res, dict) and isinstance(res.get("structuredContent"), dict):
        d = res["structuredContent"]
        # alguns servidores embrulham tudo num "result"
        return _talvez_json(d.get("result", d))
    return _talvez_json(_texto_do(res)) or None


def _audio_do(res):
    """Acha os bytes do áudio na resposta, aceitando os três modos de saída dele.

    `resources` (padrão) devolve o WAV em base64 embutido; `files` devolve um caminho no disco
    e/ou uma URL. Aceitamos os três para não depender de como o aplicativo está configurado —
    é exatamente o tipo de coisa que quebra na máquina de outra pessoa.
    """
    for c in (res or {}).get("content") or []:
        if not isinstance(c, dict):
            continue
        if c.get("type") == "audio" and c.get("data"):
            try:
                return base64.b64decode(c["data"]), None
            except (binascii.Error, ValueError):
                pass
        if c.get("type") == "resource":
            r = c.get("resource") or {}
            if r.get("blob"):
                try:
                    return base64.b64decode(r["blob"]), None
                except (binascii.Error, ValueError):
                    pass
    d = _json_do(res)
    if isinstance(d, dict):
        for campo in ("wav_base64", "audio_base64", "data"):
            if isinstance(d.get(campo), str) and len(d[campo]) > 256:
                try:
                    return base64.b64decode(d[campo]), None
                except (binascii.Error, ValueError):
                    pass
        caminho = d.get("output_path") or d.get("path")
        if caminho and Path(str(caminho)).is_file():
            return Path(str(caminho)).read_bytes(), None
        if d.get("audio_url"):
            return None, str(d["audio_url"])
    return None, None


async def _ler(resp):
    """A resposta pode vir JSON puro ou como fluxo SSE ('data: {...}'). Lê os dois."""
    bruto = (await resp.read()).decode("utf-8", "replace").strip()
    if not bruto:
        return None
    if "text/event-stream" in (resp.headers.get("Content-Type") or ""):
        for linha in bruto.splitlines():
            linha = linha.strip()
            if linha.startswith("data:"):
                try:
                    d = json.loads(linha[5:].strip())
                except Exception:
                    continue
                if isinstance(d, dict) and ("result" in d or "error" in d):
                    return d
        return None
    try:
        return json.loads(bruto)
    except Exception:
        return None


async def _abrir(ses):
    """Aperto de mão do MCP. Guarda o id da sessão por 10 min."""
    if _sessao["id"] and time.time() < _sessao["ate"]:
        return _sessao["id"]
    corpo = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": PROTOCOLO, "capabilities": {},
        "clientInfo": {"name": "estudio-local", "version": "1.0"}}}
    cab = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    async with ses.post(MCP, json=corpo, headers=cab,
                        timeout=aiohttp.ClientTimeout(total=TEMPO_RAPIDO)) as r:
        d = await _ler(r)
        sid = r.headers.get("mcp-session-id") or r.headers.get("Mcp-Session-Id")
    if d and d.get("error"):
        raise RuntimeError("O VoiceStudio recusou a conexão: %s" % str(d["error"])[:200])
    _sessao.update(id=sid or "", ate=time.time() + 600)
    cab2 = dict(cab)
    if sid:
        cab2["Mcp-Session-Id"] = sid
    try:  # aviso de "pronto": alguns servidores exigem, outros ignoram
        async with ses.post(MCP, json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                            headers=cab2, timeout=aiohttp.ClientTimeout(total=10)):
            pass
    except Exception:
        pass
    return _sessao["id"]


def _amigavel(texto):
    """Troca o recado de licenca do VoiceStudio (em ingles) por uma explicacao em portugues."""
    m = re.search(r"Licence not accepted for (.+?)\. Review", texto or "")
    if not m:
        return texto
    return ("O VoiceStudio travou a narração porque a licença destes modelos de voz ainda não foi aceita: "
            f"{m.group(1)}. Abra a janela do VoiceStudio, vá em Catálogo de modelos (Model Catalogue), leia a licença "
            "de cada um e aceite. A decisão é sua: confira se a licença permite o seu uso (inclusive comercial, "
            "se for publicar ou vender) antes de aceitar.")


async def chamar(ferramenta, argumentos=None, timeout=TEMPO_RAPIDO, _retentar=True):
    """Chama uma ferramenta do VoiceStudio. Devolve o resultado cru do MCP."""
    async with aiohttp.ClientSession() as ses:
        sid = await _abrir(ses)
        cab = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if sid:
            cab["Mcp-Session-Id"] = sid
        corpo = {"jsonrpc": "2.0", "id": int(time.time() * 1000) % 100000, "method": "tools/call",
                 "params": {"name": ferramenta, "arguments": argumentos or {}}}
        async with ses.post(MCP, json=corpo, headers=cab,
                            timeout=aiohttp.ClientTimeout(total=timeout)) as r:
            if r.status in (400, 404) and _retentar:
                # sessão velha/derrubada (ele reinicia sozinho depois de 15 min parado)
                _sessao.update(id=None, ate=0.0)
                return await chamar(ferramenta, argumentos, timeout, _retentar=False)
            d = await _ler(r)
    if not d:
        raise RuntimeError("O VoiceStudio não respondeu direito. Ele está aberto?")
    if d.get("error"):
        raise RuntimeError(_amigavel(str(d["error"].get("message") or d["error"]))[:500])
    res = d.get("result") or {}
    if res.get("isError"):
        raise RuntimeError(_amigavel(_texto_do(res))[:500] or "O VoiceStudio recusou o pedido.")
    return res


# ----------------------------------------------------------------- o que a tela usa
async def motor_ativo():
    """Qual motor de voz está ligado agora — e a licença DELE.

    Isto não vem pelo MCP: é uma rota HTTP comum do VoiceStudio (`/engines`). Importa porque
    a lista de vozes não diz de qual motor cada voz é, e sem isso TODA voz apareceria como
    "licença não conferida" — um alerta que grita sempre não avisa nada. Com o motor ativo em
    mãos, a voz herda a licença dele.
    """
    try:
        async with aiohttp.ClientSession() as ses:
            async with ses.get(URL.rstrip("/") + "/engines",
                               timeout=aiohttp.ClientTimeout(total=15)) as r:
                d = await r.json()
    except Exception:
        return None
    t = (d or {}).get("tts") or {}
    ativo = t.get("active")
    if not ativo:
        return None
    nome = ativo
    for b in t.get("backends") or []:
        if b.get("id") == ativo:
            nome = b.get("display_name") or ativo
            break
    selo, txt = licenca_de(ativo)
    return {"id": ativo, "nome": nome, "modelo": t.get("active_model"),
            "licenca": selo, "licenca_txt": txt}


async def estado():
    """{no_ar, gpu, motor, detalhe} — nunca levanta erro: a tela precisa sempre de resposta."""
    try:
        res = await chamar("check_health", timeout=8)
    except Exception as e:
        return {"no_ar": False, "gpu": None, "motor": None, "detalhe": str(e)[:200]}
    d = _json_do(res) or {}
    gpu = None
    if isinstance(d, dict):
        gpu = d.get("device") or d.get("gpu") or d.get("active_device")
    return {"no_ar": True, "gpu": gpu, "motor": await motor_ativo(),
            "detalhe": d if isinstance(d, dict) else str(d)[:300]}


def _normalizar_vozes(d):
    """A lista vem em formatos diferentes conforme a versão. Aceita todos."""
    if isinstance(d, dict):
        d = d.get("voices") or d.get("profiles") or d.get("items") or []
    if not isinstance(d, list):
        return []
    saida = []
    for v in d:
        if isinstance(v, str):
            v = {"id": v, "name": v}
        if not isinstance(v, dict):
            continue
        vid = v.get("profile_id") or v.get("id") or v.get("voice_id") or v.get("name")
        if not vid:
            continue
        nome = v.get("name") or v.get("label") or str(vid)
        motor = v.get("engine") or v.get("model") or v.get("backend") or ""
        selo, txt = licenca_de(motor or nome)
        saida.append({"id": str(vid), "nome": str(nome), "motor": str(motor),
                      "tipo": v.get("type") or v.get("kind") or "",
                      "licenca": selo, "licenca_txt": txt})
    saida.sort(key=lambda v: ({"ok": 0, "limite": 1, "duvida": 2, "proibido": 3}[v["licenca"]], v["nome"].lower()))
    return saida


# ----------------------------------------------------------------- apagar uma voz
# 07/11/2026. O MCP do VoiceStudio NAO tem ferramenta de apagar: list_voices, clone_voice e
# design_voice criam e listam, e mais nada. Quem apaga e a API REST dele (DELETE /profiles/
# <id>), que o proprio aplicativo publica em http://127.0.0.1:3900/docs.
#
# Continua valendo "chamar, nunca copiar": falamos pela rede com o aplicativo dele, como ja
# fazemos no MCP. Nenhum arquivo do VoiceStudio e tocado por nos - apagar mexendo na pasta de
# dados dele seria entrar por tras do aplicativo e quebrar na primeira versao nova.
async def apagar_voz(pid):
    """Apaga um perfil de voz no VoiceStudio. Devolve True se sumiu.

    Apagar e irreversivel e do lado dele: a voz some para tudo que usa o VoiceStudio nesta
    maquina, nao so para o nosso painel. Quem pergunta antes e a tela.
    """
    pid = str(pid or "").strip()
    if not pid:
        raise RuntimeError("Diga qual voz apagar.")
    alvo = URL.rstrip("/") + "/profiles/" + pid
    async with aiohttp.ClientSession() as ses:
        async with ses.delete(alvo, timeout=aiohttp.ClientTimeout(total=60)) as r:
            corpo = (await r.text())[:200]
            if r.status == 404:
                raise RuntimeError("Essa voz ja nao existe no VoiceStudio.")
            if r.status >= 400:
                raise RuntimeError("O VoiceStudio recusou apagar (HTTP %d): %s" % (r.status, corpo))
    _cache.update(vozes=None, ate=0.0)
    # Nao confiamos no 200: conferimos que ela sumiu MESMO da lista. Foi assim que
    # descobrimos, em outras partes deste projeto, resposta de sucesso sem efeito nenhum.
    restantes = await vozes(True)
    return not any(str(v.get("id")) == pid for v in restantes)


_IDIOMAS_PRESET = {
    "a": "Inglês (EUA)", "b": "Inglês (UK)", "e": "Espanhol", "f": "Francês",
    "h": "Híndi", "i": "Italiano", "j": "Japonês", "p": "Português", "z": "Chinês",
}
_presets_cache = {"ativos": None, "ate": 0.0}


def _nome_preset(vid):
    vid = str(vid or "")
    lingua = _IDIOMAS_PRESET.get(vid[:1].lower(), "")
    genero = {"f": "feminina", "m": "masculina"}.get(vid[1:2].lower(), "")
    nome = vid.split("_", 1)[1].capitalize() if "_" in vid else vid
    partes = [p for p in (lingua, genero) if p]
    return "%s%s" % (nome, (" (" + ", ".join(partes) + ")") if partes else "")


async def presets_do_motor():
    """Vozes predefinidas do motor ativo. O MCP só lista profiles; os presets vêm de /engines."""
    if _presets_cache["ativos"] is not None and time.time() < _presets_cache["ate"]:
        return _presets_cache["ativos"]
    try:
        async with aiohttp.ClientSession() as ses:
            async with ses.get(URL.rstrip("/") + "/engines/tts",
                               timeout=aiohttp.ClientTimeout(total=15)) as r:
                d = await r.json()
    except Exception:
        return _presets_cache["ativos"] or []
    ativo = (d or {}).get("active")
    entry = next((b for b in (d.get("backends") or []) if b.get("id") == ativo), None)
    lista = []
    if entry:
        selo, txt = licenca_de(ativo)
        for vid in entry.get("preset_voices") or []:
            lista.append({"id": str(vid), "nome": _nome_preset(str(vid)),
                          "motor": str(ativo or ""), "tipo": "preset",
                          "licenca": selo, "licenca_txt": txt})
    _presets_cache.update(ativos=lista, ate=time.time() + 300)
    return lista


async def vozes(forcar=False):
    """[{id, nome, motor, licenca, licenca_txt}] — em cache por 2 min."""
    if not forcar and _cache["vozes"] is not None and time.time() < _cache["ate"]:
        return _cache["vozes"]
    try:
        lista = _normalizar_vozes(_json_do(await chamar("list_voices", timeout=20)))
    except Exception:
        return _cache["vozes"] or []
    presets = await presets_do_motor()
    if presets:
        ids = {str(v.get("id")) for v in lista}
        lista.extend(p for p in presets if p["id"] not in ids)
    # a voz não diz de qual motor é: herda a licença do motor LIGADO AGORA
    m = await motor_ativo()
    if m:
        for v in lista:
            if not v["motor"]:
                v.update(motor=m["nome"], licenca=m["licenca"], licenca_txt=m["licenca_txt"])
    lista.sort(key=lambda v: ({"ok": 0, "limite": 1, "duvida": 2, "proibido": 3}.get(v["licenca"], 2),
                              v["nome"].lower()))
    # NÃO guardar lista vazia: durante os ~30 s de aquecimento ele responde sem as vozes, e
    # guardar isso deixava a tela dizendo "nenhuma voz" por 2 minutos depois de já estar
    # pronta. Resposta de quem ainda está acordando não é resposta.
    if lista:
        _cache.update(vozes=lista, ate=time.time() + 120)
    return lista


async def idiomas():
    if _cache["idiomas"] is not None and time.time() < _cache["idiomas_ate"]:
        return _cache["idiomas"]
    try:
        d = _json_do(await chamar("list_languages", timeout=20))
    except Exception:
        return _cache["idiomas"] or []
    # Ele devolve {"total": 646, "popular": ["en","es",...], "note": ...} — a lista inteira não
    # vem, e nem precisa: o que interessa é português. A nota dele diz, com todas as letras,
    # que **"pt" significa pt-BR** e que pt-PT é o de Portugal. Por isso pt-BR entra à mão em
    # primeiro lugar: deixar "automático" escolher foi o que fez a voz sair embaralhada por aí.
    if isinstance(d, dict):
        d = d.get("languages") or d.get("popular") or d.get("items") or []
    lista = [{"codigo": "pt", "nome": "Português do Brasil"},
             {"codigo": "pt-PT", "nome": "Português de Portugal"}]
    vistos = {"pt", "pt-pt"}
    for x in d if isinstance(d, list) else []:
        c = x if isinstance(x, str) else (x.get("code") or x.get("id") or x.get("language")) if isinstance(x, dict) else None
        if not c or str(c).lower() in vistos:
            continue
        vistos.add(str(c).lower())
        nome = NOMES_IDIOMA.get(str(c).lower(), x.get("name") if isinstance(x, dict) else None) or str(c)
        lista.append({"codigo": str(c), "nome": str(nome)})
    # mesma coisa: só guarda se veio algo ALÉM dos dois portugueses que a gente põe à mão,
    # senão uma falha de aquecimento congelava a lista curta por 10 minutos.
    if len(lista) > 2:
        _cache.update(idiomas=lista, idiomas_ate=time.time() + 600)
    return lista


async def descrever(descricao):
    """O que ele entendeu da descrição — e, principalmente, o que NÃO entendeu.

    É isto que deixa a tela avisar "não entendi 'acolhedora'" ENQUANTO ele escreve, em vez de
    ele descobrir depois de esperar a geração.
    """
    d = _json_do(await chamar("describe_voice", {"description": descricao}, timeout=25))
    if not isinstance(d, dict):
        return {"entendeu": {}, "ignorou": [], "cru": d}
    ignorou = d.get("unmapped") or d.get("unmapped_words") or d.get("ignored") or []
    entendeu = {k: v for k, v in d.items()
                if k in ("gender", "age", "pitch", "style", "accent", "speed", "tone") and v}
    return {"entendeu": entendeu, "ignorou": list(ignorou) if isinstance(ignorou, list) else [], "cru": d}


async def desenhar(descricao, nome=None, idioma="pt", entrega=None):
    """Cria uma voz a partir de uma descrição escrita. Devolve o profile_id.

    `name` é OBRIGATÓRIO no design_voice (conferido na lista de ferramentas dele em 30/10):
    sem nome ele recusa. Então, se a pessoa não deu nome, a gente inventa um em vez de
    deixar o pedido quebrar na cara dela.
    """
    args = {"description": descricao, "name": (nome or "").strip() or "Voz nova", "language": idioma}
    if entrega:
        args["instruct"] = entrega   # a entrega mora na voz; o generate_speech não a aceita
    d = _json_do(await chamar("design_voice", args, timeout=180))
    pid = (d or {}).get("profile_id") if isinstance(d, dict) else None
    if not pid:
        raise RuntimeError("Ele não devolveu uma voz. Tente uma descrição mais concreta "
                           "(tipo: 'homem idoso, voz grave e calma, sotaque brasileiro').")
    _cache.update(vozes=None, ate=0.0)
    return str(pid)


# ----------------------------------------------------------------- a referência do clone
# A ficha do `clone_voice` (lida em 31/10) pede **5 a 30 segundos** de fala limpa. Mandar o
# arquivo inteiro não melhora nada e QUEBRA: um mp3 de 4 MB vira 5,5 MB em base64 e o
# VoiceStudio responde `413 Request body too large` — que na tela aparecia como "o VoiceStudio
# não respondeu direito", mandando procurar no lugar errado.
#
# Então: cortamos para 25 s e preferimos mandar o CAMINHO (`ref_audio_path`), que é a via que a
# própria ficha recomenda — o áudio não viaja dentro do pedido. Se a pasta base do MCP não
# estiver configurada, cai no base64 do trecho curto, que agora cabe.
REF_SEGUNDOS = 25


def _ffmpeg():
    """O ffmpeg do projeto, o do PATH, ou None."""
    perto = Path(__file__).resolve().parent.parent / "_ferramentas" / "ffmpeg" / "bin" / plataforma.exe("ffmpeg")
    if perto.is_file():
        return str(perto)
    return shutil.which("ffmpeg")


# ------------------------------------------------------------- conferir a referencia
# 07/11/2026. Antes disso o painel cortava os PRIMEIROS 25 s do arquivo e mandava, sem olhar
# o que tinha dentro. A referencia da YAMI tem musica tocando nos 252 s INTEIROS - zero
# trecho de silencio abaixo de -30 dB em todo o arquivo - e um laco de ~21 s repetido. O
# clone saiu lixo (0 de 4 falas certas, contra 4 de 4 na voz do Cris) e a tela nao disse
# nada: so "Pronto. Ouca um trecho curto".
#
# A licao: nao era o motor, era a referencia. Trocar de motor nao conserta audio com musica.
#
# Agora: antes de clonar, MEDIMOS o arquivo e dizemos o que ha de errado em portugues. E em
# vez de pegar os primeiros 25 s, escolhemos a melhor janela de 25 s do arquivo - a que tem
# mais PAUSAS, porque pausa e o que separa fala de musica: gente respira, trilha nao.
MIN_SEGUNDOS = 5.0          # menos que isso o motor nao tem o que copiar
MAX_SEGUNDOS = 30.0         # a ficha do clone_voice pede 5 a 30; mais nao melhora e estoura o pedido
PAUSAS_MINIMAS = 1          # uma referencia de 25 s de fala de verdade tem ao menos uma pausa


def _ffprobe():
    perto = Path(__file__).resolve().parent.parent / "_ferramentas" / "ffmpeg" / "bin" / plataforma.exe("ffprobe")
    if perto.is_file():
        return str(perto)
    return shutil.which("ffprobe")


def _duracao(caminho):
    fp = _ffprobe()
    if not fp:
        return None
    try:
        saida = subprocess.run([fp, "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", str(caminho)], capture_output=True, text=True,
                               timeout=60,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        return round(float(saida.strip().splitlines()[0]), 1)
    except Exception:
        return None


# 07/11/2026, MEDIDO: -30 dB / 0,35 s era apertado demais e REPROVOU audio bom. Ele mandou
# uma fala do ElevenLabs de 34 s e deu "0 pausas" - as respiradas da fala sintetica sao mais
# curtas e menos fundas que as de gravacao humana. Nos cinco arquivos que eu tinha:
#
#                                  -30 dB/0,35 s     -35 dB/0,20 s
#   fala do ElevenLabs 33 s             0                14
#   fala do ElevenLabs 10 s             -                 4
#   voz do Cris 258 s                  10                 5
#   voz do Cris, 34 s                   2                 3
#   MUSICA (a YAMI velha) 252 s         0                 0      <- e 0 ate a -50 dB
#
# A -35 dB / 0,20 s a separacao e limpa: fala tem pausa, musica nao tem nenhuma em limiar
# nenhum. A licao: eu calibrei a regra em DOIS arquivos e tratei o resultado como lei.
SILENCIO_DB = -35
SILENCIO_S = 0.20


def _pausas(caminho, inicio=None, duracao=None):
    """Instantes (em segundos) onde comeca uma pausa (SILENCIO_S abaixo de SILENCIO_DB).

    E a medida que tenta separar fala de musica. Fala tem pausa; trilha de fundo nao tem.
    """
    ff = _ffmpeg()
    if not ff:
        return None
    cmd = [ff, "-v", "info"]
    if inicio is not None:
        cmd += ["-ss", str(inicio)]
    if duracao is not None:
        cmd += ["-t", str(duracao)]
    cmd += ["-i", str(caminho),
            "-af", "silencedetect=noise=%ddB:d=%s" % (SILENCIO_DB, SILENCIO_S),
            "-f", "null", "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        return None
    achados = []
    for linha in (r.stderr or "").splitlines():
        m = re.search(r"silence_start:\s*(-?[\d.]+)", linha)
        if m:
            try:
                achados.append(round(float(m.group(1)), 2))
            except ValueError:
                pass
    return achados


def melhor_janela(caminho, segundos=None):
    """Onde comeca a melhor janela de `segundos` - a que tem mais pausas.

    Devolve (inicio, pausas_na_janela, pausas_no_arquivo). Sem ffmpeg, devolve (0.0, None, None):
    sem medida nao ha escolha, e tentar com o comeco e melhor que nao tentar.
    """
    segundos = segundos or REF_SEGUNDOS
    dur = _duracao(caminho)
    todas = _pausas(caminho)
    if todas is None or dur is None or dur <= segundos:
        return 0.0, (len(todas) if todas is not None else None), \
               (len(todas) if todas is not None else None)
    # desliza de 5 em 5 s e conta quantas pausas caem dentro; empate fica com a mais ao inicio,
    # que costuma ser onde a pessoa fala com mais calma.
    melhor, quantas = 0.0, -1
    passo = 5.0
    inicio = 0.0
    while inicio + segundos <= dur:
        n = sum(1 for t in todas if inicio < t < inicio + segundos)
        if n > quantas:
            melhor, quantas = inicio, n
        inicio += passo
    return melhor, max(quantas, 0), len(todas)


def conferir_referencia(caminho):
    """Olha o audio ANTES de clonar e diz o que ha de errado, em portugues.

    Devolve dict com: segundos, pausas, trecho (inicio escolhido), veredito
    ('ok' | 'alerta' | 'ruim') e `motivos` - as frases que a tela mostra.
    """
    p = Path(caminho)
    dur = _duracao(p)
    inicio, pausas_janela, pausas_total = melhor_janela(p)
    motivos, veredito = [], "ok"

    if dur is None:
        return {"segundos": None, "pausas": None, "trecho": 0.0, "veredito": "alerta",
                "motivos": ["Não consegui medir o áudio (ffmpeg não encontrado). "
                            "Vou tentar com os primeiros %.0f s." % REF_SEGUNDOS]}

    if dur < MIN_SEGUNDOS:
        veredito = "ruim"
        motivos.append("Áudio de %.1f s. O motor pede ao menos %.0f s de fala — "
                       "com menos ele não tem o que copiar." % (dur, MIN_SEGUNDOS))
    elif dur > MAX_SEGUNDOS:
        motivos.append("O áudio tem %.0f s, e o motor usa no máximo %.0f s. Não há problema: "
                       "eu recorto %.0f s daqui a pouco — mandar o arquivo inteiro não melhora "
                       "o clone e estoura o pedido." % (dur, MAX_SEGUNDOS, REF_SEGUNDOS))

    if pausas_total == 0:
        # 07/11/2026: isto JA FOI "ruim" e travava o botao. Reprovou um audio bom dele, e a
        # conta era minha: regra calibrada em dois arquivos nao manda em quem tem ouvido.
        # Agora avisa e deixa passar - quem decide e ele, olhando o proprio audio.
        veredito = "alerta" if veredito == "ok" else veredito
        motivos.append("Não achei nenhuma pausa em %.0f s. Em geral isso é música ou ruído "
                       "tocando por cima da fala, que estraga o clone — mas se o áudio for "
                       "só a voz, sem trilha, pode clonar: a medida erra em fala muito "
                       "corrida." % dur)
    elif pausas_janela is not None and pausas_janela < PAUSAS_MINIMAS:
        veredito = "alerta" if veredito == "ok" else veredito
        motivos.append("O melhor trecho que achei tem pouca pausa. Se o clone sair embolado, "
                       "grave um pedaço falando mais devagar.")

    if inicio > 0:
        motivos.append("Vou usar os %.0f s a partir de %.0f s — é o trecho com mais pausas, "
                       "não o começo do arquivo." % (REF_SEGUNDOS, inicio))

    if veredito == "ok" and not motivos:
        motivos.append("Áudio bom: %.0f s, %d pausas. Pode clonar." % (dur, pausas_total or 0))

    return {"segundos": dur, "pausas": pausas_total, "pausas_no_trecho": pausas_janela,
            "trecho": round(inicio, 1), "veredito": veredito, "motivos": motivos}


def _recortar_referencia(origem, pasta, inicio=0.0):
    """REF_SEGUNDOS em WAV mono 24 kHz dentro de `pasta`, a partir de `inicio`.

    Sem ffmpeg, devolve o original — melhor tentar com o arquivo inteiro do que não tentar.

    `inicio` vem de `melhor_janela()`: até 07/11/2026 isto pegava sempre os primeiros 25 s,
    e por isso a referência da YAMI (música tocando nos 252 s inteiros) passou direto.
    """
    ff = _ffmpeg()
    if not ff:
        return Path(origem)
    pasta = Path(pasta)
    try:
        pasta.mkdir(parents=True, exist_ok=True)
    except Exception:
        return Path(origem)
    limpo = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(origem).stem)[:40] or "ref"
    destino = pasta / ("%s_%ds_de_%ds.wav" % (limpo, int(REF_SEGUNDOS), int(inicio)))
    cmd = [ff, "-y", "-v", "error"]
    if inicio and inicio > 0:
        cmd += ["-ss", str(inicio)]
    cmd += ["-i", str(origem), "-t", str(REF_SEGUNDOS),
            "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(destino)]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        return Path(origem)
    return destino if destino.is_file() and destino.stat().st_size > 1024 else Path(origem)


async def transcrever_referencia(caminho_audio, idioma="pt", base_mcp=None):
    """Descobre o que esta falado no audio de referencia. Devolve o texto, ou "".

    07/11/2026. Ele perguntou: "e quando eu nao sei?" - o campo da transcricao pode ficar em
    branco, mas texto CERTO ajuda o clone. O motor sabe transcrever (`transcribe`), entao a
    pessoa nao precisa saber: o painel descobre.

    ⚠️ Transcreve o MESMO trecho de REF_SEGUNDOS que vai ser clonado, nao o arquivo inteiro.
    Se transcrevesse tudo, o texto descreveria audio que o motor nunca ouve - que e
    exatamente a falha medida em 31/10: transcricao que nao bate com o audio fez a fala sair
    CORTADA PELA METADE. Texto errado e pior que campo vazio, e "certo para outro pedaco" e
    uma forma de errado.
    """
    p = Path(caminho_audio)
    if not p.is_file():
        raise RuntimeError("Nao achei o audio: %s" % p)

    pasta_ref = (Path(base_mcp) / "refs") if base_mcp else p.parent
    laudo = await asyncio.to_thread(conferir_referencia, p)
    curto = await asyncio.to_thread(_recortar_referencia, p, pasta_ref, laudo.get("trecho") or 0.0)

    base = {"language": idioma} if idioma else {}
    vias = []
    if base_mcp:
        try:
            rel = curto.resolve().relative_to(Path(base_mcp).resolve())
            vias.append({"audio_path": str(rel).replace("\\", "/")})
        except ValueError:
            pass
    vias.append({"audio_base64": base64.b64encode(curto.read_bytes()).decode()})

    ultimo = None
    for extra in vias:
        try:
            d = _json_do(await chamar("transcribe", {**base, **extra}, timeout=300))
        except Exception as e:
            ultimo = str(e)
            continue
        if isinstance(d, dict) and d.get("error"):
            ultimo = str(d["error"])[:200]
            continue
        texto = ""
        if isinstance(d, dict):
            texto = str(d.get("text") or d.get("transcript") or d.get("transcription") or "")
        elif isinstance(d, str):
            texto = d
        texto = texto.strip()
        if texto:
            return {"texto": texto, "trecho": laudo.get("trecho") or 0.0,
                    "segundos": REF_SEGUNDOS, "por": "motor"}
        ultimo = "ele respondeu sem texto"

    # ⚠️ O `transcribe` do VoiceStudio QUEBRA quando ele roda sem janela: por dentro ele
    # chama "http://127.0.0.1/transcribe" - SEM A PORTA - e leva 403. E defeito dele, ja
    # anotado em `estudio/prova_voz.py`. Entao a segunda via e o faster-whisper que este
    # projeto ja usa, no Python 3.12 (o `py` padrao virou 3.14 e nao tem a biblioteca).
    try:
        texto = await asyncio.to_thread(_ouvir_local, curto, idioma or "pt")
    except Exception as e:
        print("[voz] transcricao falhou | motor: %s | local: %s"
              % ((ultimo or "?")[:120], str(e)[:200]), flush=True)
        # A mensagem ENSINA. Quem instalou o pacote hoje nao tem o faster-whisper, e um
        # erro tecnico ("nenhum python com faster-whisper") nao diz a ninguem o que fazer.
        raise RuntimeError(
            "Nao consegui descobrir o texto. Isto precisa do faster-whisper, que nao vem no "
            "pacote. Para ligar, rode uma vez:  pip install faster-whisper  (no Python do "
            "painel). Ele baixa ~464 MB na primeira transcricao. Sem isso, deixe o campo em "
            "branco: o motor se vira sozinho, e esta e a opcao recomendada na duvida.")
    if not texto:
        raise RuntimeError("Nao ouvi palavra nenhuma nesse trecho. Deixe o campo em branco.")
    return {"texto": texto, "trecho": laudo.get("trecho") or 0.0,
            "segundos": REF_SEGUNDOS, "por": "whisper"}


_OUVIR = r"""
import sys, json
from faster_whisper import WhisperModel
m = WhisperModel("small", device="cpu", compute_type="int8")
segs, _ = m.transcribe(sys.argv[1], language=sys.argv[2], beam_size=5)
print(json.dumps({"texto": " ".join(s.text.strip() for s in segs)}, ensure_ascii=False))
"""


def _pythons_com_whisper():
    """Onde procurar o faster-whisper, na ordem.

    07/11/2026: isto comecou chamando `py -3.12` fixo, copiado do `prova_voz.py`. Errado
    para quem INSTALA: `py -3.12` e uma particularidade desta maquina (veio do projeto dos
    Poemas). O certo e tentar PRIMEIRO o python que esta rodando o painel - se a biblioteca
    estiver nele, funciona em qualquer instalacao sem depender de mais nada.
    """
    vias = [sys.executable]
    vias += ["py -3.12", "py -3.11"]   # so para quem ja tinha, como esta maquina
    return vias


def _ouvir_local(arquivo, idioma="pt"):
    """Transcreve com o faster-whisper. Devolve o texto.

    Numa instalacao sem a biblioteca isto FALHA - e tudo bem: quem chama transforma a falha
    em instrucao ("instale assim, ou deixe o campo em branco"), que e honesto e funciona.
    """
    erros = []
    for via in _pythons_com_whisper():
        cmd = (via.split() if " " in via else [via]) + ["-c", _OUVIR, str(arquivo), idioma]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=900,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception as e:
            erros.append("%s: %s" % (via, e))
            continue
        linhas = [l for l in (r.stdout or "").splitlines() if l.strip().startswith("{")]
        if linhas:
            return json.loads(linhas[-1]).get("texto", "").strip()
        erros.append("%s: %s" % (via, (r.stderr or "").strip()[-120:] or "sem resposta"))
    raise RuntimeError(" | ".join(erros[:2]) or "nenhum python com faster-whisper")


async def clonar(caminho_audio, nome=None, transcricao=None, idioma="pt", entrega=None,
                 base_mcp=None):
    """Clona a voz de um áudio de referência. Devolve o profile_id.

    A transcrição NO IDIOMA CERTO é o que separa clone bom de voz embaralhada: foi assim que
    os dois vídeos de 18 e 19/10 produziram áudio ininteligível — a referência estava marcada
    como inglês. Por isso aqui ela é pedida, não opcional de verdade.

    `base_mcp` é a pasta que o VoiceStudio recebeu em OMNIVOICE_MCP_BASE_PATH. Com ela, o
    áudio vai por caminho e não por dentro do pedido (ver o comentário do REF_SEGUNDOS).
    """
    p = Path(caminho_audio)
    if not p.is_file():
        raise RuntimeError("Não achei o áudio de referência: %s" % p)

    # 07/11/2026: conferimos o áudio ANTES, para AVISAR — nunca para impedir.
    #
    # Isto já recusou: áudio sem pausa era "ruim" e o botão ficava desligado. Reprovou uma
    # fala boa do ElevenLabs, e o dono cortou o assunto: "tem que deixar ele aceitando a
    # clonagem de voz sem ajustar o áudio original, porque nem todo mundo vai saber disso".
    # Está certo. Uma regra minha calibrada em dois arquivos não pode mandar em quem tem o
    # áudio na mão e ouvido para julgar.
    #
    # Quem recusa é o MOTOR, com o motivo dele, que é verdade. Nós só mostramos o que medimos.
    laudo = await asyncio.to_thread(conferir_referencia, p)
    if laudo.get("veredito") == "ruim":
        print("[voz] clonando mesmo com aviso: %s" % " ".join(laudo.get("motivos") or []),
              flush=True)

    pasta_ref = (Path(base_mcp) / "refs") if base_mcp else p.parent
    curto = await asyncio.to_thread(_recortar_referencia, p, pasta_ref, laudo.get("trecho") or 0.0)

    # Os nomes dos campos vêm da lista de ferramentas dele (30/10): é `ref_text`, não
    # "transcript", e `name` é obrigatório.
    base = {"name": (nome or "").strip() or "Voz clonada", "language": idioma}
    if transcricao:
        base["ref_text"] = transcricao
    if entrega:
        base["instruct"] = entrega

    vias = []
    if base_mcp:
        try:
            rel = curto.resolve().relative_to(Path(base_mcp).resolve())
            vias.append(("caminho", {"ref_audio_path": str(rel).replace("\\", "/")}))
        except ValueError:
            pass  # o recorte não ficou dentro da pasta base: só resta o base64
    vias.append(("base64", {"ref_audio_base64": base64.b64encode(curto.read_bytes()).decode()}))

    ultimo = None
    for _via, extra in vias:
        try:
            d = _json_do(await chamar("clone_voice", {**base, **extra}, timeout=300))
        except Exception as e:
            ultimo = str(e)
            continue
        if isinstance(d, dict) and d.get("error"):
            ultimo = str(d["error"])[:200]
            continue
        pid = (d or {}).get("profile_id") if isinstance(d, dict) else None
        if pid:
            _cache.update(vozes=None, ate=0.0)
            return str(pid)
        ultimo = "ele respondeu sem a voz"

    raise RuntimeError("Não consegui clonar: %s. O áudio precisa ser limpo, sem música e sem "
                       "outra pessoa falando junto." % (ultimo or "sem resposta"))


AJUSTES_REAIS = ("speed", "steps")
# MEDIDO em 30/10, um por um, contra o motor rodando:
#   speed    ok   — velocidade da fala
#   steps    ok   — capricho (mais passos, mais tempo de placa)
#   instruct NÃO  — a lista de ferramentas ANUNCIA o campo, mas o generate_speech devolve
#                   400 com ele, mesmo com uma voz escolhida. Ele vale no clone_voice e no
#                   design_voice: a ENTREGA entra na VOZ, não em cada fala.
#   temperature / cfg / top_p — não existem (eu tinha chutado).
# Anunciado não é o mesmo que aceito: o que vale é o que respondeu OK no teste.


async def _falar_preset(texto, saida, preset, idioma="pt", formato="wav", ajustes=None):
    """Fala uma voz predefinida do motor (Kokoro etc.). O MCP não aceita preset; o HTTP aceita."""
    form = {"text": texto, "preset_voice": str(preset)}
    if idioma:
        form["language"] = idioma
    vel = (ajustes or {}).get("speed")
    if vel:
        form["speed"] = str(vel)
    async with _vez:
        t0 = time.time()
        async with aiohttp.ClientSession() as ses:
            async with ses.post(URL.rstrip("/") + "/generate", data=form,
                                timeout=aiohttp.ClientTimeout(total=TEMPO_FALA)) as r:
                dados = await r.read()
                if r.status >= 400:
                    raise RuntimeError("O VoiceStudio recusou a voz %s (%s): %s"
                                       % (preset, r.status, dados[:200]))
        demorou = time.time() - t0
    if not dados:
        raise RuntimeError("Ele respondeu, mas sem áudio. Veja a janela do VoiceStudio.")
    p = Path(saida)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(dados)
    return {"caminho": str(p), "bytes": len(dados), "demorou": round(demorou, 1),
            "segundos": _duracao_wav(dados)}


async def falar(texto, saida, voz_id=None, idioma="pt", formato="wav", ajustes=None):
    """Gera a fala e salva em `saida`. Devolve {segundos, caminho, demorou}.

    Se a versão instalada recusar algum ajuste por campo desconhecido, repetimos sem eles —
    o estúdio tem de funcionar igual em versões diferentes do VoiceStudio, na máquina de
    quem baixar, em vez de quebrar.
    """
    texto = (texto or "").strip()
    if not texto:
        raise RuntimeError("Sem texto para falar.")
    presets = await presets_do_motor()
    if voz_id and any(str(p.get("id")) == str(voz_id) for p in presets):
        return await _falar_preset(texto, saida, voz_id, idioma, formato, ajustes)
    base = {"text": texto, "format": formato}
    if voz_id:
        base["profile_id"] = voz_id
    if idioma:
        base["language"] = idioma
    extras = {k: v for k, v in (ajustes or {}).items()
              if k in AJUSTES_REAIS and v not in (None, "")}

    async with _vez:  # uma geração por vez
        t0 = time.time()
        try:
            res = await chamar("generate_speech", {**base, **extras}, timeout=TEMPO_FALA)
        except RuntimeError as e:
            # Ele recusa campo desconhecido com um "400 Bad Request" seco, sem dizer qual.
            # Por isso a repetição vale para QUALQUER recusa quando havia extras: a narração
            # sair sem o ajuste fino é melhor do que não sair.
            if not extras:
                raise
            res = await chamar("generate_speech", base, timeout=TEMPO_FALA)
        demorou = time.time() - t0

    dados, url = _audio_do(res)
    if dados is None and url:
        endereco = url if url.startswith("http") else URL.rstrip("/") + "/" + url.lstrip("/")
        async with aiohttp.ClientSession() as ses:
            async with ses.get(endereco, timeout=aiohttp.ClientTimeout(total=120)) as r:
                dados = await r.read()
    if not dados:
        raise RuntimeError("Ele respondeu, mas sem áudio. Veja a janela do VoiceStudio.")
    p = Path(saida)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(dados)
    return {"caminho": str(p), "bytes": len(dados), "demorou": round(demorou, 1),
            "segundos": _duracao_wav(dados)}


async def transcrever(caminho_audio, idioma="pt"):
    """Ouve um áudio e devolve o texto. É com isto que a gente confere a própria voz.

    Manda o áudio em base64 e NÃO pelo caminho: por caminho ele exige uma pasta configurada
    no servidor (`OMNIVOICE_MCP_BASE_PATH`) e, sem ela, responde um ERRO que parece
    transcrição vazia. Foi assim que a primeira prova acusou "1 de 68 palavras" num áudio
    que estava perfeito — verificador que mente é pior que verificador nenhum.
    """
    p = Path(caminho_audio)
    if not p.is_file():
        raise RuntimeError("Não achei o áudio: %s" % p)
    d = _json_do(await chamar("transcribe", {
        "audio_base64": base64.b64encode(p.read_bytes()).decode(),
        "language": idioma}, timeout=300))
    if isinstance(d, dict):
        if d.get("error"):
            raise RuntimeError(str(d["error"])[:300])
        return str(d.get("text") or d.get("transcript") or d.get("result") or "").strip()
    return str(d or "").strip()


def _duracao_wav(dados):
    """Duração do WAV lendo o cabeçalho — sem ffmpeg, sem biblioteca.

    É este número que importa para a narração: a conta de "13,2 letras por segundo" é
    estimativa, e só o áudio gerado confirma onde cada fala cai de verdade.
    """
    try:
        if dados[:4] != b"RIFF" or dados[8:12] != b"WAVE":
            return None
        i, taxa, bloco = 12, None, None
        while i + 8 <= len(dados):
            pedaco, tam = dados[i:i + 4], int.from_bytes(dados[i + 4:i + 8], "little")
            corpo = dados[i + 8:i + 8 + tam]
            if pedaco == b"fmt " and len(corpo) >= 16:
                taxa = int.from_bytes(corpo[4:8], "little")
                bloco = int.from_bytes(corpo[12:14], "little")
            elif pedaco == b"data" and taxa and bloco:
                return round(tam / (taxa * bloco), 2)
            i += 8 + tam + (tam % 2)
    except Exception:
        pass
    return None
