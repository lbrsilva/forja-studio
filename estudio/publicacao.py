"""Publicação — YouTube, TikTok e Instagram a partir do arquivo final.

As credenciais ficam em `canais/segredos.json` (chmod 600) e nunca voltam para a tela:
o GET devolve só "configurado" e os campos mascarados. Sem credencial a publicação não
some com o vídeo: grava um pacote manual (legenda + caminho) e devolve "aguardando
credenciais", para o agendador tentar de novo quando a conta for conectada.
"""
import asyncio
import json
import math
import os
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import aiohttp

TIMEOUT = aiohttp.ClientTimeout(total=600)
YT_TOKEN = "https://oauth2.googleapis.com/token"
YT_UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"
TT_INIT = "https://open.tiktokapis.com/v2/post/publish/video/init/"
TT_STATUS = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
IG_BASE = "https://graph.facebook.com/v21.0"


class PublicacaoErro(Exception):
    pass


def _texto(v, limite):
    return str(v or "").strip()[:limite]


def _bool(v):
    return str(v).strip().lower() in ("1", "true", "sim", "yes", "on")


def _iso(quando):
    return datetime.fromtimestamp(int(quando), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mime(caminho):
    nome = str(caminho).lower()
    if nome.endswith(".mov"):
        return "video/quicktime"
    if nome.endswith(".webm"):
        return "video/webm"
    return "video/mp4"


async def _json(metodo, url, *, headers=None, params=None, corpo=None, timeout=TIMEOUT):
    async with aiohttp.ClientSession(timeout=timeout) as s:
        async with s.request(metodo, url, headers=headers, params=params, json=corpo) as r:
            txt = await r.text()
            try:
                dados = json.loads(txt) if txt else {}
            except Exception:
                dados = {"texto": txt}
            if r.status >= 400:
                detalhe = dados.get("error_description") or dados.get("error") or dados.get("message") or txt
                raise PublicacaoErro("%s (%s)" % (str(detalhe)[:300], r.status))
            return dados, dict(r.headers)


async def _put(url, dados, headers, timeout=TIMEOUT):
    async with aiohttp.ClientSession(timeout=timeout) as s:
        async with s.put(url, data=dados, headers=headers) as r:
            txt = await r.text()
            if r.status >= 400:
                raise PublicacaoErro("envio do vídeo falhou (%s): %s" % (r.status, txt[:300]))
            try:
                return json.loads(txt) if txt else {}
            except Exception:
                return {"texto": txt}


async def _form(url, dados, headers=None, timeout=TIMEOUT):
    async with aiohttp.ClientSession(timeout=timeout) as s:
        async with s.post(url, data=dados, headers=headers) as r:
            txt = await r.text()
            try:
                resp = json.loads(txt) if txt else {}
            except Exception:
                resp = {"texto": txt}
            if r.status >= 400:
                detalhe = resp.get("error_description") or resp.get("error") or txt
                raise PublicacaoErro("%s (%s)" % (str(detalhe)[:300], r.status))
            return resp


def _topo(meta, plataforma, padrao_titulo):
    tags = [str(h).lstrip("#") for h in (meta.get("hashtags") or []) if str(h).strip()]
    if plataforma == "youtube":
        return {
            "titulo": _texto(meta.get("titulo") or padrao_titulo, 100),
            "descricao": _texto(meta.get("descricao") or "", 4900),
            "tags": tags[:30],
        }
    if plataforma == "tiktok":
        sufixo = " ".join(meta.get("hashtags") or [])
        return {"titulo": _texto(((meta.get("titulo") or padrao_titulo) + " " + sufixo).strip(), 2200)}
    if plataforma in ("instagram", "facebook"):
        legenda = _texto(meta.get("descricao") or "", 2100)
        if tags:
            legenda = (legenda + "\n\n" + " ".join("#" + t for t in tags[:30])).strip()
        return {"legenda": legenda}
    return {"legenda": _texto(meta.get("descricao") or "", 2100)}


async def _youtube(cfg, video, meta, quando, visibilidade, formato=None):
    if not (cfg.get("client_id") and cfg.get("client_secret") and cfg.get("refresh_token")):
        raise PublicacaoErro("Faltam client_id, client_secret e refresh_token do YouTube.")
    tok = await _form(YT_TOKEN, {
        "client_id": cfg["client_id"], "client_secret": cfg["client_secret"],
        "refresh_token": cfg["refresh_token"], "grant_type": "refresh_token",
    })
    access = tok.get("access_token")
    if not access:
        raise PublicacaoErro("O Google não devolveu o token de acesso.")
    info = _topo(meta, "youtube", "Vídeo")
    futuro = int(quando or 0) > int(time.time()) + 120
    status = {"privacyStatus": "private" if futuro else (visibilidade or "public")}
    if futuro:
        status["publishAt"] = _iso(quando)
    corpo = {
        "snippet": {"title": info["titulo"], "description": info["descricao"],
                    "tags": info["tags"], "categoryId": str(cfg.get("categoria") or "22")},
        "status": status,
    }
    dados = Path(video).read_bytes()
    headers = {"Authorization": "Bearer " + access,
               "Content-Type": "application/json; charset=UTF-8",
               "X-Upload-Content-Type": _mime(video),
               "X-Upload-Content-Length": str(len(dados))}
    _, resp = await _json("POST", YT_UPLOAD + "?uploadType=resumable&part=snippet,status",
                          headers=headers, corpo=corpo)
    url = resp.get("Location") or resp.get("location")
    if not url:
        raise PublicacaoErro("O YouTube não devolveu o endereço de envio.")
    r = await _put(url, dados, {"Content-Type": _mime(video), "Content-Length": str(len(dados))})
    vid = r.get("id") or ""
    return {"ok": True, "id": vid, "url": ("https://youtu.be/" + vid) if vid else "",
            "agendado": bool(futuro)}


async def _tiktok(cfg, video, meta, quando, visibilidade, formato=None):
    if not cfg.get("access_token"):
        raise PublicacaoErro("Falta o access_token do TikTok.")
    info = _topo(meta, "tiktok", "Vídeo")
    dados = Path(video).read_bytes()
    tamanho = len(dados)
    if tamanho <= 0:
        raise PublicacaoErro("O vídeo está vazio.")
    passo = tamanho if tamanho <= 5 * 1024 * 1024 else 10 * 1024 * 1024
    partes = max(1, math.ceil(tamanho / passo))
    privacidade = "SELF_ONLY" if (visibilidade or "").lower() in ("private", "privado") else \
        (cfg.get("privacy_level") or "PUBLIC_TO_EVERYONE")
    corpo = {
        "post_info": {"title": info["titulo"], "privacy_level": privacidade,
                      "disable_comment": _bool(cfg.get("disable_comment")),
                      "disable_duet": _bool(cfg.get("disable_duet")),
                      "disable_stitch": _bool(cfg.get("disable_stitch"))},
        "source_info": {"source": "FILE_UPLOAD", "video_size": tamanho,
                        "chunk_size": passo, "total_chunk_count": partes},
    }
    headers = {"Authorization": "Bearer " + cfg["access_token"], "Content-Type": "application/json"}
    d, _ = await _json("POST", TT_INIT, headers=headers, corpo=corpo)
    data = d.get("data") or {}
    url = data.get("upload_url")
    publish_id = data.get("publish_id")
    if not url or not publish_id:
        raise PublicacaoErro("O TikTok não devolveu o endereço de envio: " + str(d.get("error") or d)[:200])
    for i in range(partes):
        ini = i * passo
        fim = min(tamanho - 1, ini + passo - 1)
        pedaco = dados[ini:fim + 1]
        h = {"Content-Type": "video/mp4", "Content-Length": str(len(pedaco)),
             "Content-Range": "bytes %d-%d/%d" % (ini, fim, tamanho)}
        await _put(url, pedaco, h)
    estado = "PROCESSING_UPLOAD"
    for _ in range(60):
        await asyncio.sleep(5)
        d, _ = await _json("POST", TT_STATUS, headers=headers, corpo={"publish_id": publish_id})
        estado = str((d.get("data") or {}).get("status") or "")
        if estado in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX", "FAILED"):
            break
    if estado == "FAILED":
        raise PublicacaoErro("O TikTok recusou a publicação: " + str(d.get("error") or "")[:200])
    return {"ok": estado in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"), "id": publish_id,
            "estado": estado}


async def _instagram(cfg, video, meta, quando, visibilidade, formato=None):
    if not (cfg.get("access_token") and cfg.get("ig_user_id")):
        raise PublicacaoErro("Faltam access_token e ig_user_id do Instagram.")
    base = (cfg.get("video_base_url") or "").strip().rstrip("/")
    if not base:
        raise PublicacaoErro("O Instagram exige uma URL pública do vídeo. Configure "
                             "'video_base_url' na aba Ajustes (uma pasta servida por link público).")
    nome = urllib.parse.quote(Path(video).name)
    url_video = base + "/" + nome
    info = _topo(meta, "instagram", "Vídeo")
    tipo = "STORIES" if (formato or {}).get("id") == "instagram-stories" else "REELS"
    corpo = {"media_type": tipo, "video_url": url_video, "caption": info["legenda"],
             "access_token": cfg["access_token"]}
    if tipo == "REELS":
        corpo["share_to_feed"] = True
    d, _ = await _json("POST", IG_BASE + "/" + cfg["ig_user_id"] + "/media", corpo=corpo)
    container = d.get("id")
    if not container:
        raise PublicacaoErro("O Instagram não criou o container: " + str(d)[:200])
    pronto = False
    for _ in range(90):
        await asyncio.sleep(5)
        st, _ = await _json("GET", IG_BASE + "/" + container,
                            params={"fields": "status_code,status", "access_token": cfg["access_token"]})
        if st.get("status_code") == "FINISHED":
            pronto = True
            break
        if st.get("status_code") == "ERROR":
            raise PublicacaoErro("O Instagram recusou o vídeo: " + str(st.get("status") or "")[:200])
    if not pronto:
        raise PublicacaoErro("O Instagram ainda está processando o vídeo. Tente publicar de novo em alguns minutos.")
    r, _ = await _json("POST", IG_BASE + "/" + cfg["ig_user_id"] + "/media_publish",
                       corpo={"creation_id": container, "access_token": cfg["access_token"]})
    mid = r.get("id") or ""
    return {"ok": bool(mid), "id": mid}


async def _facebook(cfg, video, meta, quando, visibilidade, formato=None):
    token = cfg.get("access_token")
    page = cfg.get("page_id")
    if not (token and page):
        raise PublicacaoErro("Faltam page_id e access_token da Página do Facebook.")
    info = _topo(meta, "facebook", "Vídeo")
    dados = Path(video).read_bytes()
    futuro = int(quando or 0) > int(time.time()) + 600
    form = aiohttp.FormData()
    form.add_field("access_token", token)
    form.add_field("description", info["legenda"] or "")
    form.add_field("title", _texto(meta.get("titulo") or "Vídeo", 200))
    if futuro:
        form.add_field("published", "false")
        form.add_field("scheduled_publish_time", str(int(quando)))
    else:
        form.add_field("published", "true")
    form.add_field("source", dados, filename=Path(video).name, content_type=_mime(video))
    async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
        async with s.post("https://graph.facebook.com/v21.0/" + str(page) + "/videos", data=form) as r:
            txt = await r.text()
            try:
                d = json.loads(txt) if txt else {}
            except Exception:
                d = {}
            if r.status >= 400:
                e = (d.get("error") or {}).get("message") if isinstance(d.get("error"), dict) else d.get("error")
                raise PublicacaoErro("Facebook recusou o vídeo: " + str(e or txt)[:300])
            vid = d.get("id") or ""
            return {"ok": bool(vid), "id": vid,
                    "url": ("https://www.facebook.com/" + vid) if vid else "", "agendado": futuro}


ADAPTADORES = {"youtube": _youtube, "tiktok": _tiktok, "instagram": _instagram, "facebook": _facebook}
ROTULOS = {"youtube": "YouTube", "tiktok": "TikTok", "instagram": "Instagram", "facebook": "Facebook"}


def _configurado(plataforma, cfg):
    cfg = cfg or {}
    if plataforma == "youtube":
        return bool(cfg.get("client_id") and cfg.get("client_secret") and cfg.get("refresh_token"))
    if plataforma == "tiktok":
        return bool(cfg.get("access_token"))
    if plataforma == "facebook":
        return bool(cfg.get("page_id") and cfg.get("access_token"))
    return bool(cfg.get("access_token") and cfg.get("ig_user_id"))


def pacote_manual(producao, formato, meta, pasta):
    pasta = Path(pasta) / "publicacao"
    pasta.mkdir(parents=True, exist_ok=True)
    legenda = _texto(meta.get("descricao") or "", 20000)
    tags = " ".join(str(h) for h in (meta.get("hashtags") or []))
    (pasta / "legenda.txt").write_text(legenda + ("\n\n" + tags if tags else "") + "\n", encoding="utf-8")
    (pasta / "post.json").write_text(json.dumps({
        "titulo": meta.get("titulo"), "descricao": meta.get("descricao"),
        "hashtags": meta.get("hashtags"), "formato": formato.get("id"),
        "video": str(producao.get("arquivos", {}).get("videos", {}).get(formato.get("id")) or ""),
        "quando": meta.get("quando"),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(pasta / "legenda.txt")


async def publicar(canal, producao, formato, plataformas, meta, segredos, pasta_producao):
    video = (producao.get("arquivos", {}).get("videos", {}) or {}).get(formato.get("id"))
    if not video or not Path(video).is_file():
        raise PublicacaoErro("O arquivo final do formato %s não existe." % formato.get("nome"))
    meta = dict(meta or {})
    meta.setdefault("titulo", producao.get("titulo"))
    pacote_manual(producao, formato, meta, pasta_producao)
    cfg_canal = (segredos or {}).get(canal.get("id")) or {}
    resultados = {}
    for p in plataformas:
        if p not in ADAPTADORES:
            continue
        cfg = cfg_canal.get(p) or {}
        if not _configurado(p, cfg):
            resultados[p] = {"ok": False, "pendente": True,
                             "erro": "Conta de %s ainda não conectada." % ROTULOS.get(p, p)}
            continue
        try:
            resultados[p] = await ADAPTADORES[p](cfg, video, meta, meta.get("quando"),
                                                 meta.get("visibilidade") or "public", formato)
        except Exception as exc:
            resultados[p] = {"ok": False, "erro": str(exc)[:400]}
    return resultados
