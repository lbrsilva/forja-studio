"""Análise — o retorno de cada canal, por plataforma, por horário e por vídeo.

Não inventa número: só agrega o que foi importado (CSV/JSON das plataformas) e o que o
próprio estúdio registrou ao publicar. Com dados de menos, a tela diz o que falta em vez
de desenhar um gráfico que parece verdade e não é.
"""
import csv
import io
import json
import re
import time
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

DIAS_SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def _sem_acento(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c))


def _chave(s):
    return re.sub(r"[^a-z0-9]+", "_", _sem_acento(s).lower()).strip("_")


def _num(v):
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("R$", "").replace("$", "").replace("€", "").replace(" ", " ")
    s = re.sub(r"[^0-9,.\-]", "", s)
    if not s:
        return 0.0
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        if re.fullmatch(r"-?\d{1,3}(,\d{3})+", s):
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _data(v):
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v or "").strip()
    if not s:
        return 0
    if re.fullmatch(r"\d{10,13}", s):
        n = int(s)
        return n // 1000 if n > 10 ** 12 else n
    s = s.replace("Z", "+00:00")
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                "%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return int(datetime.strptime(s, fmt).timestamp())
        except ValueError:
            continue
    try:
        return int(datetime.fromisoformat(s).timestamp())
    except ValueError:
        return 0


CAMPOS = {
    "data": ("data", "date", "dia", "publicado_em", "published_at", "postado_em", "when"),
    "plataforma": ("plataforma", "platform", "rede", "canal"),
    "titulo": ("titulo", "title", "video", "nome", "conteudo"),
    "views": ("views", "visualizacoes", "visualizações", "views_count", "impressoes"),
    "likes": ("likes", "curtidas", "like"),
    "comments": ("comments", "comentarios", "comentários", "comment"),
    "shares": ("shares", "compartilhamentos", "compartilhado", "share"),
    "watch_time": ("watch_time", "tempo_assistido", "tempo", "horas_assistidas"),
    "receita": ("receita", "revenue", "ganhos", "renda", "earnings", "valor"),
    "seguidores": ("seguidores", "followers", "inscritos", "subs"),
    "url": ("url", "link"),
    "producao_id": ("producao_id", "producao", "production_id"),
}


def _mapa(cabecalho):
    mapa = {}
    for col in cabecalho:
        k = _chave(col)
        for campo, nomes in CAMPOS.items():
            if k in (_chave(n) for n in nomes):
                mapa[col] = campo
                break
    return mapa


def _linha(d, mapa):
    r = {campo: None for campo in CAMPOS}
    for col, campo in mapa.items():
        r[campo] = d.get(col)
    if not r.get("plataforma"):
        r["plataforma"] = "youtube"
    r["plataforma"] = _chave(r["plataforma"]) or "youtube"
    if r["plataforma"] not in ("youtube", "tiktok", "instagram"):
        r["plataforma"] = "youtube"
    for campo in ("views", "likes", "comments", "shares", "watch_time", "receita", "seguidores"):
        r[campo] = _num(r.get(campo))
    r["publicado_em"] = _data(r.get("data"))
    r["titulo"] = str(r.get("titulo") or "").strip()[:200]
    r["url"] = str(r.get("url") or "").strip()[:500]
    r["producao_id"] = str(r.get("producao_id") or "").strip()[:60]
    return r


def _arquivo(canal_id, canal_dir):
    return Path(canal_dir) / "metricas.json"


