"""Equalizador / masterizador do painel de música (27/09/2026).

Pedido do dono: escolher uma música pronta, mexer no som (EQ, compressor, largura, volume) ouvindo uma prévia na hora
e, só se clicar em "Salvar como cópia", criar uma música NOVA "(equalizada)". A original nunca é alterada.

Roda no processador (sem placa, sem ComfyUI, fora da fila de geração):
- filtros e compressor: Pedalboard (Spotify, pacote "pedalboard");
- largura estéreo (Mid/Side), medição de volume (LUFS, ITU-R BS.1770 com filtro K), pico real aproximado (4x) e o
  limitador com antecipação: numpy/scipy, aqui mesmo. O Limiter do Pedalboard não serve para masterizar: ele tem um
  compressor fixo interno (-10 dB, 4:1) e muda o volume de tudo (medido em 27/09: -20 dB entra, -15,3 dB sai).

Crédito: a ideia e vários números vêm do ComfyUI_MD_Nodes de MDMAchine (github.com/MDMAchine/ComfyUI_MD_Nodes,
licença GPL v3), lido em 27/09/2026 sem instalar nada na ComfyUI:
- MD_AudioAutoEQ (core/audio_autoeq_core.py): medir a energia média por faixa, comparar com um perfil-alvo
  (o "Music Master"/"Rock/Metal"), converter a diferença em ganho de filtro e limitar o ganho;
- Mastering Chain (core/mastering_core.py): a ordem ganho → EQ → compressor → limitador e os padrões do compressor
  (ataque 20 ms, liberação 250 ms, razão 2,5:1) e dos filtros de prateleira (Q 0,707);
- AutoMaster (core/automaster_core.py): largura estéreo por Mid/Side, normalizar para um alvo em LUFS e teto do
  limitador em -1 dB.
O código abaixo foi escrito do zero para o painel (não é cópia do MD_Nodes).
"""
import io
import json
import math
import os
import subprocess
import tempfile
import threading
import time
import uuid
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from scipy import ndimage, signal

try:
    import pedalboard as pb
    from pedalboard.io import AudioFile
except ImportError:  # a tela mostra o aviso; o resto do painel continua funcionando
    pb = None
    AudioFile = None

SEM_PEDALBOARD = ('O equalizador precisa do pacote "pedalboard", que não está instalado no Python da ComfyUI. '
                  'Para ativar, rode na pasta ComfyUI_windows_portable: '
                  'python_embeded\\python.exe -s -m pip install pedalboard') if os.name == 'nt' else (
                  'O equalizador precisa do pacote "pedalboard", que não está instalado no Python da ComfyUI. '
                  'Para ativar, rode na pasta ComfyUI_mac: venv/bin/python -s -m pip install pedalboard')
SEM_JANELA = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
# A pasta de temporários é a do ambiente (o estúdio aponta TEMP para o _cache dele ao ligar o painel).
PASTA_TEMP = Path(tempfile.gettempdir())

# ---------------------------------------------------------------- faixas do EQ
# (id, nome, frequência central do filtro, tipo, faixa medida na análise)
FAIXAS = (
    ('sub', 'Sub', 60, 'grave', (30, 90)),
    ('graves', 'Graves', 150, 'pico', (90, 250)),
    ('medios_graves', 'Médios-graves', 400, 'pico', (250, 630)),
    ('medios', 'Médios', 1000, 'pico', (630, 1800)),
    ('presenca', 'Presença', 3000, 'pico', (1800, 5500)),
    ('brilho', 'Brilho', 10000, 'agudo', (5500, 16000)),
)
IDS_FAIXAS = tuple(f[0] for f in FAIXAS)
Q_PICO = 1.0          # largura de ~1,4 oitava (o Q "moderado" do MD_AudioAutoEQ)
Q_PRATELEIRA = 0.707  # como os filtros de prateleira do MD Mastering Chain
REFERENCIA_LUFS = -18.0  # a música entra no compressor sempre neste volume: o limiar vale igual para toda música
ALVOS_LUFS = (-14.0, -11.0, -9.0)

# ---------------------------------------------------------------- predefinições
def _aj(corte, eq, comp, largura=100, ganho=0.0, lufs=-14.0, limitador=True, teto=-1.0):
    ligado, limiar, razao, ataque, liberacao = comp
    return {'corte_graves_hz': corte, 'eq': dict(zip(IDS_FAIXAS, eq)),
            'compressor': {'ligado': ligado, 'limiar_db': limiar, 'razao': razao, 'ataque_ms': ataque,
                           'liberacao_ms': liberacao},
            'largura_pct': largura, 'ganho_db': ganho, 'lufs_alvo': lufs,
            'limitador': {'ligado': limitador, 'teto_db': teto}}


