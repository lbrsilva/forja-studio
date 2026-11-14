"""B-roll grátis para as cenas: Pexels e Pixabay.

As chaves são opcionais e ficam em API/pexels.txt e API/pixabay.txt. Sem chave,
o canal continua com as imagens geradas pela IA. O vídeo baixado fica em
_cache/broll e é reaproveitado por termo, proporção e URL.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import urllib.parse
import urllib.request

import chaves
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
API = Path(os.environ.get("ESTUDIO_API_DIR") or (RAIZ / "API"))
CACHE = Path(os.environ.get("ESTUDIO_CACHE") or (RAIZ / "_cache")) / "broll"
MAX_BYTES = 80 * 1024 * 1024


def fontes_disponiveis():
    return [f for f in ("pexels", "pixabay") if chaves.lista(f)]


def disponivel(fonte="auto"):
    if fonte and fonte not in ("auto", ""):
        return bool(chaves.lista(fonte))
    return bool(fontes_disponiveis())


def termo_de_cena(cena):
    texto = str((cena or {}).get("broll") or (cena or {}).get("broll_termo")
                or (cena or {}).get("imagem") or (cena or {}).get("fala") or "")
    texto = re.sub(r"\([^)]*\)", " ", texto)
    texto = re.sub(r"[^\w\s-]", " ", texto, flags=re.UNICODE)
    palavras = [p for p in texto.split() if len(p) > 2][:8]
    return " ".join(palavras)


def _orientacao(proporcao):
    try:
        l, a = (int(x) for x in str(proporcao).split(":"))
    except Exception:
        return "portrait"
    if l > a:
        return "landscape"
    if l == a:
        return "square"
    return "portrait"


def _get_json(url, headers=None, timeout=15):
    pedido = urllib.request.Request(url, headers=headers or {},
                                    )
    with urllib.request.urlopen(pedido, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _melhor_arquivo(arquivos, proporcao):
    alvo = None
    try:
        l, a = (int(x) for x in str(proporcao).split(":"))
        alvo = l / float(a)
    except Exception:
        alvo = 9 / 16.0
    melhor, nota = None, -1e9
    for arq in arquivos:
        try:
            w, h = int(arq.get("width") or 0), int(arq.get("height") or 0)
        except Exception:
            continue
        if not w or not h:
            continue
        nota_arq = -abs((w / float(h)) - alvo) * 100
        if h >= 720:
            nota_arq += 10
        if h > 1920:
            nota_arq -= 20
        if str(arq.get("quality") or "").lower() == "hd":
            nota_arq += 5
        if nota_arq > nota:
            melhor, nota = arq, nota_arq
    return melhor


def _buscar_pexels(termo, proporcao, chave):
    url = ("https://api.pexels.com/videos/search?query=%s&per_page=15&orientation=%s"
           % (urllib.parse.quote(termo), _orientacao(proporcao)))
    d = _get_json(url, {"Authorization": chave})
    for v in d.get("videos") or []:
        arq = _melhor_arquivo(v.get("video_files") or [], proporcao)
        if arq and arq.get("link"):
            return {"url": arq["link"], "duracao": float(v.get("duration") or 0),
                    "fonte": "pexels", "id": v.get("id")}
    return None


def _buscar_pixabay(termo, proporcao, chave):
    url = ("https://pixabay.com/api/videos/?key=%s&q=%s&per_page=20&video_type=film&safesearch=true"
           % (urllib.parse.quote(chave), urllib.parse.quote(termo)))
    d = _get_json(url)
    for v in d.get("hits") or []:
        videos = v.get("videos") or {}
        arquivos = []
        for nome in ("large", "medium", "small"):
            x = videos.get(nome)
            if isinstance(x, dict) and x.get("url"):
                arquivos.append({"link": x["url"], "width": x.get("width"),
                                 "height": x.get("height"), "quality": "hd" if nome == "large" else ""})
        arq = _melhor_arquivo(arquivos, proporcao)
        if arq:
            return {"url": arq["link"], "duracao": float(v.get("duration") or 0),
                    "fonte": "pixabay", "id": v.get("id")}
    return None


def _buscar_fonte(fonte, termo, proporcao, chave):
    if fonte == "pexels":
        return _buscar_pexels(termo, proporcao, chave)
    if fonte == "pixabay":
        return _buscar_pixabay(termo, proporcao, chave)
    return None


def _valido(caminho):
    try:
        r = subprocess.run([shutil.which("ffprobe") or "ffprobe", "-v", "error",
                            "-show_entries", "format=duration", "-of", "default=nw=1:nk=1",
                            str(caminho)], capture_output=True, text=True, timeout=20)
        return r.returncode == 0 and float((r.stdout or "").strip() or 0) > 0.2
    except Exception:
        return False


def _url_sem_chave(url):
    try:
        partes = urllib.parse.urlsplit(url)
        query = [(k, v) for k, v in urllib.parse.parse_qsl(partes.query, keep_blank_values=True)
                 if k.lower() not in ("key", "api_key", "token", "access_token")]
        return urllib.parse.urlunsplit((partes.scheme, partes.netloc, partes.path,
                                        urllib.parse.urlencode(query), ""))
    except Exception:
        return url


def _cache_path(termo, proporcao, fonte, url):
    limpa = _url_sem_chave(url)
    h = hashlib.sha256(("%s|%s|%s|%s" % (termo, proporcao, fonte, limpa)).encode("utf-8")).hexdigest()
    return CACHE / (h + ".mp4"), CACHE / (h + ".json")


def _baixar(url, termo, proporcao, fonte, timeout=30):
    CACHE.mkdir(parents=True, exist_ok=True)
    destino, meta = _cache_path(termo, proporcao, fonte, url)
    if destino.is_file() and destino.stat().st_size > 10000:
        return destino
    tmp = destino.with_name(destino.name + ".tmp")
    try:
        pedido = urllib.request.Request(url, headers={"User-Agent": "ForjaStudio/1.0"})
        with urllib.request.urlopen(pedido, timeout=timeout) as r, tmp.open("wb") as f:
            total = 0
            while True:
                bloco = r.read(1024 * 256)
                if not bloco:
                    break
                total += len(bloco)
                if total > MAX_BYTES:
                    raise RuntimeError("vídeo de B-roll grande demais")
                f.write(bloco)
        if tmp.stat().st_size < 10000:
            raise RuntimeError("download vazio")
        if not _valido(tmp):
            raise RuntimeError("vídeo de B-roll inválido")
        os.replace(tmp, destino)
        meta.write_text(json.dumps({"termo": termo, "proporcao": proporcao, "fonte": fonte,
                                    "url": _url_sem_chave(url)}, ensure_ascii=False, indent=1),
                        encoding="utf-8")
        return destino
    except Exception:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        return None


def buscar(termo, proporcao="9:16", duracao=5.0, fonte="auto"):
    termo = str(termo or "").strip()
    if not termo:
        return None
    fontes = fontes_disponiveis() if fonte in ("auto", "") else [fonte]
    for f in fontes:
        for chave in chaves.ordenadas(f):
            try:
                achado = _buscar_fonte(f, termo, proporcao, chave)
            except Exception:
                achado = None
            if not achado:
                continue
            arq = _baixar(achado["url"], termo, proporcao, f)
            if arq:
                return arq
    return None
