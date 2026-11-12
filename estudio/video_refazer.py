"""Vídeo de referência — baixar, transcrever, refazer e cortar.

Serve para duas coisas:
  1. Refazer: mantém o texto falado e reimagina voz, imagens e montagem.
  2. Cortes: escolhe melhores momentos e transforma em clipes verticais legendados.

Só use URL de vídeo próprio ou com permissão. O módulo não decide direitos autorais por
você; ele apenas baixa, transcreve e corta o que foi mandado.
"""
import json
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import uuid
from pathlib import Path

import canais
import roteirista
import esteira

_MODELO = None


def _sem_acento(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c))


def _slug(s, limite=48):
    s = re.sub(r"[^a-z0-9]+", "-", _sem_acento(s).lower()).strip("-")
    return s[:limite] or "video"


def _ffmpeg():
    return shutil.which("ffmpeg") or "ffmpeg"


def baixar_video(url, pasta, altura=1080):
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / "fonte.%(ext)s"
    cmd = [sys.executable, "-m", "yt_dlp", "--no-playlist", "--no-warnings",
           "--force-overwrites", "-o", str(destino),
           "-f", "bv*[height<=%d][ext=mp4]+ba[ext=m4a]/b[height<=%d]/b" % (altura, altura),
           "--merge-output-format", "mp4"]
    ff = shutil.which("ffmpeg")
    if ff:
        cmd += ["--ffmpeg-location", ff]
    cmd.append(url)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    except subprocess.TimeoutExpired:
        raise RuntimeError("O download passou de 30 minutos. Use um vídeo menor ou baixe à mão.")
    if r.returncode:
        cauda = ((r.stderr or "") + (r.stdout or "")).strip()[-500:]
        raise RuntimeError("Não consegui baixar o vídeo. " + (cauda or "yt-dlp falhou."))
    arquivos = sorted(pasta.glob("fonte.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not arquivos:
        raise RuntimeError("O download terminou, mas o arquivo não apareceu.")
    return arquivos[0]


def extrair_audio(video, pasta):
    audio = Path(pasta) / "audio.wav"
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
                    str(audio)], check=True, timeout=900)
    return audio


def transcrever(audio, idioma="pt"):
    global _MODELO
    from faster_whisper import WhisperModel
    if _MODELO is None:
        _MODELO = WhisperModel("small", device="cpu", compute_type="int8")
    segmentos, _ = _MODELO.transcribe(str(audio), language=idioma or None, beam_size=1,
                                      vad_filter=False, condition_on_previous_text=True)
    saida = []
    for s in segmentos:
        txt = str(getattr(s, "text", "") or "").strip()
        if not txt:
            continue
        saida.append({"inicio": round(float(s.start), 2), "fim": round(float(s.end), 2), "texto": txt})
    return saida


def texto_de(segmentos):
    return " ".join(s["texto"] for s in segmentos).strip()


def _blocos_para_cenas(segmentos, alvo=8.0, maximo=12.0):
    blocos, atual = [], []
    inicio = None
    for s in segmentos:
        if inicio is None:
            inicio = s["inicio"]
        atual.append(s)
        if s["fim"] - inicio >= alvo or (s["fim"] - inicio >= 4 and re.search(r"[.!?]$", s["texto"])):
            blocos.append({"inicio": inicio, "fim": s["fim"],
                           "texto": " ".join(x["texto"] for x in atual).strip()})
            atual, inicio = [], None
    if atual:
        blocos.append({"inicio": inicio or atual[0]["inicio"], "fim": atual[-1]["fim"],
                       "texto": " ".join(x["texto"] for x in atual).strip()})
    return blocos


