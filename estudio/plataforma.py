"""Tudo o que muda entre Windows e macOS fica neste arquivo.

Os outros modulos perguntam aqui em vez de testar o sistema cada um do seu jeito.
"""
import hashlib
import json
import os
import re
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


def memoria():
    """(total, disponivel) em bytes, ou (None, None)."""
    try:
        import psutil
        m = psutil.virtual_memory()
        return m.total, m.available
    except Exception:
        return None, None


def gpu_unificada():
    """(nome, total, livre) em bytes para o chip da Apple.

    A memoria da GPU e a RAM. O Metal deixa a GPU usar cerca de 3/4 dela por padrao, entao o
    "total" da placa e esse teto, e o "livre" nunca passa dele.
    """
    total, livre = memoria()
    if not total:
        return None
    nome = _sysctl("machdep.cpu.brand_string") or "Apple Silicon"
    teto = int(total * 0.75)
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
