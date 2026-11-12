"""Estúdio Local — imagem, vídeo e música num lugar só.

Roda com o Python da ComfyUI de vídeo (já tem aiohttp), porta 8194:
  ComfyUI_windows_portable\\python_embeded\\python.exe -s estudio\\server.py
Fala com a ComfyUI (8188) e embute o painel de música (painel_musica\\, porta 8190).

Música (14/11/2026): o painel de música vem no pacote (pasta painel_musica\\, ao lado desta) e usa a MESMA ComfyUI
da imagem e do vídeo. Quem liga o painel é o estúdio, com o Python da ComfyUI, e passa tudo o que depende da
máquina por variável de ambiente (ver ambiente_do_painel). O painel nunca liga nem desliga a ComfyUI: pede aqui
(POST /api/servicos/ligar {"servico": "video"}). Não existem mais a "ComfyUI de música" (8189) nem o ACE-Step.

Variáveis de ambiente (todas opcionais):
  ESTUDIO_PORTA        porta (padrão 8194; instâncias de TESTE usam 8195–8199)
  ESTUDIO_DADOS        pasta de historico.json, tempos.json, vozes.json e vozes\\ (padrão: estudio\\)
  ESTUDIO_WEB          pasta da interface (padrão: estudio\\web)
  ESTUDIO_COMFY_URL    endereço da ComfyUI de vídeo (padrão http://127.0.0.1:8188)
  ESTUDIO_COMFY_DIR    pasta da ComfyUI com input\\ e output\\ (padrão: ComfyUI_windows_portable\\ComfyUI)
  ESTUDIO_MUSICA_URL   endereço do painel de música (padrão http://127.0.0.1:8190). O estúdio liga o painel NESTA
                       porta (passa PAINEL_PORTA), então trocar aqui troca a porta do painel inteiro, tela e tudo
  ESTUDIO_LIBERAR_MIN  minutos sem nenhum trabalho até descarregar os modelos da ComfyUI (padrão 10; 0 desliga)
  ESTUDIO_TEXTO_*      IA de texto (llama.cpp): portas e tempos — ver estudio\\texto.py
  ESTUDIO_TEXTO_AUTO_S segundos depois de iniciar para ligar a IA de texto "sempre pronta" (padrão 20)
  ESTUDIO_LOGS         pasta dos logs dos serviços que o estúdio liga (padrão outputs\\; testes usam outra)
  Só para TESTE (instância em outra porta), para nunca ligar uma 2ª ComfyUI de verdade:
  ESTUDIO_COMANDO_COMFY, ESTUDIO_COMANDO_PAINEL        linha de comando que o botão "Ligar" usa no lugar da de
                                                       verdade (ex.: um servidorzinho falso numa porta livre)
  (o painel de música de verdade a instância de teste só liga se ESTUDIO_MUSICA_URL apontar para outra porta)

IA de texto (23/09/2026): POST /api/texto e GET /api/texto/estado (CORS liberado para o painel de música). O estúdio liga
os llama-server sob demanda (placa 8180 / processador 8181), responde ocupado=true enquanto o texto usa a placa e
descarrega o modelo de texto antes de QUALQUER envio para a ComfyUI (ver texto.py).

Home com botões de ligar (23/09/2026):
  POST /api/servicos/ligar {"servico": "video"|"musica"|"texto"|"tudo"}  liga o que estiver desligado (responde na
       hora; o progresso aparece no /api/inicio como "ligando" com o tempo). "video" usa a MESMA linha de comando do
       lançador "Abrir Estudio.ps1" (lida de lá); "musica" liga o painel de música E a ComfyUI (a música usa a
       mesma da imagem e do vídeo).
  POST /api/texto/ligar      liga a IA de texto no PROCESSADOR com o Qwen3.5-9B já carregado e marca "manter ligada"
  POST /api/texto/desligar   desliga os dois servidores de texto e desmarca
  GET/POST /api/preferencias {"texto_sempre_ligada": true} (config.json em ESTUDIO_DADOS): com ela ligada, o estúdio
       liga a IA de texto sozinho uns 20 s depois de iniciar, em segundo plano.
  /api/inicio devolve "servicos" {chave: {"estado": ligado|ligando|desligado|erro, ...}} e texto.simples.estado
       (pronta | em espera | ligando | na placa agora | erro); a tela nunca fica sem resposta (cada parte é protegida).
"""
import asyncio
import copy
import hashlib
import json
import math
import mimetypes
import os
import random
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.parse
import uuid
from datetime import datetime
from pathlib import Path

import aiohttp
from aiohttp import web

sys.path.insert(0, str(Path(__file__).resolve().parent))  # python_embeded não inclui a pasta do script
import plataforma  # noqa: E402  (o que muda entre Windows e macOS)
plataforma.completar_path()
import cofre  # noqa: E402  (os presets e workflows fechados: ver cofre.py)
import ias  # noqa: E402  (instalar cada IA depois, pela tela: ver ias.py)
import motor  # noqa: E402  (instalar a ComfyUI pelo botao: ver motor.py)
import requisitos  # noqa: E402  (ffmpeg e VoiceStudio pelo botao: ver requisitos.py)
# 14/11/2026: o Python do instalador veio SEM o psutil ate esta data. Ligar funcionava, mas
# DESLIGAR qualquer motor respondia "500 Server got itself in trouble", sem dizer o motivo.
# Agora ele vai no requirements.txt; e quem instalou antes fica sabendo, aqui e na tela.
try:
    import psutil as _psutil_conferido  # noqa: F401
    FALTA_PSUTIL = False
except ImportError:
    FALTA_PSUTIL = True
    print("[estúdio] FALTA a biblioteca psutil neste Python: desligar os motores não vai funcionar. "
          "Instale de novo pelo ForjaStudio-Instalador.exe (o que você já baixou continua no lugar).", flush=True)
requisitos.ativar_ffmpeg()     # o ffmpeg da pasta do estudio vale para este processo
import enquadrar  # noqa: E402
import licenca  # noqa: E402  (conta e licenca: ver licenca.py)
import atualizacao  # noqa: E402  (configuracao nova vinda do servidor)
import apresentador  # noqa: E402
import voz  # noqa: E402
import texto  # noqa: E402
import elevenlabs  # noqa: E402  (voz na nuvem, opcional: só funciona se a chave estiver em API\elevenlabs.txt)
import voz_studio  # noqa: E402  (voz LOCAL e de graça, opcional: só funciona com o VoiceStudio aberto)
import canal  # noqa: E402  (a esteira do Canal automático)

# o registro do Windows às vezes diz que .js é text/plain; a interface precisa dos tipos certos
for _tipo, _ext in (("text/javascript", ".js"), ("text/css", ".css"), ("font/woff2", ".woff2"),
                    ("image/svg+xml", ".svg"), ("application/json", ".json")):
    mimetypes.add_type(_tipo, _ext)

AQUI = Path(__file__).resolve().parent
ROOT = AQUI.parent
NOME_PASTA_IAS = "ForjaStudio-IAs"      # a pasta criada no disco que a pessoa escolher


def _comfy_dir_inicial():
    """Onde esta (ou vai ficar) a ComfyUI com os modelos. UMA fonte para o painel inteiro.

    1. ESTUDIO_COMFY_DIR  - o caminhos.bat de quem configurou a mao: manda em tudo;
    2. "pasta_ias" do config.json - o disco que a pessoa escolheu na tela inicial;
    3. a pasta do proprio painel - o padrao de sempre.
    """
    if os.environ.get("ESTUDIO_COMFY_DIR"):
        return Path(os.environ["ESTUDIO_COMFY_DIR"])
    try:
        cfg = Path(os.environ.get("ESTUDIO_DADOS") or AQUI) / "config.json"
        base = (json.loads(cfg.read_text(encoding="utf-8")).get("pasta_ias") or "").strip()
    except (OSError, ValueError, AttributeError):
        base = ""
    raiz = Path(base) if base else ROOT
    return plataforma.comfy_dir(raiz)


COMFY_DIR = _comfy_dir_inicial()
ias.MODELOS = COMFY_DIR / "models"      # o download vai para o MESMO lugar que o motor le


def _pasta_da_voz():
    """Onde o VoiceStudio fica: ao lado das IAs, no disco que a pessoa escolheu."""
    return COMFY_DIR.parent.parent / "VoiceStudio"


voz_studio.OUTRAS[:] = [_pasta_da_voz()]


def _apontar_o_texto():
    """Os modelos de texto moram no disco das IAs. Instalacao antiga (ao lado do painel) fica."""
    antiga = ROOT / "modelos_texto"
    pasta = antiga if (antiga / "modelos.ini").is_file() else COMFY_DIR.parent.parent / "modelos_texto"
    texto.usar_pasta(pasta)
    requisitos.TEXTO["pasta_modelos"] = str(pasta)
    texto.escrever_ini()        # caminho completo dentro: refaz se a pasta mudou


_apontar_o_texto()
# Instância de TESTE: ESTUDIO_DADOS aponta para uma CÓPIA dos dados (histórico/tempos/vozes) e ESTUDIO_WEB para a
# pasta da interface em desenvolvimento, para testar sem mexer no estúdio de produção (8194).
DADOS = Path(os.environ["ESTUDIO_DADOS"]) if os.environ.get("ESTUDIO_DADOS") else AQUI
WEB = Path(os.environ["ESTUDIO_WEB"]) if os.environ.get("ESTUDIO_WEB") else AQUI / "web"
VOZES_DIR = DADOS / "vozes"  # biblioteca de vozes clonadas: o áudio de referência fica guardado aqui
VOZES_JSON = DADOS / "vozes.json"
FICHAS_JSON = AQUI / "fichas.json"  # fichas das IAs (texto da tela, fonte única)
COMFY = os.environ.get("ESTUDIO_COMFY_URL") or "http://127.0.0.1:8188"
MUSICA = (os.environ.get("ESTUDIO_MUSICA_URL") or "http://127.0.0.1:8190").rstrip("/")
# A música (14/11/2026): o painel vem no pacote e os dados de quem usa (lista de músicas, envios) ficam na pasta
# de dados do estúdio, FORA da pasta do código - a pasta do código é trocada inteira numa atualização.
PAINEL_DIR = ROOT / "painel_musica"
MUSICA_DADOS = DADOS / "musica"
PAINEL_JOBS = MUSICA_DADOS / "jobs.json"  # só leitura: contagem de músicas na tela inicial
PORTA = int(os.environ.get("ESTUDIO_PORTA", 8194))
try:
    LIBERAR_MIN = float(os.environ.get("ESTUDIO_LIBERAR_MIN") or 10)
except ValueError:
    LIBERAR_MIN = 10.0
COMFY_FORA_S = 60  # ComfyUI sem responder por mais que isso, com trabalho rodando = erro
REVISAR_VIGIA_S = 6 * 3600  # trabalho que o vigia marcou como erro: continua sendo conferido por 6 h
CEDER_MAX_S = 60  # [C] cede a vez para música pedida antes, mas no máximo 60 s se o estúdio não estiver na placa
# Nomes que o PRÓPRIO estúdio cria em ComfyUI\input (só esses podem ser apagados ao remover um trabalho;
# o resto da pasta input é do dono: ghibli_start.png, placa_*.png, teste_*.png, example.png...)
RE_UPLOAD = re.compile(r"estudio_[0-9a-f]{10}(?:_16fps\.mp4|_voz\.wav|\.[A-Za-z0-9]+)")
RE_ENQ = re.compile(r"enq_[0-9a-f]{12}\.(?:png|json)")
FPS_ANIMATE = 16
SEG_ANIMATE = 81  # quadros por trecho do Wan Animate (cada extensão reaproveita 5 do anterior)
CLIENT_ID = "estudio-local" if PORTA == 8194 else f"estudio-teste-{PORTA}"  # teste não rouba os eventos
HIST = DADOS / "historico.json"
TEMPOS = DADOS / "tempos.json"
VOZ_MOTOR = "Chatterbox Multilingual"

# 04/11/2026: os presets podem estar dentro do cofre (pacote publicado) ou soltos aqui
# (maquina de desenvolvimento). O cofre so abre com a chave que a VPS da a quem tem conta -
# por isso a carga NAO pode derrubar o painel: sem conta ainda, PRESETS fica vazio e a tela
# pede para entrar, em vez de o programa nem subir. Ver estudio/cofre.py.
try:
    PRESETS = cofre.ler_json("presets.json")
except cofre.CofreFechado:
    PRESETS = {}


def _ler_json_ou_avisar(arq, vazio):
    """Le um arquivo de estado SEM deixar que ele impeca o painel de subir.

    07/11/2026: a maquina reiniciou no tranco e o Windows deixou o historico.json com o
    tamanho certo (4,2 MB) e TODOS os bytes zerados - dano classico de NTFS quando o
    arquivo nao chegou a ser gravado de verdade. O painel morria aqui, na linha 122, antes
    de abrir a porta: a pagina ficava girando "Abrindo o estudio" para sempre e so o
    estudio_stderr.log sabia o motivo. Mesmo principio do cofre, logo acima: carregar
    estado NAO pode derrubar o painel.

    Arquivo ilegivel vai para o lado com a data no nome (nunca apagado: pode haver resto
    recuperavel) e o painel sobe com o estado vazio, gritando no log o que aconteceu.
    """
    if not arq.exists():
        return vazio
    try:
        return json.loads(arq.read_text(encoding="utf-8"))
    except Exception as e:
        destino = arq.with_name(arq.name + ".quebrado_" + time.strftime("%Y-%m-%d_%H%M%S"))
        try:
            arq.rename(destino)
            onde = destino.name
        except Exception:
            onde = "nao consegui mover o arquivo"
        print("[estudio] ATENCAO: %s estava ilegivel (%s). Guardei como %s e comecei do zero. "
              "Se havia copia de seguranca, da para repor o arquivo e reiniciar." % (arq.name, e, onde),
              flush=True)
        return vazio


JOBS = _ler_json_ou_avisar(HIST, [])
STATS = _ler_json_ou_avisar(TEMPOS, {})
ULTIMO_PRESET = {"id": next((j["preset"] for j in reversed(JOBS) if j.get("estado") == "concluido"), None)}

# Estado só da memória (não vai para o historico.json)
ENVIO = asyncio.Lock()      # manda um trabalho por vez para a placa (e na ordem em que foram pedidos)
RECONC = asyncio.Lock()
TAREFAS_ATIVAS = set()      # ids com tarefa viva (esperando a vez/música, voz do Apresentador, enquadramento)
CANCELAR = set()            # ids que o dono mandou cancelar enquanto a tarefa ainda estava viva
CONCLUINDO = set()
SUMIDOS = {}                # id -> hora em que o prompt sumiu (nem na fila nem no histórico da ComfyUI)
ORFAOS = {}                 # prompt_id -> [hora, eventos] que chegaram antes de o trabalho registrar o prompt_id
RESERVA = {"ate": 0.0}      # [C] o estúdio está mandando algo para a placa (o painel de música deve esperar)
PAINEL_INFO = {"esperando_desde": None}  # [C] desde quando a música mais antiga do painel espera a placa
COMFY_ESTADO = {"online": None, "fora_desde": None}
ATIVIDADE = {"ultima": time.time(), "liberado": False}
SEGUNDO_PLANO = set()
TEXTO = texto.MotorTexto()  # IA de texto (llama.cpp): liga/desliga os servidores e segue a regra da placa
_CACHE_VIDEO = {}
_FICHAS = {"mtime": None, "visto": 0.0, "dados": {"ias": {}}}
_MUSICAS = {"mtime": None, "n": None}


def em_segundo_plano(coro):
    t = asyncio.get_running_loop().create_task(coro)
    SEGUNDO_PLANO.add(t)
    t.add_done_callback(SEGUNDO_PLANO.discard)
    return t


def _gravar(arq, dados):
    """Grava num .tmp e troca (se o PC desligar no meio, o arquivo antigo continua inteiro)."""
    txt = json.dumps(dados, ensure_ascii=False, indent=1)
    tmp = arq.with_name(arq.name + ".tmp")
    try:
        tmp.write_text(txt, encoding="utf-8")
        for _ in range(5):
            try:
                os.replace(tmp, arq)
                return
            except PermissionError:
                time.sleep(0.1)
    except OSError:
        pass
    arq.write_text(txt, encoding="utf-8")
    tmp.unlink(missing_ok=True)


def salvar():
    _gravar(HIST, JOBS)
    _gravar(TEMPOS, STATS)


