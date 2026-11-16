r"""Instala o MOTOR (a ComfyUI) sozinho, no disco que a pessoa escolheu.

13/11/2026. Ate aqui o instalador .exe punha o painel e parava: a ComfyUI era o "Passo 0"
do manual - baixar um .7z no GitHub, descompactar na pasta certa, instalar dois
complementos pelo Manager. Quem nao tem IA de codigo para fazer isso por ele parava ali.

O que este modulo faz, nesta ordem:

 1. baixa a ComfyUI portatil OFICIAL, numa versao FIXA (a mesma em que os workflows do
    pacote foram testados), com retomada se a internet cair;
 2. confere o tamanho e a assinatura SHA-256 que o proprio GitHub publica - o arquivo tem
    um Python inteiro dentro, e programa baixado nao se roda sem conferir;
 3. descompacta com o `tar.exe` do Windows (ele le .7z; nao precisa instalar o 7-Zip);
 4. poe os 2 complementos que os workflows usam, cada um FIXADO num commit;
 5. instala a unica biblioteca que eles pedem (`gguf`), no Python da propria ComfyUI.

POR QUE VERSAO FIXA e nao "a mais nova": a ComfyUI sai nova quase toda semana, e workflow
que rodava numa pode parar na seguinte. A linha de partida do painel usa opcoes
(--use-ck-attention, --fast fp16_accumulation) que precisam existir na versao instalada -
conferido que existem na v0.36.0. Trocar a versao e trocar AS TRES constantes de cima,
e testar.

O que NAO faz: nao baixa modelo nenhum (isso e o ias.py), e nao escolhe a pasta (isso vem
do server.py, que sabe o disco que a pessoa escolheu).

No macOS o mesmo botao faz o caminho do Homebrew: instala `python@3.12` e `git`, clona a
ComfyUI em `ComfyUI_mac/ComfyUI`, cria o venv em `ComfyUI_mac/venv`, instala PyTorch
(Metal/MPS) e as dependencias, e poe os mesmos complementos fixados. Sem .7z e sem tar.exe.
"""
import hashlib
import io
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

# ------------------------------------------------------------------ o que e instalado
VERSAO = "v0.36.0"
VERSAO_MAC = "main"
ARQUIVO = "ComfyUI_windows_portable_nvidia.7z"
URL = f"https://github.com/Comfy-Org/ComfyUI/releases/download/{VERSAO}/{ARQUIVO}"
BYTES = 1917442353
BYTES_MAC = 6 * 1024 ** 3        # git clone + complementos + PyTorch e dependencias no pip
SHA256 = "c3c60192840f8b68c9a47cf3e8161ecb108e5ffdf5ea236c1c72a402e442695d"

# Os 2 complementos que os workflows do pacote usam (medido em 06/11/2026: de 78 tipos de
# no, 73 sao da ComfyUI de fabrica e os outros 5 vem destes dois). Fixados no commit do
# estudio de origem - "main" muda sem avisar.
COMPLEMENTOS = (
    ("ComfyUI-Easy-Media", "https://github.com/yolain/ComfyUI-Easy-Media",
     "f91dcda4b584a471454bc7fdc04f1380e833e029"),
    ("ComfyUI-GGUF", "https://github.com/city96/ComfyUI-GGUF",
     "6ea2651e7df66d7585f6ffee804b20e92fb38b8a"),
)
BIBLIOTECAS = ("gguf>=0.13.0",)

PRECISA_GB = 12          # 1,8 do .7z + ~6 descompactado + folga para o pip e os temporarios
PRECISA_GB_MAC = 20      # clone + venv + PyTorch e dependencias no pip
PASTA = "ComfyUI_windows_portable"

# Os nos que SAO NOSSOS e viajam dentro do pacote (estudio/nos/<nome>/). Nao ha o que baixar:
# e so copiar para a custom_nodes da ComfyUI. Hoje e um so, o `fz_score_guard`, que a musica
# do YuE2 usa para conferir a partitura antes de sintetizar (ver nos_do_pacote, la embaixo).
NOS = Path(__file__).resolve().parent / "nos"

