"""Leitura e rotação de chaves de API guardadas em API/<servico>.txt.

Uma chave por linha. A rotação só decide por qual chave começar; quem chama
tenta as outras se a primeira falhar. Não há estado em disco: o cursor vive no
processo.
"""

import os
import threading
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
API = Path(os.environ.get("ESTUDIO_API_DIR") or (RAIZ / "API"))
_TRAVA = threading.Lock()
_CURSOR = {}


def lista(nome):
    arq = API / (str(nome or "").strip().lower() + ".txt")
    try:
        return [l.strip() for l in arq.read_text(encoding="utf-8").splitlines() if l.strip()]
    except Exception:
        return []


def ordenadas(nome):
    """Devolve as chaves começando pela próxima da rotação."""
    with _TRAVA:
        ks = lista(nome)
        if not ks:
            return []
        i = _CURSOR.get(nome, 0) % len(ks)
        _CURSOR[nome] = i + 1
        return ks[i:] + ks[:i]


def proxima(nome):
    ks = ordenadas(nome)
    return ks[0] if ks else ""