def carregar(canal_id, canal_dir):
    try:
        d = json.loads(_arquivo(canal_id, canal_dir).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {"videos": []}
    except (OSError, ValueError):
        return {"videos": []}


def gravar(canal_id, canal_dir, dados):
    dados["atualizado"] = int(time.time())
    arq = _arquivo(canal_id, canal_dir)
    arq.parent.mkdir(parents=True, exist_ok=True)
    tmp = arq.with_name(arq.name + ".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(arq)
    return dados


def _registro(base):
    return {
        "id": (str(base.get("producao_id") or "") + "|" + str(base.get("plataforma") or "") + "|" +
               str(base.get("publicado_em") or "") + "|" + str(base.get("titulo") or ""))[:180],
        "producao_id": base.get("producao_id") or "",
        "titulo": base.get("titulo") or "",
        "plataforma": base.get("plataforma") or "youtube",
        "publicado_em": int(base.get("publicado_em") or 0),
        "url": base.get("url") or "",
        "views": float(base.get("views") or 0),
        "likes": float(base.get("likes") or 0),
        "comments": float(base.get("comments") or 0),
        "shares": float(base.get("shares") or 0),
        "watch_time": float(base.get("watch_time") or 0),
        "receita": float(base.get("receita") or 0),
        "seguidores": float(base.get("seguidores") or 0),
        "atualizado": int(time.time()),
    }


def registrar(canal_id, canal_dir, base):
    d = carregar(canal_id, canal_dir)
    itens = d.setdefault("videos", [])
    novo = _registro(base)
    for i, antigo in enumerate(itens):
        if antigo.get("id") == novo["id"]:
            itens[i] = {**antigo, **{k: v for k, v in novo.items() if v not in ("", 0, 0.0)}}
            break
    else:
        itens.append(novo)
    gravar(canal_id, canal_dir, d)
    return novo


def importar(canal_id, canal_dir, texto, formato="auto"):
    texto = str(texto or "").strip()
    if not texto:
        raise ValueError("Cole o CSV ou o JSON exportado da plataforma.")
    registros = []
    if formato == "auto":
        formato = "json" if texto[:1] in "[{" else "csv"
    if formato == "json":
        d = json.loads(texto)
        lista = d if isinstance(d, list) else (d.get("videos") or d.get("items") or d.get("data") or [])
        registros = [_linha(x, _mapa(x.keys())) for x in lista if isinstance(x, dict)]
    else:
        try:
            dialeto = csv.Sniffer().sniff(texto[:4000], delimiters=",;\t")
        except csv.Error:
            dialeto = csv.excel
        leitor = csv.DictReader(io.StringIO(texto), dialect=dialeto)
        if not leitor.fieldnames:
            raise ValueError("O CSV não tem cabeçalho.")
        mapa = _mapa(leitor.fieldnames)
        if not mapa:
            raise ValueError("Não reconheci nenhuma coluna. Use cabeçalhos como data, plataforma, views, receita.")
        registros = [_linha(x, mapa) for x in leitor]
    registros = [r for r in registros if r.get("publicado_em") or r.get("views") or r.get("receita")]
    if not registros:
        raise ValueError("Nenhuma linha aproveitável encontrada.")
    d = carregar(canal_id, canal_dir)
    itens = d.setdefault("videos", [])
    indice = {x.get("id"): x for x in itens}
    novos = 0
    for r in registros:
        novo = _registro(r)
        if novo["id"] in indice:
            indice[novo["id"]].update({k: v for k, v in novo.items() if v not in ("", 0, 0.0)})
        else:
            itens.append(novo)
            indice[novo["id"]] = novo
            novos += 1
    gravar(canal_id, canal_dir, d)
    return {"importados": len(registros), "novos": novos, "total": len(itens)}


def _hora_local(ts):
    try:
        return time.localtime(int(ts)).tm_hour
    except Exception:
        return 12


def _dia_semana(ts):
    return time.localtime(int(ts)).tm_wday


def dashboard(canal_id, canal_dir, dias=30, canal=None):
    d = carregar(canal_id, canal_dir)
    videos = [v for v in (d.get("videos") or []) if isinstance(v, dict)]
    agora = int(time.time())
    corte = agora - max(1, int(dias)) * 86400
    janela = [v for v in videos if int(v.get("publicado_em") or 0) >= corte]
    base = janela or videos
    total = {
        "views": sum(float(v.get("views") or 0) for v in janela),
        "likes": sum(float(v.get("likes") or 0) for v in janela),
        "comments": sum(float(v.get("comments") or 0) for v in janela),
        "shares": sum(float(v.get("shares") or 0) for v in janela),
        "watch_time": sum(float(v.get("watch_time") or 0) for v in janela),
        "receita": sum(float(v.get("receita") or 0) for v in janela),
        "seguidores": sum(float(v.get("seguidores") or 0) for v in janela),
        "videos": len(janela),
    }
    total["engagement"] = round((total["likes"] + total["comments"] + total["shares"]) / total["views"], 4) \
        if total["views"] else 0

    serie = []
    for i in range(max(1, int(dias)) - 1, -1, -1):
        dia = datetime.fromtimestamp(agora - i * 86400).date()
        ini = int(datetime.combine(dia, datetime.min.time()).timestamp())
        fim = ini + 86400
        do_dia = [v for v in janela if ini <= int(v.get("publicado_em") or 0) < fim]
        serie.append({"dia": dia.isoformat(), "rotulo": "%d/%s" % (dia.day, MESES[dia.month - 1]),
                      "views": round(sum(float(v.get("views") or 0) for v in do_dia)),
                      "receita": round(sum(float(v.get("receita") or 0) for v in do_dia), 2)})

    plataformas = {}
    for v in janela:
        p = v.get("plataforma") or "youtube"
        x = plataformas.setdefault(p, {"views": 0, "receita": 0, "videos": 0, "likes": 0,
                                       "comments": 0, "shares": 0, "seguidores": 0})
        x["views"] += float(v.get("views") or 0)
        x["receita"] += float(v.get("receita") or 0)
        x["videos"] += 1
        x["likes"] += float(v.get("likes") or 0)
        x["comments"] += float(v.get("comments") or 0)
        x["shares"] += float(v.get("shares") or 0)
        x["seguidores"] += float(v.get("seguidores") or 0)
    for x in plataformas.values():
        x["engagement"] = round((x["likes"] + x["comments"] + x["shares"]) / x["views"], 4) if x["views"] else 0

    horas = []
    for h in range(24):
        do_h = [v for v in base if _hora_local(v.get("publicado_em")) == h]
        horas.append({"hora": h, "videos": len(do_h),
                      "views": round(sum(float(v.get("views") or 0) for v in do_h)),
                      "media": round(sum(float(v.get("views") or 0) for v in do_h) / len(do_h)) if do_h else 0})

    dias_semana = []
    for w in range(7):
        do_d = [v for v in base if _dia_semana(v.get("publicado_em")) == w]
        dias_semana.append({"dia": DIAS_SEMANA[w], "videos": len(do_d),
                            "views": round(sum(float(v.get("views") or 0) for v in do_d)),
                            "media": round(sum(float(v.get("views") or 0) for v in do_d) / len(do_d)) if do_d else 0})

    top = sorted(janela or videos, key=lambda v: float(v.get("views") or 0), reverse=True)[:10]
    top = [{"titulo": v.get("titulo") or "(sem título)", "plataforma": v.get("plataforma"),
            "views": round(float(v.get("views") or 0)), "receita": round(float(v.get("receita") or 0), 2),
            "url": v.get("url"), "data": int(v.get("publicado_em") or 0)} for v in top]

    melhores = sorted([h for h in horas if h["videos"]], key=lambda h: (h["media"], h["views"]), reverse=True)[:3]
    if melhores:
        sugestoes = ["%02d:00" % h["hora"] for h in melhores]
    else:
        sugestoes = list(((canal or {}).get("publicacao") or {}).get("horarios") or ["06:00", "12:00", "18:00"])[:3]

    meses = {}
    for v in videos:
        ts = int(v.get("publicado_em") or 0)
        if not ts:
            continue
        dt = datetime.fromtimestamp(ts)
        chave = "%04d-%02d" % (dt.year, dt.month)
        x = meses.setdefault(chave, {"mes": chave, "rotulo": "%s/%s" % (MESES[dt.month - 1], str(dt.year)[2:]),
                                     "receita": 0, "views": 0})
        x["receita"] += float(v.get("receita") or 0)
        x["views"] += float(v.get("views") or 0)
    serie_meses = [{"mes": x["mes"], "rotulo": x["rotulo"], "receita": round(x["receita"], 2),
                    "views": round(x["views"])} for x in sorted(meses.values(), key=lambda x: x["mes"])][-6:]

    meta_receita = float(((canal or {}).get("analytics") or {}).get("meta_receita") or 0)
    dados_em = 0
    for v in videos:
        dados_em = max(dados_em, int(v.get("atualizado") or 0))
    return {
        "dias": int(dias),
        "agora": agora,
        "tem_dados": bool(videos),
        "atualizado": dados_em,
        "total": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in total.items()},
        "meta_receita": meta_receita,
        "progresso_meta": round(total["receita"] / meta_receita, 4) if meta_receita else 0,
        "serie": serie,
        "por_plataforma": plataformas,
        "horas": horas,
        "dias_semana": dias_semana,
        "top": top,
        "melhores_horarios": sugestoes,
        "serie_meses": serie_meses,
        "total_historico": len(videos),
    }
