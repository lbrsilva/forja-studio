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
                f"e se o token ainda vale (API\\huggingface.txt). Veja REPOSITORIOS.md.")
    return (f"{nome}: o repositório {repo or 'deste modelo'} pede conta no Hugging Face e "
            f"aceitar a licença. Abra {onde}, entre na sua conta e aceite a licença; depois "
            f"crie um token de leitura em https://huggingface.co/settings/tokens e salve a "
            f"primeira linha dele em API\\huggingface.txt. Daí clique em instalar de novo. "
            f"Está explicado em REPOSITORIOS.md.")


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
_API_DIR = Path(os.environ.get("ESTUDIO_API_DIR") or RAIZ / "API")
HOST_HF = "huggingface.co"


def _token_hf():
    """Token do Hugging Face: variavel HF_TOKEN ou primeira linha de API/huggingface.txt. None se nao houver."""
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not token:
        try:
            token = (_API_DIR / "huggingface.txt").read_text(encoding="utf-8")
        except OSError:
            return None
    linhas = token.strip().splitlines()
    return linhas[0].strip() if linhas else None


ARQ_TOKEN_HF = _API_DIR / "huggingface.txt"


def origem_do_token_hf():
    """'variavel' (HF_TOKEN manda), 'arquivo' ou None."""
    if os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN"):
        return "variavel"
    return "arquivo" if _token_hf() else None


def guardar_token_hf(token):
    ARQ_TOKEN_HF.parent.mkdir(parents=True, exist_ok=True)
    ARQ_TOKEN_HF.write_text(token.strip() + "\n", encoding="utf-8")
    if os.name != "nt":
        os.chmod(ARQ_TOKEN_HF, 0o600)


def remover_token_hf():
    try:
        ARQ_TOKEN_HF.unlink()
    except FileNotFoundError:
        pass


class TokenRecusado(OSError):
    pass


