r"""O cofre: os presets e os workflows viajam fechados, e so abrem com a chave da conta.

## Por que isto existe

As IAs sao todas gratuitas e o Forja nao cobra nada. O que tem valor aqui e a
CONFIGURACAO: quais IAs, com que modelo, que passos, que amostrador, em que ordem -
meses de medicao e de erro ate ficar bom. Isso ia para o GitHub em texto aberto, e
bastava abrir o arquivo e copiar.

## O que isto protege, e o que NAO protege

Seja honesto com quem le este codigo: **nada que roda na maquina de outra pessoa e
inviolavel.** O painel precisa ABRIR a configuracao para usar, logo a chave chega
naquela maquina, logo alguem determinado pode pega-la na memoria. Isso vale para
Netflix, para jogo caro e para este programa.

O que muda, e muda muito:

  antes  -> abriu o arquivo no bloco de notas e copiou.
  agora  -> tem que ter conta, licenca valida, e desmontar o programa.

E, principalmente: **sem conta nao abre.** A chave vem do servidor, so para quem entrou
e tem licenca viva. E isso que amarra o cadastro ao produto, em vez de pedir cadastro
"porque sim".

## Como e feito

- um arquivo so, `presets.cofre`, com tudo dentro (o presets.json e cada .api.json);
- **AES-256-GCM**: fecha E assina ao mesmo tempo. Se alguem mexer um byte, nao abre -
  em vez de abrir errado e o painel fazer besteira com um workflow adulterado;
- a chave (32 bytes sorteados na montagem do pacote) **nunca vai no pacote**. Mora na
  VPS, e o painel pede depois de entrar na conta;
- aberto **so na memoria**. Nada de gravar o conteudo aberto no disco - senao bastaria
  esperar o programa abrir uma vez e pegar o que ele deixou gravado.

## Sem cofre, segue a vida

Na maquina de desenvolvimento (esta aqui) nao existe `presets.cofre`: os arquivos estao
soltos e o cofre so repassa. E de proposito - quem escreve a configuracao nao pode
depender de internet para mexer nela.
"""
import hashlib
import json
import os
import struct
from pathlib import Path

import plataforma

AQUI = Path(__file__).resolve().parent
ARQUIVO = AQUI / "presets.cofre"
MARCA = b"FORJACOFRE1\n"     # muda se o formato mudar; cliente velho recusa na cara limpa

_aberto = None               # {nome: objeto} depois de aberto. So memoria.
_chave = None                # bytes. So memoria.
_erro = None                 # ultima explicacao, em portugues, para a tela


class CofreFechado(Exception):
    """Pediram um preset e o cofre ainda nao abriu (sem conta, sem chave, sem internet)."""


