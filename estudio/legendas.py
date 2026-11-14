"""Alinha o texto do roteiro aos tempos reais da voz.

O Whisper transcreve o áudio com timestamps de palavra; o texto do roteiro é a
verdade. O alinhamento usa a transcrição só para descobrir QUANDO cada palavra do
roteiro foi dita, sem trocar o texto por erro de reconhecimento.
"""

import hashlib
import json
import re
import threading
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

_MODELO = None
_TRAVA = threading.Lock()


def _norm(texto):
    s = unicodedata.normalize("NFKD", str(texto or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s)


def _tokens(texto):
    return [(i, p, _norm(p)) for i, p in enumerate(str(texto or "").split()) if _norm(p)]


def _modelo():
    global _MODELO
    if _MODELO is None:
        with _TRAVA:
            if _MODELO is None:
                from faster_whisper import WhisperModel
                _MODELO = WhisperModel("small", device="cpu", compute_type="int8")
    return _MODELO


def _transcrever(audio, idioma="pt"):
    modelo = _modelo()
    segmentos, _ = modelo.transcribe(
        str(audio), language=idioma or None, beam_size=1,
        word_timestamps=True, vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=300),
    )
    palavras = []
    for seg in segmentos:
        for w in (getattr(seg, "words", None) or []):
            texto = str(getattr(w, "word", "") or "").strip()
            if not texto:
                continue
            inicio = float(getattr(w, "start", 0) or 0)
            fim = float(getattr(w, "end", inicio) or inicio)
            palavras.append({"palavra": texto, "inicio": inicio, "fim": fim, "norm": _norm(texto)})
    return palavras


def _interpolar(saida, texto_tokens, de, ate, inicio, fim):
    """Distribui as palavras sem correspondência no intervalo disponível."""
    faltam = [i for i in range(de, ate) if saida[i] is None]
    if not faltam:
        return
    passo = (fim - inicio) / float(len(faltam) + 1)
    for n, i in enumerate(faltam, 1):
        t = inicio + passo * n
        saida[i] = {"palavra": texto_tokens[i][1], "inicio": round(t, 3), "fim": round(t + 0.12, 3)}


def alinhar(audio, texto, idioma="pt", usar_cache=True):
    """Devolve [{palavra, inicio, fim}] na ordem do texto, ou [] se não der."""
    audio = Path(audio)
    if not audio.is_file() or not str(texto or "").strip():
        return []
    texto_tokens = _tokens(texto)
    if not texto_tokens:
        return []
    cache = audio.with_suffix(".palavras.json")
    chave = hashlib.sha1(str(texto).encode("utf-8")).hexdigest()
    if usar_cache and cache.is_file():
        try:
            d = json.loads(cache.read_text(encoding="utf-8"))
            if d.get("chave") == chave and d.get("audio_mtime") == audio.stat().st_mtime:
                return d.get("palavras") or []
        except Exception:
            pass

    try:
        reconhecidas = _transcrever(audio, idioma)
    except Exception:
        return []
    if not reconhecidas:
        return []

    saida = [None] * len(texto_tokens)
    rec_norm = [p["norm"] for p in reconhecidas]
    txt_norm = [t[2] for t in texto_tokens]
    matcher = SequenceMatcher(None, rec_norm, txt_norm, autojunk=False)
    for op, a1, a2, b1, b2 in matcher.get_opcodes():
        if op == "equal":
            for n in range(b2 - b1):
                r = reconhecidas[a1 + n]
                saida[b1 + n] = {"palavra": texto_tokens[b1 + n][1],
                                 "inicio": round(r["inicio"], 3), "fim": round(r["fim"], 3)}
        elif op == "replace":
            pares = min(a2 - a1, b2 - b1)
            for n in range(pares):
                r = reconhecidas[a1 + n]
                saida[b1 + n] = {"palavra": texto_tokens[b1 + n][1],
                                 "inicio": round(r["inicio"], 3), "fim": round(r["fim"], 3)}
            if b2 - b1 > pares:
                ini = reconhecidas[a2 - 1]["fim"] if a2 > a1 else reconhecidas[a1]["inicio"]
                fim = reconhecidas[a2]["inicio"] if a2 < len(reconhecidas) else ini + 0.5
                _interpolar(saida, texto_tokens, b1 + pares, b2, ini, max(ini + 0.1, fim))
        elif op == "delete":
            ini = reconhecidas[a1 - 1]["fim"] if a1 > 0 else reconhecidas[a1]["inicio"]
            fim = reconhecidas[a1]["inicio"] if a1 < len(reconhecidas) else ini + 0.5
            _interpolar(saida, texto_tokens, b1, b2, ini, max(ini + 0.1, fim))

    for i, p in enumerate(saida):
        if p is None:
            ini = saida[i - 1]["fim"] if i and saida[i - 1] else 0.0
            fim = next((x["inicio"] for x in saida[i + 1:] if x), ini + 0.4)
            _interpolar(saida, texto_tokens, i, i + 1, ini, max(ini + 0.1, fim))

    palavras = [p for p in saida if p]
    if usar_cache and palavras:
        try:
            cache.write_text(json.dumps({"chave": chave, "audio_mtime": audio.stat().st_mtime,
                                         "palavras": palavras}, ensure_ascii=False, indent=1),
                             encoding="utf-8")
        except Exception:
            pass
    return palavras
