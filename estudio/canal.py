"""Canal automático — a esteira de um vídeo narrado, do texto ao arquivo pronto.

O QUE ISTO É
------------
O estúdio já sabia fazer cada peça (imagem, vídeo, pessoa falando, música) separada.
Isto é a ESTEIRA: texto -> voz -> tempos -> imagens de apoio -> a pessoa falando ->
montagem. É o que estava em linha de comando e em arquivo JSON escrito à mão.

Serve a QUALQUER canal, não só aum canal especifico: a pasta do canal é um ajuste
(`canal_dir` nas preferências, ou ESTUDIO_CANAL_DIR). O que muda de canal para canal é a
pasta e a voz; o resto da esteira é igual.

AS SEIS ETAPAS (é assim que a tela mostra o andamento)
------------------------------------------------------
  1 texto      narracao.txt           escrito por você
  2 voz        narracao_v4.mp3        ElevenLabs (nuvem) ou VoiceStudio (local, de graça)
  3 tempos     tempos.json+palavras   onde cada palavra cai — é o que ancora as imagens
  4 cenas      cenas.json             qual imagem entra, e em qual PALAVRA
  5 apoio      apoio/*.png            as imagens geradas
  6 pessoa     ..._inteiro.mp4        a pessoa falando (a parte longa)
  7 montagem   FINAL ANIMADO.mp4      o vídeo pronto

CUIDADOS QUE ESTÃO NO CÓDIGO
----------------------------
- A conta do tempo é MOSTRADA ANTES de começar. Medido: ~1,05 min de placa por segundo de
  fala. Um lote de 6 vídeos de 75 s é mais de 7 horas — quem não vê a conta antes promete
  o que não cabe na noite.
- A imagem entra na PALAVRA, não no relógio: quem resolve isso é o `cenas_ancoradas.py` do
  canal, e a gente só o alimenta.
- Nada é apagado e nada é publicado: a esteira para no arquivo pronto.
"""
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

import plataforma

# Pasta do canal. O painel guarda a dele em config.json (ajuste "canal_dir");
# ESTUDIO_CANAL_DIR tem prioridade. Isto aqui e so o chute inicial.
PADRAO = Path(os.environ.get("ESTUDIO_CANAL_DIR")
              or Path.home() / "Videos" / "meu-canal")
# ~1,05 min de placa por 1 s de fala, medido no lote 3 (9 vídeos) e confirmado depois.
MIN_POR_SEG_FALA = 1.05
LETRAS_SEG = 13.2          # a voz do senhor; é estimativa, o áudio é quem confirma
SEG_POR_IMAGEM = 25        # Krea 2, com o modelo já carregado

_fila = {"tarefa": None, "proc": None, "comecou": 0.0, "agora": None, "feitos": [], "falhas": []}


def pasta_canal(prefs=None):
    p = (prefs or {}).get("canal_dir") or os.environ.get("ESTUDIO_CANAL_DIR")
    return Path(p) if p else PADRAO


def _sem_acento(s):
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c))


def nome_de_pasta(titulo, numero=None):
    """'A pedra de Ebenézer' -> '87-a-pedra-de-ebenezer' — o mesmo formato das que existem."""
    s = re.sub(r"[^a-z0-9]+", "-", _sem_acento(titulo).lower()).strip("-")[:60]
    return ("%02d-%s" % (numero, s)) if numero else s


def proximo_numero(raiz):
    maior = 0
    pasta = raiz / "explicativos"
    if pasta.is_dir():
        for d in pasta.iterdir():
            m = re.match(r"^(\d+)", d.name)
            if d.is_dir() and m:
                maior = max(maior, int(m.group(1)))
    return maior + 1


# ----------------------------------------------------------------- o estado de um vídeo
ETAPAS = [
    ("texto",    "narracao.txt"),
    ("voz",      "narracao_v4.mp3"),
    ("tempos",   "tempos.json"),
    ("cenas",    "cenas.json"),
    ("apoio",    None),                       # conferido contra o cenas.json
    ("pessoa",   "senhor_falando_inteiro.mp4"),
    ("montagem", "FINAL ANIMADO (9x16).mp4"),
]


