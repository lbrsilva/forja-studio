"""IA de texto do Estúdio Local — llama.cpp oficial (llama-server), 100% local (criado em 23/09/2026).

Dois servidores, que o ESTÚDIO liga e desliga sob demanda (como o painel faz com o ACE-Step):
  placa (GPU):       _ferramentas\\llama.cpp\\gpu\\llama-server.exe em modo roteador (modelos_texto\\modelos.ini),
                     127.0.0.1:8180 — "rapido" (Qwen3.5-9B, com visão) e "principal" (Qwen3.6-35B-A3B)
  processador (CPU): _ferramentas\\llama.cpp\\cpu\\llama-server.exe só com o 9B (+ visão), 127.0.0.1:8181.
                     É a build SÓ de processador: não abre nada na placa de vídeo.

Regra da placa (contrato com o painel de música):
  - placa LIVRE   -> roda na placa; o estúdio responde ocupado=true enquanto roda; terminou -> POST /models/unload NA
                     HORA e confere no nvidia-smi que a memória voltou (se não voltou, encerra o roteador inteiro).
  - placa OCUPADA -> roda no processador com o 9B, sem esperar e sem marcar ocupado (texto é curto).
  - antes de QUALQUER envio para 8188/8189/8193: garantir_fora_da_placa() (espera o texto que estiver na placa e
    descarrega o que tiver sobrado).
Os processos ficam num "Job" do Windows: se o estúdio fechar (ou cair), os llama-server fecham junto.

"Sempre pronta" (Home com botões de ligar, 23/09/2026): ligar_processador() liga o servidor do PROCESSADOR com o
Qwen3.5-9B já carregado (só RAM, ~8 GB, nada na placa), faz um pedido mínimo de aquecimento e marca manter=True
(o vigia não desliga por ociosidade enquanto estiver marcado). desligar() fecha os dois servidores e desmarca.
A regra da placa não muda: pedido com a placa livre roda na placa e descarrega no fim.

Variáveis de ambiente (opcionais):
  ESTUDIO_TEXTO_PORTA_GPU        porta do roteador na placa (padrão 8180; testes usam 8195–8199)
  ESTUDIO_TEXTO_PORTA_CPU        porta do servidor do processador (padrão 8181)
  ESTUDIO_TEXTO_CPU_OCIOSO_MIN   minutos sem uso até desligar o servidor do processador (padrão 10; não vale com
                                 "manter ligada")
  ESTUDIO_TEXTO_GPU_OCIOSO_MIN   minutos sem uso até desligar o roteador da placa (padrão 10; o modelo já sai no fim
                                 de cada pedido, isto só fecha o processo vazio)
  ESTUDIO_LOGS                   pasta dos logs llama_*.log (padrão outputs\\; testes usam outra)
"""
import asyncio
import base64
import ctypes
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

import aiohttp

import plataforma

AQUI = Path(__file__).resolve().parent
ROOT = AQUI.parent
LLAMA = ROOT / "_ferramentas" / "llama.cpp"


def _exe_llama(variante):
    """No Windows, o pacote traz um llama-server por variante. No macOS (Metal) um so serve aos dois:
    o da pasta do projeto, ou o que o Homebrew instalou (brew install llama.cpp)."""
    nome = plataforma.exe("llama-server")
    proprio = LLAMA / variante / nome
    if plataforma.WIN or proprio.is_file():
        return proprio
    for candidato in (LLAMA / nome, shutil.which("llama-server")):
        if candidato and Path(candidato).is_file():
            return Path(candidato)
    return proprio


EXE_GPU = _exe_llama("gpu")
EXE_CPU = _exe_llama("cpu")
MODELOS_DIR = ROOT / "modelos_texto"
MODELOS_INI = MODELOS_DIR / "modelos.ini"
LOGS = Path(os.environ["ESTUDIO_LOGS"]) if os.environ.get("ESTUDIO_LOGS") else ROOT / "outputs"
CACHE = ROOT / "_cache"
LIMITE_LOG = 20 * 1024 * 1024

PORTA_GPU = int(os.environ.get("ESTUDIO_TEXTO_PORTA_GPU") or 8180)
PORTA_CPU = int(os.environ.get("ESTUDIO_TEXTO_PORTA_CPU") or 8181)
URL_GPU = f"http://127.0.0.1:{PORTA_GPU}"
URL_CPU = f"http://127.0.0.1:{PORTA_CPU}"


def _min_env(nome, padrao):
    try:
        return float(os.environ.get(nome) or padrao)
    except ValueError:
        return float(padrao)


CPU_OCIOSO_S = _min_env("ESTUDIO_TEXTO_CPU_OCIOSO_MIN", 10) * 60
GPU_OCIOSO_S = _min_env("ESTUDIO_TEXTO_GPU_OCIOSO_MIN", 10) * 60

# Papéis -> modelos (os nomes dos blocos do modelos.ini são os papéis)
MODELOS = {
    "rapido": {"nome": "Qwen3.5-9B", "pasta": "qwen3.5-9b", "arquivo": "Qwen3.5-9B-UD-Q4_K_XL.gguf",
               "mmproj": "mmproj-F16.gguf", "licenca": "Apache 2.0",
               # memória livre que a placa precisa ter (medido em 23/09/2026: ~7,5 GB com visão e contexto de 16 mil)
               "vram_mib": 7800},
    "principal": {"nome": "Qwen3.6-35B-A3B", "pasta": "qwen3.6-35b-a3b", "arquivo": "Qwen3.6-35B-A3B-UD-IQ3_XXS.gguf",
                  "mmproj": None, "licenca": "Apache 2.0",
                  # medido: ~13,0 GB na placa (KV q4_0, contexto de 16 mil, sem visão). Com 12,8–13 GB livres o --fit
                  # deixa um pouco dos especialistas na RAM (fica mais lento); abaixo disso o 9B roda na placa no lugar
                  "vram_mib": 12800},
}
TAREFAS = ("melhorar_prompt", "letra", "roteiro", "canal_roteiro", "canal_personagens", "traduzir",
           "descrever_imagem", "livre", "contexto")
PAPEL_PADRAO = {"melhorar_prompt": "rapido", "letra": "principal", "roteiro": "principal", "canal_roteiro": "principal",
                "canal_personagens": "rapido", "traduzir": "rapido", "descrever_imagem": "rapido",
                "livre": "principal", "contexto": "rapido"}
MAX_TOKENS = {"melhorar_prompt": 220,   # 70 palavras cabem em ~140; 220 e a rede de seguranca "letra": 1400, "roteiro": 1800, "traduzir": 2500, "descrever_imagem": 500,
              "livre": 1200, "contexto": 3000, "canal_roteiro": 3000, "canal_personagens": 1600}
ENTRADA_MAX = 12000  # caracteres


class ErroTexto(Exception):
    """Erro com mensagem em português para mostrar na tela."""

    def __init__(self, msg, status=400):
        super().__init__(msg)
        self.status = status


