"""Tudo o que muda entre Windows e macOS fica neste arquivo.

Os outros modulos perguntam aqui em vez de testar o sistema cada um do seu jeito.
"""
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

WIN = os.name == "nt"
MAC = sys.platform == "darwin"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

PASTA_COMFY = "ComfyUI_windows_portable" if WIN else "ComfyUI_mac"


def pasta_comfy(raiz):
    return Path(raiz) / PASTA_COMFY


def comfy_dir(raiz):
    return pasta_comfy(raiz) / "ComfyUI"


def python_comfy(raiz):
    base = pasta_comfy(raiz)
    return base / "python_embeded" / "python.exe" if WIN else base / "venv" / "bin" / "python"


def exe(nome):
    return nome + ".exe" if WIN else nome


def e_python(nome_do_processo):
    return (nome_do_processo or "").lower().startswith("python")


def sem_janela():
    """kwargs do Popen para rodar sem console (Windows) ou desligado do terminal (macOS)."""
    return {"creationflags": NO_WINDOW} if WIN else {"start_new_session": True}


def comando_para_texto(comando):
    return comando if isinstance(comando, str) else " ".join(str(c) for c in comando)


# ----------------------------------------------------------------- identidade da maquina (macOS)
_ioreg = {}


def _ler_ioreg():
    if _ioreg:
        return _ioreg
    try:
        saida = subprocess.run(["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                               capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        saida = ""
    for campo in ("IOPlatformUUID", "IOPlatformSerialNumber"):
        m = re.search(r'"%s"\s*=\s*"([^"]+)"' % campo, saida)
        _ioreg[campo] = m.group(1) if m else ""
    return _ioreg


def _serie_do_disco_mac():
    try:
        saida = subprocess.run(["/usr/sbin/system_profiler", "SPNVMeDataType", "-json"],
                               capture_output=True, text=True, timeout=30).stdout
        for controlador in json.loads(saida or "{}").get("SPNVMeDataType", []):
            for item in controlador.get("_items", []):
                if item.get("device_serial"):
                    return item["device_serial"]
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return ""


def maquina_mac():
    """Os mesmos tres campos que o licenca.py le no Windows."""
    d = _ler_ioreg()
    return {"placa_uuid": d.get("IOPlatformUUID", ""), "placa_serie": d.get("IOPlatformSerialNumber", ""),
            "disco_serie": _serie_do_disco_mac()}


def segredo_da_maquina():
    """Bytes ligados a ESTA maquina e a ESTE usuario (o papel que o DPAPI faz no Windows)."""
    uuid = _ler_ioreg().get("IOPlatformUUID", "")
    if not uuid:
        return None
    return hashlib.sha256(f"{uuid}|{os.getuid()}".encode("utf-8")).digest()


# ----------------------------------------------------------------- memoria e placa
def _sysctl(chave):
    try:
        return subprocess.run(["/usr/sbin/sysctl", "-n", chave], capture_output=True, text=True,
                              timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def pids_escutando(porta):
    """PIDs que escutam em `porta` (TCP). No macOS o psutil exige root para listar conexoes; la usa-se o lsof."""
    if not MAC:
        try:
            import psutil
            return {c.pid for c in psutil.net_connections(kind="tcp")
                    if c.status == psutil.CONN_LISTEN and c.laddr and c.laddr.port == porta and c.pid}
        except Exception:
            pass
    try:
        saida = subprocess.run(["/usr/sbin/lsof", "-nP", f"-iTCP:{porta}", "-sTCP:LISTEN", "-t"],
                               capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return set()
    return {int(x) for x in saida.split() if x.isdigit()}


def apple_silicon():
    return MAC and platform.machine() == "arm64"


def memoria():
    """(total, disponivel) em bytes, ou (None, None)."""
    try:
        import psutil
        m = psutil.virtual_memory()
        return m.total, m.available
    except Exception:
        return None, None


_teto_metal_bytes = None


def _medir_teto_metal():
    global _teto_metal_bytes
    try:
        saida = subprocess.run(
            [sys.executable, "-c", "import torch;print(int(torch.mps.recommended_max_memory()))"],
            capture_output=True, text=True, timeout=60).stdout.strip().splitlines()
        valor = int(saida[-1]) if saida else 0
        if valor > 0:
            _teto_metal_bytes = valor
    except (OSError, subprocess.SubprocessError, ValueError):
        pass


_medicao_iniciada = False


def gpu_unificada():
    """(nome, total, livre) em bytes para o chip da Apple.

    A memoria da GPU e a RAM. O "total" e o teto que o proprio Metal recomenda (medido uma vez pelo
    PyTorch); sem PyTorch, 3/4 da RAM. O "livre" nunca passa dele.
    """
    global _medicao_iniciada
    if not apple_silicon():
        return None
    if not _medicao_iniciada:
        import threading
        _medicao_iniciada = True
        threading.Thread(target=_medir_teto_metal, daemon=True).start()
    total, livre = memoria()
    if not total:
        return None
    nome = _sysctl("machdep.cpu.brand_string") or "Apple Silicon"
    teto = min(_teto_metal_bytes, total) if _teto_metal_bytes else int(total * 0.75)
    return nome, teto, min(livre, teto)


def threads_cpu():
    return os.cpu_count() or 8


def completar_path():
    """Programas abertos fora do Terminal (atalho, login) nao herdam o PATH do Homebrew."""
    if not MAC:
        return
    atual = os.environ.get("PATH", "").split(os.pathsep)
    faltam = [p for p in ("/opt/homebrew/bin", "/opt/homebrew/sbin", "/usr/local/bin") if p not in atual
              and os.path.isdir(p)]
    os.environ["PATH"] = os.pathsep.join(faltam + atual)


# ---------------------------------------------------------------- navegadores da automacao
# A tela invisivel do plano-sequencia dirige um navegador Chromium por linha de comando
# (--user-data-dir, --headless, --remote-debugging-port). Chrome, Edge, Brave, Chromium,
# Vivaldi e Opera aceitam as mesmas opcoes. O Safari nao aceita e precisaria de safaridriver.
NAVEGADORES = (
    {"id": "chrome", "nome": "Google Chrome", "app": "Google Chrome", "exe": "Google Chrome",
     "win": ("Google/Chrome/Application/chrome.exe",)},
    {"id": "chrome-beta", "nome": "Google Chrome Beta", "app": "Google Chrome Beta",
     "exe": "Google Chrome Beta", "win": ("Google/Chrome Beta/Application/chrome.exe",)},
    {"id": "chrome-dev", "nome": "Google Chrome Dev", "app": "Google Chrome Dev",
     "exe": "Google Chrome Dev", "win": ("Google/Chrome Dev/Application/chrome.exe",)},
    {"id": "chrome-canary", "nome": "Google Chrome Canary", "app": "Google Chrome Canary",
     "exe": "Google Chrome Canary", "win": ("Google/Chrome SxS/Application/chrome.exe",)},
    {"id": "edge", "nome": "Microsoft Edge", "app": "Microsoft Edge", "exe": "Microsoft Edge",
     "win": ("Microsoft/Edge/Application/msedge.exe",)},
    {"id": "edge-beta", "nome": "Microsoft Edge Beta", "app": "Microsoft Edge Beta",
     "exe": "Microsoft Edge Beta", "win": ("Microsoft/Edge Beta/Application/msedge.exe",)},
    {"id": "edge-dev", "nome": "Microsoft Edge Dev", "app": "Microsoft Edge Dev",
     "exe": "Microsoft Edge Dev", "win": ("Microsoft/Edge Dev/Application/msedge.exe",)},
    {"id": "edge-canary", "nome": "Microsoft Edge Canary", "app": "Microsoft Edge Canary",
     "exe": "Microsoft Edge Canary", "win": ("Microsoft/Edge SxS/Application/msedge.exe",)},
    {"id": "brave", "nome": "Brave", "app": "Brave Browser", "exe": "Brave Browser",
     "win": ("BraveSoftware/Brave-Browser/Application/brave.exe",)},
    {"id": "brave-beta", "nome": "Brave Beta", "app": "Brave Browser Beta", "exe": "Brave Browser Beta",
     "win": ("BraveSoftware/Brave-Browser-Beta/Application/brave.exe",)},
    {"id": "brave-nightly", "nome": "Brave Nightly", "app": "Brave Browser Nightly",
     "exe": "Brave Browser Nightly",
     "win": ("BraveSoftware/Brave-Browser-Nightly/Application/brave.exe",)},
    {"id": "chromium", "nome": "Chromium", "app": "Chromium", "exe": "Chromium",
     "win": ("Chromium/Application/chrome.exe",)},
    {"id": "vivaldi", "nome": "Vivaldi", "app": "Vivaldi", "exe": "Vivaldi",
     "win": ("Vivaldi/Application/vivaldi.exe", "Programs/Vivaldi/Application/vivaldi.exe")},
    {"id": "opera", "nome": "Opera", "app": "Opera", "exe": "Opera",
     "win": ("Opera/launcher.exe", "Programs/Opera/launcher.exe")},
)


def _navegador_mac(nome_do_app, exe):
    for base in (Path("/Applications"), Path.home() / "Applications"):
        p = base / f"{nome_do_app}.app" / "Contents" / "MacOS" / exe
        if p.is_file():
            return p
    return None


def _navegador_win(relativos):
    bases = [os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"),
             os.environ.get("LOCALAPPDATA"), os.environ.get("PROGRAMW6432")]
    for base in filter(None, bases):
        for rel in relativos:
            p = Path(base) / rel
            if p.is_file():
                return p
    return None


def navegador_caminho(opcao):
    if MAC:
        p = _navegador_mac(opcao["app"], opcao["exe"])
        if p:
            return p
        if opcao["id"] == "chromium":      # Homebrew: /opt/homebrew/bin/chromium, fora de .app
            achado = shutil.which("chromium")
            return Path(achado) if achado else None
        return None
    if WIN:
        return _navegador_win(opcao["win"])
    return None


def navegadores_instalados():
    """[{id, nome, caminho}] dos navegadores presentes, na ordem de preferencia (Chrome antes do Edge)."""
    fora = []
    for opcao in NAVEGADORES:
        p = navegador_caminho(opcao)
        if p:
            fora.append({"id": opcao["id"], "nome": opcao["nome"], "caminho": str(p)})
    return fora


def navegador_por_id(navegador_id):
    return next((n for n in navegadores_instalados() if n["id"] == navegador_id), None)


def navegador_escolhido(preferido=""):
    """O escolhido nas configuracoes, se instalado; senao o primeiro instalado na ordem de preferencia."""
    lista = navegadores_instalados()
    if preferido:
        achado = next((n for n in lista if n["id"] == preferido), None)
        if achado:
            return achado
    return lista[0] if lista else None