def plano_do_texto(canal, contexto, segmentos, estilo=None, parte=0, serie_id=""):
    """Mantém o texto falado e troca voz, imagens e montagem."""
    blocos = _blocos_para_cenas(segmentos)
    if not blocos:
        raise ValueError("A transcrição ficou vazia.")
    est = canais.estilo_de(canal, estilo)
    cenas = []
    for i, b in enumerate(blocos, 1):
        fala = b["texto"]
        imagem = roteirista._imagem_de_apoio(contexto, fala)
        if est.get("prompt"):
            imagem += ", " + est["prompt"]
        cenas.append({"n": i, "fala": fala, "imagem": imagem, "personagem": ""})
    total = max(15.0, sum(max(0.5, b["fim"] - b["inicio"]) for b in blocos))
    texto = texto_de(segmentos)
    return {
        "titulo": (texto[:70] + ("…" if len(texto) > 70 else "")) or "Vídeo refeito",
        "gancho": blocos[0]["texto"][:300],
        "publico_alvo": contexto.get("publico") or "",
        "tom": contexto.get("tom") or "",
        "duracao_estimada": round(total, 1),
        "duracao_alvo": round(total, 1),
        "duracao_minima": round(total, 1),
        "estilo": est.get("id") or "auto",
        "parte": int(parte or 0),
        "serie_id": serie_id or "",
        "personagens": [dict(p) for p in (contexto.get("personagens") or [])],
        "cenas": cenas,
        "legenda": texto[:2000],
        "hashtags": list(contexto.get("hashtags") or []),
        "cta": contexto.get("chamada_final") or "",
        "observacoes": "Texto original mantido; voz, imagens e montagem refeitas.",
        "motor": "refazer-texto",
        "canal_id": canal.get("id"),
        "criado": time.time(),
    }


async def plano_melhorado(pedir_texto, canal, contexto, segmentos, instrucoes="", estilo=None, fiel=False):
    texto = texto_de(segmentos)
    if len(texto) > 11000:
        texto = texto[:11000]
    regra = ("Mantenha o texto o mais fiel possível; aplique APENAS as instruções pontuais, "
             "sem reescrever o resto." if fiel else
             "Reescreva mantendo o conteúdo e as ideias, melhorando ritmo, clareza e gancho.")
    pedido = ("%s Não invente fato novo.\n\nINSTRUÇÕES PONTUAIS:\n%s\n\nTEXTO:\n%s"
              % (regra, instrucoes or "nenhuma", texto))
    plano = await roteirista.gerar_plano(pedir_texto, canal, contexto, pedido,
                                         duracao=max(20, int(len(texto.split()) / 2.4)),
                                         estilo=estilo)
    return plano


