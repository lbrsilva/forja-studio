"""Painel de música do Forja Studio (aba "Música" do estúdio).

Nasceu em setembro de 2026 como um programa à parte: tinha uma ComfyUI só dele (porta 8189), o ACE-Step (8193) e
duas IAs pagas na nuvem. Em 14/11/2026 entrou no pacote do estúdio, e o que mudou foi:

- usa a MESMA ComfyUI da imagem e do vídeo (uma só, uma fila só, uma placa só). O painel NUNCA liga nem desliga a
  ComfyUI: quando precisa dela e ela está desligada, pede ao estúdio (POST /api/servicos/ligar {"servico": "video"})
  e espera na fila;
- só as IAs que vêm no pacote aparecem (PAINEL_MOTORES): YuE2 INT8 e Stable Audio 3. ACE-Step, Treblo e Musicful
  não vêm; se os arquivos deles estiverem na pasta, o painel os carrega, senão segue sem eles;
- nada depende do nome de uma pasta nem da letra de um disco: quem liga o painel é o estúdio (estudio/server.py),
  e ele passa tudo por variável de ambiente.

Variáveis de ambiente (todas opcionais):
  PAINEL_PORTA        porta deste painel (padrão 8190)
  PAINEL_COMFY_DIR    pasta da ComfyUI; input\\, output\\ e models\\ saem dela
                      (padrão: ComfyUI_windows_portable\\ComfyUI ao lado do pacote)
  PAINEL_COMFY_URL    endereço da ComfyUI (padrão http://127.0.0.1:8188)
  PAINEL_ESTUDIO_URL  endereço do estúdio (padrão http://127.0.0.1:8194)
  PAINEL_DADOS        onde ficam jobs.json, uploads.json e as cópias convertidas para baixar
                      (padrão: estudio\\musica; nunca a pasta do código)
  PAINEL_MOTORES      ids das IAs que aparecem, separados por vírgula (padrão yue2-int8,stable-audio3)
  PAINEL_FICHAS       arquivo das fichas das IAs (padrão estudio\\fichas.json)
  PAINEL_WEB          pasta da tela (padrão: web\\ ao lado deste arquivo)
  PAINEL_TEXTO_URL    onde fica a IA de texto (padrão: o próprio estúdio)
  PAINEL_TESTE=1      modo de teste: não processa a fila e não gera nada

O que continua igual desde a reforma de 23/09/2026:
- os nomes das IAs vêm só da fichas.json (catalogo.py);
- "Apagar" apaga do HD de verdade (com confirmação na tela), sem apagar arquivo de outra música;
- contrato com o estúdio: /api/recentes, /api/ocupado, /api/fichas (com CORS para o endereço do estúdio);
- uma geração por vez na placa: toda música entra numa fila local e só vai para a ComfyUI quando ela está vazia e o
  estúdio diz que a placa está livre (novos_motores.py);
- IA de texto: POST /api/texto repassa o pedido ao estúdio ("Escrever letra com IA", "Melhorar descrição");
- equalizador (equalizador.py): roda no processador, fora da fila. Precisa do pacote "pedalboard"; sem ele o botão
  "Equalizar" some e o resto do painel funciona igual.
"""
import os
from pathlib import Path

import asyncio
import copy
import csv
import contextlib
import hashlib
import importlib
import json
import math
import re
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from urllib.parse import quote

import psutil
sys.path.insert(0, str(Path(__file__).resolve().parent))  # o Python embutido da ComfyUI não inclui a pasta do script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "estudio"))

from aiohttp import ClientConnectorError, ClientError, ClientSession, ClientTimeout, WSMsgType, web
import catalogo
import novos_motores
import equalizador
import plataforma


class _MotorAusente:
    """Fica no lugar de um motor que não vem neste pacote (ACE-Step, Treblo, Musicful).

    Responde "não é comigo" a tudo o que o painel pergunta, para o resto do código não precisar de um `if` em cada
    lugar. Nenhum pedido chega a usar um motor ausente: o /api/generate recusa antes (catalogo.MOTORES)."""
    presente = False
    MOTOR = '(motor ausente)'
    CAMPOS_ACOMPANHAMENTO = ()

    def __init__(self, nome):
        self.nome = nome

    @staticmethod
    def eh_treblo(job):
        return False

    eh_musicful = eh_treblo

    @staticmethod
    async def ace_vivo(*_a, **_k):
        return False

    @staticmethod
    async def call(*_a, **_k):
        raise ConnectionError('Este motor de música não vem neste pacote.')


def _motor_opcional(nome):
    try:
        modulo = importlib.import_module(nome)
    except ModuleNotFoundError as exc:
        if exc.name != nome:  # o arquivo existe, mas falta uma biblioteca DELE: isso é defeito, não ausência
            raise
        return _MotorAusente(nome)
    modulo.presente = True
    return modulo


ace_backend = _motor_opcional('ace_backend')
treblo_backend = _motor_opcional('treblo_backend')
musicful_backend = _motor_opcional('musicful_backend')

STATIC = Path(__file__).resolve().parent
ROOT = STATIC.parent
PORTA = int(os.environ.get('PAINEL_PORTA', '8190'))
TESTE = os.environ.get('PAINEL_TESTE') == '1'
# Os dados de quem usa (lista de músicas, envios) moram FORA da pasta do código: a pasta do código é trocada inteira
# numa atualização, e um jobs.json dentro dela iria junto para o GitHub de quem mantém o pacote.
DADOS = Path(os.environ.get('PAINEL_DADOS') or (ROOT / 'estudio' / 'musica')).resolve()
DADOS.mkdir(parents=True, exist_ok=True)
WEB = Path(os.environ.get('PAINEL_WEB') or (STATIC / 'web')).resolve()
WORKFLOWS = STATIC / 'workflows'
# A ComfyUI é a do estúdio (a mesma da imagem e do vídeo). O painel só fala com ela; não a liga nem desliga.
COMFY = Path(os.environ.get('PAINEL_COMFY_DIR') or (ROOT / 'ComfyUI_windows_portable' / 'ComfyUI')).resolve()
INPUT = COMFY / 'input'
OUTPUT = COMFY / 'output'
MODELOS = COMFY / 'models'
BASE = (os.environ.get('PAINEL_COMFY_URL') or 'http://127.0.0.1:8188').rstrip('/')
ESTUDIO = (os.environ.get('PAINEL_ESTUDIO_URL') or 'http://127.0.0.1:8194').rstrip('/')
ACE_API_DIR = ROOT / 'ACE-Step-1.5' / '.cache' / 'acestep' / 'tmp' / 'api_audio'  # só existe com o ACE-Step
STATE = DADOS / 'jobs.json'
UPLOADS = DADOS / 'uploads.json'
# Cada porta com o seu clientId: uma cópia de teste não recebe o progresso do painel de verdade. O estúdio reconhece
# as músicas na fila da ComfyUI por este começo ("painel-musica") e não as mostra duas vezes na aba Fila.
CLIENTE = 'painel-musica' if PORTA == 8190 else f'painel-musica-{PORTA}'
TEMPLATE = json.loads((WORKFLOWS / 'yue2_teste_20s_api.json').read_text(encoding='utf-8-sig'))
JOBS = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
MIGRADOS = catalogo.migrar(JOBS)  # só na memória: o arquivo é regravado no próximo salvamento
LOCK = asyncio.Lock()
PROGRESS = {}
REFRESH_LOCK = asyncio.Lock()
AUDIO_EXT = {'.flac', '.wav', '.mp3', '.ogg', '.opus', '.m4a', '.aac',
             '.aiff', '.aif', '.caf', '.m4b'}   # AIFF/CAF/M4B: os formatos comuns do macOS
TIPOS_AUDIO = {'.flac': 'audio/flac', '.wav': 'audio/wav', '.mp3': 'audio/mpeg', '.ogg': 'audio/ogg',
               '.opus': 'audio/ogg', '.m4a': 'audio/mp4', '.aac': 'audio/aac',
               '.aiff': 'audio/aiff', '.aif': 'audio/aiff', '.caf': 'audio/x-caf', '.m4b': 'audio/mp4'}


def _as_duas_formas(url):
    """O mesmo endereço escrito com 127.0.0.1 e com localhost (o navegador trata os dois como origens diferentes)."""
    return {url, url.replace('//127.0.0.1', '//localhost'), url.replace('//localhost', '//127.0.0.1')}


ORIGENS_CORS = _as_duas_formas(ESTUDIO)
ROTAS_CORS = ('/api/recentes', '/api/ocupado', '/api/fichas', '/api/audio/')
SEM_JANELA = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
SEM_COMFY = ('O motor (ComfyUI) ainda não está instalado neste computador. Abra o Início do Forja Studio e instale o '
             'motor antes de usar a música.')


def exigir_comfy():
    """As pastas input\\ e output\\ são da ComfyUI. Sem ela instalada não há onde guardar o áudio."""
    if not (COMFY / 'main.py').is_file():
        raise ValueError(SEM_COMFY)
    INPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / 'audio').mkdir(parents=True, exist_ok=True)


# Os arquivos de modelo de cada IA do pacote (os mesmos do estudio/ias.py, MUSICA_ARQUIVOS). O painel só confere se
# estão no disco, para dizer na tela o que falta em vez de deixar a ComfyUI recusar o pedido com um erro em inglês.
MODELOS_DO_MOTOR = {
    'yue2-int8': ('checkpoints/yue2_3b_int8_convrot.safetensors',),
    'stable-audio3': ('checkpoints/stable_audio_3_medium.safetensors', 'text_encoders/t5gemma_b_b_ul2.safetensors',
                      'text_encoders/qwen3.5_2b_bf16.safetensors'),
}
MODELO_COVER = 'audio_encoders/sheetsage2_bf16.safetensors'  # só o cover do YuE2 usa


def faltam_modelos(motor):
    """Nomes dos arquivos de modelo que esta IA precisa e que não estão em models\\. Lista vazia = pode gerar."""
    return [Path(rel).name for rel in MODELOS_DO_MOTOR.get(motor, ()) if not (MODELOS / rel).is_file()]


def erro_json(mensagem, status=400):
    return web.json_response({'error': mensagem}, status=status)


# ---------------------------------------------------------------- arquivos de áudio
def item_saida(item):
    return (OUTPUT / (item.get('subfolder') or '') / item['filename']).resolve()


async def fade_audio(item):
    source = item_saida(item)
    if not source.is_relative_to(OUTPUT.resolve()) or not source.is_file():
        raise ValueError('Áudio de saída inválido.')
    probe = await asyncio.create_subprocess_exec('ffprobe', '-v', 'error', '-show_entries',
        'format=duration', '-of', 'json', str(source), stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, creationflags=SEM_JANELA)
    output, _ = await probe.communicate()
    if probe.returncode:
        raise ValueError('Não foi possível medir a duração do áudio.')
    duration = float(json.loads(output)['format']['duration'])
    seconds = min(2.0, duration)
    target = source.with_name(source.stem + '_fade_' + uuid.uuid4().hex[:8] + '.flac')
    process = await asyncio.create_subprocess_exec('ffmpeg', '-v', 'error', '-nostdin', '-n',
        '-i', str(source), '-af', f'afade=t=out:st={max(0, duration-seconds)}:d={seconds}',
        '-c:a', 'flac', str(target), stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, creationflags=SEM_JANELA)
    _, error = await process.communicate()
    if process.returncode:
        target.unlink(missing_ok=True)
        raise ValueError(error.decode(errors='replace')[-300:])
    return {**item, 'filename': target.name}