PREDEFINICOES = OrderedDict([
    ('natural', {'nome': 'Natural (só volume)', 'curto': 'Natural',
                 'descricao': 'Não mexe no timbre: só acerta o volume para o padrão das plataformas e segura os picos.',
                 'ajustes': _aj(20, (0, 0, 0, 0, 0, 0), (False, -14, 2, 20, 250))}),
    ('streaming', {'nome': 'Pronta para streaming', 'curto': 'Streaming',
                   'descricao': 'Leve limpeza nos médios-graves, um pouco de brilho, compressão suave e volume de '
                                'Spotify/YouTube (-14 LUFS).',
                   'ajustes': _aj(30, (0, 0.5, -1, 0, 1, 1.5), (True, -14, 2, 20, 250), largura=105)}),
    ('rock', {'nome': 'Rock / Metal pesado', 'curto': 'Rock/Metal',
              'descricao': 'Graves com peso, menos "caixa" nos médios-graves, guitarras e voz na frente, compressão '
                           'mais firme e volume alto (-11 LUFS).',
              'ajustes': _aj(35, (1, 2, -3, 0, 2.5, 2), (True, -18, 3, 10, 150), largura=110, lufs=-11.0)}),
    ('voz', {'nome': 'Voz na frente', 'curto': 'Voz na frente',
             'descricao': 'Tira um pouco de grave e de embolado e realça a faixa da voz (1 a 3 kHz).',
             'ajustes': _aj(40, (-1, -1, -2, 1.5, 3, 1), (True, -16, 2.5, 15, 200), largura=95)}),
    ('graves', {'nome': 'Mais graves', 'curto': 'Mais graves',
                'descricao': 'Mais peso no sub e nos graves, sem embolar (corta um pouco dos médios-graves).',
                'ajustes': _aj(25, (4, 3, -1.5, 0, 0, 0.5), (True, -14, 2, 30, 300))}),
    ('suave', {'nome': 'Suave / Acústico', 'curto': 'Suave',
               'descricao': 'Menos aspereza na presença, um toque de ar nos agudos, compressão bem leve e som mais '
                            'aberto.',
               'ajustes': _aj(30, (-1, 0, 0.5, 0, -1.5, 1), (True, -12, 1.5, 30, 400), largura=110)}),
])
PADRAO = 'streaming'

LIMITES = {
    'corte_graves_hz': (20, 120), 'eq': (-12, 12), 'limiar_db': (-40, 0), 'razao': (1, 10), 'ataque_ms': (1, 100),
    'liberacao_ms': (20, 1000), 'largura_pct': (0, 150), 'ganho_db': (-12, 12), 'teto_db': (-3, -0.1),
}


def _numero(valor, nome, minimo, maximo, unidade=''):
    try:
        v = float(valor)
    except (TypeError, ValueError):
        raise ValueError(f'{nome}: use um número.') from None
    if not math.isfinite(v) or not (minimo <= v <= maximo):
        raise ValueError(f'{nome} deve ficar entre {_br(minimo)} e {_br(maximo)}{unidade}.')
    return round(v, 2)


def normalizar_ajustes(dados):
    """Confere os ajustes vindos da tela e devolve um dicionário limpo (erros em português)."""
    if not isinstance(dados, dict):
        raise ValueError('Ajustes do equalizador inválidos.')
    base = PREDEFINICOES[PADRAO]['ajustes']
    preset = dados.get('preset') if dados.get('preset') in PREDEFINICOES else 'personalizado'
    eq_in = dados.get('eq') if isinstance(dados.get('eq'), dict) else {}
    eq = {}
    for fid, nome, hz, *_ in FAIXAS:
        eq[fid] = _numero(eq_in.get(fid, 0), f'O ganho da faixa {nome} ({_hz(hz)})', *LIMITES['eq'], ' dB')
    c_in = dados.get('compressor') if isinstance(dados.get('compressor'), dict) else {}
    cb = base['compressor']
    comp = {'ligado': bool(c_in.get('ligado', False)),
            'limiar_db': _numero(c_in.get('limiar_db', cb['limiar_db']), 'O limiar do compressor', *LIMITES['limiar_db'], ' dB'),
            'razao': _numero(c_in.get('razao', cb['razao']), 'A razão do compressor', *LIMITES['razao'], ':1'),
            'ataque_ms': _numero(c_in.get('ataque_ms', cb['ataque_ms']), 'O ataque do compressor', *LIMITES['ataque_ms'], ' ms'),
            'liberacao_ms': _numero(c_in.get('liberacao_ms', cb['liberacao_ms']), 'A liberação do compressor',
                                    *LIMITES['liberacao_ms'], ' ms')}
    l_in = dados.get('limitador') if isinstance(dados.get('limitador'), dict) else {}
    lim = {'ligado': bool(l_in.get('ligado', True)),
           'teto_db': _numero(l_in.get('teto_db', -1.0), 'O teto do limitador', *LIMITES['teto_db'], ' dB')}
    lufs = dados.get('lufs_alvo', -14.0)
    if lufs in (None, '', 'nenhum', 'sem'):
        lufs = None
    else:
        try:
            lufs = float(lufs)
        except (TypeError, ValueError):
            lufs = float('nan')
        if lufs not in ALVOS_LUFS:
            raise ValueError('Volume alvo inválido: escolha -14, -11 ou -9 LUFS, ou "Sem normalizar".')
    return {'preset': preset,
            'corte_graves_hz': _numero(dados.get('corte_graves_hz', base['corte_graves_hz']), 'O corte de graves',
                                       *LIMITES['corte_graves_hz'], ' Hz'),
            'eq': eq, 'compressor': comp,
            'largura_pct': _numero(dados.get('largura_pct', 100), 'A largura estéreo', *LIMITES['largura_pct'], '%'),
            'ganho_db': _numero(dados.get('ganho_db', 0), 'O ganho extra', *LIMITES['ganho_db'], ' dB'),
            'lufs_alvo': lufs, 'limitador': lim}


