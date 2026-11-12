r"""Instalar as IAs DEPOIS, uma por uma, pela propria tela do estudio.

## Por que isto existe

Antes, para usar o Forja, a pessoa tinha de baixar **235,7 GB de modelos antes de ver a
primeira tela**. Quem tem internet boa e disco grande aguenta; o resto desiste no meio,
sem nunca ter visto o programa.

Agora a ordem se inverte:

  1. instala a PLATAFORMA - ~5,6 GB, abre em minutos, entra na conta, ve tudo funcionando;
  2. a tela inicial mostra cada IA com **"falta instalar - 19,3 GB"** e um botao;
  3. a pessoa instala as que quiser, quando quiser, e so as que o computador dela aguenta.

Quem so quer fazer imagem baixa 19,3 GB e acabou. Nao precisa dos 235.

## Como ele sabe o que falta

O `modelos.json` (feito pelo `_github/gerar_inventario.py`) diz, para cada arquivo: o
**nome**, a **pasta** dentro de `models/`, o **tamanho em bytes** e **quais IAs usam ele**.
Daqui saem as duas contas que importam:

  - **instalada**: todos os arquivos dela estao no disco, com o tamanho certo;
  - **falta X GB**: o que ainda nao esta - descontando o que outras IAs ja trouxeram,
    porque varias dividem o mesmo arquivo (as duas Krea sao quase o mesmo download).

## O que ele NAO faz

- **Nao baixa duas coisas ao mesmo tempo.** Uma fila, um arquivo de cada vez: duas
  conexoes grandes na mesma internet terminam as duas mais devagar, e a barra de progresso
  vira mentira.
- **Nao apaga nada.** Desinstalar IA e coisa de apagar modelo de 20 GB por engano; se um
  dia existir, sera com confirmacao escrita.
- **Nao baixa o que ja esta la.** Confere o tamanho antes; arquivo completo e pulado, e
  arquivo pela metade **continua de onde parou** (HTTP Range), em vez de recomecar.
"""
import json
import os
import shutil
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import plataforma

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent

# A pasta API fica AO LADO da pasta estudio (mesmo lugar da chave do ElevenLabs).
_API_DIR = Path(os.environ.get("ESTUDIO_API_DIR") or RAIZ / "API")
TOKEN_ARQ = _API_DIR / "huggingface.txt"


class _SemTokenEmOutroHost(urllib.request.HTTPRedirectHandler):
    """Tira o Authorization assim que o redirect troca de host.

    O urllib REENVIA o cabeçalho ao seguir um redirect, e o Hugging Face responde 302
    mandando para o CDN (medido em 12/11/2026: us.aws.cdn.hf.co). O token não tem nada que
    fazer lá - a URL do CDN já vem assinada - e mandar segredo para um host que não é o
    dono dele é justamente o que a gente evita no resto do projeto.

    Achado por lbrsilva, no PR #1 do macOS.
    """

    def redirect_request(self, req, fp, code, msg, headers, novaurl):
        novo = super().redirect_request(req, fp, code, msg, headers, novaurl)
        de = urllib.parse.urlparse(req.full_url).hostname
        para = urllib.parse.urlparse(novaurl).hostname
        if novo is not None and para != de:
            novo.remove_header("Authorization")
        return novo