def _srt_time(seg):
    seg = max(0.0, float(seg))
    h = int(seg // 3600)
    m = int((seg % 3600) // 60)
    s = seg % 60
    return ("%02d:%02d:%06.3f" % (h, m, s)).replace(".", ",")


def _srt(segmentos, inicio, fim, destino):
    linhas = []
    n = 1
    for s in segmentos:
        a, b = max(inicio, s["inicio"]), min(fim, s["fim"])
        if b - a < 0.25:
            continue
        linhas.append("%d\n%s --> %s\n%s\n" % (n, _srt_time(a - inicio), _srt_time(b - inicio), s["texto"]))
        n += 1
    Path(destino).write_text("\n".join(linhas), encoding="utf-8")
    return Path(destino)


def cortar(video, inicio, fim, destino, segmentos, formato="9:16"):
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.parent / ("tmp-" + destino.stem)
    tmp.mkdir(parents=True, exist_ok=True)
    dur = max(1.0, fim - inicio)
    vertical = formato == "9:16"
    W, H = (1080, 1920) if vertical else (1920, 1080)
    tamanho = 60 if vertical else 48
    largura_max = int(W * (0.84 if vertical else 0.72))
    y = H - 130 if vertical else H - 80

    janelas = []
    for s in segmentos:
        a, b = max(inicio, s["inicio"]), min(fim, s["fim"])
        if b - a < 0.25:
            continue
        blocos = esteira._blocos(s["texto"])
        pesos = [max(1, len(x)) for x in blocos]
        total = float(sum(pesos)) or 1.0
        t = a
        for blk, peso in zip(blocos, pesos):
            f = t + (b - a) * peso / total
            janelas.append((blk, t - inicio, max(t - inicio + 0.02, f - inicio)))
            t = f

    pngs = []
    for i, (texto, _, _) in enumerate(janelas):
        png = tmp / ("leg%02d.png" % i)
        try:
            w, h = esteira._legenda_png(texto, png, largura_max, tamanho)
            pngs.append((png, janelas[i][1], janelas[i][2], h))
        except Exception:
            pngs = []
            break

    if pngs:
        cmd = [_ffmpeg(), "-v", "error", "-y", "-ss", "%.3f" % inicio, "-t", "%.3f" % dur,
               "-i", str(video)]
        for png, _, _, _ in pngs:
            cmd += ["-loop", "1", "-framerate", "30", "-i", str(png)]
        filtro = ("[0:v]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,setsar=1[base]"
                  % (W, H, W, H))
        atual = "base"
        for k, (_, a, b, h) in enumerate(pngs, 1):
            yy = max(20, min(y, H - h - 20))
            filtro += (";[%s][%d:v]overlay=x=(W-w)/2:y=%d:enable='between(t,%.3f,%.3f)'[v%d]"
                       % (atual, k, yy, a, b, k))
            atual = "v%d" % k
        filtro += ";[%s]format=yuv420p[saida]" % atual
        cmd += ["-filter_complex", filtro, "-map", "[saida]", "-map", "0:a?",
                "-t", "%.3f" % dur, "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
                "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(destino)]
        try:
            subprocess.run(cmd, cwd=str(tmp), check=True, timeout=1800)
            shutil.rmtree(tmp, ignore_errors=True)
            return destino
        except subprocess.CalledProcessError:
            pass

    # Sem PIL ou se a sobreposição falhar: entrega o corte sem legenda queimada.
    vf = ("scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d" % (W, H, W, H))
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-ss", "%.3f" % inicio, "-t", "%.3f" % dur,
                    "-i", str(video), "-vf", vf, "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
                    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(destino)],
                   cwd=str(tmp), check=True, timeout=1800)
    shutil.rmtree(tmp, ignore_errors=True)
    return destino


def _heuristicas(segmentos, quantidade):
    blocos = _blocos_para_cenas(segmentos, alvo=28.0, maximo=45.0)
    if not blocos:
        return []
    def nota(b):
        t = b["texto"]
        return (2 if "?" in t else 0) + (1 if re.search(r"\d", t) else 0) + min(3, len(t) / 120.0)
    blocos = sorted(blocos, key=nota, reverse=True)[:max(1, quantidade)]
    blocos.sort(key=lambda b: b["inicio"])
    return [{"inicio": b["inicio"], "fim": b["fim"], "titulo": b["texto"][:80],
             "gancho": b["texto"][:120], "motivo": "escolha heurística"} for b in blocos]


async def selecionar_cortes(pedir_texto, segmentos, quantidade, contexto):
    quantidade = max(1, min(10, int(quantidade or 5)))
    linhas = []
    for s in segmentos[:400]:
        linhas.append("[%.1f-%.1f] %s" % (s["inicio"], s["fim"], s["texto"]))
    timeline = "\n".join(linhas)[:12000]
    pedido = """Você escolhe cortes de um vídeo. A transcrição tem tempos em segundos.

Escolha %d trechos AUTOSSUFICIENTES, com 15 a 45 segundos, que comecem e terminem fazendo sentido.
Prefira: pergunta forte, conflito, revelação, número, opinião clara ou história fechada.
Não invente fala; use os tempos reais. Responda SÓ com JSON:
[{"inicio":12.3,"fim":38.7,"titulo":"...","gancho":"...","motivo":"..."}]

TRANSCRIÇÃO:
%s""" % (quantidade, timeline)
    try:
        res = await pedir_texto("canal_pautas", pedido)
        bruto = roteirista._json_do_texto((res or {}).get("texto") if isinstance(res, dict) else res)
        if isinstance(bruto, dict):
            bruto = bruto.get("cortes") or bruto.get("clips") or []
        if isinstance(bruto, list):
            saida = []
            for x in bruto:
                if not isinstance(x, dict):
                    continue
                ini, fim = float(x.get("inicio") or 0), float(x.get("fim") or 0)
                if fim - ini < 8 or fim - ini > 90:
                    continue
                saida.append({"inicio": round(ini, 2), "fim": round(fim, 2),
                              "titulo": str(x.get("titulo") or "")[:120],
                              "gancho": str(x.get("gancho") or "")[:200],
                              "motivo": str(x.get("motivo") or "")[:300]})
            if saida:
                return saida[:quantidade]
    except Exception:
        pass
    return _heuristicas(segmentos, quantidade)


def analisar(url, pasta, idioma="pt"):
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    video = baixar_video(url, pasta)
    audio = extrair_audio(video, pasta)
    segmentos = transcrever(audio, idioma)
    dados = {"url": url, "video": str(video), "audio": str(audio),
             "segmentos": segmentos, "duracao": segmentos[-1]["fim"] if segmentos else 0,
             "texto": texto_de(segmentos), "quando": int(time.time())}
    (pasta / "referencia.json").write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    return dados
