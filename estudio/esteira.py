"""Esteira — do plano aprovado ao vídeo pronto, sem clique no meio.

Cada produção vive dentro da pasta do canal (`canais/<id>/producoes/<pid>/`), tem o seu
`producao.json` com o andamento e nunca entra no histórico de trabalhos do estúdio.
As etapas são as mesmas do canal.py, mas guiadas pelo plano: voz por cena, uma imagem por
cena, montagem em todos os formatos ativos do canal (16:9, 9:16, 1:1).

O trabalho pesado é feito por callbacks que o server injeta (falar, gerar_imagem), para
este módulo não depender do servidor nem do VoiceStudio diretamente.
"""
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import uuid
from pathlib import Path

import canais

PAUSA = 0.35
FPS = 30
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FONTES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def _log(producao, msg, callbacks=None):
    linha = time.strftime("%H:%M:%S") + "  " + str(msg)
    log = producao.setdefault("log", [])
    log.append(linha)
    del log[:-80]
    if callbacks and callbacks.get("log"):
        try:
            callbacks["log"](linha)
        except Exception:
            pass


def _gravar(p, producao):
    producao["atualizado"] = int(time.time())
    canais.gravar_producao(p["canal_id"], p["id"], producao)


def _cancelado(producao, callbacks):
    if producao.get("cancelar"):
        return True
    fn = (callbacks or {}).get("cancelado")
    return bool(fn and fn())


def _etapa(producao, nome, estado, feito=None, total=None, erro=""):
    e = producao.setdefault("etapas", {}).setdefault(nome, {})
    e["estado"] = estado
    if feito is not None:
        e["feito"] = feito
    if total is not None:
        e["total"] = total
    if erro:
        e["erro"] = erro
    return e


def criar(canal, plano, briefing, formato_ids=None):
    pid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    pasta = canais.pasta_producao(canal["id"], pid)
    (pasta / "voz").mkdir(parents=True, exist_ok=True)
    (pasta / "cenas").mkdir(parents=True, exist_ok=True)
    (pasta / "saida").mkdir(parents=True, exist_ok=True)
    (pasta / "roteiro.json").write_text(json.dumps(plano, ensure_ascii=False, indent=1), encoding="utf-8")
    (pasta / "narracao.txt").write_text(
        "\n".join(c.get("fala") or "" for c in plano.get("cenas") or []) + "\n", encoding="utf-8")
    (pasta / "cenas.txt").write_text(
        "\n".join(c.get("imagem") or "" for c in plano.get("cenas") or []) + "\n", encoding="utf-8")
    (pasta / "legendas.txt").write_text(
        "\n".join(c.get("fala") or "" for c in plano.get("cenas") or []) + "\n", encoding="utf-8")
    (pasta / "personagens.json").write_text(
        json.dumps(plano.get("personagens") or [], ensure_ascii=False, indent=1), encoding="utf-8")
    ativos = {f["id"] for f in canais.formatos_ativos(canal)}
    escolhidos = [f for f in (formato_ids or []) if f in ativos] or list(ativos)
    lista_formatos = [f for f in canais.formatos_ativos(canal) if f["id"] in escolhidos]
    reps = canais.formatos_distintos({"formatos": lista_formatos})
    producao = {
        "id": pid,
        "canal_id": canal["id"],
        "canal_nome": canal.get("nome") or "",
        "titulo": plano.get("titulo") or "Vídeo novo",
        "briefing": (briefing or "")[:4000],
        "criado": int(time.time()),
        "atualizado": int(time.time()),
        "iniciado": 0,
        "fim": 0,
        "estado": "preparando",
        "plano": plano,
        "formatos": escolhidos,
        "duracao_minima": int(plano.get("duracao_minima") or plano.get("duracao_alvo") or
                              (canal.get("producao") or {}).get("duracao_alvo") or 45),
        "imagens_por_formato": (canal.get("producao") or {}).get("imagens_por_formato") or "auto",
        "inspiracao": plano.get("inspiracao") or {},
        "etapas": {
            "voz": {"estado": "pendente", "feito": 0, "total": len(plano.get("cenas") or [])},
            "imagens": {"estado": "pendente", "feito": 0, "total": len(plano.get("cenas") or [])},
            "montagem": {"estado": "pendente", "feito": 0, "total": len(reps)},
        },
        "arquivos": {"voz": "", "imagens": [], "videos": {}},
        "log": [],
        "erro": "",
        "cancelar": False,
    }
    _gravar({"canal_id": canal["id"], "id": pid}, producao)
    return producao