# ---------------------------------------------------------------- Job do Windows (os filhos fecham com o estúdio)
class _JobWindows:
    """Job object com KILL_ON_JOB_CLOSE: tudo o que estiver nele fecha quando o estúdio fechar (ou cair) e
    matar() encerra a árvore inteira (o roteador e os processos de modelo que ele abriu)."""

    def __init__(self):
        self.h = None
        try:
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.CreateJobObjectW.restype = wintypes.HANDLE
            k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
            k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
            k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
            k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
            k32.CloseHandle.argtypes = [wintypes.HANDLE]
            self.k32 = k32

            class IO(ctypes.Structure):
                _fields_ = [(n, ctypes.c_ulonglong) for n in ("a", "b", "c", "d", "e", "f")]

            class BASICA(ctypes.Structure):
                _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                            ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                            ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                            ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                            ("SchedulingClass", wintypes.DWORD)]

            class ESTENDIDA(ctypes.Structure):
                _fields_ = [("Basic", BASICA), ("IoInfo", IO), ("ProcessMemoryLimit", ctypes.c_size_t),
                            ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                            ("PeakJobMemoryUsed", ctypes.c_size_t)]

            h = k32.CreateJobObjectW(None, None)
            if not h:
                return
            info = ESTENDIDA()
            info.Basic.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not k32.SetInformationJobObject(h, 9, ctypes.byref(info), ctypes.sizeof(info)):
                k32.CloseHandle(h)
                return
            self.h = h
        except Exception as exc:  # sem o Job, os processos ainda são encerrados pelo estúdio (só não na queda)
            print(f"[texto] não consegui criar o Job do Windows: {exc}", flush=True)

    def colocar(self, proc):
        if self.h:
            try:
                self.k32.AssignProcessToJobObject(self.h, int(proc._handle))
            except Exception as exc:
                print(f"[texto] não consegui pôr o processo no Job: {exc}", flush=True)

    def matar(self):
        if self.h:
            try:
                self.k32.TerminateJobObject(self.h, 1)
                self.k32.CloseHandle(self.h)
            except Exception:
                pass
            self.h = None


_VIGIA = (
    "import os,sys,time,signal\n"
    "pai,grupo=int(sys.argv[1]),int(sys.argv[2])\n"
    "def vivo(p):\n"
    "    try:\n"
    "        os.kill(p,0)\n"
    "        return True\n"
    "    except ProcessLookupError:\n"
    "        return False\n"
    "    except PermissionError:\n"
    "        return True\n"
    "while vivo(pai) and vivo(grupo):\n"
    "    time.sleep(2)\n"
    "if not vivo(pai):\n"
    "    try:\n"
    "        os.killpg(grupo,signal.SIGKILL)\n"
    "    except OSError:\n"
    "        pass\n")


class _JobPosix:
    """O mesmo contrato do Job do Windows, com grupo de processos: matar() encerra a árvore inteira, e um vigia
    separado faz o mesmo se o estúdio cair (o macOS não tem KILL_ON_JOB_CLOSE)."""

    def __init__(self):
        self.grupo = None

    def colocar(self, proc):
        self.grupo = proc.pid  # o processo foi aberto com start_new_session: ele é líder do próprio grupo
        try:
            subprocess.Popen([sys.executable, "-c", _VIGIA, str(os.getpid()), str(proc.pid)],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        except OSError as exc:
            print(f"[texto] não consegui abrir o vigia do servidor de texto: {exc}", flush=True)

    def matar(self):
        if self.grupo:
            try:
                os.killpg(self.grupo, signal.SIGKILL)
            except OSError:
                pass
            self.grupo = None


_Job = _JobWindows if plataforma.WIN else _JobPosix


# ---------------------------------------------------------------- utilidades
def _ambiente():
    """Variáveis de cache/temporários no E: (o CUDA compila e guarda o cache em CUDA_CACHE_PATH). HF_HOME aponta
    para uma pasta vazia só do llama.cpp: assim o roteador não lista como 'modelo' o que está no cache do Hugging
    Face (Chatterbox, Whisper...). Nada é baixado: os .gguf ficam em modelos_texto e são indicados no modelos.ini."""
    env = dict(os.environ)
    pastas = {"TEMP": "temp", "TMP": "temp", "CUDA_CACHE_PATH": "cuda", "XDG_CACHE_HOME": "xdg",
              "LLAMA_CACHE": "llama.cpp", "HF_HOME": "llama.cpp/hf"}
    for nome, sub in pastas.items():
        p = CACHE / sub
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        env[nome] = str(p)
    env["CUDA_CACHE_MAXSIZE"] = "4294967296"
    env["HF_HUB_OFFLINE"] = "1"
    env["HF_HUB_DISABLE_TELEMETRY"] = "1"
    return env


def _abrir_log(nome):
    arq = LOGS / nome
    try:
        LOGS.mkdir(exist_ok=True)
        if arq.exists() and arq.stat().st_size > LIMITE_LOG:
            os.replace(arq, arq.with_name(arq.name + ".1"))
    except OSError:
        pass
    f = open(arq, "ab")
    f.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} estúdio ligou este servidor =====\n".encode("utf-8"))
    f.flush()
    return f


def _cauda_log(nome, linhas=12):
    try:
        txt = (LOGS / nome).read_bytes()[-6000:].decode("utf-8", "replace")
        return "\n".join(txt.splitlines()[-linhas:])
    except OSError:
        return ""


async def _http(metodo, url, timeout=10, **kw):
    """(status, json|texto) — nunca levanta erro de conexão: devolve (None, None)."""
    try:
        async with aiohttp.ClientSession() as s:
            async with s.request(metodo, url, timeout=aiohttp.ClientTimeout(total=timeout), **kw) as r:
                txt = await r.text()
                try:
                    return r.status, json.loads(txt) if txt else {}
                except ValueError:
                    return r.status, txt
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
        return None, None


async def vram_mib():
    """(usada, livre) em MiB pelo nvidia-smi (no macOS, pela memória unificada), ou (None, None)."""
    if not plataforma.WIN:
        info = plataforma.gpu_unificada() if plataforma.MAC else None
        if not info:
            return None, None
        _, total, livre = info
        return (total - livre) // 1024 ** 2, livre // 1024 ** 2
    try:
        proc = await asyncio.create_subprocess_exec(
            "nvidia-smi", "--query-gpu=memory.used,memory.free", "--format=csv,noheader,nounits",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            creationflags=plataforma.NO_WINDOW)
        out, _ = await asyncio.wait_for(proc.communicate(), 8)
        usada, livre = (int(x) for x in out.decode().strip().splitlines()[0].split(","))
        return usada, livre
    except Exception:
        return None, None


def _matar_llama_na_porta(porta):
    """Encerra o llama-server DESTE projeto (_ferramentas\\llama.cpp) que estiver escutando na porta — um servidor
    'externo', que sobrou de antes e que o estúdio não ligou. Nunca encerra outro programa. True se encerrou algo."""
    try:
        import psutil
    except ImportError:
        return False
    alvo = str(LLAMA).lower()
    matou = False
    for pid in plataforma.pids_escutando(porta):
        try:
            p = psutil.Process(pid)
            if p.name().lower() != plataforma.exe("llama-server") or not (
                    (p.exe() or "").lower().startswith(alvo)
                    or os.path.realpath(p.exe() or "") in (os.path.realpath(EXE_GPU), os.path.realpath(EXE_CPU))):
                continue
            for filho in p.children(recursive=True):  # o roteador da placa abre um processo por modelo
                try:
                    filho.kill()
                except psutil.Error:
                    pass
            p.kill()
            matou = True
            print(f"[texto] servidor de texto que sobrou na porta {porta} encerrado (processo {pid}).", flush=True)
        except psutil.Error:
            pass
    return matou