def quem_e_o_token_hf(token=None):
    """Nome da conta dona do token, perguntando ao Hugging Face. Levanta OSError com frase em portugues."""
    token = token or _token_hf()
    pedido = urllib.request.Request(f"https://{HOST_HF}/api/whoami-v2",
                                    headers={"User-Agent": "ForjaStudio/1.0", "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(pedido, timeout=20) as r:
            return json.loads(r.read()).get("name") or "?"
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise TokenRecusado("O Hugging Face nao aceitou este token, entao nao guardei. Confira se ele foi copiado inteiro e se e de leitura.") from exc
        raise OSError(f"O Hugging Face respondeu erro {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise OSError("Nao consegui falar com o Hugging Face (sem internet?). O token foi guardado mesmo assim.") from exc


def _abrir(pedido, nome):
    if urllib.parse.urlparse(pedido.full_url).hostname == HOST_HF:
        token = _token_hf()
        if token:
            pedido.add_header("Authorization", f"Bearer {token}")
    try:
        return urllib.request.build_opener(_SemTokenEmOutroHost).open(pedido, timeout=60)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403) and urllib.parse.urlparse(pedido.full_url).hostname == HOST_HF:
            raise OSError(
                f"{nome}: o Hugging Face recusou o download (HTTP {exc.code}). Esta IA exige conta: aceite a "
                f"licenca do modelo no site e coloque um token de leitura em API/huggingface.txt "
                f"(ou na variavel HF_TOKEN).") from exc
        raise
MODELOS = plataforma.comfy_dir(RAIZ) / "models"

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
def catalogo():
    """{nome do arquivo: {fonte, pasta, bytes, usado_por}}. Vazio se nao houver catalogo."""
    try:
        d = json.loads(CATALOGO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d.get("comfyui") or {}


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
        return {"baixando": d, "fila": list(_fila), "erro": _erro, "erro_ia": _erro_ia}


def _baixar_arquivo(nome, info):
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

    with _abrir(pedido, nome) as r:
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
            for nome, info in arquivos_da(ia, cat).items():
                if _parar:
                    raise InterruptedError("parado por quem pediu")
                if esta_completo(nome, info):
                    continue
                if not info.get("fonte"):
                    raise OSError(f"{nome}: nao sei de onde baixar este arquivo")
                with _trava:
                    _agora = {"ia": ia, "arquivo": nome, "baixados": 0,
                              "total": info.get("bytes") or 0, "comecou": time.time()}
                _baixar_arquivo(nome, info)
            with _trava:
                if _fila and _fila[0] == ia:
                    _fila.pop(0)
    except Exception as exc:
        with _trava:
            _erro = str(exc)
            _erro_ia = ia
    finally:
        with _trava:
            _agora = None
            _tocando = False
            _parar = False


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
    with _trava:
        if ia in _fila:
            return False, "Esta IA já está na fila."
        _fila.append(ia)
        _erro = None
        _erro_ia = None
        if _tocando:
            return True, "Entrou na fila."
        _tocando = True
    threading.Thread(target=_trabalhar, args=(None,), daemon=True).start()
    return True, "Começando a baixar."


def plano_de_remocao(ia, junto=False):
    """O que apagar ao remover `ia`: so os arquivos que NENHUMA outra IA instalada usa.

    Devolve {"apagar": [(nome, bytes)], "manter": [(nome, [outras IAs])], "bytes": total_liberado}.
    """
    cat = catalogo()
    meus = arquivos_da(ia, cat)
    outras = {}
    for nome, info in cat.items():
        for outra in info.get("usado_por") or []:
            if outra != ia:
                outras.setdefault(nome, []).append(outra)
    instaladas = {n for n in {u for i in cat.values() for u in (i.get("usado_por") or [])}
                  if n != ia and estado_de(n, cat).get("instalada")}
    apagar, manter = [], []
    for nome, info in sorted(meus.items()):
        if "/" in nome or "\\" in nome or nome.startswith(".") or ".." in (info.get("pasta") or ""):
            continue
        existe = caminho_de(nome, info).is_file() or caminho_de(nome, info).with_suffix(
            caminho_de(nome, info).suffix + ".baixando").is_file()
        if not existe:
            continue
        donos = [] if junto else [o for o in outras.get(nome, []) if o in instaladas]
        if donos:
            manter.append((nome, donos))
        else:
            apagar.append((nome, _tamanho_no_disco(nome, info)))
    return {"apagar": apagar, "manter": manter, "bytes": sum(b for _, b in apagar)}


def _tamanho_no_disco(nome, info):
    destino = caminho_de(nome, info)
    for p in (destino, destino.with_suffix(destino.suffix + ".baixando")):
        try:
            return p.stat().st_size
        except OSError:
            continue
    return 0


def remover(ia, junto=False):
    """Apaga do disco os arquivos exclusivos de `ia`. Devolve (ok, recado, bytes_liberados)."""
    with _trava:
        if _tocando and (ia in _fila or (_agora and _agora.get("ia") == ia)):
            return False, "Esta IA está sendo baixada agora. Pare o download antes de remover.", 0
    cat = catalogo()
    base = MODELOS.resolve()
    liberados = 0
    for nome, _ in plano_de_remocao(ia, junto)["apagar"]:
        info = cat[nome]
        destino = caminho_de(nome, info)
        for alvo in (destino, destino.with_suffix(destino.suffix + ".baixando")):
            try:
                real = alvo.resolve()
                if base not in real.parents or not alvo.is_file():
                    continue
                tam = alvo.stat().st_size
                alvo.unlink()
                liberados += tam
            except OSError as exc:
                return False, f"Não consegui apagar {nome}: {exc}", liberados
    return True, "IA removida.", liberados


def parar():
    """Para o download atual. O pedaco baixado FICA: continua da proxima vez."""
    global _parar
    with _trava:
        _fila.clear()
        _parar = _tocando
    return True