def _br(x, casas=1):
    return f'{round(float(x), casas):g}'.replace('.', ',')


def _hz(hz):
    return f'{hz / 1000:g} kHz'.replace('.', ',') if hz >= 1000 else f'{hz:g} Hz'


def resumo(ajustes):
    """Texto curto para o cartão: "EQ Rock/Metal · -11 LUFS"."""
    nome = PREDEFINICOES[ajustes['preset']]['curto'] if ajustes.get('preset') in PREDEFINICOES else 'Personalizada'
    alvo = ajustes.get('lufs_alvo')
    return f"{nome} · {alvo:g} LUFS" if alvo is not None else f'{nome} · volume original'


# ---------------------------------------------------------------- leitura do áudio (com cache pequeno)
_TRAVA = threading.Lock()
_ENTRADAS = OrderedDict()   # (caminho, mtime) -> (audio (canais, amostras) float32, taxa)
_ANALISES = OrderedDict()   # (caminho, mtime) -> análise
_PROCESSADOS = OrderedDict()  # (caminho, mtime, ajustes) -> resultado do processamento


_ULTIMO_USO = {'t': time.monotonic()}


def liberar_se_parado(minutos=10):
    """Solta a memória (músicas lidas e processadas, ~100 MB cada) se o equalizador ficou parado por `minutos`."""
    if time.monotonic() - _ULTIMO_USO['t'] < minutos * 60:
        return False
    with _TRAVA:
        vazio = not (_ENTRADAS or _PROCESSADOS or _CADEIAS)
        for cache in (_ENTRADAS, _ANALISES, _PROCESSADOS, _CADEIAS):
            cache.clear()
    return not vazio


def _guardar(cache, chave, valor, maximo):
    _ULTIMO_USO['t'] = time.monotonic()
    cache[chave] = valor
    cache.move_to_end(chave)
    while len(cache) > maximo:
        cache.popitem(last=False)


def _chave(path):
    st = Path(path).stat()
    return str(Path(path).resolve()), st.st_mtime_ns, st.st_size


def ler_audio(path):
    """(áudio float32 (canais, amostras), taxa). FLAC/WAV/MP3/OGG pelo Pedalboard; outros formatos pelo ffmpeg."""
    if pb is None:
        raise ValueError(SEM_PEDALBOARD)
    path = Path(path)
    if not path.is_file():
        raise ValueError('O arquivo desta música não está mais no HD.')
    chave = _chave(path)
    with _TRAVA:
        if chave in _ENTRADAS:
            _ENTRADAS.move_to_end(chave)
            return _ENTRADAS[chave]
    try:
        with AudioFile(str(path)) as f:
            audio, taxa = f.read(f.frames), int(round(f.samplerate))
    except Exception:
        audio, taxa = _ler_com_ffmpeg(path)
    audio = np.ascontiguousarray(audio, dtype=np.float32)
    if audio.ndim != 2 or audio.shape[1] < taxa:  # menos de 1 segundo
        raise ValueError('A música é curta demais para equalizar (menos de 1 segundo).')
    if audio.shape[0] > 2:
        audio = audio[:2]
    with _TRAVA:
        _guardar(_ENTRADAS, chave, (audio, taxa), 2)
    return audio, taxa


def _ler_com_ffmpeg(path):
    PASTA_TEMP.mkdir(parents=True, exist_ok=True)
    temporario = PASTA_TEMP / f'eq_leitura_{uuid.uuid4().hex}.wav'
    try:
        r = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', str(path), '-vn', '-c:a', 'pcm_f32le',
                            str(temporario)], capture_output=True, creationflags=SEM_JANELA, timeout=300)
        if r.returncode or not temporario.is_file():
            raise ValueError('Não foi possível ler o áudio desta música: '
                             + r.stderr.decode(errors='replace')[-200:])
        with AudioFile(str(temporario)) as f:
            return f.read(f.frames), int(round(f.samplerate))
    finally:
        temporario.unlink(missing_ok=True)


# ---------------------------------------------------------------- medições
def _filtro_k(taxa):
    """Coeficientes do filtro K (ITU-R BS.1770): prateleira de agudos +4 dB e passa-altas de ~38 Hz."""
    g, q, fc = 4.0, 1 / math.sqrt(2), 1500.0
    a = 10 ** (g / 40)
    w0 = 2 * math.pi * fc / taxa
    alfa, cw = math.sin(w0) / (2 * q), math.cos(w0)
    b1 = [a * ((a + 1) + (a - 1) * cw + 2 * math.sqrt(a) * alfa), -2 * a * ((a - 1) + (a + 1) * cw),
          a * ((a + 1) + (a - 1) * cw - 2 * math.sqrt(a) * alfa)]
    a1 = [(a + 1) - (a - 1) * cw + 2 * math.sqrt(a) * alfa, 2 * ((a - 1) - (a + 1) * cw),
          (a + 1) - (a - 1) * cw - 2 * math.sqrt(a) * alfa]
    q2, fc2 = 0.5, 38.0
    w0 = 2 * math.pi * fc2 / taxa
    alfa, cw = math.sin(w0) / (2 * q2), math.cos(w0)
    b2 = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]
    a2 = [1 + alfa, -2 * cw, 1 - alfa]
    return np.vstack([signal.tf2sos(b1, a1), signal.tf2sos(b2, a2)])