def _sem_acento(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c))


def _rodar(cmd, cwd=None, timeout=3600):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout)
    if r.returncode:
        cauda = ((r.stderr or "") + (r.stdout or "")).strip()[-700:]
        raise RuntimeError("ffmpeg falhou: " + (cauda or "erro %d" % r.returncode))
    return r


def _fonte(tamanho):
    from PIL import ImageFont
    for f in FONTES:
        if Path(f).is_file():
            try:
                return ImageFont.truetype(f, tamanho)
            except Exception:
                continue
    return ImageFont.load_default()


def _quebrar(draw, texto, fonte, largura):
    linhas, atual = [], ""
    for palavra in str(texto or "").split():
        teste = (atual + " " + palavra).strip()
        if draw.textlength(teste, font=fonte) <= largura:
            atual = teste
        else:
            if atual:
                linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas or [""]


def _blocos(frase, maximo=6):
    palavras = str(frase or "").split()
    blocos, atual = [], []
    for p in palavras:
        atual.append(p)
        fim = re.search(r"[.!?,:;]$", p)
        if len(atual) >= maximo or (fim and len(atual) >= 3):
            blocos.append(" ".join(atual))
            atual = []
    if atual:
        if blocos and len(atual) <= 2:
            blocos[-1] += " " + " ".join(atual)
        else:
            blocos.append(" ".join(atual))
    return blocos or [str(frase or "")]


def _legenda_png(texto, destino, largura_max, tamanho):
    from PIL import Image, ImageDraw
    fonte = _fonte(tamanho)
    medidor = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    linhas = _quebrar(medidor, texto, fonte, largura_max)
    altura_linha = int(tamanho * 1.25)
    margem = max(18, int(tamanho * 0.4))
    larg = int(max(medidor.textlength(l, font=fonte) for l in linhas)) + 2 * margem + 8
    alt = altura_linha * len(linhas) + 2 * margem
    img = Image.new("RGBA", (larg, alt), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, larg - 1, alt - 1), radius=max(20, int(tamanho * 0.5)),
                        fill=(0, 0, 0, 165))
    for i, linha in enumerate(linhas):
        w = d.textlength(linha, font=fonte)
        d.text(((larg - w) / 2, margem + i * altura_linha), linha, font=fonte,
               fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))
    img.save(destino)
    return img.size


