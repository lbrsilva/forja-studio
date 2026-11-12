"""Baixa e instala o VoiceStudio (o motor de voz local) a partir da versao oficial no GitHub.

So roda quando a pessoa clica em "Instalar" na tela da Narracao. O arquivo vem do repositorio
oficial, tem o SHA-256 conferido contra o SHA256SUMS.txt publicado na mesma versao e fica em
_ferramentas/VoiceStudio. No Windows o instalador e aberto para a pessoa concluir o assistente.
"""
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

import plataforma

REPO = "debpalash/VoiceStudio"
RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "_ferramentas" / "VoiceStudio"
USER_AGENT = "ForjaStudio/1.0"

_trava = threading.Lock()
_estado = {"fase": "parado", "baixados": 0, "total": 0, "mensagem": "", "arquivo": None, "versao": None}


def _definir(**kw):
    with _trava:
        _estado.update(kw)


def estado():
    with _trava:
        d = dict(_estado)
    d["app"] = str(app_instalado() or "") or None
    return d


def _abrir(url, timeout=30):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout)


def escolher_asset(assets, sistema=None, maquina=None):
    """O arquivo da versao que serve a este computador, ou None."""
    sistema = sistema or platform.system()
    maquina = (maquina or platform.machine()).lower()
    arm = maquina in ("arm64", "aarch64")
    if sistema == "Darwin":
        sufixo = "-mac-arm64.zip" if arm else "-mac-x64.zip"
    elif sistema == "Windows":
        sufixo = "-win-arm64.exe" if arm else "-win-x64.exe"
    elif sistema == "Linux" and not arm:
        sufixo = "-linux-x64.AppImage"
    else:
        return None
    return next((a for a in assets if a["name"].endswith(sufixo)), None)


def app_instalado():
    if plataforma.MAC:
        for pasta in (PASTA, Path.home() / "Applications", Path("/Applications")):
            if (pasta / "VoiceStudio.app").is_dir():
                return pasta / "VoiceStudio.app"
    elif not plataforma.WIN:
        achados = sorted(PASTA.glob("VoiceStudio-*.AppImage")) if PASTA.is_dir() else []
        return achados[-1] if achados else None
    return None


def _sha_esperado(assets, nome):
    soma = next((a for a in assets if a["name"] == "SHA256SUMS.txt"), None)
    if not soma:
        return None
    with _abrir(soma["browser_download_url"]) as r:
        for linha in r.read().decode("utf-8", "replace").splitlines():
            m = re.match(r"^([0-9a-fA-F]{64})\s+\*?(.+)$", linha.strip())
            if m and m.group(2).strip() == nome:
                return m.group(1).lower()
    return None


def abrir_app():
    app = app_instalado()
    if not app:
        return False
    try:
        if plataforma.MAC:
            subprocess.Popen(["/usr/bin/open", str(app)])
        else:
            subprocess.Popen([str(app)], start_new_session=True)
        return True
    except OSError:
        return False


def _trabalho():
    try:
        _definir(fase="procurando", mensagem="Procurando a versão mais nova do VoiceStudio…", baixados=0, total=0)
        with _abrir(f"https://api.github.com/repos/{REPO}/releases/latest") as r:
            versao = json.loads(r.read())
        assets = versao.get("assets") or []
        alvo = escolher_asset(assets)
        if not alvo:
            _definir(fase="erro", mensagem=f"Não há instalador do VoiceStudio para este sistema ({platform.system()} {platform.machine()}). "
                     f"Veja github.com/{REPO}/releases.")
            return
        PASTA.mkdir(parents=True, exist_ok=True)
        destino = PASTA / alvo["name"]
        parcial = destino.with_suffix(destino.suffix + ".baixando")
        _definir(fase="baixando", arquivo=alvo["name"], versao=versao.get("tag_name"), total=int(alvo.get("size") or 0),
                 mensagem=f"Baixando {alvo['name']}…")
        sha = hashlib.sha256()
        feitos = 0
        with _abrir(alvo["browser_download_url"], timeout=60) as r, open(parcial, "wb") as f:
            while True:
                pedaco = r.read(1024 * 512)
                if not pedaco:
                    break
                f.write(pedaco)
                sha.update(pedaco)
                feitos += len(pedaco)
                _definir(baixados=feitos)
        _definir(fase="conferindo", mensagem="Conferindo a integridade do arquivo…")
        esperado = _sha_esperado(assets, alvo["name"])
        if esperado and esperado != sha.hexdigest():
            parcial.unlink(missing_ok=True)
            _definir(fase="erro", mensagem="O arquivo baixado não bate com o SHA-256 publicado. Apaguei e não instalei.")
            return
        parcial.replace(destino)
        _instalar(destino)
    except Exception as exc:
        _definir(fase="erro", mensagem=f"Não consegui instalar o VoiceStudio: {str(exc)[:200]}")


def _instalar(arquivo):
    if plataforma.MAC:
        _definir(fase="instalando", mensagem="Descompactando o VoiceStudio…")
        app = PASTA / "VoiceStudio.app"
        if app.exists():
            shutil.rmtree(app)
        r = subprocess.run(["/usr/bin/ditto", "-x", "-k", str(arquivo), str(PASTA)], capture_output=True, text=True)
        if r.returncode or not app.is_dir():
            _definir(fase="erro", mensagem="Não consegui descompactar o VoiceStudio: " + (r.stderr or "")[:150])
            return
        subprocess.run(["/usr/bin/xattr", "-dr", "com.apple.quarantine", str(app)], capture_output=True)
        arquivo.unlink(missing_ok=True)
        abrir_app()
        _definir(fase="pronto", mensagem="VoiceStudio instalado e aberto. Na primeira vez ele monta o motor de voz "
                 "(baixa vários GB): conclua o assistente na janela dele. Este painel detecta sozinho quando terminar.")
    elif plataforma.WIN:
        os.startfile(str(arquivo))
        _definir(fase="pronto", mensagem="Abri o instalador do VoiceStudio. Conclua o assistente na janela dele; "
                 "depois volte aqui e clique em Procurar de novo.")
    else:
        os.chmod(arquivo, 0o755)
        abrir_app()
        _definir(fase="pronto", mensagem="VoiceStudio aberto. Conclua o assistente na janela dele; depois clique em Procurar de novo.")


def iniciar():
    """Comeca a instalacao em segundo plano. Devolve (comecou, recado)."""
    with _trava:
        if _estado["fase"] in ("procurando", "baixando", "conferindo", "instalando"):
            return False, "A instalação já está em andamento."
    threading.Thread(target=_trabalho, daemon=True).start()
    return True, "Começando a instalação do VoiceStudio."
