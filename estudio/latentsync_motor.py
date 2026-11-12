"""LatentSync: sincroniza a boca de uma foto com a voz, rodando num ambiente Python proprio.

O LatentSync nao e um fluxo da ComfyUI: ele roda como programa separado em _ferramentas/latentsync
(codigo do repositorio oficial num commit fixo + um patch pequeno para Apple Silicon, venv e pesos).
Este modulo instala tudo isso quando a pessoa pede, diz se esta instalado e roda a inferencia.
"""
import asyncio
import math
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

import plataforma

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
BASE = RAIZ / "_ferramentas" / "latentsync"
REPO = BASE / "LatentSync"
VENV = BASE / "venv"
URL_REPO = "https://github.com/bytedance/LatentSync"
COMMIT = "a229c3948406bc2cf6eaf4873e662e70c6a04746"
PATCH = AQUI / "latentsync" / "mac.patch"
REQUISITOS = AQUI / "latentsync" / "requisitos-mac.txt"
URL_ROSTO = "https://github.com/deepinsight/insightface/releases/download/model-zoo/buffalo_l.zip"
DET_ROSTO = REPO / "checkpoints" / "auxiliary" / "models" / "buffalo_l" / "det_10g.onnx"
WHISPER = REPO / "checkpoints" / "whisper" / "tiny.pt"
USER_AGENT = "ForjaStudio/1.0"
FPS = 25
QUADROS_POR_BLOCO = 16

VERSOES = {
    "1.5": {"hf": "ByteDance/LatentSync-1.5", "config": "configs/unet/stage2.yaml",
            "pesos": REPO / "checkpoints" / "v15" / "latentsync_unet.pt", "bytes": 5072348184},
}
GB_BASE = 4.0

_trava = threading.Lock()
_inst = {"ativo": False, "ia": None, "etapa": "", "baixados": 0, "total": 0, "erro": None}


def suportado():
    return plataforma.apple_silicon()


def _base_pronta():
    return ((REPO / "scripts" / "inference.py").is_file() and (VENV / "bin" / "python").is_file()
            and DET_ROSTO.is_file() and WHISPER.is_file())


def instalada(versao):
    v = VERSOES[versao]
    try:
        return _base_pronta() and v["pesos"].stat().st_size >= v["bytes"] * 0.99
    except OSError:
        return False


def estado_ia(versao):
    """Mesmo formato que ias.estado_de(), para o cartao mostrar 'Falta instalar' e a lixeira."""
    ok = instalada(versao)
    gb_peso = VERSOES[versao]["bytes"] / 1e9
    falta = 0.0 if ok else round((0 if _base_pronta() else GB_BASE) + (0 if _peso_ok(versao) else gb_peso), 1)
    return {"conhecida": True, "instalada": ok, "arquivos": 3, "faltando": 0 if ok else 1,
            "gb_total": round(GB_BASE + gb_peso, 1), "gb_falta": falta, "da_para_baixar": True, "sem_link": []}


def _peso_ok(versao):
    v = VERSOES[versao]
    try:
        return v["pesos"].stat().st_size >= v["bytes"] * 0.99
    except OSError:
        return False


# ------------------------------------------------------------------------------------ instalar
def progresso():
    with _trava:
        return dict(_inst)


def instalando():
    with _trava:
        return _inst["ativo"]


def _set(**kw):
    with _trava:
        _inst.update(kw)


def _rodar(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"{' '.join(str(c) for c in cmd[:3])}: {(r.stderr or r.stdout).strip()[-300:]}")


def _baixar(url, destino, etapa):
    import ias
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_suffix(destino.suffix + ".baixando")
    _set(etapa=etapa, baixados=0, total=0)
    pedido = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    feitos = 0
    with ias._abrir(pedido, destino.name) as r, open(parcial, "wb") as f:
        _set(total=int(r.headers.get("Content-Length") or 0))
        while True:
            pedaco = r.read(1024 * 512)
            if not pedaco:
                break
            f.write(pedaco)
            feitos += len(pedaco)
            _set(baixados=feitos)
    parcial.replace(destino)


def _trabalho(versao, nome_ia):
    try:
        v = VERSOES[versao]
        BASE.mkdir(parents=True, exist_ok=True)
        if not (REPO / "scripts" / "inference.py").is_file():
            _set(etapa="Baixando o código do LatentSync", baixados=0, total=0)
            REPO.mkdir(parents=True, exist_ok=True)
            _rodar(["git", "init", "-q"], REPO)
            _rodar(["git", "remote", "add", "origin", URL_REPO], REPO)
            _rodar(["git", "fetch", "-q", "--depth", "1", "origin", COMMIT], REPO)
            _rodar(["git", "checkout", "-q", "FETCH_HEAD"], REPO)
            _rodar(["git", "apply", str(PATCH)], REPO)
        if not (VENV / "bin" / "python").is_file():
            _set(etapa="Criando o ambiente Python")
            _rodar([sys.executable, "-m", "venv", str(VENV)])
        if not (VENV / ".pronto").is_file():
            _set(etapa="Instalando as bibliotecas (PyTorch e outras)")
            _rodar([str(VENV / "bin" / "python"), "-m", "pip", "install", "-q", "-r", str(REQUISITOS)])
            (VENV / ".pronto").write_text("ok", encoding="utf-8")
        if not DET_ROSTO.is_file():
            zip_rosto = BASE / "buffalo_l.zip"
            _baixar(URL_ROSTO, zip_rosto, "Baixando o detector de rosto")
            alvo = DET_ROSTO.parent
            alvo.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_rosto) as z:
                z.extractall(alvo)
            zip_rosto.unlink(missing_ok=True)
        if not WHISPER.is_file():
            _baixar(f"https://huggingface.co/{VERSOES['1.5']['hf']}/resolve/main/whisper/tiny.pt", WHISPER,
                    "Baixando o modelo de áudio")
        if not _peso_ok(versao):
            _baixar(f"https://huggingface.co/{v['hf']}/resolve/main/latentsync_unet.pt", v["pesos"],
                    f"Baixando o LatentSync {versao} (5 GB)")
        _set(ativo=False, etapa="Pronto", erro=None)
    except Exception as exc:
        _set(ativo=False, erro=str(exc)[:300], etapa="")