# 28/09 (pedido do dono): a ComfyUI grava no arquivo a "receita" inteira (etiquetas prompt/workflow: letra, semente, modo do cover,
# nome do arquivo de referência). O painel apaga essas duas; ficam só título, comentário (qual IA) e estilo.
SEM_RECEITA = ['-metadata', 'prompt=', '-metadata', 'workflow=']


async def gravar_metadados(item, titulo, motor, estilo=''):
    """Grava no próprio arquivo quem gerou (só nas músicas novas; as antigas não são regravadas)."""
    path = item_saida(item)
    if not path.is_relative_to(OUTPUT.resolve()) or not path.is_file():
        return False
    temporario = path.with_name(path.stem + '_meta_' + uuid.uuid4().hex[:6] + path.suffix)
    argumentos = ['ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', str(path), '-map', '0', '-c', 'copy',
                  '-metadata', f'title={titulo[:200]}', '-metadata', f'comment=Forja Studio · {motor}', *SEM_RECEITA]
    if estilo:
        argumentos += ['-metadata', f'estilo={estilo[:1500]}']  # 'description' viraria COMMENT no FLAC
    processo = await asyncio.create_subprocess_exec(*argumentos, str(temporario), stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.PIPE, creationflags=SEM_JANELA)
    await processo.communicate()
    if processo.returncode or not temporario.is_file() or temporario.stat().st_size < 4:
        temporario.unlink(missing_ok=True)
        return False
    await asyncio.to_thread(os.replace, temporario, path)
    DURACOES.pop(str(path), None)
    return True


DURACOES = {}


def duracao_arquivo(path):
    """Duração em segundos lendo o cabeçalho do FLAC (sem abrir processo). None se não der."""
    chave = str(path)
    if chave in DURACOES:
        return DURACOES[chave]
    valor = None
    try:
        with open(path, 'rb') as f:
            if f.read(4) == b'fLaC':
                f.read(4)
                info = f.read(34)
                bits = int.from_bytes(info[10:18], 'big')
                taxa, total = bits >> 44, bits & ((1 << 36) - 1)
                if taxa and total:
                    valor = round(total / taxa, 1)
    except OSError:
        return None
    DURACOES[chave] = valor
    return valor


def duracao_item(item):
    try:
        return duracao_arquivo(item_saida(item))
    except (KeyError, TypeError):
        return None


ENTRADAS_TEMPORARIAS = ('entrada_cover', 'entrada_referencia')


def limpar_entradas(job):
    """Apaga os trechos recortados (cover do YuE2 e música de referência) depois de usados, se nenhum outro job em
    andamento usar o mesmo trecho."""
    s = job.get('settings') or {}
    for chave in ENTRADAS_TEMPORARIAS:
        nome = s.get(chave)
        if not isinstance(nome, str) or not nome.startswith('painel_trecho_') or Path(nome).name != nome:
            continue
        if any(j is not job and j.get('state') == 'running' and (j.get('settings') or {}).get(chave) == nome
               for j in JOBS.values()):
            continue
        if not TESTE:
            with contextlib.suppress(OSError):
                (INPUT / nome).unlink(missing_ok=True)


# ---------------------------------------------------------------- monitor do sistema
METRICS_LOCK = asyncio.Lock()
METRICS_CACHE = {}
METRICS_TIME = 0
psutil.cpu_percent()


async def system_metrics(request):
    global METRICS_TIME, METRICS_CACHE
    async with METRICS_LOCK:
        if time.monotonic() - METRICS_TIME < 2 and METRICS_CACHE:
            return web.json_response(METRICS_CACHE)
        memory = psutil.virtual_memory()
        result = {'cpu': psutil.cpu_percent(), 'ram_used': memory.used,
                  'ram_total': memory.total, 'ram_percent': memory.percent, 'gpu': None}
        if plataforma.MAC:
            try:
                info = plataforma.gpu_unificada()
                if info:
                    nome, total, livre = info
                    usado = max(0, total - livre)
                    result['gpu'] = {'name': nome,
                                     'percent': round(usado / total * 100, 1) if total else 0,
                                     'used_mib': usado / 1024 ** 2, 'total_mib': total / 1024 ** 2}
            except Exception:
                pass
        else:
            try:
                process = await asyncio.create_subprocess_exec(
                    'nvidia-smi', '--query-gpu=name,utilization.gpu,memory.used,memory.total',
                    '--format=csv,noheader,nounits', stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE, creationflags=SEM_JANELA)
                try:
                    output, _ = await asyncio.wait_for(process.communicate(), timeout=3)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.communicate()
                    raise
                if process.returncode == 0:
                    row = next(csv.reader(output.decode().splitlines()))
                    result['gpu'] = {'name': row[0].strip(), 'percent': float(row[1]),
                                     'used_mib': float(row[2]), 'total_mib': float(row[3])}
            except (OSError, ValueError, StopIteration, IndexError, asyncio.TimeoutError):
                pass
        METRICS_CACHE = result
        METRICS_TIME = time.monotonic()
        return web.json_response(result)


# ---------------------------------------------------------------- progresso vindo da ComfyUI
def progress_event(event):
    data = event.get('data', {})
    prompt_id = data.get('prompt_id')
    kind = event.get('type')
    if not prompt_id:
        return
    if kind == 'executing':
        PROGRESS[prompt_id] = {'node': str(data.get('node') or ''), 'percent': None}
    elif kind == 'progress_state':
        for node, state in data.get('nodes', {}).items():
            if state.get('state') == 'running':
                maximum = state.get('max', 0)
                percent = min(100, max(0, int(100 * state.get('value', 0) / maximum))) if maximum else None
                PROGRESS[prompt_id] = {'node': str(node), 'percent': percent}
    elif kind == 'progress':
        maximum = data.get('max', 0)
        if maximum:
            PROGRESS[prompt_id] = {'node': str(data.get('node', '')), 'percent': min(100, max(0, int(100 * data.get('value', 0) / maximum)))}


async def progress_listener():
    while True:
        try:
            async with ClientSession() as session:
                async with session.ws_connect(BASE + '/ws?clientId=' + CLIENTE, heartbeat=20) as socket:
                    async for message in socket:
                        if message.type == WSMsgType.TEXT:
                            progress_event(message.json())
        except (ClientError, OSError, asyncio.TimeoutError, ValueError):
            pass
        finally:
            PROGRESS.clear()
        await asyncio.sleep(2)


async def progress_context(app):
    task = asyncio.create_task(progress_listener())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


BACKUP_JOBS = STATE.with_name(STATE.name + '.bak_reforma_2026-09-23')
_BACKUP = {'feito': False}


def copiar_antes_da_migracao():
    """Na primeira gravação desta versão, guarda o jobs.json como estava antes da migração (MIGRADOS > 0 tira campos
    antigos sem volta). Só uma vez por processo e nunca sobrescreve uma cópia que já existe.

    Só vale para quem TRAZ um jobs.json antigo: numa instalação nova nada é migrado e nenhuma cópia é criada."""
    if _BACKUP['feito']:
        return
    _BACKUP['feito'] = True
    if not MIGRADOS or BACKUP_JOBS.exists() or not STATE.exists():
        return
    try:
        shutil.copy2(STATE, BACKUP_JOBS)
    except OSError as exc:
        print(f'Aviso: não deu para copiar o jobs.json para {BACKUP_JOBS.name}: {exc}', flush=True)


