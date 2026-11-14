"""Manifesto e reaproveitamento de uma produção do Canais.

Cada asset guarda um sidecar com a chave das entradas que o geraram. Se a fala, o
prompt, o preset, a referência ou o formato mudarem, a chave muda e só aquele asset
é refeito. O vídeo final também tem uma chave, então uma produção sem mudanças não
remonta nada.
"""

import hashlib
import json
import os
import time
from pathlib import Path


def hash_arquivo(caminho):
    if not caminho:
        return ""
    p = Path(caminho)
    if not p.is_file():
        return ""
    h = hashlib.sha256()
    try:
        with p.open("rb") as f:
            for bloco in iter(lambda: f.read(1024 * 1024), b""):
                h.update(bloco)
    except OSError:
        return ""
    return h.hexdigest()


def hash_texto(texto):
    return hashlib.sha256(str(texto or "").encode("utf-8")).hexdigest()


def _hash_json(dados):
    return hash_texto(json.dumps(dados, ensure_ascii=False, sort_keys=True))


def _ler(arq, padrao=None):
    try:
        return json.loads(Path(arq).read_text(encoding="utf-8"))
    except Exception:
        return padrao


def _gravar(arq, dados):
    arq = Path(arq)
    arq.parent.mkdir(parents=True, exist_ok=True)
    tmp = arq.with_name(arq.name + ".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, arq)


def chave_voz(cena, canal):
    voz = canal.get("voz") or {}
    return _hash_json({
        "texto": cena.get("fala") or "",
        "voz_id": voz.get("voz_id") or "",
        "idioma": voz.get("idioma") or "pt",
        "velocidade": float(voz.get("velocidade") or 1.0),
    })


def chave_imagem(prompt, proporcao, preset, qualidade, referencia=None):
    return _hash_json({
        "prompt": str(prompt or ""),
        "proporcao": str(proporcao or ""),
        "preset": str(preset or ""),
        "qualidade": str(qualidade or ""),
        "referencia": hash_arquivo(referencia) if referencia else "",
    })


def chave_fala(retrato, voz, formato="1:1"):
    return _hash_json({
        "retrato": hash_arquivo(retrato),
        "voz": hash_arquivo(voz),
        "formato": str(formato or "1:1"),
    })


def chave_video(imagem, movimento, formato):
    mov = movimento or {}
    return _hash_json({
        "imagem": hash_arquivo(imagem),
        "prompt": str(mov.get("prompt") or ""),
        "duracao": str(mov.get("duracao") or "2 s"),
        "formato": str(formato or ""),
    })


def chave_clip(imagem, video, fala, dur, larg, alt, legendas, gancho, palavras, voz=None,
               transicao="nenhuma", legenda_estilo="bloco", legenda_posicao="baixo"):
    return _hash_json({
        "imagem": hash_arquivo(imagem),
        "video": hash_arquivo(video) if video else "",
        "fala": str(fala or ""),
        "dur": round(float(dur), 3),
        "larg": int(larg),
        "alt": int(alt),
        "legendas": bool(legendas),
        "gancho": str(gancho or ""),
        "palavras": str(palavras or ""),
        "voz": hash_arquivo(voz) if voz else "",
        "transicao": str(transicao or "nenhuma"),
        "legenda_estilo": str(legenda_estilo or "bloco"),
        "legenda_posicao": str(legenda_posicao or "baixo"),
    })


def chave_montagem(producao, fmt, cenas, imagens_dir, videos_por_cena, voz_dir):
    dados = {
        "formato": {k: fmt.get(k) for k in (
            "id", "largura", "altura", "legendas", "encaixe", "transicao", "zoom_suave",
            "legenda_estilo", "legenda_posicao", "bgm", "bgm_volume")},
        "gancho": (producao.get("plano") or {}).get("gancho") or "",
        "cenas": [],
    }
    for i, cena in enumerate(cenas, 1):
        img = Path(imagens_dir) / ("cena_%02d.png" % i)
        voz = Path(voz_dir) / ("voz_%02d.wav" % i)
        vid = (videos_por_cena or {}).get(i)
        dados["cenas"].append({
            "fala": cena.get("fala") or "",
            "imagem": hash_arquivo(img),
            "voz": hash_arquivo(voz),
            "video": hash_arquivo(vid) if vid else "",
        })
    return _hash_json(dados)


def meta_confere(arq, chave):
    d = _ler(arq, {})
    return bool(d and d.get("chave") == chave)


def gravar_meta(arq, chave, **dados):
    _gravar(arq, {"chave": chave, "quando": int(time.time()), **dados})


def manifesto(producao, pasta, formatos=None):
    pasta = Path(pasta)
    cenas = [c for c in (producao.get("plano") or {}).get("cenas") or [] if c.get("fala")]
    itens = []
    for i, cena in enumerate(cenas, 1):
        voz = pasta / "voz" / ("voz_%02d.wav" % i)
        item = {
            "n": i,
            "fala": cena.get("fala") or "",
            "imagem": cena.get("imagem") or "",
            "personagem": cena.get("personagem") or "",
            "movimento": cena.get("movimento") or {},
            "voz": {"arquivo": str(voz) if voz.is_file() else "",
                    "hash": hash_arquivo(voz)},
            "imagens": {},
            "video": "",
        }
        for d in sorted((pasta / "cenas").glob("*")):
            img = d / ("cena_%02d.png" % i)
            if img.is_file():
                item["imagens"][d.name] = {"arquivo": str(img), "hash": hash_arquivo(img)}
        vid = pasta / "videos" / ("cena_%02d.mp4" % i)
        if vid.is_file():
            item["video"] = {"arquivo": str(vid), "hash": hash_arquivo(vid)}
        itens.append(item)
    saidas = {}
    for arq in sorted((pasta / "saida").glob("final-*.mp4")):
        saidas[arq.stem.replace("final-", "")] = {"arquivo": str(arq), "hash": hash_arquivo(arq)}
    return {
        "id": producao.get("id"),
        "canal_id": producao.get("canal_id"),
        "titulo": producao.get("titulo") or "",
        "atualizado": int(time.time()),
        "formatos": list(producao.get("formatos") or []),
        "preset": producao.get("preset") or "",
        "preset_versao": producao.get("preset_versao") or 0,
        "cenas": itens,
        "saidas": saidas,
        "reuso": producao.get("reuso") or {},
    }


def planejar(producao, pasta, formatos=None):
    """Diz o que já existe e o que seria refeito, sem gerar nada."""
    pasta = Path(pasta)
    cenas = [c for c in (producao.get("plano") or {}).get("cenas") or [] if c.get("fala")]
    plano = {"cenas": [], "saidas": [], "reuso": producao.get("reuso") or {}}
    for i, cena in enumerate(cenas, 1):
        voz = pasta / "voz" / ("voz_%02d.wav" % i)
        item = {"n": i, "fala": cena.get("fala") or "", "voz": voz.is_file(),
                "imagens": {}, "video": (pasta / "videos" / ("cena_%02d.mp4" % i)).is_file()}
        for d in sorted((pasta / "cenas").glob("*")):
            item["imagens"][d.name] = (d / ("cena_%02d.png" % i)).is_file()
        plano["cenas"].append(item)
    for arq in sorted((pasta / "saida").glob("final-*.mp4")):
        plano["saidas"].append(arq.stem.replace("final-", ""))
    return plano


def gravar_projeto(producao, pasta, formatos=None):
    dados = manifesto(producao, pasta, formatos)
    _gravar(Path(pasta) / "projeto.json", dados)
    return dados