_trava = threading.Lock()
_estado = {"fase": None, "baixados": 0, "total": BYTES if plataforma.WIN else BYTES_MAC,
           "erro": None, "comecou": None}
_parar = False


class _Parado(Exception):
    pass


# ---------------------------------------------------------------------------- consultas
def _comfy_dir(base):
    base = Path(base)
    return base / PASTA / "ComfyUI" if plataforma.WIN else base / "ComfyUI"


def instalado(base):
    return (_comfy_dir(base) / "main.py").is_file()


def versao():
    return VERSAO if plataforma.WIN else VERSAO_MAC


def bytes_estimados():
    return BYTES if plataforma.WIN else BYTES_MAC


def precisa_gb():
    return PRECISA_GB if plataforma.WIN else PRECISA_GB_MAC


def progresso():
    with _trava:
        return dict(_estado)


def _fase(nome, **mais):
    with _trava:
        _estado.update({"fase": nome, **mais})


def _tar():
    """O tar DO WINDOWS. O do Git (GNU tar) nao le .7z, e pode estar na frente no PATH."""
    p = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "tar.exe"
    return p if p.is_file() else None


def _brew():
    if not plataforma.MAC:
        return None
    for p in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew"):
        if Path(p).is_file():
            return p
    return shutil.which("brew")


def _comando(cmd, fase, **kw):
    """Roda um passo da instalacao e devolve a saida; qualquer codigo != 0 vira frase na tela."""
    _fase(fase)
    if _parar:
        raise _Parado()
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", **kw)
    if _parar:
        raise _Parado()
    if r.returncode != 0:
        saida = (r.stderr or r.stdout or "").strip()
        raise OSError(" ".join(str(c) for c in cmd[:2]) + ": "
                      + (saida[-400:] or f"codigo {r.returncode}"))
    return r


# ------------------------------------------------------------------------------ baixar
def _baixar(url, destino, total=None, com_progresso=False):
    """Baixa com retomada. O pedaco ja baixado FICA se parar: continua de onde estava."""
    parte = Path(str(destino) + ".baixando")
    ja = parte.stat().st_size if parte.is_file() else 0
    if total and ja > total:                 # sobra de outra versao: recomeca
        parte.unlink()
        ja = 0
    pedido = urllib.request.Request(url, headers={"User-Agent": "forja-studio"})
    if ja:
        pedido.add_header("Range", f"bytes={ja}-")
    try:
        r = urllib.request.urlopen(pedido, timeout=60)
    except urllib.error.HTTPError as e:
        if e.code == 416 and total and ja == total:      # ja estava inteiro
            parte.replace(destino)
            return
        raise OSError(f"O servidor respondeu {e.code} ao baixar {Path(url).name}.") from e
    with r:
        if ja and r.status != 206:           # o servidor ignorou a retomada: comeca do zero
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
                if com_progresso:
                    with _trava:
                        _estado["baixados"] = feito
    if total and parte.stat().st_size != total:
        raise OSError(f"O download de {Path(url).name} veio com {parte.stat().st_size} bytes "
                      f"e deviam ser {total}. Tente de novo: ele continua de onde parou.")
    parte.replace(destino)