def estado_video(pasta):
    d = {"nome": pasta.name, "caminho": str(pasta)}
    feito = {}
    for chave, arq in ETAPAS:
        feito[chave] = (pasta / arq).is_file() if arq else False

    txt = ""
    if feito["texto"]:
        try:
            txt = (pasta / "narracao.txt").read_text(encoding="utf-8").strip()
        except Exception:
            txt = ""
    d["letras"] = len(txt)
    d["primeira_linha"] = txt.splitlines()[0][:110] if txt else ""

    # quantas imagens o cenas.json pede, e quantas já existem
    quer = tem = 0
    if feito["cenas"]:
        try:
            cfg = json.loads((pasta / "cenas.json").read_text(encoding="utf-8"))
            aps = cfg.get("apoio") or []
            quer = len(aps)
            tem = sum(1 for a in aps if (pasta / "apoio" / (a["id"] + ".png")).is_file())
        except Exception:
            pass
    feito["apoio"] = bool(quer) and tem >= quer
    d["apoio_tem"], d["apoio_quer"] = tem, quer
    d["tem_avatar"] = (pasta / "avatar.jpg").is_file() or (pasta / "avatar.png").is_file()

    # segundos de fala: o tempos.json é a verdade; antes dele, a estimativa por letras
    segundos = None
    if feito["tempos"]:
        try:
            segundos = float(json.loads((pasta / "tempos.json").read_text(encoding="utf-8"))["total"])
        except Exception:
            segundos = None
    d["segundos"] = round(segundos, 1) if segundos else (round(d["letras"] / LETRAS_SEG, 1) if d["letras"] else 0)
    d["segundos_medido"] = segundos is not None

    d["etapas"] = feito
    d["pronto"] = feito["montagem"]
    # o que falta de placa, em minutos: só a pessoa falando e as imagens que faltam pesam
    falta = 0.0
    if not feito["pessoa"] and d["segundos"]:
        falta += d["segundos"] * MIN_POR_SEG_FALA
    if quer > tem:
        falta += (quer - tem) * SEG_POR_IMAGEM / 60.0
    d["minutos_faltando"] = round(falta, 1)
    d["falta_avatar"] = not d["tem_avatar"] and not feito["pessoa"]
    return d


def listar(raiz):
    pasta = raiz / "explicativos"
    if not pasta.is_dir():
        return []
    vids = [estado_video(d) for d in sorted(pasta.iterdir())
            if d.is_dir() and (d / "narracao.txt").is_file()]
    vids.reverse()   # os mais novos em cima: é neles que se mexe
    return vids


# ----------------------------------------------------------------- criar um vídeo novo
def criar(raiz, titulo, texto):
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("Escreva o texto da narração.")
    if not (titulo or "").strip():
        raise ValueError("Dê um título ao vídeo.")
    # TRAVA CONTRA REPETIR: o número muda a cada vídeo novo, então dois vídeos com o mesmo
    # assunto nunca colidiriam de pasta — e passariam batido. Ele pediu DUAS VEZES na mesma
    # conversa para não repetir vídeo, então a conferência é pelo ASSUNTO, não pelo número.
    assunto = nome_de_pasta(titulo)
    pasta = raiz / "explicativos"
    if pasta.is_dir():
        for d in pasta.iterdir():
            if d.is_dir() and re.sub(r"^\d+-", "", d.name) == assunto:
                raise ValueError("Já existe um vídeo com esse assunto: %s. "
                                 "Mude o título ou apague o antigo." % d.name)
    destino = pasta / nome_de_pasta(titulo, proximo_numero(raiz))
    if destino.exists():
        raise ValueError("Já existe uma pasta com esse nome: %s" % destino.name)
    destino.mkdir(parents=True)
    (destino / "narracao.txt").write_text(texto + "\n", encoding="utf-8")
    return estado_video(destino)


# ----------------------------------------------------------------- as cenas, no automático
PEDIDO_CENAS = """Você escolhe as imagens de apoio de um vídeo narrado.

Abaixo está a narração. Escolha %d momentos e, para cada um, devolva:
- "gatilho": UMA palavra que aparece LITERALMENTE no texto, escrita exatamente como está lá.
  A imagem entra logo depois dessa palavra ser dita.
- "prompt": a descrição da imagem, EM INGLÊS, de um OBJETO ou LUGAR concreto.
  Nunca descreva rosto de pessoa. Nada de texto escrito na imagem.

Regras:
- a primeira escolha tem que ser o OBJETO QUE DÁ NOME ao vídeo;
- não repita gatilho;
- escolha palavras distantes entre si no texto, não todas no começo;
- responda SÓ com a lista JSON, sem nenhuma explicação.

Formato exato:
[{"gatilho":"palavra","prompt":"an english description of an object"}]

NARRAÇÃO:
%s"""


