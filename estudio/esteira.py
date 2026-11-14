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

import asyncio
import broll
import canais
import legendas
import projeto

PAUSA = 0.35
FPS = 30
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
CACHE = Path(os.environ.get("ESTUDIO_CACHE") or (Path(__file__).resolve().parent.parent / "_cache"))
CACHE_IMAGENS = CACHE / "imagens"
CACHE_IMAGENS_ATIVO = os.environ.get("ESTUDIO_CACHE_IMAGENS", "1") != "0"
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


def preflight(producao, canal, callbacks, pasta):
    """Confere o essencial antes de ocupar a GPU e o VoiceStudio.

    Erro aqui vira mensagem na produção, não uma falha no meio da esteira depois de
    minutos de trabalho. A checagem é de propósito barata: não abre modelo, não fala
    com a ComfyUI, só olha arquivos, disco e callbacks.
    """
    faltas = []
    cenas = [c for c in (producao.get("plano") or {}).get("cenas") or [] if c.get("fala")]
    if not cenas:
        faltas.append("o roteiro não tem nenhuma cena com fala")
    formatos = [f for f in canais.formatos_ativos(canal)
                if f["id"] in (producao.get("formatos") or [])] or canais.formatos_ativos(canal)
    if not formatos:
        faltas.append("o canal não tem formato ativo")
    if not shutil.which(FFMPEG) and not Path(FFMPEG).is_file():
        faltas.append("ffmpeg não encontrado")
    if not callbacks.get("gerar_imagem"):
        faltas.append("gerador de imagem indisponível")
    if bool((canal.get("producao") or {}).get("falar_cenas", True)) and not callbacks.get("falar"):
        faltas.append("gerador de voz indisponível")
    pasta = Path(pasta)
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        teste = pasta / ".preflight"
        teste.write_text("ok", encoding="utf-8")
        teste.unlink()
    except OSError as exc:
        faltas.append("não consigo escrever na pasta da produção (%s)" % exc)
    try:
        livre = shutil.disk_usage(pasta).free
        if livre < 300 * 1024 * 1024:
            faltas.append("disco livre abaixo de 300 MB (%.0f MB)" % (livre / 1024 / 1024))
    except OSError:
        pass
    _etapa(producao, "preflight", "erro" if faltas else "ok", erro="; ".join(faltas)[:600])
    if faltas:
        producao["estado"] = "erro"
        producao["erro"] = "Antes de produzir: " + "; ".join(faltas)[:600]
        _log(producao, producao["erro"], callbacks)
        try:
            _gravar({"canal_id": producao["canal_id"], "id": producao["id"]}, producao)
        except Exception:
            pass
        return False
    return True


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
        "parte": int(plano.get("parte") or 0),
        "serie_id": plano.get("serie_id") or "",
        "estilo": plano.get("estilo") or (canal.get("producao") or {}).get("estilo") or "auto",
        "preset": canal.get("preset") or canal.get("playbook") or "",
        "preset_versao": int(canal.get("preset_versao") or 0),
        "planos": sum(len(c.get("planos") or []) for c in plano.get("cenas") or []),
        "movimento_cenas": sum(1 for c in plano.get("cenas") or []
                               if (c.get("movimento") or {}).get("ativo")),
        "legendas": plano.get("legendas"),
        "duracao_minima": int(plano.get("duracao_minima") or plano.get("duracao_alvo") or
                              (canal.get("producao") or {}).get("duracao_alvo") or 45),
        "imagens_por_formato": (canal.get("producao") or {}).get("imagens_por_formato") or "auto",
        "inspiracao": plano.get("inspiracao") or {},
        "etapas": {
            "preflight": {"estado": "pendente"},
            "voz": {"estado": "pendente", "feito": 0, "total": len(plano.get("cenas") or [])},
            "legendas": {"estado": "pendente", "feito": 0, "total": len(plano.get("cenas") or [])},
            "broll": {"estado": "pendente", "feito": 0, "total": len(plano.get("cenas") or [])},
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


def _codificar_video(entradas, grafo, destino, dur):
    """Codifica uma cena tentando libx264, depois o encoder do Mac e por fim mpeg4."""
    destino = Path(destino)
    erro = None
    for codec, extra in (("libx264", ["-crf", "20", "-preset", "fast"]),
                         ("h264_videotoolbox", ["-b:v", "6M"]),
                         ("mpeg4", ["-q:v", "3"])):
        tmp = destino.with_name(destino.stem + ".tmp" + destino.suffix)
        try:
            _rodar([FFMPEG, "-v", "error", "-y", *entradas, "-filter_complex", grafo,
                    "-map", "[saida]", "-t", "%.3f" % dur, "-r", str(FPS),
                    "-c:v", codec, *extra, str(tmp)], timeout=1800)
            os.replace(tmp, destino)
            return
        except Exception as exc:
            erro = exc
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass
    raise RuntimeError("não consegui codificar o vídeo: %s" % erro)


def _cache_imagem(chave, destino):
    """Copia uma imagem já gerada para a produção, se a chave existir no cache."""
    if not CACHE_IMAGENS_ATIVO:
        return False
    cache = CACHE_IMAGENS / (chave + ".png")
    if not cache.is_file() or cache.stat().st_size < 1000:
        return False
    try:
        tmp = Path(destino).with_name(Path(destino).name + ".tmp")
        shutil.copyfile(cache, tmp)
        os.replace(tmp, destino)
        return True
    except OSError:
        return False


def _guardar_cache_imagem(chave, origem):
    if not CACHE_IMAGENS_ATIVO:
        return
    try:
        CACHE_IMAGENS.mkdir(parents=True, exist_ok=True)
        cache = CACHE_IMAGENS / (chave + ".png")
        tmp = cache.with_name(cache.name + ".tmp")
        shutil.copyfile(origem, tmp)
        os.replace(tmp, cache)
    except OSError:
        pass


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


def _blocos_indices(frase, maximo=6):
    palavras = str(frase or "").split()
    blocos, atual, inicio = [], [], 0
    for i, p in enumerate(palavras):
        atual.append(p)
        fim = re.search(r"[.!?,:;]$", p)
        if len(atual) >= maximo or (fim and len(atual) >= 3):
            blocos.append((" ".join(atual), inicio, i))
            atual, inicio = [], i + 1
    if atual:
        if blocos and len(atual) <= 2:
            texto, ini, _ = blocos[-1]
            blocos[-1] = (texto + " " + " ".join(atual), ini, len(palavras) - 1)
        else:
            blocos.append((" ".join(atual), inicio, len(palavras) - 1))
    return blocos or [(str(frase or ""), 0, -1)]


def _luminancia(cor):
    def canal(v):
        v = max(0.0, min(1.0, float(v) / 255.0))
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (canal(x) for x in cor[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contraste(a, b):
    la, lb = _luminancia(a), _luminancia(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _cor_legivel(fundo, preferida):
    if _contraste(fundo, preferida) >= 4.5:
        return preferida
    branco, preto = (255, 255, 255), (0, 0, 0)
    return branco if _contraste(fundo, branco) >= _contraste(fundo, preto) else preto


def _legenda_png(texto, destino, largura_max, tamanho, estilo="bloco"):
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
    estilo = str(estilo or "bloco")
    if estilo == "limpa":
        fundo, texto_cor, contorno = None, (255, 255, 255, 255), 4
    elif estilo == "destaque":
        fundo, texto_cor, contorno = (0, 0, 0, 180), (255, 210, 63, 255), 2
    else:
        fundo, texto_cor, contorno = (0, 0, 0, 165), (255, 255, 255, 255), 3
    if fundo:
        texto_cor = (*_cor_legivel(fundo[:3], texto_cor[:3]), 255)
        d.rounded_rectangle((0, 0, larg - 1, alt - 1), radius=max(20, int(tamanho * 0.5)), fill=fundo)
    for i, linha in enumerate(linhas):
        w = d.textlength(linha, font=fonte)
        d.text(((larg - w) / 2, margem + i * altura_linha), linha, font=fonte,
               fill=texto_cor, stroke_width=contorno, stroke_fill=(0, 0, 0, 255))
    img.save(destino)
    return img.size


def _base_filtro(larg, alt, quadros, dentro, encaixe="cover", zoom_suave=True):
    l2, a2 = ((int(larg * 1.5), int(alt * 1.5)) if zoom_suave else (larg * 2, alt * 2))
    z = "min(zoom+0.0008,1.20)" if dentro else "if(eq(on,0),1.20,max(zoom-0.0008,1.0))"
    s_zoom = "%dx%d" % ((l2, a2) if zoom_suave else (larg, alt))
    fim = ("zoompan=z='%s':d=%d:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=%s:fps=%d"
           % (z, quadros, s_zoom, FPS))
    if zoom_suave:
        fim += ",scale=%d:%d:flags=lanczos" % (larg, alt)
    fim += "[v0]"
    if encaixe == "contain":
        return ("split=2[bg][fg];[bg]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,"
                "boxblur=36:8[bg2];[fg]scale=%d:%d:force_original_aspect_ratio=decrease[fg2];"
                "[bg2][fg2]overlay=(W-w)/2:(H-h)/2,%s" % (l2, a2, l2, a2, l2, a2, fim))
    return ("scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,%s"
            % (l2, a2, l2, a2, fim))


def _base_video_filtro(larg, alt, dur, encaixe="cover"):
    """Encaixa um clipe de vídeo no formato, com o último quadro congelado na pausa."""
    if encaixe == "contain":
        return ("split=2[bg][fg];[bg]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,"
                "boxblur=36:8[bg2];[fg]scale=%d:%d:force_original_aspect_ratio=decrease[fg2];"
                "[bg2][fg2]overlay=(W-w)/2:(H-h)/2,fps=%d,tpad=stop_mode=clone:stop_duration=%.3f,"
                "trim=duration=%.3f,setpts=PTS-STARTPTS,setsar=1[v0]"
                % (larg, alt, larg, alt, larg, alt, FPS, PAUSA + 0.5, dur))
    return ("scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,fps=%d,"
            "tpad=stop_mode=clone:stop_duration=%.3f,trim=duration=%.3f,"
            "setpts=PTS-STARTPTS,setsar=1[v0]"
            % (larg, alt, larg, alt, FPS, PAUSA + 0.5, dur))


def montar_video(pasta, plano, duracoes, formato, callbacks=None, imagens_dir=None, videos_por_cena=None):
    pasta = Path(pasta)
    larg = int(formato.get("largura") or 1080)
    alt = int(formato.get("altura") or 1920)
    fid = formato.get("id") or "video"
    legendas = bool(formato.get("legendas", False))
    encaixe = str(formato.get("encaixe") or "cover")
    transicao = str(formato.get("transicao") or "nenhuma")
    zoom_suave = bool(formato.get("zoom_suave", True))
    legenda_estilo = str(formato.get("legenda_estilo") or "bloco")
    legenda_posicao = str(formato.get("legenda_posicao") or "baixo")
    bgm = str(formato.get("bgm") or "")
    bgm_volume = float(formato.get("bgm_volume") or 0.12)
    tmp = pasta / "tmp" / fid
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    cenas = [c for c in (plano.get("cenas") or []) if c.get("fala")]
    origem = Path(imagens_dir) if imagens_dir else (pasta / "cenas")
    imagens = [origem / ("cena_%02d.png" % i) for i in range(1, len(cenas) + 1)]
    for i, img in enumerate(imagens, 1):
        if not img.is_file() and not (videos_por_cena or {}).get(i):
            raise RuntimeError("Faltam imagens: cena %d." % i)
    if len(duracoes) < len(cenas):
        raise RuntimeError("Faltam durações de fala.")
    vertical = alt >= larg
    tamanho = 70 if vertical else max(46, int(larg / 26))
    largura_max = int(larg * (0.84 if vertical else 0.72))
    if legenda_posicao == "cima":
        y_legenda = int(alt * 0.12)
    elif legenda_posicao == "centro":
        y_legenda = int(alt * 0.45)
    else:
        y_legenda = int(alt * (0.72 if vertical else 0.78))
    y_gancho = 80 if vertical else 60
    gancho = plano.get("gancho") or (cenas[0].get("fala") if cenas else "")
    clipes = []
    clipes_dir = pasta / "clipes" / fid
    clipes_dir.mkdir(parents=True, exist_ok=True)
    for i, cena in enumerate(cenas, 1):
        dur = float(duracoes[i - 1])
        fala_s = max(0.8, dur - PAUSA)
        clipe_fala = (videos_por_cena or {}).get(i)
        imagem_fonte = imagens[i - 1]
        arq_palavras = pasta / "voz" / ("palavras_%02d.json" % i)
        chave_clip = projeto.chave_clip(imagem_fonte, clipe_fala, cena.get("fala"), dur,
                                        larg, alt, legendas, gancho if i == 1 else "",
                                        projeto.hash_arquivo(arq_palavras),
                                        pasta / "voz" / ("voz_%02d.wav" % i),
                                        transicao, legenda_estilo, legenda_posicao)
        clipe = clipes_dir / ("clipe_%02d.mp4" % i)
        meta_clip = clipes_dir / ("clipe_%02d.json" % i)
        if (clipe.is_file() and clipe.stat().st_size > 1000
                and (not meta_clip.is_file() or projeto.meta_confere(meta_clip, chave_clip))):
            clipes.append(clipe)
            _log({}, "cena %d/%d reaproveitada" % (i, len(cenas)), callbacks)
            continue
        blocos_idx = _blocos_indices(cena.get("fala"))
        palavras = None
        if arq_palavras.is_file():
            try:
                palavras = json.loads(arq_palavras.read_text(encoding="utf-8"))
            except Exception:
                palavras = None
        if palavras and len(palavras) != len(str(cena.get("fala") or "").split()):
            palavras = None
        pesos = [max(1, len(b[0])) for b in blocos_idx]
        total = float(sum(pesos)) or 1.0
        t, janelas = 0.0, []
        if legendas:
            for j, (b, ini_i, fim_i) in enumerate(blocos_idx):
                if palavras and 0 <= ini_i <= fim_i < len(palavras):
                    ini = max(0.0, float(palavras[ini_i].get("inicio") or 0))
                    fim = min(dur, float(palavras[fim_i].get("fim") or ini) + 0.02)
                else:
                    ini = t
                    fim = min(dur, t + fala_s * pesos[j] / total)
                arq = tmp / ("leg_%02d_%02d.png" % (i, j))
                try:
                    _legenda_png(b, arq, largura_max, tamanho, legenda_estilo)
                    janelas.append((arq, ini, max(ini + 0.05, fim)))
                except Exception as exc:
                    _log({}, "legenda %d.%d falhou: %s" % (i, j, exc), callbacks)
                t = fim
        if i == 1 and gancho:
            arq = tmp / "gancho.png"
            try:
                _legenda_png(gancho, arq, largura_max, int(tamanho * 1.22), legenda_estilo)
                janelas.append((arq, 0.0, min(2.8, dur), True))
            except Exception:
                pass
        quadros = int(round(dur * FPS)) + 2
        if clipe_fala and Path(clipe_fala).is_file():
            entradas = ["-i", str(clipe_fala)]
            grafo = _base_video_filtro(larg, alt, dur, encaixe)
            _log({}, "cena %d com vídeo" % i, callbacks)
        else:
            entradas = ["-loop", "1", "-framerate", str(FPS), "-i", str(imagem_fonte)]
            grafo = _base_filtro(larg, alt, quadros, i % 2 == 1, encaixe, zoom_suave)
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
        fade = ""
        if transicao == "fade":
            fade = (",fade=t=in:st=0:d=0.25,fade=t=out:st=%.3f:d=0.25"
                    % max(0.0, dur - 0.25))
        grafo += ";[v%d]format=yuv420p%s[saida]" % (len(janelas), fade)
        _codificar_video(entradas, grafo, clipe, dur)
        projeto.gravar_meta(meta_clip, chave_clip)
        clipes.append(clipe)
        _log({}, "cena %d/%d montada (%s, %.1fs)" % (i, len(cenas), fid, dur), callbacks)
    lista = tmp / "lista.txt"
    lista.write_text("".join("file '%s'\n" % c.resolve().as_posix() for c in clipes), encoding="utf-8")
    junta = tmp / "video.mp4"
    _rodar([FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
            "-c", "copy", str(junta)], timeout=1800)
    saida = pasta / "saida" / ("final-%s.mp4" % fid)
    voz = pasta / "voz.wav"
    if not voz.is_file():
        raise RuntimeError("A narração não ficou pronta: falta voz.wav.")
    saida_tmp = saida.with_name(saida.stem + ".tmp" + saida.suffix)
    try:
        saida_tmp.unlink()
    except FileNotFoundError:
        pass
    simples = [FFMPEG, "-v", "error", "-y", "-i", str(junta), "-i", str(voz),
               "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
               "-shortest", "-movflags", "+faststart", str(saida_tmp)]
    bgm_path = Path(bgm).expanduser() if bgm else None
    if bgm_path and not bgm_path.is_absolute() and (pasta / bgm_path).is_file():
        bgm_path = pasta / bgm_path
    dur_total = sum(float(x) for x in duracoes)
    try:
        if bgm_path and bgm_path.is_file() and bgm_volume > 0:
            volume = max(0.0, min(1.0, bgm_volume))
            com_bgm = [FFMPEG, "-v", "error", "-y", "-i", str(junta), "-i", str(voz),
                       "-stream_loop", "-1", "-i", str(bgm_path),
                       "-filter_complex",
                       "[1:a]volume=1.0[voz];[2:a]volume=%.3f,afade=t=out:st=%.3f:d=2[bg];"
                       "[voz][bg]amix=inputs=2:duration=first:dropout_transition=0,alimiter=limit=0.95[a]"
                       % (volume, max(0.0, dur_total - 2)),
                       "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                       "-ar", "48000", "-ac", "2", "-shortest", "-movflags", "+faststart", str(saida_tmp)]
            try:
                _rodar(com_bgm, timeout=1800)
            except Exception as exc:
                _log({}, "música de fundo falhou (%s); seguindo sem música" % exc, callbacks)
                _rodar(simples, timeout=1800)
        else:
            _rodar(simples, timeout=1800)
        os.replace(saida_tmp, saida)
    except Exception:
        try:
            saida_tmp.unlink()
        except FileNotFoundError:
            pass
        raise
    return saida


def _fala_clip(imagem, voz, dur, larg, alt, legendas, tamanho, largura_max, y_legenda, tmp, idx, destino, fala="", callbacks=None):
    """Cena de narrador: imagem parada + voz + legenda queimada, já com áudio próprio."""
    quadros = int(round(dur * FPS)) + 2
    entradas = ["-loop", "1", "-framerate", str(FPS), "-i", str(imagem), "-i", str(voz)]
    grafo = _base_filtro(larg, alt, quadros, idx % 2 == 1)
    atual = "v0"
    k = 0
    janelas = []
    if legendas:
        blocos = _blocos(fala)
        pesos = [max(1, len(b)) for b in blocos]
        total = float(sum(pesos)) or 1.0
        fala_s = max(0.8, dur - PAUSA)
        t = 0.0
        for j, b in enumerate(blocos):
            ini = t
            fim = min(dur, t + fala_s * pesos[j] / total)
            arq = tmp / ("leg_not_%02d_%02d.png" % (idx, j))
            try:
                _legenda_png(b, arq, largura_max, tamanho)
                janelas.append((arq, ini, min(fim + 0.02, dur)))
            except Exception as exc:
                _log({}, "legenda da cena %d falhou: %s" % (idx + 1, exc), callbacks)
            t = fim
    for arq, ini, fim in janelas:
        k += 1
        entradas += ["-loop", "1", "-framerate", str(FPS), "-i", str(arq)]
        grafo += (";[%s][%d:v]overlay=x=(W-w)/2:y=%d:enable='between(t,%.3f,%.3f)'[v%d]"
                  % (atual, 1 + k, y_legenda, ini, fim, k))
        atual = "v%d" % k
    grafo += ";[%s]format=yuv420p[saida]" % atual
    grafo += (";[1:a]apad,atrim=0:%.3f,asetpts=PTS-STARTPTS,aresample=48000,"
              "aformat=channel_layouts=stereo[aout]" % dur)
    _rodar([FFMPEG, "-v", "error", "-y", *entradas, "-filter_complex", grafo,
            "-map", "[saida]", "-map", "[aout]", "-t", "%.3f" % dur, "-r", str(FPS),
            "-c:v", "libx264", "-crf", "20", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart", str(destino)], timeout=1800)
    return destino


def _normalizar_corte(origem, destino, larg, alt):
    vf = ("scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,setsar=1,fps=%d,format=yuv420p"
          % (larg, alt, larg, alt, FPS))
    _rodar([FFMPEG, "-v", "error", "-y", "-i", str(origem), "-vf", vf,
            "-c:v", "libx264", "-crf", "20", "-preset", "fast",
            "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart", str(destino)], timeout=1800)
    return destino


def _concatenar_clipes(tmp, clipes, saida, callbacks=None):
    lista = tmp / "lista_noticia.txt"
    lista.write_text("".join("file '%s'\n" % Path(c).name for c in clipes), encoding="utf-8")
    try:
        _rodar([FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
                "-c", "copy", str(saida)], cwd=str(tmp), timeout=1800)
        return saida
    except Exception as exc:
        _log({}, "concat por cópia falhou (%s); refazendo com re-encode" % str(exc)[:160], callbacks)
    _rodar([FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
            "-c:v", "libx264", "-crf", "20", "-preset", "fast", "-r", str(FPS), "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart", str(saida)], cwd=str(tmp), timeout=3600)
    return saida


async def montar_noticia(pasta, plano, formato, imagens_dir, duracoes, callbacks):
    """Junta falas do narrador (imagem + voz) e cortes do vídeo original (áudio próprio)."""
    pasta = Path(pasta)
    larg = int(formato.get("largura") or 1080)
    alt = int(formato.get("altura") or 1920)
    fid = formato.get("id") or "video"
    legendas = bool(formato.get("legendas", False))
    tmp = pasta / "tmp" / ("noticia-" + fid)
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    cenas = [c for c in (plano.get("cenas") or []) if c.get("tipo") in ("fala", "corte")]
    origem = Path(imagens_dir) if imagens_dir else (pasta / "cenas")
    vertical = alt >= larg
    tamanho = 70 if vertical else max(46, int(larg / 26))
    largura_max = int(larg * (0.84 if vertical else 0.72))
    y_legenda = int(alt * (0.72 if vertical else 0.78))
    cortar = (callbacks or {}).get("cortar")
    video_fonte = (callbacks or {}).get("video_fonte")
    if not cortar or not video_fonte:
        raise RuntimeError("Faltam os dados do vídeo de referência para montar a notícia.")
    ratio = canais.proporcao_de(formato)
    clipes = []
    for idx, cena in enumerate(cenas):
        clipe = tmp / ("clipe_%02d.mp4" % idx)
        if cena.get("tipo") == "corte":
            raw = tmp / ("corte_raw_%02d.mp4" % idx)
            try:
                await cortar(video_fonte, float(cena.get("inicio") or 0),
                             float(cena.get("fim") or 0), raw, ratio)
            except Exception as exc:
                raise RuntimeError("Falha ao cortar a cena %d: %s" % (idx + 1, str(exc)[:200]))
            _normalizar_corte(raw, clipe, larg, alt)
        else:
            imagem = origem / ("cena_%02d.png" % idx)
            voz = pasta / "voz" / ("voz_%02d.wav" % idx)
            if not imagem.is_file():
                raise RuntimeError("Falta a imagem da cena %d." % (idx + 1))
            if not voz.is_file():
                raise RuntimeError("Falta a voz da cena %d." % (idx + 1))
            dur = float((duracoes or {}).get(idx) or 0)
            if dur <= 0:
                raise RuntimeError("Falta a duração da cena %d." % (idx + 1))
            _fala_clip(imagem, voz, dur, larg, alt, legendas, tamanho, largura_max,
                       y_legenda, tmp, idx, clipe, cena.get("fala") or "", callbacks)
        clipes.append(clipe)
        _log({}, "cena %d/%d (%s)" % (idx + 1, len(cenas), fid), callbacks)
    if not clipes:
        raise RuntimeError("A notícia ficou sem cenas.")
    saida = pasta / "saida" / ("final-%s.mp4" % fid)
    saida.parent.mkdir(parents=True, exist_ok=True)
    _concatenar_clipes(tmp, clipes, saida, callbacks)
    return saida


async def produzir_noticia(producao, canal, callbacks):
    cid, pid = producao["canal_id"], producao["id"]
    pasta = canais.pasta_producao(cid, pid)
    plano = producao.get("plano") or {}
    cenas = [c for c in (plano.get("cenas") or []) if c.get("tipo") in ("fala", "corte")]
    falas = [(i, c) for i, c in enumerate(cenas) if c.get("tipo") == "fala"]
    producao["iniciado"] = int(time.time())
    producao["estado"] = "voz"
    _etapa(producao, "voz", "rodando", 0, len(falas))
    _gravar({"canal_id": cid, "id": pid}, producao)
    callbacks = callbacks or {}
    if not preflight(producao, canal, callbacks, pasta):
        return producao
    try:
        voz_dir = pasta / "voz"
        voz_dir.mkdir(parents=True, exist_ok=True)
        ajustes = {}
        vel = float((canal.get("voz") or {}).get("velocidade") or 1.0)
        if abs(vel - 1.0) > 0.01:
            ajustes["speed"] = vel
        voz_id = (canal.get("voz") or {}).get("voz_id") or None
        idioma = (canal.get("voz") or {}).get("idioma") or "pt"
        duracoes = {}
        feito = 0
        for idx, cena in falas:
            if _cancelado(producao, callbacks):
                producao["estado"] = "cancelado"
                _etapa(producao, "voz", "cancelado")
                _gravar({"canal_id": cid, "id": pid}, producao)
                return producao
            destino = voz_dir / ("voz_%02d.wav" % idx)
            if destino.is_file() and destino.stat().st_size > 1000:
                seg = _duracao_wav(destino)
            else:
                _log(producao, "voz %d/%d" % (feito + 1, len(falas)), callbacks)
                r = await callbacks["falar"](cena["fala"], destino, voz_id, idioma, ajustes)
                seg = float(r.get("segundos") or 0)
            if not seg:
                seg = max(0.8, len(str(cena["fala"]).split()) / 2.4)
            duracoes[idx] = seg + PAUSA
            feito += 1
            _etapa(producao, "voz", "rodando", feito, len(falas))
            _gravar({"canal_id": cid, "id": pid}, producao)
        _etapa(producao, "voz", "ok", len(falas), len(falas))
        producao["estado"] = "imagens"
        _gravar({"canal_id": cid, "id": pid}, producao)

        escolhidos = [f for f in canais.formatos_ativos(canal) if f["id"] in (producao.get("formatos") or [])]
        if not escolhidos:
            escolhidos = canais.formatos_ativos(canal)
        if not bool((canal.get("producao") or {}).get("legendas", False)):
            escolhidos = [dict(f, legendas=False) for f in escolhidos]
        grupos = canais.grupos_de_imagem(canal, escolhidos, producao.get("imagens_por_formato"))
        preset = (canal.get("producao") or {}).get("preset_imagem") or "z_image_turbo"
        qualidade = (canal.get("producao") or {}).get("qualidade") or "Normal"
        total_img = len(falas) * len(grupos)
        _etapa(producao, "imagens", "rodando", 0, total_img)
        _gravar({"canal_id": cid, "id": pid}, producao)
        visuais = {}
        for p in plano.get("personagens") or []:
            nome = str((p or {}).get("nome") or "").strip().lower()
            if nome:
                visuais[nome] = str((p or {}).get("visual") or "").strip()
        estilo_prompt = _estilo_com_inspiracao(canal, plano)
        producao["arquivos"]["imagens"] = []
        feito_img = 0
        for proporcao in grupos:
            cenas_dir = pasta / "cenas" / proporcao.replace(":", "x")
            cenas_dir.mkdir(parents=True, exist_ok=True)
            for idx, cena in falas:
                if _cancelado(producao, callbacks):
                    producao["estado"] = "cancelado"
                    _etapa(producao, "imagens", "cancelado")
                    _gravar({"canal_id": cid, "id": pid}, producao)
                    return producao
                destino = cenas_dir / ("cena_%02d.png" % idx)
                if not destino.is_file() or destino.stat().st_size < 1000:
                    _log(producao, "imagem %s %d/%d" % (proporcao, feito_img + 1, total_img), callbacks)
                    await callbacks["gerar_imagem"](
                        _prompt_com_personagem(cena, visuais, estilo_prompt),
                        proporcao, destino, preset, qualidade)
                feito_img += 1
                _etapa(producao, "imagens", "rodando", feito_img, total_img)
                _gravar({"canal_id": cid, "id": pid}, producao)
        _etapa(producao, "imagens", "ok", total_img, total_img)
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
            saida = await montar_noticia(pasta, plano, fmt, imagens_dir, duracoes, callbacks)
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
        _log(producao, "notícia montada. Aguardando aprovação para publicar.", callbacks)
    except Exception as exc:
        producao["estado"] = "erro"
        producao["erro"] = str(exc)[:600]
        _log(producao, "erro: " + str(exc)[:400], callbacks)
    _gravar({"canal_id": cid, "id": pid}, producao)
    return producao


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
    if not preflight(producao, canal, callbacks, pasta):
        return producao
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
        producao["reuso"] = {"voz": 0, "imagens": 0, "videos": 0, "montagens": 0, "broll": 0}
        duracoes, arquivos = [], []
        for i, cena in enumerate(cenas, 1):
            if _cancelado(producao, callbacks):
                producao["estado"] = "cancelado"
                _etapa(producao, "voz", "cancelado")
                _gravar({"canal_id": cid, "id": pid}, producao)
                return producao
            destino = voz_dir / ("voz_%02d.wav" % i)
            chave_v = projeto.chave_voz(cena, canal)
            meta_v = voz_dir / ("voz_%02d.json" % i)
            if falar_cenas:
                if (destino.is_file() and destino.stat().st_size > 1000
                        and (not meta_v.is_file() or projeto.meta_confere(meta_v, chave_v))):
                    seg = _duracao_wav(destino)
                    producao["reuso"]["voz"] += 1
                    if not meta_v.is_file() and seg:
                        projeto.gravar_meta(meta_v, chave_v, texto=cena.get("fala") or "", segundos=seg)
                else:
                    _log(producao, "voz %d/%d" % (i, len(cenas)), callbacks)
                    r = await callbacks["falar"](cena["fala"], destino, voz_id, idioma, ajustes)
                    seg = float(r.get("segundos") or 0)
                    if seg and destino.is_file():
                        projeto.gravar_meta(meta_v, chave_v, texto=cena.get("fala") or "", segundos=seg)
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
        quer_legendas = producao.get("legendas")
        if quer_legendas is None:
            quer_legendas = bool((canal.get("producao") or {}).get("legendas", False))
        if falar_cenas and quer_legendas:
            _etapa(producao, "legendas", "rodando", 0, len(cenas))
            for i, cena in enumerate(cenas, 1):
                arq_voz = voz_dir / ("voz_%02d.wav" % i)
                if arq_voz.is_file():
                    try:
                        palavras = legendas.alinhar(arq_voz, cena.get("fala") or "", idioma)
                        if palavras:
                            (voz_dir / ("palavras_%02d.json" % i)).write_text(
                                json.dumps(palavras, ensure_ascii=False, indent=1), encoding="utf-8")
                    except Exception as exc:
                        _log(producao, "alinhamento da cena %d falhou: %s" % (i, exc), callbacks)
                _etapa(producao, "legendas", "rodando", i, len(cenas))
                _gravar({"canal_id": cid, "id": pid}, producao)
            _etapa(producao, "legendas", "ok", len(cenas), len(cenas))
        else:
            _etapa(producao, "legendas", "ok", 0, 0)
        falas_video = {}
        if any(c.get("falar") for c in cenas):
            (pasta / "falas").mkdir(parents=True, exist_ok=True)
            if not falar_cenas:
                _log(producao, "narração desligada: as cenas com Falar seguem como imagem", callbacks)
            else:
                for i, cena in enumerate(cenas, 1):
                    if not cena.get("falar"):
                        continue
                    nome = str(cena.get("personagem") or "").strip()
                    retrato = _retrato_do_personagem(cid, nome) if nome else None
                    if not retrato:
                        _log(producao, "cena %d marcada como Falar, mas sem personagem/retrato; segue com a imagem" % i,
                             callbacks)
                        continue
                    destino_fala = pasta / "falas" / ("cena_%02d.mp4" % i)
                    meta_fala = pasta / "falas" / ("cena_%02d.json" % i)
                    voz_cena = pasta / "voz" / ("voz_%02d.wav" % i)
                    chave_fala = projeto.chave_fala(retrato, voz_cena)
                    if (destino_fala.is_file() and destino_fala.stat().st_size > 1000
                            and (not meta_fala.is_file() or projeto.meta_confere(meta_fala, chave_fala))):
                        falas_video[i] = destino_fala
                        producao["reuso"]["videos"] += 1
                        if not meta_fala.is_file():
                            projeto.gravar_meta(meta_fala, chave_fala)
                        continue
                    if not callbacks.get("falar_video"):
                        _log(producao, "motor de boca sincronizada indisponível; segue com a imagem", callbacks)
                        continue
                    try:
                        if not voz_cena.is_file():
                            raise RuntimeError("áudio da cena não encontrado")
                        _log(producao, "boca sincronizada %d/%d (%s)" % (i, len(cenas), nome), callbacks)
                        await callbacks["falar_video"](retrato, voz_cena, destino_fala, "1:1")
                        if destino_fala.is_file():
                            falas_video[i] = destino_fala
                            projeto.gravar_meta(meta_fala, chave_fala)
                    except Exception as exc:
                        _log(producao, "boca sincronizada da cena %d falhou: %s" % (i, exc), callbacks)
        producao["estado"] = "imagens"

        escolhidos = [f for f in canais.formatos_ativos(canal) if f["id"] in (producao.get("formatos") or [])]
        if not escolhidos:
            escolhidos = canais.formatos_ativos(canal)
        pr = canal.get("producao") or {}
        escolhidos = [dict(f,
            encaixe=pr.get("encaixe") or f.get("encaixe") or "cover",
            transicao=pr.get("transicao") or f.get("transicao") or "nenhuma",
            zoom_suave=pr.get("zoom_suave", f.get("zoom_suave", True)),
            legenda_estilo=pr.get("legenda_estilo") or f.get("legenda_estilo") or "bloco",
            legenda_posicao=pr.get("legenda_posicao") or f.get("legenda_posicao") or "baixo",
            bgm=pr.get("bgm") or f.get("bgm") or "",
            bgm_volume=pr.get("bgm_volume") if pr.get("bgm_volume") is not None else f.get("bgm_volume", 0.12),
            broll=pr.get("broll", f.get("broll", False)),
            broll_fonte=pr.get("broll_fonte") or f.get("broll_fonte") or "auto",
        ) for f in escolhidos]
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
        estilo_prompt = _estilo_com_inspiracao(canal, plano)
        broll_videos = {}
        fonte_broll = next((f.get("broll_fonte") for f in escolhidos if f.get("broll")), "auto")
        quer_broll = any(f.get("broll") for f in escolhidos)
        if quer_broll and broll.disponivel(fonte_broll):
            _etapa(producao, "broll", "rodando", 0, len(cenas))
            proporcao_broll = next(iter(grupos))
            broll_usados = set()
            for i, cena in enumerate(cenas, 1):
                if _cancelado(producao, callbacks):
                    producao["estado"] = "cancelado"
                    _etapa(producao, "broll", "cancelado")
                    _gravar({"canal_id": cid, "id": pid}, producao)
                    return producao
                termo = broll.termo_de_cena(cena)
                try:
                    arq = await asyncio.to_thread(broll.buscar, termo, proporcao_broll,
                                                  float(duracoes[i - 1]), fonte_broll)
                except Exception as exc:
                    arq = None
                    _log(producao, "b-roll da cena %d falhou: %s" % (i, exc), callbacks)
                if arq and arq in broll_usados:
                    arq = None
                if arq:
                    broll_usados.add(arq)
                    broll_videos[i] = arq
                    producao["reuso"]["broll"] += 1
                    _log(producao, "b-roll %d/%d: %s" % (i, len(cenas), Path(arq).name), callbacks)
                _etapa(producao, "broll", "rodando", i, len(cenas))
                _gravar({"canal_id": cid, "id": pid}, producao)
            _etapa(producao, "broll", "ok", len(cenas), len(cenas))
        else:
            if quer_broll:
                _log(producao, "B-roll ligado, mas sem chave Pexels/Pixabay; seguindo com imagens", callbacks)
            _etapa(producao, "broll", "ok", 0, 0)
        videos_por_cena = dict(falas_video)
        videos_por_cena.update(broll_videos)
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
                if i in broll_videos:
                    feito_img += 1
                    _etapa(producao, "imagens", "rodando", feito_img, total_imagens)
                    _gravar({"canal_id": cid, "id": pid}, producao)
                    continue
                destino = cenas_dir / ("cena_%02d.png" % i)
                nome_p = str(cena.get("personagem") or "").strip()
                ref = None
                if nome_p:
                    try:
                        retratos = canais.retratos(cid)
                        arq_ret = (retratos.get(nome_p)
                                   or {str(k).lower(): v for k, v in retratos.items()}.get(nome_p.lower()))
                        pasta_retratos = canais.pasta_retratos(cid)
                        if arq_ret and (pasta_retratos / arq_ret).is_file():
                            ref = pasta_retratos / arq_ret
                    except Exception:
                        ref = None
                prompt_cena = _prompt_com_personagem(cena, visuais, estilo_prompt)
                chave_i = projeto.chave_imagem(prompt_cena, proporcao, preset, qualidade, ref)
                meta_i = cenas_dir / ("cena_%02d.json" % i)
                if (destino.is_file() and destino.stat().st_size >= 1000
                        and (not meta_i.is_file() or projeto.meta_confere(meta_i, chave_i))):
                    producao["reuso"]["imagens"] += 1
                    if not meta_i.is_file():
                        projeto.gravar_meta(meta_i, chave_i, prompt=prompt_cena, proporcao=proporcao)
                elif _cache_imagem(chave_i, destino):
                    _log(producao, "imagem %s %d/%d do cache" % (proporcao, i, len(cenas)), callbacks)
                    producao["reuso"]["imagens"] += 1
                    projeto.gravar_meta(meta_i, chave_i, prompt=prompt_cena, proporcao=proporcao)
                else:
                    _log(producao, "imagem %s %d/%d" % (proporcao, i, len(cenas)), callbacks)
                    await callbacks["gerar_imagem"](prompt_cena, proporcao, destino, preset, qualidade,
                                                    referencia=ref, sujeito=nome_p,
                                                    visual=visuais.get(nome_p.lower(), ""))
                    if destino.is_file():
                        _guardar_cache_imagem(chave_i, destino)
                        projeto.gravar_meta(meta_i, chave_i, prompt=prompt_cena, proporcao=proporcao)
                producao["arquivos"]["imagens"].append(str(destino))
                feito_img += 1
                _etapa(producao, "imagens", "rodando", feito_img, total_imagens)
                _gravar({"canal_id": cid, "id": pid}, producao)
        _etapa(producao, "imagens", "ok", total_imagens, total_imagens)
        videos_movimento = {}
        cenas_mov = [i for i, c in enumerate(cenas, 1)
                     if (c.get("movimento") or {}).get("ativo")
                     and (c.get("movimento") or {}).get("modo") != "rapido"]
        if cenas_mov and callbacks.get("gerar_video"):
            (pasta / "videos").mkdir(parents=True, exist_ok=True)
            grupo_mov = "9:16" if "9:16" in grupos else next(iter(grupos))
            cenas_mov_dir = pasta / "cenas" / grupo_mov.replace(":", "x")
            for i in cenas_mov:
                if i in videos_por_cena:
                    continue
                if _cancelado(producao, callbacks):
                    producao["estado"] = "cancelado"
                    _etapa(producao, "imagens", "cancelado")
                    _gravar({"canal_id": cid, "id": pid}, producao)
                    return producao
                destino_mov = pasta / "videos" / ("cena_%02d.mp4" % i)
                imagem_mov = cenas_mov_dir / ("cena_%02d.png" % i)
                if not imagem_mov.is_file():
                    _log(producao, "movimento da cena %d sem imagem; segue parado" % i, callbacks)
                    continue
                mov = cenas[i - 1].get("movimento") or {}
                chave_vid = projeto.chave_video(imagem_mov, mov, grupo_mov)
                meta_vid = pasta / "videos" / ("cena_%02d.json" % i)
                if (destino_mov.is_file() and destino_mov.stat().st_size > 1000
                        and (not meta_vid.is_file() or projeto.meta_confere(meta_vid, chave_vid))):
                    videos_movimento[i] = destino_mov
                    producao["reuso"]["videos"] += 1
                    if not meta_vid.is_file():
                        projeto.gravar_meta(meta_vid, chave_vid, prompt=mov.get("prompt") or "")
                    continue
                try:
                    _log(producao, "movimento %d/%d" % (i, len(cenas_mov)), callbacks)
                    await callbacks["gerar_video"](imagem_mov, destino_mov,
                                                   mov.get("prompt") or "",
                                                   mov.get("duracao") or "2 s", grupo_mov)
                    if destino_mov.is_file():
                        videos_movimento[i] = destino_mov
                        projeto.gravar_meta(meta_vid, chave_vid, prompt=mov.get("prompt") or "")
                except Exception as exc:
                    _log(producao, "movimento da cena %d falhou: %s" % (i, exc), callbacks)
        for i, caminho in videos_movimento.items():
            videos_por_cena.setdefault(i, caminho)
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
            saida = pasta / "saida" / ("final-%s.mp4" % fmt["id"])
            chave_m = projeto.chave_montagem(producao, fmt, cenas, imagens_dir, videos_por_cena, voz_dir)
            meta_m = saida.with_suffix(".json")
            if (saida.is_file() and saida.stat().st_size > 1000
                    and (not meta_m.is_file() or projeto.meta_confere(meta_m, chave_m))):
                _log(producao, "montagem %s reaproveitada" % fmt.get("nome"), callbacks)
                producao["reuso"]["montagens"] += 1
                if not meta_m.is_file():
                    projeto.gravar_meta(meta_m, chave_m)
            else:
                saida = montar_video(pasta, plano, duracoes, fmt, callbacks, imagens_dir=imagens_dir,
                                     videos_por_cena=videos_por_cena)
                projeto.gravar_meta(meta_m, chave_m)
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
    try:
        projeto.gravar_projeto(producao, pasta)
    except Exception:
        pass
    _gravar({"canal_id": cid, "id": pid}, producao)
    return producao


def _duracao_wav(caminho):
    import wave
    try:
        with wave.open(str(caminho), "rb") as w:
            return w.getnframes() / float(w.getframerate() or 24000)
    except Exception:
        return None


def _retrato_do_personagem(cid, nome):
    try:
        retratos = canais.retratos(cid)
        arq = retratos.get(nome)
        if not arq:
            arq = next((v for k, v in retratos.items()
                        if str(k).lower() == str(nome or "").lower()), None)
        if arq:
            arq = canais.pasta_retratos(cid) / Path(arq).name
            if arq.is_file():
                return arq
    except Exception:
        pass
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


def _estilo_com_inspiracao(canal, plano):
    prompt = canais.estilo_de(canal, plano.get("estilo")).get("prompt") or ""
    insp = plano.get("inspiracao") or {}
    visual = str(insp.get("visual") or "").strip() if isinstance(insp, dict) else ""
    if visual:
        prompt = ((prompt.rstrip(", ") + ", ") if prompt else "") + visual
    return prompt


def _prompt_com_personagem(cena, visuais, estilo_prompt=""):
    prompt = str(cena.get("imagem") or cena.get("fala") or "")
    nome = str(cena.get("personagem") or "").strip().lower()
    visual = visuais.get(nome)
    if not visual and len(visuais) == 1:
        visual = next(iter(visuais.values()))
    if visual and visual.lower()[:24] not in prompt.lower():
        prompt = (visual + ", " + prompt).strip(", ")
    if estilo_prompt and estilo_prompt.lower()[:24] not in prompt.lower():
        prompt = (prompt.rstrip(", ") + ", " + estilo_prompt).strip(", ")
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
    alvos = [pasta / "cenas", pasta / "voz", pasta / "tmp", pasta / "clipes",
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
        "parte": producao.get("parte") or 0,
        "serie_id": producao.get("serie_id") or "",
        "estilo": producao.get("estilo") or "auto",
        "limpeza": producao.get("limpeza") or {},
        "reuso": producao.get("reuso") or {},
        "etapas": etapas,
        "progresso": int(round(100.0 * feito / total)) if total else (100 if producao.get("estado") == "concluido" else 0),
        "arquivos": producao.get("arquivos"),
    }
