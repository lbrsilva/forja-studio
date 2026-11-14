"""Redação de segredos em textos de erro e log."""

import re

_PADROES = (
    (re.compile(r"\bhf_[A-Za-z0-9]{8,}\b"), "hf_***"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"), "sk-***"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._-]{8,}"), r"\1***"),
    (re.compile(r"(?i)([?&](?:key|api_key|token|access_token)=)[^&\s]+"), r"\1***"),
)


def redigir(texto):
    s = str(texto or "")
    for padrao, troca in _PADROES:
        s = padrao.sub(troca, s)
    return s
