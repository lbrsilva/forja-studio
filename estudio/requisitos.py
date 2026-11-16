r"""O que esta maquina ainda precisa de FORA para o estudio funcionar inteiro.

14/11/2026, regra do dono: "tudo que eu tiver que criar conta, baixar, tem que estar na
pagina inicial, tem que mostrar o passo a passo. A pessoa vai instalar na casa dela, e se
ela tiver problema, nao vale."

Ate aqui dois pre-requisitos so existiam num manual (INSTALAR.md):

  ffmpeg        o painel usa para converter audio e video que a pessoa envia. Sem ele,
                enviar um MP3 ou um video respondia "o ffmpeg nao foi encontrado".
  VoiceStudio   o motor da VOZ (narracao local). E um programa de terceiros, com instalador
                proprio; sem ele a aba Narracao nao fala nada.

Este modulo baixa os dois pelo botao da tela, cada um numa versao FIXA e conferindo o
SHA-256 que o GitHub publica - sao programas, e programa baixado nao se roda sem conferir.

  - o ffmpeg e so descompactado dentro da pasta do estudio (_ferramentas\ffmpeg\bin): nao
    mexe no PATH do Windows nem pede administrador;
  - o VoiceStudio NAO e instalado por aqui: o painel baixa o instalador oficial, confere, e
    ABRE. Quem clica em "avancar" no instalador de outro programa e a pessoa, nao a gente.

Nenhum dos dois vai dentro do instalador do Forja: o ffmpeg tem 118 MB e o VoiceStudio 222 MB
mais ~22 GB de modelos, e nem todo mundo quer voz.

No macOS o caminho e outro: ffmpeg e llama.cpp vem pelo Homebrew, o VoiceStudio usa o
instalador oficial do proprio sistema (instalar_voz.py) e a IA de texto baixa so os .gguf,
porque o llama-server do Homebrew ja roda no chip da Apple.
"""
import hashlib
import os
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import plataforma

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
FFMPEG_DIR = RAIZ / "_ferramentas" / "ffmpeg" / "bin"
BAIXADOS = RAIZ / "_baixados"

# Versoes FIXAS. Trocar e trocar os quatro campos, e testar.
FFMPEG = {
    "nome": "ffmpeg-2026-11-09-git-16a345b022-essentials_build.zip",
    "url": ("https://github.com/GyanD/codexffmpeg/releases/download/2026-11-09-git-16a345b022/"
            "ffmpeg-2026-11-09-git-16a345b022-essentials_build.zip"),
    "bytes": 117769418,
    "sha256": "eb2e1e721ae0a160b244a33d1284d5e0e98f30b00910d4a662d02ca68c0c3cb3",
}
VOICESTUDIO = {
    "versao": "0.5.8",
    "nome": "VoiceStudio-0.5.8-win-x64.exe",
    "url": "https://github.com/debpalash/VoiceStudio/releases/download/v0.5.8/VoiceStudio-0.5.8-win-x64.exe",
    "bytes": 232785545,
    "sha256": "11238cb8b08ea38b9b4e8e3050cd950ee2a2d3af1856d54e5ce6fb877444ad34",
    "pagina": "https://github.com/debpalash/VoiceStudio",
}

# A IA de texto: o llama.cpp oficial (b10964) + os tres arquivos de modelo. Tudo com o
# SHA-256 publicado. "pasta_modelos" quem preenche e o server.py (o disco das IAs).
_LLAMA = "https://github.com/ggml-org/llama.cpp/releases/download/b10964/"
_HF = "https://huggingface.co/unsloth/"
LLAMA_DIR = RAIZ / "_ferramentas" / "llama.cpp"
TEXTO = {
    "pasta_modelos": None,
    "programas": [      # (arquivo, para qual subpasta, bytes, sha256)
        {"nome": "llama-b10964-bin-win-cpu-x64.zip", "para": "cpu", "bytes": 18427629,
         "sha256": "917f39c076402c421224824607397af20f53625a60defc20e8dd22446bf4c5d7"},
        {"nome": "llama-b10964-bin-win-cuda-13.3-x64.zip", "para": "gpu", "bytes": 149703589,
         "sha256": "cd63ae76ad78a1540aa0f30f6c6284bab14c146d99a58f70c3f0a38cb9c62351"},
        {"nome": "cudart-llama-bin-win-cuda-13.3-x64.zip", "para": "gpu", "bytes": 390970417,
         "sha256": "1462a050eb4c684921ba51dcc4cc488a036674c3e73e9945ee705b854808d03e"},
    ],
    "modelos": [
        {"nome": "mmproj-F16.gguf", "pasta": "qwen3.5-9b", "bytes": 918166080,
         "url": _HF + "Qwen3.5-9B-GGUF/resolve/main/mmproj-F16.gguf",
         "sha256": "f70dc3509053962b0d0d3ee8a7eacebf5d60aa560cad78254ae8698516ae029f"},
        {"nome": "Qwen3.5-9B-UD-Q4_K_XL.gguf", "pasta": "qwen3.5-9b", "bytes": 5966095584,
         "url": _HF + "Qwen3.5-9B-GGUF/resolve/main/Qwen3.5-9B-UD-Q4_K_XL.gguf",
         "sha256": "6f5d30666c2d8ae16a306e616d95341dcf3cc46810df84d7e6f5a7d1e4c1b293"},
        {"nome": "Qwen3.6-35B-A3B-UD-IQ3_XXS.gguf", "pasta": "qwen3.6-35b-a3b", "bytes": 13211155424,
         "url": _HF + "Qwen3.6-35B-A3B-GGUF/resolve/main/Qwen3.6-35B-A3B-UD-IQ3_XXS.gguf",
         "sha256": "9c964e657212fea1f24905dd7b0a89b82fd807d19fab0b41da14251b07b88fbe"},
    ],
}
for _p in TEXTO["programas"]:
    _p["url"] = _LLAMA + _p["nome"]