async def sugerir_cenas(pedir_texto, texto, quantas=6):
    """Pede à IA de texto do estúdio uma lista de (gatilho, prompt). Só sugere: quem decide
    se cabe é o cenas_ancoradas, que confere se a palavra existe mesmo na fala."""
    res = await pedir_texto("livre", PEDIDO_CENAS % (quantas, texto[:6000]))
    bruto = (res or {}).get("texto") or ""
    m = re.search(r"\[.*\]", bruto, re.S)
    if not m:
        raise ValueError("A IA de texto não devolveu uma lista. Escreva as cenas à mão.")
    try:
        itens = json.loads(m.group(0))
    except Exception:
        raise ValueError("A IA de texto devolveu uma lista quebrada. Tente de novo.")
    saida = []
    vistos = set()
    for x in itens:
        if not isinstance(x, dict):
            continue
        g = str(x.get("gatilho") or "").strip()
        p = str(x.get("prompt") or "").strip()
        if not g or not p or g.lower() in vistos:
            continue
        vistos.add(g.lower())
        saida.append({"gatilho": g, "prompt": p})
    if not saida:
        raise ValueError("Nenhuma cena aproveitável veio da IA de texto.")
    return saida


def escrever_cenas(raiz, pasta, itens):
    """Grava o cenas.json usando o cenas_ancoradas.py DO CANAL — é ele que confere se o
    gatilho existe na fala e que pula o apoio que não couber, em vez de jogá-lo em
    qualquer lugar."""
    script = raiz / "cenas_ancoradas.py"
    if not script.is_file():
        raise RuntimeError("Não achei o cenas_ancoradas.py em %s" % raiz)
    lista = [(i["gatilho"], i["prompt"], bool(i.get("prioritario"))) for i in itens]
    codigo = (
        "import sys, json, io, pathlib\n"
        "sys.path.insert(0, %r)\n"
        "from cenas_ancoradas import montar\n"
        "itens = json.loads(sys.argv[2])\n"
        "montar(pathlib.Path(sys.argv[1]), [tuple(x) for x in itens])\n"
    ) % str(raiz)
    r = subprocess.run([_py(), "-c", codigo, str(pasta), json.dumps(lista, ensure_ascii=False)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    if r.returncode:
        raise RuntimeError(((r.stdout or "") + (r.stderr or "")).strip()[-300:] or "falhou")
    return (r.stdout or "").strip()


def _py():
    """O python que tem o faster_whisper e as bibliotecas do canal é o 3.12 (o 'py' padrão
    virou 3.14). Isso já derrubou o tempos.py antes."""
    return "py" if plataforma.WIN else (shutil.which("python3.12") or shutil.which("python3") or sys.executable)


# ----------------------------------------------------------------- a fila
def conta_da_fila(raiz, nomes):
    """A conta ANTES de começar: quanto tempo de placa, e o que está faltando."""
    total = 0.0
    itens, sem_avatar = [], []
    for n in nomes:
        e = estado_video(raiz / "explicativos" / n)
        total += e["minutos_faltando"]
        itens.append({"nome": n, "minutos": e["minutos_faltando"], "pronto": e["pronto"]})
        if e["falta_avatar"]:
            sem_avatar.append(n)
    fim = time.time() + total * 60
    return {"minutos": round(total, 1), "horas": round(total / 60, 1),
            "termina": time.strftime("%H:%M", time.localtime(fim)),
            "itens": itens, "sem_avatar": sem_avatar}


def fila_estado():
    p = _fila["proc"]
    rodando = bool(p and p.poll() is None)
    if not rodando and p is not None:
        _fila["proc"] = None
    return {"rodando": rodando, "agora": _fila["agora"],
            "desde": round(time.time() - _fila["comecou"], 1) if rodando else 0,
            "feitos": _fila["feitos"], "falhas": _fila["falhas"]}


def comecar_fila(raiz, nomes, log):
    if fila_estado()["rodando"]:
        raise RuntimeError("Já tem uma fila rodando.")
    codigo = raiz / "fazer_tudo.py"
    if not codigo.is_file():
        raise RuntimeError("Não achei o fazer_tudo.py em %s" % raiz)
    roteiro = (
        "import subprocess, sys, pathlib, time\n"
        "raiz = pathlib.Path(%r)\n"
        "for nome in %r:\n"
        "    print('>>> ' + nome, flush=True)\n"
        "    subprocess.run([%r, str(raiz / 'fazer_tudo.py'), str(raiz / 'explicativos' / nome)])\n"
        "print('>>> FIM', flush=True)\n"
    ) % (str(raiz), list(nomes), _py())
    log.parent.mkdir(parents=True, exist_ok=True)
    f = open(log, "w", encoding="utf-8")
    _fila.update(proc=subprocess.Popen([_py(), "-c", roteiro], stdout=f, stderr=subprocess.STDOUT,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)),
                 comecou=time.time(), agora=nomes[0] if nomes else None, feitos=[], falhas=[])
    return fila_estado()


def parar_fila():
    p = _fila["proc"]
    if p and p.poll() is None:
        p.terminate()
    _fila["proc"] = None
    return fila_estado()