def _energia_k(audio, taxa):
    """Energia por amostra depois do filtro K (soma dos canais, peso 1 para esquerdo e direito)."""
    energia = np.zeros(audio.shape[1], dtype=np.float64)
    sos = _filtro_k(taxa)
    for canal in audio:
        y = signal.sosfilt(sos, canal.astype(np.float64))
        energia += y * y
    return energia.astype(np.float32)


def _blocos(energia, taxa, bloco_s=0.4, passo_s=0.1):
    """Média da energia em blocos de 400 ms com passo de 100 ms (75% de sobreposição)."""
    bloco, passo = int(bloco_s * taxa), int(passo_s * taxa)
    if energia.size < bloco:
        return np.array([energia.mean()]) if energia.size else np.array([0.0])
    acumulado = np.concatenate([[0.0], np.cumsum(energia, dtype=np.float64)])
    inicios = np.arange(0, energia.size - bloco + 1, passo)
    return (acumulado[inicios + bloco] - acumulado[inicios]) / bloco


def _blocos_k(audio, taxa, bloco_s=0.4, passo_s=0.1):
    return _blocos(_energia_k(audio, taxa), taxa, bloco_s, passo_s)


def lufs(audio, taxa):
    """Volume integrado (LUFS) pelo ITU-R BS.1770-4: blocos de 400 ms, porta absoluta -70 e relativa -10 LU."""
    return _lufs_blocos(_blocos_k(audio, taxa))


def _lufs_blocos(z):
    with np.errstate(divide='ignore'):
        nivel = -0.691 + 10 * np.log10(z)
    z = z[nivel > -70]
    if not z.size:
        return float('-inf')
    relativo = -0.691 + 10 * np.log10(z.mean()) - 10
    with np.errstate(divide='ignore'):
        z = z[-0.691 + 10 * np.log10(z) > relativo]
    return float(-0.691 + 10 * np.log10(z.mean())) if z.size else float('-inf')