_base = 0       # bytes ja contados dos arquivos anteriores (instalacao com varios arquivos)
_trava = threading.Lock()
_estado = {"id": None, "fase": None, "baixados": 0, "total": 0, "erro": None, "erro_de": None,
           "pronto": None}
_parar = False


class _Parado(Exception):
    pass


# ----------------------------------------------------------------------------- consultas
def ffmpeg_onde():
    """O caminho do ffmpeg que o painel vai usar, ou None."""
    proprio = FFMPEG_DIR / "ffmpeg.exe"
    if proprio.is_file():
        return str(proprio)
    return shutil.which("ffmpeg")


def ativar_ffmpeg():
    """Poe o ffmpeg DO ESTUDIO na frente do PATH deste processo (nao no do Windows).

    O painel chama "ffmpeg" pelo nome. Sem isto, ter o arquivo na pasta do estudio nao
    adiantava nada: so o PATH do Windows era olhado.
    """
    if (FFMPEG_DIR / "ffmpeg.exe").is_file():
        atual = os.environ.get("PATH", "")
        if str(FFMPEG_DIR).lower() not in atual.lower():
            os.environ["PATH"] = str(FFMPEG_DIR) + os.pathsep + atual
        return True
    if plataforma.MAC:
        plataforma.completar_path()
        return bool(shutil.which("ffmpeg"))
    return False


def _brew():
    if not plataforma.MAC:
        return None
    for p in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew"):
        if Path(p).is_file():
            return p
    return shutil.which("brew")


def progresso():
    with _trava:
        return dict(_estado)


def _fase(**mais):
    with _trava:
        _estado.update(mais)