def save_jobs():
    copiar_antes_da_migracao()
    temporary = STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps(JOBS, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(STATE)


def registrar_motor(job):
    motor_id, motor_nome, _ = catalogo.motor_do_job(job, JOBS)
    job['motor_id'], job['motor_nome'] = motor_id, motor_nome
    return job


async def comfy(method, path, **kwargs):
    if TESTE and method.upper() != 'GET':
        raise ValueError('Modo de teste: nada é enviado para a ComfyUI.')
    async with ClientSession(timeout=ClientTimeout(total=30)) as session:
        async with session.request(method, BASE + path, **kwargs) as response:
            text = await response.text()
            data = json.loads(text) if text.strip() else {}
            if response.status >= 400:
                raise web.HTTPBadRequest(text=json.dumps({'error': data}, ensure_ascii=False), content_type='application/json')
            return data


# ---------------------------------------------------------------- middleware (erros em português + CORS do Estúdio)
# ---------------------------------------------------------------- tela antiga guardada no navegador
# O server.py antigo mandava a tela sem Cache-Control: o navegador pode reaproveitar a tela antiga por horas depois
# que o painel reinicia. A tela nova usa outros nomes de arquivo, com versão (?v=), e manda o cabeçalho X-Painel-Tela
# em toda consulta. Pedidos da mesma origem sem esse cabeçalho só podem vir da tela antiga: ela recebe um aviso para
# apertar F5 (e nenhuma ação dela é executada). Os arquivos que só a tela antiga pede trocam a página pela nova.
VERSAO_TELA = '20261114q'  # a mesma do ?v= em web/index.html (q = no pacote do estúdio, só as IAs do pacote; p = filtros em pílulas; s = sugestões de estilo; n = renomear; e = equalizador; a = ajustes no cartão; c = copiar estilo/letra; f = favoritos; d = baixar MP3/WAV; m = Musicful; u = Treblo; b = letra com IA e referência)
CABECALHO_TELA = 'X-Painel-Tela'
LEGADO_JS = {'app.js', 'library.js', 'system.js', 'genres.js', 'style_examples.js', 'lucide.min.js'}
LIVRES_TELA_ANTIGA = ('/api/audio/', '/api/reference/', '/api/system')
AVISO_TELA_ANTIGA = ('O painel de música foi atualizado e esta é a tela antiga guardada no navegador. '
                     'Aperte F5 (ou Ctrl+F5) para abrir a tela nova.')
# Parâmetro próprio ('tela'), diferente do que o Estúdio põe no endereço do quadro: um endereço novo nunca está no cache.
RECARREGAR_JS = f"""/* Tela antiga do painel de música guardada no navegador: troca pela tela nova (endereço novo, fora do cache). */
(function () {{
  var u = new URL(location.href);
  if (u.searchParams.get('tela') === '{VERSAO_TELA}') return;
  u.searchParams.set('tela', '{VERSAO_TELA}');
  location.replace(u.href);
}})();
"""


def tela_antiga(request):
    return (request.path.startswith('/api/') and not request.path.startswith(LIVRES_TELA_ANTIGA)
            and request.headers.get('Sec-Fetch-Site') == 'same-origin' and CABECALHO_TELA not in request.headers)


def resposta_tela_antiga(request):
    if request.method == 'GET' and request.path == '/api/status':
        return web.json_response({'online': False, 'ace_online': False, 'cover': False, 'tela_antiga': True})
    if request.method == 'GET' and request.path == '/api/jobs':
        # a tela antiga mostra este cartão na lista dela (título e texto de erro)
        return web.json_response([{'id': 'painel-atualizado', 'title': 'O painel de música foi atualizado: aperte F5',
                                   'state': 'error', 'error': AVISO_TELA_ANTIGA, 'mode': 'create',
                                   'created': time.time(), 'seed': 0, 'settings': {}}])
    return web.json_response({'error': AVISO_TELA_ANTIGA}, status=410)


@web.middleware
async def errors(request, handler):
    origin = request.headers.get('Origin')
    if request.method == 'POST' and origin and origin != f'http://{request.host}':
        raise web.HTTPForbidden()
    if tela_antiga(request):
        return resposta_tela_antiga(request)
    try:
        response = await handler(request)
    except web.HTTPException as exc:
        response = exc
        if request.method == 'GET' and origin in ORIGENS_CORS and request.path.startswith(ROTAS_CORS):
            exc.headers['Access-Control-Allow-Origin'] = origin
        raise
    except (ValueError, KeyError) as exc:
        # nossas mensagens já são em português; o resto (int() com '120.5', KeyError…) vira frase em português
        tecnico = str(exc) or type(exc).__name__
        mensagem = catalogo.traduzir_erro(exc, generico='O painel recebeu um dado inválido e não conseguiu continuar '
                                                        '(veja o detalhe técnico).')
        corpo = {'error': mensagem}
        if mensagem != tecnico:
            corpo['erro_tecnico'] = tecnico[:300]
        response = web.json_response(corpo, status=400)
    except Exception as exc:
        response = web.json_response({'error': f'Falha na operação: {catalogo.traduzir_erro(exc)}',
                                      'erro_tecnico': str(exc)[:300]}, status=503)
    if request.method in ('GET', 'HEAD', 'OPTIONS') and origin in ORIGENS_CORS and request.path.startswith(ROTAS_CORS):
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Vary'] = 'Origin'
    return response


async def preflight(request):
    resposta = web.Response(status=204)
    origem = request.headers.get('Origin')
    if origem in ORIGENS_CORS:
        resposta.headers.update({'Access-Control-Allow-Origin': origem, 'Access-Control-Allow-Methods': 'GET',
                                 'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Max-Age': '600'})
    return resposta


STATUS_CACHE = {'t': 0, 'dados': None}


async def status(request):
    if STATUS_CACHE['dados'] and time.monotonic() - STATUS_CACHE['t'] < 3:
        return web.json_response(STATUS_CACHE['dados'])
    ace_online = False
    if ace_backend.presente:
        try:
            await ace_backend.call('GET', '/health')
            ace_online = True
        except Exception:
            pass
    try:
        await comfy('GET', '/queue')
        online = True
    except Exception:
        online = False
    dados = {'online': online, 'ace_online': ace_online, 'tem_ace': ace_backend.presente,
             # o cover do YuE2 precisa do transcritor de melodia: sem o arquivo, a tela não oferece cover nele
             'cover': (MODELOS / MODELO_COVER).is_file(),
             'motor_instalado': (COMFY / 'main.py').is_file(),
             # o que falta baixar de cada IA (lista vazia = pronta). A tela avisa no cartão e no botão de gerar.
             'faltam': {m: faltam_modelos(m) for m in catalogo.MOTORES},
             'equalizador': equalizador.pb is not None,
             'separador': await tem_separador() if online else False,
             'comfy_recado': PEDIDO_COMFY['erro']}
    dados['teste'] = TESTE
    # A tela é servida do disco, mas o servidor só muda ao reiniciar: a tela nova confere esta versão e esconde o que
    # o servidor em memória ainda não sabe fazer (letra com IA, música de referência) até o painel ser reiniciado.
    dados['versao_tela'] = VERSAO_TELA
    STATUS_CACHE.update(t=time.monotonic(), dados=dados)
    return web.json_response(dados)


# ---------------------------------------------------------------- envio de áudio de referência
def _indice_uploads():
    try:
        return json.loads(UPLOADS.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


async def upload(request):
    if TESTE:
        return erro_json('Modo de teste: enviar áudio está desligado (não grava nada na pasta da ComfyUI).', 403)
    exigir_comfy()
    reader = await request.multipart()
    part = await reader.next()
    if part is None or not part.filename:
        raise ValueError('Escolha um arquivo de áudio.')
    extension = Path(part.filename).suffix.lower()
    if extension not in AUDIO_EXT:
        raise ValueError('Use WAV, MP3, FLAC, OGG, M4A, AAC, OPUS, AIFF ou CAF.')
    temporario = INPUT / ('painel_envio_' + uuid.uuid4().hex + '.part')
    total, resumo = 0, hashlib.sha1()
    try:
        with temporario.open('wb') as output:
            while chunk := await part.read_chunk(1024 * 1024):
                total += len(chunk)
                if total > 100 * 1024 * 1024:
                    raise ValueError('O arquivo deve ter no máximo 100 MB.')
                resumo.update(chunk)
                output.write(chunk)
        name = guardar_envio(temporario, resumo.hexdigest(), extension)
    except Exception:
        temporario.unlink(missing_ok=True)
        raise
    return web.json_response({'name': name, 'label': Path(part.filename).name, 'url': '/api/reference/' + name})


def guardar_envio(temporario, resumo, extension):
    """Põe o arquivo (já copiado em `temporario`, dentro de input/) com nome definitivo. O mesmo áudio enviado de novo
    reaproveita a cópia que já existe (antes virava 12 cópias iguais)."""
    indice = _indice_uploads()
    chave = resumo + extension
    existente = indice.get(chave)
    if existente and (INPUT / existente).is_file():
        temporario.unlink(missing_ok=True)
        return existente
    name = 'painel_' + uuid.uuid4().hex + extension
    temporario.replace(INPUT / name)
    indice[chave] = name
    with contextlib.suppress(OSError):
        UPLOADS.write_text(json.dumps(indice, ensure_ascii=False, indent=1), encoding='utf-8')
    return name


def copiar_para_entrada(origem):
    """Cópia de uma música pronta (output/) para input/, para servir de referência. Mesmo conteúdo = mesma cópia."""
    temporario = INPUT / ('painel_envio_' + uuid.uuid4().hex + '.part')
    resumo = hashlib.sha1()
    try:
        with origem.open('rb') as entrada, temporario.open('wb') as saida:
            while bloco := entrada.read(1024 * 1024):
                resumo.update(bloco)
                saida.write(bloco)
        return guardar_envio(temporario, resumo.hexdigest(), origem.suffix.lower())
    except Exception:
        temporario.unlink(missing_ok=True)
        raise


async def referencia_da_biblioteca(request):
    """Usa uma música pronta da biblioteca como "música de referência" (copia para input/ e devolve como um envio)."""
    if TESTE:
        return erro_json('Modo de teste: usar uma música como referência está desligado (não grava nada na pasta da '
                         'ComfyUI).', 403)
    job = JOBS.get(request.match_info['id'])
    if not job or job.get('deleted_at') or job.get('state') != 'done' or not job.get('audio'):
        return erro_json('Música não encontrada ou ainda não terminou.', 404)
    origem = item_saida(job['audio'][0])
    if not origem.is_relative_to(OUTPUT.resolve()) or not origem.is_file():
        raise ValueError('O arquivo desta música não está mais no HD.')
    nome = await asyncio.to_thread(copiar_para_entrada, origem)
    motor_nome = catalogo.motor_do_job(job, JOBS)[1]
    return web.json_response({'name': nome, 'label': f"{job.get('title') or 'Música'} ({motor_nome})",
                              'url': '/api/reference/' + nome, 'duracao_s': job.get('duracao_s') or duracao_item(job['audio'][0])})


def reference_path(name):
    if name == 'demo':
        return OUTPUT / 'audio/fz_yue2_teste_20s_00001.flac'
    if Path(name).name != name or not name.startswith('painel_'):
        raise ValueError('Áudio de referência inválido.')
    path = INPUT / name
    if not path.is_file():
        raise ValueError('Áudio de referência não encontrado (pode ter sido apagado junto com a música).')
    return path


async def reference(request):
    path = reference_path(request.match_info['name'])
    return web.FileResponse(path, headers={'Content-Type': TIPOS_AUDIO.get(path.suffix.lower(), 'application/octet-stream')})


# ---------------------------------------------------------------- geração
def instrumental_style(style):
    """Tira do estilo as frases que pedem voz e acrescenta UMA vez o sufixo técnico de instrumental.

    Antes o sufixo se acumulava ao usar "Usar configurações" ("no spoken words" escapava do filtro)."""
    vocal = re.compile(
        r'\b(?:vocals?|voices?|singers?|singing|sung|chant(?:ing)?|choirs?|'
        r'rap(?:ping)?|spoken[ -]words?|humming|voz(?:es)?|vocais|vocalista\w*|'
        r'cantor\w*|cantando|cantad[ao]s?|canto|coral|corais|sussurr\w*)\b', re.I)
    base = catalogo.limpar_sufixo(style)
    clauses = re.split(r'[,;\n.!?]+', base)
    kept = [part.strip() for part in clauses if part.strip() and not vocal.search(part)]
    return ', '.join(kept + catalogo.SUFIXO)


def montar_yue2(data):
    """Monta o fluxo da ComfyUI para o YuE2 a partir das configurações salvas no job."""
    mode = data.get('mode', 'create')
    style = str(data.get('style', '')).strip()
    lyrics = str(data.get('lyrics', '')).strip()
    seed = int(data['seed'])
    duration = int(data.get('effective_duration') or 360)
    reference_mode = data.get('reference_mode', 'melody')
    graph = copy.deepcopy(TEMPLATE)
    if data.get('instrumental'):
        style = instrumental_style(style)
        lyrics = ''
    args = graph['2']['inputs']
    args.update(style=style, lyrics=lyrics, seed=seed, max_duration=duration)
    graph['5']['inputs']['seed'] = seed
    if mode == 'cover':
        graph['8'] = {'class_type': 'AudioEncoderLoader', 'inputs': {'audio_encoder_name': 'sheetsage2_bf16.safetensors'}}
        graph['9'] = {'class_type': 'LoadAudio', 'inputs': {'audio': data['entrada_cover']}}
        graph['10'] = {'class_type': 'SheetSage2AudioToABC', 'inputs': {'audio_encoder': ['8', 0], 'audio': ['9', 0], 'mode': reference_mode}}
        args.update(abc=['10', 0], mode=reference_mode, cfg_scale=1)
    elif data.get('planning', True):
        graph['8'] = {'class_type': 'YuE2GenerateABC', 'inputs': {'clip': ['1', 1], 'style': style, 'lyrics': lyrics, 'seed': seed, 'mode': 'full', 'max_abc_tokens': 8192, 'temperature': 0.7, 'top_p': 0.9, 'top_k': 30, 'repetition_penalty': 1.005, 'penalty_window': 100}}
        args.update(abc=['8', 0], mode='full', cfg_scale=1)
    args['temperature'] = float(data.get('temperature', 1.0))
    if isinstance(args.get('abc'), list):
        graph['11'] = {'class_type': 'FZScoreGuard', 'inputs': {
            'score': args['abc'], 'instrumental': bool(data.get('instrumental')),
            'require_vocal': mode == 'cover' and not data.get('instrumental')}}
        args['abc'] = ['11', 0]
    args['cfg_scale'] = float(data.get('guidance', 1.0))
    graph['7']['inputs']['filename_prefix'] = 'audio/painel_yue2_' + mode + '_' + time.strftime('%Y%m%d_%H%M%S')
    return graph


# ---------------------------------------------------------------- música de referência (estilo por áudio, sem treinar)
MOTORES_REFERENCIA = {'ace-step-official'} | novos_motores.REFERENCIA_XL
CAMPOS_REFERENCIA = ('referencia_estilo', 'referencia_forca', 'referencia_inicio', 'entrada_referencia')


async def recortar_referencia(fonte, inicio, segundos):
    """Recorta da música de referência o trecho que vai para a IA (a partir de `inicio`, com a duração pedida).

    O ACE-Step Oficial trava a duração da música no tamanho do trecho; o XL usa o trecho alinhado com o começo da
    música nova (o que faltar vira silêncio)."""
    nome = 'painel_trecho_' + uuid.uuid4().hex + '.flac'
    destino = INPUT / nome
    processo = await asyncio.create_subprocess_exec(
        'ffmpeg', '-v', 'error', '-nostdin', '-n', '-ss', str(inicio), '-i', str(fonte), '-t', str(segundos),
        '-ar', '48000', '-ac', '2', '-c:a', 'flac', str(destino),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, creationflags=SEM_JANELA)
    _, erro = await processo.communicate()
    tamanho = duracao_arquivo(destino) if processo.returncode == 0 else None
    DURACOES.pop(str(destino), None)
    if processo.returncode or not tamanho or tamanho < 5:
        destino.unlink(missing_ok=True)
        if processo.returncode:
            raise ValueError('Não foi possível ler a música de referência: ' + erro.decode(errors='replace')[-300:])
        raise ValueError('O trecho da música de referência ficou com menos de 5 segundos. Diminua o "Começar em" '
                         'ou escolha uma música mais longa.')
    return nome


async def preparar_referencia(data, mode, engine, duration_setting):
    """Valida a música de referência e recorta o trecho. Devolve o nome do trecho (ou None, sem referência).

    Só vale em "Criar música" (no cover o áudio enviado já é a base) e só nos motores do ACE-Step 1.5."""
    nome = data.get('referencia_estilo')
    if mode != 'create' or not nome:
        for chave in CAMPOS_REFERENCIA:
            data.pop(chave, None)
        return None
    if engine not in MOTORES_REFERENCIA:
        if not MOTORES_REFERENCIA & set(catalogo.MOTORES):
            raise ValueError('Nenhuma IA de música desta instalação aceita música de referência. Tire a referência.')
        raise ValueError(f'{catalogo.nome(engine)} não aceita música de referência. Use o '
                         f'{catalogo.nome("ace-step-official")} ou um dos ACE-Step 1.5 XL (Turbo ou SFT), ou tire a referência.')
    try:
        forca = float(data.get('referencia_forca', 0.3))
        inicio = float(data.get('referencia_inicio') or 0)
    except (TypeError, ValueError):
        raise ValueError('A força e o início da música de referência devem ser números.') from None
    if not (math.isfinite(forca) and 0.05 <= forca <= 1):
        raise ValueError('A força da música de referência deve ficar entre 5% e 100%.')
    if not (math.isfinite(inicio) and 0 <= inicio <= 7200):
        raise ValueError('O início da música de referência deve ficar entre 0 e 7200 segundos.')
    fonte = reference_path(str(nome))
    segundos = 120 if duration_setting in ('auto', None, '') else int(duration_setting)
    trecho = await recortar_referencia(fonte, inicio, segundos)
    data.update(referencia_forca=round(forca, 3), referencia_inicio=inicio, entrada_referencia=trecho)
    return trecho


async def generate(request):
    if TESTE:
        return erro_json('Modo de teste: gerar música está desligado.', 403)
    data = await request.json()
    mode = data.get('mode', 'create')
    if mode not in {'create', 'cover'}:
        raise ValueError('Modo inválido.')
    reference_mode = data.get('reference_mode', 'melody')
    if reference_mode not in {'melody', 'full'}:
        raise ValueError('Orientação da referência inválida.')
    style = catalogo.limpar_sufixo(str(data.get('style', '')).strip())
    data['style'] = style
    data['style_original'] = style
    lyrics = str(data.get('lyrics', '')).strip()
    engine = data.get('engine', 'yue2-int8')
    treblo = engine == treblo_backend.MOTOR
    musicful = engine == musicful_backend.MOTOR
    if not style:
        raise ValueError('Preencha o estilo musical.')
    # no cover da Treblo a letra é opcional: sem letra, a própria Treblo escreve uma letra nova
    if not data.get('instrumental') and not lyrics and not (treblo and mode == 'cover'):
        raise ValueError('Preencha a letra ou escolha Instrumental.')
    duration_setting = data.get('duration', 'auto')
    duration = 360 if duration_setting in ('auto', None, '') else int(duration_setting)
    temperature = float(data.get('temperature', 1.0))
    guidance = float(data.get('guidance', 1.0))
    if not 0.7 <= temperature <= 1.2 or not 1.0 <= guidance <= 1.5:
        raise ValueError('Criatividade ou orientação fora do intervalo permitido.')
    seed = int(data.get('seed', secrets.randbelow(2**32)))
    if not 10 <= duration <= 360 or not 0 <= seed <= 2**53 - 1:
        raise ValueError('Duração ou variação fora do intervalo permitido.')
    if engine not in catalogo.MOTORES:
        raise ValueError('Esta IA de música não vem nesta instalação. Escolha uma das IAs da lista.')
    if musicful and mode == 'cover':
        raise ValueError('A Musicful não faz cover. Use o ACE-Step 1.5 · Oficial, o YuE2 ou a Treblo.')
    falta = faltam_modelos(engine)
    if falta:
        raise ValueError(f'Falta baixar o modelo do {catalogo.nome(engine)} ({", ".join(falta)}). Abra o Início do '
                         'Forja Studio e baixe essa IA na lista de IAs; depois volte aqui.')
    if mode == 'cover' and engine == 'yue2-int8' and not (MODELOS / MODELO_COVER).is_file():
        raise ValueError(f'O cover do {catalogo.nome(engine)} precisa de um arquivo que ainda não foi baixado '
                         f'({Path(MODELO_COVER).name}). Baixe o {catalogo.nome(engine)} de novo pela lista de IAs do '
                         'Início (ele traz esse arquivo) ou use "Criar música".')
    # "Tirar a voz no final" usa um nó que não vem no pacote: só vale se a ComfyUI desta máquina tiver esse nó.
    data['remove_vocals'] = (bool(data.get('remove_vocals')) and bool(data.get('instrumental'))
                             and engine != 'stable-audio3' and await tem_separador())
    na_nuvem = treblo or musicful  # Treblo e Musicful geram fora: só "tirar a voz" no final usa a ComfyUI
    precisa = set()
    if engine == 'ace-step-official':
        precisa.add('ace')
    elif not na_nuvem or data['remove_vocals']:
        precisa.add('comfy')
    if 'comfy' in precisa:
        exigir_comfy()
    # A ComfyUI a fila espera sozinha (o painel só PEDE ao estúdio para ligar); o ACE-Step, quando existe, precisa
    # estar no ar antes de receber o pedido.
    if not await garantir_servicos(precisa, esperar='ace' in precisa):
        return erro_json('A IA de música não está ligada. Tente de novo em 1 minuto.', 503)
    idioma = data.get('idioma') or 'pt'
    if idioma not in catalogo.IDIOMAS_LETRA:
        raise ValueError('Idioma da letra inválido. Escolha Português, Inglês ou Espanhol.')
    data['idioma'] = idioma
    trecho = await preparar_referencia(data, mode, engine, duration_setting)
    if treblo:
        data.update(mode=mode, seed=seed)
        return await treblo_backend.enqueue(sys.modules[__name__], data)
    if musicful:
        data.update(mode=mode, seed=seed)
        return await musicful_backend.enqueue(sys.modules[__name__], data)
    if engine in novos_motores.ENGINES or engine == 'ace-step-official':
        try:
            if engine in novos_motores.ENGINES:
                data.update(mode=mode, seed=seed, effective_duration=duration)
                return await novos_motores.enqueue(sys.modules[__name__], data)
            data.update(mode=mode, seed=seed)
            return await ace_backend.enqueue(sys.modules[__name__], data)
        except BaseException:
            if trecho:  # não entrou na fila: o trecho recortado não serve para mais nada
                with contextlib.suppress(OSError):
                    (INPUT / trecho).unlink(missing_ok=True)
            raise
    # YuE2: valida e prepara a referência agora; a música entra na fila local e só vai para a placa quando ela estiver livre.
    data.update(engine='yue2-int8', effective_duration=duration, seed=seed, mode=mode, reference_mode=reference_mode)
    if mode == 'cover':
        source = reference_path(str(data.get('reference', '')))
        if data.get('reference_duration') == 'full':
            if source.parent == INPUT:
                name = source.name  # o envio já está na pasta de entrada da ComfyUI
            else:
                name = 'painel_trecho_' + uuid.uuid4().hex + source.suffix
                await asyncio.to_thread(shutil.copyfile, source, INPUT / name)
            data['start'] = 0
        else:
            start = float(data.get('start', 0))
            length = float(data.get('reference_duration', 30))
            if not 0 <= start <= 7200 or not 5 <= length <= 120:
                raise ValueError('Trecho de referência inválido.')
            name = 'painel_trecho_' + uuid.uuid4().hex + '.flac'
            process = await asyncio.create_subprocess_exec('ffmpeg', '-v', 'error', '-ss', str(start), '-i', str(source), '-t', str(length), '-ar', '48000', '-ac', '2', str(INPUT / name), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, creationflags=SEM_JANELA)
            _, error = await process.communicate()
            if process.returncode:
                raise ValueError('Não foi possível ler esse áudio: ' + error.decode(errors='replace')[-400:])
        data['entrada_cover'] = name
    montar_yue2(data)  # confere se o fluxo monta antes de entrar na fila
    async with LOCK:
        job_id = 'yue-' + uuid.uuid4().hex
        JOBS[job_id] = registrar_motor({
            'id': job_id, 'title': str(data.get('title', '')).strip()[:120] or ('Meu cover' if mode == 'cover' else 'Minha música'),
            'mode': mode, 'created': time.time(), 'seed': seed, 'state': 'running', 'settings': data,
            'nm_phase': 'queued', 'fila_local': True})
        save_jobs()
        return web.json_response(JOBS[job_id])


# ---------------------------------------------------------------- jobs antigos do YuE2 (enviados direto para a ComfyUI)
async def refresh(job):
    async with REFRESH_LOCK:
        await refresh_unlocked(job)


async def refresh_unlocked(job):
    if job.get('settings', {}).get('engine') == 'ace-step-official' or novos_motores.eh_novo(job) \
            or treblo_backend.eh_treblo(job) or musicful_backend.eh_musicful(job):
        return
    if job['state'] != 'running' or job.get('fase_final') or job.get('audio_bruto'):
        return
    prompt_id = job.get('prompt_id') or job['id']
    history = await comfy('GET', '/history/' + prompt_id)
    item = history.get(prompt_id)
    if not item:
        queue = await comfy('GET', '/queue')
        if not any(row[1] == prompt_id for row in queue['queue_running'] + queue['queue_pending']):
            job.update(state='error', error='Geração interrompida ou servidor reiniciado.')
            save_jobs()
        return
    messages = item['status'].get('messages', [])
    if item['status']['status_str'] == 'success':
        audio = [a for output in item['outputs'].values() for a in output.get('audio', [])]
        if item['outputs'].get('11'):
            job['score_inspection'] = item['outputs']['11']
        if item['outputs'].get('12'):
            job['audio_inspection'] = item['outputs']['12']
        timestamps = [m[1]['timestamp'] for m in messages if 'timestamp' in m[1]]
        job['elapsed'] = round((timestamps[-1] - timestamps[0]) / 1000, 1) if timestamps else 0
        if not audio:
            job.update(state='error', error='A geração terminou sem áudio.')
        else:
            # termina pela fila (tirar voz precisa da placa livre; final suave e etiquetas não)
            job.update(audio_bruto=audio[:1], fase_final='pendente')
    else:
        detail = next((m[1].get('exception_message') for m in messages if m[0] == 'execution_error'), None)
        job.update(state='error', error=detail or 'Geração cancelada.')
    save_jobs()


# ---------------------------------------------------------------- lista de músicas
OCULTAR = {'ace_payload', 'score_inspection', 'audio_inspection', 'audio_bruto', 'treblo_pedido', 'musicful_pedido',
           'musicful_resposta'}
ESTAGIOS_YUE2 = {'1': 'Carregando modelo', '2': 'Compondo a música', '5': 'Sintetizando o áudio', '6': 'Decodificando o áudio',
                 '7': 'Salvando o áudio', '9': 'Lendo a referência', '10': 'Transcrevendo a melodia', '11': 'Conferindo a partitura'}


def estagio_yue2(job, node):
    if node == '8':
        return 'Carregando o transcritor' if job['mode'] == 'cover' else 'Planejando a melodia'
    return ESTAGIOS_YUE2.get(node, 'Preparando a geração')


def estagio(job, progress):
    s = job.get('settings', {})
    fase = job.get('fase_final')
    if fase == 'separando':
        return 'Tirando a voz (separador MelBandRoFormer)'
    if fase == 'finalizando':
        return 'Finalizando (final suave e etiquetas do arquivo)'
    if fase == 'pendente':
        return job.get('aviso_fila') or 'Na fila para terminar (tirar a voz)'
    if treblo_backend.eh_treblo(job):
        return treblo_backend.estagio(job)
    if musicful_backend.eh_musicful(job):
        return musicful_backend.estagio(job)
    if s.get('engine') == 'ace-step-official':
        if job.get('connection_warning'):
            return job['connection_warning']
        if job.get('ace_phase') == 'queued':
            return job.get('aviso_fila') or 'Na fila (espera a placa ficar livre)'
        if job.get('ace_phase') in ('liberado', 'submitting'):
            return 'Enviando para o ACE-Step'
        return 'Gerando no ACE-Step'
    if novos_motores.eh_novo(job):
        if s.get('engine') == 'yue2-int8' and job.get('nm_phase') == 'gerando':
            return estagio_yue2(job, progress.get('node')) if progress.get('node') else 'Preparando a geração'
        return novos_motores.estagio(job, progress)
    return estagio_yue2(job, progress.get('node'))


def cancelavel(job):
    if job['state'] != 'running' or job.get('fase_final'):
        return False
    if treblo_backend.eh_treblo(job):
        return treblo_backend.cancelavel(job)
    if musicful_backend.eh_musicful(job):
        return musicful_backend.cancelavel(job)
    if job.get('settings', {}).get('engine') == 'ace-step-official':
        # depois de enviada, só dá para cancelar (no painel) quando o ACE-Step parou de responder
        return job.get('ace_phase') in ('queued', 'liberado') or (
            job.get('ace_phase') in ('submitting', 'generating') and bool(job.get('ace_fora_desde')))
    if novos_motores.eh_novo(job):
        return job.get('nm_phase') in ('queued', 'gerando')
    return True


def job_para_tela(job, progress=None, posicao=0):
    item = {k: v for k, v in job.items() if k not in OCULTAR}
    motor_id, motor_nome, detalhe = catalogo.motor_do_job(job, JOBS)
    item.update(motor_id=motor_id, motor_nome=motor_nome, motor_detalhe=detalhe)
    if job.get('audio'):
        item['duracao_s'] = job.get('duracao_s') or duracao_item(job['audio'][0])
    if job.get('error'):
        traduzido = catalogo.traduzir_erro(job['error'])
        item['error'] = traduzido
        if traduzido != job['error']:
            item['erro_tecnico'] = str(job['error'])[:600]
    if job.get('finish_warning'):
        item['finish_warning'] = (catalogo.traduzir_erro(job['finish_warning']) if job['finish_warning'] in catalogo._ANTIGAS
                                  else re.sub(r'^Nao deu', 'Não deu', job['finish_warning'])
                                  .replace('indisponivel', 'indisponível').replace('audio original', 'áudio original'))
    if progress is not None:
        item.update(queue_position=posicao, cancelable=cancelavel(job), progress={**progress, 'stage': estagio(job, progress)})
    return item


async def jobs(request):
    for job in list(JOBS.values()):
        if job['state'] == 'running':
            with contextlib.suppress(Exception):
                await refresh(job)
    try:
        queue = await comfy('GET', '/queue')
    except Exception:
        queue = {'queue_pending': []}
    positions = {row[1]: index + 1 for index, row in enumerate(sorted(queue['queue_pending'], key=lambda row: row[0]))}
    fila = sorted((j for j in JOBS.values() if j['state'] == 'running' and novos_motores.na_fila(j)), key=lambda j: j['created'])
    positions.update({j['id']: i + 1 for i, j in enumerate(fila)})
    result = []
    for job in reversed(list(JOBS.values())):
        progress = PROGRESS.get(job.get('prompt_id') or job['id'], {}) if job['state'] == 'running' else {}
        result.append(job_para_tela(job, progress, positions.get(job['id'], 0)))
    return web.json_response(result)


async def cancel(request):
    job_id = request.match_info['id']
    job = JOBS.get(job_id)
    if job is None:
        return erro_json('Música não encontrada.', 404)
    if job['state'] != 'running':
        return web.json_response({'ok': True, 'aviso': 'Esta música já não estava gerando.'})
    engine = job.get('settings', {}).get('engine')
    if treblo_backend.eh_treblo(job):
        return await treblo_backend.cancelar(sys.modules[__name__], job)
    if musicful_backend.eh_musicful(job):
        return await musicful_backend.cancelar(sys.modules[__name__], job)
    if engine == 'ace-step-official':
        if job.get('ace_phase') in ('submitting', 'generating') and not job.get('fase_final'):
            # Já foi enviada: o ACE-Step não tem como cancelar. Mas se ele parou de responder, a geração se perdeu e a
            # placa está livre: marca como cancelada só no painel (senão a fila e o vídeo ficariam presos).
            if await ace_backend.ace_vivo():
                return erro_json('O ACE-Step não deixa cancelar depois que a música foi enviada. Espere terminar '
                                 '(leva poucos minutos) e apague, se não quiser.', 409)
            async with LOCK:
                if job['state'] == 'running' and job.get('ace_phase') in ('submitting', 'generating'):
                    job.update(state='error', error='Cancelada no painel: o ACE-Step parou de responder e a geração se perdeu.')
                    for chave in ace_backend.CAMPOS_ACOMPANHAMENTO:
                        job.pop(chave, None)
                    limpar_entradas(job)
                    save_jobs()
            return web.json_response({'ok': True})
        async with LOCK:
            if job['state'] != 'running':
                return web.json_response({'ok': True, 'aviso': 'Esta música já não estava gerando.'})
            if job.get('ace_phase') not in ('queued', 'liberado'):
                return erro_json('Não dá para cancelar agora: a música já está sendo finalizada.', 409)
            job.update(state='error', error='Retirado da fila.')
            job.pop('aviso_fila', None)
            limpar_entradas(job)
            save_jobs()
        return web.json_response({'ok': True})
    if novos_motores.eh_novo(job):
        async with LOCK:  # a fila (novos_motores.despachar) confere o estado com esta mesma trava antes de enviar
            if job['state'] != 'running':
                return web.json_response({'ok': True, 'aviso': 'Esta música já não estava gerando.'})
            fase = job.get('nm_phase')
            if fase == 'queued' and not job.get('fase_final'):
                job.update(state='error', error='Retirado da fila.')
                for chave in ('nm_phase', 'aviso_fila', 'nm_aviso'):
                    job.pop(chave, None)
                limpar_entradas(job)
                save_jobs()
                return web.json_response({'ok': True})
        if fase == 'gerando':
            try:
                await comfy('POST', '/interrupt', json={'prompt_id': job['prompt_id']})
            except Exception:
                # ComfyUI parada ou modo de teste: marca como cancelada para não travar a fila
                job.update(state='error', error='Cancelado (a ComfyUI não respondeu).')
                job.pop('nm_phase', None)
                limpar_entradas(job)
                save_jobs()
        else:
            return erro_json('Não dá para cancelar agora: a música já está sendo finalizada.', 409)
        return web.json_response({'ok': True})
    prompt_id = job.get('prompt_id') or job_id
    try:
        queue = await comfy('GET', '/queue')
        if any(row[1] == prompt_id for row in queue['queue_running']):
            await comfy('POST', '/interrupt', json={'prompt_id': prompt_id})
        else:
            await comfy('POST', '/queue', json={'delete': [prompt_id]})
    except Exception:
        job.update(state='error', error='Cancelado (a ComfyUI não respondeu).')
        save_jobs()
    return web.json_response({'ok': True})


async def separar(request):
    if TESTE:
        return erro_json('Modo de teste: tirar a voz está desligado.', 403)
    if not await tem_separador():
        return erro_json('O "Tirar voz" precisa de um complemento da ComfyUI que não vem nesta instalação '
                         '(MelBandRoFormer).', 409)
    await garantir_servicos({'comfy'}, esperar=False)  # a fila espera a ComfyUI subir
    return web.json_response(registrar_motor(await novos_motores.enqueue_separar(sys.modules[__name__], request.match_info['id'])))


# ---------------------------------------------------------------- apagar do HD
def arquivos_do_job(job):
    """Todos os arquivos que pertencem a um job: saídas, originais, intermediários e entradas enviadas."""
    lista = []
    for chave, tipo in (('audio', 'Música final'), ('original_audio', 'Versão original guardada'),
                        ('intermediarios', 'Arquivo intermediário'), ('audio_bruto', 'Áudio bruto')):
        for item in job.get(chave) or []:
            with contextlib.suppress(KeyError, TypeError, ValueError):
                lista.append((item_saida(item), tipo))
    s = job.get('settings') or {}
    for nome, tipo in ((s.get('reference'), 'Áudio de referência enviado (cópia)'),
                       (s.get('entrada_cover'), 'Trecho do áudio de referência'),
                       (s.get('referencia_estilo'), 'Música de referência (cópia usada pelo painel)'),
                       (s.get('entrada_referencia'), 'Trecho da música de referência')):
        if isinstance(nome, str) and nome.startswith('painel_') and Path(nome).name == nome:
            lista.append(((INPUT / nome).resolve(), tipo))
    if job.get('ace_arquivo_api'):
        lista.append((Path(job['ace_arquivo_api']).resolve(), 'Cópia guardada pelo ACE-Step'))
    return lista


def pode_apagar(path):
    """Só apaga dentro das pastas do painel: nunca segue caminho para fora delas."""
    if path.suffix.lower() not in AUDIO_EXT:
        return False
    if path.is_relative_to(OUTPUT.resolve()) or path.is_relative_to(INPUT.resolve()):
        return path.name.startswith('painel_')
    return path.is_relative_to(ACE_API_DIR.resolve())


def plano_remocao(ids):
    ids = set(ids)
    protegidos = {caminho for i, j in JOBS.items() if i not in ids for caminho, _ in arquivos_do_job(j)}
    protegidos.add(reference_path('demo').resolve())
    apagar, mantidos, vistos = [], [], set()
    for i in ids:
        for caminho, tipo in arquivos_do_job(JOBS[i]):
            if caminho in vistos:
                continue
            vistos.add(caminho)
            if not caminho.is_file():
                continue
            if caminho in protegidos:
                mantidos.append((caminho, tipo, 'outra música usa este arquivo'))
            elif not pode_apagar(caminho):
                mantidos.append((caminho, tipo, 'fora das pastas do painel'))
            else:
                apagar.append((caminho, tipo, caminho.stat().st_size))
    return apagar, mantidos


async def executar_remocao(apagar):
    apagados, falhas, total = 0, [], 0
    for caminho, _tipo, tamanho in apagar:
        if TESTE:
            apagados, total = apagados + 1, total + tamanho  # simulação: nada sai do HD
            continue
        for tentativa in range(3):
            try:
                caminho.unlink(missing_ok=True)
                apagados, total = apagados + 1, total + tamanho
                DURACOES.pop(str(caminho), None)
                break
            except OSError:
                if tentativa == 2:
                    falhas.append(caminho.name)
                else:
                    await asyncio.sleep(0.5)
    return apagados, falhas, total


def _descrever(apagar, mantidos):
    return {'arquivos': [{'nome': c.name, 'tipo': t, 'mb': round(b / 2**20, 2)} for c, t, b in apagar],
            'mantidos': [{'nome': c.name, 'tipo': t, 'motivo': m} for c, t, m in mantidos],
            'mb': round(sum(b for *_, b in apagar) / 2**20, 1)}


async def remover_previa(request):
    job = JOBS.get(request.match_info['id'])
    if job is None:
        return erro_json('Música não encontrada.', 404)
    apagar, mantidos = plano_remocao([job['id']])
    return web.json_response({**_descrever(apagar, mantidos), 'titulo': job.get('title', ''), 'teste': TESTE})


async def favorito(request):
    """POST /api/favorito/{id} {"favorito": true|false}: marca ou desmarca a música como favorita (fica no jobs.json)."""
    try:
        dados = await request.json()
    except Exception:
        dados = {}
    async with LOCK:
        job = JOBS.get(request.match_info['id'])
        if not job or job.get('deleted_at'):
            raise web.HTTPNotFound(text='Música não encontrada.')
        if dados.get('favorito'):
            job['favorito'] = True
            job['favorito_em'] = time.time()
        else:
            job.pop('favorito', None)
            job.pop('favorito_em', None)
        save_jobs()
    return web.json_response({'ok': True, 'favorito': bool(job.get('favorito'))})


async def renomear(request):
    """POST /api/renomear/{id} {"titulo": "..."}: troca o nome da música (só no jobs.json; o arquivo no HD não muda)."""
    try:
        dados = await request.json()
    except Exception:
        dados = {}
    titulo = re.sub(r'\s+', ' ', str(dados.get('titulo') or '')).strip()[:120]
    if not titulo:
        return erro_json('Escreva um nome para a música.', 400)
    async with LOCK:
        job = JOBS.get(request.match_info['id'])
        if not job or job.get('deleted_at'):
            return erro_json('Música não encontrada.', 404)
        if job.get('state') in ('queued', 'running'):
            return erro_json('Espere a música terminar de gerar para trocar o nome.', 409)
        job['title'] = titulo
        save_jobs()
    return web.json_response({'ok': True, 'titulo': titulo})


async def remover(request):
    job_id = request.match_info['id']
    try:
        dados = await request.json()
    except Exception:
        dados = {}
    async with LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return erro_json('Música não encontrada (talvez já tenha sido apagada).', 404)
        if job['state'] == 'running':
            return erro_json('Esta música ainda está sendo gerada. Cancele ou espere terminar antes de apagar.', 409)
        if dados.get('confirmar') is not True:
            return erro_json('Confirme na tela para apagar do computador.', 400)
        apagar, mantidos = plano_remocao([job_id])
        apagados, falhas, total = await executar_remocao(apagar)
        if falhas:
            save_jobs()
            return erro_json('Alguns arquivos estão em uso e não foram apagados: ' + ', '.join(falhas[:3])
                             + '. Pare o player e tente de novo.', 409)
        JOBS.pop(job_id, None)
        PROGRESS.pop(job_id, None)
        save_jobs()
    return web.json_response({'ok': True, 'apagados': apagados, 'mb': round(total / 2**20, 1),
                              'mantidos': len(mantidos), 'simulado': TESTE})


async def esvaziar_lixeira(request):
    """A lixeira antiga (antes de 23/09). Esvaziar apaga do HD tudo o que estiver nela."""
    try:
        dados = await request.json()
    except Exception:
        dados = {}
    if dados.get('confirmar') is not True:
        return erro_json('Confirme na tela para esvaziar a lixeira.', 400)
    async with LOCK:
        ids = [i for i, j in JOBS.items() if j.get('deleted_at') and j['state'] != 'running']
        apagar, mantidos = plano_remocao(ids)
        apagados, falhas, total = await executar_remocao(apagar)
        if falhas:
            save_jobs()
            return erro_json('Alguns arquivos estão em uso e não foram apagados. Tente de novo.', 409)
        for i in ids:
            JOBS.pop(i, None)
        save_jobs()
    return web.json_response({'ok': True, 'removidos': len(ids), 'apagados': apagados,
                              'mb': round(total / 2**20, 1), 'simulado': TESTE})


async def rota_antiga(request):
    return erro_json('O painel foi atualizado: aperte F5 para recarregar a página.', 410)


# ---------------------------------------------------------------- áudio
def nome_download(job):
    motor = catalogo.motor_do_job(job, JOBS)[1]
    base = f"{job.get('title') or 'Música'} - {motor}"
    return re.sub(r'[\\/:*?"<>|]+', ' ', base).strip()[:150]


async def audio(request):
    job = JOBS.get(request.match_info['id'])
    if not job or job.get('deleted_at') or not job.get('audio'):
        raise web.HTTPNotFound()
    path = item_saida(job['audio'][0])
    if not path.is_relative_to(OUTPUT.resolve()):
        raise web.HTTPForbidden()
    if not path.is_file():
        raise web.HTTPNotFound()
    formato = request.query.get('formato', '').lower()
    if formato in FORMATOS_BAIXAR and path.suffix.lower() != '.' + formato:
        path = await converter_para_baixar(job, path, formato)
    elif request.query.get('baixar') == '1':  # baixar no formato original: cópia sem a receita da ComfyUI
        path = await converter_para_baixar(job, path, path.suffix.lower().lstrip('.'), copiar=True)
    cabecalhos = {'Content-Type': TIPOS_AUDIO.get(path.suffix.lower(), 'application/octet-stream')}
    if request.query.get('baixar') == '1':
        cabecalhos['Content-Disposition'] = "attachment; filename*=UTF-8''" + quote(nome_download(job) + path.suffix)
    return web.FileResponse(path, headers=cabecalhos)


# "Baixar em MP3 / WAV" (26/09): converte na hora e guarda a cópia em PAINEL_DADOS\baixar_convertido (apagada após 3 dias)
FORMATOS_BAIXAR = {
    'mp3': ['-c:a', 'libmp3lame', '-b:a', '320k', '-id3v2_version', '3'],  # a melhor qualidade de MP3
    'wav': ['-c:a', 'pcm_s16le'],                                            # sem perda (qualidade de CD)
}
PASTA_CONVERTIDOS = DADOS / 'baixar_convertido'


async def converter_para_baixar(job, origem, formato, copiar=False):
    PASTA_CONVERTIDOS.mkdir(parents=True, exist_ok=True)
    agora = time.time()
    for velho in PASTA_CONVERTIDOS.glob('*'):  # faxina: cópias com mais de 3 dias
        with contextlib.suppress(OSError):
            if agora - velho.stat().st_mtime > 3 * 86400:
                velho.unlink()
    destino = PASTA_CONVERTIDOS / f"{re.sub(r'[^A-Za-z0-9_-]', '_', job['id'])}_{int(origem.stat().st_mtime)}_limpo.{formato}"
    if destino.is_file() and destino.stat().st_size > 0:
        return destino
    temporario = destino.with_name(destino.stem + '.part.' + formato)
    processo = await asyncio.create_subprocess_exec(
        'ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', str(origem), '-vn', '-map_metadata', '0', *SEM_RECEITA,
        *(['-c', 'copy'] if copiar else FORMATOS_BAIXAR[formato]), str(temporario),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, creationflags=SEM_JANELA)
    _, erro = await processo.communicate()
    if processo.returncode != 0 or not temporario.is_file():
        with contextlib.suppress(OSError):
            temporario.unlink()
        raise ValueError('Não deu para converter a música para ' + formato.upper() + ': '
                         + erro.decode(errors='replace')[-200:])
    temporario.replace(destino)
    return destino


# ---------------------------------------------------------------- equalizador / masterizador (27/09)
# Roda no processador (Pedalboard + numpy), não usa a placa nem entra na fila de geração. Uma conta por vez: a prévia
# mais nova espera a anterior terminar (a tela cancela as antigas e o servidor pula as que ninguém espera mais).
EQ_TRAVA = asyncio.Lock()
# Campos do job original que apontam para arquivos de entrada: a cópia não herda (senão "Apagar" a cópia levaria junto
# ou protegeria para sempre o arquivo de outra música).
EQ_SEM_HERDAR = ('reference', 'entrada_cover', 'referencia_estilo', 'entrada_referencia', 'eq', 'eq_fonte',
                 'eq_fonte_titulo')


def _erro_http(classe, mensagem):
    return classe(text=json.dumps({'error': mensagem}, ensure_ascii=False), content_type='application/json')


def eq_musica(job_id):
    """(job, caminho do áudio) de uma música pronta; erro 404 em português se não der."""
    job = JOBS.get(str(job_id or ''))
    if not job or job.get('deleted_at') or job.get('state') != 'done' or not job.get('audio'):
        raise _erro_http(web.HTTPNotFound, 'Música não encontrada ou ainda não terminou.')
    path = item_saida(job['audio'][0])
    if not path.is_relative_to(OUTPUT.resolve()) or not path.is_file():
        raise _erro_http(web.HTTPNotFound, 'O arquivo desta música não está mais no HD.')
    return job, path


async def _json_pedido(request):
    try:
        dados = await request.json()
    except Exception:
        raise ValueError('Pedido inválido para o equalizador.') from None
    if not isinstance(dados, dict):
        raise ValueError('Pedido inválido para o equalizador.')
    return dados


def _cliente_foi_embora(request):
    transporte = request.transport
    return transporte is None or transporte.is_closing()


async def eq_analise(request):
    """GET /api/eq/analise/{id}: volume (LUFS), pico real, energia por faixa, sugestão do Auto EQ, trecho mais alto e
    o catálogo dos controles (faixas, predefinições, limites)."""
    job, path = eq_musica(request.match_info['id'])
    async with EQ_TRAVA:
        dados = await asyncio.to_thread(equalizador.analisar, path)
    return web.json_response({**dados, **equalizador.catalogo_tela(), 'id': job['id'], 'titulo': job.get('title', ''),
                              'motor_nome': catalogo.motor_do_job(job, JOBS)[1]})


async def eq_previa(request):
    """POST /api/eq/previa {id, ajustes, inicio_s, duracao_s (até 30), original?}: devolve o trecho em MP3.
    Com original=true é o MESMO trecho da música original, com o volume igualado ao da equalizada (comparação A/B).
    Os números (LUFS antes/depois, pico, faixas) vão no cabeçalho X-Eq-Info (JSON)."""
    dados = await _json_pedido(request)
    _job, path = eq_musica(dados.get('id'))
    ajustes = equalizador.normalizar_ajustes(dados.get('ajustes') or {})
    try:
        inicio, duracao = float(dados.get('inicio_s') or 0), float(dados.get('duracao_s') or 20)
    except (TypeError, ValueError):
        raise ValueError('O início e a duração da prévia devem ser números (em segundos).') from None
    if not (math.isfinite(inicio) and math.isfinite(duracao)):
        raise ValueError('O início e a duração da prévia devem ser números (em segundos).')
    if duracao > 30:
        raise ValueError('A prévia pode ter no máximo 30 segundos.')
    async with EQ_TRAVA:
        if _cliente_foi_embora(request):  # a tela já pediu outra prévia: não gasta processador com esta
            return web.Response(status=204)
        corpo, tipo, info = await asyncio.to_thread(equalizador.previa, path, ajustes, inicio, duracao,
                                                    bool(dados.get('original')))
    return web.Response(body=corpo, content_type=tipo,
                        headers={'X-Eq-Info': quote(json.dumps(info, ensure_ascii=False)), 'Cache-Control': 'no-store'})


def titulo_equalizada(titulo):
    base = re.sub(r'\s*\(equalizada(?: \d+)?\)\s*$', '', str(titulo or 'Música')).strip() or 'Música'
    return (base[:106] + ' (equalizada)')[:120]


async def eq_salvar(request):
    """POST /api/eq/salvar {id, ajustes, titulo?}: processa a música inteira e cria um job NOVO, já pronto, com o arquivo
    OUTPUT/audio/painel_eq_<id>.flac. Mesmo motor (selo) da original, detalhe "Equalizada" e settings.eq = ajustes.
    A original nunca é alterada."""
    dados = await _json_pedido(request)
    job, path = eq_musica(dados.get('id'))
    ajustes = equalizador.normalizar_ajustes(dados.get('ajustes') or {})
    titulo = str(dados.get('titulo') or '').strip()[:120] or titulo_equalizada(job.get('title'))
    codigo = uuid.uuid4().hex
    novo_id = 'eq-' + codigo
    nome = f'painel_eq_{codigo}.flac'
    destino = OUTPUT / 'audio' / nome
    item = {'filename': nome, 'subfolder': 'audio', 'type': 'output'}
    inicio = time.monotonic()
    async with EQ_TRAVA:
        info = await asyncio.to_thread(equalizador.salvar_flac, path, ajustes, destino)
    try:
        motor_nome = catalogo.motor_do_job(job, JOBS)[1]
        s_orig = job.get('settings') or {}
        estilo = s_orig.get('style_original') or catalogo.limpar_sufixo(s_orig.get('style', ''))
        resumo = equalizador.resumo(ajustes)
        await gravar_metadados(item, titulo, f'{motor_nome} · Equalizada ({resumo})', estilo)
        settings = {k: copy.deepcopy(v) for k, v in s_orig.items() if k not in EQ_SEM_HERDAR}
        settings.update(eq={**ajustes, 'resumo': resumo, 'lufs_final': info['lufs_depois'],
                            'pico_final': info['pico_real_depois'], 'lufs_original': info['lufs_antes']},
                        eq_fonte=job['id'], eq_fonte_titulo=job.get('title', ''))
        novo = {'id': novo_id, 'title': titulo, 'mode': job.get('mode', 'create'), 'created': time.time(),
                'seed': job.get('seed', 0), 'state': 'done', 'settings': settings, 'audio': [item],
                'equalizada': True, 'eq_segundos': round(time.monotonic() - inicio, 1)}
        duracao = duracao_item(item) or job.get('duracao_s')
        if duracao:
            novo['duracao_s'] = duracao
        for chave in ('voz_removida', 'treblo_letra', 'musicful_letra', 'treblo_tags'):
            if job.get(chave):
                novo[chave] = copy.deepcopy(job[chave])
        async with LOCK:
            JOBS[novo_id] = registrar_motor(novo)
            save_jobs()
    except BaseException:
        JOBS.pop(novo_id, None)
        destino.unlink(missing_ok=True)  # não deixa arquivo órfão no HD
        raise
    return web.json_response({'ok': True, 'job': job_para_tela(novo), 'info': info})


async def vigia_equalizador(app):
    """Solta a memória do equalizador (músicas lidas e processadas) depois de 10 minutos sem uso."""
    async def laco():
        while True:
            await asyncio.sleep(60)
            with contextlib.suppress(Exception):
                equalizador.liberar_se_parado(10)
    tarefa = asyncio.create_task(laco())
    yield
    tarefa.cancel()


# ---------------------------------------------------------------- contrato com o estúdio
def url_publica(job_id):
    return f'http://127.0.0.1:{PORTA}/api/audio/{job_id}'


async def recentes(request):
    try:
        n = max(1, min(50, int(request.query.get('n', 6))))
    except ValueError:
        n = 6
    feitos = sorted((j for j in JOBS.values() if j['state'] == 'done' and not j.get('deleted_at') and j.get('audio')),
                    key=lambda j: j.get('created', 0), reverse=True)[:n]
    lista = []
    for job in feitos:
        motor_id, motor_nome, _ = catalogo.motor_do_job(job, JOBS)
        s = job.get('settings') or {}
        lista.append({'id': job['id'], 'titulo': job.get('title', ''), 'motor_id': motor_id, 'motor_nome': motor_nome,
                      'url': url_publica(job['id']), 'duracao_s': job.get('duracao_s') or duracao_item(job['audio'][0]),
                      'criado': int(job.get('created', 0)),
                      'instrumental': bool(s.get('instrumental')) or s.get('engine') in ('stable-audio3', 'separador')})
    return web.json_response(lista)


async def ocupado(request):
    esta, motivo = await novos_motores.estado_ocupado(sys.modules[__name__])
    # "tipo" e "termina_em" (contrato do treino): por enquanto só música; "treino" entra com a tela de treino.
    # "na_fila": músicas gerando ou esperando a vez. O estúdio usa para não deixar desligar a ComfyUI com música
    # pendente (senão o painel pediria para ligar de novo logo em seguida).
    pendentes = sum(1 for j in JOBS.values() if j.get('state') == 'running')
    return web.json_response({'ocupado': esta, 'motivo': motivo, 'tipo': 'musica' if esta else None, 'termina_em': None,
                              'na_fila': pendentes})


# ---------------------------------------------------------------- IA de texto (fica no estúdio)
# Contrato: POST <estúdio>/api/texto {"tarefa", "entrada", "contexto", "modelo"?} → {"texto", "modelo", "onde", "segundos"}.
# O Estúdio decide se roda na placa (livre) ou no processador (placa ocupada) e responde "ocupado" enquanto usa a
# placa; a fila de música já consulta esse "ocupado" antes de mandar qualquer coisa para a placa.
# O painel repassa pelo próprio servidor (mesma origem): funciona dentro do Estúdio, fora dele e nas cópias de teste.
TEXTO_URL = (os.environ.get('PAINEL_TEXTO_URL') or ESTUDIO).rstrip('/')
TEXTO_TAREFAS = {'letra', 'melhorar_prompt'}
TEXTO_LIMITE_S = 15 * 60  # 1ª vez: a IA carrega do HD lento (~35–90 s); no processador ela escreve devagar
TEXTO_CONTEXTO = ('ia', 'estilo', 'idioma', 'preset', 'instrumental')
_PENSAMENTO = re.compile(r'<think>.*?</think>', re.S | re.I)
_CERCA = re.compile(r'^```[\w-]*[ \t]*\r?\n?|\r?\n?```\s*$')
SEM_ESTUDIO = ('O Forja Studio está desligado, e a IA de texto funciona por ele. Abra o Forja Studio '
               '(atalho na área de trabalho) e tente de novo.')
ESTUDIO_SEM_TEXTO = ('O Forja Studio está ligado, mas ainda não tem a IA de texto. Feche e abra o estúdio de novo '
                     'depois da atualização e tente outra vez.')


def limpar_texto_ia(texto, tarefa):
    """Tira o 'pensamento', cercas de código e aspas em volta que às vezes sobram na resposta da IA."""
    t = _CERCA.sub('', _PENSAMENTO.sub('', str(texto or '')).strip()).strip()
    if tarefa == 'melhorar_prompt' and len(t) >= 2 and t[0] in '"“\'' and t[-1] in '"”\'':
        t = t[1:-1].strip()
    return t


def _mensagem_do_estudio(corpo):
    if isinstance(corpo, dict):
        for chave in ('erro', 'error', 'mensagem', 'message', 'detail'):
            if isinstance(corpo.get(chave), str) and corpo[chave].strip():
                return corpo[chave].strip()
    return ''


async def texto_ia(request):
    if TESTE and not os.environ.get('PAINEL_TEXTO_URL'):
        return erro_json('Modo de teste: a IA de texto está desligada nesta cópia do painel.', 403)
    try:
        dados = await request.json()
    except Exception:
        raise ValueError('Pedido inválido para a IA de texto.') from None
    if not isinstance(dados, dict):
        raise ValueError('Pedido inválido para a IA de texto.')
    tarefa = dados.get('tarefa')
    if tarefa not in TEXTO_TAREFAS:
        raise ValueError('Tarefa de texto inválida.')
    entrada = str(dados.get('entrada') or '').strip()
    if not entrada:
        raise ValueError('Escreva o tema da letra.' if tarefa == 'letra' else 'Escreva algumas palavras do estilo primeiro.')
    if len(entrada) > 4000:
        raise ValueError('O texto para a IA ficou grande demais (máximo de 4.000 caracteres).')
    contexto = dados.get('contexto') if isinstance(dados.get('contexto'), dict) else {}
    contexto = {k: (v[:2000] if isinstance(v, str) else v) for k, v in contexto.items()
                if k in TEXTO_CONTEXTO and isinstance(v, (str, bool)) and v != ''}
    corpo = {'tarefa': tarefa, 'entrada': entrada, 'contexto': contexto}
    if dados.get('modelo') in ('rapido', 'principal'):
        corpo['modelo'] = dados['modelo']
    inicio = time.monotonic()
    try:
        async with ClientSession(timeout=ClientTimeout(total=TEXTO_LIMITE_S, sock_connect=3)) as sessao:
            async with sessao.post(TEXTO_URL + '/api/texto', json=corpo) as resposta:
                bruto, codigo = await resposta.text(), resposta.status
    except asyncio.TimeoutError:
        return erro_json(f'A IA de texto demorou mais de {TEXTO_LIMITE_S // 60} minutos e o painel desistiu de esperar. '
                         'Tente de novo; se repetir, escolha a IA rápida.', 504)
    except ClientError as exc:
        texto = str(exc).lower()
        if isinstance(exc, ClientConnectorError) or 'cannot connect' in texto or 'connect call failed' in texto:
            return erro_json(SEM_ESTUDIO, 503)
        return web.json_response({'error': 'A conexão com o Estúdio caiu no meio da resposta (ele pode ter sido '
                                           'reiniciado). Tente de novo.', 'erro_tecnico': str(exc)[:300]}, status=502)
    try:
        resposta_json = json.loads(bruto) if bruto.strip() else {}
    except ValueError:
        resposta_json = None
    if codigo in (404, 405) and not _mensagem_do_estudio(resposta_json):
        return erro_json(ESTUDIO_SEM_TEXTO, 503)
    if codigo >= 400 or not isinstance(resposta_json, dict):
        mensagem = _mensagem_do_estudio(resposta_json)
        frase = catalogo.traduzir_erro(mensagem, generico='A IA de texto informou um erro (veja o detalhe técnico).') \
            if mensagem else f'A IA de texto não conseguiu responder (código {codigo}).'
        corpo_erro = {'error': frase}
        if mensagem != frase or not mensagem:
            corpo_erro['erro_tecnico'] = (mensagem or bruto)[:300]
        return web.json_response(corpo_erro, status=codigo if codigo >= 400 else 502)
    texto = limpar_texto_ia(resposta_json.get('texto'), tarefa)
    if not texto:
        return erro_json('A IA de texto respondeu vazio. Tente de novo.', 502)
    segundos = resposta_json.get('segundos')
    if not isinstance(segundos, (int, float)) or isinstance(segundos, bool):
        segundos = round(time.monotonic() - inicio, 1)
    return web.json_response({'texto': texto, 'modelo': str(resposta_json.get('modelo') or ''),
                              'onde': str(resposta_json.get('onde') or ''), 'segundos': segundos})


async def fichas_api(request):
    """As fichas das IAs que ESTE pacote mostra (PAINEL_MOTORES). A do "Tirar voz" só entra se a ComfyUI tiver o nó."""
    ias = catalogo.fichas_musica()
    if not await tem_separador():
        ias.pop('separador', None)
    return web.json_response({'ias': ias, 'ordem': [i for i in catalogo.IDS_MUSICA if i in ias]})


# ---------------------------------------------------------------- interface
# Nomes diferentes dos da tela antiga (app.js → painel.js) e sempre com ?v= no index.html: um arquivo antigo guardado
# no navegador nunca é misturado com a tela nova.
ARQUIVOS_WEB = {'index.html', 'painel.js', 'estilo.css', 'generos.js', 'exemplos_estilo.js', 'sugestoes_estilo.js'}


async def static(request):
    name = request.match_info.get('name', 'index.html')
    if name in LEGADO_JS:  # só a tela antiga pede estes: troca a página pela tela nova
        return web.Response(text=RECARREGAR_JS, content_type='application/javascript', charset='utf-8',
                            headers={'Cache-Control': 'no-store'})
    if name not in ARQUIVOS_WEB or not (WEB / name).is_file():
        raise web.HTTPNotFound()
    return web.FileResponse(WEB / name, headers={'Cache-Control': 'no-cache'})


# ---------------------------------------------------------------- a ComfyUI é do estúdio: o painel só pede
# Até 13/11/2026 o painel tinha uma ComfyUI só dele: ligava ao gerar e DESLIGAVA depois de 15 min sem música. Agora a
# ComfyUI é a mesma da imagem e do vídeo, e quem manda nela é o estúdio. Desligá-la daqui derrubaria um vídeo no
# meio; ligá-la daqui criaria duas no mesmo disco. Por isso o painel só faz duas coisas: pergunta se ela está no ar
# e, se não estiver, PEDE ao estúdio para ligar. Quem economiza a memória da placa é o estúdio (ESTUDIO_LIBERAR_MIN).
ULTIMA_ATIVIDADE = {'t': time.time()}
LIGANDO = asyncio.Lock()
PEDIDO_COMFY = {'t': 0.0, 'ok': False, 'erro': ''}
PEDIR_DE_NOVO_S = 30
SEPARADOR = {'t': 0.0, 'tem': False}


def marcar_atividade():
    ULTIMA_ATIVIDADE['t'] = time.time()


async def tem_separador():
    """O "Tirar voz" usa um nó que NÃO vem no pacote (MelBandRoFormer). Se esta ComfyUI tiver o nó, o botão aparece;
    sem ele, a tela nem oferece. Pergunta à ComfyUI no máximo 1 vez por minuto; com ela desligada vale a última
    resposta (e, sem resposta nenhuma ainda, vale "não tem")."""
    if not (WORKFLOWS / novos_motores.SEPARAR).is_file():
        return False
    if SEPARADOR['t'] and time.monotonic() - SEPARADOR['t'] < 60:
        return SEPARADOR['tem']
    try:
        info = await comfy('GET', '/object_info/MelBandRoFormerSampler')
        SEPARADOR.update(t=time.monotonic(), tem=bool(isinstance(info, dict) and info.get('MelBandRoFormerSampler')))
    except Exception:
        pass
    return SEPARADOR['tem']


async def pedir_comfy_ao_estudio(forcar=False):
    """Pede ao estúdio para ligar a ComfyUI. Devolve True se o estúdio aceitou o pedido (ligar leva 1 a 2 min).

    No máximo 1 pedido a cada 30 s: a fila chama isto a cada volta enquanto houver música esperando. Quando o estúdio
    diz por que não ligou (motor não instalado, por exemplo), o motivo fica em PEDIDO_COMFY['erro'] e vai para a tela."""
    if TESTE:
        return False
    agora = time.monotonic()
    if not forcar and PEDIDO_COMFY['t'] and agora - PEDIDO_COMFY['t'] < PEDIR_DE_NOVO_S:
        return PEDIDO_COMFY['ok']
    PEDIDO_COMFY['t'] = agora
    ok, erro = False, ''
    try:
        async with ClientSession(timeout=ClientTimeout(total=20)) as sessao:
            async with sessao.post(ESTUDIO + '/api/servicos/ligar', json={'servico': 'video'}) as resposta:
                corpo = await resposta.json(content_type=None)
                codigo = resposta.status
        if not isinstance(corpo, dict):
            corpo = {}
        ok = codigo == 200
        video = (corpo.get('servicos') or {}).get('video') or {}
        # "erro_anterior": por que a tentativa de antes não deu certo (o pedido de agora já voltou a "ligando")
        anterior = (corpo.get('erro_anterior') or {}).get('video') if isinstance(corpo.get('erro_anterior'), dict) else None
        if video.get('estado') == 'erro':
            ok, erro = False, str(video.get('mensagem') or 'O estúdio não conseguiu ligar a ComfyUI.')
        elif anterior:
            erro = str(anterior)
        elif not ok:
            erro = str(corpo.get('erro') or f'O estúdio recusou o pedido (código {codigo}).')
    except Exception as exc:
        erro = ('O Forja Studio não respondeu, e é ele quem liga a ComfyUI. Abra o Forja Studio (atalho na área de '
                'trabalho).')
        print(f'[música] não consegui pedir a ComfyUI ao estúdio ({ESTUDIO}): {exc!r}', flush=True)
    if erro and erro != PEDIDO_COMFY['erro']:
        print(f'[música] a ComfyUI não ligou: {erro}', flush=True)
    elif ok and not PEDIDO_COMFY['ok']:
        print('[música] pedi ao estúdio para ligar a ComfyUI (a música espera na fila).', flush=True)
    PEDIDO_COMFY.update(ok=ok, erro=erro)
    return ok


async def servico_no_ar(tipo):
    try:
        if tipo == 'ace':
            await ace_backend.call('GET', '/health')
        else:
            await comfy('GET', '/queue')
        return True
    except Exception:
        return False


async def garantir_servicos(precisa, esperar=True):
    """Confere o que a música vai precisar ('comfy' e/ou 'ace'). A ComfyUI desligada é PEDIDA ao estúdio; com
    esperar=True, espera responder (até 3 min). O ACE-Step não vem no pacote e o painel não o liga: se o pedido
    precisa dele e ele não responde, devolve False."""
    marcar_atividade()
    if TESTE:
        return True
    async with LIGANDO:
        for tipo in precisa:
            if await servico_no_ar(tipo):
                if tipo == 'comfy':
                    PEDIDO_COMFY.update(ok=False, erro='')
                continue
            if tipo == 'ace':
                return False
            await pedir_comfy_ao_estudio(forcar=True)
            if not esperar:
                continue
            for _ in range(90):
                await asyncio.sleep(2)
                if await servico_no_ar(tipo):
                    PEDIDO_COMFY.update(ok=False, erro='')
                    break
            else:
                return False
    return True


async def manter_ligado(request):
    """POST /api/manter-ligado: o dono apertou "Ligar música" no estúdio com o painel já no ar. O estúdio já liga a
    ComfyUI por conta própria; aqui só fica registrado que a música está em uso (rota mantida do painel antigo)."""
    marcar_atividade()
    return web.json_response({'ok': True, 'ligando': [], 'comfy': await servico_no_ar('comfy')})


async def startup(app):
    print(f'Painel de música na porta {PORTA} | ComfyUI: {BASE} ({COMFY}) | estúdio: {ESTUDIO} | dados: {DADOS} | '
          f'IAs: {", ".join(catalogo.MOTORES) or "nenhuma"}', flush=True)
    if not (COMFY / 'main.py').is_file():
        print(f'[música] ATENÇÃO: não achei a ComfyUI em {COMFY}. O painel abre, mas só gera depois que o motor for '
              'instalado pelo Início do estúdio.', flush=True)
    for motor in catalogo.MOTORES:
        falta = faltam_modelos(motor)
        if falta:
            print(f'[música] {catalogo.nome(motor)}: falta baixar {", ".join(falta)}.', flush=True)
    if equalizador.pb is None:
        print('[música] equalizador desligado: o pacote "pedalboard" não está neste Python (o resto funciona).',
              flush=True)
    if TESTE:
        print('PAINEL EM MODO DE TESTE: não processa fila, não pede a ComfyUI e não gera nada.', flush=True)
        return
    marcar_atividade()

app = web.Application(middlewares=[errors], client_max_size=100 * 1024 * 1024)
app['panel_module'] = sys.modules[__name__]
if not TESTE:
    for _motor in (ace_backend, treblo_backend, musicful_backend):
        if _motor.presente:
            app.cleanup_ctx.append(_motor.context)
    app.cleanup_ctx.append(novos_motores.context)
    app.cleanup_ctx.append(progress_context)
app.cleanup_ctx.append(vigia_equalizador)  # também no modo de teste (o equalizador funciona nele)
app.on_startup.append(startup)
app.add_routes([
    web.get('/api/eq/analise/{id}', eq_analise), web.post('/api/eq/previa', eq_previa), web.post('/api/eq/salvar', eq_salvar),
    web.get('/api/system', system_metrics), web.get('/api/status', status), web.post('/api/upload', upload),
    web.get('/api/reference/{name}', reference), web.post('/api/generate', generate), web.get('/api/jobs', jobs),
    web.post('/api/cancel/{id}', cancel), web.post('/api/separar/{id}', separar), web.get('/api/audio/{id}', audio),
    web.get('/api/remover/{id}/previa', remover_previa), web.post('/api/remover/{id}', remover), web.post('/api/favorito/{id}', favorito),
    web.post('/api/renomear/{id}', renomear),
    web.post('/api/esvaziar-lixeira', esvaziar_lixeira),
    web.get('/api/recentes', recentes), web.get('/api/ocupado', ocupado), web.get('/api/fichas', fichas_api),
    web.post('/api/manter-ligado', manter_ligado),
    web.post('/api/texto', texto_ia), web.post('/api/referencia-da-biblioteca/{id}', referencia_da_biblioteca)])
# IAs pagas na nuvem: as rotas só existem se o arquivo do motor estiver na pasta (não vêm no pacote)
if treblo_backend.presente:
    app.add_routes([web.get('/api/treblo/saldo', treblo_backend.saldo), web.post('/api/treblo/chave', treblo_backend.trocar_chave)])
if musicful_backend.presente:
    app.add_routes([web.get('/api/musicful/saldo', musicful_backend.saldo),
                    web.post('/api/musicful/chave', musicful_backend.trocar_chave)])
app.add_routes([
    web.options('/api/{rota:.*}', preflight),
    # rotas da lixeira antiga: uma aba aberta com a versão velha recebe um aviso para recarregar
    web.post('/api/trash/{id}', rota_antiga), web.post('/api/restore/{id}', rota_antiga), web.post('/api/empty-trash', rota_antiga),
    web.get('/', static), web.get('/{name}', static)])

if __name__ == '__main__':
    if TESTE:  # no teste, registra cada pedido (ajuda a conferir se as consultas param com a aba escondida)
        import logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    web.run_app(app, host='127.0.0.1', port=PORTA, print=lambda message: print(message, flush=True))