def _base_filtro(larg, alt, quadros, dentro):
    l2, a2 = larg * 2, alt * 2
    z = "min(zoom+0.0008,1.20)" if dentro else "if(eq(on,0),1.20,max(zoom-0.0008,1.0))"
    proporcao = larg / float(alt)
    if proporcao < 1.05:
        return (f"scale={l2}:{a2}:force_original_aspect_ratio=increase,crop={l2}:{a2},"
                f"zoompan=z='{z}':d={quadros}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"s={larg}x{alt}:fps={FPS}[v0]")
    return (f"split=2[bg][fg];[bg]scale={l2}:{a2}:force_original_aspect_ratio=increase,"
            f"crop={l2}:{a2},boxblur=36:8[bg2];[fg]scale={l2}:{a2}:"
            f"force_original_aspect_ratio=decrease[fg2];[bg2][fg2]overlay=(W-w)/2:(H-h)/2,"
            f"zoompan=z='{z}':d={quadros}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"s={larg}x{alt}:fps={FPS}[v0]")


def montar_video(pasta, plano, duracoes, formato, callbacks=None, imagens_dir=None):
    pasta = Path(pasta)
    larg = int(formato.get("largura") or 1080)
    alt = int(formato.get("altura") or 1920)
    fid = formato.get("id") or "video"
    legendas = bool(formato.get("legendas", True))
    tmp = pasta / "tmp" / fid
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    cenas = [c for c in (plano.get("cenas") or []) if c.get("fala")]
    origem = Path(imagens_dir) if imagens_dir else (pasta / "cenas")
    imagens = sorted(origem.glob("cena_*.png"))
    if len(imagens) < len(cenas):
        raise RuntimeError("Faltam imagens: %d de %d cenas." % (len(imagens), len(cenas)))
    if len(duracoes) < len(cenas):
        raise RuntimeError("Faltam durações de fala.")
    vertical = alt >= larg
    tamanho = 70 if vertical else max(46, int(larg / 26))
    largura_max = int(larg * (0.84 if vertical else 0.72))
    y_legenda = int(alt * (0.72 if vertical else 0.78))
    y_gancho = 80 if vertical else 60
    gancho = plano.get("gancho") or (cenas[0].get("fala") if cenas else "")
    clipes = []
    for i, cena in enumerate(cenas, 1):
        dur = float(duracoes[i - 1])
        fala_s = max(0.8, dur - PAUSA)
        blocos = _blocos(cena.get("fala"))
        pesos = [max(1, len(b)) for b in blocos]
        total = float(sum(pesos)) or 1.0
        t, janelas = 0.0, []
        if legendas:
            for j, b in enumerate(blocos):
                ini = t
                fim = min(dur, t + fala_s * pesos[j] / total)
                arq = tmp / ("leg_%02d_%02d.png" % (i, j))
                try:
                    _legenda_png(b, arq, largura_max, tamanho)
                    janelas.append((arq, ini, min(fim + 0.02, dur)))
                except Exception as exc:
                    _log({}, "legenda %d.%d falhou: %s" % (i, j, exc), callbacks)
                t = fim
        if i == 1 and gancho:
            arq = tmp / "gancho.png"
            try:
                _legenda_png(gancho, arq, largura_max, int(tamanho * 1.22))
                janelas.append((arq, 0.0, min(2.8, dur), True))
            except Exception:
                pass
        quadros = int(round(dur * FPS)) + 2
        entradas = ["-loop", "1", "-framerate", str(FPS), "-i", str(imagens[i - 1])]
        grafo = _base_filtro(larg, alt, quadros, i % 2 == 1)
        for k, j in enumerate(janelas, 1):
            arq, ini, fim = j[0], j[1], j[2]
            topo = len(j) > 3
            from PIL import Image
            try:
                w, h = Image.open(arq).size
            except Exception:
                w, h = int(larg * 0.8), 200
            y = y_gancho if topo else max(40, min(y_legenda, alt - h - 40))
            entradas += ["-i", str(arq)]
            grafo += (";[v%d][%d:v]overlay=x=(W-w)/2:y=%d:enable='between(t,%.3f,%.3f)'[v%d]"
                      % (k - 1, k, y, ini, fim, k))
        grafo += ";[v%d]format=yuv420p[saida]" % len(janelas)
        clipe = tmp / ("clipe_%02d.mp4" % i)
        _rodar([FFMPEG, "-v", "error", "-y", *entradas, "-filter_complex", grafo,
                "-map", "[saida]", "-t", "%.3f" % dur, "-r", str(FPS),
                "-c:v", "libx264", "-crf", "20", "-preset", "fast", str(clipe)], timeout=1800)
        clipes.append(clipe)
        _log({}, "cena %d/%d montada (%s, %.1fs)" % (i, len(cenas), fid, dur), callbacks)
    lista = tmp / "lista.txt"
    lista.write_text("".join("file '%s'\n" % c.name for c in clipes), encoding="utf-8")
    junta = tmp / "video.mp4"
    _rodar([FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
            "-c", "copy", str(junta)], timeout=1800)
    saida = pasta / "saida" / ("final-%s.mp4" % fid)
    voz = pasta / "voz.wav"
    if not voz.is_file():
        raise RuntimeError("A narração não ficou pronta: falta voz.wav.")
    _rodar([FFMPEG, "-v", "error", "-y", "-i", str(junta), "-i", str(voz),
            "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
            "-shortest", "-movflags", "+faststart", str(saida)], timeout=1800)
    return saida


async def produzir(producao, canal, callbacks):
    cid, pid = producao["canal_id"], producao["id"]
    pasta = canais.pasta_producao(cid, pid)
    plano = producao.get("plano") or {}
    cenas = [c for c in (plano.get("cenas") or []) if c.get("fala")]
    producao["iniciado"] = int(time.time())
    producao["estado"] = "voz"
    _etapa(producao, "voz", "rodando", 0, len(cenas))
    _gravar({"canal_id": cid, "id": pid}, producao)
    callbacks = callbacks or {}
    try:
        voz_dir = pasta / "voz"
        voz_dir.mkdir(parents=True, exist_ok=True)
        ajustes = {}
        vel = float((canal.get("voz") or {}).get("velocidade") or 1.0)
        if abs(vel - 1.0) > 0.01:
            ajustes["speed"] = vel
        voz_id = (canal.get("voz") or {}).get("voz_id") or None
        idioma = (canal.get("voz") or {}).get("idioma") or "pt"
        falar_cenas = bool((canal.get("producao") or {}).get("falar_cenas", True))
        duracoes, arquivos = [], []
        for i, cena in enumerate(cenas, 1):
            if _cancelado(producao, callbacks):
                producao["estado"] = "cancelado"
                _etapa(producao, "voz", "cancelado")
                _gravar({"canal_id": cid, "id": pid}, producao)
                return producao
            destino = voz_dir / ("voz_%02d.wav" % i)
            if falar_cenas:
                if destino.is_file() and destino.stat().st_size > 1000:
                    seg = _duracao_wav(destino)
                else:
                    _log(producao, "voz %d/%d" % (i, len(cenas)), callbacks)
                    r = await callbacks["falar"](cena["fala"], destino, voz_id, idioma, ajustes)
                    seg = float(r.get("segundos") or 0)
            else:
                seg = max(0.8, len(str(cena["fala"]).split()) / 2.4)
            if not seg:
                seg = max(0.8, len(str(cena["fala"]).split()) / 2.4)
            duracoes.append(seg + PAUSA)
            arquivos.append(destino)
            _etapa(producao, "voz", "rodando", i, len(cenas))
            _gravar({"canal_id": cid, "id": pid}, producao)
        if falar_cenas:
            _concatenar_voz(pasta, arquivos, duracoes)
        else:
            duracoes = _ajustar_duracoes(duracoes, producao.get("duracao_minima"))
            _silencio(pasta, duracoes)
        producao["arquivos"]["voz"] = str(pasta / "voz.wav")
        _etapa(producao, "voz", "ok", len(cenas), len(cenas))
        if falar_cenas:
            duracoes = _garantir_minimo_voz(pasta, duracoes, producao.get("duracao_minima"), callbacks)
        producao["estado"] = "imagens"

        escolhidos = [f for f in canais.formatos_ativos(canal) if f["id"] in (producao.get("formatos") or [])]
        if not escolhidos:
            escolhidos = canais.formatos_ativos(canal)
        quer_legendas = bool((canal.get("producao") or {}).get("legendas", True))
        if not quer_legendas:
            escolhidos = [dict(f, legendas=False) for f in escolhidos]
        grupos = canais.grupos_de_imagem(canal, escolhidos, producao.get("imagens_por_formato"))
        preset = (canal.get("producao") or {}).get("preset_imagem") or "z_image_turbo"
        qualidade = (canal.get("producao") or {}).get("qualidade") or "Normal"
        total_imagens = len(cenas) * len(grupos)
        _etapa(producao, "imagens", "rodando", 0, total_imagens)
        _gravar({"canal_id": cid, "id": pid}, producao)
        visuais = {}
        for p in plano.get("personagens") or []:
            nome = str((p or {}).get("nome") or "").strip().lower()
            if nome:
                visuais[nome] = str((p or {}).get("visual") or "").strip()
        feito_img = 0
        for proporcao in grupos:
            cenas_dir = pasta / "cenas" / proporcao.replace(":", "x")
            cenas_dir.mkdir(parents=True, exist_ok=True)
            for i, cena in enumerate(cenas, 1):
                if _cancelado(producao, callbacks):
                    producao["estado"] = "cancelado"
                    _etapa(producao, "imagens", "cancelado")
                    _gravar({"canal_id": cid, "id": pid}, producao)
                    return producao
                destino = cenas_dir / ("cena_%02d.png" % i)
                if not destino.is_file() or destino.stat().st_size < 1000:
                    _log(producao, "imagem %s %d/%d" % (proporcao, i, len(cenas)), callbacks)
                    await callbacks["gerar_imagem"](_prompt_com_personagem(cena, visuais),
                                                    proporcao, destino, preset, qualidade)
                producao["arquivos"]["imagens"].append(str(destino))
                feito_img += 1
                _etapa(producao, "imagens", "rodando", feito_img, total_imagens)
                _gravar({"canal_id": cid, "id": pid}, producao)
        _etapa(producao, "imagens", "ok", total_imagens, total_imagens)
        producao["estado"] = "montagem"
        _gravar({"canal_id": cid, "id": pid}, producao)

        distintos = canais.formatos_distintos({"formatos": escolhidos})
        _etapa(producao, "montagem", "rodando", 0, len(distintos))
        arquivo_por_chave = {}
        for i, fmt in enumerate(distintos, 1):
            if _cancelado(producao, callbacks):
                producao["estado"] = "cancelado"
                _etapa(producao, "montagem", "cancelado")
                _gravar({"canal_id": cid, "id": pid}, producao)
                return producao
            _log(producao, "montagem %s" % fmt.get("nome"), callbacks)
            proporcao = _proporcao_do_grupo(producao, fmt, grupos)
            imagens_dir = pasta / "cenas" / proporcao.replace(":", "x")
            saida = montar_video(pasta, plano, duracoes, fmt, callbacks, imagens_dir=imagens_dir)
            chave = canais.chave_formato(fmt)
            arquivo_por_chave[chave] = str(saida)
            producao["arquivos"]["videos"][fmt["id"]] = str(saida)
            _etapa(producao, "montagem", "rodando", i, len(distintos))
            _gravar({"canal_id": cid, "id": pid}, producao)
        for f in escolhidos:
            chave = canais.chave_formato(f)
            if chave in arquivo_por_chave:
                producao["arquivos"]["videos"][f["id"]] = arquivo_por_chave[chave]
        _etapa(producao, "montagem", "ok", len(distintos), len(distintos))
        producao["fim"] = int(time.time())
        producao["estado"] = "aguardando_aprovacao"
        _log(producao, "vídeo montado. Aguardando aprovação para publicar.", callbacks)
    except Exception as exc:
        producao["estado"] = "erro"
        producao["erro"] = str(exc)[:600]
        _log(producao, "erro: " + str(exc)[:400], callbacks)
    _gravar({"canal_id": cid, "id": pid}, producao)
    return producao


def _duracao_wav(caminho):
    import wave
    try:
        with wave.open(str(caminho), "rb") as w:
            return w.getnframes() / float(w.getframerate() or 24000)
    except Exception:
        return None


def _concatenar_voz(pasta, arquivos, duracoes):
    pasta = Path(pasta)
    pausa = pasta / "pausa.wav"
    _rodar([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
            "-t", str(PAUSA), str(pausa)], timeout=120)
    lista = pasta / "lista_voz.txt"
    linhas = []
    for a in arquivos:
        rel = Path(a).resolve().relative_to(pasta.resolve()).as_posix()
        linhas.append("file '%s'\nfile '%s'\n" % (rel, pausa.resolve().relative_to(pasta.resolve()).as_posix()))
    lista.write_text("".join(linhas), encoding="utf-8")
    _rodar([FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
            "-c:a", "pcm_s16le", str(pasta / "voz.wav")], cwd=str(pasta), timeout=600)
    (pasta / "duracoes.txt").write_text("\n".join("%.3f" % d for d in duracoes) + "\n", encoding="utf-8")


def _silencio(pasta, duracoes):
    """Canal sem narração: o vídeo sai mudo, mas com a duração que o texto pediria."""
    pasta = Path(pasta)
    total = max(1.0, float(sum(duracoes)))
    _rodar([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
            "-t", "%.3f" % total, "-c:a", "pcm_s16le", str(pasta / "voz.wav")], timeout=120)
    (pasta / "duracoes.txt").write_text("\n".join("%.3f" % d for d in duracoes) + "\n", encoding="utf-8")


def _prompt_com_personagem(cena, visuais):
    prompt = str(cena.get("imagem") or cena.get("fala") or "")
    nome = str(cena.get("personagem") or "").strip().lower()
    visual = visuais.get(nome)
    if not visual and len(visuais) == 1:
        visual = next(iter(visuais.values()))
    if visual and visual.lower()[:24] not in prompt.lower():
        return (visual + ", " + prompt).strip(", ")
    return prompt


def _proporcao_do_grupo(producao, fmt, grupos):
    modo = producao.get("imagens_por_formato") or "auto"
    if modo in ("9:16", "16:9", "1:1") and modo in grupos:
        return modo
    if modo == "unico":
        return next(iter(grupos))
    p = canais.proporcao_de(fmt)
    return p if p in grupos else next(iter(grupos))


def _ajustar_duracoes(duracoes, minimo):
    d = list(duracoes or [])
    try:
        minimo = float(minimo or 0)
    except (TypeError, ValueError):
        minimo = 0.0
    total = sum(d)
    if minimo and d and total < minimo:
        d[-1] += minimo - total
    return d


def _garantir_minimo_voz(pasta, duracoes, minimo, callbacks=None):
    """A duração alvo é um piso: se a fala sair menor, o último quadro segura até o mínimo."""
    d = _ajustar_duracoes(duracoes, minimo)
    falta = sum(d) - sum(duracoes)
    if falta <= 0.01:
        return d
    p = Path(pasta)
    sil = p / "silencio_final.wav"
    _rodar([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
            "-t", "%.3f" % falta, "-c:a", "pcm_s16le", str(sil)], timeout=120)
    lista = p / "lista_final.txt"
    lista.write_text("file 'voz.wav'\nfile 'silencio_final.wav'\n", encoding="utf-8")
    tmp = p / "voz_com_minimo.wav"
    _rodar([FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
            "-c:a", "pcm_s16le", str(tmp)], cwd=str(p), timeout=600)
    tmp.replace(p / "voz.wav")
    (p / "duracoes.txt").write_text("\n".join("%.3f" % x for x in d) + "\n", encoding="utf-8")
    _log({}, "duração ajustada para o mínimo de %.1f s" % sum(d), callbacks)
    return d


def _tamanho_arvore(p):
    total = 0
    try:
        if p.is_file():
            return p.stat().st_size
        for x in p.rglob("*"):
            if x.is_file():
                total += x.stat().st_size
    except OSError:
        pass
    return total


def limpar_brutos(pasta):
    """Depois da aprovação, deixa só os vídeos, os personagens e os metadados.

    Some com imagens, vozes por cena, áudio juntado, temporários e textos intermediários.
    `producao.json` e `personagens.json` ficam: são pequenos e mantêm o histórico do canal.
    """
    pasta = Path(pasta)
    alvos = [pasta / "cenas", pasta / "voz", pasta / "tmp",
             pasta / "voz.wav", pasta / "pausa.wav", pasta / "silencio_final.wav",
             pasta / "voz_com_minimo.wav", pasta / "lista_voz.txt", pasta / "lista_final.txt",
             pasta / "duracoes.txt", pasta / "roteiro.json", pasta / "narracao.txt",
             pasta / "cenas.txt", pasta / "legendas.txt"]
    liberado = 0
    for alvo in alvos:
        if not alvo.exists():
            continue
        liberado += _tamanho_arvore(alvo)
        try:
            if alvo.is_dir():
                shutil.rmtree(alvo, ignore_errors=True)
            else:
                alvo.unlink()
        except OSError as exc:
            print("[esteira] não consegui apagar %s: %s" % (alvo, exc), flush=True)
    return liberado


def resumo(producao):
    etapas = producao.get("etapas") or {}
    total = feito = 0
    for e in etapas.values():
        total += int(e.get("total") or 0)
        feito += int(e.get("feito") or 0)
    return {
        "id": producao.get("id"),
        "titulo": producao.get("titulo"),
        "estado": producao.get("estado"),
        "criado": producao.get("criado"),
        "fim": producao.get("fim"),
        "erro": producao.get("erro"),
        "legenda": (producao.get("plano") or {}).get("legenda") or "",
        "hashtags": (producao.get("plano") or {}).get("hashtags") or [],
        "duracao_minima": producao.get("duracao_minima"),
        "limpeza": producao.get("limpeza") or {},
        "etapas": etapas,
        "progresso": int(round(100.0 * feito / total)) if total else (100 if producao.get("estado") == "concluido" else 0),
        "arquivos": producao.get("arquivos"),
    }
