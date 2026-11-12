"""Coleta automática de métricas nas plataformas.

Usa as mesmas contas já conectadas para publicar. O que cada API entrega depende das
permissões do token:

  YouTube  -> YouTube Analytics API (yt-analytics.readonly) + Data API (youtube.readonly)
  TikTok   -> user.info.basic + video.list
  Instagram-> instagram_manage_insights + instagram_basic

Se o token não tiver a permissão, a coleta devolve o motivo em português e não inventa
número. O dashboard continua mostrando o que já foi coletado antes.
"""
import json
import re
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

import aiohttp

import analytics


class ColetaErro(Exception):
    pass


def _num(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _iso_ts(s):
    try:
        txt = str(s).replace("Z", "+00:00")
        txt = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", txt)
        return int(datetime.fromisoformat(txt).timestamp())
    except (ValueError, TypeError):
        return 0


def _dia_ts(s):
    try:
        return int(datetime.strptime(str(s)[:10], "%Y-%m-%d").replace(hour=12).timestamp())
    except (ValueError, TypeError):
        return int(time.time())


def _erro(d, txt, status):
    e = d.get("error") if isinstance(d, dict) else None
    if isinstance(e, dict):
        e = e.get("message") or e.get("code")
    msg = e or (d.get("error_description") if isinstance(d, dict) else None) or \
        (d.get("message") if isinstance(d, dict) else None) or txt
    return "%s (%s)" % (str(msg)[:320], status)


async def _req(metodo, url, headers=None, params=None, corpo=None, form=None, timeout=45):
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as s:
        kw = {"headers": headers, "params": params}
        if form is not None:
            kw["data"] = form
        elif corpo is not None:
            kw["json"] = corpo
        async with s.request(metodo, url, **kw) as r:
            txt = await r.text()
            try:
                d = json.loads(txt) if txt else {}
            except Exception:
                d = {"texto": txt}
            if r.status >= 400:
                raise ColetaErro(_erro(d, txt, r.status))
            return d


def _parece_permissao(msg):
    m = str(msg).lower()
    return any(x in m for x in ("403", "forbidden", "permission", "insufficient", "scope", "unauthorized", "401"))


async def _google_token(cfg):
    if not (cfg.get("client_id") and cfg.get("client_secret") and cfg.get("refresh_token")):
        raise ColetaErro("Faltam client_id, client_secret e refresh_token do YouTube.")
    d = await _req("POST", "https://oauth2.googleapis.com/token", form={
        "client_id": cfg["client_id"], "client_secret": cfg["client_secret"],
        "refresh_token": cfg["refresh_token"], "grant_type": "refresh_token",
    })
    token = d.get("access_token")
    if not token:
        raise ColetaErro("O Google não devolveu o token de acesso.")
    return token


async def _youtube_titulos(ids, token):
    saida = {}
    for i in range(0, len(ids), 50):
        lote = ids[i:i + 50]
        d = await _req("GET", "https://www.googleapis.com/youtube/v3/videos", headers={
            "Authorization": "Bearer " + token}, params={"part": "snippet", "id": ",".join(lote)})
        for item in d.get("items") or []:
            sn = item.get("snippet") or {}
            saida[item.get("id")] = {
                "titulo": sn.get("title") or "",
                "quando": _iso_ts(sn.get("publishedAt")),
                "url": "https://youtu.be/" + item.get("id", ""),
            }
    return saida


async def youtube(cfg, cid, canal_dir, dias=30):
    token = await _google_token(cfg)
    h = {"Authorization": "Bearer " + token}
    fim = datetime.now(timezone.utc).date()
    ini = fim - timedelta(days=max(1, dias) - 1)
    base = "https://youtubeanalytics.googleapis.com/v2/reports"
    params = {"ids": "channel==MINE", "startDate": ini.isoformat(), "endDate": fim.isoformat(),
              "metrics": "views,estimatedMinutesWatched,likes,comments,shares,subscribersGained,estimatedRevenue",
              "dimensions": "day", "sort": "day"}
    try:
        d = await _req("GET", base, headers=h, params=params)
    except ColetaErro as e:
        if _parece_permissao(e):
            raise ColetaErro("O YouTube não autorizou a análise. Reconecte a conta com o escopo "
                             "yt-analytics.readonly.")
        params["metrics"] = "views,estimatedMinutesWatched,likes,comments,shares,subscribersGained"
        d = await _req("GET", base, headers=h, params=params)
    col = [x.get("name") for x in d.get("columnHeaders") or []]
    novos = 0
    for row in d.get("rows") or []:
        m = dict(zip(col, row))
        dia = str(row[0])[:10] if row else ""
        analytics.registrar(cid, canal_dir, {
            "plataforma": "youtube", "titulo": "Canal · " + dia,
            "publicado_em": _dia_ts(dia), "tipo": "dia",
            "views": _num(m.get("views")), "likes": _num(m.get("likes")),
            "comments": _num(m.get("comments")), "shares": _num(m.get("shares")),
            "watch_time": _num(m.get("estimatedMinutesWatched")) * 60,
            "seguidores": _num(m.get("subscribersGained")),
            "receita": _num(m.get("estimatedRevenue")),
        })
        novos += 1

    p2 = {"ids": "channel==MINE", "startDate": ini.isoformat(), "endDate": fim.isoformat(),
          "metrics": "views,estimatedMinutesWatched,likes,comments,shares,estimatedRevenue",
          "dimensions": "video", "sort": "-views", "maxResults": 50}
    try:
        d2 = await _req("GET", base, headers=h, params=p2)
    except ColetaErro as e:
        if _parece_permissao(e):
            raise
        p2["metrics"] = "views,estimatedMinutesWatched,likes,comments,shares"
        d2 = await _req("GET", base, headers=h, params=p2)
    col2 = [x.get("name") for x in d2.get("columnHeaders") or []]
    rows2 = d2.get("rows") or []
    ids = [str(r[0]) for r in rows2 if r]
    titulos = await _youtube_titulos(ids, token)
    for row in rows2:
        m = dict(zip(col2, row))
        vid = str(row[0])
        info = titulos.get(vid) or {}
        analytics.registrar(cid, canal_dir, {
            "plataforma": "youtube", "producao_id": "yt:" + vid,
            "titulo": info.get("titulo") or ("YouTube · " + vid[:8]),
            "publicado_em": info.get("quando") or int(time.time()), "tipo": "video",
            "url": info.get("url") or "", "views": _num(m.get("views")),
            "likes": _num(m.get("likes")), "comments": _num(m.get("comments")),
            "shares": _num(m.get("shares")), "watch_time": _num(m.get("estimatedMinutesWatched")) * 60,
            "receita": _num(m.get("estimatedRevenue")),
        })
        novos += 1
    return {"novos": novos}


async def tiktok(cfg, cid, canal_dir, dias=30):
    token = cfg.get("access_token")
    if not token:
        raise ColetaErro("Falta o access_token do TikTok.")
    h = {"Authorization": "Bearer " + token}
    try:
        u = await _req("GET", "https://open.tiktokapis.com/v2/user/info/", headers=h,
                       params={"fields": "follower_count"})
        seg = _num(((u.get("data") or {}).get("user") or {}).get("follower_count"))
        if seg:
            analytics.registrar(cid, canal_dir, {
                "plataforma": "tiktok", "titulo": "Seguidores TikTok", "publicado_em": int(time.time()),
                "tipo": "seguidores", "seguidores": seg,
            })
    except ColetaErro as e:
        if _parece_permissao(e):
            raise ColetaErro("O TikTok não autorizou a análise. Reconecte com user.info.basic e video.list.")
    d = await _req("POST", "https://open.tiktokapis.com/v2/video/list/", headers=h,
                   params={"fields": "id,title,create_time,view_count,like_count,comment_count,share_count"},
                   corpo={"max_count": 50})
    lista = ((d.get("data") or {}).get("videos") or d.get("videos") or [])
    novos = 0
    for v in lista:
        vid = v.get("id") or ""
        analytics.registrar(cid, canal_dir, {
            "plataforma": "tiktok", "producao_id": "tt:" + str(vid),
            "titulo": v.get("title") or "TikTok · " + str(vid)[:10],
            "publicado_em": int(v.get("create_time") or time.time()), "tipo": "video",
            "url": ("https://www.tiktok.com/video/" + str(vid)) if vid else "",
            "views": _num(v.get("view_count")), "likes": _num(v.get("like_count")),
            "comments": _num(v.get("comment_count")), "shares": _num(v.get("share_count")),
        })
        novos += 1
    return {"novos": novos}


async def instagram(cfg, cid, canal_dir, dias=30):
    token = cfg.get("access_token")
    ig = cfg.get("ig_user_id")
    if not (token and ig):
        raise ColetaErro("Faltam access_token e ig_user_id do Instagram.")
    base = "https://graph.facebook.com/v21.0/" + str(ig)
    try:
        u = await _req("GET", base, params={"fields": "followers_count", "access_token": token})
        seg = _num(u.get("followers_count"))
        if seg:
            analytics.registrar(cid, canal_dir, {
                "plataforma": "instagram", "titulo": "Seguidores Instagram",
                "publicado_em": int(time.time()), "tipo": "seguidores", "seguidores": seg,
            })
    except ColetaErro as e:
        if _parece_permissao(e):
            raise ColetaErro("O Instagram não autorizou a análise. Reconecte com instagram_manage_insights.")
    d = await _req("GET", base + "/media", params={
        "fields": "id,caption,permalink,timestamp,like_count,comments_count,media_type",
        "limit": 50, "access_token": token})
    novos = 0
    for m in d.get("data") or []:
        mid = m.get("id") or ""
        views = shares = 0.0
        for metrica in ("impressions,reach,plays,shares,saved", "views,reach,shares,saved"):
            try:
                ins = await _req("GET", "https://graph.facebook.com/v21.0/" + mid + "/insights",
                                 params={"metric": metrica, "access_token": token})
                vals = {}
                for item in ins.get("data") or []:
                    vs = item.get("values") or []
                    if vs:
                        vals[item.get("name")] = _num(vs[0].get("value"))
                views = vals.get("impressions") or vals.get("plays") or vals.get("views") or vals.get("reach") or 0
                shares = vals.get("shares") or 0
                break
            except ColetaErro:
                continue
        analytics.registrar(cid, canal_dir, {
            "plataforma": "instagram", "producao_id": "ig:" + mid,
            "titulo": (m.get("caption") or "Instagram · " + mid[:8])[:200],
            "publicado_em": _iso_ts(m.get("timestamp")) or int(time.time()), "tipo": "video",
            "url": m.get("permalink") or "", "views": views,
            "likes": _num(m.get("like_count")), "comments": _num(m.get("comments_count")),
            "shares": shares,
        })
        novos += 1
    return {"novos": novos}


async def facebook(cfg, cid, canal_dir, dias=30):
    token = cfg.get("access_token")
    page = cfg.get("page_id")
    if not (token and page):
        raise ColetaErro("Faltam page_id e access_token da Página do Facebook.")
    base = "https://graph.facebook.com/v21.0/" + str(page)
    try:
        u = await _req("GET", base, params={"fields": "followers_count", "access_token": token})
        seg = _num(u.get("followers_count"))
        if seg:
            analytics.registrar(cid, canal_dir, {
                "plataforma": "facebook", "titulo": "Seguidores Facebook",
                "publicado_em": int(time.time()), "tipo": "seguidores", "seguidores": seg,
            })
    except ColetaErro as e:
        if _parece_permissao(e):
            raise ColetaErro("O Facebook não autorizou a análise. Reconecte com pages_read_engagement.")
    d = await _req("GET", base + "/videos", params={
        "fields": "id,title,created_time,permalink_url", "limit": 50, "access_token": token})
    novos = 0
    for v in d.get("data") or []:
        vid = v.get("id") or ""
        views = 0.0
        try:
            ins = await _req("GET", "https://graph.facebook.com/v21.0/" + vid + "/video_insights",
                             params={"metric": "total_video_views", "access_token": token})
            for item in ins.get("data") or []:
                vs = item.get("values") or []
                if vs:
                    views = _num(vs[0].get("value"))
        except ColetaErro:
            pass
        analytics.registrar(cid, canal_dir, {
            "plataforma": "facebook", "producao_id": "fb:" + vid,
            "titulo": v.get("title") or ("Facebook · " + vid[:8]),
            "publicado_em": _iso_ts(v.get("created_time")) or int(time.time()), "tipo": "video",
            "url": v.get("permalink_url") or "", "views": views,
        })
        novos += 1
    return {"novos": novos}


COLETORES = {"youtube": youtube, "tiktok": tiktok, "instagram": instagram, "facebook": facebook}


async def coletar(canal, canal_dir, dias=30):
    cid = canal["id"]
    cred = canais_cred(cid)
    resultados = {}
    for plataforma, fn in COLETORES.items():
        cfg = cred.get(plataforma) or {}
        if not cfg:
            resultados[plataforma] = {"ok": False, "erro": "Conta não conectada."}
            continue
        try:
            r = await fn(cfg, cid, canal_dir, dias)
            resultados[plataforma] = {"ok": True, **r}
        except Exception as exc:
            resultados[plataforma] = {"ok": False, "erro": str(exc)[:400]}
    d = analytics.carregar(cid, canal_dir)
    coleta = d.setdefault("coleta", {})
    agora = int(time.time())
    for p, r in resultados.items():
        coleta[p] = {"quando": agora, "ok": bool(r.get("ok")),
                     "novos": int(r.get("novos") or 0), "erro": r.get("erro") or ""}
    analytics.gravar(cid, canal_dir, d)
    return {"resultados": resultados, "coleta": coleta}


def canais_cred(cid):
    import canais
    return canais.credenciais(cid)