def _conferir_assinatura(arquivo):
    h = hashlib.sha256()
    with open(arquivo, "rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024 * 4), b""):
            if _parar:
                raise _Parado()
            h.update(bloco)
    if h.hexdigest() != SHA256:
        arquivo.unlink(missing_ok=True)
        raise OSError("A ComfyUI baixada NAO confere com a assinatura publicada pelo GitHub. "
                      "Apaguei o arquivo por seguranca. Tente de novo.")


# ------------------------------------------------------------------------ descompactar
def _descompactar(arquivo, base):
    tar = _tar()
    if not tar:
        raise OSError("Nao achei o tar.exe do Windows (vem no Windows 10 de 2018 em diante). "
                      "Descompacte a ComfyUI a mao: veja o Passo 0 do INSTALAR.md.")
    r = subprocess.run([str(tar), "-xf", str(arquivo), "-C", str(base)],
                       capture_output=True, text=True, errors="replace",
                       creationflags=0x08000000 if os.name == "nt" else 0)
    if r.returncode != 0 or not instalado(base):
        raise OSError("Nao consegui descompactar a ComfyUI: "
                      + ((r.stderr or r.stdout or "").strip()[:300] or f"codigo {r.returncode}"))


def _complemento(nome, repo, commit, base, comfy_dir=None):
    comfy = Path(comfy_dir) if comfy_dir else _comfy_dir(base)
    destino = comfy / "custom_nodes" / nome
    if destino.is_dir() and any(destino.iterdir()):
        return
    zip_local = Path(base) / f"_{nome}.zip"
    _baixar(f"{repo}/archive/{commit}.zip", zip_local)
    try:
        with zipfile.ZipFile(zip_local) as z:
            raiz = z.namelist()[0].split("/")[0] + "/"      # o zip vem com <nome>-<commit>/
            for item in z.infolist():
                if not item.filename.startswith(raiz):
                    continue
                rel = item.filename[len(raiz):]
                if not rel:
                    continue
                alvo = (destino / rel).resolve()
                if destino.resolve() not in alvo.parents and alvo != destino.resolve():
                    raise OSError(f"O complemento {nome} tem um caminho estranho dentro do zip.")
                if item.is_dir():
                    alvo.mkdir(parents=True, exist_ok=True)
                else:
                    alvo.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(item) as origem, open(alvo, "wb") as f:
                        shutil.copyfileobj(origem, f)
    finally:
        zip_local.unlink(missing_ok=True)


def _python_do_motor(base):
    base = Path(base)
    return base / "python_embeded" / "python.exe" if plataforma.WIN else base / "venv" / "bin" / "python"


def _bibliotecas(base):
    py = _python_do_motor(base)
    r = subprocess.run([str(py), "-s", "-m", "pip", "install", *BIBLIOTECAS,
                        "--no-warn-script-location", "--disable-pip-version-check", "-q"],
                       capture_output=True, text=True, errors="replace",
                       creationflags=0x08000000 if os.name == "nt" else 0)
    if r.returncode != 0:
        raise OSError("Nao consegui instalar a biblioteca dos complementos (gguf): "
                      + (r.stderr or r.stdout or "").strip()[-300:])


# ------------------------------------------------------------------- os nos do pacote
def _iguais(a, b):
    """Os dois arquivos tem o mesmo conteudo? (a data nao serve: copia e clone do git mudam a data)"""
    try:
        if a.stat().st_size != b.stat().st_size:
            return False
        return a.read_bytes() == b.read_bytes()      # sao arquivos de poucos KB
    except OSError:
        return False


def nos_do_pacote(comfy_dir, avisar=print):
    r"""Copia os nos do pacote (estudio\nos\*) para <ComfyUI>\custom_nodes. Devolve um resumo.

    14/11/2026. A aba Musica passou a usar a MESMA ComfyUI da imagem e do video, e o YuE2
    precisa de um no pequeno, nosso (`fz_score_guard`), que nao existe em repositorio nenhum
    para o motor baixar. Entao ele viaja no pacote e e copiado em tres horas:
      1. no fim da instalacao do motor (`_trabalhar`);
      2. quando o estudio sobe (motor ja instalado por fora, ou pacote atualizado);
      3. logo antes de o estudio ligar a ComfyUI.
    Copia so o que FALTA ou esta DIFERENTE do pacote - assim uma atualizacao do pacote troca
    o no antigo, e quem ja esta em dia nao tem arquivo regravado a toa.

    NUNCA falha calado: cada copia e cada erro saem em `avisar` (o log do estudio), e o
    resumo volta para a tela poder dizer o que houve.
      {"ok": bool, "copiados": [nomes], "em_dia": [nomes], "erro": str|None,
       "reiniciar": bool}   <- reiniciar: copiou agora, a ComfyUI ligada so enxerga ao reiniciar
    """
    res = {"ok": True, "copiados": [], "em_dia": [], "erro": None, "reiniciar": False}
    comfy_dir = Path(comfy_dir)
    if not (comfy_dir / "main.py").is_file():
        res.update(ok=False, erro="a ComfyUI ainda nao esta instalada em %s" % comfy_dir)
        return res          # sem motor nao ha onde copiar: quem instala o motor copia no fim
    try:
        pastas = sorted(p for p in NOS.iterdir() if p.is_dir() and (p / "__init__.py").is_file())
    except OSError as exc:
        res.update(ok=False, erro="nao consegui ler a pasta dos nos do pacote (%s): %s" % (NOS, exc))
        avisar("[estudio] NOS DO PACOTE: " + res["erro"])
        return res
    for origem in pastas:
        destino = comfy_dir / "custom_nodes" / origem.name
        try:
            arquivos = [a for a in origem.rglob("*")
                        if a.is_file() and "__pycache__" not in a.parts and a.suffix != ".pyc"]
            diferentes = [a for a in arquivos if not _iguais(a, destino / a.relative_to(origem))]
            if not diferentes:
                res["em_dia"].append(origem.name)
                continue
            for a in diferentes:
                alvo = destino / a.relative_to(origem)
                alvo.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(a, alvo)
            res["copiados"].append(origem.name)
            res["reiniciar"] = True
            avisar("[estudio] no do pacote copiado para a ComfyUI: %s (%d arquivo(s)) -> %s"
                   % (origem.name, len(diferentes), destino))
        except OSError as exc:
            res.update(ok=False, erro="nao consegui copiar o no %s para %s: %s"
                       % (origem.name, destino, exc))
            avisar("[estudio] NOS DO PACOTE: " + res["erro"])
    return res


# ----------------------------------------------------------------------------- o trabalho
def _trabalhar(base):
    global _parar
    base = Path(base)
    arquivo = base / ARQUIVO
    try:
        base.mkdir(parents=True, exist_ok=True)
        livre = shutil.disk_usage(str(base)).free / 1024 ** 3
        if livre < PRECISA_GB:
            raise OSError(f"O motor precisa de {PRECISA_GB} GB livres e o disco de {base.anchor} "
                          f"tem {livre:.1f} GB. Escolha outro disco.")
        if not instalado(base):
            if not arquivo.is_file():
                _fase("baixando", baixados=0, total=BYTES)
                _baixar(URL, arquivo, BYTES, com_progresso=True)
            _fase("conferindo")
            _conferir_assinatura(arquivo)
            _fase("descompactando")
            _descompactar(arquivo, base)
        _fase("complementos")
        for nome, repo, commit in COMPLEMENTOS:
            if _parar:
                raise _Parado()
            _complemento(nome, repo, commit, base)
        _bibliotecas(base)
        # os nos que viajam no pacote (o da musica). Falha aqui PARA a instalacao com a frase
        # na tela: motor "pronto" sem o no deixaria a musica do YuE2 quebrada sem ninguem saber.
        nos = nos_do_pacote(_comfy_dir(base))
        if not nos["ok"]:
            raise OSError("O motor foi instalado, mas " + (nos["erro"] or "os nos do pacote nao foram copiados") + ".")
        arquivo.unlink(missing_ok=True)       # so depois de tudo certo: 1,8 GB a menos
        _fase("pronto", erro=None)
    except _Parado:
        _fase(None, erro="Instalacao do motor parada. O que ja baixou fica guardado.")
    except Exception as exc:            # qualquer falha vira frase na tela, nunca silencio
        _fase(None, erro=str(exc))
    finally:
        _parar = False


def _trabalhar_mac(base):
    """O mesmo trabalho do Windows, com o Homebrew no lugar do .7z: brew, git clone, venv e pip."""
    global _parar
    base = Path(base)
    comfy = base / "ComfyUI"
    venv = base / "venv"
    vpy = venv / "bin" / "python"
    try:
        base.mkdir(parents=True, exist_ok=True)
        livre = shutil.disk_usage(str(base)).free / 1024 ** 3
        if livre < PRECISA_GB_MAC:
            raise OSError(f"O motor precisa de {PRECISA_GB_MAC} GB livres e o disco de {base.anchor} "
                          f"tem {livre:.1f} GB. Escolha outro disco.")
        brew = _brew()
        if not brew:
            raise OSError("Nao achei o Homebrew. Instale em https://brew.sh e clique de novo.")
        _fase("preparando", total=0, baixados=0)
        for pacote in ("python@3.12", "git"):
            if subprocess.run([brew, "list", "--formula", pacote],
                              capture_output=True).returncode != 0:
                _comando([brew, "install", pacote], "preparando")
        prefixo = _comando([brew, "--prefix", "python@3.12"], "preparando").stdout.strip()
        py312 = Path(prefixo) / "bin" / "python3.12"
        if not py312.is_file():
            raise OSError("O Homebrew instalou o python@3.12, mas nao achei o python3.12.")
        if not (comfy / "main.py").is_file():
            _fase("baixando", total=0, baixados=0)
            _comando(["git", "clone", "--depth", "1", "https://github.com/comfyanonymous/ComfyUI",
                      str(comfy)], "baixando")
        if not vpy.is_file():
            _comando([str(py312), "-m", "venv", str(venv)], "ambiente")
        _comando([str(vpy), "-m", "pip", "install", "--upgrade", "pip"], "ambiente")
        _comando([str(vpy), "-m", "pip", "install", "torch", "torchvision", "torchaudio"], "ambiente")
        _comando([str(vpy), "-m", "pip", "install", "-r", str(comfy / "requirements.txt")], "ambiente")
        _comando([str(vpy), "-m", "pip", "install", "-r",
                  str(Path(__file__).resolve().parent.parent / "requirements.txt")], "ambiente")
        _fase("complementos")
        for nome, repo, commit in COMPLEMENTOS:
            if _parar:
                raise _Parado()
            _complemento(nome, repo, commit, base, comfy_dir=comfy)
        _bibliotecas(base)
        nos = nos_do_pacote(comfy)
        if not nos["ok"]:
            raise OSError("O motor foi instalado, mas " + (nos["erro"] or "os nos do pacote nao foram copiados") + ".")
        _fase("pronto", erro=None)
    except _Parado:
        _fase(None, erro="Instalacao do motor parada.")
    except Exception as exc:
        _fase(None, erro=str(exc))
    finally:
        _parar = False


def instalar(base):
    """Comeca a instalar em segundo plano. Devolve (comecou, recado)."""
    global _parar
    if not (plataforma.WIN or plataforma.MAC):
        return False, "A instalacao automatica do motor nao existe neste sistema."
    if instalado(base):
        return False, "O motor ja esta instalado neste disco."
    with _trava:
        if _estado["fase"] not in (None, "pronto"):
            return False, "O motor ja esta sendo instalado."
        _estado.update({"fase": "baixando" if plataforma.WIN else "preparando", "baixados": 0,
                        "total": bytes_estimados(), "erro": None, "comecou": time.time()})
    _parar = False
    alvo = _trabalhar if plataforma.WIN else _trabalhar_mac
    threading.Thread(target=alvo, args=(str(base),), daemon=True).start()
    return True, "Comecando a instalar o motor."


def parar():
    global _parar
    _parar = True
    return True