# ---------------------------------------------------------------- utilitários
def sem_acento(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


def achar_chave(opcoes, nome, antigos=None):
    """Nome atual de uma opção (qualidade, resolução, estilo...), aceitando nomes antigos e texto sem acento.
    Trabalhos antigos gravaram 'Rapido', 'Maxima (48)', '1 MP (padrao)'... e o Reusar continua funcionando."""
    if not isinstance(nome, str) or not opcoes:
        return None
    if nome in opcoes:
        return nome
    if antigos and antigos.get(nome) in opcoes:
        return antigos[nome]
    alvo = sem_acento(nome)
    return next((k for k in opcoes if sem_acento(k) == alvo), None)


def motor_rotulo(p, motor):
    """Rótulo completo do motor do Apresentador ('LTX' -> 'LTX-2.3 (rápido, até 15 s)')."""
    motores = p.get("motores") or []
    m = achar_chave(motores, motor)
    if m:
        return m
    alvo = sem_acento(motor)
    if alvo:
        m = next((k for k in motores if sem_acento(k).startswith(alvo)), None)
        if m:
            return m
    return (p.get("padrao") or {}).get("motor") or "Automático"


def preset_ou_none(pid):
    for aba in ("imagem", "video"):
        for p in PRESETS.get(aba, []):
            if p["id"] == pid:
                return aba, p
    return None, None


def preset(pid):
    aba, p = preset_ou_none(pid)
    if not p:
        raise web.HTTPBadRequest(text=f"Modelo desconhecido: {pid}. Ele pode ter sido removido do estúdio.")
    return aba, p


def achar_job(jid):
    return next((x for x in JOBS if x.get("id") == jid), None)


def trabalhos_ativos():
    return [j for j in JOBS if not j.get("lixeira") and j.get("estado") in ("fila", "rodando")]


def fichas():
    """fichas.json lido do disco (relido quando o arquivo muda)."""
    agora = time.time()
    if agora - _FICHAS["visto"] > 2:
        _FICHAS["visto"] = agora
        try:
            m = FICHAS_JSON.stat().st_mtime
            if m != _FICHAS["mtime"]:
                _FICHAS["dados"] = json.loads(FICHAS_JSON.read_text(encoding="utf-8"))
                _FICHAS["mtime"] = m
        except (OSError, ValueError) as exc:
            print(f"[estúdio] não consegui ler fichas.json: {exc}")
    return _FICHAS["dados"]


def ficha(pid):
    return (fichas().get("ias") or {}).get(pid)


def fmt_seg(s):
    s = float(s)
    return f"{s:.0f} s" if s >= 10 or s == int(s) else f"{s:.1f} s".replace(".", ",")


def nome_curto(nome):
    return re.sub(r"\s*\([^)]*\)", "", nome or "").strip() or nome


# ---------------------------------------------------------------- "qual IA gerou"
def motor_apresentador(j):
    if j.get("motor_usado"):
        return j["motor_usado"]
    amos = j.get("amostradores") or []  # trabalhos antigos: descobre pelo fluxo que foi mandado
    if any(str(a).startswith("340:") for a in amos):
        return "LTX-2.3"
    if any(re.fullmatch(r"t\d+_k", str(a)) for a in amos):
        return "InfiniteTalk"
    return None


def texto_voz(j):
    if j.get("audio"):
        return "áudio enviado"
    if j.get("voz_nome"):
        return f"{VOZ_MOTOR} · {j['voz_nome']}"
    if j.get("voz"):
        return f"{VOZ_MOTOR} · voz clonada do áudio enviado"
    return f"{VOZ_MOTOR} · voz padrão"


def info_ia(j):
    """Campo 'ia' de todo trabalho: {id, nome, motor, voz, resumo}."""
    _, p = preset_ou_none(j.get("preset"))
    f = ficha(j.get("preset")) or {}
    nome = f.get("nome") or (p or {}).get("nome") or j.get("nome") or j.get("preset") or "IA desconhecida"
    motor = voz_txt = None
    if j.get("preset") == "apresentador":
        motor = motor_apresentador(j)
        voz_txt = texto_voz(j)
    partes = [nome_curto(nome)]
    if motor:
        partes.append(motor)
    est = j.get("estilo")
    if est and sem_acento(est) != "livre":
        partes.append(est)
    if j.get("duracao") and j["duracao"] != "Igual ao vídeo":
        partes.append(j["duracao"])
    elif j.get("segundos_video"):
        partes.append(fmt_seg(j["segundos_video"]))
    elif j.get("segundos_audio"):
        partes.append(fmt_seg(j["segundos_audio"]))
    tam = j.get("tamanho")
    if isinstance(tam, (list, tuple)) and len(tam) == 2 and all(tam):
        partes.append(f"{tam[0]}×{tam[1]}")
    else:
        if j.get("formato") and j["formato"] != "Igual ao vídeo":
            partes.append(j["formato"])
        if j.get("resolucao"):
            partes.append(j["resolucao"].split(" (")[0])
    return {"id": j.get("preset"), "nome": nome, "motor": motor, "voz": voz_txt, "resumo": " · ".join(partes)}


def extra_data(job, motor=None, prompt=None, ia=None):
    """Vai junto em TODO POST /prompt: a ComfyUI grava isso dentro do PNG/MP4/FLAC (metadado 'estudio_local')."""
    info = info_ia(job)
    return {"extra_pnginfo": {"estudio_local": {
        "ia": ia or info["nome"], "preset": job.get("preset"), "motor": motor or info.get("motor"),
        "voz": info.get("voz"), "prompt": job.get("prompt") if prompt is None else prompt,
        "seed": job.get("seed"), "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "trabalho": job.get("id"), "gerado_por": "Estúdio Local (ComfyUI MCP)"}}}


def marcar(job, estado, msg=None):
    job["estado"] = estado
    job["fim"] = time.time()
    if msg:
        job["erro"] = msg
    job.pop("aguardando", None)
    ATIVIDADE["ultima"] = time.time()


def erro_legivel(tipo, msg):
    """Frase em português para um erro da ComfyUI durante a geração (o texto técnico vai em job['erro_tecnico'])."""
    t = f"{tipo or ''} {msg or ''}"
    tl = t.lower()
    if "OutOfMemory" in t or "out of memory" in tl or "Allocation on device" in t:
        return ("Faltou memória na placa de vídeo. Tente com resolução ou duração menor "
                "(ou libere a memória e tente de novo).")
    if "filenotfound" in tl or "no such file" in tl or "não foi possível encontrar" in tl:
        return "A ComfyUI não achou um arquivo que o fluxo precisa (modelo ou arquivo enviado). Envie de novo ou confira os modelos."
    if any(x in tl for x in ("given groups", "size mismatch", "shapes cannot be multiplied", "must match the size",
                              "expected input", "sizes of tensors", "mat1 and mat2")):
        return ("Os tamanhos não bateram dentro do modelo (resolução, formato ou arquivo de modelo incompatível). "
                "Tente outra resolução ou outro formato.")
    if "headertoolarge" in tl or "safetensor" in tl or "unexpected end" in tl or "corrupt" in tl:
        return "O arquivo do modelo parece corrompido ou incompleto. Baixe o modelo de novo."
    if "cuda" in tl or "cudnn" in tl or "cublas" in tl:
        return "A placa de vídeo deu erro (CUDA). Tente de novo; se repetir, reinicie a ComfyUI de vídeo."
    return "A ComfyUI deu erro durante a geração. Tente de novo; o detalhe técnico ficou guardado no trabalho."


def _arquivo_invalido(det):
    """'image - Invalid image file: x.png' -> ('imagem', 'x.png')."""
    m = re.search(r"Invalid (image|video|audio|file)[^:]*:\s*(.+)$", det or "")
    if not m:
        return None
    return {"image": "a imagem", "video": "o vídeo", "audio": "o áudio"}.get(m.group(1), "o arquivo"), m.group(2).strip()


def traduzir_erro_no(no, classe, er):
    """Um erro de validação de nó da ComfyUI em português."""
    tipo = er.get("type")
    ext = er.get("extra_info") or {}
    det = str(er.get("details") or "")
    entrada = ext.get("input_name") or re.split(r"[: ]", det, 1)[0] or "?"
    onde = f"nó {no}, {classe}"
    if tipo == "value_not_in_list":
        val = ext.get("received_value")
        if entrada.endswith("_name") or entrada in ("ckpt", "lora", "model", "vae", "clip", "unet"):
            return (f"O arquivo do modelo “{val}” não está na pasta de modelos da ComfyUI ({onde}). "
                    "Baixe o modelo ou escolha outra IA.")
        if entrada in ("image", "video", "audio", "file", "upload"):
            return f"O arquivo “{val}” não está na pasta input da ComfyUI ({onde}). Envie de novo."
        return f"O valor “{val}” não é aceito na opção “{entrada}” ({onde})."
    if tipo == "required_input_missing":
        return f"Falta a entrada obrigatória “{entrada}” ({onde}). O fluxo desta IA precisa ser atualizado."
    if tipo == "custom_validation_failed":
        inv = _arquivo_invalido(det)
        if inv:
            return f"Não achei {inv[0]} “{inv[1]}” na pasta input da ComfyUI (ou o arquivo não é válido). Envie de novo."
        return f"A ComfyUI não aceitou o valor de “{entrada}” ({onde})."
    if tipo == "return_type_mismatch":
        return f"Ligação incompatível no fluxo ({onde}). O fluxo desta IA precisa ser atualizado."
    if tipo == "exception_during_validation":
        inv = _arquivo_invalido(det)
        if inv:
            return f"Não achei {inv[0]} “{inv[1]}” na pasta input da ComfyUI. Envie de novo."
        return f"A ComfyUI teve um erro ao conferir o fluxo ({onde})."
    return f"A ComfyUI encontrou um problema no fluxo ({onde})."


def explicar_recusa(status, txt):
    """Frase em português quando a ComfyUI recusa um pedido (ex.: 400 com node_errors)."""
    try:
        d = json.loads(txt)
    except ValueError:
        d = None
    if not isinstance(d, dict):
        return f"A ComfyUI de vídeo respondeu com erro ({status}). Tente de novo em instantes."
    partes = []
    e = d.get("error") if isinstance(d.get("error"), dict) else {}
    tipo = e.get("type")
    if tipo == "missing_node_type":
        classe = (e.get("extra_info") or {}).get("class_type")
        partes.append(f"A ComfyUI de vídeo não tem o nó “{classe}”. Falta instalar ou atualizar um custom node."
                      if classe else "O fluxo está incompleto (um nó sem tipo). O fluxo desta IA precisa ser atualizado.")
    elif tipo == "prompt_no_outputs":
        partes.append("O fluxo não tem nenhum nó que salve o resultado.")
    ne = d.get("node_errors") if isinstance(d.get("node_errors"), dict) else {}
    for no, info in ne.items():
        for er in (info or {}).get("errors", [])[:2]:
            if isinstance(er, dict):
                frase = traduzir_erro_no(no, (info or {}).get("class_type", "?"), er)
                if frase not in partes:
                    partes.append(frase)
    if not partes:
        partes.append("O pedido não passou na conferência da ComfyUI.")
    return "A ComfyUI recusou o trabalho: " + " ".join(partes[:4])


class RecusaComfy(web.HTTPBadGateway):
    """A ComfyUI respondeu com erro: frase em português no texto e a resposta original em .tecnico."""

    def __init__(self, texto, tecnico=None):
        super().__init__(text=texto)
        self.tecnico = tecnico


def guardar_tecnico(job, exc):
    tec = getattr(exc, "tecnico", None)
    if tec:
        job["erro_tecnico"] = str(tec)[:1500]


def msg_erro(exc):
    if isinstance(exc, web.HTTPException):
        return exc.text or exc.reason
    porta = COMFY.rsplit(":", 1)[-1]
    if isinstance(exc, (aiohttp.ClientConnectorError, ConnectionError)):
        return f"A ComfyUI de vídeo (porta {porta}) não está respondendo. Veja se ela está aberta e tente de novo."
    if isinstance(exc, asyncio.TimeoutError):
        return "A ComfyUI de vídeo demorou demais para responder."
    if isinstance(exc, aiohttp.ClientError):
        return f"Falha ao falar com a ComfyUI de vídeo: {exc}"
    return (str(exc) or exc.__class__.__name__)[:500]


def resposta_erro(exc):
    if isinstance(exc, web.HTTPException):
        return web.Response(status=exc.status, text=exc.text or exc.reason)
    return web.Response(status=502, text=msg_erro(exc))


def alvos(campo):
    """Aceita ["no","input"] ou [["no","input"], ...]."""
    if not campo:
        return []
    return [campo] if isinstance(campo[0], str) else campo


def setar(api, campo, valor):
    for no, entrada in alvos(campo):
        if no in api:
            api[no]["inputs"][entrada] = valor


def tamanho_final(p, dims):
    """Tamanho que o VIDEO SAI, nao o que a IA gera por dentro.

    O LTX 2.5 gera 640x360 e o proprio workflow passa num ampliador x2: o arquivo sai 1280x704.
    A tela mostrava 360x640 ao lado da palavra "720p" e parecia estar mentindo (02/11/2026).
    `dims` continua intocado porque e ele que alimenta a largura/altura do workflow.
    """
    if not dims:
        return dims
    try:
        k = float(p.get("escala_saida") or 1)
    except (TypeError, ValueError):
        k = 1
    if k == 1:
        return dims
    # o ampliador trabalha em latente: o lado desce para o multiplo de 32 mais proximo abaixo.
    # Conferido em 8 videos do LTX 2.5: 640x360 -> 1280x704 (e nao 1280x720).
    def lado(v):
        return max(32, int(v * k) // 32 * 32)
    return [lado(dims[0]), lado(dims[1])]


# ---------------------------------------------------------------- migração dos trabalhos antigos (em memória)
def normalizar_opcoes(j):
    """Troca nomes antigos/sem acento pelos atuais (o Reusar de trabalhos antigos volta a funcionar)."""
    _, p = preset_ou_none(j.get("preset"))
    if not p:
        return
    ant = p.get("nomes_antigos")
    res = p.get("resolucoes") or p.get("resolucoes_mp")
    for campo, opcoes in (("qualidade", p.get("qualidades")), ("resolucao", res), ("resolucao_padrao", res),
                          ("estilo", p.get("estilos")), ("duracao", p.get("duracoes")),
                          ("formato", p.get("formatos")), ("idioma", p.get("idiomas"))):
        v = j.get(campo)
        if isinstance(v, str) and opcoes:
            novo = achar_chave(opcoes, v, ant)
            if novo and novo != v:
                j[campo] = novo
    if p.get("tipo") == "apresentador" and j.get("motor"):
        j["motor"] = motor_rotulo(p, j["motor"])


def migrar_jobs():
    for j in JOBS:
        normalizar_opcoes(j)
        if j.get("estado") in ("fila", "rodando") and not j.get("prompt_id") and not j.get("lixeira"):
            # a tarefa que cuidava dele morreu junto com o estúdio anterior
            if j.get("preset") == "apresentador" and j.get("estado") == "rodando":
                marcar(j, "erro", "O estúdio foi reiniciado durante a geração da voz. Gere de novo.")
            else:
                marcar(j, "erro", "O estúdio foi reiniciado antes de mandar este trabalho para a ComfyUI. Gere de novo.")
        if j.get("preset") == "apresentador" and not j.get("motor_usado"):
            m = motor_apresentador(j)
            if m:
                j["motor_usado"] = m
        j["ia"] = info_ia(j)


migrar_jobs()


# ---------------------------------------------------------------- estimativa de tempo
def chave_tempo(job):
    k = f"{job['preset']}|{job.get('duracao') or ''}|{job.get('steps')}"
    if job.get("segmentos") and job.get("duracao") == "Igual ao vídeo":
        k += f"|seg{job['segmentos']}"
    if job.get("resolucao") and job["resolucao"] != job.get("resolucao_padrao"):
        k += f"|{job['resolucao'].split(' ')[0]}"
    return k


def estimativa_por_trecho(job):
    """Wan Animate com N trechos: usa o tempo médio por trecho das gerações ~5 s / ~10 s."""
    carga, trecho = [], []
    for dur, n in (("~5 s", 1), ("~10 s", 2)):
        for r in STATS.get(chave_tempo({**job, "duracao": dur, "segmentos": None, "resolucao": None}), [])[-5:]:
            carga.append(r["carga"])
            trecho.append((r["total"] - r["carga"]) / n)
    if not trecho:
        return None
    t = sum(trecho) / len(trecho) * job["segmentos"]
    return t + (3 if ULTIMO_PRESET["id"] == job["preset"] else sum(carga) / len(carga))


_LTX23 = {"quando": 0.0, "tem": False}


def ltx23_instalado():
    """Os modelos que o LTX-2.3 do Apresentador pede estao TODOS no disco?

    Sem esta pergunta, o "Automatico" mandava todo audio de ate 15 s para o LTX-2.3 - que
    quem instalou o Apresentador pelo botao NAO tem: os 40 GB dele nao fazem parte do
    Apresentador no catalogo. O painel dizia "instalada" e o primeiro video curto falhava.
    A resposta fica guardada 20 s: a estimativa de tempo pergunta isto a toda hora.
    """
    agora = time.time()
    if agora - _LTX23["quando"] < 20:
        return _LTX23["tem"]
    tem = False
    try:
        base = cofre.ler_json("presets/ltx23_ia2v.api.json")
        nomes = set(re.findall(r"[\w.\-]+\.(?:safetensors|gguf)", json.dumps(base)))
        cat = ias.catalogo()
        tem = bool(nomes)
        for nome in nomes:
            info = cat.get(nome)
            ok = ias.esta_completo(nome, info) if info else any((COMFY_DIR / "models").glob("*/" + nome))
            if not ok:
                tem = False
                break
    except Exception:
        tem = False
    _LTX23.update({"quando": agora, "tem": tem})
    return tem


def estimativa_apresentador(job):
    """~150 s por trecho de 3,2 s (medido: 8 s em 3 trechos), + voz, + carga se o modelo não estiver na memória."""
    seg = job.get("segundos_audio") or max(4.0, len(job.get("prompt") or "") / 18.0)
    voz_s = 0 if job.get("audio") else 30 + 8 * len(voz.dividir(job.get("prompt") or "x"))
    carga = 0 if ULTIMO_PRESET["id"] == "apresentador" else 240
    motor = job.get("motor_usado") or job.get("motor") or "Automático"
    if motor.startswith("LTX") or (sem_acento(motor).startswith("automatico")
                                   and seg <= apresentador.LTX_MAX_S and ltx23_instalado()):
        return 25 * seg + 60 + voz_s + carga  # medido: 8 s em ~436 s com carga do HD
    n = apresentador.num_trechos(int(seg * apresentador.FPS))
    return 150 * n + voz_s + carga


def estimativa(job):
    """Estimativa total (s) a partir do histórico; senão, do preset."""
    if job.get("preset") == "apresentador":
        return estimativa_apresentador(job)
    reg = STATS.get(chave_tempo(job))
    if reg:
        reg = reg[-5:]
        if ULTIMO_PRESET["id"] == job["preset"]:  # modelo já carregado: só geração + finalização
            return sum(r["total"] - r["carga"] for r in reg) / len(reg) + 3
        return sum(r["total"] for r in reg) / len(reg)
    fator = job.get("fator_res") or 1  # resolução maior sem histórico: escala pelo nº de pixels
    if fator != 1:
        return estimativa({**job, "resolucao": None, "fator_res": 1}) * fator
    if job.get("segmentos"):
        e = estimativa_por_trecho(job)
        return e if e else 540 * job["segmentos"]
    _, p = preset(job["preset"])
    if job.get("duracao") and p.get("estimativa_por_duracao_s"):
        return p["estimativa_por_duracao_s"].get(job["duracao"], 600)
    return p.get("estimativa_s", 120)


def estimativa_segura(job):
    """Nunca derruba a galeria (ex.: trabalho de um modelo que foi removido)."""
    try:
        return estimativa(job)
    except Exception:
        return None


# ---------------------------------------------------------------- ComfyUI: eventos, conclusão e vigia
def job_por_prompt(pid):
    return next((j for j in JOBS if j.get("prompt_id") == pid), None)


def registrar_prompt(job, pid):
    """Grava o prompt_id e reaplica eventos que chegaram antes (a ComfyUI pode começar antes da resposta)."""
    job["prompt_id"] = pid
    pend = ORFAOS.pop(pid, None)
    if pend:
        for m in pend[1]:
            ao_evento(m)


def ao_evento(msg):
    tipo, d = msg.get("type"), msg.get("data") or {}
    pid = d.get("prompt_id") if isinstance(d, dict) else None
    if not pid:
        return
    agora = time.time()
    ATIVIDADE["ultima"] = agora
    ATIVIDADE["liberado"] = False
    job = job_por_prompt(pid)
    if not job:
        for k in [k for k, v in ORFAOS.items() if agora - v[0] > 120]:
            ORFAOS.pop(k, None)
        lista = ORFAOS.setdefault(pid, [agora, []])[1]
        if len(lista) < 300:
            lista.append(msg)
        return
    p = job.setdefault("prog", {})
    if (job.get("erro_vigia") and job.get("estado") == "erro" and not job.get("lixeira")
            and tipo in ("execution_start", "executing", "progress")):
        # o vigia deu erro porque a ComfyUI ficou muda, mas ela só estava travada e continuou: volta a 'rodando'
        job["estado"] = "rodando"
        for k in ("erro", "erro_vigia", "fim"):
            job.pop(k, None)
        job.setdefault("inicio", agora)
    ativo = job.get("estado") in ("fila", "rodando")
    if tipo == "execution_start":
        if ativo:
            job["estado"] = "rodando"
            job["inicio"] = job.get("inicio_voz") or agora  # Apresentador: conta desde a geração da voz
            p.update(fase="Carregando modelo", passos=0)
    elif tipo == "executing" and d.get("node") is not None:
        p["no"] = d["node"]
        if d["node"] not in job.get("amostradores", []) and p.get("passos", 0) >= job.get("total_passos", 1):
            p["fase"] = "Finalizando (decodificando e salvando)"
    elif tipo == "progress" and d.get("node") in job.get("amostradores", []):
        if job.get("estado") == "fila":  # perdeu o execution_start: já está gerando
            job["estado"] = "rodando"
            job.setdefault("inicio", job.get("inicio_voz") or agora)
        feitos_antes = p.setdefault("concluidos", {})
        feitos_antes[d["node"]] = d["value"]
        p["passos"] = sum(feitos_antes.values())
        p.setdefault("t_primeiro", agora)
        p["t_ultimo"] = agora
        p["fase"] = f"Gerando (passo {p['passos']} de {job['total_passos']})"
    elif tipo == "execution_success":
        em_segundo_plano(concluir(job))
    elif tipo == "execution_error":
        marcar(job, "erro", erro_legivel(d.get("exception_type"), d.get("exception_message")))
        job["erro_tecnico"] = f"{d.get('exception_type')}: {d.get('exception_message')}"[:1500]
        job.pop("erro_vigia", None)
        salvar()
    elif tipo == "execution_interrupted":
        marcar(job, "cancelado", "Cancelado")
        job.pop("erro_vigia", None)
        salvar()


async def ouvir_comfy():
    while True:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.ws_connect(f"{COMFY.replace('http', 'ws', 1)}/ws?clientId={CLIENT_ID}", heartbeat=30) as ws:
                    COMFY_ESTADO.update(online=True, fora_desde=None)
                    em_segundo_plano(reconciliar())  # pode ter perdido eventos enquanto estava desconectado
                    async for m in ws:
                        if m.type == aiohttp.WSMsgType.TEXT:
                            try:
                                ao_evento(json.loads(m.data))
                            except Exception as exc:
                                print(f"[estúdio] evento da ComfyUI com problema: {exc}")
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        await asyncio.sleep(3)


async def comfy(metodo, caminho, timeout=60, **kw):
    if metodo == "POST" and caminho == "/prompt":
        # regra da placa: nenhum modelo de texto fica na placa quando um trabalho vai para a ComfyUI
        # (se um pedido de texto estiver usando a placa agora, espera ele terminar — ele descarrega no fim)
        await TEXTO.garantir_fora_da_placa()
    async with aiohttp.ClientSession() as s:
        async with s.request(metodo, COMFY + caminho, timeout=aiohttp.ClientTimeout(total=timeout), **kw) as r:
            txt = await r.text()
            if r.status >= 400:
                raise RecusaComfy(explicar_recusa(r.status, txt), tecnico=f"{r.status} {txt[:1500]}")
            return json.loads(txt) if txt else {}


async def cancelar_no_comfy(pid):
    """Tira da fila e interrompe (se estiver rodando). Nunca levanta erro."""
    try:
        await comfy("POST", "/queue", json={"delete": [pid]}, timeout=5)
        await comfy("POST", "/interrupt", json={"prompt_id": pid}, timeout=5)
        return True
    except Exception:
        return False


async def buscar_saidas(prompt_id, tentativas=8):
    """Arquivos gerados; a ComfyUI às vezes grava o histórico um instante depois do aviso de 'terminou'."""
    for _ in range(tentativas):
        hist = await comfy("GET", f"/history/{prompt_id}", timeout=15)
        saidas = []
        for no, out in hist.get(prompt_id, {}).get("outputs", {}).items():
            for lista in out.values():
                if isinstance(lista, list):
                    for it in lista:
                        if isinstance(it, dict) and it.get("filename"):
                            saidas.append({"no": no, "arquivo": it["filename"], "sub": it.get("subfolder", ""),
                                           "tipo": it.get("type", "output")})
        if saidas:
            return saidas
        await asyncio.sleep(1.5)
    return []


async def concluir(job):
    jid = job["id"]
    if jid in CONCLUINDO or job.get("estado") == "concluido":
        return
    CONCLUINDO.add(jid)
    try:
        saidas = await buscar_saidas(job["prompt_id"])
        if job.get("lixeira"):
            # o dono removeu (apagar do HD) antes de a ComfyUI terminar (o interrupt não para o SaveVideo):
            # registra o que ela gravou e apaga na hora, sem mostrar como concluído
            job["saidas"] = saidas
            job.pop("erro_vigia", None)
            apagar_trabalho(job)
            salvar()
            return
        if not saidas:
            marcar(job, "erro", "A geração terminou, mas o arquivo não apareceu na pasta de saída da ComfyUI.")
            salvar()
            return
        final = job.get("saida_final")
        saidas.sort(key=lambda s: 0 if s["no"] == final else 1)
        job["saidas"] = saidas
        job["estado"] = "concluido"
        for k in ("erro", "erro_tecnico", "erro_vigia", "aguardando"):
            job.pop(k, None)
        job["fim"] = time.time()
        p = job.get("prog", {})
        total = job["fim"] - job.get("inicio", job["criado"])
        carga = p.get("t_primeiro", job["fim"]) - job.get("inicio", job["criado"])
        feitos = p.get("passos", 0)
        por_passo = (p["t_ultimo"] - p["t_primeiro"]) / (feitos - 1) if feitos > 1 else None
        pos = job["fim"] - p.get("t_ultimo", job["fim"])
        STATS.setdefault(chave_tempo(job), []).append({"total": total, "carga": carga, "por_passo": por_passo,
                                                       "pos": pos})
        ULTIMO_PRESET["id"] = job["preset"]
        ATIVIDADE["ultima"] = time.time()
        ATIVIDADE["liberado"] = False
        job["ia"] = info_ia(job)
        salvar()
    except Exception as exc:  # a ComfyUI caiu logo depois de terminar: o vigia tenta de novo
        print(f"[estúdio] não consegui concluir {jid}: {exc}")
    finally:
        CONCLUINDO.discard(jid)


def resultado_do_historico(item):
    """(estado, mensagem, texto técnico) de um item do /history que não terminou com sucesso."""
    for m in (item.get("status") or {}).get("messages") or []:
        if isinstance(m, (list, tuple)) and len(m) == 2:
            tipo, d = m
            if tipo == "execution_interrupted":
                return "cancelado", "Cancelado", None
            if tipo == "execution_error" and isinstance(d, dict):
                return ("erro", erro_legivel(d.get("exception_type"), d.get("exception_message")),
                        f"{d.get('exception_type')}: {d.get('exception_message')}"[:1500])
    return "erro", "A ComfyUI terminou este trabalho com erro (sem detalhes).", None


def revisar_vigia():
    """Trabalhos que o vigia marcou como erro (ComfyUI muda por >60 s) e que ainda vale conferir: ela pode só ter
    travado (troca de memória no disco) e terminado depois, com o aviso do WebSocket perdido."""
    agora, lista, mudou = time.time(), [], False
    for j in JOBS:
        ev = j.get("erro_vigia")
        if not ev:
            continue
        if j.get("estado") != "erro" or not j.get("prompt_id") or agora - float(ev) > REVISAR_VIGIA_S:
            j.pop("erro_vigia", None)
            mudou = True
            continue
        lista.append(j)
    if mudou:
        salvar()
    return lista


async def conferir_vigia(lista, na_comfy):
    """Parte do reconciliar para os trabalhos de revisar_vigia(). Devolve True se mudou algo."""
    mudou = False
    for j in lista:
        pid = j["prompt_id"]
        if pid in na_comfy:  # ainda está na ComfyUI: não era erro
            if j.get("lixeira"):
                await cancelar_no_comfy(pid)
                j.pop("erro_vigia", None)
            else:
                j["estado"] = na_comfy[pid]
                for k in ("erro", "erro_vigia", "fim"):
                    j.pop(k, None)
                j.setdefault("inicio", time.time())
            mudou = True
            continue
        try:
            h = await comfy("GET", f"/history/{pid}", timeout=15)
        except Exception:
            continue
        item = h.get(pid)
        if item:
            st = item.get("status") or {}
            if st.get("status_str") == "success" or (st.get("completed") and st.get("status_str") != "error"):
                await concluir(j)  # na lixeira, concluir() só apaga o que ela gravou
            else:
                estado, msg, tec = resultado_do_historico(item)
                if not j.get("lixeira"):
                    marcar(j, estado, msg)
                    if tec:
                        j["erro_tecnico"] = tec
            j.pop("erro_vigia", None)
            mudou = True
        else:  # nem na fila nem no histórico: a ComfyUI reiniciou e o trabalho se perdeu mesmo
            j.pop("erro_vigia", None)
            mudou = True
    return mudou


async def reconciliar():
    """Confere na ComfyUI os trabalhos em fila/rodando (depois de reconectar, a cada 30 s e ao iniciar)."""
    if RECONC.locked():
        return
    async with RECONC:
        ativos = [j for j in trabalhos_ativos() if j["id"] not in TAREFAS_ATIVAS]
        vigiados = revisar_vigia()
        if not ativos and not vigiados:
            return
        try:
            q = await comfy("GET", "/queue", timeout=10)
        except Exception:
            return  # fora do ar: o vigia conta o tempo e marca erro depois de 60 s
        na_comfy = {row[1]: "fila" for row in q.get("queue_pending", [])}
        na_comfy.update({row[1]: "rodando" for row in q.get("queue_running", [])})
        mudou = await conferir_vigia(vigiados, na_comfy)
        for j in ativos:
            if j["id"] in TAREFAS_ATIVAS or j.get("estado") not in ("fila", "rodando"):
                continue
            pid = j.get("prompt_id")
            if not pid:
                marcar(j, "erro", "O estúdio foi reiniciado antes de mandar este trabalho para a ComfyUI. Gere de novo.")
                mudou = True
                continue
            if pid in na_comfy:
                SUMIDOS.pop(j["id"], None)
                if na_comfy[pid] == "rodando" and j["estado"] == "fila":
                    j["estado"] = "rodando"
                    j.setdefault("inicio", time.time())
                continue
            try:
                h = await comfy("GET", f"/history/{pid}", timeout=15)
            except Exception:
                continue
            item = h.get(pid)
            if item:
                SUMIDOS.pop(j["id"], None)
                st = item.get("status") or {}
                if st.get("status_str") == "success" or (st.get("completed") and st.get("status_str") != "error"):
                    await concluir(j)
                else:
                    estado, msg, tec = resultado_do_historico(item)
                    marcar(j, estado, msg)
                    if tec:
                        j["erro_tecnico"] = tec
                    mudou = True
                continue
            primeira = SUMIDOS.setdefault(j["id"], time.time())
            if time.time() - primeira >= 10:  # nem na fila nem no histórico em 2 conferências separadas: reiniciou
                SUMIDOS.pop(j["id"], None)
                marcar(j, "erro", "A ComfyUI caiu ou reiniciou no meio da geração (provável falta de memória). "
                                  "Tente com resolução ou duração menor.")
                mudou = True
        if mudou:
            salvar()


async def liberar_memoria():
    """POST /free na ComfyUI de vídeo, só se nada estiver rodando. Devolve (ok, motivo)."""
    if trabalhos_ativos() or TAREFAS_ATIVAS:
        return False, "Há trabalho do estúdio gerando ou na fila; a memória não foi liberada."
    try:
        q = await comfy("GET", "/queue", timeout=5)
    except Exception:
        # Motor DESLIGADO nao e defeito: nao ha modelo nenhum na placa. Antes a resposta era
        # "nao esta respondendo", e o dono leu como "o botao nao funcionou" (14/11/2026).
        try:
            desligado = not porta_aberta(servico_def("video")["porta_real"])
        except Exception:
            desligado = False
        if desligado:
            return True, ("O motor de imagem e vídeo está desligado, então a memória da placa já está livre. "
                          "Não havia nada para liberar.")
        return False, ("O motor de imagem e vídeo está ligado, mas não respondeu. "
                       "Use o botão Reparar, em Motores.")
    if q.get("queue_running") or q.get("queue_pending"):
        return False, "A ComfyUI de vídeo está gerando algo agora; a memória não foi liberada."
    try:
        await comfy("POST", "/free", json={"unload_models": True, "free_memory": True}, timeout=10)
    except Exception as exc:
        return False, f"A ComfyUI não aceitou o pedido: {msg_erro(exc)}"
    ULTIMO_PRESET["id"] = None  # a próxima geração carrega o modelo do HD de novo (a estimativa sabe disso)
    ATIVIDADE["liberado"] = True
    print("[estúdio] memória da ComfyUI de vídeo liberada (modelos descarregados).")
    return True, "Modelos descarregados da ComfyUI de vídeo. A próxima geração carrega o modelo do HD de novo."


async def vigia():
    """A cada 15 s: vê se a ComfyUI está viva, confere trabalhos e libera a memória depois de um tempo parado."""
    volta = 0
    while True:
        try:
            await asyncio.sleep(15)
            volta += 1
            q = None
            try:
                q = await comfy("GET", "/queue", timeout=5)
                COMFY_ESTADO.update(online=True, fora_desde=None)
            except Exception:
                COMFY_ESTADO["online"] = False
                COMFY_ESTADO["fora_desde"] = COMFY_ESTADO["fora_desde"] or time.time()
            if TEM_MUSICA and volta % 4 == 0:  # 1 vez por minuto: a ComfyUI ligada carregou o nó da música?
                await conferir_no_carregado()
            ativos = trabalhos_ativos()
            if ativos or TAREFAS_ATIVAS or (q and (q.get("queue_running") or q.get("queue_pending"))):
                ATIVIDADE["ultima"] = time.time()
                ATIVIDADE["liberado"] = False
            if COMFY_ESTADO["online"] is False:
                if time.time() - COMFY_ESTADO["fora_desde"] > COMFY_FORA_S:
                    mudou = False
                    for j in ativos:
                        if j.get("prompt_id") and j["id"] not in TAREFAS_ATIVAS:
                            marcar(j, "erro", "A ComfyUI de vídeo parou de responder por mais de 1 minuto no meio da "
                                              "geração (fechou ou travou, provável falta de memória). Abra o estúdio "
                                              "de novo e tente com resolução ou duração menor.")
                            j["erro_vigia"] = time.time()  # se ela só travou e terminar depois, o reconciliar conserta
                            mudou = True
                    if mudou:
                        salvar()
            elif (ativos or any(j.get("erro_vigia") for j in JOBS)) and volta % 2 == 0:
                await reconciliar()
            if (LIBERAR_MIN > 0 and not ATIVIDADE["liberado"] and q is not None
                    and time.time() - ATIVIDADE["ultima"] > LIBERAR_MIN * 60):
                ok, motivo = await liberar_memoria()
                if not ok:
                    ATIVIDADE["ultima"] = time.time() - LIBERAR_MIN * 60 + 60  # tenta de novo daqui a 1 min
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[estúdio] vigia: {exc}")


# ---------------------------------------------------------------- [C] exclusão mútua da placa de vídeo
class Cancelado(Exception):
    pass


def verificar_cancelado(job):
    if job["id"] in CANCELAR or job.get("estado") == "cancelado":
        raise Cancelado()


async def musica_ocupada():
    """Pergunta ao painel de música se ele está usando a placa. Sem resposta em 2 s = livre.
    Guarda em PAINEL_INFO desde quando a música mais antiga dele espera a placa (campo opcional 'esperando_desde'),
    o 'tipo' do uso ("musica" | "treino" | None) e 'termina_em' (epoch s estimado, quando é treino)."""
    PAINEL_INFO["esperando_desde"] = None
    PAINEL_INFO["tipo"] = None
    PAINEL_INFO["termina_em"] = None
    PAINEL_INFO["na_fila"] = 0
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(MUSICA + "/api/ocupado", timeout=aiohttp.ClientTimeout(total=2)) as r:
                if r.status != 200:
                    return False, None
                d = await r.json(content_type=None)
                # quantas músicas o painel tem gerando OU esperando a vez. "ocupado" é só a que usa a placa
                # agora; uma música parada na fila não segura a placa, mas segura o "Desligar" da ComfyUI.
                nf = d.get("na_fila")
                if isinstance(nf, int) and not isinstance(nf, bool) and nf > 0:
                    PAINEL_INFO["na_fila"] = nf
                ed = d.get("esperando_desde")
                if isinstance(ed, (int, float)) and not isinstance(ed, bool) and ed > 0:
                    PAINEL_INFO["esperando_desde"] = float(ed)
                ocupado = bool(d.get("ocupado"))
                if ocupado and d.get("tipo") in ("musica", "treino"):
                    PAINEL_INFO["tipo"] = d["tipo"]
                te = d.get("termina_em")
                if isinstance(te, (int, float)) and not isinstance(te, bool) and te > 0:
                    PAINEL_INFO["termina_em"] = float(te)
                motivo = d.get("motivo")
                if ocupado and PAINEL_INFO["tipo"] == "treino":
                    motivo = texto_treino()
                return ocupado, motivo
    except Exception:
        return False, None


def texto_treino():
    """'Treino de estilo em andamento — termina por volta de HH:MM' (contrato do treino com o painel)."""
    te = PAINEL_INFO.get("termina_em")
    if te:
        return f"Treino de estilo em andamento — termina por volta de {datetime.fromtimestamp(te).strftime('%H:%M')}"
    return "Treino de estilo em andamento"


def estudio_na_placa():
    """Algum trabalho do estúdio já está na ComfyUI (gerando ou na fila dela)?"""
    return any(j.get("estado") == "rodando" or (j.get("estado") == "fila" and j.get("prompt_id"))
               for j in trabalhos_ativos())


def _avisar(sinal):
    if sinal is not None and not sinal.is_set():
        sinal.set()


ESPERA_MUSICA_MAX_S = int(os.environ.get("ESTUDIO_ESPERA_MUSICA_MAX_MIN", 90)) * 60


async def esperar_gpu(job, sinal=None):
    """Antes de mandar para a placa: espera a música terminar (uma geração por vez) e cede a vez para a música
    que foi pedida ANTES deste trabalho (ordem dos pedidos). Volta com a RESERVA ligada (o chamador desliga
    depois de mandar o prompt). `sinal` avisa o /api/gerar que o trabalho entrou em espera."""
    avisou = False
    cedendo_desde = None
    inicio_espera = time.time()
    while True:
        verificar_cancelado(job)
        RESERVA["ate"] = time.time() + 600
        ocupada, motivo = await musica_ocupada()
        treino = ocupada and PAINEL_INFO.get("tipo") == "treino"
        if ocupada and not treino and time.time() - inicio_espera > ESPERA_MUSICA_MAX_S:
            # proteção: se o painel ficar preso em "ocupado" (defeito), o estúdio não espera para sempre
            # (treino de estilo não tem esse limite: ele segura a placa até acabar, pelo contrato com o painel)
            print(f"[esperar_gpu] {job['id']}: música 'ocupada' há mais de {ESPERA_MUSICA_MAX_S // 60} min; seguindo.")
            job["aviso"] = "A música ficou ocupada tempo demais; o estúdio seguiu mesmo assim."
            ocupada = False
        ceder = False
        ed = PAINEL_INFO.get("esperando_desde")
        if not ocupada and ed and ed < job.get("criado", time.time()):
            if estudio_na_placa():  # a música (pedida antes) espera o estúdio terminar: este não passa na frente
                cedendo_desde, ceder = None, True
            else:  # o painel deve começar a música; se não começar em 60 s, segue (sem impasse)
                cedendo_desde = cedendo_desde or time.time()
                ceder = time.time() - cedendo_desde < CEDER_MAX_S
        if not ocupada and not ceder:
            if avisou:
                job.pop("aguardando", None)
                job.get("prog", {}).pop("fase", None)
                salvar()
            return
        RESERVA["ate"] = 0.0  # enquanto espera, não segura a placa (senão o painel também esperaria: impasse)
        job["aguardando"] = (motivo if ocupada and motivo else
                             "O painel de música está usando a placa de vídeo." if ocupada else
                             "Uma música pedida antes deste trabalho vai usar a placa primeiro.")
        job.setdefault("prog", {})["fase"] = (texto_treino() if treino else
                                              "Aguardando a música terminar" if ocupada else
                                              "Aguardando a música pedida antes")
        _avisar(sinal)
        if not avisou:
            salvar()
            avisou = True
        await asyncio.sleep(4 + random.random() * 3)


async def pegar_vez(job, sinal=None):
    """Espera a vez de mandar para a placa (ENVIO, na ordem dos pedidos) conferindo o cancelamento a cada 1 s:
    um trabalho cancelado enquanto espera sai da fila na hora (e pode ser removido), sem esperar o da frente."""
    verificar_cancelado(job)
    if ENVIO.locked():
        _avisar(sinal)
    t = asyncio.ensure_future(ENVIO.acquire())
    try:
        while not t.done():
            await asyncio.wait({t}, timeout=1)
            if not t.done():
                verificar_cancelado(job)
        t.result()
    except BaseException:
        if t.done() and not t.cancelled() and t.exception() is None:
            ENVIO.release()  # chegou a pegar a vez: devolve
        else:
            t.cancel()
        raise


def limpar_se_removido(job):
    """Trabalho removido (lixeira) enquanto a tarefa dele ainda terminava: apaga o que ela ainda gravou."""
    if job.get("lixeira"):
        try:
            apagar_trabalho(job)
        except Exception as exc:
            print(f"[estúdio] não consegui apagar os arquivos do trabalho removido {job.get('id')}: {exc}")


async def despachar(job, api, antes=None, sinal=None):
    """Manda o trabalho para a ComfyUI na vez dele. Devolve None (deu certo/cancelado) ou a exceção do erro."""
    jid = job["id"]
    try:
        await pegar_vez(job, sinal)
        try:
            await esperar_gpu(job, sinal)
            verificar_cancelado(job)
            if antes:
                _avisar(sinal)  # o enquadramento (DWPose) pode levar minutos: o /api/gerar responde já
                job.setdefault("prog", {})["fase"] = "Enquadrando o personagem"
                await antes()
                verificar_cancelado(job)
            job.get("prog", {}).pop("fase", None)
            r = await comfy("POST", "/prompt", json={"prompt": api, "client_id": CLIENT_ID,
                                                     "extra_data": extra_data(job)})
            registrar_prompt(job, r["prompt_id"])
            if jid in CANCELAR:  # cancelaram enquanto o pedido estava indo
                await cancelar_no_comfy(r["prompt_id"])
                marcar(job, "cancelado", "Cancelado")
        finally:
            RESERVA["ate"] = 0.0
            ENVIO.release()
        return None
    except Cancelado:
        marcar(job, "cancelado", "Cancelado")
        return None
    except Exception as exc:
        marcar(job, "erro", msg_erro(exc))
        guardar_tecnico(job, exc)
        return exc
    finally:
        TAREFAS_ATIVAS.discard(jid)
        CANCELAR.discard(jid)
        limpar_se_removido(job)
        salvar()


# ---------------------------------------------------------------- progresso
def calcular_esperas():
    """{id: (quantos na frente, segundos de espera)} dos trabalhos na fila, numa passada só (custo linear):
    primeiro os que estão gerando, depois a fila pela hora do pedido; a espera de cada um é a soma do que falta
    dos que estão na frente. Calculado UMA vez por requisição e passado a progresso()."""
    ativos = trabalhos_ativos()
    rodando = sorted((j for j in ativos if j.get("estado") == "rodando"), key=lambda j: j.get("criado", 0))
    fila = sorted((j for j in ativos if j.get("estado") == "fila"), key=lambda j: j.get("criado", 0))
    res, acum, n = {}, 0.0, 0
    for j in rodando:
        try:
            r = progresso(j, {}).get("restante")
        except Exception:
            r = None
        acum += r if r is not None else (estimativa_segura(j) or 0)
        n += 1
    for j in fila:
        res[j["id"]] = (n, acum)
        acum += estimativa_segura(j) or 120
        n += 1
    return res


def progresso(job, esperas=None):
    agora = time.time()
    est = job.get("estado")
    p = job.get("prog", {})
    if est == "concluido":
        return {"pct": 100, "fase": "Concluído",
                "decorrido": (job.get("fim") or agora) - job.get("inicio", job.get("criado", agora))}
    if est in ("erro", "cancelado"):
        return {"pct": 0, "fase": job.get("erro") or ("Cancelado" if est == "cancelado" else "Erro")}
    total_est = estimativa_segura(job) or 120
    if est == "fila":  # a ComfyUI gera um por vez: soma o que falta dos que estão na frente
        if esperas is None:
            esperas = calcular_esperas()
        n_frente, espera = esperas.get(job.get("id"), (0, 0.0))
        if job.get("aguardando"):
            fase = p.get("fase") if str(p.get("fase") or "").startswith(("Aguardando a música", "Treino de estilo")) \
                else "Aguardando a música terminar"
        elif job["id"] in TAREFAS_ATIVAS and p.get("fase"):
            fase = p["fase"]
        else:
            fase = (f"Na fila ({n_frente} na frente)" if n_frente > 1 else
                    "Na fila (espera o anterior terminar)" if n_frente else "Na fila")
        return {"pct": 0, "fase": fase, "restante": total_est + espera, "espera": espera, "na_frente": n_frente,
                "base": "inclui a espera", "aguardando": job.get("aguardando")}
    dec = agora - job.get("inicio", agora)
    tp, feitos = job.get("total_passos", 1) or 1, p.get("passos", 0)
    if not feitos:  # carregando: a ComfyUI não informa % da carga; usa o histórico
        carga_est = max(10.0, total_est * 0.3)
        pct = min(4.9, 5 * dec / carga_est)
        rest = total_est - dec
        if rest < 5:  # passou do histórico: não inventa número
            return {"pct": pct, "fase": p.get("fase") or "Carregando modelo do HD (1ª vez demora mais)",
                    "decorrido": dec, "restante": None, "base": "calculando"}
        return {"pct": pct, "fase": p.get("fase", "Carregando"), "decorrido": dec, "restante": rest,
                "base": "pelo histórico"}
    if feitos > 1:  # velocidade real entre passos (sem o tempo de carga)
        por_passo = (p["t_ultimo"] - p["t_primeiro"]) / (feitos - 1)
    else:  # só 1 passo: usa a velocidade registrada no histórico, se houver
        reg = [r["por_passo"] for r in STATS.get(chave_tempo(job), []) if r.get("por_passo")]
        if not reg:
            return {"pct": 5 + 88 * feitos / tp, "fase": p.get("fase"), "decorrido": dec, "restante": None,
                    "base": "calculando"}
        por_passo = sum(reg[-5:]) / len(reg[-5:])
    posr = [r["pos"] for r in STATS.get(chave_tempo(job), []) if r.get("pos") is not None]
    pos = sum(posr[-5:]) / len(posr[-5:]) if posr else max(5.0, total_est * 0.06)
    restante = (tp - feitos) * por_passo + (pos if feitos < tp else max(0, pos - (agora - p["t_ultimo"])))
    pct = 5 + 88 * feitos / tp if feitos < tp else min(99, 93 + 6 * (agora - p["t_ultimo"]) / max(pos, 1))
    return {"pct": pct, "fase": p.get("fase"), "decorrido": dec, "restante": max(0, restante),
            "por_passo": por_passo, "base": "velocidade real"}


def caminho_saida(s):
    return COMFY_DIR / ("output" if s.get("tipo", "output") == "output" else s["tipo"]) / s.get("sub", "") / s["arquivo"]


def publico(j, esperas=None):
    """Trabalho como vai para a tela (sem os campos internos), com 'ia', progresso e se o preset ainda existe.
    `esperas` = calcular_esperas() feito uma vez pela requisição (evita refazer a conta da fila a cada trabalho)."""
    j["ia"] = info_ia(j)
    _, p = preset_ou_none(j.get("preset"))
    d = {k: v for k, v in j.items() if k not in ("amostradores", "prog", "erro_vigia")}
    d["preset_existe"] = p is not None
    try:
        d["progresso"] = progresso(j, esperas)
    except Exception:
        d["progresso"] = {"pct": 0, "fase": j.get("estado")}
    d["estimativa_total"] = estimativa_segura(j)
    if j.get("estado") == "concluido" and j.get("saidas"):
        d["midia"] = f"/api/midia/{j['id']}/0"
        try:
            d["arquivo_existe"] = caminho_saida(j["saidas"][0]).exists()
        except Exception:
            d["arquivo_existe"] = False
    return d


# ---------------------------------------------------------------- rotas
async def api_presets(req):
    dados = copy.deepcopy(PRESETS)
    # IAs com "desligado": true nao aparecem no painel. Para reativar uma basta tirar essa
    # chave em presets.json: o modelo continua no disco.
    # 02/11/2026 isto escondeu 7 IAs pouco usadas, para o painel parecer plataforma.
    # 07/11/2026 o dono desfez: "Imagem e Video tem que ter no painel mesmo que demore".
    # DEMORA NAO E MOTIVO PARA ESCONDER - cada cartao ja mostra a estimativa (o HunyuanVideo
    # diz ~15 min), entao quem escolhe o tempo e a pessoa, nao nos. Hoje nenhuma esta
    # desligada; antes de desligar alguma de novo, pergunte a ele.
    for aba in ("imagem", "video"):
        dados[aba] = [p for p in dados.get(aba, []) if not p.get("desligado")]
    ativos = [p for aba in ("imagem", "video") for p in dados.get(aba, [])]
    for p in ativos:
        f = ficha(p["id"])
        p["ficha"] = f
        p["categoria"] = (f or {}).get("categoria")
    nomes = [sem_acento(p["nome"]) for p in ativos]
    ag = dados.get("aguardando_teste") or {}
    for aba, lista in list(ag.items()):  # o que já foi liberado não aparece de novo "em cinza"
        ag[aba] = [n for n in lista if not any(x.startswith(sem_acento(n)) or sem_acento(n).startswith(x)
                                               for x in nomes)]
    dados["aguardando_teste"] = ag
    dados["musica_fichas"] = [f for k, f in (fichas().get("ias") or {}).items() if eh_musica_do_pacote(k, f)]
    return web.json_response(dados)


def eh_musica_do_pacote(fid, f):
    """Esta ficha e de uma IA de musica que o pacote TRAZ?

    A fichas.json veio do estudio de origem com 8 fichas de musica (ACE-Step, ACE XL, MiniMax,
    Treblo, separador...). O pacote so leva duas: as do ias.MUSICA_IAS, as mesmas que o painel
    de musica mostra (PAINEL_MOTORES). As outras nao podem aparecer no catalogo do Inicio nem
    nas dicas: anunciariam uma IA que nao da para instalar aqui.
    """
    return (f or {}).get("aba") == "musica" and fid in ias.MUSICA_IAS


def ids_ativos():
    """ids das IAs de imagem/video que o painel mostra (as sem "desligado": true)."""
    vivos = set()
    for aba in ("imagem", "video"):
        for p in PRESETS.get(aba, []) or []:
            if not p.get("desligado") and p.get("id"):
                vivos.add(p["id"])
    return vivos


def novidades():
    """As notícias da página inicial (estudio/novidades.json).

    Arquivo à parte de propósito: dá para publicar uma notícia sem mexer em código nenhum,
    e, quando o servidor de contas entrar no ar, basta esta função passar a ler de lá.
    Sem o arquivo, a tela simplesmente não mostra o bloco — não dá erro.
    """
    caminho = DADOS / "novidades.json"
    try:
        d = json.loads(caminho.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except Exception as exc:
        print(f"[estúdio] novidades.json: {exc!r}", flush=True)
        return []
    lista = d.get("novidades") if isinstance(d, dict) else d
    if not isinstance(lista, list):
        return []
    return [n for n in lista if isinstance(n, dict) and n.get("titulo")]


async def api_novidades(req):
    return web.json_response(novidades())


async def api_fichas(req):
    """So as fichas das IAs que existem neste painel.

    Filtra pelo que ESTA no presets.json, nao pelo que foi marcado como desligado: no pacote
    do GitHub as IAs cortadas nem aparecem no presets.json, e as fichas delas ficavam orfas --
    o catalogo do Inicio e as dicas chegaram a anunciar um FLUX.2 que nao viaja (02/11/2026).
    As fichas de musica nao tem preset: passam as das IAs de musica que o pacote traz
    (eh_musica_do_pacote); as dos motores que nao vem (ACE-Step, MiniMax, Treblo...) ficam fora.
    """
    dados = copy.deepcopy(fichas())
    vivos = ids_ativos()
    todas = dados.get("ias")
    if isinstance(todas, dict):
        dados["ias"] = {k: v for k, v in todas.items()
                        if ((v or {}).get("aba") != "musica" or eh_musica_do_pacote(k, v))
                        and (not vivos or (v or {}).get("aba") not in ("imagem", "video") or k in vivos)}
    return web.json_response(dados)


async def duracao_audio(caminho):
    try:
        proc = await asyncio.create_subprocess_exec("ffprobe", "-v", "error", "-show_entries", "format=duration",
                                                    "-of", "csv=p=0", str(caminho), stdout=asyncio.subprocess.PIPE)
        out, _ = await proc.communicate()
        return round(float(out.decode().strip()), 2)
    except (ValueError, OSError):
        return None


def vozes_lista():
    if not VOZES_JSON.exists():
        return []
    try:
        return json.loads(VOZES_JSON.read_text(encoding="utf-8"))
    except ValueError:
        return []


def vozes_gravar(lista):
    VOZES_JSON.write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")


def voz_em_input(v):
    """Garante que o áudio da voz salva esteja na pasta input da ComfyUI (o Chatterbox lê de lá) e devolve o nome."""
    guardado = VOZES_DIR / v["arquivo"]
    destino = COMFY_DIR / "input" / v["arquivo"]
    if not destino.exists():
        if not guardado.exists():
            raise web.HTTPBadRequest(text=f"O áudio da voz '{v.get('nome')}' sumiu da biblioteca. Salve a voz de novo.")
        shutil.copy(guardado, destino)
    return v["arquivo"]


async def api_vozes(req):
    return web.json_response(vozes_lista())


async def api_vozes11(req):
    """Vozes do ElevenLabs (nuvem, paga) + quanto sobra de crédito. Lista vazia = sem chave configurada."""
    vs = await asyncio.to_thread(elevenlabs.vozes, req.query.get("atualizar") == "1")
    cred = await asyncio.to_thread(elevenlabs.creditos) if vs else None
    return web.json_response({"vozes": vs, "creditos": ({"usados": cred[0], "limite": cred[1]} if cred else None)})


async def api_chave_nuvem(req):
    """A chave do ElevenLabs de QUEM USA o estudio - nunca a nossa.

    O pacote do GitHub nao leva chave nenhuma: a pasta API fica de fora. Quem quiser usar
    voz na nuvem poe a propria chave aqui, e ela vai para um arquivo texto na maquina dele,
    dentro da pasta API, que ja esta no .gitignore.

    O GET NUNCA devolve a chave, so se existe uma. Nao ha motivo para o navegador ler de
    volta um segredo que ele mesmo mandou - devolver so aumenta a chance de ele vazar num
    log, num print de tela ou no historico de uma aba aberta.
    """
    if req.method == "GET":
        return web.json_response({"tem": elevenlabs.tem_chave(),
                                  "arquivo": str(elevenlabs.CHAVE_ARQ)})
    b = await req.json()
    chave = (b.get("chave") or "").strip()
    arq = elevenlabs.CHAVE_ARQ
    if not chave:                      # mandar vazio = remover
        try:
            arq.unlink()
        except FileNotFoundError:
            pass
        elevenlabs.esquecer()
        return web.json_response({"ok": True, "tem": False,
                                  "mensagem": "Chave removida. A narração continua "
                                              "funcionando com a voz local."})
    if len(chave) > 300 or any(c.isspace() for c in chave):
        raise web.HTTPBadRequest(text="Isso não parece uma chave. Cole só a chave, "
                                      "sem espaços nem quebra de linha.")
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(chave + "\n", encoding="utf-8")
    elevenlabs.esquecer()
    vs = await asyncio.to_thread(elevenlabs.vozes, True)
    if not vs:
        return web.json_response({"ok": False, "tem": True,
                                  "mensagem": "Guardei a chave, mas o ElevenLabs não "
                                              "respondeu com nenhuma voz. Confira se ela "
                                              "está certa e se a conta tem saldo."})
    return web.json_response({"ok": True, "tem": True, "vozes": len(vs),
                              "mensagem": f"Pronto: {len(vs)} vozes da sua conta apareceram "
                                          f"na lista, com o símbolo de nuvem."})


# ---------------------------------------------------------------- as chaves de API, numa tela só
# 11/11/2026: antes cada chave morava num canto. A do ElevenLabs ficava escondida dentro da
# aba Narração, e o token do Hugging Face só existia como arquivo - quem instalasse o pacote
# não tinha como saber que ele existia, nem onde criar um. Agora os dois ficam no mesmo
# lugar, com o endereço de onde se cria cada um.
#
# A REGRA DAS DUAS: o GET diz SE existe uma chave, NUNCA qual é. Devolver um segredo que o
# próprio navegador mandou não serve para nada e só aumenta a chance de ele vazar num log,
# num print de tela ou no histórico de uma aba aberta.
CHAVES_DE_API = {
    "elevenlabs": {
        "nome": "ElevenLabs",
        "para_que": "vozes na nuvem, na aba Narração. Sem ela, a narração continua "
                    "funcionando com as vozes locais, de graça.",
        "onde_criar": "https://elevenlabs.io/app/settings/api-keys",
        "paga": True,
    },
    "huggingface": {
        "nome": "Hugging Face",
        "para_que": "baixar o LTX 2.5. Dos 19 repositórios de modelos, 18 abrem sem nada; "
                    "só o Lightricks/LTX-2.5 pede conta e aceitar a licença.",
        "onde_criar": "https://huggingface.co/settings/tokens",
        "antes": [
            ("Crie uma conta (é de graça)", "https://huggingface.co/join"),
            ("Aceite a licença nesta página", "https://huggingface.co/Lightricks/LTX-2.5"),
            ("Crie um token de LEITURA e cole aqui", "https://huggingface.co/settings/tokens"),
        ],
        "paga": False,
    },
}


def _estado_das_chaves():
    fora = []
    for cid, info in CHAVES_DE_API.items():
        tem = elevenlabs.tem_chave() if cid == "elevenlabs" else ias.tem_token()
        arq = elevenlabs.CHAVE_ARQ if cid == "elevenlabs" else ias.TOKEN_ARQ
        fora.append(dict(info, id=cid, tem=bool(tem), arquivo=str(arq)))
    return fora


async def api_chaves(req):
    """Lista o estado das chaves (GET) ou guarda uma (POST {id, valor})."""
    if req.method == "GET":
        return web.json_response({"chaves": _estado_das_chaves()})
    b = await req.json()
    cid = (b.get("id") or "").strip()
    if cid not in CHAVES_DE_API:
        raise web.HTTPBadRequest(text="Não conheço esta chave.")
    valor = (b.get("valor") or "").strip()
    if cid == "huggingface":
        ok, recado = await asyncio.to_thread(ias.guardar_token, valor)
        if not ok:
            raise web.HTTPBadRequest(text=recado)
        return web.json_response({"ok": True, "tem": ias.tem_token(), "mensagem": recado})
    # ElevenLabs: reaproveita o caminho que já existia, para não haver dois jeitos de
    # guardar a mesma chave e um deles ficar para trás.
    arq = elevenlabs.CHAVE_ARQ
    if not valor:
        try:
            arq.unlink()
        except FileNotFoundError:
            pass
        elevenlabs.esquecer()
        return web.json_response({"ok": True, "tem": False,
                                  "mensagem": "Chave removida. A narração continua "
                                              "funcionando com a voz local."})
    if len(valor) > 300 or any(c.isspace() for c in valor):
        raise web.HTTPBadRequest(text="Isso não parece uma chave. Cole só a chave, "
                                      "sem espaços nem quebra de linha.")
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(valor + "\n", encoding="utf-8")
    elevenlabs.esquecer()
    vs = await asyncio.to_thread(elevenlabs.vozes, True)
    if not vs:
        return web.json_response({"ok": False, "tem": True,
                                  "mensagem": "Guardei a chave, mas o ElevenLabs não "
                                              "respondeu com nenhuma voz. Confira se ela "
                                              "está certa e se a conta tem saldo."})
    return web.json_response({"ok": True, "tem": True,
                              "mensagem": "Pronto: %d vozes da sua conta apareceram na "
                                          "lista, com o símbolo de nuvem." % len(vs)})


async def api_voz_salvar(req):
    b = await req.json()
    nome = (b.get("nome") or "").strip()
    arq = Path(b.get("arquivo") or "").name
    if not nome:
        raise web.HTTPBadRequest(text="Dê um nome para a voz.")
    origem = COMFY_DIR / "input" / arq
    if not arq or not origem.exists():
        raise web.HTTPBadRequest(text="Envie o áudio da voz primeiro.")
    VOZES_DIR.mkdir(exist_ok=True)
    vid = uuid.uuid4().hex[:8]
    guardado = f"voz_{vid}{origem.suffix}"
    shutil.copy(origem, VOZES_DIR / guardado)
    shutil.copy(origem, COMFY_DIR / "input" / guardado)
    lista = vozes_lista()
    lista.append({"id": vid, "nome": nome, "arquivo": guardado,
                  "segundos": await duracao_audio(COMFY_DIR / "input" / guardado), "criada": time.time()})
    vozes_gravar(lista)
    return web.json_response({"ok": True, "vozes": lista})


async def api_voz_remover(req):
    vid = req.match_info["id"]
    lista = vozes_lista()
    for v in lista:
        if v["id"] == vid:
            (VOZES_DIR / v["arquivo"]).unlink(missing_ok=True)
            # a cópia em ComfyUI\input também sai (só fica se um trabalho que ainda vai gerar estiver usando)
            if not any(j.get("voz") == v["arquivo"] for j in trabalhos_ativos()):
                try:
                    (COMFY_DIR / "input" / v["arquivo"]).unlink(missing_ok=True)
                except OSError as exc:
                    print(f"[estúdio] não consegui apagar a cópia da voz: {exc}")
            break
    lista = [v for v in lista if v["id"] != vid]
    vozes_gravar(lista)
    return web.json_response({"ok": True, "vozes": lista})


def tocar(arq):
    """Atualiza a data do arquivo: marca que ele acabou de ser enviado de novo (ver reenviado_depois)."""
    try:
        os.utime(arq, None)
    except OSError:
        pass


async def converter(args, saida):
    """Roda o ffmpeg gravando num arquivo temporário e só troca pelo nome final se deu certo
    (um arquivo pela metade nunca fica com o nome final, que é reaproveitado por outros envios)."""
    tmp = saida.with_name(f"estudio_tmp_{uuid.uuid4().hex}{saida.suffix}")
    try:
        proc = await asyncio.create_subprocess_exec("ffmpeg", "-v", "error", "-y", *args, str(tmp))
        await proc.wait()
        if proc.returncode != 0 or not tmp.is_file() or tmp.stat().st_size == 0:
            return False
        os.replace(tmp, saida)
        return True
    finally:
        tmp.unlink(missing_ok=True)


async def api_upload(req):
    """Guarda o arquivo em ComfyUI\\input com o nome tirado do CONTEÚDO (estudio_<sha1 10>): o mesmo arquivo enviado
    de novo reaproveita o que já está no HD, sem cópia repetida. Áudio e vídeo ficam só na versão convertida
    (o original de ~35 MB não é mais guardado ao lado)."""
    reader = await req.multipart()
    campo = await reader.next()
    if campo is None:
        raise web.HTTPBadRequest(text="Nenhum arquivo foi enviado.")
    tipo = req.query.get("tipo", "imagem")
    ext = Path(campo.filename or "arquivo").suffix.lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,8}", ext):
        ext = {"imagem": ".png", "audio": ".wav"}.get(tipo, ".mp4")
    inp = COMFY_DIR / "input"
    tmp = inp / f"estudio_tmp_{uuid.uuid4().hex}{ext}"  # não segue o padrão estudio_<hex>: nunca é confundido
    h = hashlib.sha1()
    try:
        with tmp.open("wb") as f:
            while chunk := await campo.read_chunk():
                f.write(chunk)
                h.update(chunk)
        if tmp.stat().st_size == 0:
            raise web.HTTPBadRequest(text="O arquivo enviado está vazio.")
        base = f"estudio_{h.hexdigest()[:10]}"
        if tipo == "audio":  # voz para clonar ou áudio pronto: fica só o WAV convertido
            conv = inp / f"{base}_voz.wav"
            if conv.is_file():
                tocar(conv)
            elif not await converter(["-i", str(tmp), "-vn", "-ar", "44100"], conv):
                raise web.HTTPBadRequest(text="Não consegui ler esse áudio (ffmpeg).")
            return web.json_response({"nome": conv.name, "url": f"/api/entrada/{conv.name}",
                                      "segundos": await duracao_audio(conv)})
        if tipo == "video":  # Wan Animate trabalha a 16 fps: fica só o vídeo convertido
            conv = inp / f"{base}_16fps.mp4"
            if conv.is_file():
                tocar(conv)
            elif not await converter(["-i", str(tmp), "-vf", "fps=16", "-an", "-c:v", "libx264", "-crf", "16",
                                      "-pix_fmt", "yuv420p"], conv):
                raise web.HTTPBadRequest(text="Não consegui converter o vídeo (ffmpeg).")
            return web.json_response({"nome": conv.name, "url": f"/api/entrada/{conv.name}",
                                      **await info_video(conv.name)})
        destino = inp / f"{base}{ext}"
        if destino.is_file():
            tocar(destino)
        else:
            os.replace(tmp, destino)
        return web.json_response({"nome": destino.name, "url": f"/api/entrada/{destino.name}"})
    except FileNotFoundError:
        raise web.HTTPBadRequest(text="O ffmpeg não foi encontrado neste computador.")
    finally:
        tmp.unlink(missing_ok=True)


async def info_video(nome):
    """Largura, altura, quadros e segundos (a 16 fps) de um vídeo em ComfyUI\\input (guardado em cache:
    o upload não muda, e a estimativa pergunta isso a cada poucos segundos)."""
    arq = COMFY_DIR / "input" / Path(nome).name
    try:
        st = arq.stat()
    except OSError:
        raise web.HTTPBadRequest(text=f"Vídeo não encontrado: {nome}")
    chave = (arq.name, st.st_size, st.st_mtime)
    if chave in _CACHE_VIDEO:
        return dict(_CACHE_VIDEO[chave])
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
            "-show_entries", "stream=width,height,nb_read_packets", "-of", "json", str(arq),
            stdout=asyncio.subprocess.PIPE)
        out, _ = await proc.communicate()
    except FileNotFoundError:
        raise web.HTTPBadRequest(text="O ffprobe não foi encontrado neste computador.")
    s = (json.loads(out or b"{}").get("streams") or [{}])[0]
    quadros = int(s.get("nb_read_packets") or 0)
    res = {"largura": s.get("width"), "altura": s.get("height"), "quadros": quadros,
           "segundos": round(quadros / FPS_ANIMATE, 2)}
    if quadros and s.get("width"):
        if len(_CACHE_VIDEO) > 200:
            _CACHE_VIDEO.clear()
        _CACHE_VIDEO[chave] = res
    return dict(res)


def dims_auto(area, largura, altura):
    """Mesma proporção do vídeo com ~area pixels, múltiplos de 16."""
    ar = largura / altura
    w = max(256, round(math.sqrt(area * ar) / 16) * 16)
    h = max(256, round(math.sqrt(area / ar) / 16) * 16)
    return w, h


def plano_trechos(quadros):
    """Comprimento de cada trecho do Wan Animate para cobrir `quadros` (cada extensão soma len-5)."""
    q4 = lambda n: max(21, math.ceil((n - 1) / 4) * 4 + 1)  # noqa: E731  4k+1
    if quadros <= SEG_ANIMATE:
        return [q4(quadros)]
    trechos, feito = [SEG_ANIMATE], SEG_ANIMATE
    while quadros - feito > SEG_ANIMATE - 5:
        trechos.append(SEG_ANIMATE)
        feito += SEG_ANIMATE - 5
    trechos.append(q4(quadros - feito + 5))
    return trechos


def montar_trechos(api, trechos, quadros):
    """Parte do workflow de 2 trechos (232 + 242) e encadeia quantos trechos forem precisos."""
    api["232:62"]["inputs"]["length"] = trechos[0]
    api["242:90"]["inputs"]["length"] = trechos[1]
    api["242:90"]["inputs"]["height"] = ["160", 0]  # template original fixava 480
    modelo = {k: v for k, v in api.items() if k.startswith("242:")}
    ant = "242"
    for i, comp in enumerate(trechos[2:], start=3):
        novo = f"s{i}"
        for k, v in modelo.items():
            n = copy.deepcopy(v)
            for ent, val in n["inputs"].items():
                if isinstance(val, list) and isinstance(val[0], str) and val[0].startswith("242:"):
                    n["inputs"][ent] = [novo + val[0][3:], val[1]]
            api[novo + k[3:]] = n
        api[f"{novo}:90"]["inputs"].update(length=comp, video_frame_offset=[f"{ant}:90", 5],
                                           continue_motion=[f"{ant}:86", 0])
        api[f"{novo}:86"]["inputs"]["image1"] = [f"{ant}:86", 0]
        ant = novo
    # corta o excesso do último trecho (comprimento 4k+1) para bater com o vídeo
    api["900"] = {"class_type": "ImageFromBatch",
                  "inputs": {"image": [f"{ant}:86", 0], "batch_index": 0, "length": quadros}}
    api[f"{ant}:88"]["inputs"]["images"] = ["900", 0]
    api["243"]["inputs"]["video"] = [f"{ant}:88", 0]


ENQ_TRAVA = asyncio.Lock()


async def esperar_prompt(pid, job=None, limite=3600):
    """Espera um prompt terminar na ComfyUI. Para se cancelarem, se a ComfyUI reiniciar ou ficar fora por 60 s."""
    t0, fora_desde, ultima_fila, sumiu = time.time(), None, 0.0, 0
    while time.time() - t0 < limite:
        if job is not None and (job["id"] in CANCELAR or job.get("estado") == "cancelado"):
            await cancelar_no_comfy(pid)
            raise Cancelado()
        try:
            h = await comfy("GET", f"/history/{pid}", timeout=15)
            fora_desde = None
            if pid in h:
                return h[pid]
            if time.time() - ultima_fila > 10:
                ultima_fila = time.time()
                q = await comfy("GET", "/queue", timeout=10)
                ids = {row[1] for row in q.get("queue_running", []) + q.get("queue_pending", [])}
                if pid in ids:
                    sumiu = 0
                else:
                    h = await comfy("GET", f"/history/{pid}", timeout=15)  # pode ter terminado entre as perguntas
                    if pid in h:
                        return h[pid]
                    sumiu += 1
                    if sumiu >= 2:
                        raise RuntimeError("A ComfyUI reiniciou no meio da geração (provável falta de memória). "
                                           "Gere de novo.")
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
            fora_desde = fora_desde or time.time()
            if time.time() - fora_desde > COMFY_FORA_S:
                raise RuntimeError("A ComfyUI de vídeo parou de responder por mais de 1 minuto (fechou ou travou). "
                                   "Abra o estúdio de novo e gere outra vez.")
        await asyncio.sleep(2)
    raise TimeoutError("A ComfyUI demorou demais (mais de 1 hora).")


async def enquadrar_personagem(imagem, video, job=None, checar_musica=False):
    """Recorta a imagem do personagem no enquadramento da pessoa do vídeo (resultado em cache)."""
    imagem, video = Path(imagem).name, Path(video).name
    chave = hashlib.sha1(f"{imagem}|{video}|v1".encode()).hexdigest()[:12]
    destino = COMFY_DIR / "input" / f"enq_{chave}.png"
    meta = destino.with_suffix(".json")
    if meta.exists() and destino.exists():
        return json.loads(meta.read_text(encoding="utf-8"))
    async with ENQ_TRAVA:
        if meta.exists() and destino.exists():
            return json.loads(meta.read_text(encoding="utf-8"))
        if checar_musica:
            ocupada, _ = await musica_ocupada()
            if ocupada:
                return {"ok": False, "motivo": "A música está usando a placa de vídeo agora. O enquadramento "
                                               "automático é feito quando você mandar gerar."}
        prefixo = f"estudio_pose/{chave}"
        api = enquadrar.api_pose(imagem, video, prefixo)
        info_job = job or {"id": None, "preset": "wan_animate", "prompt": "", "seed": None}
        # "front": passa na frente da fila (só espera a geração que já estiver rodando)
        r = await comfy("POST", "/prompt", json={
            "prompt": api, "client_id": CLIENT_ID + "-prep", "front": True,
            "extra_data": extra_data(info_job, motor="DWPose", prompt="", ia="Detecção de pose (DWPose)")})
        pid = r["prompt_id"]
        try:
            item = await esperar_prompt(pid, None, limite=3600)
        except TimeoutError:
            return {"ok": False, "motivo": "A ComfyUI demorou demais para detectar a pose."}
        if (item.get("status") or {}).get("status_str") != "success":
            return {"ok": False, "motivo": "Falhou a detecção de pose na ComfyUI."}
        saida = COMFY_DIR / "output" / "estudio_pose"
        ji = sorted(saida.glob(f"{chave}_img*.json"))
        jv = sorted(saida.glob(f"{chave}_vid*.json"))
        if not ji or not jv:
            return {"ok": False, "motivo": "A detecção de pose não gerou resultado."}
        caixa, info = await asyncio.to_thread(enquadrar.calcular_recorte, ji[-1], jv[-1], COMFY_DIR / "input" / imagem)
        if caixa is None:
            return {"ok": False, "motivo": info}
        rec = await asyncio.to_thread(enquadrar.recortar, COMFY_DIR / "input" / imagem, caixa, destino)
        res = {"ok": True, "nome": destino.name, "url": f"/api/entrada/{destino.name}", "fonte": info["fonte"],
               "tamanho": rec["tamanho"], "preenchido": rec["preenchido"]}
        meta.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
        return res


async def api_enquadrar(req):
    b = await req.json()
    if not b.get("imagem") or not b.get("video"):
        raise web.HTTPBadRequest(text="Envie a imagem do personagem e o vídeo de movimento.")
    try:
        return web.json_response(await enquadrar_personagem(b["imagem"], b["video"], checar_musica=True))
    except web.HTTPException:
        raise
    except Exception as exc:
        return web.json_response({"ok": False, "motivo": msg_erro(exc)})


async def api_entrada(req):
    nome = Path(req.match_info["nome"]).name
    arq = COMFY_DIR / "input" / nome
    if not arq.is_file():
        raise web.HTTPNotFound(text="Arquivo não encontrado no HD.")
    return web.FileResponse(arq)


def qualidade_chave(p, nome):
    qs = p.get("qualidades") or {}
    return achar_chave(qs, nome, p.get("nomes_antigos")) if nome else None


def qualidade(p, nome):
    """Passos e ajustes da qualidade escolhida. Valor pode ser int ou {"passos": n, "ajustes": [[no, entrada, v]]}.
    Aceita nomes antigos ('Rapido', 'Maxima (48)'...) para o Reusar de trabalhos antigos."""
    qs = p.get("qualidades") or {}
    chave = qualidade_chave(p, nome) or qualidade_chave(p, (p.get("padrao") or {}).get("qualidade"))
    q = qs.get(chave) if chave else None
    if q is None:
        return int(p.get("padrao", {}).get("steps", 8)), []
    if isinstance(q, dict):
        return int(q["passos"]), q.get("ajustes", [])
    return int(q), []


async def planejar(p, b):
    """Decide workflow, tamanho e trechos a partir das escolhas (usado por gerar e por estimativa)."""
    pad = p.get("padrao", {})
    ant = p.get("nomes_antigos")
    dur = b.get("duracao") or pad.get("duracao")
    fmt = b.get("formato") or pad.get("formato")
    res = b.get("resolucao") or pad.get("resolucao")
    if p.get("duracoes") and dur:
        dur = achar_chave(p["duracoes"], dur, ant) or dur
    if p.get("formatos") and fmt:
        fmt = achar_chave(p["formatos"], fmt, ant) or fmt
    tab_res = p.get("resolucoes") or p.get("resolucoes_mp")
    if tab_res and res:
        res = achar_chave(tab_res, res, ant) or res
    pl = {"dur": dur, "fmt": fmt, "res": res, "res_padrao": pad.get("resolucao"), "dims": None,
          "proporcao": None, "trechos": None, "quadros": None, "fator_res": 1, "aviso": None, "video_info": None}
    if p.get("duracoes") and dur not in p["duracoes"]:
        raise web.HTTPBadRequest(text=f"Duração inválida: {dur}")
    if p.get("resolucoes") and res not in p["resolucoes"]:
        raise web.HTTPBadRequest(text=f"Resolução inválida: {res}")
    if p.get("formatos") and fmt and fmt not in p["formatos"]:
        raise web.HTTPBadRequest(text=f"Formato inválido: {fmt}")
    if p.get("resolucoes_mp"):  # modelos que escolhem o tamanho por megapixels (ResolutionSelector)
        if res not in p["resolucoes_mp"]:
            raise web.HTTPBadRequest(text=f"Resolução inválida: {res}")
        pl["mp"] = p["resolucoes_mp"][res]
        pl["fator_res"] = round(pl["mp"] / p["resolucoes_mp"][pl["res_padrao"]], 2)
    precisa_video = dur == "Igual ao vídeo" or (p.get("formatos", {}).get(fmt) == "auto")
    if precisa_video:
        if not b.get("video"):
            raise web.HTTPBadRequest(text="Envie o vídeo de movimento (a opção 'Igual ao vídeo' usa ele).")
        pl["video_info"] = vi = await info_video(b["video"])
    if fmt and p.get("formatos"):
        v = p["formatos"][fmt]
        if p.get("resolucoes"):
            tab, tab_pad = p["resolucoes"][res], p["resolucoes"][pl["res_padrao"]]
            chave = "auto" if v == "auto" else fmt
            v, base = tab[chave], tab_pad[chave]
            if chave == "auto":
                v, base = dims_auto(v, vi["largura"], vi["altura"]), dims_auto(base, vi["largura"], vi["altura"])
            pl["fator_res"] = round((v[0] * v[1]) / (base[0] * base[1]), 2)
        if isinstance(v, (list, tuple)):
            pl["dims"] = [int(v[0]), int(v[1])]
        else:
            pl["proporcao"] = v
    if "api_por_duracao" in p:
        if dur in p["api_por_duracao"]:
            pl["arq"] = p["api_por_duracao"][dur]
        else:  # Igual ao vídeo: quantos trechos forem precisos
            q = pl["video_info"]["quadros"]
            lim = int(p.get("duracao_video_max_s", 60) * FPS_ANIMATE)
            if q > lim:
                pl["aviso"] = f"O vídeo tem {q / FPS_ANIMATE:.1f} s; gerando só os primeiros {lim // FPS_ANIMATE} s."
                q = lim
            if q < 17:
                raise web.HTTPBadRequest(text="Vídeo de movimento curto demais (menos de 1 s).")
            pl["quadros"], pl["trechos"] = q, plano_trechos(q)
            pl["arq"] = p["api_por_duracao"]["~5 s" if len(pl["trechos"]) == 1 else "~10 s"]
    else:
        pl["arq"] = p["api"]
    return pl


def conferir_entradas(nomes):
    """Os arquivos enviados ainda estão no HD? (um 'Reusar' de trabalho removido pode apontar para arquivo apagado)"""
    faltando = sorted({Path(n).name for n in nomes if n and not (COMFY_DIR / "input" / Path(n).name).is_file()})
    if faltando:
        raise web.HTTPBadRequest(text="Esse arquivo não existe mais no HD: " + ", ".join(faltando) +
                                      ". Ele pode ter sido apagado junto com um trabalho removido. Envie de novo.")


CENA_APRESENTADOR = ("A person talking naturally to the camera like a presenter, natural head movement, "
                     "expressive face, blinking, steady camera, realistic.")


async def processar_apresentador(job):
    """1) voz: Chatterbox (por frases) + limpeza com Whisper; 2) vídeo: LTX-2.3 ou InfiniteTalk do tamanho do áudio."""
    jid = job["id"]
    TAREFAS_ATIVAS.add(jid)
    try:
        await pegar_vez(job)  # na ordem dos pedidos; se cancelarem enquanto espera, sai na hora
        try:
            await esperar_gpu(job)  # [C] inclui a fase da voz
            verificar_cancelado(job)
            agora = time.time()
            job.update(estado="rodando", inicio=agora, inicio_voz=agora)
            entrada = COMFY_DIR / "input"
            if job.get("audio"):
                audio_nome = job["audio"]
                dur = await duracao_audio(entrada / audio_nome)
            elif job.get("voz11"):  # voz do ElevenLabs (nuvem): gera o MP3 e usa como áudio pronto
                job["prog"] = {"fase": f"Gerando a voz no ElevenLabs ({job.get('voz_nome') or ''})", "passos": 0}
                salvar()
                mp3 = entrada / f"apres_{jid}_11l.mp3"
                gastos = await asyncio.to_thread(elevenlabs.falar, job["prompt"], job["voz11"], mp3)
                job["creditos_11l"] = gastos
                verificar_cancelado(job)
                audio_nome = mp3.name
                dur = await duracao_audio(mp3)
            else:
                trechos = voz.dividir(job["prompt"])
                idioma = voz.IDIOMAS.get(job.get("idioma") or "Português", "Portuguese (pt)")
                job["prog"] = {"fase": f"Gerando a voz ({len(trechos)} trecho{'s' if len(trechos) > 1 else ''})",
                               "passos": 0}
                api = voz.montar_tts(trechos, idioma, job.get("voz"), job["seed"], f"audio/estudio/apres_{jid}")
                r = await comfy("POST", "/prompt", json={
                    "prompt": api, "client_id": CLIENT_ID,
                    "extra_data": extra_data(job, motor=VOZ_MOTOR, ia=f"{VOZ_MOTOR} (voz do Apresentador)")})
                job["prompt_id_voz"] = r["prompt_id"]
                RESERVA["ate"] = 0.0  # daqui em diante o estado 'rodando' já avisa o painel
                salvar()
                item = await esperar_prompt(r["prompt_id"], job)
                if (item.get("status") or {}).get("status_str") != "success":
                    estado, msg, tec = resultado_do_historico(item)
                    if estado == "cancelado":
                        raise Cancelado()
                    if tec:
                        job["erro_tecnico"] = tec
                    raise RuntimeError("Falhou ao gerar a voz. " + msg)
                arquivos = []
                for i, t in enumerate(trechos):
                    it = item["outputs"].get(f"s{i}", {}).get("audio", [{}])[0]
                    arquivos.append((COMFY_DIR / "output" / it.get("subfolder", "") / it["filename"], t))
                verificar_cancelado(job)
                job["prog"]["fase"] = "Limpando a voz (cortando sobras com o Whisper)"
                destino = entrada / f"apres_{jid}.wav"
                codigo = idioma.split("(")[-1].rstrip(")")
                dur, job["relatorio_voz"] = await asyncio.to_thread(voz.juntar, arquivos, destino, codigo)
                for arq, _ in arquivos:  # os trechos já foram juntados no .wav: não servem mais
                    try:
                        arq.unlink(missing_ok=True)
                    except OSError:
                        pass
                audio_nome = destino.name
            if not dur:
                raise RuntimeError("Não consegui medir a duração do áudio.")
            if dur > 180:
                job["aviso"] = f"Áudio de {dur:.0f} s: gerando só os primeiros 180 s."
                dur = 180
            job["segundos_audio"] = dur
            from PIL import Image
            with Image.open(entrada / job["imagem"]) as im:
                tam_foto = im.size
            motor = job.get("motor") or "Automático"
            automatico = sem_acento(motor).startswith("automatico")
            usar_ltx = motor.startswith("LTX") or (automatico and dur <= apresentador.LTX_MAX_S)
            if usar_ltx and not ltx23_instalado():
                # 13/11/2026: o Automatico so vai de LTX-2.3 se ele ESTIVER instalado. Quem
                # instalou o Apresentador pelo botao tem o InfiniteTalk, e e com ele que vai.
                if not automatico:
                    raise RuntimeError("O motor LTX-2.3 não está instalado nesta máquina. "
                                       "Escolha o motor Automático ou InfiniteTalk.")
                usar_ltx = False
            cena = job.get("cena") or CENA_APRESENTADOR
            if usar_ltx:
                if dur > apresentador.LTX_MAX_S + 5:
                    raise RuntimeError(f"Áudio de {dur:.0f} s: longo demais para o LTX-2.3. Use o motor InfiniteTalk.")
                w, h = apresentador.tamanho_ltx(*tam_foto)
                base = cofre.ler_json("presets/ltx23_ia2v.api.json")
                api = apresentador.montar_ltx(base, job["imagem"], audio_nome, dur, w, h,
                                              cena + " Perfect lip sync to the audio.", job["seed"],
                                              f"video/estudio/apresentador_{jid}")
                job["amostradores"] = ["340:291", "340:310"]
                job["total_passos"] = 10  # medido pelo progresso da ComfyUI: 6 na meia resolução + 4 na ampliação
                job["segmentos"] = 1
                job["saida_final"] = "341"
                job["motor_usado"] = "LTX-2.3"
            else:
                w, h = apresentador.tamanho(*tam_foto)
                api = apresentador.montar(job["imagem"], audio_nome, dur, w, h, cena,
                                          job["seed"], f"video/estudio/apresentador_{jid}")
                job["amostradores"] = [k for k, n in api.items() if n["class_type"] == "SamplerCustomAdvanced"]
                job["total_passos"] = job["steps"] * len(job["amostradores"])
                job["segmentos"] = len(job["amostradores"])
                job["motor_usado"] = "InfiniteTalk"
            job["tamanho"] = [w, h]
            job["ia"] = info_ia(job)
            job["prog"] = {"fase": "Carregando modelo do vídeo", "passos": 0}
            verificar_cancelado(job)
            r = await comfy("POST", "/prompt", json={"prompt": api, "client_id": CLIENT_ID,
                                                     "extra_data": extra_data(job)})
            registrar_prompt(job, r["prompt_id"])
            if jid in CANCELAR:
                await cancelar_no_comfy(r["prompt_id"])
                raise Cancelado()
            salvar()
        finally:
            RESERVA["ate"] = 0.0
            ENVIO.release()
    except Cancelado:
        marcar(job, "cancelado", "Cancelado")
    except Exception as exc:
        marcar(job, "erro", msg_erro(exc))
        guardar_tecnico(job, exc)
    finally:
        TAREFAS_ATIVAS.discard(jid)
        CANCELAR.discard(jid)
        limpar_se_removido(job)  # ex.: removido durante a limpeza da voz: apaga o apres_<id>.wav que o Whisper gravou
        salvar()


async def gerar_apresentador(aba, p, b):
    foto = b.get("imagem")
    if not foto:
        raise web.HTTPBadRequest(text="Envie a foto do apresentador.")
    texto = (b.get("prompt") or "").strip()
    if not b.get("audio") and not texto:
        raise web.HTTPBadRequest(text="Escreva o texto que ele vai falar (ou envie um áudio pronto).")
    seed = int(b["seed"]) if str(b.get("seed", "")).strip().isdigit() else random.randint(1, 2**31)
    jid = uuid.uuid4().hex[:8]
    voz_ref, voz_nome, origem = b.get("voz"), None, ("enviada" if b.get("voz") else "padrao")
    if b.get("voz_id"):  # voz escolhida na biblioteca (já clonada antes)
        v = next((x for x in vozes_lista() if x["id"] == b["voz_id"]), None)
        if not v:
            raise web.HTTPBadRequest(text="Essa voz não está mais salva.")
        voz_ref, voz_nome, origem = voz_em_input(v), v["nome"], "salva"
    if b.get("audio"):
        origem = "audio_pronto"
    voz11 = (b.get("voz11") or "").strip() or None  # id de uma voz do ElevenLabs (nuvem)
    if voz11 and not b.get("audio"):
        if not elevenlabs.tem_chave():
            raise web.HTTPBadRequest(text="A chave do ElevenLabs não está salva na pasta API (elevenlabs.txt).")
        v11 = next((x for x in elevenlabs.vozes() if x["id"] == voz11), None)
        voz_nome, origem = (v11 or {}).get("nome") or "ElevenLabs", "elevenlabs"
    conferir_entradas([foto, b.get("audio"), voz_ref])
    idioma = achar_chave(p.get("idiomas") or [], b.get("idioma")) or p["padrao"].get("idioma")
    job = {"id": jid, "aba": aba, "preset": p["id"], "nome": p["nome"], "modo": "referencia", "prompt": texto,
           "imagem": Path(foto).name, "audio": Path(b["audio"]).name if b.get("audio") else None,
           "voz": Path(voz_ref).name if voz_ref else None, "voz_nome": voz_nome, "voz_id": b.get("voz_id"),
           "voz_origem": origem, "voz11": voz11, "idioma": idioma, "cena": (b.get("cena") or "").strip(),
           "motor": motor_rotulo(p, b.get("motor")), "steps": p["padrao"]["steps"], "seed": seed,
           "estado": "fila", "criado": time.time(), "amostradores": [], "total_passos": 1, "saida_final": "salvar"}
    job["ia"] = info_ia(job)
    if b.get("simular"):
        return web.json_response({"job": job, "trechos": voz.dividir(texto) if texto else []})
    JOBS.append(job)
    TAREFAS_ATIVAS.add(jid)
    salvar()
    em_segundo_plano(processar_apresentador(job))
    return web.json_response({"id": jid})


# ---------------------------------------------------------------- plano-sequência (H3 Singularity + Motion Context)
# A IA "MiniMax H3 Singularity - Plano-sequência": o trabalho roda pelo script projetos\fz_contexto\plano_sequencia.py
# (tomada contínua com pessoa real). O nó Easy-Media SÓ executa pela tela da ComfyUI (não por POST /prompt), então o
# estúdio não manda workflow: ele roda o script em segundo plano, leva o progresso do log dele para a tela e, no fim,
# registra o vídeo na galeria (o script, ao ver o estúdio ocupado, pula sozinho a etapa "por_no_painel").
FZ_CONTEXTO = ROOT / "projetos" / "fz_contexto"
FZ_SAIDAS = FZ_CONTEXTO / "saidas"
FZ_PROJETOS = FZ_CONTEXTO / "projetos"
RE_LINHA_LOG = re.compile(r"^\[(\d\d:\d\d:\d\d)\]\s*(.*)$")
CONTEXTO_LOCK = asyncio.Lock()  # um plano-sequência por vez (a tela invisível do envio usa um perfil só do Edge)


def _soltar_vez():
    """Devolve a vez da placa (ENVIO). O plano-sequência solta no meio (para o PRÓPRIO estúdio fazer a ficha no
    Krea 2) e de novo no fim — daí o release tolerante."""
    RESERVA["ate"] = 0.0
    try:
        ENVIO.release()
    except RuntimeError:
        pass
PEDIDO_CONTEXTO = (
    "Você prepara a geração de um vídeo realista com pessoa de verdade (MiniMax H3 Singularity) a partir de uma CENA "
    "escrita em português. Responda SÓ com um JSON, sem comentário e sem cercas de código, com estas 3 chaves:\n"
    '{"personagem": "...", "sujeito": "...", "som": "..."}\n'
    '- "personagem": descrição EM INGLÊS da foto realista da pessoa principal (idade, cabelo, rosto, roupa, '
    'acessórios) para gerar o retrato; comece exatamente com "Candid photograph, photorealistic, shot on 35mm film, '
    'natural skin texture, visible pores, soft natural light, plain background, no text, no logo," e siga descrevendo '
    'a pessoa (uma só, de frente, rosto visível).\n'
    '- "sujeito": EM INGLÊS, uma frase no formato "<Subject 1> is the <quem é a pessoa> in <Picture 1>: hair, clothes, '
    'accessories."\n'
    '- "som": EM INGLÊS, só o som ambiente da cena (ninguém fala, sem vozes).\n'
    "Ninguém fala nem canta. CENA (português): "
)


def py_dos_scripts():
    """O `py` do Windows (tem requests); o python_embeded não acha os módulos dos scripts do fz_clipe."""
    if not plataforma.WIN:
        return shutil.which("python3") or sys.executable
    c = shutil.which("py")
    if c:
        return c
    for p in (Path(os.environ.get("WINDIR") or r"C:\Windows") / "py.exe", Path(r"C:\Windows\py.exe")):
        if p.is_file():
            return str(p)
    return "py"


def ler_texto(caminho):
    try:
        return caminho.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def ultima_fase(caminho):
    """Última linha do log do script, sem o [HH:MM:SS]."""
    linhas = [l for l in ler_texto(caminho).splitlines() if l.strip()]
    if not linhas:
        return None
    m = RE_LINHA_LOG.match(linhas[-1])
    return (m.group(2) if m else linhas[-1]).strip()


def json_da_ia(txt):
    """A resposta da IA de texto vem com conversa em volta: pega o primeiro objeto JSON."""
    i, j = txt.find("{"), txt.rfind("}")
    if i < 0 or j <= i:
        raise RuntimeError("A IA de texto não devolveu o JSON com personagem/sujeito/som. Tente gerar de novo.")
    try:
        d = json.loads(txt[i:j + 1])
    except ValueError as exc:
        raise RuntimeError(f"A IA de texto devolveu um JSON inválido ({exc}). Tente gerar de novo.")
    return {k: str(d.get(k) or "").strip() for k in ("personagem", "sujeito", "som")}


async def textos_do_contexto(job):
    """O H3 exige personagem/sujeito/som em inglês: pede à IA de texto local (Qwen) a partir da cena em português.
    Usa o 9B ("rapido"): com o trabalho já na fila a placa conta como ocupada, então ele tende a rodar no processador."""
    res = await TEXTO.pedir("livre", PEDIDO_CONTEXTO + (job.get("prompt") or ""), {}, "rapido",
                            placa_ocupada_para_texto, ficha=None, fichas_ias=fichas().get("ias"),
                            pasta_input=COMFY_DIR / "input")
    return json_da_ia(res.get("texto") or "")


async def encerrar_contexto(proc):
    """Cancelar/erro: mata o script, a tela invisível dele e interrompe o que ele já pôs na ComfyUI."""
    if proc and proc.returncode is None:
        try:
            proc.kill()
            await proc.wait()
        except Exception:
            pass
        try:
            if not plataforma.WIN:
                import psutil
                for p in psutil.process_iter(["cmdline"]):
                    if "edge_comfy_headless" in " ".join(p.info.get("cmdline") or []):
                        p.kill()
                raise OSError("sem powershell")
            await asyncio.create_subprocess_exec(
                "powershell", "-NoProfile", "-Command",
                "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object { $_.CommandLine -match "
                "'edge_comfy_headless' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }",
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        except Exception:
            pass
    try:
        await comfy("POST", "/interrupt")
    except Exception:
        pass


def erro_do_log(conteudo):
    for l in reversed(conteudo.splitlines()):
        if "ERRO:" in l:  # a linha vem com o carimbo de hora na frente: "[19:11:35] ERRO: ..."
            return l.split("ERRO:", 1)[1].strip().split("Traceback")[0].strip()[:400] or \
                "O plano-sequência terminou com erro (veja o log na pasta do trabalho)."
    return "O plano-sequência terminou com erro (veja o log na pasta do trabalho)."


async def processar_contexto(job):
    """Roda o plano_sequencia.py em segundo plano e leva o progresso do log dele para a tela do estúdio."""
    jid = job["id"]
    proc = None
    pegou_lock = False
    TAREFAS_ATIVAS.add(jid)
    try:
        # Um plano-sequência por vez: o envio usa uma "tela invisível" com UM perfil do Edge — dois ao mesmo tempo
        # brigariam pelo perfil e a ComfyUI receberia dois blocos juntos.
        await CONTEXTO_LOCK.acquire()
        pegou_lock = True
        await pegar_vez(job)
        try:
            await esperar_gpu(job)
            # Devolve a vez JÁ: o script gera a ficha do personagem no Krea 2 pelo PRÓPRIO ESTÚDIO — se este trabalho
            # segurasse o ENVIO (a vez), o estúdio esperaria a si mesmo (impasse) e a foto nunca sairia.
            _soltar_vez()
            verificar_cancelado(job)
            job.update(estado="rodando", inicio=time.time())
            job["prog"] = {"fase": "Escrevendo o roteiro e a descrição da pessoa (IA de texto local)", "passos": 0}
            salvar()
            textos = await textos_do_contexto(job)
            verificar_cancelado(job)
            nome = job["fz_nome"]
            pasta = FZ_SAIDAS / nome
            pasta.mkdir(parents=True, exist_ok=True)
            log = pasta / "log.txt"
            if log.exists():
                log.unlink()
            FZ_PROJETOS.mkdir(parents=True, exist_ok=True)
            arq = FZ_PROJETOS / f"{nome}.json"
            projeto = {"nome": nome, "cena": job["prompt"], "sujeito": textos["sujeito"], "som": textos["som"],
                       "segmentos": job["segmentos"], "segundos": job["fz_segundos"], "megapixels": job["fz_mp"],
                       "lora_cinema": 0.5, "lora_real": 0.7, "gatilho": "r34l1sm"}
            if job.get("imagem"):
                projeto["imagem"] = str(COMFY_DIR / "input" / job["imagem"])
            else:
                if not textos["personagem"]:
                    raise RuntimeError("A IA de texto não descreveu a pessoa (campo personagem vazio). Tente de novo.")
                projeto["personagem"] = textos["personagem"]
            arq.write_text(json.dumps(projeto, ensure_ascii=False, indent=1), encoding="utf-8")
            job["fz_projeto"] = str(arq)
            job["prog"]["fase"] = "Começando: ficha do personagem e envio pela tela da ComfyUI"
            salvar()
            proc = await asyncio.create_subprocess_exec(
                py_dos_scripts(), str(FZ_CONTEXTO / "plano_sequencia.py"), str(arq), cwd=str(ROOT),
                env=ambiente_e(), stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            job["fz_pid"] = proc.pid
            t0, visto = time.time(), None
            while proc.returncode is None:
                await asyncio.sleep(10)
                verificar_cancelado(job)
                fase = ultima_fase(log)
                if fase and fase != visto:
                    visto = fase
                    job["prog"]["fase"] = fase[:200]
                    m = re.search(r"segmento (\d+) começou", fase)
                    if m:
                        if not job["prog"].get("t_primeiro"):
                            job["prog"]["t_primeiro"] = time.time()
                        job["prog"]["passos"] = int(m.group(1))
                        job["prog"]["t_ultimo"] = time.time()
                    salvar()
                if time.time() - t0 > 6 * 3600:
                    raise RuntimeError("O plano-sequência passou de 6 horas; parece travado (veja o log do trabalho).")
            await proc.wait()
            conteudo = ler_texto(log)
            if proc.returncode != 0:
                raise RuntimeError(erro_do_log(conteudo))
            final = pasta / f"{nome}.mp4"
            if not final.is_file():
                raise RuntimeError(f"O script terminou sem deixar o vídeo em {final}")
            destino = COMFY_DIR / "output" / "video" / "estudio"
            destino.mkdir(parents=True, exist_ok=True)
            arquivo = f"h3_contexto_{jid}_00001_.mp4"
            shutil.copy2(final, destino / arquivo)
            job["saidas"] = [{"no": "h3c", "arquivo": arquivo, "sub": "video/estudio", "tipo": "output"}]
            job["estado"] = "concluido"
            job["fim"] = time.time()
            for k in ("erro", "erro_tecnico", "erro_vigia", "aguardando"):
                job.pop(k, None)
            for l in conteudo.splitlines():  # "Emendas: 8s=0.0006, 16s=0.0011 (média 0.0028)"
                if "Emendas:" in l:
                    job["emendas"] = l.split("Emendas:", 1)[1].strip()[:300]
            tam = re.search(r"(\d{3,4})x(\d{3,4})", conteudo)
            if tam:
                job["tamanho"] = [int(tam.group(1)), int(tam.group(2))]
            job["folha_quadros"] = str(pasta / "folha_quadros.png")
            job["pasta_fz"] = str(pasta)
            job["ia"] = info_ia(job)
            ULTIMO_PRESET["id"] = job["preset"]
            ATIVIDADE["ultima"] = time.time()
            ATIVIDADE["liberado"] = False
            try:  # entra no histórico de tempos (a estimativa do próximo já sai certa)
                total = job["fim"] - job["inicio"]
                STATS.setdefault(chave_tempo(job), []).append(
                    {"total": total, "carga": 0.0, "por_passo": total / max(1, job["segmentos"]), "pos": None})
            except Exception:
                pass
        finally:
            _soltar_vez()
    except Cancelado:
        await encerrar_contexto(proc)
        marcar(job, "cancelado", "Cancelado")
    except Exception as exc:
        await encerrar_contexto(proc)
        marcar(job, "erro", msg_erro(exc))
        guardar_tecnico(job, exc)
    finally:
        if pegou_lock:
            CONTEXTO_LOCK.release()
        TAREFAS_ATIVAS.discard(jid)
        CANCELAR.discard(jid)
        limpar_se_removido(job)
        salvar()


async def gerar_contexto(aba, p, b):
    """Pedido do plano-sequência: só a cena (português) + duração/resolução e, se quiser, a foto da pessoa."""
    cena = (b.get("prompt") or "").strip()
    if not cena:
        raise web.HTTPBadRequest(text="Escreva a CENA inteira (em português): é o que a IA transforma em vídeo.")
    dur = achar_chave(p["duracoes"], b.get("duracao")) or p["padrao"]["duracao"]
    segundos_total = int(p["duracoes"][dur])
    segundos = int(p.get("segundos_por_segmento", 8))
    n_seg = max(1, int(round(segundos_total / segundos)))
    res = achar_chave(p["resolucoes_mp"], b.get("resolucao")) or p["padrao"]["resolucao"]
    mp = float(p["resolucoes_mp"][res])
    imagem = Path(b["imagem"]).name if b.get("imagem") else None
    if imagem and not (COMFY_DIR / "input" / imagem).is_file():
        raise web.HTTPBadRequest(text="A imagem enviada não está mais na pasta de entrada: envie de novo.")
    seed = int(b["seed"]) if str(b.get("seed", "")).strip().isdigit() else random.randint(1, 2**31)
    jid = uuid.uuid4().hex[:8]
    job = {"id": jid, "aba": aba, "preset": p["id"], "nome": p["nome"],
           "modo": "referencia" if imagem else "prompt", "prompt": cena, "estilo": None, "formato": None,
           "duracao": dur, "qualidade": None, "steps": 10, "resolucao": f"{mp:.1f} MP".replace(".", ","),
           "resolucao_padrao": f"{mp:.1f} MP".replace(".", ","), "tamanho": None, "segmentos": n_seg,
           "segundos_video": segundos_total, "seed": seed, "imagem": imagem, "fz_nome": f"est_{jid}",
           "fz_mp": mp, "fz_segundos": segundos, "estado": "fila", "criado": time.time(), "amostradores": [],
           "total_passos": n_seg, "saida_final": "h3c"}
    job["ia"] = info_ia(job)
    if b.get("simular"):
        return web.json_response({"job": job})
    JOBS.append(job)
    TAREFAS_ATIVAS.add(jid)
    salvar()
    em_segundo_plano(processar_contexto(job))
    return web.json_response({"id": jid})


async def api_gerar(req):
    try:
        b = await req.json()
    except ValueError:
        raise web.HTTPBadRequest(text="Pedido inválido.")
    aba, p = preset(b.get("preset"))
    if p.get("tipo") == "apresentador":
        return await gerar_apresentador(aba, p, b)
    if p.get("tipo") == "contexto":  # MiniMax H3 Singularity - Plano-sequência (roda por script, não por POST /prompt)
        return await gerar_contexto(aba, p, b)
    modo = b.get("modo") or p["modos"][0]
    if modo not in p["modos"]:
        raise web.HTTPBadRequest(text=f"{p['nome']} não aceita o modo {modo}")
    if modo == "personagem" and not b.get("video"):
        raise web.HTTPBadRequest(text="Envie o vídeo de movimento.")
    pl = await planejar(p, b)
    dur, fmt = pl["dur"], pl["fmt"]
    api = cofre.ler_json("presets/" + pl["arq"])
    aj = p.get("ajustes_api", {})
    for no in aj.get("remover", []):
        api.pop(no, None)
    for no, entrada, valor in aj.get("religar", []):
        api[no]["inputs"][entrada] = valor
    for no, novo in aj.get("trocar", {}).items():  # correções feitas à mão (ex.: VAEDecodeTiled no Hunyuan)
        api[no] = copy.deepcopy(novo)
    c = p["campos"]
    prompt = (b.get("prompt") or "").strip()
    estilo = b.get("estilo") or p.get("padrao", {}).get("estilo")
    if estilo and p.get("estilos"):
        chave_est = achar_chave(p["estilos"], estilo, p.get("nomes_antigos"))
        if not chave_est:
            raise web.HTTPBadRequest(text=f"Estilo desconhecido: {estilo}")
        estilo = chave_est
        e = p["estilos"][estilo]
        prompt = e.get("prefixo_prompt", "") + prompt
        for no, entrada, valor in e.get("ajustes", []):
            api[no]["inputs"][entrada] = valor
    if not prompt and modo != "personagem":
        raise web.HTTPBadRequest(text="Escreva um prompt.")
    if prompt and p.get("molde_prompt"):
        # Ideogram 4 só funciona com o prompt no formato estruturado em que foi treinado; em texto solto ele
        # desenha por cima a marca "Image blocked by safety filter" (comportamento aprendido, não é censura real).
        prompt = p["molde_prompt"].replace("{proporcao}", fmt or "1:1").replace("{prompt}", prompt)
    if prompt:
        setar(api, c["prompt"], prompt)
    q_nome = qualidade_chave(p, b.get("qualidade")) or b.get("qualidade")
    steps, ajustes_q = qualidade(p, b.get("qualidade"))
    setar(api, c.get("steps"), steps)
    for no, entrada, valor in ajustes_q:
        api[no]["inputs"][entrada] = valor
    seed = int(b["seed"]) if str(b.get("seed", "")).strip().isdigit() else random.randint(1, 2**31)
    setar(api, c.get("seed"), seed)
    if pl["dims"]:
        setar(api, c.get("largura"), pl["dims"][0])
        setar(api, c.get("altura"), pl["dims"][1])
    elif pl["proporcao"]:
        setar(api, c.get("proporcao"), pl["proporcao"])
    if pl.get("mp"):
        setar(api, c.get("megapixels"), pl["mp"])
    if dur and p.get("duracoes") and "quadros" in c:
        setar(api, c["quadros"], p["duracoes"][dur])
    if "forca" in c:
        setar(api, c["forca"], float(b.get("forca") or p["padrao"].get("forca", 0.6)))
    imagens = None
    vi8 = p.get("vae_int8")  # VAE int8 do MiniMax H3: ~15% mais rápido, mesma qualidade (usa se o arquivo existir)
    if vi8 and vi8["no"] in api and (COMFY_DIR / "models" / "vae" / vi8["arquivo"]).exists():
        api[vi8["no"]]["inputs"]["vae_name"] = vi8["arquivo"]
    qc = p.get("quadros_chave")
    if qc:  # MiniMax H3 Fast: só prompt, ou primeiro (e opcionalmente último) quadro
        imagens = [Path(i).name for i in (b.get("imagens") or ([b["imagem"]] if b.get("imagem") else [])) if i][:2]
        alvo = api[qc["no"]]["inputs"]
        if modo == "prompt" or not imagens:
            if modo == "referencia":
                raise web.HTTPBadRequest(text="Envie a imagem do primeiro quadro.")
            for no in qc["remover_sem_imagem"]:
                api.pop(no, None)
            api["rs"] = {"class_type": "ResolutionSelector", "inputs": {
                "aspect_ratio": pl["proporcao"] or "16:9 (Widescreen)", "megapixels": pl.get("mp") or 0.9,
                "multiple": 32}}
            alvo.update(width=["rs", 0], height=["rs", 1])
            for ent in qc["entradas"]:
                alvo.pop(ent, None)
            imagens = None
        else:
            conferir_entradas(imagens)
            api["136"]["inputs"]["image"] = imagens[0]
            if len(imagens) > 1:
                api["qf1"] = {"class_type": "LoadImage", "inputs": {"image": imagens[1]}}
                alvo[qc["entradas"][1]] = ["qf1", 0]
    elif modo == "referencia" and p.get("referencias"):  # várias imagens: <Picture 1>, <Picture 2>...
        rf = p["referencias"]
        imagens = [Path(i).name for i in (b.get("imagens") or ([b["imagem"]] if b.get("imagem") else [])) if i]
        if not imagens:
            raise web.HTTPBadRequest(text="Envie pelo menos 1 imagem de referência.")
        if len(imagens) > rf["max"]:
            raise web.HTTPBadRequest(text=f"No máximo {rf['max']} imagens de referência.")
        conferir_entradas(imagens)
        for no in rf.get("remover", []):
            api.pop(no, None)
        destino = api[rf["no"]]["inputs"]
        for k in [k for k in destino if k.startswith(rf["prefixo"])]:
            destino.pop(k)
        for i, nome in enumerate(imagens):
            api[f"ref{i}"] = {"class_type": "LoadImage", "inputs": {"image": nome}}
            destino[f"{rf['prefixo']}{i}"] = [f"ref{i}", 0]
    elif modo in ("referencia", "personagem"):
        img = b.get("imagem")
        if not img:
            raise web.HTTPBadRequest(text="Envie a imagem de referência/personagem.")
        img = Path(img).name
        conferir_entradas([img])
        if "imagem_inicial" in p:
            ii = p["imagem_inicial"]
            api[ii["no"]] = {"class_type": "LoadImage", "inputs": {"image": img}}
            api[ii["destino"][0]]["inputs"][ii["destino"][1]] = [ii["no"], 0]
        else:
            setar(api, c["imagem"], img)
    if modo == "personagem":
        conferir_entradas([b["video"]])
        setar(api, c["video"], Path(b["video"]).name)
    if "242:90" in api:  # template original fixava a altura do 2º trecho em 480
        api["242:90"]["inputs"]["height"] = ["160", 0]
    saida_final = p.get("saida_final", {}).get(dur)
    if pl["trechos"]:  # Igual ao vídeo (feito depois de seed/steps: os trechos extras copiam o 2º)
        if len(pl["trechos"]) == 1:
            api["232:62"]["inputs"]["length"] = pl["trechos"][0]
            saida_final = "19"
        else:
            montar_trechos(api, pl["trechos"], pl["quadros"])
            saida_final = "243"
    jid = uuid.uuid4().hex[:8]
    setar(api, c.get("prefixo"), f"{'video/' if aba == 'video' else ''}estudio/{p['id']}_{jid}")
    amostradores = [k for k, n in api.items() if n["class_type"] in ("KSampler", "KSamplerAdvanced", "SamplerCustom",
                                                                      "SamplerCustomAdvanced")]
    n_amostr = len(pl["trechos"]) if pl["trechos"] else \
        p.get("amostragens_por_duracao", {}).get(dur, p.get("amostragens", len(amostradores) or 1))
    job = {"id": jid, "aba": aba, "preset": p["id"], "nome": p["nome"], "modo": modo, "prompt": b.get("prompt", ""),
           "estilo": estilo, "formato": fmt, "duracao": dur, "qualidade": q_nome, "steps": steps,
           "resolucao": pl["res"], "resolucao_padrao": pl["res_padrao"], "fator_res": pl["fator_res"],
           "tamanho": tamanho_final(p, pl["dims"]), "segmentos": len(pl["trechos"]) if pl["trechos"] else None,
           "segundos_video": round(pl["quadros"] / FPS_ANIMATE, 1) if pl["quadros"] else None, "aviso": pl["aviso"],
           "seed": seed, "forca": b.get("forca"), "imagem": Path(b["imagem"]).name if b.get("imagem") else None,
           "video": Path(b["video"]).name if b.get("video") else None,
           "enquadrar": bool(b.get("enquadrar")), "imagem_enquadrada": None, "imagens": imagens,
           "estado": "fila", "criado": time.time(), "amostradores": amostradores,
           "total_passos": steps * n_amostr, "saida_final": saida_final}
    job["ia"] = info_ia(job)
    if req.query.get("simular"):  # só monta o workflow (para validar sem gastar GPU)
        return web.json_response({"api": api, "job": job})
    antes = None
    if modo == "personagem" and b.get("enquadrar"):
        async def antes():  # roda na vez do trabalho (depois de esperar a música), não na hora do clique
            enq = await enquadrar_personagem(job["imagem"], job["video"], job)
            if enq.get("ok"):
                setar(api, c["imagem"], enq["nome"])
                job["imagem_enquadrada"] = enq["nome"]
            else:
                job["aviso"] = ((job["aviso"] + " · ") if job.get("aviso") else "") + \
                    "Enquadramento automático não aplicado: " + enq.get("motivo", "")
    JOBS.append(job)
    TAREFAS_ATIVAS.add(jid)
    salvar()
    sinal = asyncio.Event()  # o despachante acende quando o trabalho entra em espera (vez, música, enquadramento)
    tarefa = em_segundo_plano(despachar(job, api, antes, sinal))
    espera = asyncio.ensure_future(sinal.wait())
    try:
        # os 8 s só valem quando o POST /prompt está mesmo indo: se o trabalho ficou esperando, responde na hora
        done, _ = await asyncio.wait({tarefa, espera}, timeout=8, return_when=asyncio.FIRST_COMPLETED)
    finally:
        espera.cancel()
    if tarefa in done:
        exc = tarefa.result()
        if exc is not None:  # a ComfyUI recusou ou está fora do ar: como antes, erro no formulário e sem card
            if getattr(exc, "tecnico", None):
                try:  # o detalhe técnico (em inglês) fica só no log do estúdio
                    print(f"[estúdio] a ComfyUI recusou {p['id']}: {exc.tecnico[:1500]}", flush=True)
                except Exception:
                    pass
            if job in JOBS:
                JOBS.remove(job)
                salvar()
            return resposta_erro(exc)
        return web.json_response({"id": jid})
    resp = {"id": jid}
    if sinal.is_set():
        resp["aguardando"] = job.get("aguardando") or job.get("prog", {}).get("fase") or \
            "Na fila: espera o trabalho da frente ser enviado para a placa de vídeo."
    return web.json_response(resp)


async def api_jobs(req):
    aba = req.query.get("aba")
    try:
        limite = max(1, min(5000, int(req.query.get("limite") or 120)))
    except ValueError:
        limite = 120
    try:
        antes = float(req.query["antes"]) if req.query.get("antes") else None
    except ValueError:
        antes = None
    lista = [j for j in reversed(JOBS) if not j.get("lixeira") and (not aba or j.get("aba") == aba)
             and (antes is None or j.get("criado", 0) < antes)]
    esperas = calcular_esperas()  # uma vez só por requisição (a conta da fila é linear)
    return web.json_response([publico(j, esperas) for j in lista[:limite]], headers={"X-Total": str(len(lista))})


async def api_estimativa(req):
    q = req.query
    _, p = preset(q.get("preset"))
    steps, _ = qualidade(p, q.get("qualidade"))
    if p.get("tipo") == "apresentador":  # não tem workflow fixo: o tempo vem do texto/áudio e do motor
        job = {"preset": p["id"], "motor": q.get("motor"), "prompt": q.get("texto") or "",
               "audio": q.get("audio") or None}
        return web.json_response({"segundos": estimativa_segura(job), "historico": False,
                                  "carregado": ULTIMO_PRESET["id"] == p["id"]})
    try:
        pl = await planejar(p, {k: q.get(k) or None for k in ("duracao", "formato", "resolucao", "video")})
    except web.HTTPBadRequest as e:
        return web.json_response({"segundos": None, "motivo": e.text})
    job = {"preset": p["id"], "duracao": pl["dur"], "steps": steps, "resolucao": pl["res"],
           "resolucao_padrao": pl["res_padrao"], "fator_res": pl["fator_res"],
           "segmentos": len(pl["trechos"]) if pl["trechos"] else None}
    tem_hist = bool(STATS.get(chave_tempo(job)))
    return web.json_response({"segundos": estimativa_segura(job), "historico": tem_hist,
                              "carregado": ULTIMO_PRESET["id"] == p["id"], "tamanho": tamanho_final(p, pl["dims"]),
                              "segmentos": job["segmentos"], "aviso": pl["aviso"],
                              "segundos_video": round(pl["quadros"] / FPS_ANIMATE, 1) if pl["quadros"] else None})


async def api_cancelar(req):
    """Nunca dá 500: se a ComfyUI estiver fora do ar ou o trabalho estiver na fase da voz, marca cancelado aqui."""
    j = achar_job(req.match_info["id"])
    if not j:
        return web.json_response({"ok": False, "motivo": "Trabalho não encontrado."}, status=404)
    try:
        if j.get("estado") not in ("fila", "rodando"):
            return web.json_response({"ok": True, "estado": j.get("estado")})
        if j["id"] in TAREFAS_ATIVAS:
            CANCELAR.add(j["id"])  # a tarefa (espera da música, voz do Apresentador) para sozinha
        aviso = None
        for pid in [x for x in (j.get("prompt_id"), j.get("prompt_id_voz")) if x]:
            if not await cancelar_no_comfy(pid):
                aviso = "A ComfyUI não respondeu; o trabalho foi marcado como cancelado aqui."
        marcar(j, "cancelado", "Cancelado")
        salvar()
        return web.json_response({"ok": True, "estado": "cancelado", "aviso": aviso})
    except Exception as exc:
        try:
            marcar(j, "cancelado", "Cancelado")
            salvar()
        except Exception:
            pass
        return web.json_response({"ok": True, "estado": "cancelado", "aviso": msg_erro(exc)})


# ---------------------------------------------------------------- remover = apagar do HD
def arquivos_do_job(j):
    """Caminhos no disco das saídas de um trabalho."""
    for s in j.get("saidas") or []:
        yield caminho_saida(s)


def entradas_do_job(j):
    """Nomes (em ComfyUI\\input) dos arquivos que o trabalho usa: uploads, recorte, voz."""
    nomes = set()
    for campo in ("imagem", "video", "audio", "voz", "imagem_enquadrada"):
        v = j.get(campo)
        if isinstance(v, str) and v.strip():
            nomes.add(Path(v).name)
    for v in j.get("imagens") or []:
        if isinstance(v, str) and v.strip():
            nomes.add(Path(v).name)
    if j.get("preset") == "apresentador" and j.get("id"):
        nomes.add(f"apres_{j['id']}.wav")
    return nomes


def junto_com(nome):
    """Arquivos que andam junto com uma entrada: o original de um upload convertido (e vice-versa) e o .json do
    recorte (cache do enquadramento)."""
    inp = COMFY_DIR / "input"
    extra = set()
    m = re.fullmatch(r"(estudio_[0-9a-f]+)_(?:16fps\.mp4|voz\.wav)", nome)
    if m:
        extra.update(x.name for x in inp.glob(m.group(1) + ".*"))
    m = re.fullmatch(r"(estudio_[0-9a-f]+)\.[A-Za-z0-9]+", nome)
    if m:
        extra.update(x.name for x in inp.glob(m.group(1) + "_16fps.mp4"))
        extra.update(x.name for x in inp.glob(m.group(1) + "_voz.wav"))
    m = re.fullmatch(r"(enq_[0-9a-f]+)\.png", nome)
    if m:
        extra.add(m.group(1) + ".json")
    return extra


def _dentro(caminho, base):
    try:
        caminho.resolve().relative_to(base.resolve())
        return True
    except (ValueError, OSError):
        return False


def criado_pelo_estudio(nome, j=None):
    """Arquivo de ComfyUI\\input que o PRÓPRIO estúdio criou (upload estudio_<hex>, recorte enq_<hex>, voz
    apres_<id do trabalho>.wav). As vozes salvas (voz_*) são da biblioteca e o resto é do dono."""
    if RE_UPLOAD.fullmatch(nome) or RE_ENQ.fullmatch(nome):
        return True
    return bool(j and j.get("id") and nome == f"apres_{j['id']}.wav")


def reenviado_depois(nome, j):
    """O mesmo arquivo foi enviado de novo DEPOIS deste trabalho (o nome vem do conteúdo, então o dono pode estar
    com ele num formulário ainda não enviado): não apaga."""
    if not RE_UPLOAD.fullmatch(nome):
        return False
    try:
        return (COMFY_DIR / "input" / nome).stat().st_mtime > float(j.get("criado") or 0) + 2
    except (OSError, ValueError, TypeError):
        return False


def apagar_trabalho(j):
    """Apaga do HD as saídas E os intermediários (voz do Apresentador, trechos, recorte, uploads).
    Em ComfyUI\\input só apaga o que o estúdio criou (criado_pelo_estudio); o resto fica no HD e volta em 'mantidos'.
    Nunca apaga o que outro trabalho (fora da lixeira) ou a biblioteca de vozes usa.
    Devolve (n apagados, bytes, falhas, mantidos)."""
    inp, out = COMFY_DIR / "input", COMFY_DIR / "output"
    outros = [x for x in JOBS if x is not j and not x.get("lixeira")]
    protegidos = set()
    for x in outros:
        for n in entradas_do_job(x):
            protegidos.add(n)
            protegidos.update(junto_com(n))
    protegidos.update(v.get("arquivo") for v in vozes_lista() if v.get("arquivo"))
    saidas_outros = {str(caminho_saida(s)).lower() for x in outros for s in (x.get("saidas") or [])}

    candidatos, mantidos = [], []
    for s in j.get("saidas") or []:
        arq = caminho_saida(s)
        if s.get("tipo", "output") == "input" and not criado_pelo_estudio(arq.name, j):
            mantidos.append(arq.name)  # nó que "mostra" um arquivo da pasta input (não é saída de verdade)
            continue
        if str(arq).lower() not in saidas_outros:
            candidatos.append(arq)
    nomes = set()
    for n in entradas_do_job(j):
        nomes.add(n)
        nomes.update(junto_com(n))
    for n in sorted(nomes - protegidos):
        if not criado_pelo_estudio(n, j) or reenviado_depois(n, j):
            if (inp / n).is_file():
                mantidos.append(n)
            continue
        candidatos.append(inp / n)
        m = re.fullmatch(r"enq_([0-9a-f]+)\.png", n)
        if m:  # poses detectadas para esse recorte
            candidatos.extend((out / "estudio_pose").glob(f"{m.group(1)}_img*.json"))
            candidatos.extend((out / "estudio_pose").glob(f"{m.group(1)}_vid*.json"))
    if j.get("preset") == "apresentador" and j.get("id"):  # trechos da voz (Chatterbox) antes de juntar
        candidatos.extend((out / "audio" / "estudio").glob(f"apres_{j['id']}_t*"))

    apagados, total, falhas = 0, 0, []
    for arq in candidatos:
        if not (_dentro(arq, inp) or _dentro(arq, out) or _dentro(arq, COMFY_DIR / "temp")):
            continue
        try:
            if arq.is_file():
                tam = arq.stat().st_size
                arq.unlink()
                apagados += 1
                total += tam
        except OSError as exc:
            falhas.append(arq.name)
            print(f"[estúdio] não consegui apagar {arq}: {exc}")
    return apagados, total, falhas, sorted(set(mantidos))


def apagar_saidas(j):
    """Só as saídas (usado pelo /api/limpar-lixeira antigo)."""
    apagados = 0
    for arq in arquivos_do_job(j):
        try:
            if arq.exists():
                arq.unlink()
                apagados += 1
        except OSError as e:
            print(f"[estúdio] não consegui apagar {arq}: {e}")
    return apagados


async def api_remover(req):
    j = achar_job(req.match_info["id"])
    if not j:
        return web.Response(status=404, text="Trabalho não encontrado.")
    if j.get("estado") in ("fila", "rodando"):
        return web.Response(status=409, text="Esse trabalho ainda está gerando. Cancele antes de remover.")
    # Cancelado mas com a tarefa ainda terminando (ex.: parando a voz do Apresentador): remove já; o que a tarefa
    # ainda gravar é apagado quando ela terminar (limpar_se_removido / concluir).
    ainda_parando = j["id"] in TAREFAS_ATIVAS
    j["lixeira"] = True
    j["removido_em"] = time.time()
    apagados, total, falhas, mantidos = apagar_trabalho(j)
    salvar()
    resp = {"ok": True, "apagados": apagados, "mb": round(total / 1048576, 2), "falhas": falhas,
            "mantidos": mantidos}
    if mantidos:
        resp["aviso"] = ("Ficaram no HD " + str(len(mantidos)) + " arquivo(s) da pasta input que não foram criados "
                         "pelo estúdio (postos lá por você ou usados em outro envio): " + ", ".join(mantidos[:5]) +
                         ("..." if len(mantidos) > 5 else ""))
    if ainda_parando:
        resp["parando"] = True
    return web.json_response(resp)


async def api_limpar_lixeira(req):
    """Apaga do HD o que foi removido do painel antes desta mudança (ficou ocupando espaço à toa)."""
    apagados, bytes_ = 0, 0
    for j in JOBS:
        if not j.get("lixeira"):
            continue
        for arq in arquivos_do_job(j):
            if arq.exists():
                bytes_ += arq.stat().st_size
        apagados += apagar_saidas(j)
    return web.json_response({"ok": True, "apagados": apagados, "mb": round(bytes_ / 1048576, 1)})


async def api_midia(req):
    j = achar_job(req.match_info["id"])
    try:
        i = int(req.match_info["i"])
    except ValueError:
        i = -1
    saidas = (j or {}).get("saidas") or []
    if not j or i < 0 or i >= len(saidas):
        raise web.HTTPNotFound(text="Arquivo não encontrado.")
    arq = caminho_saida(saidas[i])
    if not arq.is_file():
        raise web.HTTPNotFound(text="Arquivo não encontrado no HD.")
    return web.FileResponse(arq)


async def online(url, timeout=2):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                return r.status == 200
    except Exception:
        return False


async def _get_json(url, timeout=2):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                if r.status != 200:
                    return None
                return await r.json(content_type=None)
    except Exception:
        return None


def _gpu(st):
    dev = ((st or {}).get("devices") or [{}])[0]
    nome = str(dev.get("name") or "").split(" : ")[0]
    nome = nome.split(" ", 1)[1] if nome.startswith("cuda:") and " " in nome else nome
    return nome or None, dev.get("vram_total"), dev.get("vram_free")


async def api_sistema(req):
    info = {"comfy": False, "musica": await online(MUSICA), "ultimo_preset": ULTIMO_PRESET["id"],
            "musica_url": MUSICA, "musica_estado": estado_musica(),
            "comfy_ligando": "video" in LIGANDO,
            "texto": {"na_placa": TEXTO.ocupando_placa(), "fase": TEXTO.fase, "instalado": TEXTO.instalado()}}
    try:
        st = await comfy("GET", "/system_stats", timeout=3)
        nome, total, livre = _gpu(st)
        # mesmo motivo do outro lugar: a placa conta todo programa, o torch so o dele
        nv = await gpu_nvidia_smi()
        if nv and nv[1] and nv[2] is not None:
            nome, total, livre = nv[0] or nome, nv[1], nv[2]
        info.update(comfy=True, gpu=nome, vram_total=total, vram_livre=livre)
        q = await comfy("GET", "/queue", timeout=3)
        info["fila"] = len(q.get("queue_running", [])) + len(q.get("queue_pending", []))
    except Exception:
        pass
    return web.json_response(info)


def memoria_ram():
    """RAM e memória virtual (com o arquivo de paginação) pelo próprio Windows, sem instalar nada."""
    if not plataforma.WIN:
        try:
            import psutil
            gb = 1024 ** 3
            m, sw = psutil.virtual_memory(), psutil.swap_memory()
            return {"ram_total_gb": round(m.total / gb, 1), "ram_livre_gb": round(m.available / gb, 1),
                    "memoria_virtual_total_gb": round((m.total + sw.total) / gb, 1),
                    "memoria_virtual_livre_gb": round((m.available + sw.free) / gb, 1)}
        except Exception:
            return {"ram_total_gb": None, "ram_livre_gb": None}
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        st = MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            raise OSError("GlobalMemoryStatusEx falhou")
        gb = 1024 ** 3
        return {"ram_total_gb": round(st.ullTotalPhys / gb, 1), "ram_livre_gb": round(st.ullAvailPhys / gb, 1),
                "memoria_virtual_total_gb": round(st.ullTotalPageFile / gb, 1),
                "memoria_virtual_livre_gb": round(st.ullAvailPageFile / gb, 1)}
    except Exception:
        return {"ram_total_gb": None, "ram_livre_gb": None}


def disco(raiz):
    try:
        u = shutil.disk_usage(raiz)
        return round(u.free / 1024 ** 3, 1), round(u.total / 1024 ** 3, 1)
    except OSError:
        return None, None


def _disco_com_letra(pasta):
    """{"unidade": "E", "livre_gb":, "total_gb":} do disco onde a pasta mora, ou None."""
    raiz = Path(pasta).anchor
    livre, total = disco(raiz) if raiz else (None, None)
    if livre is None:
        return None
    return {"unidade": raiz[:1].upper(), "livre_gb": livre, "total_gb": total}


def contar_musicas():
    """Músicas prontas no painel (lê o jobs.json dele, só leitura). None se não der para ler."""
    try:
        m = PAINEL_JOBS.stat().st_mtime
    except OSError:
        return None
    if m != _MUSICAS["mtime"]:
        try:
            d = json.loads(PAINEL_JOBS.read_text(encoding="utf-8"))
            itens = d.values() if isinstance(d, dict) else d
            _MUSICAS["n"] = sum(1 for x in itens if isinstance(x, dict) and x.get("state") == "done"
                                and not x.get("deleted_at") and x.get("audio"))
            _MUSICAS["mtime"] = m
        except (OSError, ValueError):
            return _MUSICAS["n"]
    return _MUSICAS["n"]


# ---------------------------------------------------------------- serviços: ligar pelo Início (23/09/2026)
# "Ligar" em cada serviço desligado, "Ligar tudo" e o estado ligado | ligando | desligado | erro para a tela Início.
# Nunca liga em dobro: confere a resposta, a porta e se o processo já está subindo (aberto pelo lançador ou pelo
# painel) antes de abrir outro; e um clique a mais com o serviço "ligando" não faz nada.
LOGS_DIR = Path(os.environ["ESTUDIO_LOGS"]) if os.environ.get("ESTUDIO_LOGS") else ROOT / "outputs"
LIMITE_LOG = 20 * 1024 * 1024
LANCADOR = ROOT / "Abrir Estudio.ps1"
# Sai do COMFY_DIR, e nao da pasta do painel: ate 13/11/2026 o botao "Ligar" procurava o
# Python da ComfyUI sempre dentro do painel, mesmo com a ComfyUI apontada para outro disco.
PY_VIDEO = (COMFY_DIR.parent / "python_embeded" / "python.exe" if plataforma.WIN
            else COMFY_DIR.parent / "venv" / "bin" / "python")
# a linha que o lançador usa (se não der para ler o lançador, esta cópia vale)
ARGS_COMFY_VIDEO_PADRAO = (r"-s ComfyUI\main.py --windows-standalone-build --disable-auto-launch --listen 127.0.0.1 "
                           r"--port 8188 --fast fp16_accumulation --use-ck-attention") if plataforma.WIN else \
    f"-s {shlex.quote(str(COMFY_DIR / 'main.py'))} --disable-auto-launch --listen 127.0.0.1 --port 8188"
# o mesmo que _setup\ambiente_E.ps1 (temporários e caches no E:)
PASTAS_CACHE = (("TEMP", "temp"), ("TMP", "temp"), ("HF_HOME", "huggingface"), ("PIP_CACHE_DIR", "pip"),
                ("TORCH_HOME", "torch"), ("TRITON_CACHE_DIR", "triton"), ("CUDA_CACHE_PATH", "cuda"),
                ("UV_CACHE_DIR", "uv"), ("XDG_CACHE_HOME", "xdg"), ("GRADIO_TEMP_DIR", "temp/gradio"),
                ("MPLCONFIGDIR", "matplotlib"))
# A ComfyUI e o coracao: sempre aparece. A musica (14/11/2026) vem no pacote, na pasta
# painel_musica, e usa a MESMA ComfyUI - entao so existe UM servico a mais, o painel. Ate
# 13/11 a musica era um projeto separado (painel_yue2 + ComfyUI_YuE2 + ACE-Step, tres servicos)
# que o pacote nao levava, e a aba sumia. Agora a aba existe sempre que a pasta do painel
# existir; se faltar o motor ou o modelo, a propria aba diz o que falta (estado_musica).
TEM_MUSICA = (PAINEL_DIR / "server.py").is_file()
CHAVES_SERVICO = ("video", "painel_musica") if TEM_MUSICA else ("video",)
NOMES_SERVICO = {"video": "Imagem e vídeo (ComfyUI)", "painel_musica": "Painel de música"}
COMANDO_TESTE = {"video": "ESTUDIO_COMANDO_COMFY", "painel_musica": "ESTUDIO_COMANDO_PAINEL"}
PORTA_PAINEL_PADRAO = 8190
LIGANDO = {}        # chave -> {"desde": epoch, "pid": int | None}
ERRO_SERVICO = {}   # chave -> {"msg": texto em português, "quando": epoch}
NOS_PACOTE = {"ok": None, "erro": None, "reiniciar": False}  # o que houve na última cópia dos nós do pacote
TRAVA_SERVICO = {k: asyncio.Lock() for k in CHAVES_SERVICO}
_PROCS = {"t": 0.0, "lista": []}
_NVSMI = {"t": 0.0, "d": None}
CONFIG = DADOS / "config.json"
# "canal_dir": a pasta do canal da aba Canal automático. Vazio = a padrão do canal.py.
# É um ajuste de propósito: a esteira serve a qualquer canal, não só ao de quem a escreveu.
PREF_PADRAO = {"texto_sempre_ligada": False, "canal_dir": "", "hermes_dir": "", "pasta_ias": ""}  # economia de memória (pedido do dono): liga sozinha ao usar
try:
    AUTO_TEXTO_S = float(os.environ.get("ESTUDIO_TEXTO_AUTO_S") or 20)
except ValueError:
    AUTO_TEXTO_S = 20.0


class ErroServico(Exception):
    """Mensagem em português para a linha do serviço no Início."""


def ler_pref():
    try:
        d = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    if not isinstance(d, dict):
        d = {}
    return {**PREF_PADRAO, **{k: d[k] for k in PREF_PADRAO if isinstance(d.get(k), type(PREF_PADRAO[k]))}}


def gravar_pref(novas):
    try:
        atual = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}
    except (OSError, ValueError):
        atual = {}
    if not isinstance(atual, dict):
        atual = {}
    atual.update(novas)
    _gravar(CONFIG, atual)


def _porta_url(url):
    try:
        return int(url.split("//", 1)[-1].split("/", 1)[0].rsplit(":", 1)[1])
    except (IndexError, ValueError):
        return None


def args_comfy_video():
    """A MESMA linha de comando do lançador "Abrir Estudio.ps1" (lida dele, para as duas nunca ficarem diferentes)."""
    if not plataforma.WIN:
        return ARGS_COMFY_VIDEO_PADRAO
    try:
        m = re.search(r"^\s*\$ARGS_COMFY_VIDEO\s*=\s*'([^']+)'", LANCADOR.read_text(encoding="utf-8-sig"), re.M)
        if m:
            return m.group(1)
    except OSError:
        pass
    return ARGS_COMFY_VIDEO_PADRAO


def ambiente_e(extra=None):
    """O mesmo ambiente do _setup\\ambiente_E.ps1: temporários e caches no E: e o ffmpeg do projeto na frente do PATH.
    Tira as variáveis ESTUDIO_*/PAINEL_* (de teste): o serviço sobe igual ao que o lançador abre."""
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("ESTUDIO_", "PAINEL_"))}
    cache = ROOT / "_cache"
    for nome, sub in PASTAS_CACHE:
        p = cache / sub
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        env[nome] = str(p)
    env["HF_HUB_DISABLE_TELEMETRY"] = "1"
    # Console em UTF-8: nós que imprimem chinês/acentos (ex.: Easy-Media) quebravam a geração no cp1252.
    env["PYTHONIOENCODING"] = "utf-8"
    if plataforma.MAC:
        env["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"  # operações que o Metal ainda não tem rodam no processador
    ff = ROOT / "_ferramentas" / "ffmpeg" / "bin"
    caminho = env.get("PATH", "")
    if (ff / plataforma.exe("ffmpeg")).is_file() and str(ff).lower() not in [
            x.lower().rstrip("\\/") for x in caminho.split(os.pathsep)]:
        env["PATH"] = f"{ff}{os.pathsep}{caminho}"
    if extra:
        env.update(extra)
    return env


def ambiente_do_painel():
    """O que o painel de música precisa saber DESTA máquina, passado por variável de ambiente.

    É o contrato inteiro entre o estúdio e o painel (painel_musica\\server.py lê exatamente estas):
      PAINEL_PORTA        a porta do ESTUDIO_MUSICA_URL (a tela do estúdio abre o quadro nela)
      PAINEL_COMFY_DIR    a pasta da ComfyUI (o disco que a pessoa escolheu): input, output e models saem dela
      PAINEL_COMFY_URL    a ComfyUI que o estúdio usa (a mesma da imagem e do vídeo)
      PAINEL_ESTUDIO_URL  este estúdio (o painel pergunta /api/ocupado, pede /api/servicos/ligar e /api/texto)
      PAINEL_DADOS        <dados do estúdio>\\musica: jobs.json e uploads.json de quem usa, fora do código
      PAINEL_MOTORES      as IAs de música que o pacote traz (ias.MUSICA_IAS), na ordem
      PAINEL_FICHAS       a mesma fichas.json que o estúdio mostra
    O ambiente_e() tira todo PAINEL_* herdado antes de aplicar estas: o painel sobe sempre igual.
    """
    return {"PAINEL_PORTA": str(_porta_url(MUSICA) or PORTA_PAINEL_PADRAO),
            "PAINEL_COMFY_DIR": str(COMFY_DIR), "PAINEL_COMFY_URL": COMFY,
            "PAINEL_ESTUDIO_URL": f"http://127.0.0.1:{PORTA}",
            "PAINEL_DADOS": str(MUSICA_DADOS),
            "PAINEL_MOTORES": ",".join(ias.MUSICA_IAS),
            "PAINEL_FICHAS": str(FICHAS_JSON)}


def copiar_nos_do_pacote(motivo):
    """Garante os nós do pacote (hoje, o fz_score_guard da música) na custom_nodes da ComfyUI. Ver motor.nos_do_pacote.
    O resultado fica em NOS_PACOTE para a aba Música poder dizer se algo deu errado; nunca levanta exceção."""
    if not (COMFY_DIR / "main.py").is_file():
        return None  # sem motor não há onde copiar; a instalação do motor copia no fim
    try:
        res = motor.nos_do_pacote(COMFY_DIR, avisar=lambda m: print(m, flush=True))
    except Exception as exc:  # o nó é da música: uma falha aqui não pode impedir o estúdio de subir
        res = {"ok": False, "erro": f"erro inesperado ao copiar os nós do pacote: {exc!r}", "copiados": [],
               "em_dia": [], "reiniciar": False}
        print(f"[estudio] NOS DO PACOTE ({motivo}): {res['erro']}", flush=True)
    NOS_PACOTE.update(ok=res["ok"], erro=res.get("erro"))
    if res["ok"] and not res["copiados"]:
        print(f"[estudio] nos do pacote em dia na ComfyUI ({motivo}): {', '.join(res['em_dia']) or 'nenhum'}",
              flush=True)
    return res


async def conferir_no_carregado():
    """A ComfyUI LIGADA enxerga o nó da música? Copiar o arquivo não basta: ela só lê a custom_nodes ao subir.

    Pergunta à própria ComfyUI (/object_info/FZScoreGuard) em vez de adivinhar pela ordem em que as coisas ligaram:
    cobre o pacote atualizado com a ComfyUI no ar e a ComfyUI aberta por fora do estúdio. Com ela desligada não há o
    que reiniciar. O resultado vai para a aba Música (estado_musica: "reiniciar_comfy")."""
    antes = NOS_PACOTE.get("reiniciar")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(COMFY + "/object_info/FZScoreGuard", timeout=aiohttp.ClientTimeout(total=4)) as r:
                if r.status != 200:
                    return
                d = await r.json(content_type=None)
        NOS_PACOTE["reiniciar"] = not (isinstance(d, dict) and d.get("FZScoreGuard"))
    except Exception:
        NOS_PACOTE["reiniciar"] = False  # ComfyUI desligada: na próxima subida ela já carrega
    if NOS_PACOTE["reiniciar"] and not antes:
        print("[estudio] ATENCAO: a ComfyUI ligada ainda nao carregou o no da musica (fz_score_guard). O YuE2 so "
              "funciona depois de desligar e ligar 'Imagem e video (ComfyUI)' no Inicio.", flush=True)


async def nos_ao_iniciar():
    """Ao subir o estúdio: copia os nós do pacote (motor instalado por fora, pacote atualizado) e confere a ComfyUI."""
    await asyncio.to_thread(copiar_nos_do_pacote, "ao iniciar o estudio")
    await conferir_no_carregado()


def estado_musica():
    """O que falta para a aba Música funcionar NESTA máquina (a tela explica em vez de sumir).

    {"tem_painel", "motor_instalado", "ias": [{"id", "nome", "pronta", "gb_falta", "gb_total"}], "alguma_pronta",
     "no_ok", "no_erro", "reiniciar_comfy", "falta": None | "painel" | "motor" | "modelo"}
    "pronta" = dá para GERAR com ela (ias.musica_pronta: o YuE2 sem o arquivo do cover já conta).
    """
    try:
        cat = ias.catalogo()
        lista = []
        for mid, nome in ias.MUSICA_IAS.items():
            e = ias.estado_de(nome, cat) if cat else {}
            lista.append({"id": mid, "nome": nome, "pronta": ias.musica_pronta(mid),
                          "gb_falta": e.get("gb_falta"), "gb_total": e.get("gb_total")})
    except Exception as exc:
        print(f"[estúdio] estado da música: {exc!r}", flush=True)
        lista = []
    tem_motor = (COMFY_DIR / "main.py").is_file()
    alguma = any(i["pronta"] for i in lista)
    falta = "painel" if not TEM_MUSICA else "motor" if not tem_motor else "modelo" if not alguma else None
    return {"tem_painel": TEM_MUSICA, "motor_instalado": tem_motor, "ias": lista, "alguma_pronta": alguma,
            "no_ok": NOS_PACOTE["ok"], "no_erro": NOS_PACOTE["erro"],
            # copiamos o nó com a ComfyUI ligada: ela só enxerga depois de desligar e ligar
            "reiniciar_comfy": bool(NOS_PACOTE.get("reiniciar")), "falta": falta}


def servico_def(chave):
    """Como ligar e conferir cada serviço (a ComfyUI com a linha de comando do lançador; o painel de música com o
    Python da ComfyUI e o ambiente do ambiente_do_painel)."""
    if chave == "video":
        d = {"nome": "A ComfyUI de vídeo", "url": COMFY + "/system_stats", "porta": _porta_url(COMFY), "limite": 480,
             "cmd": f'"{PY_VIDEO}" {args_comfy_video()}' if plataforma.WIN else
             [str(PY_VIDEO), *shlex.split(args_comfy_video())],
             "cwd": COMFY_DIR.parent if plataforma.WIN else COMFY_DIR, "exe": PY_VIDEO,
             "saida": "comfy_video_stdout.log", "erro": "comfy_video_stderr.log", "log_novo": True,
             "console_escondido": True, "extra_env": None, "porta_real": 8188}
    else:  # painel_musica
        porta = _porta_url(MUSICA)
        d = {"nome": "O painel de música", "url": MUSICA + "/", "porta": porta, "limite": 120,
             # o Python da ComfyUI já tem tudo o que o painel usa (aiohttp, psutil, numpy, scipy)
             "cmd": [str(PY_VIDEO), "-s", str(PAINEL_DIR / "server.py")], "cwd": ROOT, "exe": PY_VIDEO,
             "saida": "painel_musica.log", "extra_env": ambiente_do_painel(),
             # a porta do painel é a que o estúdio manda (PAINEL_PORTA): nunca "configurado numa porta diferente"
             "porta_real": porta,
             # instância de teste do estúdio: só liga o painel de verdade se ele foi apontado para OUTRA porta
             # (na 8190 ele disputaria com o painel de quem está usando o estúdio de produção)
             "liga_no_teste": porta not in (None, PORTA_PAINEL_PADRAO)}
    teste = os.environ.get(COMANDO_TESTE[chave])
    d["teste"] = bool(teste)
    if teste:
        d.update(cmd=teste, cwd=ROOT, exe=None)
    return d


def porta_aberta(porta, timeout=0.3):
    """Tem algum programa escutando nesta porta? (conexão rápida em 127.0.0.1)"""
    import socket
    if not porta:
        return False
    try:
        with socket.create_connection(("127.0.0.1", int(porta)), timeout=timeout):
            return True
    except OSError:
        return False


def _processos_python(fresco=False):
    """(pid, criado_em, linha de comando) dos python.exe abertos. A lista fica guardada por 5 s só para a tela;
    `fresco=True` (na hora de decidir se liga) lê de novo, para não deixar de ver um processo que acabou de abrir."""
    agora = time.time()
    if not fresco and agora - _PROCS["t"] < 5:
        return _PROCS["lista"]
    lista = []
    try:
        import psutil
        for p in psutil.process_iter(["pid", "name", "create_time"]):
            if not plataforma.e_python(p.info.get("name")):
                continue
            try:
                lista.append((p.info["pid"], p.info.get("create_time") or 0.0, " ".join(p.cmdline())))
            except Exception:
                continue
    except Exception:
        pass
    _PROCS.update(t=agora, lista=lista)
    return lista


def _eh_o_servico(chave, cmd):
    c = cmd.lower().replace("/", "\\")
    if chave == "video":
        return "comfyui\\main.py" in c and "--port 8188" in c
    # o painel DESTA instalação (caminho inteiro): uma cópia de teste noutra pasta não conta como "já subindo"
    return str(PAINEL_DIR / "server.py").lower().replace("/", "\\") in c


async def processo_subindo(chave, fresco=False):
    """(pid, criado_em) se o processo do serviço já foi aberto (pelo lançador, pelo painel ou por nós), está vivo e
    ainda não abriu a porta; None se não há. Qualquer idade conta (igual ao lançador): um processo vivo que demora
    mais que o normal continua "ligando", nunca faz abrir um segundo. Na instância de teste não procura."""
    d = servico_def(chave)
    if d["teste"]:
        return None
    lista = await asyncio.to_thread(_processos_python, fresco)
    achados = [(pid, cri) for pid, cri, cmd in lista if _eh_o_servico(chave, cmd)]
    return min(achados, key=lambda x: x[1]) if achados else None


def _girar_log(arq, sempre=False):
    """Passa o log para *.log.1 (sempre, ou só se passou de 20 MB), como o lançador faz. Em uso: deixa como está."""
    try:
        if not arq.exists() or arq.stat().st_size == 0:
            return
        if not sempre and arq.stat().st_size <= LIMITE_LOG:
            return
        os.replace(arq, arq.with_name(arq.name + ".1"))
    except OSError:
        pass


def _abrir_log(arq, modo):
    try:
        return open(arq, modo)
    except OSError:  # preso por outro programa: grava num arquivo ao lado
        return open(arq.with_name(f"{arq.stem}_{int(time.time())}{arq.suffix}"), modo)


def _abrir_processo(d):
    """Abre o serviço escondido, com os logs na pasta de logs. Devolve o Popen."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    saida = LOGS_DIR / d["saida"]
    erro = LOGS_DIR / d["erro"] if d.get("erro") else None
    for a in (saida, erro):
        if a:
            _girar_log(a, sempre=bool(d.get("log_novo")))
    modo = "wb" if d.get("log_novo") else "ab"  # o lançador começa um log novo da ComfyUI de vídeo a cada início
    f_saida = _abrir_log(saida, modo)
    f_erro = _abrir_log(erro, modo) if erro else subprocess.STDOUT
    if not d.get("log_novo"):
        f_saida.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} o Estúdio ligou este serviço (botão Ligar) "
                      f"=====\n".encode("utf-8"))
        f_saida.flush()
    kw = {"cwd": str(d["cwd"]), "env": ambiente_e(d.get("extra_env")), "stdout": f_saida, "stderr": f_erro,
          "stdin": subprocess.DEVNULL}
    if not plataforma.WIN:
        return subprocess.Popen(d["cmd"], start_new_session=True, **kw)
    if d.get("console_escondido"):
        # igual ao Start-Process -WindowStyle Hidden do lançador: console próprio, janela escondida
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        kw["startupinfo"] = si
        flags = subprocess.CREATE_NEW_CONSOLE
    else:
        flags = subprocess.CREATE_NO_WINDOW
    flags |= subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        try:  # fora de qualquer "Job" do Windows: o serviço continua ligado mesmo se o estúdio fechar
            return subprocess.Popen(d["cmd"], creationflags=flags | 0x01000000, **kw)  # CREATE_BREAKAWAY_FROM_JOB
        except OSError:
            return subprocess.Popen(d["cmd"], creationflags=flags, **kw)
    finally:
        f_saida.close()
        if erro:
            f_erro.close()


def _onde_logs(d):
    arq = d.get("erro") or d["saida"]
    pasta = "outputs" if LOGS_DIR == ROOT / "outputs" else str(LOGS_DIR)
    return f"Veja o arquivo {arq} na pasta {pasta}."


def pedir_ligar(chave):
    """Marca "ligando" na hora e liga em segundo plano. Com o serviço já ligando, não faz nada (sem ligar em dobro)."""
    if chave in LIGANDO:
        return False
    ERRO_SERVICO.pop(chave, None)
    LIGANDO[chave] = {"desde": time.time(), "pid": None}
    em_segundo_plano(_ligar_servico(chave))
    return True


async def _ligar_servico(chave):
    d = servico_def(chave)
    nome = d["nome"]
    try:
        async with TRAVA_SERVICO[chave]:
            async def no_ar():
                return await online(d["url"], 3) or await asyncio.to_thread(porta_aberta, d["porta"])
            if await no_ar():
                return  # já está no ar (ou já abriu a porta): nada a fazer
            if PORTA != 8194 and not d["teste"] and not d.get("liga_no_teste"):
                raise ErroServico(f"Instância de teste: {nome[0].lower() + nome[1:]} não é ligado de verdade "
                                  f"(defina {COMANDO_TESTE[chave]} com um comando de teste).")
            if not d["teste"] and d["porta"] != d["porta_real"]:
                raise ErroServico(f"{nome} está configurado numa porta diferente ({d['porta']}); não liguei.")
            # lista de processos lida NA HORA (não a guardada da tela): vê o que o lançador ou o painel acabou de abrir
            sub = await processo_subindo(chave, fresco=True)
            proc = None
            if sub:  # já foi aberto (pelo lançador, pelo painel ou antes) e está subindo: só acompanha
                LIGANDO[chave].update(pid=sub[0], desde=min(LIGANDO[chave]["desde"], sub[1]))
            else:
                if d.get("exe") and not Path(d["exe"]).is_file():
                    if chave == "painel_musica":
                        raise ErroServico("O painel de música roda com o Python do motor (ComfyUI), que ainda não "
                                          f"está instalado neste computador (falta {d['exe']}). Instale o motor "
                                          "pelo Início e ligue a música de novo.")
                    raise ErroServico(f"{nome} não está instalado neste computador (falta {d['exe']}).")
                if await no_ar():  # confere de novo logo antes de abrir
                    return
                if chave == "video" and not d["teste"]:
                    # a ComfyUI só lê a custom_nodes ao subir: o nó da música tem que estar lá ANTES
                    await asyncio.to_thread(copiar_nos_do_pacote, "antes de ligar a ComfyUI")
                if chave == "painel_musica":
                    await asyncio.to_thread(MUSICA_DADOS.mkdir, parents=True, exist_ok=True)
                proc = await asyncio.to_thread(_abrir_processo, d)
                LIGANDO[chave]["pid"] = proc.pid
                _PROCS["t"] = 0.0
                print(f"[estúdio] ligando {nome[0].lower() + nome[1:]} (processo {proc.pid}).", flush=True)
            t0 = time.time()
            # acompanha enquanto o processo estiver vivo, sem prazo: passar do tempo normal só vira "demorando"
            # (fechar ou abrir outro por cima faria dois carregarem juntos do HD, e o log seria trocado no meio)
            while True:
                await asyncio.sleep(1.5)
                if await online(d["url"], 3):
                    print(f"[estúdio] {nome[0].lower() + nome[1:]} ligou em "
                          f"{time.time() - LIGANDO[chave]['desde']:.0f} s.", flush=True)
                    return
                if proc is not None and proc.poll() is not None:
                    raise ErroServico(f"{nome} fechou logo ao ligar (código {proc.returncode}). {_onde_logs(d)}")
                if proc is None:
                    import psutil
                    if not psutil.pid_exists(sub[0]):
                        return  # quem estava subindo fechou: volta a "desligado" (o dono pode clicar de novo)
                if not LIGANDO[chave].get("demorando") and time.time() - t0 > d["limite"]:
                    LIGANDO[chave]["demorando"] = True
                    print(f"[estúdio] {nome[0].lower() + nome[1:]} passou de {d['limite'] // 60} min sem "
                          f"responder; continuo esperando (processo {LIGANDO[chave]['pid']}).", flush=True)
    except ErroServico as exc:
        ERRO_SERVICO[chave] = {"msg": str(exc), "quando": time.time()}
        print(f"[estúdio] ligar {chave}: {exc}", flush=True)
    except Exception as exc:
        ERRO_SERVICO[chave] = {"msg": f"Não consegui ligar {nome[0].lower() + nome[1:]}: {exc}", "quando": time.time()}
        print(f"[estúdio] ligar {chave}: {exc!r}", flush=True)
    finally:
        LIGANDO.pop(chave, None)


def demora_msg(d):
    return f"Está demorando mais que o normal (o HD pode estar ocupado); continua ligando. {_onde_logs(d)}"


async def estados_servicos():
    """{chave: {"estado": "ligado"|"ligando"|"desligado"|"erro", "nome", "mensagem"?, "desde"?, "lento"?}}."""
    defs = {k: servico_def(k) for k in CHAVES_SERVICO}
    on = dict(zip(CHAVES_SERVICO, await asyncio.gather(*(online(defs[k]["url"]) for k in CHAVES_SERVICO))))
    faltam = [k for k in CHAVES_SERVICO if not on[k] and k not in LIGANDO]
    abertas = dict(zip(faltam, await asyncio.gather(*(asyncio.to_thread(porta_aberta, defs[k]["porta"])
                                                      for k in faltam)))) if faltam else {}
    res = {}
    for k in CHAVES_SERVICO:
        e = {"nome": NOMES_SERVICO[k], "porta": defs[k]["porta"]}
        if on[k] or abertas.get(k):
            ERRO_SERVICO.pop(k, None)
            e["estado"] = "ligado"
            if not on[k]:
                e["lento"] = True  # a porta está aberta, mas não respondeu em 2 s (carregando modelo, HD ocupado...)
        elif k in LIGANDO:
            e.update(estado="ligando", desde=LIGANDO[k]["desde"])
            if LIGANDO[k].get("demorando"):
                e.update(demorando=True, mensagem=demora_msg(defs[k]))
        else:
            sub = await processo_subindo(k)
            if sub:
                e.update(estado="ligando", desde=sub[1])
                if time.time() - sub[1] > defs[k]["limite"]:
                    e.update(demorando=True, mensagem=demora_msg(defs[k]))
            elif k in ERRO_SERVICO:
                e.update(estado="erro", mensagem=ERRO_SERVICO[k]["msg"])
            else:
                e["estado"] = "desligado"
        res[k] = e
    try:        # a voz e de terceiros: um defeito nela nao pode impedir os outros motores de ligar
        voz = estado_voz()
    except Exception as exc:
        print(f"[estúdio] não consegui ler o estado da voz: {exc!r}", flush=True)
        voz = None
    if voz:
        res["voz"] = voz
    return res


# ---- a VOZ como motor (14/11/2026). O VoiceStudio e um programa de terceiros: o estudio nao o
# instala nem o gerencia como os outros servicos - so sobe o motor dele sem janela (voz_studio.ligar)
# e o encerra pela porta. Quem nao tem o VoiceStudio nao ve este motor.
VOZ_LIGANDO = {}


def estado_voz():
    """O estado da voz local para a lista de motores, ou None se o VoiceStudio nao existe aqui."""
    porta = _porta_url(voz_studio.URL) or 3900
    e = {"nome": "Voz e clone de voz (VoiceStudio)", "porta": porta}
    if porta_aberta(porta):
        VOZ_LIGANDO.clear()
        e["estado"] = "ligado"
    elif VOZ_LIGANDO and time.time() - VOZ_LIGANDO.get("desde", 0) < 120:
        e.update(estado="ligando", desde=VOZ_LIGANDO["desde"])
    elif VOZ_LIGANDO.get("erro"):
        e.update(estado="erro", mensagem=VOZ_LIGANDO["erro"])
    elif voz_studio.achar_backend() is not None:
        if VOZ_LIGANDO:     # passou de 2 minutos e a porta nao abriu
            VOZ_LIGANDO.clear()
            VOZ_LIGANDO["erro"] = "O motor de voz não respondeu em 2 minutos. Tente de novo; se repetir, abra o VoiceStudio uma vez."
            e.update(estado="erro", mensagem=VOZ_LIGANDO["erro"])
        else:
            e["estado"] = "desligado"
    else:
        return None
    return e


def _encerrar_voz():
    """Encerra o motor de voz que escuta na porta dele. So mata processo que seja mesmo o VoiceStudio."""
    import psutil
    porta = _porta_url(voz_studio.URL) or 3900
    n = 0
    for c in psutil.net_connections(kind="tcp"):
        if not (c.laddr and c.laddr.port == porta and c.status == psutil.CONN_LISTEN and c.pid):
            continue
        try:
            proc = psutil.Process(c.pid)
            linha = " ".join(proc.cmdline()).lower()
            if not ("voicestudio" in linha or "omnivoice" in linha or ("backend" in linha and "main.py" in linha)):
                print(f"[estúdio] porta {porta}: não é o VoiceStudio ({linha[:120]}); não mexi.", flush=True)
                continue
            proc.terminate()
            try:
                proc.wait(8)
            except psutil.TimeoutExpired:
                proc.kill()
            n += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            print(f"[estúdio] não consegui encerrar a voz: {exc}", flush=True)
    return n


async def gpu_nvidia_smi():
    """(nome, total, livre) em bytes pelo nvidia-smi (guardado 10 s), para a tela mostrar a placa com a ComfyUI
    desligada; None se não der."""
    if time.time() - _NVSMI["t"] < 10:
        return _NVSMI["d"]
    _NVSMI["t"] = time.time()
    if plataforma.MAC:
        _NVSMI["d"] = plataforma.gpu_unificada()
        return _NVSMI["d"]
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            "nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, creationflags=plataforma.NO_WINDOW)
        out, _ = await asyncio.wait_for(proc.communicate(), 4)
        nome, total, livre = [x.strip() for x in out.decode(errors="replace").strip().splitlines()[0].split(",")]
        _NVSMI["d"] = (nome, int(float(total)) * 1024 ** 2, int(float(livre)) * 1024 ** 2)
    except Exception:
        _NVSMI["d"] = None
        if proc is not None and proc.returncode is None:
            try:
                proc.kill()
            except Exception:
                pass
    return _NVSMI["d"]


async def _seguro(coro, padrao=None, rotulo=""):
    """Uma parte do Início que falhar não derruba a tela: devolve o padrão (e registra no log)."""
    try:
        return await coro
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        print(f"[estúdio] /api/inicio ({rotulo}): {exc!r}", flush=True)
        return padrao


def _tente(fn, padrao=None, rotulo=""):
    try:
        return fn()
    except Exception as exc:
        print(f"[estúdio] /api/inicio ({rotulo}): {exc!r}", flush=True)
        return padrao


async def montar_inicio():
    st, servicos, (m_ocupada, _), recentes_m = await asyncio.gather(
        _seguro(_get_json(COMFY + "/system_stats", 2), None, "placa"),
        _seguro(estados_servicos(), {}, "serviços"),
        _seguro(musica_ocupada(), (None, None), "música ocupada"),
        _seguro(_get_json(MUSICA + "/api/recentes?n=6", 2), None, "músicas recentes"))
    try:
        if TEM_HERMES:
            servicos = {**(servicos or {}), "hermes": estado_hermes(), "telegram": estado_telegram()}
    except Exception:
        pass
    gpu, vt, vl = _gpu(st)
    # 07/11/2026, MEDIDO: o numero da ComfyUI vem do torch e NAO conta o que os outros
    # programas usam na placa (desktop, navegador) - estava 0,54 GB otimista. Quem manda e a
    # PLACA. Antes isto so era consultado com a ComfyUI desligada; agora sempre, porque o
    # cartao diz "AO VIVO" e a conta serve para decidir se um modelo cabe.
    nv = await _seguro(gpu_nvidia_smi(), None, "nvidia-smi")
    if nv and nv[1] and nv[2] is not None:
        gpu, vt, vl = nv[0] or gpu, nv[1], nv[2]
    e_livre, e_total = _tente(lambda: disco(ROOT.anchor or "E:\\") if plataforma.WIN else disco(ROOT),
                              (None, None), "disco do estúdio")
    c_livre, _ = _tente(lambda: disco("C:\\") if plataforma.WIN else disco(Path.home()), (None, None), "disco do usuário")
    gb = 1024 ** 3
    ligado = {k: (servicos.get(k) or {}).get("estado") == "ligado" for k in CHAVES_SERVICO}
    sistema = {"gpu": gpu, "vram_total": vt, "vram_livre": vl,
               "vram_total_gb": round(vt / gb, 1) if vt else None, "vram_livre_gb": round(vl / gb, 1) if vl else None,
               **_tente(memoria_ram, {}, "RAM"), "disco_e_livre_gb": e_livre, "disco_e_total_gb": e_total,
               "disco_c_livre_gb": c_livre,
               # 14/11/2026: a tela dizia "Disco E: (projeto)" com os numeros do disco do
               # PAINEL. Agora cada disco vai com a sua letra: o das IAs e o do painel.
               "disco_ias": _disco_com_letra(COMFY_DIR), "disco_painel": _disco_com_letra(ROOT),
               # (compatível com a tela antiga: só ligado sim/não; o estado completo vai em "servicos")
               # .get com padrao: sem os projetos de musica, CHAVES_SERVICO so tem "video" e as
               # outras chaves nem existem. Com indice direto isso virava KeyError e derrubava
               # a tela INTEIRA do Inicio -- a pessoa que acabou de instalar via "Sem resposta
               # do estudio" e "Placa de video --" na primeira tela (achado em 02/11/2026).
               # SO as chaves que existem nesta instalacao. Com `False` fixo, o pacote do GitHub
               # (que nao leva os projetos de musica) mostrava "Painel de musica - desligado -
               # Ligar" para servicos que nem existem la. A tela esconde o que nao tem chave.
               "servicos": {"video": st is not None or ligado.get("video", False),
                            **{k: ligado.get(k, False) for k in ("painel_musica",) if k in CHAVES_SERVICO}}}
    ativos = _tente(trabalhos_ativos, [], "fila")
    rodando = next((j for j in ativos if j.get("estado") == "rodando"), None)
    visiveis = [j for j in JOBS if isinstance(j, dict) and not j.get("lixeira")]
    prontos = [j for j in visiveis if j.get("estado") == "concluido" and j.get("saidas")]
    prontos.sort(key=lambda j: j.get("fim") or j.get("criado") or 0, reverse=True)
    recentes = []
    for j in prontos[:8]:
        p = _tente(lambda: publico(j), None, "recente")
        if p:
            recentes.append(p)
    return {
        "sistema": sistema,
        "servicos": servicos,
        "fila": {"rodando": _tente(lambda: publico(rodando), None, "rodando") if rodando else None,
                 "na_fila": sum(1 for j in ativos if j.get("estado") == "fila"), "musica_ocupada": m_ocupada},
        "contagem": {"imagens": sum(1 for j in prontos if j.get("aba") == "imagem"),
                     "videos": sum(1 for j in prontos if j.get("aba") == "video"),
                     "musicas": _tente(contar_musicas, None, "músicas")},
        "recentes": recentes,
        "musicas_recentes": recentes_m if isinstance(recentes_m, list) else [],
        "liberar_memoria_min": LIBERAR_MIN, "memoria_liberada": ATIVIDADE["liberado"],
        "texto": _tente(TEXTO.estado_publico, None, "IA de texto"),
        "preferencias": _tente(ler_pref, dict(PREF_PADRAO), "preferências"),
        "tem_musica": TEM_MUSICA,  # só é falso se a pasta painel_musica não existir (aí a aba some da tela)
        # o endereço do painel (a tela abre o quadro nele) e o que falta para a música funcionar nesta máquina
        "musica_url": MUSICA, "musica_estado": _tente(estado_musica, None, "estado da música"),
        "agora": time.time(),
    }


async def api_inicio(req):
    try:
        return web.json_response(await montar_inicio())
    except Exception as exc:  # nunca deixa a tela Início sem resposta: devolve o mínimo, e a tela tenta de novo
        print(f"[estúdio] /api/inicio: {exc!r}", flush=True)
        return web.json_response({"sistema": {"servicos": {}}, "servicos": {}, "fila": {}, "contagem": {},
                                  "recentes": [], "musicas_recentes": [], "incompleto": True, "agora": time.time()})


# ---------------------------------------------------------------- Hermes (IA que conversa) — liga/desliga pelo Início
# O Hermes e um projeto SEPARADO (agente de conversa). Quem nao tem, nao ve o cartao:
# o Inicio so mostra Hermes e Telegram se esta pasta existir. Ver TEM_HERMES, logo abaixo.
HERMES_DIR = Path(os.environ.get("ESTUDIO_HERMES_DIR") or ler_pref().get("hermes_dir")
                  or Path(__file__).resolve().parent.parent.parent / "Hermes Agent")
HERMES_PORTA = 9119
TEM_HERMES = HERMES_DIR.is_dir()  # sem a pasta, o cartao nem aparece no Inicio
HERMES_LIGANDO = {"desde": 0.0}
TELEGRAM_LIGANDO = {"desde": 0.0}  # Telegram do Hermes (gateway de mensagens)


def estado_hermes():
    """Estado do Hermes para a linha de Serviços do Início (ligado | ligando | desligado)."""
    if porta_aberta(HERMES_PORTA):
        return {"estado": "ligado", "porta": HERMES_PORTA, "url": f"http://127.0.0.1:{HERMES_PORTA}/?profile=default"}
    if HERMES_LIGANDO["desde"] and time.time() - HERMES_LIGANDO["desde"] < 40:
        return {"estado": "ligando", "desde": HERMES_LIGANDO["desde"], "porta": HERMES_PORTA}
    return {"estado": "desligado", "porta": HERMES_PORTA}


def estado_telegram():
    """Telegram do Hermes (o 'gateway' de mensagens): ligado | ligando | desligado."""
    if any(p.get("cmd", "").lower().find("gateway") >= 0 and "hermes" in p.get("cmd", "").lower()
           for p in _processos_hermes()):
        return {"estado": "ligado"}
    if TELEGRAM_LIGANDO["desde"] and time.time() - TELEGRAM_LIGANDO["desde"] < 60:
        return {"estado": "ligando", "desde": TELEGRAM_LIGANDO["desde"]}
    return {"estado": "desligado"}


def _processos_hermes():
    """lista os processos do Hermes (para saber se o gateway está no ar)"""
    if not plataforma.WIN:
        try:
            import psutil
            return [{"cmd": " ".join(p.info.get("cmdline") or [])} for p in psutil.process_iter(["name", "cmdline"])
                    if p.info.get("name") == "hermes"]
        except Exception:
            return []
    try:
        r = subprocess.run(["wmic", "process", "where", "name='hermes.exe'", "get", "CommandLine"],
                           capture_output=True, text=True, errors="replace", timeout=15,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return [{"cmd": l.strip()} for l in r.stdout.splitlines() if l.strip()]
    except (OSError, subprocess.SubprocessError):
        return []


def _processos_hermes_vivos(palavra):
    import psutil
    return [p for p in psutil.process_iter(["name", "cmdline"])
            if p.info.get("name") == "hermes" and palavra in " ".join(p.info.get("cmdline") or [])]


def telegram_ligar():
    exe = HERMES_DIR / "bin" / plataforma.exe("hermes")
    if not exe.exists():
        raise ErroServico("Não achei o hermes em " + str(exe))
    log = HERMES_DIR / "gateway.log"
    with open(log, "ab") as f:
        subprocess.Popen([str(exe), "gateway", "run"], cwd=str(HERMES_DIR), stdout=f, stderr=f,
                         **plataforma.sem_janela())
    TELEGRAM_LIGANDO["desde"] = time.time()


def telegram_desligar():
    TELEGRAM_LIGANDO["desde"] = 0.0
    exe = HERMES_DIR / "bin" / plataforma.exe("hermes")
    try:
        subprocess.run([str(exe), "gateway", "stop"], cwd=str(HERMES_DIR), timeout=30,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        pass
    if not plataforma.WIN:
        for p in _processos_hermes_vivos("gateway"):
            p.kill()
        return
    subprocess.run(["taskkill", "/F", "/FI", "IMAGENAME eq hermes.exe", "/FI", "WINDOWTITLE eq *gateway*"],
                   capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def hermes_ligar():
    exe = HERMES_DIR / "bin" / plataforma.exe("hermes")
    if not exe.exists():
        raise ErroServico("Não achei o hermes em " + str(exe))
    subprocess.Popen([str(exe), "dashboard"], cwd=str(HERMES_DIR), **plataforma.sem_janela())
    HERMES_LIGANDO["desde"] = time.time()


def hermes_desligar():
    HERMES_LIGANDO["desde"] = 0.0
    bat = HERMES_DIR / "Desligar Hermes.bat"
    if not plataforma.WIN:
        for p in _processos_hermes_vivos("dashboard"):
            p.kill()
    elif bat.exists():
        try:
            subprocess.run(["cmd", "/c", str(bat)], cwd=str(HERMES_DIR),
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=30)
        except (OSError, subprocess.SubprocessError):
            pass


async def api_servicos_ligar(req):
    """POST {"servico": "video"|"musica"|"painel"|"texto"|"hermes"|"tudo"}: liga o que estiver desligado e responde na
    hora. "video" é a ComfyUI (o painel de música também pede por aqui quando precisa dela); "musica" liga o painel
    de música E a ComfyUI (a música usa a mesma da imagem e do vídeo); "painel" só o painel; "tudo" = os dois."""
    try:
        b = await req.json()
    except ValueError:
        b = {}
    alvo = b.get("servico") if isinstance(b, dict) else None
    if alvo in ("hermes", "telegram") and not TEM_HERMES:
        # projeto separado: quem nao tem a pasta nao tem o servico, nem pela rota
        return web.json_response(
            {"erro": "O Hermes nao esta instalado nesta maquina."}, status=404)
    if alvo == "telegram":
        try:
            await asyncio.to_thread(telegram_ligar)
        except ErroServico as e:
            return web.json_response({"erro": str(e)}, status=500)
        return web.json_response({"ok": True, "ligando": ["telegram"], "mensagem": "Ligando o Telegram do Hermes…",
                                  "servicos": {**(await estados_servicos()), "hermes": estado_hermes(), "telegram": estado_telegram()},
                                  "texto": TEXTO.estado_simples()})
    if alvo == "hermes":
        try:
            await asyncio.to_thread(hermes_ligar)
        except ErroServico as e:
            return web.json_response({"erro": str(e)}, status=500)
        return web.json_response({"ok": True, "ligando": ["hermes"], "mensagem": "Ligando o Hermes…",
                                  "servicos": {**(await estados_servicos()), "hermes": estado_hermes(), "telegram": estado_telegram()},
                                  "texto": TEXTO.estado_simples()})
    if alvo == "voz":
        if estado_voz() is None:
            return web.json_response({"erro": "O VoiceStudio não está instalado nesta máquina. Marque "
                                              "\"Voz e clone de voz\" em IAs aprovadas, na tela inicial."}, status=404)
        ligando = []
        if not porta_aberta(_porta_url(voz_studio.URL) or 3900):
            ok, recado = await asyncio.to_thread(voz_studio.ligar, VOZ_SAIDA)
            if not ok:
                VOZ_LIGANDO.clear()
                VOZ_LIGANDO["erro"] = recado
                return web.json_response({"erro": recado}, status=400)
            VOZ_LIGANDO.clear()
            VOZ_LIGANDO["desde"] = time.time()
            ligando = ["voz"]
        return web.json_response({"ok": True, "ligando": ligando, "servicos": await estados_servicos(),
                                  "texto": TEXTO.estado_simples()})
    # "musica" = o painel + a ComfyUI: desde 14/11/2026 a música gera na MESMA ComfyUI da imagem e do vídeo, então
    # ligar só o painel deixaria a primeira música esperando alguém ligar a ComfyUI.
    grupos = {"video": ("video",), "musica": ("video", "painel_musica"), "painel": ("painel_musica",),
              "texto": ("texto",), "tudo": ("video", "painel_musica")}
    if not isinstance(alvo, str) or alvo not in grupos:
        return web.json_response({"erro": "Serviço desconhecido. Use video, musica, painel, texto ou tudo."}, status=400)
    estados = await estados_servicos()
    ligou = []
    precisa = lambda k: (estados.get(k) or {}).get("estado") in ("desligado", "erro")  # noqa: E731
    for g in grupos[alvo]:
        if g in ("video", "painel_musica"):
            # sem a pasta do painel o serviço nem existe (CHAVES_SERVICO): não tenta ligar o que não há
            if g in CHAVES_SERVICO and precisa(g) and pedir_ligar(g):
                ligou.append(g)
        elif g == "texto":
            s = TEXTO.estado_simples()
            if s["estado"] in ("em espera", "erro") and s.get("pode_ligar") and texto_pode_ligar():
                TEXTO.iniciar_ligar()
                ligou.append("texto")
    # Por que a tentativa ANTERIOR falhou (ex.: "o motor não está instalado"). O pedido de agora apaga o erro e
    # marca "ligando" na hora, então sem isto quem pede de tempos em tempos (o painel de música, a cada 30 s com
    # música na fila) nunca chegaria a ver o motivo.
    anteriores = {k: e.get("mensagem") for k, e in estados.items()
                  if isinstance(e, dict) and e.get("estado") == "erro" and e.get("mensagem")}
    return web.json_response({"ok": True, "ligando": ligou,
                              "mensagem": "Ligando…" if ligou else "Já estava tudo ligado (ou ligando).",
                              "erro_anterior": anteriores,
                              "servicos": await estados_servicos(), "texto": TEXTO.estado_simples()})


def texto_pode_ligar():
    """A instância de TESTE só liga a IA de texto numa porta de teste (nunca na 8180/8181 da produção)."""
    return PORTA == 8194 or bool(os.environ.get("ESTUDIO_TEXTO_PORTA_CPU"))


async def api_texto_ligar(req):
    s = TEXTO.estado_simples()
    falta = TEXTO.falta_processador()
    if falta:
        return web.json_response({"erro": "A IA de texto não está instalada por completo. Falta: " + "; ".join(falta),
                                  "texto": s}, status=503)
    if not texto_pode_ligar():
        return web.json_response({"erro": "Instância de teste: defina ESTUDIO_TEXTO_PORTA_CPU com uma porta de teste.",
                                  "texto": s}, status=409)
    TEXTO.iniciar_ligar()
    return web.json_response({"ok": True, "mensagem": "Ligando a IA de texto no processador…",
                              "texto": TEXTO.estado_simples()})


def _pastas_do_projeto():
    """As pastas que sao NOSSAS nesta instalacao, em minusculo.

    Serve para o "Desligar" so matar o que e do projeto. Antes isto era um teste pelo NOME
    da pasta ("_projetos" e "comfyui mcp") - os nomes da MINHA maquina. Na maquina de quem
    baixasse, o teste nunca batia e o Desligar nao desligava nada, sem dizer por que.
    Comparar pelo CAMINHO de verdade funciona em qualquer pasta, com qualquer nome de
    usuario, em qualquer disco - e ainda e mais preciso que comparar nome.
    """
    pastas = {str(AQUI.parent).lower()}
    try:
        pastas.add(str(COMFY_DIR.parent).lower())   # a ComfyUI pode estar noutro disco
    except Exception:
        pass
    return {p for p in pastas if p}


def _e_nosso(linha_de_comando):
    linha = (linha_de_comando or "").lower()
    return any(p in linha for p in _pastas_do_projeto())


def _encerrar_na_porta(porta):
    """Encerra o programa DO PROJETO que escuta na porta. Nunca mexe em outros."""
    import psutil
    n = 0
    for c in psutil.net_connections(kind="tcp"):
        if not (c.laddr and c.laddr.port == porta and c.status == psutil.CONN_LISTEN and c.pid):
            continue
        try:
            proc = psutil.Process(c.pid)
            linha = " ".join(proc.cmdline()).lower()
            if not _e_nosso(linha):
                continue
            alvos = [proc]
            for a in alvos:
                a.terminate()
            _, vivos = psutil.wait_procs(alvos, timeout=15)
            for a in vivos:
                a.kill()
            n += 1
        except (psutil.Error, OSError):
            pass
    return n


async def _fila_vazia(url):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url + "/queue", timeout=aiohttp.ClientTimeout(total=3)) as r:
                q = await r.json()
        return not q.get("queue_running") and not q.get("queue_pending")
    except Exception:
        return True  # fora do ar = nada rodando


async def api_servicos_desligar(req):
    """POST {"servico": "video"|"musica"|"painel"|"texto"|"tudo"}: desliga para liberar memória.
    Recusa (com aviso em português) se houver geração em andamento. "video" é a ComfyUI, que também gera a música:
    com música gerando ou na fila ela não desliga. "musica" e "painel" desligam só o painel de música (quem segura a
    memória da placa é a ComfyUI). "tudo" = ComfyUI + texto (o painel e a própria página continuam, são leves)."""
    try:
        b = await req.json()
    except ValueError:
        b = {}
    alvo = b.get("servico") if isinstance(b, dict) else None
    if FALTA_PSUTIL and alvo != "texto":
        return web.json_response({"erro": "Esta instalação é anterior a 14/11/2026 e veio sem uma peça que o "
                                          "Desligar usa. Baixe o ForjaStudio-Instalador.exe de novo e instale por "
                                          "cima: as IAs que você já baixou continuam no lugar."}, status=500)
    if alvo in ("hermes", "telegram") and not TEM_HERMES:
        return web.json_response(
            {"erro": "O Hermes nao esta instalado nesta maquina."}, status=404)
    if alvo == "telegram":
        await asyncio.to_thread(telegram_desligar)
        return web.json_response({"ok": True, "mensagem": "Telegram desligado.",
                                  "servicos": {**(await estados_servicos()), "hermes": estado_hermes(), "telegram": estado_telegram()},
                                  "texto": TEXTO.estado_simples()})
    if alvo == "hermes":
        await asyncio.to_thread(hermes_desligar)
        return web.json_response({"ok": True, "mensagem": "Hermes desligado.",
                                  "servicos": {**(await estados_servicos()), "hermes": estado_hermes(), "telegram": estado_telegram()},
                                  "texto": TEXTO.estado_simples()})
    if alvo == "voz":
        VOZ_LIGANDO.clear()
        n = await asyncio.to_thread(_encerrar_voz)
        return web.json_response({"ok": True, "mensagem": "Voz local desligada." if n else "A voz já estava desligada.",
                                  "servicos": await estados_servicos(), "texto": TEXTO.estado_simples()})
    grupos = {"video": ["video"], "musica": ["painel_musica"], "painel": ["painel_musica"], "texto": ["texto"],
              "tudo": ["video", "texto"]}
    if alvo not in grupos:
        return web.json_response({"erro": "Serviço desconhecido."}, status=400)
    if PORTA != 8194:
        return web.json_response({"erro": "Instância de teste: não desliga serviços de verdade."}, status=409)
    if "video" in grupos[alvo] or "painel_musica" in grupos[alvo]:
        # A música gera na ComfyUI: desligar a ComfyUI (ou o painel, que acompanha a geração) com música gerando
        # ou esperando a vez perderia a música - e o painel pediria a ComfyUI de volta logo em seguida.
        ocupada, _motivo = await musica_ocupada()
        if ocupada or PAINEL_INFO.get("na_fila"):
            return web.json_response({"erro": "Tem música gerando ou na fila. Espere terminar (ou cancele a música "
                                              "na aba Música) para desligar."}, status=409)
    if "video" in grupos[alvo]:
        visiveis = [j for j in JOBS if not j.get("lixeira")]
        if any(j.get("estado") in ("rodando", "fila") for j in visiveis) or not await _fila_vazia(COMFY):
            return web.json_response({"erro": "Tem imagem ou vídeo gerando ou na fila. Espere terminar para desligar."},
                                     status=409)
    feitos = []
    for k in grupos[alvo]:
        if k != "texto" and k not in CHAVES_SERVICO:
            continue  # sem a pasta do painel de música, esse serviço nem existe
        if k == "texto":
            await TEXTO.desligar()
            feitos.append("IA de texto")
            continue
        porta = servico_def(k)["porta_real"]
        LIGANDO.pop(k, None)
        ERRO_SERVICO.pop(k, None)
        n = await asyncio.to_thread(_encerrar_na_porta, porta)
        if n:
            feitos.append(NOMES_SERVICO[k])
    msg = ("Desligado: " + ", ".join(feitos) + ".") if feitos else "Já estava desligado."
    return web.json_response({"ok": True, "mensagem": msg, "servicos": await estados_servicos(),
                              "texto": TEXTO.estado_simples()})


# ============================================================== REPARAR (14/11/2026)
# Um botao para quando "as IAs nao respondem". Faz o que se fazia a mao: encerra os motores que
# estavam ligados, reinicia o PROPRIO painel e religa os mesmos motores. O painel renasce por
# um ajudante solto (que espera a porta vagar), e a lista do que religar atravessa o reinicio
# num arquivo pequeno. Motor desligado continua desligado; nada no disco e apagado.
REPARO_PENDENTE = AQUI / "reparo_pendente.json"


async def _em_uso_agora():
    """O que um reparo interromperia, em frases. Lista vazia = nada se perde."""
    em_uso = []
    visiveis = [j for j in JOBS if not j.get("lixeira")]
    if any(j.get("estado") in ("rodando", "fila") for j in visiveis) or not await _fila_vazia(COMFY):
        em_uso.append("Imagem ou vídeo gerando ou na fila")
    try:
        ocupada, _motivo = await musica_ocupada()
        if ocupada or PAINEL_INFO.get("na_fila"):
            em_uso.append("Música gerando ou na fila")
    except Exception:
        pass
    try:
        if (ias.progresso() or {}).get("baixando"):
            em_uso.append("Download de IA em andamento (ele continua de onde parou)")
    except Exception:
        pass
    return em_uso


async def _renascer():
    """Sobe um painel novo por um ajudante solto e encerra este."""
    await asyncio.sleep(0.8)        # da tempo de a resposta do pedido sair
    criar = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    codigo = ("import subprocess,sys,time\n"
              "time.sleep(2.5)\n"
              "try:\n"
              "    o=open(sys.argv[3],'a',encoding='utf-8',errors='replace')\n"
              "except OSError:\n"
              "    o=subprocess.DEVNULL\n"
              "subprocess.Popen([sys.executable,'-s',sys.argv[1]],cwd=sys.argv[2],creationflags=int(sys.argv[4]),"
              "stdin=subprocess.DEVNULL,stdout=o,stderr=subprocess.STDOUT)\n")
    subprocess.Popen([sys.executable, "-c", codigo, str(AQUI / "server.py"), os.getcwd(),
                      str(AQUI / "servidor_saida.txt"), str(criar)],
                     creationflags=criar, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, close_fds=True)
    try:
        TEXTO.parar_tudo()
    except Exception:
        pass
    os._exit(0)


async def api_reparar(req):
    """POST {"mesmo_assim": bool}: reinicia o painel e os motores que estavam ligados."""
    try:
        b = await req.json()
    except ValueError:
        b = {}
    b = b if isinstance(b, dict) else {}
    em_uso = await _em_uso_agora()
    if em_uso and not b.get("mesmo_assim"):
        # avisa, nao impede: a tela mostra a lista e a pessoa decide
        return web.json_response({"erro": "Tem trabalho em andamento que o reparo interrompe.",
                                  "em_uso": em_uso}, status=409)
    estados = await estados_servicos()
    de_verdade = PORTA == 8194 and not FALTA_PSUTIL     # instancia de teste nao mexe nos motores reais
    religar, passos = [], []
    for k in ("video", "painel_musica", "voz"):
        e = estados.get(k)
        if not isinstance(e, dict):
            continue
        antes = e.get("estado")
        if antes == "desligado" or not de_verdade:
            passos.append({"motor": k, "nome": e.get("nome"), "antes": antes, "acao": "nao mexi"})
            continue
        if k == "voz":
            VOZ_LIGANDO.clear()
            await asyncio.to_thread(_encerrar_voz)
        else:
            LIGANDO.pop(k, None)
            ERRO_SERVICO.pop(k, None)
            await asyncio.to_thread(_encerrar_na_porta, servico_def(k)["porta_real"])
        religar.append(k)
        passos.append({"motor": k, "nome": e.get("nome"), "antes": antes, "acao": "reiniciar"})
    try:
        if de_verdade and TEXTO.estado_simples().get("estado") != "em espera":
            await TEXTO.desligar()      # ela liga sozinha no proximo pedido de texto
            passos.append({"motor": "texto", "nome": "IA de texto", "antes": "ligada", "acao": "desligar"})
    except Exception as exc:
        print(f"[reparo] IA de texto: {exc!r}", flush=True)
    try:
        REPARO_PENDENTE.write_text(json.dumps({"religar": religar, "quando": time.time()}), encoding="utf-8")
    except OSError as exc:
        print(f"[reparo] não gravei a lista do que religar: {exc}", flush=True)
    print(f"[reparo] reiniciando o painel; religar depois: {religar}", flush=True)
    em_segundo_plano(_renascer())
    return web.json_response({"ok": True, "religar": religar, "passos": passos,
                              "mensagem": "Reparando: o painel reinicia e volta sozinho."})


async def religar_depois_do_reparo():
    """Na subida: se o painel renasceu de um reparo, religa os motores que estavam ligados."""
    try:
        await asyncio.sleep(1.5)
        if not REPARO_PENDENTE.is_file():
            return
        try:
            d = json.loads(REPARO_PENDENTE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        try:
            REPARO_PENDENTE.unlink()
        except OSError:
            pass
        if not isinstance(d, dict) or time.time() - float(d.get("quando") or 0) > 180:
            return      # pedido velho (o painel nao voltou na hora): nao liga nada de surpresa
        for k in d.get("religar") or []:
            if k == "voz":
                ok, recado = await asyncio.to_thread(voz_studio.ligar, VOZ_SAIDA)
                VOZ_LIGANDO.clear()
                VOZ_LIGANDO.update({"desde": time.time()} if ok else {"erro": recado})
            elif k in CHAVES_SERVICO:
                pedir_ligar(k)
        print(f"[reparo] painel de volta; religando: {d.get('religar')}", flush=True)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        print(f"[reparo] religar depois do reparo: {exc!r}", flush=True)


async def api_texto_desligar(req):
    frase = await TEXTO.desligar()
    return web.json_response({"ok": True, "mensagem": frase, "texto": TEXTO.estado_simples()})


async def api_preferencias(req):
    if req.method == "POST":
        try:
            b = await req.json()
        except ValueError:
            b = None
        if not isinstance(b, dict):
            return web.json_response({"erro": "Pedido inválido."}, status=400)
        novas = {k: b[k] for k in PREF_PADRAO if k in b}
        ruins = [k for k, v in novas.items() if not isinstance(v, type(PREF_PADRAO[k]))]
        if ruins or not novas:
            return web.json_response({"erro": "Preferência inválida."}, status=400)
        try:
            await asyncio.to_thread(gravar_pref, novas)
        except OSError as exc:
            return web.json_response({"erro": f"Não consegui gravar a preferência: {exc}"}, status=500)
    return web.json_response(ler_pref())


async def ligar_texto_ao_iniciar():
    """Preferência 'Deixar sempre ligada ao abrir o estúdio': liga a IA de texto no processador ~20 s depois de
    iniciar, em segundo plano (não atrasa o resto)."""
    try:
        await asyncio.sleep(AUTO_TEXTO_S)
        if not ler_pref().get("texto_sempre_ligada"):
            return
        if TEXTO.falta_processador() or not texto_pode_ligar():
            print("[texto] 'sempre ligada': não liguei (IA de texto incompleta ou instância de teste sem porta "
                  "de teste).", flush=True)
            return
        if TEXTO.estado_simples()["estado"] in ("em espera", "erro"):
            print("[texto] preferência 'sempre ligada': ligando a IA de texto no processador.", flush=True)
            TEXTO.iniciar_ligar()
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        print(f"[texto] ligar ao iniciar: {exc!r}", flush=True)


async def api_ocupado(req):
    """[C] O painel de música pergunta isto antes de usar a placa. Trabalho esperando a vez NÃO conta como ocupado
    (evita impasse), mas vai em 'esperando_desde' (hora do pedido mais antigo do estúdio que espera a placa): o
    painel pode ceder a vez a ele se a música dele foi pedida depois (ordem dos pedidos)."""
    visiveis = [j for j in JOBS if not j.get("lixeira")]
    esperando = [j.get("criado") or 0 for j in visiveis
                 if j.get("estado") == "fila" and not j.get("prompt_id") and j["id"] in TAREFAS_ATIVAS]
    ed = min(esperando) if esperando else None

    def resp(ocupado, motivo, tipo=None):
        return web.json_response({"ocupado": ocupado, "motivo": motivo, "esperando_desde": ed, "tipo": tipo})

    if TEXTO.ocupando_placa():  # IA de texto na placa (curta: descarrega sozinha no fim do pedido)
        return resp(True, TEXTO.motivo_ocupado(), "texto")
    rodando = [j for j in visiveis if j.get("estado") == "rodando"]
    if rodando:
        return resp(True, f"Estúdio gerando: {info_ia(rodando[0])['nome']}")
    enviados = [j for j in visiveis if j.get("estado") == "fila" and j.get("prompt_id")
                and j["id"] not in TAREFAS_ATIVAS]
    if enviados:
        n = len(enviados)
        return resp(True, f"Estúdio com {n} trabalho{'s' if n > 1 else ''} na fila da placa de vídeo")
    if RESERVA["ate"] > time.time():
        return resp(True, "O estúdio está mandando um trabalho para a placa de vídeo")
    try:
        q = await comfy("GET", "/queue", timeout=1.5)
        n = len(q.get("queue_running", [])) + len(q.get("queue_pending", []))
        if n:
            return resp(True, f"A ComfyUI de vídeo está gerando ({n} na fila)")
    except Exception:
        pass
    return resp(False, "Livre")


async def api_liberar_memoria(req):
    ok, motivo = await liberar_memoria()
    try:
        txt = await TEXTO.liberar()  # também tira a IA de texto da placa e fecha os servidores dela
    except Exception as exc:
        txt = f"IA de texto: {exc}"
    if txt:
        motivo = f"{motivo} {txt}".strip()
    return web.json_response({"ok": ok, "motivo": motivo})


# ---------------------------------------------------------------- IA de texto (llama.cpp) — regra da placa
TORCH_CARREGADO = 768 * 1024 ** 2  # ComfyUI com mais que isso reservado na placa = tem modelo carregado


async def placa_ocupada_para_texto(papel):
    """Motivo (texto em português) se a placa NÃO pode receber a IA de texto agora; None se está livre.
    Ocupada = geração/treino em andamento (estúdio, ComfyUI, painel de música) ou modelo carregado na ComfyUI.
    Motivo começando com 'VRAM:' = nada gerando, mas falta memória livre para esse modelo.
    (A ComfyUI é uma só desde 14/11/2026: a música gera nela, então a fila dela já conta a música.)"""
    if trabalhos_ativos() or TAREFAS_ATIVAS:
        return "o estúdio tem trabalho gerando ou na fila"
    if RESERVA["ate"] > time.time():
        return "o estúdio está mandando um trabalho para a placa"
    q_v, st_v, (m_ocup, m_motivo) = await asyncio.gather(
        _get_json(COMFY + "/queue", 2), _get_json(COMFY + "/system_stats", 2), musica_ocupada())
    if m_ocup:  # antes da fila: o motivo do painel diz QUAL música, a fila só diz "gerando"
        return (m_motivo or "o painel de música está usando a placa").rstrip(".")
    if q_v and (q_v.get("queue_running") or q_v.get("queue_pending")):
        return "a ComfyUI está gerando"
    dev = ((st_v or {}).get("devices") or [{}])[0]
    if (dev.get("torch_vram_total") or 0) > TORCH_CARREGADO:
        return "a ComfyUI está com um modelo carregado na placa"
    _, livre = await texto.vram_mib()
    precisa = texto.MODELOS[papel]["vram_mib"]
    if livre is not None and livre < precisa:
        return (f"VRAM: a placa só tem {livre / 1024:.1f} GB livres e o {texto.MODELOS[papel]['nome']} precisa de "
                f"~{precisa / 1024:.1f} GB.")
    return None


# as duas formas do endereco do painel de musica (o navegador trata 127.0.0.1 e localhost como origens diferentes)
ORIGENS_TEXTO = {MUSICA, MUSICA.replace("//127.0.0.1", "//localhost"), MUSICA.replace("//localhost", "//127.0.0.1")}


async def api_texto(req):
    """POST /api/texto {"tarefa", "entrada", "contexto"?, "modelo"?} -> {"texto", "modelo", "onde", "segundos", ...}.
    Placa livre: roda na placa (ocupado=true enquanto roda) e descarrega no fim; ocupada: 9B no processador."""
    try:
        b = await req.json()
    except ValueError:
        return web.json_response({"erro": "Pedido inválido (esperava JSON)."}, status=400)
    if not isinstance(b, dict):
        return web.json_response({"erro": "Pedido inválido."}, status=400)
    ctx = b.get("contexto") if isinstance(b.get("contexto"), dict) else {}
    pid = ctx.get("preset")
    try:
        res = await TEXTO.pedir(b.get("tarefa"), b.get("entrada"), ctx, b.get("modelo"), placa_ocupada_para_texto,
                                ficha=ficha(pid) if pid else None, fichas_ias=fichas().get("ias"),
                                pasta_input=COMFY_DIR / "input")
        return web.json_response(res)
    except texto.ErroTexto as exc:
        return web.json_response({"erro": str(exc)}, status=exc.status)
    except Exception as exc:
        print(f"[estúdio] /api/texto: {exc!r}", flush=True)
        return web.json_response({"erro": f"A IA de texto teve um problema: {exc}"}, status=500)


async def api_texto_estado(req):
    return web.json_response(TEXTO.estado_publico())


async def api_texto_opcoes(req):
    """Pré-conferência (CORS) do navegador para o POST do painel de música."""
    origem = req.headers.get("Origin")
    h = {"Access-Control-Allow-Methods": "GET, POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type",
         "Access-Control-Max-Age": "600"}
    if origem in ORIGENS_TEXTO:
        h["Access-Control-Allow-Origin"] = origem
    return web.Response(status=204, headers=h)


async def api_musica_ligar(req):
    """Botão "Ligar música" (aba Música): liga o painel (sem ligar em dobro) e espera até 40 s por ele. Também manda
    ligar a ComfyUI, se estiver desligada: a música gera nela (a mesma da imagem e do vídeo). A ComfyUI leva 1 a 2
    min e NÃO é esperada aqui: o painel abre logo e a primeira música aguarda na fila dele até ela responder.

    Responde {"musica": painel no ar?, "comfy": "ligada"|"ligando"|"desligada", "erro"?, "erro_comfy"?,
              "estado": estado_musica()} - com o que falta (motor, modelo) para a tela explicar."""
    em = estado_musica()
    if not TEM_MUSICA:
        return web.json_response({"musica": False, "comfy": "desligada", "estado": em,
                                  "erro": "O painel de música não está nesta instalação (falta a pasta painel_musica)."})
    comfy_ligada = await online(COMFY + "/system_stats")
    if not comfy_ligada and em["motor_instalado"]:
        pedir_ligar("video")  # com o motor instalado; sem ele o erro certo é "instale o motor" (vai em "estado")
    if not await online(MUSICA):
        pedir_ligar("painel_musica")
        for _ in range(40):
            if await online(MUSICA):
                break
            if "painel_musica" in ERRO_SERVICO and "painel_musica" not in LIGANDO:
                break
            await asyncio.sleep(1)
    ok = await online(MUSICA)
    resp = {"musica": ok, "estado": em,
            "comfy": "ligada" if comfy_ligada or await online(COMFY + "/system_stats")
                     else "ligando" if "video" in LIGANDO else "desligada"}
    if not ok and "painel_musica" in ERRO_SERVICO:
        resp["erro"] = ERRO_SERVICO["painel_musica"]["msg"]
    if "video" in ERRO_SERVICO:
        resp["erro_comfy"] = ERRO_SERVICO["video"]["msg"]
    return web.json_response(resp)


async def estatico(req):
    rel = req.match_info.get("caminho") or "index.html"
    arq = WEB / rel
    if not _dentro(arq, WEB) or not arq.is_file():
        raise web.HTTPNotFound()
    return web.FileResponse(arq, headers={"Cache-Control": "no-cache"})


ORIGENS_PAINEL = set(ORIGENS_TEXTO)

# ===================================================================== CONTA E LICENCA

# A conta e para a conta EXISTIR (e para o dia em que houver plano pago com API). As
# ferramentas locais sao de graca: quem gera e a placa de quem usa. Por isso o login tranca
# a TELA, e nao as rotas: se trancasse as rotas, todo atalho .bat que a pessoa escreveu
# pararia de funcionar - e o atalho e o jeito barato de usar o estudio.


def recarregar_presets():
    """Rele o presets.json do disco, sem reiniciar o estudio.

    fichas.json e novidades.json ja sao lidos do disco a cada pedido - so o PRESETS e
    carregado uma vez, na subida. Sem isto, atualizar a configuracao exigiria fechar e abrir
    o painel, e a atualizacao deixaria de ser "aparece e pronto".
    """
    global PRESETS
    PRESETS = cofre.ler_json("presets.json")


async def api_ias(req):
    """Que IAs estao instaladas, quanto falta baixar de cada uma e se da para baixar.

    06/11/2026. Antes, o Forja so servia para quem baixasse 235,7 GB ANTES de ver a
    primeira tela. Agora instala-se a plataforma (~5,6 GB), entra-se na conta, e cada IA
    vem depois, pelo botao da propria tela. Ver estudio/ias.py.
    """
    nomes = []
    for aba, lista in (PRESETS or {}).items():
        if isinstance(lista, list):
            nomes += [p.get("nome") for p in lista if p.get("nome") and not p.get("desligado")]
    cat = ias.catalogo()
    fora = {}
    for aba, lista in (PRESETS or {}).items():
        if not isinstance(lista, list):
            continue
        for p in lista:
            if p.get("desligado") or not p.get("nome"):
                continue
            fora[p["id"]] = dict(ias.estado_de(p["nome"], cat), nome=p["nome"],
                                 aprovada=p["id"] in APROVADAS, aba=aba)
    # as IAs de musica nao sao preset: entram pelo id da ficha, no fim da lista de aprovadas
    musica = []
    if cat:
        for mid, nome in ias.MUSICA_IAS.items():
            fora[mid] = dict(ias.estado_de(nome, cat), nome=nome, aprovada=True, aba="musica")
            musica.append(mid)
    return web.json_response({"ok": True, "tem_catalogo": bool(cat), "ias": fora,
                              "aprovadas": [i for i in APROVADAS if i in fora] + musica,
                              "progresso": ias.progresso()})


# As IAs que o projeto ja usou de verdade e aprova. Contado no historico do estudio de
# origem em 13/11/2026 (2.452 trabalhos, de 21/09 a 13/11), na ordem de uso:
#   krea2 743 | minimax_h3_r2v 640 | apresentador 551 | qwen_image_2512 156 |
#   ltx25_i2v 138 | fasth3 88 | ltx25_t2v 48 | krea2_img2img 29
# As outras do catalogo tem 13 usos ou menos cada. Nao estao quebradas: so nao tem estrada.
APROVADAS = ("krea2", "minimax_h3_r2v", "apresentador", "qwen_image_2512",
             "ltx25_i2v", "fasth3", "ltx25_t2v", "krea2_img2img")


def _discos():
    """Os discos FIXOS desta maquina, com o espaco de cada um. Pendrive e rede ficam fora."""
    fora = []
    if os.name != "nt":
        return fora
    import ctypes
    import string
    for letra in string.ascii_uppercase:
        raiz = letra + ":\\"
        try:
            if ctypes.windll.kernel32.GetDriveTypeW(raiz) != 3:      # 3 = disco fixo
                continue
            uso = shutil.disk_usage(raiz)
        except OSError:
            continue
        fora.append({"unidade": letra, "livre_gb": round(uso.free / 1024 ** 3, 1),
                     "total_gb": round(uso.total / 1024 ** 3, 1)})
    return fora


def _estado_do_destino(recado=None):
    pref = (ler_pref().get("pasta_ias") or "").strip()
    por_ambiente = bool(os.environ.get("ESTUDIO_COMFY_DIR"))
    return {"ok": True, "recado": recado,
            "modelos": str(COMFY_DIR / "models"),
            "unidade": (COMFY_DIR.anchor or "")[:1].upper(),
            "padrao": not pref and not por_ambiente,
            "por_ambiente": por_ambiente,
            "motor_instalado": (COMFY_DIR / "main.py").is_file(),
            # o que a tela precisa para oferecer "Instalar o motor" e mostrar o andamento
            "motor": dict(motor.progresso(), versao=motor.VERSAO,
                          gb=round(motor.BYTES / 1024 ** 3, 1), precisa_gb=motor.PRECISA_GB),
            "pasta_do_painel": str(ROOT),
            "nome_da_pasta": NOME_PASTA_IAS,
            "discos": _discos()}


async def api_ias_destino(req):
    """Onde as IAs sao instaladas. GET conta; POST {"unidade": "E"} ou {"padrao": true} troca.

    Trocar NAO move nada: o que ja foi baixado no lugar antigo fica la. A tela avisa.
    """
    global COMFY_DIR, PY_VIDEO
    if req.method != "POST":
        return web.json_response(_estado_do_destino())
    if os.environ.get("ESTUDIO_COMFY_DIR"):
        return web.json_response({"erro": "A pasta da ComfyUI está definida no arquivo caminhos.bat "
                                  "(ESTUDIO_COMFY_DIR). Para escolher pela tela, apague essa linha "
                                  "do caminhos.bat e abra o estúdio de novo."}, status=409)
    pg = ias.progresso()
    if pg.get("baixando") or pg.get("fila"):
        return web.json_response({"erro": "Há um download em andamento. Espere terminar, ou pare o "
                                  "download, antes de trocar o disco."}, status=409)
    if motor.progresso()["fase"] not in (None, "pronto"):
        return web.json_response({"erro": "O motor está sendo instalado. Espere terminar antes de "
                                  "trocar o disco."}, status=409)
    try:
        b = await req.json()
    except ValueError:
        b = {}
    if b.get("padrao"):
        base = ""
    else:
        unidade = str(b.get("unidade") or "").strip().upper().rstrip(":\\/")
        if not re.fullmatch(r"[A-Z]", unidade):
            return web.json_response({"erro": "Escolha um dos discos da lista."}, status=400)
        if unidade not in {d["unidade"] for d in _discos()}:
            return web.json_response({"erro": f"Não achei o disco {unidade}: nesta máquina."}, status=400)
        base = f"{unidade}:\\{NOME_PASTA_IAS}"
        # provar que da para escrever ANTES de gravar a escolha: disco protegido ou cheio
        # apareceria so no meio do primeiro download, horas depois.
        try:
            Path(base).mkdir(parents=True, exist_ok=True)
            teste = Path(base) / ".forja_teste_de_escrita"
            teste.write_text("ok", encoding="ascii")
            teste.unlink()
        except OSError as exc:
            return web.json_response({"erro": f"Não consegui escrever em {base}: {exc.strerror or exc}. "
                                      "Escolha outro disco."}, status=400)
    antiga = COMFY_DIR / "models"
    gravar_pref({"pasta_ias": base})
    COMFY_DIR = _comfy_dir_inicial()
    PY_VIDEO = COMFY_DIR.parent / "python_embeded" / "python.exe"
    ias.MODELOS = COMFY_DIR / "models"
    voz_studio.OUTRAS[:] = [_pasta_da_voz()]
    _apontar_o_texto()
    recado = None
    if antiga != ias.MODELOS and antiga.is_dir() and any(antiga.rglob("*.safetensors")):
        recado = (f"As IAs que você já baixou continuam em {antiga}. Elas não foram movidas: "
                  "o painel passa a procurar e a baixar no lugar novo.")
    # A ComfyUI mudou de lugar: o nó da música vai para a custom_nodes do lugar novo (se já houver motor lá).
    await asyncio.to_thread(copiar_nos_do_pacote, "troca do disco das IAs")
    # O painel de música recebe a pasta da ComfyUI quando LIGA: ligado, ele continua olhando a pasta antiga.
    if antiga != ias.MODELOS and TEM_MUSICA and await online(MUSICA):
        aviso_musica = ("O painel de música ainda está usando a pasta antiga: desligue e ligue o painel de música "
                        "no Início para ele passar a usar o disco novo.")
        recado = f"{recado} {aviso_musica}" if recado else aviso_musica
    return web.json_response(_estado_do_destino(recado))


def _porta_aberta(porta, segundos=0.3):
    import socket
    try:
        with socket.create_connection(("127.0.0.1", porta), timeout=segundos):
            return True
    except OSError:
        return False


async def api_requisitos(req):
    """Tudo que esta maquina precisa para o estudio funcionar INTEIRO, em ordem de fazer.

    14/11/2026, regra do dono: tudo que e preciso baixar, instalar ou cadastrar aparece na
    tela inicial, com o estado, o passo a passo e o link direto. Antes, o ffmpeg e o
    VoiceStudio so existiam num manual - e a pessoa descobria que faltavam no meio de um
    trabalho, por uma mensagem de erro.

    estado: "ok" (verde), "falta" (precisa fazer), "aviso" (funciona, mas olhe), "opcional".
    """
    itens = []

    # ---- 1. a placa de video
    try:
        nv = await gpu_nvidia_smi()
    except Exception:
        nv = None
    if nv:
        gb = nv[1] / 1024 ** 3
        itens.append({"id": "placa", "nome": "Placa de vídeo NVIDIA",
                      "estado": "ok" if gb >= 11.5 else "aviso",
                      "resumo": f"{nv[0]} — {gb:.0f} GB" + ("" if gb >= 11.5 else
                                " (com menos de 12 GB só a parte de imagem costuma caber)"),
                      "passos": []})
    else:
        itens.append({"id": "placa", "nome": "Placa de vídeo NVIDIA", "estado": "falta",
                      "resumo": "Não encontrei uma placa NVIDIA com o driver instalado. Sem ela as IAs não geram.",
                      "passos": ["Confira se o computador tem uma placa NVIDIA (GeForce RTX).",
                                 "Baixe e instale o driver mais novo no site da NVIDIA.",
                                 "Reinicie o computador e abra o estúdio de novo."],
                      "botao": {"acao": "link", "url": "https://www.nvidia.com/pt-br/drivers/",
                                "rotulo": "Abrir o site do driver"}})

    # ---- 2. o ffmpeg
    onde = requisitos.ffmpeg_onde()
    itens.append({"id": "ffmpeg", "nome": "ffmpeg (converte áudio e vídeo)",
                  "estado": "ok" if onde else "falta",
                  "resumo": ("Instalado." if onde else
                             "Falta. Sem ele o painel não consegue ler os áudios e vídeos que você envia."),
                  "passos": [] if onde else ["Clique em Instalar: o painel baixa (118 MB), confere "
                                             "o arquivo e põe na pasta do estúdio. Não mexe no Windows."],
                  **({} if onde else {"botao": {"acao": "instalar", "qual": "ffmpeg",
                                                "rotulo": "Instalar o ffmpeg — 118 MB"}})})

    # ---- 3. o motor de imagem e video
    tem_motor = (COMFY_DIR / "main.py").is_file()
    itens.append({"id": "motor", "nome": "Motor de imagem e vídeo (ComfyUI)",
                  "estado": "ok" if tem_motor else "falta",
                  "resumo": (f"Instalado em {COMFY_DIR.parent}." if tem_motor else
                             "Falta. É ele que gera as imagens e os vídeos."),
                  "passos": [] if tem_motor else ["Logo abaixo, em \"IAs aprovadas pelo projeto\", escolha o disco.",
                                                  "Clique em \"Instalar o motor\" (1,8 GB)."],
                  **({} if tem_motor else {"botao": {"acao": "ir", "para": "blocoAprovadas",
                                                     "rotulo": "Ir para a instalação do motor"}})})

    # ---- 4. as IAs
    cat = ias.catalogo()
    prontas = total = 0
    for lista in (PRESETS or {}).values():
        if isinstance(lista, list):
            for p in lista:
                if p.get("id") in APROVADAS and p.get("nome"):
                    total += 1
                    prontas += bool(ias.estado_de(p["nome"], cat).get("instalada"))
    if total:
        itens.append({"id": "ias", "nome": "IAs (os modelos)",
                      "estado": "ok" if prontas else "falta",
                      "resumo": (f"{prontas} de {total} das aprovadas instaladas." if prontas else
                                 "Nenhuma instalada ainda. Cada IA é um download à parte."),
                      "passos": [] if prontas == total else
                      ["Em \"IAs aprovadas pelo projeto\", marque as que quer.",
                       "Clique em \"Instalar as marcadas\". Dá para usar o estúdio enquanto baixa."],
                      **({} if prontas == total else {"botao": {"acao": "ir", "para": "blocoAprovadas",
                                                                "rotulo": "Escolher as IAs"}})})

    # ---- 5. a voz
    voz_no_ar = _porta_aberta(_porta_url(voz_studio.URL) or 3900)
    voz_instalada = voz_no_ar or voz_studio.achar_backend() is not None
    v = requisitos.VOICESTUDIO
    if voz_no_ar:
        itens.append({"id": "voz", "nome": "Motor de voz (VoiceStudio)", "estado": "ok",
                      "resumo": "Ligado. Na aba Narração, confira a licença do motor ativo antes de publicar.",
                      "passos": []})
    elif voz_instalada:
        itens.append({"id": "voz", "nome": "Motor de voz (VoiceStudio)", "estado": "aviso",
                      "resumo": "Instalado, mas desligado. A aba Narração liga ele sozinha quando você usar.",
                      "passos": []})
    else:
        itens.append({"id": "voz", "nome": "Motor de voz (VoiceStudio)", "estado": "opcional",
                      "resumo": "Não instalado. É o que faz a narração local, de graça. Opcional: sem ele "
                                "só a aba Narração fica parada.",
                      "passos": [f"Clique em Baixar: o painel baixa o instalador oficial (222 MB, versão {v['versao']}), "
                                 "confere o arquivo e abre.",
                                 "No instalador do VoiceStudio, avance até o fim. A pasta já vem "
                                 "preenchida no disco que você escolheu para as IAs.",
                                 "Abra o VoiceStudio uma vez: na primeira abertura ele baixa os modelos de voz (cerca de 22 GB).",
                                 "Dentro dele, troque o motor para o VoxCPM 2. O que vem ligado (OmniVoice) "
                                 "tem licença que NÃO permite vídeo monetizado.",
                                 "Volte aqui: esta linha fica verde."],
                      "botao": {"acao": "instalar", "qual": "voz",
                                "rotulo": "Baixar o VoiceStudio — 222 MB"},
                      "link": {"url": v["pagina"], "rotulo": "Página oficial do VoiceStudio"}})

    # ---- 6. a IA de texto
    falta_b, falta_nomes = requisitos.texto_falta()
    if not falta_nomes and TEXTO.instalado():
        itens.append({"id": "texto", "nome": "IA de texto (escreve e traduz)", "estado": "ok",
                      "resumo": f"Instalada em {texto.MODELOS_DIR}.", "passos": []})
    else:
        gb = f"{falta_b / 1024 ** 3:.1f}".replace(".", ",")
        itens.append({"id": "texto", "nome": "IA de texto (escreve e traduz)", "estado": "opcional",
                      "resumo": "Não instalada. É ela que melhora o seu prompt, traduz, descreve uma imagem "
                                "e escreve roteiro, tudo na sua máquina. Opcional: sem ela esses botões "
                                "ficam parados e o resto funciona.",
                      "passos": [f"Clique em Instalar: o painel baixa {gb} GB (o programa llama.cpp e dois "
                                 "modelos Qwen, licença Apache 2.0) e confere cada arquivo.",
                                 f"Os modelos vão para {texto.MODELOS_DIR}, no disco que você escolheu "
                                 "em \"IAs aprovadas pelo projeto\". Para mudar, troque o disco lá antes.",
                                 "Se a internet cair, clique de novo: continua de onde parou.",
                                 "Não precisa de conta nem de chave."],
                      "botao": {"acao": "instalar", "qual": "texto",
                                "rotulo": f"Instalar a IA de texto — {gb} GB"}})

    # ---- 7. as chaves
    tem_hf = ias.tem_token()
    itens.append({"id": "chaves", "nome": "Contas e chaves de API",
                  "estado": "ok" if tem_hf else "opcional",
                  "resumo": ("Token do Hugging Face guardado." if tem_hf else
                             "Opcionais. Só o LTX 2.5 precisa de uma: o token gratuito do Hugging Face."),
                  "passos": [] if tem_hf else ["Em \"Configurações de API\", no fim desta página, cada chave tem "
                                               "os links diretos: onde criar a conta, onde aceitar a licença "
                                               "e onde gerar a chave."],
                  **({} if tem_hf else {"botao": {"acao": "ir", "para": "blocoChaves",
                                                  "rotulo": "Ver as chaves"}})})

    falta = [i["id"] for i in itens if i["estado"] == "falta"]
    # 14/11/2026: os motores que NAO sao da ComfyUI entram na mesma lista de marcar e baixar
    # das IAs de imagem e video ("IAs aprovadas"). "pode": False = ainda nao instala por aqui.
    extras = [
        {"id": "voz", "nome": "Voz e clone de voz (VoiceStudio)", "instalada": voz_instalada, "pode": True,
         "gb": round(v["bytes"] / 1024 ** 3, 2),
         "nota": "Baixa e abre o instalador dele. Os modelos de voz (cerca de 22 GB) ele mesmo baixa na primeira vez que abrir."},
        {"id": "texto", "nome": "IA de texto (Qwen)", "pode": True,
         "instalada": not falta_nomes and TEXTO.instalado(), "gb": round(falta_b / 1024 ** 3, 1),
         "nota": "Melhora o prompt, traduz, descreve imagem e escreve roteiro. Não precisa de conta nem de chave."},
    ]
    return web.json_response({"ok": True, "itens": itens, "falta": falta, "extras": extras,
                              "andamento": requisitos.progresso()})


async def api_requisitos_instalar(req):
    try:
        b = await req.json()
    except ValueError:
        b = {}
    qual = str(b.get("qual") or "")
    if qual == "voz":
        # o instalador ja abre com a pasta no disco que a pessoa escolheu para as IAs
        requisitos.VOICESTUDIO["destino"] = str(_pasta_da_voz())
    entrou, recado = requisitos.instalar(qual)
    return web.json_response({"ok": entrou, "mensagem": recado}, status=200 if entrou else 409)


async def api_requisitos_parar(req):
    requisitos.parar()
    return web.json_response({"ok": True})


async def api_motor_instalar(req):
    """Instala a ComfyUI (o motor) no disco escolhido. O andamento vem no /api/ias/destino."""
    if os.environ.get("ESTUDIO_COMFY_DIR"):
        return web.json_response({"ok": False, "mensagem": "A pasta da ComfyUI está definida no "
                                  "caminhos.bat: instale a ComfyUI nela à mão (Passo 0 do INSTALAR.md)."},
                                 status=409)
    # COMFY_DIR = <base>\ComfyUI_windows_portable\ComfyUI  ->  o motor.py recebe a <base>
    entrou, recado = motor.instalar(COMFY_DIR.parent.parent)
    return web.json_response({"ok": entrou, "mensagem": recado}, status=200 if entrou else 409)


async def api_motor_parar(req):
    motor.parar()
    return web.json_response({"ok": True})


async def api_ias_instalar(req):
    b = await req.json()
    pid = (b.get("id") or "").strip()
    nome = None
    for lista in (PRESETS or {}).values():
        if isinstance(lista, list):
            for p in lista:
                if p.get("id") == pid:
                    nome = p.get("nome")
    nome = nome or ias.MUSICA_IAS.get(pid)
    if not nome:
        return web.json_response({"erro": "Não achei essa IA no painel."}, status=404)
    entrou, recado = ias.instalar(nome)
    return web.json_response({"ok": entrou, "mensagem": recado}, status=200 if entrou else 409)


async def api_ias_progresso(req):
    return web.json_response(ias.progresso())


async def api_ias_parar(req):
    ias.parar()
    return web.json_response({"ok": True, "mensagem": "Parei. O que já baixou fica; "
                                                      "da próxima vez continua de onde parou."})


async def api_atualizacao_estado(req):
    return web.json_response(await atualizacao.estado())


async def api_atualizacao_aplicar(req):
    try:
        r = await atualizacao.aplicar()
    except licenca.ErroDeConta as exc:
        return web.json_response({"erro": str(exc)}, status=exc.status if exc.status < 500 else 502)
    try:
        recarregar_presets()
    except Exception as exc:
        # os arquivos novos ja estao no HD; so a memoria ficou velha. Reiniciar resolve, e e
        # melhor dizer isso do que fingir que deu tudo certo.
        print(f"[estúdio] recarregar presets apos atualizar: {exc!r}", flush=True)
        r["recarregar_pediu_reinicio"] = True
    return web.json_response(r)


async def destrancar_presets():
    """Abre o cofre e carrega os presets. Chamado ao entrar, ao criar conta e na subida.

    Sem isto o painel entraria na conta e continuaria sem configuracao nenhuma ate ser
    reiniciado - a pessoa acharia que o login nao funcionou.
    """
    try:
        if await licenca.abrir_cofre():
            recarregar_presets()
            return True
        print(f"[estúdio] presets trancados: {cofre.erro()}", flush=True)
    except Exception as exc:
        print(f"[estúdio] abrir o cofre dos presets: {exc!r}", flush=True)
    return False


async def api_conta_estado(req):
    e = licenca.estado()
    if not e.get("entrou"):
        # So pergunta pelo servidor quando ainda nao ha conta: e a resposta que decide se a
        # tela mostra a porta de entrada ou abre o estudio avisando que nao ha servidor.
        e["servidor_no_ar"] = await licenca.servidor_no_ar()
    return web.json_response(e)


async def api_conta_criar(req):
    b = await req.json()
    try:
        r = await licenca.criar_conta(
            (b.get("nome") or "").strip(), (b.get("email") or "").strip(),
            (b.get("telefone") or "").strip(), b.get("senha") or "")
        if not r.get("precisa_confirmar"):      # falta o codigo do e-mail: ainda nao entrou
            await destrancar_presets()
        return web.json_response(r)
    except licenca.ErroDeConta as exc:
        return web.json_response({"erro": str(exc)}, status=exc.status if exc.status < 500 else 502)


async def api_conta_entrar(req):
    b = await req.json()
    try:
        r = await licenca.entrar((b.get("email") or "").strip(), b.get("senha") or "")
        if not r.get("precisa_confirmar"):
            await destrancar_presets()
        return web.json_response(r)
    except licenca.ErroDeConta as exc:
        return web.json_response({"erro": str(exc)}, status=exc.status if exc.status < 500 else 502)


async def api_conta_codigo(req):
    """Os 6 numeros que chegaram no e-mail. Bateu: a pessoa esta dentro."""
    b = await req.json()
    try:
        r = await licenca.confirmar_codigo((b.get("email") or "").strip(),
                                           re.sub(r"\D", "", str(b.get("codigo") or "")))
        await destrancar_presets()
        return web.json_response(r)
    except licenca.ErroDeConta as exc:
        return web.json_response({"erro": str(exc)}, status=exc.status if exc.status < 500 else 502)


async def api_conta_recuperar(req):
    """"Esqueci minha senha". Ate 13/11/2026 esta rota NAO EXISTIA no painel: o botao da
    tela chamava um endereco que respondia 404, e a tela dizia que o e-mail tinha saido."""
    b = await req.json()
    try:
        await licenca.pedir_codigo_da_senha((b.get("email") or "").strip())
        return web.json_response({"ok": True})
    except licenca.ErroDeConta as exc:
        return web.json_response({"erro": str(exc)}, status=exc.status if exc.status < 500 else 502)


async def api_conta_senha_por_codigo(req):
    b = await req.json()
    try:
        return web.json_response(await licenca.senha_por_codigo(
            (b.get("email") or "").strip(), re.sub(r"\D", "", str(b.get("codigo") or ""))))
    except licenca.ErroDeConta as exc:
        return web.json_response({"erro": str(exc)}, status=exc.status if exc.status < 500 else 502)


async def api_conta_reenviar_codigo(req):
    b = await req.json()
    try:
        await licenca.reenviar_codigo((b.get("email") or "").strip())
        return web.json_response({"ok": True})
    except licenca.ErroDeConta as exc:
        return web.json_response({"erro": str(exc)}, status=exc.status if exc.status < 500 else 502)


async def api_conta_sair(req):
    await licenca.sair()
    return web.json_response({"ok": True})


async def renovar_licenca_de_vez_em_quando():
    """Confere a licenca no servidor ao ABRIR o estudio e, depois, de 6 em 6 horas.

    Confere sempre ao abrir, e nao so quando a licenca esta perto de vencer. A diferenca e
    grande na pratica: conferindo so no fim, uma conta revogada seguiria trabalhando por
    quase cinco dias; conferindo ao abrir, ela para na proxima vez que a pessoa liga o
    estudio. Quem estiver sem internet nao perde nada - a licenca guardada vale ate vencer,
    que e justamente para isso que ela e assinada.

    De 6 em 6 horas, e nao a cada minuto, de proposito: a licenca vale dias, e bater no
    servidor toda hora so gastaria internet e prenderia o estudio a um servidor no ar.
    """
    # 11/11/2026: se a licenca guardada nao confere, DIGA no log. Antes ficava mudo e o
    # painel apenas voltava a pedir login - a pessoa entrava de novo, de novo, e ninguem
    # tinha como saber por que (aconteceu 5 vezes com o primeiro usuario de fora).
    try:
        inicial = licenca.estado()
        if not inicial.get("entrou") and inicial.get("motivo"):
            print(f"[estúdio] a licença não vale aqui: {inicial['motivo']}", flush=True)
    except Exception as exc:
        print(f"[estúdio] não consegui conferir a licença: {exc!r}", flush=True)

    # O cofre primeiro, e sem esperar os 20 s: se a chave ja esta guardada aqui, o painel
    # tem os presets em menos de um segundo, mesmo sem internet.
    await destrancar_presets()
    await asyncio.sleep(20)
    primeira = True
    while True:
        try:
            if primeira or licenca.precisa_renovar():
                if await licenca.renovar():
                    print("[estúdio] licença conferida e renovada.", flush=True)
                    if cofre.existe() and not cofre.aberto():
                        await destrancar_presets()   # voltou a internet: tenta de novo
        except licenca.ErroDeConta as exc:
            print(f"[estúdio] licença recusada pelo servidor: {exc}", flush=True)
        except Exception as exc:
            print(f"[estúdio] renovar licença: {exc!r}", flush=True)
        primeira = False
        await asyncio.sleep(6 * 3600)


# ===================================================================== O PORTAO (quem pode mandar)

# O estudio so escuta em 127.0.0.1, entao ninguem da rede chega nele. Mas o NAVEGADOR chega:
# qualquer pagina aberta noutra aba pode mandar um POST para ca, e o navegador manda com a
# permissao da propria maquina. Isso se chama CSRF, e aqui era possivel DE VERDADE - provado
# em 03/11/2026 contra o estudio no ar: um POST em /api/preferencias com "Content-Type:
# text/plain" e "Origin" de outro site foi aceito com HTTP 200. Dois motivos se somavam:
#   1. "text/plain" e pedido SIMPLES: o navegador manda sem pedir licenca antes (sem preflight),
#      entao a licenca de CORS la embaixo nunca era consultada;
#   2. o req.json() do aiohttp (3.14) le o corpo e NAO confere o Content-Type - conferido no
#      proprio codigo da biblioteca.
# Sem o portao, um site qualquer esvaziava a lixeira (/api/limpar-lixeira apaga do HD),
# desligava a ComfyUI no meio de uma geracao (/api/servicos/desligar) ou enfileirava trabalho.
#
# O portao NAO atrapalha os atalhos .bat: script (curl, Python, PowerShell) nao manda cabecalho
# "Origin" nem "Sec-Fetch-Site" nenhum, e passa. Navegador manda sempre - e e dele que vem o golpe.
ORIGENS_OK = ({f"http://127.0.0.1:{PORTA}", f"http://localhost:{PORTA}"}
              | ORIGENS_PAINEL | ORIGENS_TEXTO)
MAQUINAS_OK = {"127.0.0.1", "localhost", "[::1]", "::1"}
SO_LEEM = {"GET", "HEAD", "OPTIONS"}


@web.middleware
async def portao(req, handler):
    # 1. O "Host" tem que ser esta maquina. Fecha o golpe do dominio de fora que aponta para
    #    127.0.0.1 (DNS rebinding): o endereco e do atacante, mas o pedido chega aqui dentro.
    maquina = (req.headers.get("Host") or "").rsplit(":", 1)[0]
    if maquina and maquina not in MAQUINAS_OK:
        raise web.HTTPForbidden(text="Este estudio so atende em 127.0.0.1, nesta maquina.")
    if req.method in SO_LEEM:
        return await handler(req)
    # 2. Pedido que MUDA alguma coisa so e aceito de quem e daqui.
    origem = req.headers.get("Origin")
    if origem:
        if origem not in ORIGENS_OK:
            raise web.HTTPForbidden(text="Pedido recusado: veio de outro site.")
    elif (req.headers.get("Sec-Fetch-Site") or "") in ("cross-site", "same-site"):
        raise web.HTTPForbidden(text="Pedido recusado: veio de outro site.")
    return await handler(req)


@web.middleware
async def cors_painel(req, handler):
    resp = await handler(req)
    origem = req.headers.get("Origin")
    if origem in ORIGENS_PAINEL and req.method == "GET" and req.path in ("/api/ocupado", "/api/fichas", "/api/inicio",
                                                                          "/api/texto/estado"):
        resp.headers["Access-Control-Allow-Origin"] = origem
    elif origem in ORIGENS_TEXTO and req.method == "POST" and req.path == "/api/texto":
        resp.headers["Access-Control-Allow-Origin"] = origem
    return resp


async def reparar_ao_iniciar():
    await asyncio.sleep(1)
    await reconciliar()
    mudou = False
    for j in JOBS:
        if j.get("estado") == "concluido" and not j.get("saidas") and j.get("prompt_id") and not j.get("lixeira"):
            try:  # concluiu mas a saída não foi registrada: busca de novo no histórico da ComfyUI
                j["saidas"] = await buscar_saidas(j["prompt_id"], tentativas=1)
                final = j.get("saida_final")
                j["saidas"].sort(key=lambda s: 0 if s["no"] == final else 1)
                mudou = True
            except Exception:
                pass
    if mudou:
        salvar()


# ===================================================================== VOZ LOCAL (VoiceStudio)
# Narração de graça, no computador da pessoa. O estúdio inteiro já roda local — a voz era o
# único elo que ainda exigia assinatura paga, e sem ela o estúdio não serve para quem baixar.
# Tudo aqui é opcional: com o VoiceStudio fechado, /api/voz/estado devolve no_ar=false e a tela
# mostra o cartão de "ligar", exatamente como o painel de música.
VOZ_SAIDA = LOGS_DIR / "voz"


async def api_voz_estado(req):
    est = await voz_studio.estado()
    if est["no_ar"]:
        est["vozes"] = await voz_studio.vozes(req.query.get("atualizar") == "1")
        est["idiomas"] = await voz_studio.idiomas()
    else:
        est["vozes"], est["idiomas"] = [], []
    est["url"] = voz_studio.URL
    return web.json_response(est)


async def api_voz_ligar(req):
    """Liga o motor de voz sem janela e espera ele responder — igual ao botão de ligar a
    música. É o que torna a aba Narração autossuficiente: nada de depender de um programa
    que alguém precisa lembrar de deixar aberto."""
    est = await voz_studio.estado()
    if est["no_ar"]:
        return web.json_response({"ok": True, "recado": "A voz local já estava no ar.", **est})
    ok, recado = await asyncio.to_thread(voz_studio.ligar, VOZ_SAIDA)
    if not ok:
        raise web.HTTPBadRequest(text=recado)
    for _ in range(20):                      # até ~60 s
        await asyncio.sleep(3)
        est = await voz_studio.estado()
        if est["no_ar"]:
            est["vozes"] = await voz_studio.vozes(True)
            est["idiomas"] = await voz_studio.idiomas()
            return web.json_response({"ok": True, "recado": "Pronto: a voz local está no ar.", **est})
    return web.json_response({"ok": False, "recado": "Liguei, mas ele ainda não respondeu. "
                                                     "Espere um pouco e clique em procurar de novo."})


async def api_voz_descrever(req):
    b = await req.json()
    desc = (b.get("descricao") or "").strip()
    if len(desc) < 3:
        return web.json_response({"entendeu": {}, "ignorou": []})
    try:
        return web.json_response(await voz_studio.descrever(desc))
    except Exception as e:  # enquanto ele digita: nunca atrapalhar a digitação com erro
        return web.json_response({"entendeu": {}, "ignorou": [], "erro": str(e)[:200]})


async def api_voz_desenhar(req):
    b = await req.json()
    desc = (b.get("descricao") or "").strip()
    if not desc:
        raise web.HTTPBadRequest(text="Descreva a voz que você quer.")
    try:
        pid = await voz_studio.desenhar(desc, (b.get("nome") or "").strip() or None,
                                        b.get("idioma") or "pt", (b.get("entrega") or "").strip() or None)
    except Exception as e:
        raise web.HTTPBadGateway(text=str(e)[:300])
    return web.json_response({"id": pid, "vozes": await voz_studio.vozes(True)})


async def api_voz_gravadas(req):
    """As narracoes ja geradas, da mais nova para a mais velha.

    Le a pasta, nao um banco: o que vale e o arquivo. Narracao sem ficha (gerada antes de
    07/11/2026) aparece assim mesmo, com o texto vazio - some da lista seria pior.
    """
    VOZ_SAIDA.mkdir(parents=True, exist_ok=True)
    itens = []
    for arq in VOZ_SAIDA.glob("voz_*.wav"):
        try:
            st = arq.stat()
        except OSError:
            continue
        ficha = {}
        f = arq.with_suffix(".json")
        if f.is_file():
            try:
                ficha = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                ficha = {}
        itens.append({"arquivo": arq.name, "url": "/api/voz/audio/" + arq.name,
                      "quando": int(ficha.get("quando") or st.st_mtime),
                      "kb": round(st.st_size / 1024),
                      "texto": (ficha.get("texto") or "")[:300],
                      "voz": ficha.get("voz") or "", "segundos": ficha.get("segundos")})
    itens.sort(key=lambda i: i["quando"], reverse=True)
    return web.json_response({"narracoes": itens})


async def api_voz_gravada_apagar(req):
    """Apaga UMA narracao gravada (o wav e a ficha). So dentro da pasta de saida."""
    b = await req.json()
    nome = Path(str(b.get("arquivo") or "")).name
    alvo = VOZ_SAIDA / nome
    if not nome.startswith("voz_") or not nome.endswith(".wav") or not _dentro(alvo, VOZ_SAIDA):
        raise web.HTTPBadRequest(text="Nome de arquivo invalido.")
    if not alvo.is_file():
        raise web.HTTPNotFound(text="Essa narracao ja nao existe.")
    alvo.unlink()
    alvo.with_suffix(".json").unlink(missing_ok=True)
    print("[estudio] narracao apagada: %s" % nome, flush=True)
    return web.json_response({"apagada": nome})


async def api_voz_apagar(req):
    """Apaga uma voz do VoiceStudio. Pede o NOME junto, de proposito.

    07/11/2026: apagar e irreversivel e vale para tudo que usa o VoiceStudio nesta maquina,
    nao so para este painel. Por isso o pedido traz `id` E `nome`, e so segue se o nome bater
    com o da voz que tem aquele id. Um clique errado na lista nao apaga a voz de baixo.
    """
    b = await req.json()
    pid = str(b.get("id") or "").strip()
    nome_dito = str(b.get("nome") or "").strip()
    if not pid:
        raise web.HTTPBadRequest(text="Diga qual voz apagar.")

    lista = await voz_studio.vozes(True)
    alvo = next((v for v in lista if str(v.get("id")) == pid), None)
    if alvo is None:
        raise web.HTTPNotFound(text="Essa voz ja nao existe.")
    if nome_dito and nome_dito != str(alvo.get("nome") or ""):
        raise web.HTTPConflict(
            text="A lista mudou: esse lugar agora e da voz \"%s\". Confira e tente de novo."
                 % (alvo.get("nome") or "?"))

    try:
        sumiu = await voz_studio.apagar_voz(pid)
    except Exception as e:
        raise web.HTTPBadGateway(text=str(e)[:300])
    if not sumiu:
        raise web.HTTPBadGateway(text="O VoiceStudio respondeu ok, mas a voz continua na "
                                      "lista. Nao apaguei nada.")
    print("[estudio] voz apagada: %s (%s)" % (alvo.get("nome"), pid), flush=True)
    return web.json_response({"apagada": pid, "nome": alvo.get("nome"),
                              "vozes": await voz_studio.vozes(True)})


async def api_voz_conferir_ref(req):
    """Olha o áudio de referência e devolve o laudo, SEM clonar.

    07/11/2026: existe porque o clone da YAMI saiu lixo e a tela não disse nada. O painel
    cortava os primeiros 25 s do arquivo sem olhar o que havia lá — e na YAMI havia música
    tocando nos 252 s inteiros, sem uma pausa. Agora a pessoa vê o problema ANTES de esperar
    minutos por uma voz embaralhada. O arquivo é guardado num temporário e apagado na hora.
    """
    dados = await req.post()
    arq = dados.get("arquivo")
    if arq is None or not getattr(arq, "filename", ""):
        raise web.HTTPBadRequest(text="Envie um áudio de referência.")
    VOZES_DIR.mkdir(parents=True, exist_ok=True)
    tmp = VOZES_DIR / ("conferindo_" + uuid.uuid4().hex[:8] + Path(arq.filename).suffix.lower())
    try:
        tmp.write_bytes(arq.file.read())
        laudo = await asyncio.to_thread(voz_studio.conferir_referencia, tmp)
    except Exception as e:
        raise web.HTTPBadGateway(text=str(e)[:300])
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
    return web.json_response(laudo)


async def api_voz_transcrever_ref(req):
    """Descobre o que esta falado no audio de referencia e devolve o texto.

    07/11/2026: ele perguntou "e quando eu nao sei?". O campo pode ficar em branco, mas texto
    CERTO ajuda - e quem sabe transcrever e o motor, nao a pessoa. O arquivo vai para um
    temporario e e apagado no fim.
    """
    dados = await req.post()
    arq = dados.get("arquivo")
    if arq is None or not getattr(arq, "filename", ""):
        raise web.HTTPBadRequest(text="Envie o audio de referencia.")
    VOZES_DIR.mkdir(parents=True, exist_ok=True)
    tmp = VOZES_DIR / ("transcrevendo_" + uuid.uuid4().hex[:8] + Path(arq.filename).suffix.lower())
    try:
        tmp.write_bytes(arq.file.read())
        r = await voz_studio.transcrever_referencia(
            tmp, str(dados.get("idioma") or "pt"), base_mcp=VOZ_SAIDA)
    except Exception as e:
        raise web.HTTPBadGateway(text=str(e)[:300])
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
    return web.json_response(r)


async def api_voz_clonar(req):
    """O áudio de referência chega como upload; guardamos junto das outras vozes do estúdio."""
    dados = await req.post()
    arq = dados.get("arquivo")
    if arq is None or not getattr(arq, "filename", ""):
        raise web.HTTPBadRequest(text="Envie um áudio de referência.")
    nome = (str(dados.get("nome") or "").strip() or Path(arq.filename).stem)[:60]
    transcricao = str(dados.get("transcricao") or "").strip()
    # A transcrição é OPCIONAL de propósito, e isso foi MEDIDO em 31/10: com uma transcrição
    # errada ("Português, Brasil." num áudio de 25 s) a mesma frase saiu CORTADA em 2,6 s; sem
    # transcrição nenhuma, saiu inteira em 6,2 s e em metade do tempo de placa. Texto errado é
    # pior do que texto nenhum. Exigir o campo só empurrava a pessoa a inventar alguma coisa.
    VOZES_DIR.mkdir(parents=True, exist_ok=True)
    destino = VOZES_DIR / ("ref_" + re.sub(r"[^A-Za-z0-9_-]+", "_", nome) + Path(arq.filename).suffix.lower())
    destino.write_bytes(arq.file.read())
    try:
        pid = await voz_studio.clonar(destino, nome, transcricao, str(dados.get("idioma") or "pt"),
                                      str(dados.get("entrega") or "").strip() or None,
                                      base_mcp=VOZ_SAIDA)
    except Exception as e:
        raise web.HTTPBadGateway(text=str(e)[:300])
    return web.json_response({"id": pid, "vozes": await voz_studio.vozes(True)})


_voz_ultima = {"quando": 0.0}


def _ultima_narracao():
    """Quando foi a ultima narracao, em relogio de parede.

    07/11/2026: isto vivia SO na memoria, e reiniciar o painel fazia a proxima geracao ser
    contada como "motor frio" mesmo com o motor quente - sujando a medida que justamente
    separa as duas. Agora o relogio vai gravado em cada medida, entao sobrevive ao reinicio.
    """
    if _voz_ultima["quando"]:
        return _voz_ultima["quando"]
    maior = 0
    for chave in ("voz|quente", "voz|frio"):
        for m in STATS.get(chave, []):
            if isinstance(m, dict) and m.get("quando"):
                maior = max(maior, m["quando"])
    _voz_ultima["quando"] = maior
    return maior


def _prever_voz(letras):
    """Quanto deve demorar gerar `letras` caracteres. So com o que foi MEDIDO aqui.

    Devolve (segundos, amostras, frio). Sem medida nenhuma devolve (None, 0, frio) - e a
    tela mostra so o cronometro subindo, que e verdade, em vez de uma porcentagem inventada.
    """
    frio = time.time() - _ultima_narracao() > 600
    medidas = [m for m in STATS.get("voz|frio" if frio else "voz|quente", [])
               if isinstance(m, dict) and m.get("total") and m.get("letras")]
    if not medidas:
        # sem medida do estado certo, tenta o outro: previsao torta e melhor que nenhuma,
        # e a tela diz que e estimativa.
        medidas = [m for m in STATS.get("voz|quente" if frio else "voz|frio", [])
                   if isinstance(m, dict) and m.get("total") and m.get("letras")]
        if not medidas:
            return None, 0, frio
    # segundos por letra, pela MEDIANA das ultimas - a media deixa um caso ruim mandar
    taxas = sorted(m["total"] / max(m["letras"], 1) for m in medidas[-15:])
    taxa = taxas[len(taxas) // 2]
    return round(taxa * max(letras, 1), 1), len(medidas), frio


def _quem_mandou(extra):
    """Quem mandou este trabalho para a ComfyUI, olhando o que veio carimbado nele.

    07/11/2026. Ele pediu "um local para ver o que esta sendo gerado, mesmo que seja o
    Claude, o GPT ou qualquer fluxo". Da para saber porque TODO prompt que o estudio manda
    leva `extra_pnginfo.estudio_local` dentro (e assim que a ComfyUI grava a ficha no PNG).
    O que nao tem esse carimbo veio de fora - e e justamente o que ele quer enxergar.
    """
    info = ((extra or {}).get("extra_pnginfo") or {})
    nosso = info.get("estudio_local")
    if isinstance(nosso, dict):
        return {"de": "estudio", "nome": "Este painel",
                "detalhe": nosso.get("ia") or nosso.get("preset") or ""}
    # outras ferramentas tambem carimbam; mostramos o que der, sem inventar
    for chave, valor in info.items():
        if isinstance(valor, dict):
            quem = valor.get("gerado_por") or valor.get("generated_by") or valor.get("client")
            if quem:
                return {"de": "fora", "nome": str(quem)[:60], "detalhe": str(chave)[:40]}
    cliente = (extra or {}).get("client_id")
    return {"de": "fora", "nome": "De fora do painel",
            "detalhe": ("cliente " + str(cliente)[:12]) if cliente else ""}


def _e_do_painel_de_musica(extra):
    """Este trabalho da fila da ComfyUI foi mandado pelo painel de musica?

    14/11/2026: a musica passou a gerar na MESMA ComfyUI. Sem este filtro cada musica aparecia
    DUAS vezes na aba Fila e no "Ja gerado": uma vinda da ComfyUI ("de fora do painel") e outra
    vinda do painel de musica, que e quem sabe o titulo e a IA. Fica so a do painel. O painel
    carimba o clientId dele em tudo o que manda (painel_musica/server.py, CLIENTE).
    """
    return str((extra or {}).get("client_id") or "").startswith("painel-musica")


def _o_que_e(prompt):
    """O que este trabalho parece estar gerando, lido do proprio grafo.

    Nao ha campo dizendo "isto e um video": entao olhamos os modelos e os nos de saida, que
    e o que da para afirmar. Na duvida devolve vazio - melhor nao dizer do que chutar.
    """
    if not isinstance(prompt, dict):
        return {"modelos": [], "saida": ""}
    modelos, saidas = [], []
    for no in prompt.values():
        if not isinstance(no, dict):
            continue
        classe = str(no.get("class_type") or "")
        for v in (no.get("inputs") or {}).values():
            if isinstance(v, str) and v.lower().endswith((".safetensors", ".gguf", ".ckpt", ".pt")):
                modelos.append(Path(v).name)
        if "SaveImage" in classe or "PreviewImage" in classe:
            saidas.append("imagem")
        elif "VideoCombine" in classe or "SaveVideo" in classe or "SaveWEBM" in classe:
            saidas.append("video")
        elif "SaveAudio" in classe:
            saidas.append("audio")
    vistos = list(dict.fromkeys(modelos))[:4]
    return {"modelos": vistos, "saida": (saidas or [""])[0]}


_CAT_MODELOS = {"quando": 0.0, "mapa": {}}


def _ia_do_modelo(nome_arquivo):
    """De que IA e este arquivo de modelo, pelo catalogo do proprio pacote.

    07/11/2026: sem isto o titulo da fila saia "Imagem · qwen_3_4b" - que e o CODIFICADOR DE
    TEXTO do Z-Image, nao a IA. O `modelos.json` ja diz `usado_por`, entao da para nomear
    certo em vez de mostrar o primeiro arquivo que aparece no grafo.
    """
    agora = time.time()
    if agora - _CAT_MODELOS["quando"] > 300:
        mapa = {}
        for cand in (ROOT / "modelos.json", AQUI / "modelos.json",
                     ROOT / "_github" / "modelos.json"):
            try:
                if cand.is_file():
                    # o catalogo e AGRUPADO ("comfyui", "texto", "voz") - ler como se fosse
                    # plano nao achava nada e o titulo caia no nome do arquivo.
                    bruto = json.loads(cand.read_text(encoding="utf-8"))
                    for grupo in bruto.values():
                        if not isinstance(grupo, dict):
                            continue
                        for arq, d in grupo.items():
                            usado = (d or {}).get("usado_por") or []
                            if usado:
                                mapa[Path(str(arq)).name.lower()] = usado[0]
                    break
            except Exception:
                continue
        _CAT_MODELOS.update(mapa=mapa, quando=agora)
    return _CAT_MODELOS["mapa"].get(str(nome_arquivo).lower())


def _titulo_do_trabalho(meu, quem, oque):
    """Um nome que diga alguma coisa a quem olha a fila.

    "cliente 07143b39" nao diz nada. O que diz e o MODELO (z_image_turbo) e o tipo de saida
    (imagem) - e isso da para ler do proprio grafo, sem inventar.
    """
    if meu and (meu.get("ia_nome") or meu.get("preset")):
        return meu.get("ia_nome") or meu.get("preset")
    principal = ""
    # primeiro tenta pelo catalogo: ele sabe que z_image_turbo_bf16 e "Z-Image Turbo"
    for m in oque.get("modelos") or []:
        ia = _ia_do_modelo(m)
        if ia:
            principal = ia
            break
    if not principal:
        for m in oque.get("modelos") or []:
            nome = Path(str(m)).stem
            # pula peca de apoio, que nao identifica o trabalho
            if nome.lower() in ("ae", "vae", "clip_l", "t5xxl") or                nome.lower().startswith(("clip", "vae", "t5", "qwen_3", "umt5")):
                continue
            principal = nome
            break
    saida = (oque.get("saida") or "").capitalize()
    if principal and saida:
        return "%s · %s" % (saida, principal)
    return principal or saida or quem.get("detalhe") or "trabalho"


HIST_FILA = DADOS / "fila_historico.json"
TETO_HIST_FILA = 800


def _hist_fila_ler():
    """O historico proprio da Fila: {limpo_em, itens: {id: {...}}}.

    07/11/2026. Existe porque o historico da ComfyUI ROTACIONA - ela guarda os ultimos e
    joga o resto fora. Ele pediu "um historico do que foi gerado sempre", entao o nosso
    arquivo acumula, independente do que a ComfyUI ainda lembra.

    E separado do `historico.json` do painel de proposito: aquele e dos trabalhos DELE, com
    prompt e preset; este inclui o que veio de FORA (Claude, GPT, Hermes), que o painel nunca
    soube que existia.
    """
    if not HIST_FILA.is_file():
        return {"limpo_em": 0, "itens": {}}
    try:
        d = json.loads(HIST_FILA.read_text(encoding="utf-8"))
        if isinstance(d, dict) and isinstance(d.get("itens"), dict):
            return d
    except Exception as e:
        print("[estudio] historico da fila ilegivel (%s) - comecando um novo" % e, flush=True)
    return {"limpo_em": 0, "itens": {}}


def _hist_fila_gravar(d):
    itens = d.get("itens") or {}
    if len(itens) > TETO_HIST_FILA:
        # fica com os mais novos; sem teto o arquivo cresce para sempre e um dia trava a tela
        ordenados = sorted(itens.items(), key=lambda kv: kv[1].get("quando") or 0, reverse=True)
        d["itens"] = dict(ordenados[:TETO_HIST_FILA])
    _gravar(HIST_FILA, d)


async def _absorver_historico():
    """Le o que a ComfyUI ja terminou e guarda no nosso historico. Devolve quantos entraram.

    Roda a cada consulta da Fila. Um trabalho que comece E termine entre duas consultas nao
    se perde: ele continua no historico da ComfyUI, e e de la que lemos.
    """
    d = _hist_fila_ler()
    itens, limpo_em = d["itens"], d.get("limpo_em") or 0
    try:
        h = await comfy("GET", "/history?max_items=200", timeout=15)
    except Exception:
        return 0
    novos = 0
    meus = {j.get("prompt_id"): j for j in JOBS if j.get("prompt_id")}
    for pid, it in (h or {}).items():
        if pid in itens or not isinstance(it, dict):
            continue
        st = it.get("status") or {}
        quando, fim = 0, 0
        for nome, dados in (st.get("messages") or []):
            ts = int((dados or {}).get("timestamp") or 0) // 1000
            if nome == "execution_start":
                quando = ts
            elif nome in ("execution_success", "execution_error", "execution_interrupted"):
                fim = ts
        if limpo_em and quando and quando <= limpo_em:
            continue            # limpou: o que e mais velho que a limpeza nao volta
        linha = it.get("prompt") or []
        grafo = linha[2] if len(linha) > 2 else {}
        extra = linha[3] if len(linha) > 3 else {}
        if _e_do_painel_de_musica(extra):
            continue            # a musica entra logo abaixo, pelo painel (com titulo e IA)
        quem = _quem_mandou(extra)
        oque = _o_que_e(grafo)
        arquivos = []
        for saida in (it.get("outputs") or {}).values():
            for lista in (saida or {}).values():
                if isinstance(lista, list):
                    for a in lista:
                        if isinstance(a, dict) and a.get("filename"):
                            # o endereco da propria ComfyUI: o painel nao copia nem guarda
                            # os arquivos de fora, so aponta para onde eles ja estao
                            q = urllib.parse.urlencode({"filename": a["filename"],
                                                        "subfolder": a.get("subfolder") or "",
                                                        "type": a.get("type") or "output"})
                            arquivos.append({"nome": a["filename"], "pasta": a.get("subfolder") or "",
                                             "tipo": a.get("type") or "output",
                                             "url": COMFY + "/view?" + q})
        itens[pid] = {
            "id": pid, "fonte": "comfyui", "quando": quando or fim or int(time.time()),
            "fim": fim, "de": quem["de"], "quem": quem["nome"],
            "titulo": _titulo_do_trabalho(meus.get(pid), quem, oque),
            "saida": oque["saida"], "modelos": oque["modelos"],
            "deu_certo": (st.get("status_str") == "success"),
            "arquivos": arquivos[:4],
            "prompt": ((meus.get(pid) or {}).get("prompt") or "")[:160],
        }
        novos += 1

    # 09/11/2026: a musica tambem entra. Ele pediu "um historico do que foi gerado SEMPRE", e
    # depois de gerar seis musicas elas apareciam ao vivo na Fila e sumiam do "Ja gerado":
    # o absorvedor so lia a ComfyUI. O painel de musica tem fila e historico proprios.
    # Sem link do arquivo de proposito: o audio e servido pela ComfyUI de musica, que fica
    # DESLIGADA quase sempre, e um endereco que eu nao consigo provar agora viraria um botao
    # que nao abre. Titulo, motor, quando e quanto durou ja dizem o que aconteceu.
    try:
        async with aiohttp.ClientSession() as s_:
            async with s_.get(MUSICA + "/api/jobs", timeout=aiohttp.ClientTimeout(total=8)) as r:
                prontas = await r.json()
    except Exception:
        prontas = []
    for j in (prontas if isinstance(prontas, list) else []):
        estado = str(j.get("state") or "").lower()
        if estado not in ("done", "error") or j.get("id") in itens:
            continue
        quando = int(j.get("started") or j.get("created") or 0)
        if limpo_em and quando and quando <= limpo_em:
            continue
        dur = j.get("duracao_s")
        itens[j["id"]] = {
            "id": j["id"], "fonte": "musica", "quando": quando or int(time.time()),
            "fim": int(quando + (j.get("elapsed") or 0)) if quando else 0,
            "de": "musica", "quem": "Painel de música",
            "titulo": j.get("title") or "música",
            "saida": "música" + (" · %d:%02d" % (int(dur) // 60, int(dur) % 60) if dur else ""),
            "modelos": [j.get("motor_nome")] if j.get("motor_nome") else [],
            "deu_certo": estado == "done",
            "arquivos": [],
            "prompt": str(((j.get("settings") or {}).get("style") or ""))[:160],
        }
        novos += 1

    if novos:
        d["itens"] = itens
        _hist_fila_gravar(d)
    return novos


async def api_fila_historico(req):
    """O que ja foi gerado, do mais novo para o mais velho."""
    await _absorver_historico()
    d = _hist_fila_ler()
    itens = sorted(d["itens"].values(), key=lambda i: i.get("quando") or 0, reverse=True)
    try:
        quantos = int(req.query.get("quantos") or 60)
    except ValueError:
        quantos = 60
    return web.json_response({"itens": itens[:max(1, min(quantos, 400))],
                              "total": len(itens), "limpo_em": d.get("limpo_em") or 0})


async def api_fila_historico_limpar(req):
    """Apaga o NOSSO historico da fila. Nao toca no da ComfyUI nem nas imagens no disco.

    Guarda a hora da limpeza para o que ja foi apagado NAO voltar na proxima leitura - sem
    isso o botao pareceria nao funcionar, que e pior do que nao ter botao.
    """
    antes = len(_hist_fila_ler().get("itens") or {})
    _hist_fila_gravar({"limpo_em": int(time.time()), "itens": {}})
    print("[estudio] historico da fila limpo (%d itens)" % antes, flush=True)
    return web.json_response({"apagados": antes})


async def api_fila(req):
    """TUDO que esta sendo gerado agora nesta maquina, venha de onde vier.

    Tres fontes, porque cada uma tem a sua fila:
      ComfyUI (imagem/video)  - inclusive o que o Claude, o GPT ou o Hermes mandaram
      o painel de musica      - fila propria (espera a vez) e depois a MESMA ComfyUI
      a narracao              - o VoiceStudio nao tem fila: ou esta gerando, ou nao
    """
    itens = []
    # guarda o que ja terminou ANTES de olhar a fila: assim o historico anda mesmo que
    # ninguem abra a aba do historico
    try:
        await _absorver_historico()
    except Exception as e:
        print("[estudio] nao absorvi o historico da fila: %s" % e, flush=True)

    # 1) ComfyUI
    try:
        q = await comfy("GET", "/queue", timeout=10)
    except Exception as e:
        itens.append({"fonte": "comfyui", "estado": "erro",
                      "titulo": "Não consegui falar com a ComfyUI", "detalhe": str(e)[:120]})
        q = {}
    meus = {j.get("prompt_id"): j for j in JOBS if j.get("prompt_id")}
    for estado, chave in (("rodando", "queue_running"), ("fila", "queue_pending")):
        for linha in (q.get(chave) or []):
            try:
                numero, pid, prompt, extra = linha[0], linha[1], linha[2], (linha[3] if len(linha) > 3 else {})
            except Exception:
                continue
            if _e_do_painel_de_musica(extra):
                continue        # aparece no bloco da musica, logo abaixo
            quem = _quem_mandou(extra)
            oque = _o_que_e(prompt)
            meu = meus.get(pid)
            itens.append({
                "fonte": "comfyui", "estado": estado, "id": pid, "numero": numero,
                "de": quem["de"], "quem": quem["nome"],
                "titulo": _titulo_do_trabalho(meu, quem, oque),
                "saida": oque["saida"], "modelos": oque["modelos"],
                "comecou": (meu or {}).get("inicio"),
                "prompt": ((meu or {}).get("prompt") or "")[:160],
            })

    # 2) musica
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(MUSICA + "/api/jobs", timeout=aiohttp.ClientTimeout(total=8)) as r:
                musicas = await r.json()
    except Exception:
        musicas = []
    # 09/11/2026: o painel de musica marca "running" em TUDO que ele aceitou - inclusive no
    # que ainda espera a vez. Fiando-me so no "state", os tres apareciam aqui como "gerando"
    # enquanto a tela dele dizia, certissima, "Gerando / Na fila 1o / Na fila 2o".
    # Quem separa de verdade e o "started": so quem comecou tem hora de inicio. E o "created"
    # da a ordem da fila. Numero errado na tela e pior do que numero nenhum.
    vivos = [j for j in (musicas if isinstance(musicas, list) else [])
             if str(j.get("state") or "").lower() not in ("done", "error", "cancelled", "canceled")]
    vivos.sort(key=lambda j: (0 if j.get("started") else 1, j.get("created") or 0))
    lugar = 0
    for j in vivos:
        rodando = bool(j.get("started"))
        if not rodando:
            lugar += 1
        itens.append({"fonte": "musica", "estado": "rodando" if rodando else "fila",
                      "id": j.get("id"), "de": "musica", "quem": "Painel de música",
                      "numero": None if rodando else lugar,
                      "titulo": j.get("title") or "música", "saida": "música",
                      "modelos": [j.get("motor_nome") or (j.get("settings") or {}).get("engine")]
                                 if (j.get("motor_nome") or (j.get("settings") or {}).get("engine")) else [],
                      "comecou": j.get("started"), "prompt": ""})

    # 3) narracao: o VoiceStudio nao tem fila para consultar; o que sabemos e se ESTE painel
    #    esta gerando agora. Narracao mandada por fora nao aparece - e dizer isso e melhor do
    #    que fingir que a lista esta completa.
    return web.json_response({
        "itens": itens,
        "quando": int(time.time()),
        "aviso_narracao": "A narração não tem fila para consultar: só aparece aqui o que este "
                          "painel está gerando.",
    })


async def api_voz_previsao(req):
    """Quanto deve demorar, para a tela poder mostrar a barra e o tempo que falta."""
    try:
        letras = int(req.query.get("letras") or 0)
    except ValueError:
        letras = 0
    seg, amostras, frio = _prever_voz(letras)
    return web.json_response({"segundos": seg, "amostras": amostras, "frio": frio})


async def api_voz_falar(req):
    b = await req.json()
    texto_falar = (b.get("texto") or "").strip()
    if not texto_falar:
        raise web.HTTPBadRequest(text="Escreva o texto da narração.")
    if len(texto_falar) > 20000:
        raise web.HTTPBadRequest(text="Texto muito longo. Quebre em blocos — é assim que a "
                                      "narração é montada de qualquer jeito.")
    ajustes = {k: b.get(k) for k in ("speed", "temperature", "cfg", "top_p") if b.get(k) is not None}
    VOZ_SAIDA.mkdir(parents=True, exist_ok=True)
    nome = "voz_%s_%s.wav" % (datetime.now().strftime("%Y%m%d_%H%M%S"), uuid.uuid4().hex[:6])
    try:
        r = await voz_studio.falar(texto_falar, VOZ_SAIDA / nome, b.get("voz") or None,
                                   b.get("idioma") or "pt", "wav", ajustes)
    except Exception as e:
        raise web.HTTPBadGateway(text=str(e)[:300])
    r["url"] = "/api/voz/audio/" + nome
    r["arquivo"] = nome
    # 07/11/2026: a narracao sempre foi gravada em disco, mas a tela nao mostrava as de antes
    # - voce gerava, ouvia, saia da aba e ela sumia (27 arquivos orfaos quando ele reclamou).
    # Agora cada uma leva uma FICHA ao lado, com o texto falado e a voz: sem o texto a lista
    # seria 27 linhas de "voz_20261106_191753", que nao diz nada a ninguem.
    try:
        ficha = {"texto": texto_falar[:2000], "voz": b.get("voz") or "",
                 "idioma": b.get("idioma") or "pt", "segundos": r.get("segundos"),
                 "quando": int(time.time())}
        (VOZ_SAIDA / (Path(nome).stem + ".json")).write_text(
            json.dumps(ficha, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        # a ficha e conforto, nao a narracao: se falhar, o audio ja esta salvo e vale mais
        print("[estudio] nao gravei a ficha da narracao: %s" % e, flush=True)
    # A conta de "13,2 letras por segundo" é estimativa; o áudio é quem confirma. Devolvemos as
    # duas para a tela mostrar o erro da estimativa — é o que serve para encaixar os @segundo.
    r["letras"] = len(texto_falar)
    r["estimado"] = round(len(texto_falar) / 13.2, 1)
    # 07/11/2026: ele clicou em Gerar e ficou sem saber quanto falta. Para prever e preciso
    # ter medido antes - entao cada narracao entra no MESMO tempos.json que ja da o ETA das
    # imagens e videos. Guardamos tambem se o motor estava FRIO, porque a primeira geracao
    # depois de um tempo parado custou 272 s para 2,7 s de audio, e as seguintes, segundos:
    # misturar as duas faria a previsao mentir nos dois sentidos.
    try:
        frio = time.time() - _ultima_narracao() > 600
        STATS.setdefault("voz|frio" if frio else "voz|quente", []).append(
            {"total": r.get("demorou"), "letras": len(texto_falar),
             "audio_s": r.get("segundos"), "quando": int(time.time())})
        STATS["voz|frio" if frio else "voz|quente"] =             STATS["voz|frio" if frio else "voz|quente"][-40:]
        _voz_ultima["quando"] = time.time()
        salvar()
    except Exception as e:
        print("[estudio] nao guardei o tempo da narracao: %s" % e, flush=True)
    return web.json_response(r)


async def api_voz_audio(req):
    arq = VOZ_SAIDA / Path(req.match_info["nome"]).name
    if not _dentro(arq, VOZ_SAIDA) or not arq.is_file():
        raise web.HTTPNotFound()
    return web.FileResponse(arq, headers={"Cache-Control": "no-cache"})


# ===================================================================== CANAL AUTOMÁTICO
# A esteira inteira de um vídeo narrado numa tela só. Ver canal.py para as etapas e para
# por que a conta de tempo aparece ANTES de a fila começar.
def _canal_raiz():
    return canal.pasta_canal(ler_pref())


async def _pedir_texto(tarefa, entrada):
    """A IA de texto do próprio estúdio (local). Ela mesma decide placa ou processador
    conforme a fila — por isso dá para usar enquanto um vídeo está sendo gerado."""
    return await TEXTO.pedir(tarefa, entrada, {}, None, placa_ocupada_para_texto,
                             pasta_input=COMFY_DIR / "input")


def _fila_com_o_de_fora():
    """O estado da fila DA ABA mais o que estiver rodando por fora.

    A esteira também pode ser disparada por um .bat, e aí a aba dizia "nada rodando" com um
    vídeo sendo feito na frente dela. Tela que mente sobre o que está acontecendo é pior que
    tela sem informação: ele clicaria em "fazer" achando que a placa está livre.
    """
    f = canal.fila_estado()
    if not f["rodando"]:
        ativo = next((j for j in trabalhos_ativos()
                      if "presentador" in str((j.get("ia") or {}).get("nome") or j.get("nome") or "")), None)
        if ativo:
            f["rodando"] = True
            f["por_fora"] = True
            f["agora"] = "um vídeo começado por fora da aba"
            f["desde"] = max(0.0, time.time() - float(ativo.get("criado") or time.time()))
    return f


async def api_canal_listar(req):
    raiz = _canal_raiz()
    vids = await asyncio.to_thread(canal.listar, raiz)
    return web.json_response({"pasta": str(raiz), "existe": raiz.is_dir(),
                              "videos": vids, "fila": _fila_com_o_de_fora()})


async def api_canal_criar(req):
    b = await req.json()
    try:
        novo = await asyncio.to_thread(canal.criar, _canal_raiz(),
                                       b.get("titulo") or "", b.get("texto") or "")
    except ValueError as e:
        raise web.HTTPBadRequest(text=str(e))
    return web.json_response(novo)


async def api_canal_cenas_sugerir(req):
    b = await req.json()
    texto_narr = (b.get("texto") or "").strip()
    if not texto_narr:
        nome = b.get("nome") or ""
        arq = _canal_raiz() / "explicativos" / Path(nome).name / "narracao.txt"
        if arq.is_file():
            texto_narr = arq.read_text(encoding="utf-8")
    if not texto_narr:
        raise web.HTTPBadRequest(text="Sem texto para ler.")
    try:
        itens = await canal.sugerir_cenas(_pedir_texto, texto_narr, int(b.get("quantas") or 6))
    except Exception as e:
        raise web.HTTPBadGateway(text=str(e)[:300])
    return web.json_response({"itens": itens})


async def api_canal_cenas_gravar(req):
    b = await req.json()
    raiz = _canal_raiz()
    pasta = raiz / "explicativos" / Path(b.get("nome") or "").name
    if not pasta.is_dir():
        raise web.HTTPBadRequest(text="Não achei o vídeo.")
    itens = b.get("itens") or []
    if not itens:
        raise web.HTTPBadRequest(text="Sem cenas para gravar.")
    try:
        saida = await asyncio.to_thread(canal.escrever_cenas, raiz, pasta, itens)
    except Exception as e:
        raise web.HTTPBadGateway(text=str(e)[:400])
    return web.json_response({"relato": saida, "video": canal.estado_video(pasta)})


async def api_canal_conta(req):
    b = await req.json()
    nomes = [Path(n).name for n in (b.get("nomes") or [])]
    if not nomes:
        raise web.HTTPBadRequest(text="Escolha pelo menos um vídeo.")
    return web.json_response(await asyncio.to_thread(canal.conta_da_fila, _canal_raiz(), nomes))


async def api_canal_fila(req):
    if req.method == "GET":
        return web.json_response(_fila_com_o_de_fora())
    b = await req.json()
    if b.get("parar"):
        return web.json_response(canal.parar_fila())
    if _fila_com_o_de_fora().get("por_fora"):
        raise web.HTTPBadRequest(text="Já tem um vídeo sendo feito por fora da aba (um .bat, "
                                      "por exemplo). Espere ele terminar — a regra da casa é "
                                      "uma geração por vez.")
    nomes = [Path(n).name for n in (b.get("nomes") or [])]
    if not nomes:
        raise web.HTTPBadRequest(text="Escolha pelo menos um vídeo.")
    try:
        est = canal.comecar_fila(_canal_raiz(), nomes, LOGS_DIR / "canal_fila.log")
    except Exception as e:
        raise web.HTTPBadRequest(text=str(e)[:300])
    return web.json_response(est)


async def ciclo(app):
    tarefas = [asyncio.create_task(ouvir_comfy()), asyncio.create_task(vigia()),
               asyncio.create_task(nos_ao_iniciar()),  # o nó da música na custom_nodes da ComfyUI
               asyncio.create_task(reparar_ao_iniciar()), asyncio.create_task(TEXTO.vigiar()),
               asyncio.create_task(religar_depois_do_reparo()),
               asyncio.create_task(ligar_texto_ao_iniciar()),
               asyncio.create_task(renovar_licenca_de_vez_em_quando())]  # "sempre ligada": ~20 s depois, em segundo plano
    yield
    for t in tarefas:
        t.cancel()
    if TEXTO.tarefa_ligar and not TEXTO.tarefa_ligar.done():
        TEXTO.tarefa_ligar.cancel()
    TEXTO.parar_tudo()  # os llama-server também fecham sozinhos (Job do Windows) se o estúdio cair


async def api_pastas(req):
    """[C] Onde as coisas ficam NESTA maquina - para a IA de codigo de quem instalou.

    Nasceu em 07/11/2026 de uma pergunta do dono: "as imagens ficam no local que ele vai
    usar?". Nao ficam. A ComfyUI salva na pasta DELA, e a narracao numa terceira. A IA de
    fora nao tem como adivinhar isso, e o atalho .bat que ela escreve com o caminho chutado
    quebra na maquina de quem instalou - foi exatamente a falha de portabilidade de 04/11,
    quando o codigo levava o nome das pastas do dono dentro.

    Por isso o caminho se PERGUNTA, nunca se escreve no atalho. Nao e CORS-liberado (so as
    4 rotas da lista), entao pagina de terceiro no navegador nao le esta resposta.
    """
    return web.json_response({
        "instalacao": str(ROOT),
        "saida_imagens": str(COMFY_DIR / "output" / "estudio"),
        "saida_comfyui": str(COMFY_DIR / "output"),
        "saida_narracao": str(VOZ_SAIDA),
        "aviso": "Nao escreva estes caminhos dentro do atalho: pergunte aqui cada vez que ele rodar. "
                 "O jeito certo de pegar um arquivo pronto e baixar por GET /api/midia/{id}/{i}, "
                 "que funciona em qualquer instalacao. A pasta so serve para procurar arquivo orfao "
                 "quando o estudio cai no meio de um trabalho.",
    })


app = web.Application(client_max_size=1024 ** 3, middlewares=[portao, cors_painel])
app.cleanup_ctx.append(ciclo)
app.add_routes([
    web.get("/api/ias", api_ias), web.post("/api/ias/instalar", api_ias_instalar),
    web.get("/api/ias/destino", api_ias_destino), web.post("/api/ias/destino", api_ias_destino),
    web.post("/api/motor/instalar", api_motor_instalar), web.post("/api/motor/parar", api_motor_parar),
    web.get("/api/requisitos", api_requisitos), web.post("/api/requisitos/instalar", api_requisitos_instalar),
    web.post("/api/requisitos/parar", api_requisitos_parar),
    web.get("/api/ias/progresso", api_ias_progresso),
    web.post("/api/ias/parar", api_ias_parar),
    web.get("/api/presets", api_presets), web.get("/api/fichas", api_fichas),
    web.get("/api/conta/estado", api_conta_estado),
    web.get("/api/atualizacao/estado", api_atualizacao_estado),
    web.post("/api/atualizacao/aplicar", api_atualizacao_aplicar),
    web.post("/api/conta/criar", api_conta_criar),
    web.post("/api/conta/entrar", api_conta_entrar),
    web.post("/api/conta/codigo", api_conta_codigo),
    web.post("/api/conta/recuperar", api_conta_recuperar),
    web.post("/api/conta/senha-por-codigo", api_conta_senha_por_codigo),
    web.post("/api/conta/reenviar-codigo", api_conta_reenviar_codigo),
    web.post("/api/conta/sair", api_conta_sair),
    web.get("/api/novidades", api_novidades), web.post("/api/upload", api_upload),
    web.get("/api/entrada/{nome}", api_entrada), web.post("/api/gerar", api_gerar), web.post("/api/enquadrar", api_enquadrar),
    web.get("/api/trabalhos", api_jobs), web.post("/api/cancelar/{id}", api_cancelar),
    web.get("/api/estimativa", api_estimativa),
    web.post("/api/remover/{id}", api_remover), web.post("/api/limpar-lixeira", api_limpar_lixeira),
    web.get("/api/midia/{id}/{i}", api_midia),
    web.get("/api/vozes", api_vozes), web.get("/api/vozes11", api_vozes11), web.post("/api/vozes", api_voz_salvar),
    web.get("/api/chaves", api_chaves),
    web.post("/api/chaves", api_chaves),
    web.get("/api/chave-nuvem", api_chave_nuvem),
    web.post("/api/chave-nuvem", api_chave_nuvem),
    web.post("/api/vozes/remover/{id}", api_voz_remover),
    web.get("/api/sistema", api_sistema), web.get("/api/inicio", api_inicio), web.get("/api/ocupado", api_ocupado),
    web.get("/api/pastas", api_pastas),
    web.post("/api/liberar-memoria", api_liberar_memoria), web.post("/api/musica/ligar", api_musica_ligar),
    web.post("/api/texto", api_texto), web.options("/api/texto", api_texto_opcoes),
    web.get("/api/texto/estado", api_texto_estado),
    web.post("/api/texto/ligar", api_texto_ligar), web.post("/api/texto/desligar", api_texto_desligar),
    web.post("/api/servicos/ligar", api_servicos_ligar), web.post("/api/servicos/desligar", api_servicos_desligar),
    web.post("/api/reparar", api_reparar),
    web.get("/api/preferencias", api_preferencias), web.post("/api/preferencias", api_preferencias),
    web.get("/api/voz/estado", api_voz_estado), web.post("/api/voz/falar", api_voz_falar),
    web.get("/api/voz/previsao", api_voz_previsao),
    web.get("/api/fila", api_fila),
    web.get("/api/fila/historico", api_fila_historico),
    web.post("/api/fila/historico/limpar", api_fila_historico_limpar),
    web.post("/api/voz/descrever", api_voz_descrever), web.post("/api/voz/desenhar", api_voz_desenhar),
    web.post("/api/voz/clonar", api_voz_clonar),
    web.post("/api/voz/conferir-ref", api_voz_conferir_ref),
    web.post("/api/voz/transcrever-ref", api_voz_transcrever_ref),
    web.post("/api/voz/apagar", api_voz_apagar),
    web.get("/api/voz/gravadas", api_voz_gravadas),
    web.post("/api/voz/gravadas/apagar", api_voz_gravada_apagar), web.get("/api/voz/audio/{nome}", api_voz_audio),
    web.post("/api/voz/ligar", api_voz_ligar),
    web.get("/api/canal/listar", api_canal_listar), web.post("/api/canal/criar", api_canal_criar),
    web.post("/api/canal/cenas/sugerir", api_canal_cenas_sugerir),
    web.post("/api/canal/cenas/gravar", api_canal_cenas_gravar),
    web.post("/api/canal/conta", api_canal_conta),
    web.get("/api/canal/fila", api_canal_fila), web.post("/api/canal/fila", api_canal_fila),
    web.get("/", estatico), web.get("/{caminho:.+}", estatico),
])

# ------------------------------------------------------- o icone, na primeira subida
MARCA_DO_ICONE = AQUI / "icone_feito.json"


def _icone_na_primeira_subida():
    r"""Poe o icone do Forja Studio na Area de Trabalho, uma unica vez.

    POR QUE AQUI, e nao so no setup.py (12/11/2026)

    Instalaram o estudio numa maquina por uma IA: ela fez `pip install` e rodou o
    `server.py`, sem passar pelo `setup.py`. O painel subiu redondo e o icone nao
    existia - porque ele so nascia em dois lugares que da para pular: dentro do setup,
    e num .bat que alguem precisa clicar.

    Subir o estudio e a unica coisa que ninguem pula. Entao e daqui que ele nasce.

    UMA VEZ SO: depois da primeira tentativa fica o `icone_feito.json` e nunca mais se
    mexe na Area de Trabalho de ninguem. Se a pessoa apagar o icone, apagar e a
    resposta dela - recriar toda vez seria teimosia, nao ajuda.
    """
    try:
        if os.name != "nt" or MARCA_DO_ICONE.exists():
            return
        sys.path.insert(0, str(AQUI))
        import atalho

        mesa = atalho._area_de_trabalho()
        if mesa and (mesa / "Forja Studio.lnk").exists():
            feito, motivo = str(mesa / "Forja Studio.lnk"), "ja existia"
        else:
            caminho = atalho.criar(mesa)
            feito = str(caminho) if caminho else None
            motivo = None if caminho else (atalho.ultimo_motivo or "sem motivo conhecido")

        MARCA_DO_ICONE.write_text(json.dumps(
            {"quando": int(time.time()), "icone": feito, "motivo": motivo},
            ensure_ascii=False, indent=1), encoding="utf-8")

        if feito:
            print(f"[estudio] icone do Forja Studio na Area de Trabalho: {feito}",
                  flush=True)
        else:
            print(f"[estudio] nao criei o icone na Area de Trabalho: {motivo}", flush=True)
            print("[estudio]   para tentar de novo: apague estudio\\icone_feito.json e "
                  "clique em 'Criar o icone na Area de Trabalho.bat'", flush=True)
    except Exception as exc:
        # O icone e um conforto, nao o produto: ele nunca pode derrubar o estudio.
        print(f"[estudio] tropecei ao criar o icone ({exc.__class__.__name__}: {exc}); "
              "o estudio segue normalmente", flush=True)


if __name__ == "__main__":
    # Em segundo plano para nao atrasar a primeira tela: a leitura da Area de Trabalho
    # e o PowerShell do atalho levam cerca de meio segundo juntos.
    threading.Thread(target=_icone_na_primeira_subida, daemon=True).start()
    web.run_app(app, host="127.0.0.1", port=PORTA)