def instalar(versao, nome_ia):
    """Comeca a instalacao em segundo plano. Devolve (comecou, recado)."""
    if not suportado():
        return False, "O LatentSync foi preparado para Mac com chip Apple. Neste computador ele não está disponível."
    if instalada(versao):
        return False, "Esta IA já está instalada."
    with _trava:
        if _inst["ativo"]:
            return False, "Já tem uma instalação em andamento."
        _inst.update(ativo=True, ia=nome_ia, etapa="Começando", baixados=0, total=0, erro=None)
    threading.Thread(target=_trabalho, args=(versao, nome_ia), daemon=True).start()
    return True, "Começando a instalar."


def remover(versao):
    """Apaga os pesos desta versao; se nenhuma outra versao ficar, apaga tambem o ambiente inteiro."""
    import shutil
    if instalando():
        return False, "Há uma instalação em andamento.", 0
    liberados = 0
    p = VERSOES[versao]["pesos"]
    try:
        if p.is_file():
            liberados += p.stat().st_size
            p.unlink()
        outras = [k for k in VERSOES if k != versao and VERSOES[k]["pesos"].is_file()]
        if not outras and BASE.is_dir():
            liberados += sum(f.stat().st_size for f in BASE.rglob("*") if f.is_file())
            shutil.rmtree(BASE)
    except OSError as exc:
        return False, f"Não consegui apagar: {exc}", liberados
    return True, "IA removida.", liberados


# ------------------------------------------------------------------------------------ rodar
class RostoNaoEncontrado(RuntimeError):
    pass


class Cancelou(Exception):
    pass


async def executar(foto, audio, saida, versao, dur, ao_progredir, cancelado):
    """Foto + voz -> video com a boca sincronizada. ao_progredir(feitos, total, fase) e chamado enquanto roda."""
    v = VERSOES[versao]
    BASE.joinpath("tmp").mkdir(parents=True, exist_ok=True)
    video = BASE / "tmp" / f"{saida.stem}_base.mp4"
    r = await asyncio.create_subprocess_exec(
        "ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", str(FPS), "-i", str(foto), "-t", f"{dur:.2f}",
        "-vf", "scale='min(640,iw)':-2,format=yuv420p", "-c:v", "libx264", "-crf", "16", str(video),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
    _, erro = await r.communicate()
    if r.returncode or not video.is_file():
        raise RuntimeError("Não consegui preparar a foto como vídeo: " + erro.decode(errors="replace")[-200:])
    saida.parent.mkdir(parents=True, exist_ok=True)
    total = max(1, math.ceil(dur * FPS / QUADROS_POR_BLOCO))
    cmd = [str(VENV / "bin" / "python"), "-u", "-m", "scripts.inference", "--unet_config_path", v["config"],
           "--inference_ckpt_path", str(v["pesos"]), "--inference_steps", "20", "--guidance_scale", "1.5",
           "--enable_deepcache", "--video_path", str(video), "--audio_path", str(audio), "--video_out_path", str(saida)]
    env = dict(os.environ, PYTORCH_ENABLE_MPS_FALLBACK="1", PYTHONUNBUFFERED="1")
    proc = await asyncio.create_subprocess_exec(*cmd, cwd=str(REPO), env=env, stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.STDOUT)
    feitos, ultimo, cauda = 0, 0, []
    buf = b""
    try:
        while True:
            pedaco = await proc.stdout.read(4096)
            if not pedaco:
                break
            if cancelado():
                proc.kill()
                break
            buf += pedaco
            partes = re.split(rb"[\r\n]", buf)
            buf = partes.pop()
            for linha in partes:
                txt = linha.decode(errors="replace")
                cauda = (cauda + [txt])[-12:]
                if "Sample frames" in txt:
                    m = re.search(r"\b(\d+)/20\b", txt)
                    if m:
                        passo = int(m.group(1))
                        if passo < ultimo:
                            feitos += 1
                        ultimo = passo
                        ao_progredir(min(feitos, total - 1), total, "Sincronizando a boca com a voz")
                elif "Restoring" in txt:
                    ao_progredir(total, total, "Montando o vídeo final")
        await proc.wait()
    finally:
        if proc.returncode is None:
            proc.kill()
        video.unlink(missing_ok=True)
    if cancelado():
        raise Cancelou()
    if proc.returncode != 0 or not saida.is_file():
        resumo = " | ".join(t.strip() for t in cauda if t.strip())[-300:]
        if "Face not detected" in resumo:
            raise RostoNaoEncontrado("Não achei um rosto de frente na foto. Use uma foto com o rosto bem visível.")
        raise RuntimeError("O LatentSync parou com erro: " + resumo)