_TRABALHADORES = ThreadPoolExecutor(max_workers=max(2, min(8, (os.cpu_count() or 4) // 2)),
                                    thread_name_prefix='equalizador')


def _envelope_pico_real(audio, fator=4, bloco=1 << 19):
    """Envelope do pico real por amostra (maior valor absoluto com 4x de sobreamostragem, o maior entre os canais).
    Em pedaços e em paralelo (a sobreamostragem do scipy solta o GIL): ~0,2 s numa música de 3,5 min."""
    n = audio.shape[1]
    saida = np.empty(n, dtype=np.float32)
    borda = 64

    def pedaco(ini):
        a, b = max(0, ini - borda), min(n, ini + bloco + borda)
        trecho = signal.resample_poly(audio[:, a:b], fator, 1, axis=1)
        env = np.abs(trecho).max(axis=0)[: (b - a) * fator].reshape(b - a, fator).max(axis=1)
        env = np.maximum(env, np.abs(audio[:, a:b]).max(axis=0))
        saida[ini:min(n, ini + bloco)] = env[ini - a: ini - a + min(bloco, n - ini)]

    list(_TRABALHADORES.map(pedaco, range(0, n, bloco)))
    return saida


def pico_real_db(audio):
    pico = float(_envelope_pico_real(audio).max()) if audio.size else 0.0
    return 20 * math.log10(pico) if pico > 0 else float('-inf')


def energia_faixas(audio, taxa):
    """Nível de cada faixa do EQ em dB por oitava (o espectro médio da música inteira)."""
    freqs, psd = _espectro(audio, taxa)
    return {fid: _nivel_faixa(freqs, psd, faixa) for fid, _n, _hz, _t, faixa in FAIXAS}


def _espectro(audio, taxa):
    mono = audio.mean(axis=0)
    freqs, psd = signal.welch(mono, taxa, nperseg=8192, noverlap=4096, average='mean')
    return freqs, np.maximum(psd, 1e-20)


def _nivel_faixa(freqs, psd, faixa, resposta_db=None):
    lo, hi = faixa
    m = (freqs >= lo) & (freqs < hi)
    p = psd[m] if resposta_db is None else psd[m] * 10 ** (resposta_db[m] / 10)
    potencia = float(np.sum(p) * (freqs[1] - freqs[0]))
    return 10 * math.log10(max(potencia, 1e-20) / math.log2(hi / lo))


# ---------------------------------------------------------------- Auto EQ
# Curva-alvo "equilibrada" (dB por oitava, relativo aos médios), inspirada no perfil "Music Master" do MD_AudioAutoEQ
# (graves um pouco acima dos médios, agudos caindo) e no espectro médio de gravações comerciais em bandas de oitava.
# Conferida em 27/09 nas músicas do painel (YuE2 e Stable Audio 3): nenhuma sugestão passou de ±6 dB.
CURVA_ALVO = {'sub': 3.0, 'graves': 3.5, 'medios_graves': 1.0, 'medios': 0.0, 'presenca': -4.0, 'brilho': -10.0}
# Reforços arriscados ficam menores: sub demais faz o limitador "bombear" e brilho demais chia.
TETO_REFORCO = {'sub': 3.0, 'brilho': 4.0}
FORCA_AUTO = 0.7        # corrige 70% da diferença (o MD_AudioAutoEQ usa força ajustável; 100% soa artificial)
LIMITE_AUTO = 6.0       # nunca sugere mais que ±6 dB
ZONA_MORTA = 1.0        # diferenças menores que 1 dB ficam como estão
MOTIVOS = {
    'sub': ('sub-graves demais (ronco que embola)', 'falta peso no sub-grave'),
    'graves': ('graves embolados', 'graves magros, sem peso'),
    'medios_graves': ('som abafado, com cara de "caixa"', 'falta corpo nos instrumentos'),
    'medios': ('médios anasalados', 'médios escavados (voz e guitarras recuadas)'),
    'presenca': ('som áspero / estridente', 'falta definição (voz longe, sem clareza)'),
    'brilho': ('agudos chiados / sibilantes', 'som opaco, sem brilho'),
}


def _sos_faixa(fid, ganho_db, taxa):
    _f, _n, hz, tipo, _faixa = next(f for f in FAIXAS if f[0] == fid)
    a = 10 ** (ganho_db / 40)
    w0 = 2 * math.pi * hz / taxa
    cw, sw = math.cos(w0), math.sin(w0)
    if tipo == 'pico':
        alfa = sw / (2 * Q_PICO)
        b = [1 + alfa * a, -2 * cw, 1 - alfa * a]
        den = [1 + alfa / a, -2 * cw, 1 - alfa / a]
    else:
        alfa = sw / (2 * Q_PRATELEIRA)
        r = 2 * math.sqrt(a) * alfa
        if tipo == 'grave':
            b = [a * ((a + 1) - (a - 1) * cw + r), 2 * a * ((a - 1) - (a + 1) * cw), a * ((a + 1) - (a - 1) * cw - r)]
            den = [(a + 1) + (a - 1) * cw + r, -2 * ((a - 1) + (a + 1) * cw), (a + 1) + (a - 1) * cw - r]
        else:
            b = [a * ((a + 1) + (a - 1) * cw + r), -2 * a * ((a - 1) + (a + 1) * cw), a * ((a + 1) + (a - 1) * cw - r)]
            den = [(a + 1) - (a - 1) * cw + r, 2 * ((a - 1) - (a + 1) * cw), (a + 1) - (a - 1) * cw - r]
    return signal.tf2sos(b, den)


def auto_eq(freqs, psd, taxa):
    """Sugere os ganhos das 6 faixas para aproximar a música da curva-alvo (limitado a ±6 dB) e diz o motivo.

    Modelo linear: quanto cada filtro (com 1 dB) muda o nível de cada faixa medida, calculado com a resposta real dos
    filtros sobre o espectro da música; resolve por mínimos quadrados com um pouco de regularização."""
    niveis = np.array([_nivel_faixa(freqs, psd, f[4]) for f in FAIXAS])
    alvo = np.array([CURVA_ALVO[f[0]] for f in FAIXAS])
    desvio = niveis - alvo
    pesos = np.array([0.5, 1, 1, 1.2, 1, 0.8])  # o sub pesa menos (varia muito de gênero para gênero)
    desvio -= np.average(desvio, weights=pesos)  # só a forma importa: o volume o normalizador acerta
    queremos = -desvio * FORCA_AUTO
    queremos[np.abs(desvio) < ZONA_MORTA] = 0.0
    w = 2 * math.pi * freqs / taxa
    matriz = np.zeros((len(FAIXAS), len(FAIXAS)))
    for j, f in enumerate(FAIXAS):
        _w, h = signal.sosfreqz(_sos_faixa(f[0], 6.0, taxa), worN=w)
        resp = 20 * np.log10(np.maximum(np.abs(h), 1e-9))
        for i, fi in enumerate(FAIXAS):
            matriz[i, j] = (_nivel_faixa(freqs, psd, fi[4], resp) - niveis[i]) / 6.0
    lam = 0.05
    ganhos = np.linalg.solve(matriz.T @ matriz + lam * np.eye(len(FAIXAS)), matriz.T @ queremos)
    ganhos = np.clip(np.round(ganhos * 2) / 2, -LIMITE_AUTO, LIMITE_AUTO)
    for i, f in enumerate(FAIXAS):
        ganhos[i] = min(ganhos[i], TETO_REFORCO.get(f[0], LIMITE_AUTO))
    ganhos[np.abs(ganhos) < 0.5] = 0.0
    sugestao, motivos = {}, []
    for (fid, nome, hz, *_), g, d in zip(FAIXAS, ganhos, desvio):
        sugestao[fid] = float(g) + 0.0
        if abs(g) >= 1:
            texto = MOTIVOS[fid][0] if g < 0 else MOTIVOS[fid][1]
            motivos.append(f'{texto}: {g:+.1f} dB em {_hz(hz)}'.replace('.', ','))
    if not motivos:
        motivos.append('A música já está equilibrada: nenhuma faixa precisa mudar mais de 1 dB.')
    return {'ganhos': sugestao, 'motivos': motivos,
            'desvio_db': {f[0]: round(float(d), 1) for f, d in zip(FAIXAS, desvio)}}


def analisar(path):
    """Volume, pico real, energia por faixa, sugestão do Auto EQ e o trecho mais alto (para a prévia)."""
    audio, taxa = ler_audio(path)
    chave = _chave(path)
    with _TRAVA:
        if chave in _ANALISES:
            return _ANALISES[chave]
    inicio = time.perf_counter()
    volume = lufs(audio, taxa)
    if not math.isfinite(volume):
        raise ValueError('A música está em silêncio: não há o que equalizar.')
    freqs, psd = _espectro(audio, taxa)
    faixas = {f[0]: round(_nivel_faixa(freqs, psd, f[4]), 2) for f in FAIXAS}
    resultado = {
        'duracao_s': round(audio.shape[1] / taxa, 1), 'taxa': taxa, 'canais': int(audio.shape[0]),
        'lufs': round(volume, 1), 'pico_real_db': round(pico_real_db(audio), 1),
        'faixas': faixas, 'auto_eq': auto_eq(freqs, psd, taxa),
        'trecho_mais_alto_s': trecho_mais_alto(audio, taxa, 20),
        'segundos_analise': round(time.perf_counter() - inicio, 2),
    }
    with _TRAVA:
        _guardar(_ANALISES, chave, resultado, 8)
    return resultado


def trecho_mais_alto(audio, taxa, duracao_s):
    """Início (s) do trecho de `duracao_s` com mais volume (o refrão, quase sempre)."""
    z = _blocos_k(audio, taxa, 0.4, 0.5)
    n = max(1, int(duracao_s / 0.5))
    if z.size <= n:
        return 0.0
    media = np.convolve(z, np.ones(n) / n, mode='valid')
    return round(float(np.argmax(media)) * 0.5, 1)


# ---------------------------------------------------------------- cadeia de processamento
def _cadeia(audio, taxa, aj):
    """Corte de graves → EQ de 6 faixas → compressor (Pedalboard) → largura estéreo (Mid/Side)."""
    efeitos = [pb.HighpassFilter(cutoff_frequency_hz=float(aj['corte_graves_hz']))]
    for fid, _nome, hz, tipo, _faixa in FAIXAS:
        g = float(aj['eq'][fid])
        if abs(g) < 0.05:
            continue
        if tipo == 'grave':
            efeitos.append(pb.LowShelfFilter(cutoff_frequency_hz=hz, gain_db=g, q=Q_PRATELEIRA))
        elif tipo == 'agudo':
            efeitos.append(pb.HighShelfFilter(cutoff_frequency_hz=hz, gain_db=g, q=Q_PRATELEIRA))
        else:
            efeitos.append(pb.PeakFilter(cutoff_frequency_hz=hz, gain_db=g, q=Q_PICO))
    c = aj['compressor']
    if c['ligado'] and c['razao'] > 1:
        efeitos.append(pb.Compressor(threshold_db=float(c['limiar_db']), ratio=float(c['razao']),
                                     attack_ms=float(c['ataque_ms']), release_ms=float(c['liberacao_ms'])))
    saida = pb.Pedalboard(efeitos)(audio, taxa)
    largura = aj['largura_pct'] / 100
    if saida.shape[0] == 2 and abs(largura - 1) > 1e-3:
        meio = (saida[0] + saida[1]) * 0.5
        lado = (saida[0] - saida[1]) * (0.5 * largura)
        saida = np.stack([meio + lado, meio - lado])
    return saida.astype(np.float32, copy=False)


GROSSO = 32
CAMPOS_CADEIA = ('corte_graves_hz', 'eq', 'compressor', 'largura_pct')
_CADEIAS = OrderedDict()  # (caminho, mtime, parte da cadeia) -> sinal antes do volume final + medições


def _pre_volume(path, ajustes):
    """Etapa que depende só do timbre (corte, EQ, compressor, largura): o sinal e as medições que servem para acertar
    o volume depois. Mexer só no volume alvo, no ganho ou no limitador reaproveita esta etapa (prévia mais rápida)."""
    audio, taxa = ler_audio(path)
    parte = {k: ajustes[k] for k in CAMPOS_CADEIA}
    chave = (*_chave(path), json.dumps(parte, sort_keys=True))
    with _TRAVA:
        if chave in _CADEIAS:
            _CADEIAS.move_to_end(chave)
            return _CADEIAS[chave]
    analise = analisar(path)
    pre_ganho = REFERENCIA_LUFS - analise['lufs']  # o compressor sempre recebe a música em -18 LUFS
    y = _cadeia(audio * np.float32(10 ** (pre_ganho / 20)), taxa, ajustes)
    tarefa_energia = _TRABALHADORES.submit(_energia_k, y, taxa)  # medições em paralelo com o envelope de pico
    tarefa_espectro = _TRABALHADORES.submit(_espectro, y, taxa)
    envelope = _envelope_pico_real(y)
    energia = tarefa_energia.result()
    freqs, psd = tarefa_espectro.result()
    volume = _lufs_blocos(_blocos(energia, taxa))
    if not math.isfinite(volume):
        raise ValueError('Com esses ajustes a música ficou em silêncio. Diminua o corte de graves ou os cortes do EQ.')
    # versões "grossas" (1 valor a cada 32 amostras) para acertar o volume em rodadas rápidas
    n = energia.size // GROSSO * GROSSO
    resultado = {'y': y, 'taxa': taxa, 'energia': energia, 'envelope': envelope, 'lufs': volume,
                 'energia_grossa': energia[:n].reshape(-1, GROSSO).mean(axis=1),
                 'envelope_grosso': envelope[:n].reshape(-1, GROSSO).max(axis=1),
                 'faixas': {f[0]: _nivel_faixa(freqs, psd, f[4]) for f in FAIXAS}, 'analise': analise}
    with _TRAVA:
        _guardar(_CADEIAS, chave, resultado, 1)
    return resultado


def _ganho_limitador(envelope, taxa, teto_db, janela_ms=30.0):
    """Ganho por amostra do limitador com antecipação (None se nenhum pico passa do teto).

    Ganho pedido = teto / pico real. O mínimo numa janela centrada (antecipa e segura) seguido da média numa janela
    com a metade do tamanho garante ganho <= pedido em toda amostra e sobe/desce suave, sem estalo e sem laço."""
    teto = 10 ** (teto_db / 20)
    if float(envelope.max()) <= teto:
        return None
    pedido = np.minimum(1.0, teto / np.maximum(envelope, 1e-9)).astype(np.float32)
    n = max(3, int(janela_ms / 1000 * taxa) | 1)
    ganho = ndimage.minimum_filter1d(pedido, size=2 * n + 1, mode='nearest')
    ganho = ndimage.uniform_filter1d(ganho, size=n, mode='nearest')
    return np.minimum(ganho, pedido)  # arredondamento do filtro de média: garante o teto


def _limitar(audio, taxa, teto_db, janela_ms=30.0):
    """Limitador aplicado direto num áudio (usado na prévia do original com o volume igualado)."""
    ganho = _ganho_limitador(_envelope_pico_real(audio), taxa, teto_db, janela_ms)
    return audio if ganho is None else audio * ganho[None, :]


def processar(path, ajustes):
    """A música inteira com os ajustes. Resultado guardado (a prévia só recorta um trecho dele).

    O volume final (alvo em LUFS + ganho extra, com o limitador) é acertado em rodadas rápidas sem reprocessar o
    áudio: o envelope de pico real escala junto com o ganho e o volume sai da energia (filtro K) vezes o ganho do
    limitador ao quadrado (o ganho do limitador muda devagar perto dos blocos de 400 ms da medição)."""
    if pb is None:
        raise ValueError(SEM_PEDALBOARD)
    chave = (*_chave(path), json.dumps(ajustes, sort_keys=True))
    with _TRAVA:
        if chave in _PROCESSADOS:
            _PROCESSADOS.move_to_end(chave)
            return _PROCESSADOS[chave]
    inicio = time.perf_counter()
    pre = _pre_volume(path, ajustes)
    taxa, analise, energia, envelope = pre['taxa'], pre['analise'], pre['energia'], pre['envelope']
    alvo, lim = ajustes['lufs_alvo'], ajustes['limitador']
    teto = lim['teto_db'] if lim['ligado'] else -0.1  # sem limitador: só não deixa distorcer (baixa tudo junto)
    # sem normalizar: volta para o volume original da música; nos dois casos soma o ganho extra
    desejado = (alvo if alvo is not None else analise['lufs']) + ajustes['ganho_db']
    ganho_db = desejado - pre['lufs']
    avisos = []
    taxa_grossa = taxa / GROSSO
    # rodadas rápidas na versão grossa (o ganho do limitador muda devagar: 30 ms = 45 valores grossos)
    for _ in range(8):
        linear = 10 ** (ganho_db / 20)
        env = pre['envelope_grosso'] * np.float32(linear)
        g = _ganho_limitador(env, taxa_grossa, teto - 0.05) if lim['ligado'] else None
        if not lim['ligado'] and float(env.max()) > 10 ** (teto / 20):  # sem limitador: baixa tudo até caber
            ganho_db -= 20 * math.log10(float(env.max())) - (teto - 0.05)
            break
        e = pre['energia_grossa'] if g is None else pre['energia_grossa'] * (g * g)
        erro = desejado - (_lufs_blocos(_blocos(e, taxa_grossa)) + ganho_db)
        if abs(erro) < 0.05 or not lim['ligado']:
            break
        ganho_db += erro
    # rodada final na resolução completa (é esta que vale)
    linear = 10 ** (ganho_db / 20)
    g = _ganho_limitador(envelope * np.float32(linear), taxa, teto - 0.05) if lim['ligado'] else None
    e = energia if g is None else energia * (g * g)
    final = _lufs_blocos(_blocos(e, taxa)) + 20 * math.log10(linear)
    z = pre['y'] * np.float32(linear)
    if g is not None:
        z *= g[None, :]
    np.clip(z, -1.0, 1.0, out=z)
    pico_depois = float((envelope * g).max() if g is not None else envelope.max()) * linear
    if not lim['ligado'] and desejado - final > 0.5:
        avisos.append(f'Sem o limitador, a música só chegou a {_br(final)} LUFS para não distorcer '
                      '(ligue o limitador para chegar ao alvo).')
    elif lim['ligado'] and desejado - final > 1.0:
        avisos.append(f'O limitador não conseguiu chegar a {_br(desejado)} LUFS sem distorcer: ficou em {_br(final)} LUFS.')
    mudanca = final - pre['lufs']  # o limitador quase não muda o timbre: as faixas sobem/descem juntas
    resultado = {'audio': z, 'taxa': taxa, 'lufs_antes': analise['lufs'], 'lufs_depois': round(final, 1),
                 'pico_real_antes': analise['pico_real_db'], 'pico_real_depois': round(20 * math.log10(max(pico_depois, 1e-9)), 1),
                 'faixas_antes': analise['faixas'],
                 'faixas_depois': {k: round(v + mudanca, 2) for k, v in pre['faixas'].items()},
                 'avisos': avisos, 'segundos': round(time.perf_counter() - inicio, 2)}
    with _TRAVA:
        _guardar(_PROCESSADOS, chave, resultado, 2)
    return resultado


def info_publica(resultado):
    return {k: v for k, v in resultado.items() if k not in ('audio', 'taxa')}


# ---------------------------------------------------------------- prévia e gravação
def _mp3(audio, taxa):
    buf = io.BytesIO()
    if taxa in (32000, 44100, 48000):
        with AudioFile(buf, 'w', samplerate=taxa, num_channels=audio.shape[0], format='mp3', quality='V2') as f:
            f.write(audio)
        return buf.getvalue(), 'audio/mpeg'
    with AudioFile(buf, 'w', samplerate=taxa, num_channels=audio.shape[0], format='wav', bit_depth=16) as f:
        f.write(audio)
    return buf.getvalue(), 'audio/wav'


def previa(path, ajustes, inicio_s, duracao_s, original=False):
    """Trecho curto (até 30 s) para ouvir na hora. Com original=True devolve o MESMO trecho da música original, com o
    volume igualado ao da equalizada (para comparar só o timbre, não o volume)."""
    if not (1 <= duracao_s <= 30):
        raise ValueError('A prévia deve ter entre 1 e 30 segundos.')
    if inicio_s < 0:
        raise ValueError('O início da prévia não pode ser negativo.')
    inicio = time.perf_counter()
    r = processar(path, ajustes)
    taxa = r['taxa']
    total = r['audio'].shape[1]
    a = min(int(inicio_s * taxa), max(0, total - int(duracao_s * taxa)))
    b = min(total, a + int(duracao_s * taxa))
    if original:
        audio, _ = ler_audio(path)
        trecho = audio[:, a:b] * np.float32(10 ** ((r['lufs_depois'] - r['lufs_antes']) / 20))
        trecho = _limitar(trecho, taxa, -1.05)  # igualar o volume pode estourar: segura só os picos do trecho
    else:
        trecho = r['audio'][:, a:b]
    trecho = trecho.copy()
    rampa = min(int(0.01 * taxa), trecho.shape[1] // 2)  # 10 ms de entrada/saída: sem estalo no corte
    if rampa:
        janela = np.linspace(0, 1, rampa, dtype=np.float32)
        trecho[:, :rampa] *= janela
        trecho[:, -rampa:] *= janela[::-1]
    dados, tipo = _mp3(np.clip(trecho, -1, 1), taxa)
    info = info_publica(r)
    info.update(inicio_s=round(a / taxa, 2), duracao_s=round((b - a) / taxa, 2), original=bool(original),
                segundos_previa=round(time.perf_counter() - inicio, 2))
    return dados, tipo, info


def salvar_flac(path, ajustes, destino):
    """Processa a música inteira e grava o FLAC (24 bits) em `destino` (nunca em cima da original)."""
    destino = Path(destino)
    if destino.resolve() == Path(path).resolve():
        raise ValueError('O equalizador nunca grava por cima da música original.')
    inicio = time.perf_counter()
    r = processar(path, ajustes)
    audio = r['audio']
    # conferência final com o pico real medido de novo na música pronta (4x): nada passa do teto
    teto = ajustes['limitador']['teto_db'] if ajustes['limitador']['ligado'] else -0.1
    pico = pico_real_db(audio)
    if pico > teto:
        audio = audio * np.float32(10 ** ((teto - 0.02 - pico) / 20))
        pico = pico_real_db(audio)
    temporario = destino.with_name(destino.stem + '.part' + uuid.uuid4().hex[:6] + '.flac')
    try:
        with AudioFile(str(temporario), 'w', samplerate=r['taxa'], num_channels=audio.shape[0], bit_depth=24) as f:
            f.write(audio)
        os.replace(temporario, destino)
    finally:
        temporario.unlink(missing_ok=True)
    info = info_publica(r)
    info['pico_real_depois'] = round(pico, 2)
    info['segundos_total'] = round(time.perf_counter() - inicio, 2)
    return info


def catalogo_tela():
    """O que a tela precisa para montar os controles (uma fonte só: este arquivo)."""
    return {'faixas_catalogo': [{'id': f[0], 'nome': f[1], 'hz': f[2], 'rotulo_hz': _hz(f[2])} for f in FAIXAS],
            'predefinicoes': [{'id': k, 'nome': v['nome'], 'descricao': v['descricao'], 'ajustes': {**v['ajustes'], 'preset': k}}
                              for k, v in PREDEFINICOES.items()],
            'padrao': PADRAO, 'limites': LIMITES, 'alvos_lufs': list(ALVOS_LUFS)}