# -------------------------------------------------------------------------------- baixar
def _baixar(info, destino):
    """Baixa com retomada e confere tamanho e SHA-256. O pedaco baixado fica se parar."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    parte = Path(str(destino) + ".baixando")
    ja = parte.stat().st_size if parte.is_file() else 0
    if ja > info["bytes"]:
        parte.unlink()
        ja = 0
    if ja < info["bytes"]:
        pedido = urllib.request.Request(info["url"], headers={"User-Agent": "forja-studio"})
        if ja:
            pedido.add_header("Range", f"bytes={ja}-")
        try:
            r = urllib.request.urlopen(pedido, timeout=60)
        except urllib.error.HTTPError as e:
            raise OSError(f"O servidor respondeu {e.code} ao baixar {info['nome']}.") from e
        with r:
            if ja and r.status != 206:
                ja = 0
            with open(parte, "ab" if ja else "wb") as f:
                feito = ja
                while True:
                    if _parar:
                        raise _Parado()
                    bloco = r.read(1024 * 256)
                    if not bloco:
                        break
                    f.write(bloco)
                    feito += len(bloco)
                    with _trava:
                        _estado["baixados"] = _base + feito
    if parte.stat().st_size != info["bytes"]:
        raise OSError(f"O download de {info['nome']} veio incompleto. Clique de novo: ele "
                      "continua de onde parou.")
    _fase(fase="conferindo")
    if _parar:
        raise _Parado()
    h = hashlib.sha256()
    with open(parte, "rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024 * 4), b""):
            h.update(bloco)
    if h.hexdigest() != info["sha256"]:
        parte.unlink(missing_ok=True)
        raise OSError(f"O arquivo {info['nome']} NAO confere com a assinatura publicada. "
                      "Apaguei por seguranca. Tente de novo.")
    parte.replace(destino)


def _instalar_ffmpeg():
    if plataforma.MAC:
        if shutil.which("ffmpeg"):
            ativar_ffmpeg()
            return "O ffmpeg ja esta instalado."
        brew = _brew()
        if not brew:
            raise OSError("Nao achei o Homebrew. Instale em https://brew.sh e clique de novo.")
        _fase(fase="baixando", total=0)
        r = subprocess.run([brew, "install", "ffmpeg"], capture_output=True, text=True, errors="replace")
        if r.returncode != 0:
            raise OSError("O Homebrew nao conseguiu instalar o ffmpeg: "
                          + (r.stderr or r.stdout or "").strip()[-300:])
        _fase(fase="configurando")
        ativar_ffmpeg()
        return "O ffmpeg esta instalado (pelo Homebrew)."
    zip_local = BAIXADOS / FFMPEG["nome"]
    if not zip_local.is_file():
        _baixar(FFMPEG, zip_local)
    _fase(fase="descompactando")
    FFMPEG_DIR.mkdir(parents=True, exist_ok=True)
    quero = {"ffmpeg.exe", "ffprobe.exe"}
    with zipfile.ZipFile(zip_local) as z:
        for item in z.infolist():
            nome = item.filename.replace("\\", "/").rsplit("/", 1)[-1]
            if nome in quero and "/bin/" in "/" + item.filename.replace("\\", "/"):
                with z.open(item) as origem, open(FFMPEG_DIR / nome, "wb") as f:
                    shutil.copyfileobj(origem, f)
                quero.discard(nome)
    if quero:
        raise OSError("O pacote do ffmpeg veio sem " + ", ".join(sorted(quero)) + ".")
    zip_local.unlink(missing_ok=True)       # 118 MB a menos; os dois .exe ja estao no lugar
    ativar_ffmpeg()
    return "O ffmpeg esta instalado na pasta do estudio."


def _voz_por_instalar_voz():
    """No macOS e no Linux o instalador oficial ja e um .zip/.AppImage: quem sabe fazer isso e o
    instalar_voz.py. Aqui so acompanhamos o estado dele para a tela do Inicio mostrar a barra."""
    import instalar_voz
    entrou, recado = instalar_voz.iniciar()
    if not entrou:
        raise OSError(recado)
    fase = {"procurando": "baixando", "baixando": "baixando", "conferindo": "conferindo",
            "instalando": "descompactando", "pronto": "abrindo"}
    while True:
        e = instalar_voz.estado()
        _fase(fase=fase.get(e.get("fase"), "baixando"), baixados=e.get("baixados") or 0,
              total=e.get("total") or 0, arquivo=e.get("arquivo"))
        if e.get("fase") in ("pronto", "erro"):
            break
        if _parar:
            raise _Parado()
        time.sleep(0.5)
    if e.get("fase") == "erro":
        raise OSError(e.get("mensagem") or "Nao consegui instalar o VoiceStudio.")
    return e.get("mensagem") or "VoiceStudio instalado."


def _baixar_voicestudio():
    if not plataforma.WIN:
        return _voz_por_instalar_voz()
    exe = BAIXADOS / VOICESTUDIO["nome"]
    if not exe.is_file():
        _baixar(VOICESTUDIO, exe)
    _fase(fase="abrindo")
    destino = VOICESTUDIO.get("destino")
    if destino:
        # O instalador e NSIS: /D=<pasta> ja deixa a pasta preenchida. Tem de ser o ULTIMO
        # argumento e SEM aspas (regra do NSIS), por isso vai como linha pronta e nao lista.
        try:
            subprocess.Popen('"%s" /D=%s' % (exe, destino))
        except OSError:             # pediu administrador, ou outra recusa: abre do jeito comum
            os.startfile(str(exe))  # noqa: S606
    else:
        os.startfile(str(exe))      # noqa: S606 - o instalador oficial, ja conferido
    return ("Abri o instalador do VoiceStudio. Siga as telas dele; quando terminar, abra o "
            "VoiceStudio uma vez e volte aqui.")


def texto_falta():
    """(bytes que ainda faltam baixar, lista do que falta) da IA de texto."""
    falta, nomes = 0, []
    if plataforma.MAC and not shutil.which("llama-server"):
        nomes.append("llama.cpp (Homebrew)")
    for p in TEXTO["programas"]:
        if plataforma.MAC:
            continue        # no macOS o llama.cpp vem pelo Homebrew, nao pelo zip do Windows
        marca = "llama-server.exe" if p["nome"].startswith("llama-") else "cudart64_13.dll"
        if not (LLAMA_DIR / p["para"] / marca).is_file():
            falta += p["bytes"]
            nomes.append(p["nome"])
    pasta = TEXTO["pasta_modelos"]
    for m in TEXTO["modelos"]:
        arq = Path(pasta) / m["pasta"] / m["nome"] if pasta else None
        if not (arq and arq.is_file() and arq.stat().st_size == m["bytes"]):
            falta += m["bytes"]
            nomes.append(m["nome"])
    return falta, nomes


def _instalar_texto():
    global _base
    pasta = TEXTO["pasta_modelos"]
    if not pasta:
        raise OSError("Nao sei em que disco por os modelos de texto.")
    pasta = Path(pasta)
    falta, nomes = texto_falta()
    pasta.mkdir(parents=True, exist_ok=True)
    # o que ja esta pela metade conta a favor: nao precisa de espaco de novo
    meio = sum(f.stat().st_size for f in pasta.rglob("*.baixando"))
    livre = shutil.disk_usage(pasta).free
    if livre < falta - meio + 2 * 1024 ** 3:
        raise OSError("Faltam %.1f GB livres em %s para a IA de texto (precisa de %.1f GB). "
                      "Libere espaco ou escolha outro disco em \"IAs aprovadas\"."
                      % ((falta - meio + 2 * 1024 ** 3 - livre) / 1024 ** 3, pasta.anchor,
                         (falta - meio) / 1024 ** 3))
    if plataforma.MAC and not shutil.which("llama-server"):
        brew = _brew()
        if not brew:
            raise OSError("Nao achei o Homebrew. Instale em https://brew.sh e clique de novo.")
        _fase(fase="baixando", arquivo="llama.cpp (Homebrew)")
        r = subprocess.run([brew, "install", "llama.cpp"], capture_output=True, text=True, errors="replace")
        if r.returncode != 0:
            raise OSError("O Homebrew nao conseguiu instalar o llama.cpp: "
                          + (r.stderr or r.stdout or "").strip()[-300:])
        plataforma.completar_path()
        achado = shutil.which("llama-server")
        if achado:
            import texto
            texto.EXE_GPU = Path(achado)
            texto.EXE_CPU = Path(achado)
    _base = 0
    for p in TEXTO["programas"]:
        if p["nome"] not in nomes:
            continue
        _fase(fase="baixando", arquivo=p["nome"])
        zip_local = BAIXADOS / p["nome"]
        _baixar(p, zip_local)
        _fase(fase="descompactando")
        destino = LLAMA_DIR / p["para"]
        destino.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_local) as z:
            for item in z.infolist():       # os pacotes sao planos; nada de subpasta nem ".."
                nome = item.filename.replace("\\", "/").rsplit("/", 1)[-1]
                if not nome or item.is_dir():
                    continue
                with z.open(item) as origem, open(destino / nome, "wb") as f:
                    shutil.copyfileobj(origem, f)
        zip_local.unlink(missing_ok=True)
        _base += p["bytes"]
    for m in TEXTO["modelos"]:
        if m["nome"] not in nomes:
            continue
        _fase(fase="baixando", arquivo=m["nome"])
        _baixar(m, pasta / m["pasta"] / m["nome"])
        _base += m["bytes"]
    _fase(fase="configurando")
    import texto                    # so aqui: o texto.py puxa o aiohttp
    if not texto.escrever_ini():
        raise OSError("Baixei tudo, mas nao consegui gravar a configuracao dos modelos.")
    return "A IA de texto esta instalada. Ela liga sozinha quando voce pedir um texto."


_COMO = {"ffmpeg": (_instalar_ffmpeg, FFMPEG), "voz": (_baixar_voicestudio, VOICESTUDIO),
         "texto": (_instalar_texto, None)}


def _trabalhar(qual):
    global _parar
    try:
        recado = _COMO[qual][0]()
        _fase(id=None, fase=None, erro=None, erro_de=None, pronto={"id": qual, "recado": recado,
                                                                  "quando": time.time()})
    except _Parado:
        _fase(id=None, fase=None, erro="Download parado. O que ja baixou fica guardado.", erro_de=qual)
    except Exception as exc:            # toda falha vira frase na tela, nunca silencio
        _fase(id=None, fase=None, erro=str(exc), erro_de=qual)
    finally:
        _parar = False


def instalar(qual):
    """Comeca em segundo plano. Devolve (comecou, recado)."""
    global _parar
    if qual not in _COMO:
        return False, "Nao sei instalar isso."
    if not (plataforma.WIN or plataforma.MAC):
        return False, "Esta instalacao automatica so existe no Windows e no macOS."
    with _trava:
        if _estado["id"]:
            return False, "Ja ha um download em andamento. Espere terminar."
        total = texto_falta()[0] if qual == "texto" else _COMO[qual][1]["bytes"]
        _estado.update({"id": qual, "fase": "baixando", "baixados": 0, "arquivo": None,
                        "total": total, "erro": None, "erro_de": None, "pronto": None})
    global _base
    _base = 0
    _parar = False
    threading.Thread(target=_trabalhar, args=(qual,), daemon=True).start()
    return True, "Comecando a baixar."


def parar():
    global _parar
    _parar = True
    return True