# ----------------------------------------------------------------- fechar (na montagem)
def fechar(itens, chave):
    """Devolve os bytes do cofre com `itens` ({nome: objeto}) dentro. Usado pelo montador.

    O formato: MARCA | id da chave (8) | nonce (12) | selado.
    O id da chave e so os 8 primeiros bytes do sha256 dela - serve para o painel dizer
    "esta chave nao e deste cofre" em vez de falhar com erro de criptografia.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if len(chave) != 32:
        raise ValueError("a chave do cofre tem que ter 32 bytes")
    cru = json.dumps(itens, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    nonce = os.urandom(12)
    # a MARCA entra como dado autenticado: ninguem troca o cabecalho sem o cofre recusar
    selado = AESGCM(chave).encrypt(nonce, cru, MARCA)
    return MARCA + id_da_chave(chave) + nonce + selado


def id_da_chave(chave):
    return hashlib.sha256(chave).digest()[:8]


def id_do_cofre(caminho=None):
    """Que chave este cofre espera. None se nao houver cofre aqui."""
    p = Path(caminho) if caminho else ARQUIVO
    try:
        cab = p.open("rb").read(len(MARCA) + 8)
    except OSError:
        return None
    if len(cab) < len(MARCA) + 8 or not cab.startswith(MARCA):
        return None
    return cab[len(MARCA):len(MARCA) + 8]


# ------------------------------------------------------------------- abrir (no painel)
def existe():
    return ARQUIVO.is_file()


def aberto():
    return _aberto is not None


def erro():
    return _erro


def abrir(chave, caminho=None):
    """Abre o cofre na memoria. Devolve True, ou False com o motivo em erro()."""
    global _aberto, _chave, _erro
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    p = Path(caminho) if caminho else ARQUIVO
    try:
        bruto = p.read_bytes()
    except OSError as e:
        _erro = f"Nao consegui ler o cofre dos presets: {e}"
        return False

    if not bruto.startswith(MARCA):
        _erro = ("Este cofre de presets e de uma versao diferente do painel. "
                 "Atualize o Forja Studio.")
        return False
    i = len(MARCA)
    esperado, nonce, selado = bruto[i:i + 8], bruto[i + 8:i + 20], bruto[i + 20:]
    if esperado != id_da_chave(chave):
        _erro = ("A chave que o servidor mandou nao e a deste pacote. "
                 "Quase sempre e o painel desatualizado: atualize o Forja Studio.")
        return False
    try:
        cru = AESGCM(chave).decrypt(nonce, selado, MARCA)
    except InvalidTag:
        _erro = "O cofre dos presets esta corrompido ou foi adulterado. Baixe o pacote de novo."
        return False
    try:
        d = json.loads(cru.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        _erro = "O cofre abriu mas o conteudo nao faz sentido. Baixe o pacote de novo."
        return False

    _aberto, _chave, _erro = d, bytes(chave), None
    return True


def trancar():
    """Esquece o que foi aberto. Usado quando a pessoa sai da conta."""
    global _aberto, _chave, _erro
    _aberto = _chave = None
    _erro = "Voce saiu da conta."


# ------------------------------------------------------------------------ ler, no dia a dia
def ler_json(nome, padrao=None):
    """O conteudo de `nome` ("presets.json", "presets/krea2.api.json").

    Com cofre: do que esta aberto na memoria. Sem cofre: do arquivo solto, como sempre.
    Levanta CofreFechado se existe cofre e ele ainda nao abriu - quem chama transforma
    isso num recado na tela, nao num erro feio.
    """
    if not existe():
        p = AQUI / nome
        if not p.is_file():
            if padrao is not None:
                return padrao
            raise FileNotFoundError(str(p))
        return json.loads(p.read_text(encoding="utf-8"))

    if _aberto is None:
        raise CofreFechado(_erro or "Entre na sua conta para o painel abrir as configuracoes.")
    nome = nome.replace("\\", "/")
    if nome in _aberto:
        return _aberto[nome]
    if padrao is not None:
        return padrao
    raise FileNotFoundError(f"{nome} nao esta no cofre")


def tem(nome):
    nome = nome.replace("\\", "/")
    if not existe():
        return (AQUI / nome).is_file()
    return _aberto is not None and nome in _aberto


def lista():
    """O que tem dentro, so os nomes. Serve para conferir o pacote."""
    if not existe():
        return []
    return sorted(_aberto) if _aberto else []


# --------------------------------------------------------- a chave guardada para o offline
# Sem isto, ficar sem internet 10 minutos deixaria a pessoa sem painel - e nao e esse o
# trato: a licenca ja aguenta DIAS_DE_FOLGA dias sem falar com o servidor, e a chave tem
# de aguentar o mesmo tanto, senao a folga da licenca nao vale de nada.
#
# A chave guardada NAO fica legivel no disco: passa pelo DPAPI do Windows, amarrado a
# ESTA conta de usuario NESTA maquina. Copiar o arquivo para outro PC nao adianta - la
# ele nao abre. E uma peca do Windows, nao inventei criptografia nova.
GUARDADA = AQUI / "chave_presets.bin"


_ETIQUETA_MAC = b"FS1"


def _proteger_mac(entrada, proteger):
    segredo = plataforma.segredo_da_maquina()
    if not segredo:
        return None
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.primitives import hashes
        chave = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"forja-studio/cofre-de-presets/v1",
                     info=b"chave-guardada").derive(segredo)
        if proteger:
            nonce = os.urandom(12)
            return _ETIQUETA_MAC + nonce + AESGCM(chave).encrypt(nonce, bytes(entrada), _ETIQUETA_MAC)
        if not entrada.startswith(_ETIQUETA_MAC):
            return None
        corpo = entrada[len(_ETIQUETA_MAC):]
        return AESGCM(chave).decrypt(corpo[:12], corpo[12:], _ETIQUETA_MAC)
    except Exception:
        return None


def _dpapi(entrada, proteger=True):
    """CryptProtectData / CryptUnprotectData. No macOS, AES-GCM com chave presa a esta maquina e a este usuario.
    None se der errado."""
    if plataforma.MAC:
        return _proteger_mac(entrada, proteger)
    if os.name != "nt":
        return None
    import ctypes
    import ctypes.wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cb", ctypes.wintypes.DWORD),
                    ("pb", ctypes.POINTER(ctypes.c_char))]

    def para_blob(b):
        buf = ctypes.create_string_buffer(b, len(b))
        return BLOB(len(b), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf

    dentro, _guarda = para_blob(entrada)
    fora = BLOB()
    # a "entropia" extra amarra a protecao a este uso: um blob roubado de outro programa
    # desta mesma maquina nao serve aqui.
    extra, _g2 = para_blob(b"forja-studio/cofre-de-presets/v1")
    fn = (ctypes.windll.crypt32.CryptProtectData if proteger
          else ctypes.windll.crypt32.CryptUnprotectData)
    ok = fn(ctypes.byref(dentro), None, ctypes.byref(extra), None, None, 0, ctypes.byref(fora))
    if not ok:
        return None
    try:
        return ctypes.string_at(fora.pb, fora.cb)
    finally:
        ctypes.windll.kernel32.LocalFree(fora.pb)


def guardar_chave(chave):
    """Guarda a chave para os proximos dias sem internet. Silencioso se nao der."""
    protegida = _dpapi(bytes(chave), proteger=True)
    if not protegida:
        return False
    try:
        GUARDADA.write_bytes(protegida)
        if not plataforma.WIN:
            os.chmod(GUARDADA, 0o600)
        return True
    except OSError:
        return False


def chave_guardada():
    """A chave de antes, ou None. Nao julga validade: quem chama confere o id do cofre."""
    try:
        protegida = GUARDADA.read_bytes()
    except OSError:
        return None
    aberta = _dpapi(protegida, proteger=False)
    return aberta if aberta and len(aberta) == 32 else None


def esquecer_chave():
    try:
        GUARDADA.unlink()
    except OSError:
        pass