def _token_hf():
    """O token do Hugging Face, se a pessoa tiver posto um. Vazio = baixa sem se identificar.

    Quase nenhum modelo precisa disto: dos 19 repositorios, 18 entregam o arquivo a quem
    pedir. O token existe por causa do Lightricks/LTX-2.5, que fica atras de um portao -
    e sem ele o download parava com um 401 cru, sem explicar nada a ninguem.
    """
    try:
        t = (os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN") or "").strip()
        if not t and TOKEN_ARQ.is_file():
            t = TOKEN_ARQ.read_text(encoding="utf-8").strip().splitlines()[0].strip()
        return t
    except OSError:
        return ""   # pasta sem permissao: segue sem token, e o 401 explica o que fazer


def tem_token():
    """So diz SE existe um token, nunca qual e. A tela nao precisa saber o segredo."""
    return bool(_token_hf())


def guardar_token(valor):
    """Grava (ou apaga, se vier vazio) o token do Hugging Face. Devolve (ok, recado).

    Nao confere o token aqui de proposito: conferir pediria baixar alguma coisa, e o
    unico jeito honesto de saber se ele vale e tentar instalar a IA que precisa dele.
    O que da para conferir e a FORMA - token do Hugging Face comeca com "hf_" e nao tem
    espaco. Colar a senha da conta por engano no lugar do token e o erro mais comum.
    """
    valor = (valor or "").strip()
    if not valor:
        try:
            TOKEN_ARQ.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            return False, f"Não consegui apagar {TOKEN_ARQ}: {exc.strerror or exc}"
        return True, "Token removido. Os 18 repositórios abertos continuam baixando normalmente."
    if any(c.isspace() for c in valor) or len(valor) > 200:
        return False, "Isso não parece um token. Cole só o token, sem espaço nem quebra de linha."
    if not valor.startswith("hf_"):
        return False, ("Token do Hugging Face começa com \"hf_\". Confira se você copiou o "
                       "TOKEN (em Settings > Access Tokens) e não a senha da conta.")
    try:
        TOKEN_ARQ.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_ARQ.write_text(valor + "\n", encoding="utf-8")
    except OSError as exc:
        return False, f"Não consegui guardar em {TOKEN_ARQ}: {exc.strerror or exc}"
    return True, "Token guardado. Agora clique em instalar o LTX 2.5 de novo."


def _repo_do_link(url):
    """De https://huggingface.co/DONO/REPO/resolve/... tira "DONO/REPO"."""
    try:
        depois = url.split("huggingface.co/", 1)[1]
        dono, repo = depois.split("/", 2)[:2]
        return dono + "/" + repo
    except Exception:
        return ""


def _recado_do_portao(url, nome, com_token):
    """O recado que a pessoa le quando o servidor responde 401/403.

    Numero de erro nao ensina ninguem a fazer nada. Este texto diz o repositorio, o que
    fazer la, e onde esta explicado - e muda conforme ja exista um token ou nao.
    """
    repo = _repo_do_link(url)
    onde = ("https://huggingface.co/" + repo) if repo else "a pagina do modelo"
    if com_token:
        return (f"{nome}: o Hugging Face recusou o seu token para {repo or 'este modelo'}. "
                f"Confira se você aceitou a licença em {onde} com a MESMA conta do token, "
                f"e se o token ainda vale: cole de novo em \"Configurações de API\", na "
                f"tela inicial, e clique em instalar outra vez.")
    return (f"{nome}: o repositório {repo or 'deste modelo'} pede conta no Hugging Face e "
            f"aceitar a licença. É de graça: na tela inicial, em \"Configurações de API\", "
            f"o cartão do Hugging Face tem os três passos com os links. Cole o token lá e "
            f"clique em instalar de novo. As outras IAs da fila continuam baixando.")


def _achar_catalogo():
    """O modelos.json fica em lugares diferentes no pacote e aqui no desenvolvimento.

    No PACOTE ele vai para a raiz, ao lado do setup.py. Na maquina onde o projeto e
    escrito, ele mora em _github/, que e onde o gerar_inventario.py o produz. Procurar
    nos dois evita a cena de "funciona aqui e nao funciona la".
    """
    for p in (RAIZ / "modelos.json", RAIZ / "_github" / "modelos.json"):
        if p.is_file():
            return p
    return RAIZ / "modelos.json"


CATALOGO = _achar_catalogo()
# Onde os modelos ficam. O server.py troca este valor (ias.MODELOS = ...) quando a pessoa
# escolhe outro disco na tela; sozinho, este modulo respeita o ESTUDIO_COMFY_DIR.
# Ate 13/11/2026 era fixo na pasta do painel - o download ia para o C: mesmo sem espaco.
MODELOS = (Path(os.environ["ESTUDIO_COMFY_DIR"]) if os.environ.get("ESTUDIO_COMFY_DIR")
           else plataforma.comfy_dir(RAIZ)) / "models"


def espaco_livre():
    """Bytes livres no disco dos modelos, ou None se nao der para medir.

    A pasta pode nao existir ainda: sobe ate achar um pedaco do caminho que exista.
    """
    p = Path(MODELOS)
    for pasta in [p] + list(p.parents):
        if pasta.exists():
            try:
                return shutil.disk_usage(str(pasta)).free
            except OSError:
                return None
    return None

# Quanto o arquivo no disco pode diferir do catalogo e ainda contar como completo.
# Zero seria rigido demais: o mesmo modelo as vezes e republicado com metadado diferente.
# 1 MB pega "baixou pela metade" sem reclamar de diferenca boba.
FOLGA_BYTES = 1024 * 1024

_fila = []                 # ids esperando
_agora = None              # {"ia":..., "arquivo":..., "baixados":..., "total":..., "comecou":...}
_erro = None
_erro_ia = None            # de QUAL IA foi o erro: o cartao dela mostra o recado
_parar = False
_trava = threading.Lock()
_tocando = False


# --------------------------------------------------------------------------- o catalogo
# As IAs de MUSICA (14/11/2026). Ficam aqui, e nao no modelos.json, porque aquele arquivo e
# GERADO a partir do que esta instalado na maquina de origem - e la a musica morava numa
# segunda ComfyUI, que o gerador nem olha. Os nos sao nativos da ComfyUI 0.36; so faltam os
# arquivos. "id" e o mesmo id da ficha de musica (estudio/fichas.json).
_HF_COMFY = "https://huggingface.co/Comfy-Org/"
MUSICA_IAS = {"yue2-int8": "YuE2 INT8", "stable-audio3": "Stable Audio 3"}
MUSICA_ARQUIVOS = {
    "yue2_3b_int8_convrot.safetensors": {
        "pasta": "checkpoints", "bytes": 3960938800, "usado_por": ["YuE2 INT8"],
        "fonte": _HF_COMFY + "YuE2/resolve/main/checkpoints/yue2_3b_int8_convrot.safetensors"},
    "sheetsage2_bf16.safetensors": {       # so o COVER usa; sem ele o painel esconde o cover
        "pasta": "audio_encoders", "bytes": 1386868122, "usado_por": ["YuE2 INT8"],
        "fonte": _HF_COMFY + "YuE2/resolve/main/audio_encoders/sheetsage2_bf16.safetensors"},
    "stable_audio_3_medium.safetensors": {
        "pasta": "checkpoints", "bytes": 9222116660, "usado_por": ["Stable Audio 3"],
        "fonte": _HF_COMFY + "stable-audio-3/resolve/main/checkpoints/stable_audio_3_medium.safetensors"},
    "t5gemma_b_b_ul2.safetensors": {
        "pasta": "text_encoders", "bytes": 1187264003, "usado_por": ["Stable Audio 3"],
        "fonte": _HF_COMFY + "stable-audio-3/resolve/main/text_encoders/t5gemma_b_b_ul2.safetensors"},
    "qwen3.5_2b_bf16.safetensors": {
        "pasta": "text_encoders", "bytes": 4548221488, "usado_por": ["Stable Audio 3"],
        "fonte": _HF_COMFY + "Qwen3.5/resolve/main/text_encoders/qwen3.5_2b_bf16.safetensors"},
}


# O que da para ficar sem: o YuE2 CRIA musica sem o sheetsage2 (so o cover precisa dele).
MUSICA_OPCIONAIS = {"sheetsage2_bf16.safetensors"}


def musica_pronta(mid):
    """Da para GERAR com esta IA de musica? (os arquivos obrigatorios dela estao no disco)

    Nao e o mesmo que "instalada" do estado_de(): la o YuE2 so conta como instalado com o
    arquivo do cover junto. A aba Musica usa esta aqui para decidir se abre ou se explica o
    que falta - e com o YuE2 sem o cover ela ja abre, porque ja da para criar musica.
    """
    nome = MUSICA_IAS.get(mid)
    if not nome:
        return False
    return all(esta_completo(n, v) for n, v in MUSICA_ARQUIVOS.items()
               if nome in v["usado_por"] and n not in MUSICA_OPCIONAIS)


def catalogo():
    """{nome do arquivo: {fonte, pasta, bytes, usado_por}}. Vazio se nao houver catalogo."""
    try:
        d = json.loads(CATALOGO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    cat = dict(d.get("comfyui") or {})
    for nome, info in MUSICA_ARQUIVOS.items():
        if nome in cat:        # o arquivo ja serve a outra IA: so acrescenta quem mais o usa
            cat[nome] = dict(cat[nome], usado_por=list(cat[nome].get("usado_por") or []) + info["usado_por"])
        else:
            cat[nome] = info
    return cat


def caminho_de(nome, info):
    return MODELOS / (info.get("pasta") or "") / nome


def esta_completo(nome, info):
    p = caminho_de(nome, info)
    try:
        tam = p.stat().st_size
    except OSError:
        return False
    esperado = info.get("bytes") or 0
    if not esperado:
        return tam > 0
    return abs(tam - esperado) <= FOLGA_BYTES


def arquivos_da(nome_da_ia, cat=None):
    cat = cat if cat is not None else catalogo()
    return {n: v for n, v in cat.items() if nome_da_ia in (v.get("usado_por") or [])}


def estado_de(nome_da_ia, cat=None):
    """O que a tela precisa saber sobre UMA ia.

    "falta" e so o que ainda nao esta no disco - entao, se a pessoa ja instalou a Krea 2
    Turbo, a Krea 2 Transformar aparece como "falta 0,1 GB", que e a verdade, em vez de
    repetir os 17,8 GB que ela ja tem.
    """
    cat = cat if cat is not None else catalogo()
    arquivos = arquivos_da(nome_da_ia, cat)
    if not arquivos:
        return {"conhecida": False}

    faltando, sem_link, bytes_falta, bytes_total = [], [], 0, 0
    for n, v in arquivos.items():
        bytes_total += v.get("bytes") or 0
        if esta_completo(n, v):
            continue
        faltando.append(n)
        bytes_falta += v.get("bytes") or 0
        if not v.get("fonte"):
            sem_link.append(n)

    return {
        "conhecida": True,
        "instalada": not faltando,
        "arquivos": len(arquivos),
        "faltando": len(faltando),
        "gb_total": round(bytes_total / 1024 ** 3, 1),
        "gb_falta": round(bytes_falta / 1024 ** 3, 1),
        # sem link nenhum para um pedaco: o botao nao pode prometer o que nao entrega
        "da_para_baixar": bool(faltando) and not sem_link,
        "sem_link": sem_link,
    }


def todas(nomes):
    cat = catalogo()
    return {n: estado_de(n, cat) for n in nomes}


# ------------------------------------------------------------------------- baixar
def progresso():
    with _trava:
        d = dict(_agora) if _agora else None
        return {"baixando": d, "fila": list(_fila), "erro": _erro, "erro_ia": _erro_ia,
                "erros": dict(_erros), "erros_tipo": dict(_erros_tipo)}


class _Portao(OSError):
    """O servidor pediu conta/licenca (401/403). So ESTE arquivo espera; o resto da IA baixa."""


class _Lento(Exception):
    """A conexao da vez esta muito abaixo do que esta internet ja mostrou: vale pedir outra."""


JANELA_S = 20               # mede a velocidade em janelas deste tamanho
_melhor = 0.0               # a melhor velocidade (bytes/s) ja vista numa janela, nesta sessao
RELIGADAS_POR_ARQUIVO = 6   # depois disso aceita a conexao que vier: a internet e que esta ruim


def _conexao_ruim(velocidade, pode_tentar_as_cegas):
    """Decide se vale largar esta conexao e pedir outra (o download continua de onde parou).

    - ja vimos esta internet correr (2 MB/s ou mais) e agora esta a menos de 10% disso; ou
    - nunca vimos correr, esta abaixo de 1 MB/s e ainda nao tentamos trocar neste arquivo.
    Quem tem internet lenta de verdade nao entra em laco: a primeira regra nunca dispara e a
    segunda so vale uma vez por arquivo.
    """
    if _melhor >= 2 * 1024 ** 2:
        return velocidade < _melhor * 0.10
    return pode_tentar_as_cegas and velocidade < 1024 ** 2


_erros = {}     # {nome da IA: recado} - cada IA guarda o SEU erro; uma nao esconde a outra
_erros_tipo = {}  # {nome da IA: "token" | "erro"} - a tela trata "falta o token" como tarefa, nao defeito


def _baixar_arquivo(nome, info, religadas=0):
    """Baixa um arquivo, continuando de onde parou. Levanta em caso de erro."""
    global _agora
    destino = caminho_de(nome, info)
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_suffix(destino.suffix + ".baixando")
    total = info.get("bytes") or 0
    ja = parcial.stat().st_size if parcial.exists() else 0

    pedido = urllib.request.Request(info["fonte"], headers={"User-Agent": "ForjaStudio/1.0"})
    # So manda o token para o Hugging Face: token e segredo, e nao se entrega segredo a
    # um servidor que nao e o dono dele.
    # Host exato, não "contém": "huggingface.co.exemplo.com" não é o Hugging Face.
    token = _token_hf() if urllib.parse.urlparse(info["fonte"]).hostname == "huggingface.co" else ""
    if token:
        pedido.add_header("Authorization", "Bearer " + token)
    if ja:
        # continuar de onde parou. Se o servidor nao aceitar, ele responde 200 e a gente
        # recomeca do zero em vez de grudar bytes novos no fim de um arquivo pela metade.
        pedido.add_header("Range", f"bytes={ja}-")

    try:
        conexao = urllib.request.build_opener(_SemTokenEmOutroHost).open(pedido, timeout=60)
    except urllib.error.HTTPError as e:
        # 401/403 aqui quase sempre e portao de licenca, nao defeito. Sem este trecho a
        # pessoa via "HTTP Error 401: Unauthorized" - quando via, porque a tela nem
        # mostrava o erro.
        if e.code in (401, 403):
            raise _Portao(_recado_do_portao(info["fonte"], nome, bool(token))) from e
        raise
    with conexao as r:
        # 206 = "aqui esta o resto", 200 = "toma o arquivo inteiro". O segundo caso
        # acontece quando o servidor nao aceita continuar; ai e preciso zerar e gravar
        # por cima, senao a gente grudaria o arquivo inteiro no fim do pedaco antigo e
        # o resultado passaria no teste de tamanho sendo lixo.
        continuando = r.status == 206
        if ja and not continuando:
            print(f"[estúdio] {nome}: o servidor não deixou continuar, baixando do zero.",
                  flush=True)
        with _trava:
            if _agora:
                _agora["continuou"] = bool(continuando and ja)
        if not continuando:
            ja = 0
        if not total:
            total = int(r.headers.get("Content-Length") or 0) + ja
        global _melhor
        marco_t, marco_b = time.time(), ja
        with open(parcial, "ab" if continuando else "wb") as f:
            while True:
                if _parar:
                    raise InterruptedError("parado por quem pediu")
                pedaco = r.read(1024 * 512)
                if not pedaco:
                    break
                f.write(pedaco)
                ja += len(pedaco)
                with _trava:
                    if _agora:
                        _agora["baixados"] = ja
                        _agora["total"] = total
                agora = time.time()
                if agora - marco_t >= JANELA_S:
                    velocidade = (ja - marco_b) / (agora - marco_t)
                    _melhor = max(_melhor, velocidade)
                    with _trava:
                        if _agora:
                            _agora["velocidade"] = int(velocidade)
                    if (religadas < RELIGADAS_POR_ARQUIVO and total - ja > 20 * 1024 ** 2
                            and _conexao_ruim(velocidade, religadas == 0)):
                        raise _Lento(f"{velocidade / 1024 ** 2:.1f} MB/s")
                    marco_t, marco_b = agora, ja

    if total and abs(parcial.stat().st_size - total) > FOLGA_BYTES:
        raise OSError(f"{nome}: baixou {parcial.stat().st_size} de {total} bytes")
    parcial.replace(destino)


def _trabalhar(nomes_por_ia):
    global _agora, _erro, _erro_ia, _tocando, _parar
    cat = catalogo()
    ia = None
    try:
        while True:
            with _trava:
                if not _fila:
                    break
                ia = _fila[0]
            try:
                _baixar_uma_ia(ia, cat)
            except InterruptedError:
                raise                       # "Parar o download": para tudo mesmo
            except Exception as exc:        # so ESTA falhou: guarda o motivo e segue a fila
                print(f"[estúdio] {ia}: não baixou ({exc}). Seguindo para a próxima da fila.",
                      flush=True)
                with _trava:
                    _erros[ia] = str(exc)
                    _erros_tipo[ia] = "token" if isinstance(exc, _Portao) else "erro"
                    _erro, _erro_ia = str(exc), ia
            with _trava:
                if _fila and _fila[0] == ia:
                    _fila.pop(0)
    except Exception as exc:
        with _trava:
            if not isinstance(exc, InterruptedError):
                _erro = str(exc)
                _erro_ia = ia
    finally:
        with _trava:
            _agora = None
            _tocando = False
            _parar = False


def _baixar_uma_ia(ia, cat):
    """Baixa todos os arquivos que faltam de UMA ia. Levanta se algum falhar."""
    global _agora
    # A conta que a tela mostra e da IA INTEIRA. Por arquivo, a porcentagem chegava a
    # 100 e voltava a 0 a cada arquivo, e parecia que o download tinha recomecado.
    arquivos = arquivos_da(ia, cat)
    ia_total = sum(v.get("bytes") or 0 for v in arquivos.values())
    ia_antes = sum(v.get("bytes") or 0 for n, v in arquivos.items() if esta_completo(n, v))
    portao = None       # o primeiro arquivo que pediu token: avisa so no fim
    for numero, (nome, info) in enumerate(arquivos.items(), 1):
        if _parar:
            raise InterruptedError("parado por quem pediu")
        if esta_completo(nome, info):
            continue
        if not info.get("fonte"):
            raise OSError(f"{nome}: nao sei de onde baixar este arquivo")
        with _trava:
            _agora = {"ia": ia, "arquivo": nome, "baixados": 0,
                      "total": info.get("bytes") or 0, "comecou": time.time(),
                      "ia_total": ia_total, "ia_antes": ia_antes,
                      "numero": numero, "de": len(arquivos)}
        religadas = 0
        while True:
            try:
                _baixar_arquivo(nome, info, religadas)
                break
            except _Portao as exc:
                portao = portao or exc      # segue para os outros arquivos desta IA
                break
            except _Lento as lento:
                religadas += 1
                print(f"[estúdio] {nome}: conexão lenta ({lento}); pedindo outra "
                      f"({religadas} de {RELIGADAS_POR_ARQUIVO}). Continua de onde parou.",
                      flush=True)
                with _trava:
                    if _agora:
                        _agora["religadas"] = religadas
        if esta_completo(nome, info):
            ia_antes += info.get("bytes") or 0
    if portao:
        raise portao


def instalar(ia):
    """Poe a IA na fila. Devolve (entrou, recado)."""
    global _tocando, _erro, _erro_ia
    est = estado_de(ia)
    if not est.get("conhecida"):
        return False, "Não conheço esta IA no catálogo de modelos."
    if est["instalada"]:
        return False, "Esta IA já está instalada."
    if est["sem_link"]:
        return False, ("Não sei de onde baixar " + str(len(est["sem_link"])) +
                       " arquivo(s) desta IA. Veja IAS-INSTALADAS.md e baixe à mão.")
    # Conferir o espaco ANTES: sem isto o download enchia o disco e morria no meio, depois
    # de gastar horas de internet. Conta tambem o que ja esta na fila na frente desta.
    livre = espaco_livre()
    if livre is not None:
        with _trava:
            na_frente = list(_fila)
        preciso = est["gb_falta"] + sum((estado_de(n).get("gb_falta") or 0) for n in na_frente)
        livre_gb = livre / 1024 ** 3
        if preciso + 2 > livre_gb:      # 2 GB de folga: disco cheio ate a tampa trava o Windows
            return False, ("Não cabe: faltam %.1f GB para baixar e o disco de %s tem %.1f GB "
                           "livres. Escolha outro disco no bloco \"IAs aprovadas\", na tela "
                           "inicial." % (preciso, Path(MODELOS).anchor or MODELOS, livre_gb))
    with _trava:
        if ia in _fila:
            return False, "Esta IA já está na fila."
        _fila.append(ia)
        _erros.pop(ia, None)        # nova tentativa: o erro antigo DESTA ia sai da tela
        _erros_tipo.pop(ia, None)
        _erro = None
        _erro_ia = None
        if _tocando:
            return True, "Entrou na fila."
        _tocando = True
    threading.Thread(target=_trabalhar, args=(None,), daemon=True).start()
    return True, "Começando a baixar."


def parar():
    """Para o download atual. O pedaco baixado FICA: continua da proxima vez."""
    global _parar
    with _trava:
        _fila.clear()
        _parar = True
    return True