def _sem_acento(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


# ---------------------------------------------------------------- manuais (prompts de sistema em português)
REGRA_SO_TEXTO = ("Responda SOMENTE com o texto pedido: sem título, sem introdução, sem comentários, sem explicações, "
                  "sem markdown e sem aspas em volta.")

# como escrever para cada IA de destino (id do preset -> manual)
GUIA_FOTO = ("É uma IA de FOTO realista. Escreva como a descrição de uma fotografia: o sujeito principal e o que ele "
             "faz, aparência e roupa, o ambiente, a hora do dia e a luz (direção, cor, suavidade), o enquadramento e a "
             "lente (ex.: close-up, 35mm, shallow depth of field), texturas e detalhes. Frases corridas. 60 a 120 "
             "palavras.")
GUIAS = {
    "z_image_turbo": GUIA_FOTO,
    "qwen_image_2512": GUIA_FOTO + " Esta IA também escreve textos curtos na imagem: se o usuário pediu uma frase "
                                   "escrita, ponha a frase entre aspas duplas exatamente como ele escreveu.",
    "flux2_dev": GUIA_FOTO,
    "krea2": ("É uma IA de ILUSTRAÇÃO com visual de cinema. Descreva a cena como uma obra de arte: sujeito e ação, "
              "cenário, composição, paleta de cores, luz e clima, técnica (pinceladas, traço, textura). 50 a 100 "
              "palavras."),
    "krea2_img2img": ("Esta IA TRANSFORMA uma imagem enviada. Descreva o RESULTADO desejado (estilo, materiais, "
                      "cores, clima) sem redescrever a composição em detalhe. 30 a 70 palavras."),
    "ideogram4": ("É uma IA de CARTAZ/CAPA/LOGO que escreve texto dentro da imagem. Toda frase que deve aparecer "
                  "escrita fica entre aspas duplas, EXATAMENTE como o usuário escreveu (NÃO traduza o que vai escrito "
                  "na arte; se ele pediu um título sem aspas, ponha o título dele entre aspas no idioma original). "
                  "Diga onde cada texto fica (topo, centro, rodapé), o tamanho relativo, a tipografia (ex.: bold "
                  "sans-serif, elegant serif, handwritten script), as cores, o layout e o fundo ou ilustração. "
                  "50 a 110 palavras."),
    "hidream_o1": ("Descreva a CENA FINAL exatamente como deve aparecer na imagem pronta (não descreva passos nem "
                   "pedidos de edição): sujeito, ação, ambiente, luz, estilo visual e detalhes. 50 a 100 palavras."),
    "fasth3": ("É uma IA de VÍDEO curto que gera o SOM junto. Um plano só, UMA ação principal simples e clara do começo "
               "ao fim. Diga o movimento de câmera (ex.: slow dolly in, static shot, handheld), a luz e o clima, e "
               "descreva os SONS (ambiente, efeitos, música; fala entre aspas, se houver, no idioma original). Evite "
               "várias ações e cortes. 60 a 110 palavras."),
    "minimax_h3_r2v": ("É uma IA de VÍDEO com SOM que usa imagens de referência. Mantenha as etiquetas <Picture 1>, "
                       "<Picture 2>... exatamente como estão, dizendo o papel de cada uma. Um plano só, UMA ação "
                       "simples, movimento de câmera, luz e os SONS (ambiente, efeitos; fala entre aspas no idioma "
                       "original). 60 a 110 palavras."),
    "wan22_5b": ("É uma IA de VÍDEO curto (5 s) sem som. Um plano só, uma ação simples e contínua, movimento de câmera, "
                 "luz e estilo visual. 50 a 90 palavras."),
    "hunyuan15_i2v": ("O vídeo COMEÇA da imagem enviada: descreva só o que ACONTECE (movimento do sujeito, da câmera, "
                      "mudanças de luz), sem redescrever a imagem. 30 a 70 palavras."),
    "wan_animate": ("O movimento vem de um vídeo de referência: descreva só o personagem e o cenário, em poucas "
                    "palavras. 20 a 50 palavras."),
    "apresentador": ("É o cenário de uma pessoa falando para a câmera (LTX-2.3). Descreva a cena: a pessoa, o "
                     "ambiente, a luz e a câmera (parada ou quase parada). 30 a 60 palavras."),
}
GUIA_GENERICO = ("Descreva sujeito, ação, cenário, luz, câmera/enquadramento e estilo visual em frases corridas. "
                 "50 a 100 palavras.")


def _nome_ia(ficha, contexto):
    return (ficha or {}).get("nome") or contexto.get("ia") or contexto.get("preset") or "IA de imagem/vídeo"


def sistema_melhorar(ficha, contexto):
    pid = contexto.get("preset") or ""
    guia = GUIAS.get(pid, GUIA_GENERICO)
    partes = [
        "Você reescreve pedidos de geração de imagem e vídeo para uma IA específica. O usuário escreve em português, "
        "às vezes com pressa ou com erros.",
        f"IA de destino: {_nome_ia(ficha, contexto)}.",
        f"Como escrever para ela: {guia}",
        "Preserve tudo o que o usuário pediu (pessoas, objetos, quantidades, cores, textos entre aspas, etiquetas "
        "<Picture N>); acrescente só detalhes visuais que combinem com o pedido. Não invente marcas, pessoas reais "
        "nem textos escritos que ele não pediu.",
    ]
    est = contexto.get("estilo")
    if est and _sem_acento(est) != "livre":
        partes.append(f"O estúdio já aplica o estilo “{est}” sozinho: NÃO repita o nome do estilo, descreva só a cena.")
    if contexto.get("modo") == "referencia" and pid not in ("minimax_h3_r2v",):
        partes.append("O usuário também enviou uma imagem de referência/inicial: não contradiga essa imagem.")
    # 07/11/2026: sem teto, ele as vezes escrevia 600 tokens. Na placa isso e 10 s; no
    # PROCESSADOR (quando a placa esta cheia com o modelo de imagem, que e justamente
    # quando se mexe no prompt) sao ~11 tok/s: um pedido do dono levou 58,7 s assim.
    # O teto corta o pior caso E melhora o resultado: prompt longo demais dilui a
    # atencao do modelo de imagem, que nao le 600 tokens de qualquer jeito.
    partes.append("O prompt final é em INGLÊS, num único parágrafo de NO MÁXIMO 70 PALAVRAS. Corte o que for enfeite e fique com o que se vê na imagem. " + REGRA_SO_TEXTO)
    return "\n".join(partes)


def sistema_letra(contexto):
    idioma = contexto.get("idioma") or "português do Brasil"
    en = str(contexto.get("tags") or "").lower() in ("en", "ingles", "inglês")
    marcas = ("[verse], [pre-chorus] (opcional), [chorus], [verse], [chorus], [bridge], [chorus], [outro] (opcional)"
              if en else "[Verso 1], [Pré-refrão] (opcional), [Refrão], [Verso 2], [Refrão], [Ponte], [Refrão]")
    est = contexto.get("estilo")
    return "\n".join([
        f"Você é um letrista brasileiro experiente. Escreva uma letra de música ORIGINAL em {idioma} sobre o tema "
        "pedido" + (f", no estilo {est}." if est else "."),
        f"Estrutura, com cada marcação entre colchetes sozinha na linha: {marcas}.",
        "Métrica cantável: versos curtos (6 a 10 sílabas poéticas), número parecido de sílabas entre versos que se "
        "correspondem, rimas naturais (AABB ou ABAB), refrão curto, repetível e fácil de lembrar. Linguagem natural "
        "do Brasil, imagens concretas, sem clichês forçados.",
        "Não copie letras existentes e não cite artistas.",
        "Responda SOMENTE com a letra: sem título, sem comentários, sem explicações, sem markdown.",
    ])


def sistema_roteiro(contexto):
    if contexto.get("preset") == "apresentador" or contexto.get("formato") == "fala":
        idioma = contexto.get("idioma") or "português do Brasil"
        try:
            seg = max(5, min(180, int(float(contexto.get("segundos") or 15))))
        except (TypeError, ValueError):
            seg = 15
        palavras = int(seg * 2.2)  # o Chatterbox fala ~2,2 palavras/s; até 15 s o Apresentador usa o LTX-2.3 (rápido)
        return "\n".join([
            "Você escreve o texto que uma pessoa vai FALAR olhando para a câmera, como apresentadora de um vídeo.",
            f"Escreva em {idioma}, em primeira pessoa, tom natural e simpático, frases curtas e fáceis de pronunciar.",
            f"Duração alvo: cerca de {seg} segundos de fala — NO MÁXIMO {palavras} palavras.",
            "Sem emojis, sem hashtags, sem marcações de cena, sem indicações entre parênteses, sem nome de quem fala.",
            "Responda SOMENTE com o texto falado.",
        ])
    n = contexto.get("cenas")
    return "\n".join([
        "Você é roteirista de vídeos curtos feitos com IA. A partir do tema, escreva um roteiro dividido em cenas de "
        "10 a 15 segundos (a IA de vídeo gera no máximo 15 s por cena).",
        (f"Escreva {n} cenas." if n else "Escreva de 3 a 8 cenas."),
        "Para cada cena use exatamente este formato, com uma linha em branco entre as cenas:",
        "Cena N (X s)\nFala: o que é falado ou narrado, em português (ou “sem fala”)\n"
        "Prompt: o prompt da cena em INGLÊS — um plano só, uma ação simples, câmera, luz e sons",
        "Responda SOMENTE com as cenas, sem introdução nem comentários.",
    ])


def sistema_traduzir(contexto):
    destino = contexto.get("idioma")
    alvo = (f"Traduza o texto para {destino}." if destino else
            "Se o texto estiver em português, traduza para inglês; se estiver em outro idioma, traduza para "
            "português do Brasil.")
    return "\n".join([
        "Você é tradutor profissional.", alvo,
        "Mantenha o sentido, o tom, as quebras de linha, as marcações entre colchetes, as etiquetas <Picture N> e os "
        "nomes próprios.",
        "Responda SOMENTE com a tradução.",
    ])


def sistema_descrever(contexto):
    idioma = contexto.get("idioma")
    em_pt = idioma and _sem_acento(idioma).startswith("portug")
    return "\n".join([
        "Você descreve imagens para virarem PROMPT de uma IA de imagem ou vídeo.",
        ("Escreva em português do Brasil" if em_pt else "Escreva em INGLÊS") +
        ", num único parágrafo: sujeito principal (aparência, roupa, expressão, pose), ação, cenário, luz, cores, "
        "enquadramento e ângulo de câmera e o estilo (foto, ilustração, 3D...). 60 a 120 palavras.",
        "Se houver texto escrito na imagem, copie-o entre aspas.",
        REGRA_SO_TEXTO,
    ])


def sistema_livre(fichas_ias):
    linhas = []
    for f in (fichas_ias or {}).values():
        if isinstance(f, dict) and f.get("nome") and f.get("aba") in ("imagem", "video", "musica"):
            linhas.append(f"- {f['nome']} ({f.get('aba')}): {f.get('resumo_curto') or ''}")
    return "\n".join([
        "Você é o assistente do Estúdio Local, um estúdio de IA 100% local no computador do usuário (imagem, vídeo, "
        "pessoa falando e música). Responda em português do Brasil, de forma direta e curta. Nunca diga que gerou "
        "algo: você só orienta; quem gera é o botão Gerar do estúdio.",
        "IAs disponíveis no estúdio:" if linhas else "",
        "\n".join(linhas[:30]),
    ]).strip()


def sistema_canal_personagens(contexto):
    return ("Você cria personagens para canais de vídeo. Responda apenas com o JSON array pedido, "
            "sem markdown e sem explicação.")


def sistema_canal_roteiro(contexto):
    return ("Você é roteirista de vídeos curtos. Siga exatamente o pedido do usuário. "
            "Responda apenas com o JSON pedido, sem markdown e sem explicação.")


def sistema_contexto(contexto):
    return "\n".join([
        "Você monta a configuração de um canal de vídeos curtos.",
        "Responda APENAS com um objeto JSON válido, começando em { e terminando em }.",
        "Sem markdown, sem cercas de código, sem explicação antes ou depois.",
        "Mantenha os textos curtos para o JSON caber inteiro: tema 2 a 3 frases, público 1, tom 1, "
        "identidade visual 1 a 2 frases, no máximo 3 personagens, 4 regras, 4 itens em não fazer, "
        "3 referências, 1 chamada final e 8 hashtags.",
        "Nunca invente números, prêmios, tecnologias, parcerias ou nomes de canais, igrejas e empresas.",
        "As chaves são exatamente: tema, publico, tom, identidade_visual, personagens, regras, "
        "nao_fazer, referencias, chamada_final, hashtags.",
    ])


def montar_mensagens(tarefa, entrada, contexto, ficha=None, fichas_ias=None, imagem_b64=None, imagem_mime=None):
    if tarefa == "melhorar_prompt":
        sis, usr = sistema_melhorar(ficha, contexto), f"Pedido do usuário:\n{entrada}"
    elif tarefa == "letra":
        sis, usr = sistema_letra(contexto), f"Tema da música:\n{entrada}"
    elif tarefa == "roteiro":
        sis = sistema_roteiro(contexto)
        usr = f"Tema:\n{entrada}"
    elif tarefa == "canal_roteiro":
        sis, usr = sistema_canal_roteiro(contexto), entrada
    elif tarefa == "canal_personagens":
        sis, usr = sistema_canal_personagens(contexto), entrada
    elif tarefa == "traduzir":
        sis, usr = sistema_traduzir(contexto), entrada
    elif tarefa == "contexto":
        sis, usr = sistema_contexto(contexto), entrada
    elif tarefa == "descrever_imagem":
        sis = sistema_descrever(contexto)
        pedido = "Descreva esta imagem." + (f"\nObservação do usuário: {entrada}" if entrada else "")
        usr = [{"type": "image_url", "image_url": {"url": f"data:{imagem_mime};base64,{imagem_b64}"}},
               {"type": "text", "text": pedido}]
    else:
        sis, usr = sistema_livre(fichas_ias), entrada
    return [{"role": "system", "content": sis}, {"role": "user", "content": usr}]


RE_ROTULO = re.compile(r"^\s*(?:\*\*)?(?:final\s+)?(?:english\s+)?(?:prompt(?:\s+final)?|prompt\s+em\s+ingl[eê]s|"
                       r"tradu[cç][aã]o|translation|descri[cç][aã]o|description|letra|texto)\s*(?:\*\*)?\s*:\s*",
                       re.IGNORECASE)


def limpar_saida(tarefa, txt):
    """Tira o que escapou da regra 'só o texto': raciocínio <think>, cercas de código, rótulos e aspas em volta."""
    t = re.sub(r"<think>.*?</think>", "", str(txt or ""), flags=re.DOTALL).strip()
    t = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", t).strip()
    if tarefa in ("melhorar_prompt", "traduzir", "descrever_imagem"):
        t = RE_ROTULO.sub("", t, count=1).strip()
        if len(t) > 2 and t[0] == t[-1] and t[0] in "\"'“”" and t.count(t[0]) == 2:
            t = t[1:-1].strip()
        if len(t) > 2 and t[0] == "“" and t[-1] == "”" and t.count("“") == 1:
            t = t[1:-1].strip()
    if tarefa in ("melhorar_prompt", "descrever_imagem"):
        t = re.sub(r"\s*\n+\s*", " ", t).strip()  # um parágrafo só
    if tarefa in ("letra", "roteiro", "canal_roteiro", "canal_personagens", "livre", "contexto"):
        t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
        t = re.sub(r"(?m)^#+\s*", "", t)
        t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t


# ---------------------------------------------------------------- o motor
class MotorTexto:
    def __init__(self):
        self.proc = {"placa": None, "processador": None}
        self.job = {"placa": None, "processador": None}
        self.externo = {"placa": False, "processador": False}  # servidor que já estava no ar (não fomos nós que ligamos)
        self.trava_placa = asyncio.Lock()     # um pedido de texto por vez na placa
        self.trava_ligar = {"placa": asyncio.Lock(), "processador": asyncio.Lock()}
        self.na_placa = False                  # um pedido de texto está usando (ou reservou) a placa
        self.carregado = None                  # papel carregado na placa ("rapido"/"principal") ou None
        self.fase = None
        self.fase_desde = None
        self.uso = {"placa": 0.0, "processador": 0.0}
        self.ultimo = None                     # resumo do último pedido (para a tela Início)
        self.ultima_vram = None                # conferência do nvidia-smi depois de descarregar
        self.pedidos_cpu = 0
        self.papel_placa = None                # papel que o pedido atual está usando/carregando na placa
        # "sempre pronta" (Home com botões de ligar, 23/09/2026)
        self.manter = False                    # "manter ligada": o vigia não desliga o processador por ociosidade
        self.tarefa_ligar = None               # ligar_processador() em andamento
        self.ligando_desde = None              # quando o "Ligar agora" (ou o início do estúdio) começou a ligar
        self.cpu_ligando_desde = None          # quando o processo do processador foi aberto e ainda não respondeu
        self.erro_ligar = None                 # {"msg", "quando"} da última tentativa de ligar que falhou
        self.desligar_pendente = False         # "Desligar" chegou no meio de um pedido: desliga ao terminar
        self.religou_em = 0.0                  # última vez que o vigia religou sozinho o servidor do processador

    # ------------------------------------------------ instalação
    def faltando(self, papel=None):
        """Lista (em português) do que falta instalar para o papel (ou para tudo)."""
        falta = []
        if not EXE_GPU.is_file():
            falta.append(f"llama.cpp da placa ({EXE_GPU})")
        if not EXE_CPU.is_file():
            falta.append(f"llama.cpp do processador ({EXE_CPU})")
        if not MODELOS_INI.is_file():
            falta.append(f"configuração dos modelos ({MODELOS_INI})")
        for p in ([papel] if papel else list(MODELOS)):
            m = MODELOS[p]
            if not (MODELOS_DIR / m["pasta"] / m["arquivo"]).is_file():
                falta.append(f"modelo {m['nome']} ({Path('modelos_texto') / m['pasta'] / m['arquivo']})")
        return falta

    def instalado(self):
        return not self.faltando()

    # ------------------------------------------------ processos
    def _vivo(self, onde):
        p = self.proc[onde]
        return p is not None and p.poll() is None

    def _parar(self, onde, motivo=""):
        p, job = self.proc[onde], self.job[onde]
        if p is None:
            return
        print(f"[texto] desligando o servidor de texto do {onde} {motivo}".rstrip(), flush=True)
        if job:
            job.matar()
        try:
            if p.poll() is None:
                if plataforma.WIN:
                    subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True,
                                   creationflags=plataforma.NO_WINDOW, timeout=15)
                else:
                    p.kill()
        except Exception:
            pass
        self.proc[onde] = None
        self.job[onde] = None
        if onde == "placa":
            self.carregado = None

    def parar_tudo(self):
        for onde in ("placa", "processador"):
            self._parar(onde, "(estúdio fechando)")

    def _args(self, onde):
        if onde == "placa":
            return [str(EXE_GPU), "--models-preset", str(MODELOS_INI), "--models-max", "1",
                    "--host", "127.0.0.1", "--port", str(PORTA_GPU), "--no-webui",
                    "--sleep-idle-seconds", "300"]  # só rede de segurança: o estúdio descarrega no fim de cada pedido
        m = MODELOS["rapido"]
        pasta = MODELOS_DIR / m["pasta"]
        # sem --sleep-idle-seconds: quem desliga o processador parado é o vigia do estúdio (10 min), e com
        # "manter ligada" o modelo tem que continuar carregado (o llama-server "dormindo" tiraria o modelo da memória)
        return [str(EXE_CPU), "-m", str(pasta / m["arquivo"]), "--mmproj", str(pasta / m["mmproj"]),
                "-c", "8192", "-np", "1", "-t", str(16 if plataforma.WIN else plataforma.threads_cpu()),
                "-tb", str(24 if plataforma.WIN else plataforma.threads_cpu()), "--jinja", "-fa", "on",
                "--host", "127.0.0.1", "--port", str(PORTA_CPU), "--no-webui", "-a", "rapido"]

    async def _ligar(self, onde):
        """Liga o servidor (se já não estiver no ar) e espera ele responder."""
        url = URL_GPU if onde == "placa" else URL_CPU
        rota = "/models" if onde == "placa" else "/health"
        async with self.trava_ligar[onde]:
            if self._vivo(onde):
                return
            st, _ = await _http("GET", url + rota, 3)
            if st == 503 and onde == "processador":
                # um llama-server que sobrou de antes ainda está carregando o modelo (o /health dá 503 até terminar)
                self.cpu_ligando_desde = self.cpu_ligando_desde or time.time()
                try:
                    t0 = time.time()
                    while st == 503 and time.time() - t0 < 600:
                        await asyncio.sleep(1)
                        st, _ = await _http("GET", url + rota, 3)
                finally:
                    self.cpu_ligando_desde = None
            if st == 200:  # sobrou de antes (ex.: estúdio reiniciado): usa; o fim de cada pedido descarrega igual
                if not self.externo[onde]:
                    print(f"[texto] já havia um servidor de texto na porta {url.rsplit(':', 1)[-1]}; reaproveitando.",
                          flush=True)
                self.externo[onde] = True
                return
            if st is not None:
                print(f"[texto] a porta {url.rsplit(':', 1)[-1]} (IA de texto do {onde}) está ocupada por outro "
                      f"programa (respondeu {st}).", flush=True)
                raise ErroTexto("Outro programa está usando o lugar da IA de texto. Feche o estúdio pelo "
                                "“Desligar Estúdio” e abra de novo.", 503)
            self.externo[onde] = False
            falta = self.faltando("rapido")
            if onde == "placa":
                falta = [f for f in falta if "processador" not in f]
            else:
                falta = [f for f in falta if "placa" not in f and "configuração" not in f]
            if falta:
                raise ErroTexto("A IA de texto não está instalada por completo. Falta: " + "; ".join(falta), 503)
            log = _abrir_log("llama_placa.log" if onde == "placa" else "llama_processador.log")
            try:
                exe = EXE_GPU if onde == "placa" else EXE_CPU
                p = subprocess.Popen(self._args(onde), cwd=str(exe.parent), env=_ambiente(), stdout=log,
                                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                     **plataforma.sem_janela())
            finally:
                log.close()
            job = _Job()
            job.colocar(p)
            self.proc[onde], self.job[onde] = p, job
            print(f"[texto] servidor de texto do {onde} ligado (processo {p.pid}, porta "
                  f"{PORTA_GPU if onde == 'placa' else PORTA_CPU}).", flush=True)
            # a placa responde logo (o roteador não carrega modelo); o processador carrega o 9B do HD
            # (medido: ~4 min com o HD disputado por outros downloads; normal ~40 s)
            limite = 60 if onde == "placa" else 600
            self._marcar_fase("Ligando a IA de texto" if onde == "placa" else
                              "Carregando o Qwen3.5-9B no processador (do HD leva de 40 s a alguns minutos)")
            if onde == "processador":
                self.cpu_ligando_desde = time.time()
            try:
                t0 = time.time()
                while time.time() - t0 < limite:
                    if p.poll() is not None:
                        self._parar(onde)
                        raise ErroTexto(f"O servidor de texto do {onde} fechou ao ligar. Veja o arquivo "
                                        f"{'llama_placa.log' if onde == 'placa' else 'llama_processador.log'} na "
                                        "pasta outputs.", 502)
                    st, _ = await _http("GET", url + rota, 3)
                    if st == 200:
                        return
                    await asyncio.sleep(1)
                self._parar(onde, "(não respondeu a tempo)")
                raise ErroTexto(f"O servidor de texto do {onde} não respondeu em {limite // 60} min.", 504)
            finally:
                if onde == "processador":
                    self.cpu_ligando_desde = None

    # ------------------------------------------------ placa: carregar / descarregar
    async def _modelos_placa(self):
        """{papel: status} do roteador (ou {} se ele não estiver no ar)."""
        st, d = await _http("GET", URL_GPU + "/models", 5)
        if st != 200 or not isinstance(d, dict):
            return {}
        res = {}
        for m in d.get("data") or []:
            s = m.get("status") or {}
            res[m.get("id")] = s.get("value") if isinstance(s, dict) else s
        return res

    async def _carregar(self, papel):
        await self._ligar("placa")
        self._marcar_fase(f"Carregando o {MODELOS[papel]['nome']} na placa (do HD pode levar até 1–2 min)")
        st, d = await _http("POST", URL_GPU + "/models/load", 30, json={"model": papel})
        if st not in (200, 400) and st is not None:  # 400 = já carregado/carregando em algumas versões
            raise ErroTexto(f"O servidor de texto recusou carregar o {MODELOS[papel]['nome']} ({st}).", 502)
        t0 = time.time()
        while time.time() - t0 < 600:  # HD de até 185 MB/s: o 35B leva ~75 s; com o disco disputado, bem mais
            est = (await self._modelos_placa()).get(papel)
            if est == "loaded":
                self.carregado = papel
                return
            if est in ("unloaded", None) and time.time() - t0 > 5:
                st2, d2 = await _http("GET", URL_GPU + "/models", 5)
                lista = d2.get("data") if isinstance(d2, dict) else None
                falhou = any(isinstance(m, dict) and m.get("id") == papel and isinstance(m.get("status"), dict)
                             and m["status"].get("failed") for m in (lista or []))
                if falhou or not (self._vivo("placa") or self.externo["placa"]):
                    raise ErroTexto(f"Não consegui carregar o {MODELOS[papel]['nome']} na placa. Veja o "
                                    f"arquivo outputs\\llama_placa.log.\n{_cauda_log('llama_placa.log', 4)}", 502)
            await asyncio.sleep(1)
        raise ErroTexto(f"O {MODELOS[papel]['nome']} demorou demais para carregar (mais de 10 min).", 504)

    async def _descarregar_tudo(self, conferir_vram=True, base_mib=None):
        """POST /models/unload para todo modelo que não esteja 'unloaded' e confere no nvidia-smi.
        Se a memória não voltar, encerra o roteador inteiro (o processo do modelo pode ficar segurando a placa)."""
        mods = await self._modelos_placa()
        pendentes = [k for k, v in mods.items() if v not in ("unloaded", None)]
        if not pendentes and not conferir_vram:
            self.carregado = None
            return
        if pendentes:
            self._marcar_fase("Descarregando a IA de texto da placa")
        for k in pendentes:
            await _http("POST", URL_GPU + "/models/unload", 20, json={"model": k})
        t0 = time.time()
        while pendentes and time.time() - t0 < 30:
            mods = await self._modelos_placa()
            if all(mods.get(k) in ("unloaded", None) for k in pendentes):
                break
            await asyncio.sleep(0.5)
        self.carregado = None
        if not conferir_vram:
            return
        usada = None
        for _ in range(10):
            usada, _livre = await vram_mib()
            if usada is None or base_mib is None or usada <= base_mib + 600:
                break
            await asyncio.sleep(1)
        liberou = usada is None or base_mib is None or usada <= base_mib + 600
        if not liberou and self._vivo("placa"):
            print(f"[texto] a placa não voltou ({usada} MiB usados, antes {base_mib}); encerrando o roteador.",
                  flush=True)
            self._parar("placa", "(memória da placa não voltou depois de descarregar)")
            for _ in range(10):
                await asyncio.sleep(1)
                usada, _livre = await vram_mib()
                if usada is None or usada <= base_mib + 600:
                    break
            liberou = usada is None or usada <= base_mib + 600
        self.ultima_vram = {"antes_mib": base_mib, "depois_mib": usada, "liberou": liberou, "quando": time.time()}
        if pendentes:
            print(f"[texto] descarregado da placa: {', '.join(pendentes)} (nvidia-smi: {usada} MiB usados; "
                  f"antes de carregar: {base_mib} MiB).", flush=True)

    async def garantir_fora_da_placa(self):
        """Chamado antes de QUALQUER envio para 8188/8189/8193: espera o texto que estiver na placa terminar (ele
        descarrega no fim) e descarrega o que tiver sobrado (ex.: 'dormindo' no roteador)."""
        if not self.na_placa and not self._vivo("placa") and not self.externo["placa"] and self.carregado is None:
            return
        async with self.trava_placa:
            if self._vivo("placa") or self.externo["placa"] or self.carregado:
                await self._descarregar_tudo(conferir_vram=False)

    async def liberar(self):
        """Botão 'Liberar memória': tira o texto da placa e fecha os servidores de texto parados. Devolve a frase.
        Com "manter ligada" (o dono ligou pelo Início), o servidor do processador fica: ele não usa a placa."""
        if self.na_placa or self.pedidos_cpu:
            return "A IA de texto está escrevendo agora; ela sai da memória sozinha ao terminar."
        ligados = [o for o in ("placa", "processador") if self._vivo(o)
                   and not (o == "processador" and (self.manter or self._ligando_cpu()))]
        async with self.trava_placa:
            if self._vivo("placa") or self.externo["placa"]:
                await self._descarregar_tudo(conferir_vram=False)
            for o in ligados:
                self._parar(o, "(liberar memória)")
        if self.manter and (self._vivo("processador") or self.externo["processador"] or self._ligando_cpu()):
            return ("A IA de texto continua pronta no processador (fica na memória do computador, sem usar a placa); "
                    "para tirar, use Desligar na IA de texto.")
        return "IA de texto desligada." if ligados else ""

    # ------------------------------------------------ "sempre pronta": ligar / desligar pelo Início
    def _ligando_cpu(self):
        return bool(self.tarefa_ligar and not self.tarefa_ligar.done()) or self.trava_ligar["processador"].locked()

    def falta_processador(self):
        return [f for f in self.faltando("rapido") if "placa" not in f and "configuração" not in f]

    def iniciar_ligar(self):
        """Botão 'Ligar agora' (e o início do estúdio com 'sempre ligada'): marca 'manter ligada' e liga o
        processador com o 9B em segundo plano. Volta na hora; o progresso aparece em estado_simples()."""
        self.manter = True
        self.desligar_pendente = False
        if self.tarefa_ligar and not self.tarefa_ligar.done():
            return False  # já está ligando (dois cliques não ligam em dobro)
        self.erro_ligar = None
        self.ligando_desde = time.time()
        self.tarefa_ligar = asyncio.get_running_loop().create_task(self.ligar_processador())
        return True

    async def ligar_processador(self):
        """Liga o servidor do PROCESSADOR com o Qwen3.5-9B carregado (só RAM) e faz um pedido mínimo de aquecimento."""
        try:
            falta = self.falta_processador()
            if falta:
                raise ErroTexto("A IA de texto não está instalada por completo. Falta: " + "; ".join(falta), 503)
            await self._ligar("processador")
            self._marcar_fase("Aquecendo a IA de texto no processador")
            corpo = {"model": "rapido", "messages": [{"role": "user", "content": "Oi"}], "max_tokens": 1,
                     "stream": False, "temperature": 0, "chat_template_kwargs": {"enable_thinking": False}}
            st, _ = await _http("POST", URL_CPU + "/v1/chat/completions", 300, json=corpo)
            if st != 200:  # o /health já respondeu: o modelo está carregado; o aquecimento é só um extra
                print(f"[texto] aquecimento no processador respondeu {st}; seguindo (o modelo já está carregado).",
                      flush=True)
            self.uso["processador"] = time.time()
            print("[texto] IA de texto pronta no processador (Qwen3.5-9B carregado na memória; fica ligada).",
                  flush=True)
        except asyncio.CancelledError:
            raise
        except ErroTexto as exc:
            self.erro_ligar = {"msg": str(exc), "quando": time.time()}
            self.manter = False
            print(f"[texto] não consegui ligar a IA de texto no processador: {exc}", flush=True)
        except Exception as exc:
            self.erro_ligar = {"msg": f"A IA de texto não ligou ({exc}).", "quando": time.time()}
            self.manter = False
            print(f"[texto] não consegui ligar a IA de texto no processador: {exc!r}", flush=True)
        finally:
            self.ligando_desde = None
            if not self.na_placa and not self.pedidos_cpu:
                self.fase = None

    async def desligar(self):
        """Botão 'Desligar': fecha os dois servidores de texto e desmarca 'manter ligada'. Devolve a frase."""
        self.manter = False
        t = self.tarefa_ligar
        if t and not t.done():
            t.cancel()
            await asyncio.wait([t], timeout=10)
        self.erro_ligar = None
        if self.na_placa or self.pedidos_cpu:
            self.desligar_pendente = True
            return "A IA de texto está escrevendo agora; ela desliga sozinha assim que terminar."
        await self._desligar_tudo("(desligar)")
        return "IA de texto desligada."

    async def _desligar_tudo(self, motivo):
        self.desligar_pendente = False
        async with self.trava_placa:
            if self._vivo("placa") or self.externo["placa"]:
                await self._descarregar_tudo(conferir_vram=False)
            self._parar("placa", motivo)
        self._parar("processador", motivo)
        for onde, porta in (("placa", PORTA_GPU), ("processador", PORTA_CPU)):
            if self.externo[onde]:
                await asyncio.to_thread(_matar_llama_na_porta, porta)
                self.externo[onde] = False

    async def _desligar_se_pendente(self):
        if self.desligar_pendente and not self.na_placa and not self.pedidos_cpu and not self.manter:
            await self._desligar_tudo("(desligar pedido enquanto escrevia)")

    def estado_simples(self):
        """Estado em uma palavra para a tela Início:
        'pronta' (processador com o 9B carregado) | 'em espera' (desligada, liga sozinha ao usar) | 'ligando' |
        'na placa agora' (um pedido está usando a placa; sai sozinha no fim) | 'erro' (com a mensagem)."""
        cpu = self._vivo("processador") or self.externo["processador"]
        ligando = self._ligando_cpu()
        falta = self.falta_processador()
        r = {"manter": self.manter, "processador_ligado": bool(cpu and not ligando), "pode_ligar": not falta,
             "escrevendo": bool(self.pedidos_cpu or self.na_placa), "desligar_pendente": self.desligar_pendente}
        if self.na_placa:
            r["estado"] = "na placa agora"
        elif ligando:
            r.update(estado="ligando", desde=self.ligando_desde or self.cpu_ligando_desde or self.fase_desde,
                     fase=self.fase)
        elif cpu:
            r["estado"] = "pronta"
        elif self.erro_ligar:
            r.update(estado="erro", mensagem=self.erro_ligar["msg"], quando=self.erro_ligar["quando"])
        elif falta:
            r.update(estado="erro", mensagem="A IA de texto não está instalada por completo. Falta: " + "; ".join(falta))
        else:
            r["estado"] = "em espera"
        return r

    # ------------------------------------------------ estado
    def _marcar_fase(self, fase):
        self.fase = fase
        self.fase_desde = time.time()

    def ocupando_placa(self):
        """Para o /api/ocupado: a IA de texto está (ou vai estar) na placa."""
        return self.na_placa or self.carregado is not None

    def motivo_ocupado(self):
        papel = self.carregado or self.papel_placa
        return f"IA de texto usando a placa de vídeo ({MODELOS[papel]['nome']})" if papel else             "IA de texto usando a placa de vídeo"

    def estado_publico(self):
        falta = self.faltando()
        return {
            "instalado": not falta, "falta": falta,
            "modelos": {k: {"nome": v["nome"], "licenca": v["licenca"],
                            "instalado": (MODELOS_DIR / v["pasta"] / v["arquivo"]).is_file()}
                        for k, v in MODELOS.items()},
            "placa": {"ligado": self._vivo("placa") or self.externo["placa"],
                      "carregado": MODELOS[self.carregado]["nome"] if self.carregado else None, "porta": PORTA_GPU},
            "processador": {"ligado": self._vivo("processador") or self.externo["processador"], "porta": PORTA_CPU,
                            "carregado": MODELOS["rapido"]["nome"] if (self._vivo("processador")
                                                                       or self.externo["processador"]) else None},
            "em_uso": ({"onde": "placa" if self.na_placa else "processador", "fase": self.fase,
                        "desde": self.fase_desde} if (self.na_placa or self.pedidos_cpu) else None),
            "na_placa": self.ocupando_placa(),
            "ultimo": self.ultimo, "vram_depois_de_descarregar": self.ultima_vram,
            "simples": self.estado_simples(),
        }

    # ------------------------------------------------ pedido
    async def _conversar(self, url, papel, mensagens, tarefa, contexto):
        pensar = bool(contexto.get("pensar"))
        corpo = {"model": papel, "messages": mensagens, "stream": False,
                 "max_tokens": MAX_TOKENS.get(tarefa, 1000) * (3 if pensar else 1),
                 "temperature": 0.8 if tarefa in ("letra", "roteiro") else 0.6 if tarefa != "traduzir" else 0.3,
                 "top_p": 0.8 if not pensar else 0.95, "top_k": 20, "min_p": 0.0,
                 "presence_penalty": 0.5 if tarefa in ("letra", "roteiro") else 0.0,
                 "chat_template_kwargs": {"enable_thinking": pensar}}
        st, d = await _http("POST", url + "/v1/chat/completions", 900, json=corpo)
        if st is None:
            raise ErroTexto("A IA de texto parou de responder no meio do pedido.", 502)
        if st != 200 or not isinstance(d, dict):
            msg = (d.get("error") or {}).get("message") if isinstance(d, dict) and isinstance(d.get("error"), dict) \
                else str(d)[:300]
            raise ErroTexto(f"A IA de texto deu erro ({st}): {msg}", 502)
        esc = (d.get("choices") or [{}])[0]
        txt = (esc.get("message") or {}).get("content") or ""
        tm = d.get("timings") or {}
        return txt, {"tokens": (d.get("usage") or {}).get("completion_tokens") or tm.get("predicted_n"),
                     "tokens_por_segundo": round(tm["predicted_per_second"], 1) if tm.get("predicted_per_second")
                     else None,
                     "leitura_tokens_por_segundo": round(tm["prompt_per_second"], 1) if tm.get("prompt_per_second")
                     else None,
                     "cortado": esc.get("finish_reason") == "length"}

    async def pedir(self, *args, **kwargs):
        """Faz o pedido (ver _pedir). Se o dono clicou em Desligar enquanto ele rodava, desliga ao terminar."""
        try:
            return await self._pedir(*args, **kwargs)
        finally:
            if self.desligar_pendente:
                try:
                    await self._desligar_se_pendente()
                except Exception as exc:
                    print(f"[texto] desligar depois do pedido: {exc}", flush=True)

    async def _pedir(self, tarefa, entrada, contexto, modelo, placa_ocupada, ficha=None, fichas_ias=None,
                     pasta_input=None):
        """Faz o pedido e devolve {texto, modelo, papel, onde, segundos, ...}.
        placa_ocupada(papel) -> motivo (texto) se a placa não pode receber a IA de texto agora, ou None."""
        t0 = time.time()
        if tarefa not in TAREFAS:
            raise ErroTexto(f"Tarefa desconhecida: {tarefa}. Use uma destas: {', '.join(TAREFAS)}.")
        entrada = str(entrada or "").strip()
        contexto = contexto if isinstance(contexto, dict) else {}
        if len(entrada) > ENTRADA_MAX:
            raise ErroTexto(f"Texto grande demais ({len(entrada)} caracteres; o máximo é {ENTRADA_MAX}).")
        img_b64 = img_mime = None
        if tarefa == "descrever_imagem":
            nome = Path(str(contexto.get("imagem") or "")).name
            if not nome:
                raise ErroTexto("Envie a imagem primeiro (contexto.imagem com o nome do arquivo em input).")
            arq = Path(pasta_input) / nome if pasta_input else None
            if not arq or not arq.is_file():
                raise ErroTexto(f"A imagem “{nome}” não está na pasta input da ComfyUI. Envie de novo.")
            ext = arq.suffix.lower()
            img_mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
                        ".bmp": "image/bmp", ".gif": "image/gif"}.get(ext, "image/png")
            img_b64 = base64.b64encode(await asyncio.to_thread(arq.read_bytes)).decode()
            papel = "rapido"  # quem enxerga imagem é o 9B (o 35B roda sem o arquivo de visão)
        else:
            if not entrada:
                raise ErroTexto("Escreva o texto primeiro.")
            papel = modelo if modelo in MODELOS else PAPEL_PADRAO[tarefa]
        mensagens = montar_mensagens(tarefa, entrada, contexto, ficha, fichas_ias, img_b64, img_mime)
        pedido_papel = papel
        aviso = None

        def falta_placa(p):
            return [f for f in self.faltando(p) if "processador" not in f]

        if papel == "principal" and falta_placa("principal") and not falta_placa("rapido"):
            papel, aviso = "rapido", "O Qwen3.6-35B não está instalado: usei o Qwen3.5-9B."

        # ---- 1) tenta a placa
        motivo_cpu = "a IA de texto da placa não está instalada"
        if not falta_placa(papel):
            async with self.trava_placa:
                self.na_placa = True  # reserva ANTES de conferir (o painel já vê 'ocupado')
                try:
                    motivo = await placa_ocupada(papel)
                    if motivo and papel == "principal" and motivo.startswith("VRAM:"):
                        # nada gerando, mas sem memória livre para o 35B: o 9B cabe na placa
                        if not await placa_ocupada("rapido"):
                            aviso = (motivo[5:].strip() + " Usei o Qwen3.5-9B na placa no lugar do Qwen3.6-35B.")
                            papel, motivo = "rapido", None
                    if motivo:
                        self.na_placa = False
                        raise _VaiProCPU(motivo)
                    self.papel_placa = papel
                    base_mib, _ = await vram_mib()
                    if self.carregado and self.carregado != papel:
                        await self._descarregar_tudo(conferir_vram=False)
                    if self.carregado != papel:
                        await self._carregar(papel)
                    self._marcar_fase(f"Escrevendo com o {MODELOS[papel]['nome']} na placa")
                    self.uso["placa"] = time.time()
                    try:
                        txt, info = await self._conversar(URL_GPU, papel, mensagens, tarefa, contexto)
                    finally:
                        await self._descarregar_tudo(conferir_vram=True, base_mib=base_mib)
                        self.uso["placa"] = time.time()
                    return self._resposta(tarefa, txt, info, papel, "placa", t0, aviso, pedido_papel)
                except _VaiProCPU as vai:
                    motivo_cpu = str(vai)
                finally:
                    self.na_placa = False
                    self.papel_placa = None
                    self.fase = None

        # ---- 2) processador (só o 9B; não toca na placa)
        falta_cpu = [f for f in self.faltando("rapido") if "placa" not in f and "configuração" not in f]
        if falta_cpu:
            raise ErroTexto("A IA de texto não está instalada. Falta: " + "; ".join(falta_cpu), 503)
        porque = (motivo_cpu[5:].strip() if motivo_cpu.startswith("VRAM:")
                  else f"a placa de vídeo está ocupada ({motivo_cpu})" if "instalada" not in motivo_cpu
                  else motivo_cpu)
        if papel != "rapido":
            aviso = (f"Rodou o Qwen3.5-9B no processador, no lugar do {MODELOS[papel]['nome']}, porque "
                     f"{porque[0].lower() + porque[1:]}")
        else:
            aviso = f"Rodou no processador porque {porque[0].lower() + porque[1:]}"
        aviso = aviso.rstrip(".") + "."
        self.pedidos_cpu += 1
        self._marcar_fase("Escrevendo com o Qwen3.5-9B no processador")
        try:
            await self._ligar("processador")
            self._marcar_fase("Escrevendo com o Qwen3.5-9B no processador")
            self.uso["processador"] = time.time()
            txt, info = await self._conversar(URL_CPU, "rapido", mensagens, tarefa, contexto)
            self.uso["processador"] = time.time()
        finally:
            self.pedidos_cpu -= 1
            if not self.na_placa:
                self.fase = None
        return self._resposta(tarefa, txt, info, "rapido", "processador", t0, aviso, pedido_papel)

    def _resposta(self, tarefa, txt, info, papel, onde, t0, aviso, pedido_papel):
        limpo = limpar_saida(tarefa, txt)
        if not limpo:
            raise ErroTexto("A IA de texto não devolveu nada. Tente de novo.", 502)
        seg = round(time.time() - t0, 1)
        res = {"texto": limpo, "modelo": MODELOS[papel]["nome"], "papel": papel, "onde": onde, "segundos": seg,
               "tarefa": tarefa, "pedido": pedido_papel, **info}
        if aviso:
            res["aviso"] = aviso
        if info.get("cortado"):
            res["aviso"] = ((aviso + " ") if aviso else "") + "O texto ficou grande e pode ter sido cortado no fim."
        if onde == "placa":
            res["vram"] = self.ultima_vram
        self.ultimo = {"tarefa": tarefa, "modelo": res["modelo"], "onde": onde, "segundos": seg,
                       "tokens_por_segundo": info.get("tokens_por_segundo"), "quando": time.time()}
        print(f"[texto] {tarefa}: {res['modelo']} no(a) {onde} em {seg} s "
              f"({info.get('tokens')} tokens, {info.get('tokens_por_segundo')} t/s).", flush=True)
        return res

    # ------------------------------------------------ vigia (desliga os servidores parados)
    async def vigiar(self):
        # ao ligar: se sobrou um roteador de antes com modelo na placa, descarrega
        try:
            if await self._modelos_placa():
                async with self.trava_placa:
                    await self._descarregar_tudo(conferir_vram=False)
        except Exception as exc:
            print(f"[texto] vigia (início): {exc}", flush=True)
        while True:
            try:
                await asyncio.sleep(30)
                agora = time.time()
                if (self._vivo("processador") and not self.pedidos_cpu and not self.manter
                        and not self._ligando_cpu() and agora - self.uso["processador"] > CPU_OCIOSO_S):
                    self._parar("processador", f"(parado há mais de {CPU_OCIOSO_S / 60:.0f} min)")
                # "manter ligada": se o servidor do processador fechou sozinho, religa (no máximo 1 vez a cada 10 min)
                p = self.proc["processador"]
                if (self.manter and p is not None and p.poll() is not None and not self._ligando_cpu()):
                    self._parar("processador", "(fechou sozinho)")
                    if agora - self.religou_em > 600:
                        self.religou_em = agora
                        print("[texto] o servidor de texto do processador fechou sozinho; ligando de novo.",
                              flush=True)
                        self.iniciar_ligar()
                    else:
                        self.manter = False
                        self.erro_ligar = {"msg": "A IA de texto do processador fechou sozinha duas vezes em 10 min. "
                                                  "Veja o arquivo llama_processador.log na pasta outputs.",
                                           "quando": agora}
                # servidor que sobrou de antes ("externo") e que sumiu: deixa de contar como ligado
                for onde, url, rota in (("placa", URL_GPU, "/models"), ("processador", URL_CPU, "/health")):
                    if self.externo[onde]:
                        st, _ = await _http("GET", url + rota, 3)
                        if st is None:
                            self.externo[onde] = False
                if self._vivo("placa") and not self.trava_placa.locked():
                    if self.carregado and agora - self.uso["placa"] > 90:  # não deveria acontecer: descarrega
                        async with self.trava_placa:
                            await self._descarregar_tudo(conferir_vram=False)
                    elif agora - self.uso["placa"] > GPU_OCIOSO_S:
                        self._parar("placa", f"(parado há mais de {GPU_OCIOSO_S / 60:.0f} min)")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"[texto] vigia: {exc}", flush=True)


class _VaiProCPU(Exception):
    pass
