# -*- coding: utf-8 -*-
"""Prova objetiva da voz local: gera a fala e manda o Whisper transcrever de volta.

POR QUE ISTO EXISTE
-------------------
"A voz ficou boa?" é opinião, e de madrugada não tem ninguém para ouvir. Mas
"a voz saiu inteligível?" dá para medir: se o Whisper ouve de volta as mesmas
palavras que a gente escreveu, o áudio está limpo. Se vier embaralhado — que foi
o que aconteceu nos dois vídeos que circularam — a transcrição denuncia na hora.

Isto NÃO substitui o ouvido dele para julgar se a voz é bonita; substitui o
ouvido para julgar se ela está QUEBRADA.

    py prova_voz.py                 motor atual
    py prova_voz.py --voz <id>      uma voz específica
"""
import asyncio
import os
import re
import sys
import unicodedata
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import voz_studio as V  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SAIDA = Path(__file__).resolve().parent.parent / "outputs" / "voz" / "prova"

# Frases do canal dele, de propósito: tem reticências (onde a voz respira),
# referência bíblica por extenso (nunca em algarismo) e as palavras difíceis
# do português — ão, ç, lh, nh.
FRASES = [
    "Para de medir o seu valor pelo seu cansaço.",
    "Jó trinta e oito mostra que Deus não veio explicar... veio se mostrar.",
    "Se você parou de ir e ninguém ligou pra saber por quê, isso fala mais deles do que da sua fé.",
    "A única coisa que o fogo queimou neles foi a corda.",
    "O azeite nascia de um jeito só: a azeitona precisava ser esmagada na prensa.",
]


# ---------------------------------------------------------------- a medida
# ARMADILHA que custou duas rodadas: comparar PALAVRA por palavra reprova coisa que está
# certa no áudio e só difere na ESCRITA do Whisper. Medido em 30/10:
#   escrito "Jó trinta e oito"  -> ouvido "Jó 38"        (ele escreve número em algarismo)
#   escrito "por quê"           -> ouvido "porquê"       (ele junta)
# Nos dois casos a VOZ falou certo. Então a conta é feita sobre a sequência de LETRAS, com
# os algarismos abertos por extenso e os espaços fora — assim "por quê" e "porquê" viram a
# mesma coisa, e o que sobra de diferença é som engolido de verdade.
UNI = ["zero", "um", "dois", "tres", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez",
       "onze", "doze", "treze", "quatorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"]
DEZ = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]


def por_extenso(n):
    n = int(n)
    if n < 20:
        return UNI[n]
    if n < 100:
        d, u = divmod(n, 10)
        return DEZ[d] + (" e " + UNI[u] if u else "")
    c, r = divmod(n, 100)
    if n < 1000:
        cem = "cem" if n == 100 else ("cento" if c == 1 else
                                      ["", "", "duzentos", "trezentos", "quatrocentos", "quinhentos",
                                       "seiscentos", "setecentos", "oitocentos", "novecentos"][c])
        return cem + (" e " + por_extenso(r) if r else "")
    return str(n)  # acima de mil não aparece em narração nossa; deixa como está


def limpar(s):
    s = unicodedata.normalize("NFKD", str(s).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\d+", lambda m: " " + por_extenso(m.group()) + " ", s)
    return re.sub(r"[^a-z]+", "", s)


def palavras(s):
    s = unicodedata.normalize("NFKD", str(s).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return [p for p in re.sub(r"[^a-z0-9]+", " ", s).split() if p]


def acerto(escrito, ouvido):
    """Quanto do que foi escrito sobreviveu no que foi ouvido, em letras (0 a 1)."""
    import difflib
    a, b = limpar(escrito), limpar(ouvido)
    return difflib.SequenceMatcher(None, a, b).ratio(), len(a)


# O transcribe do próprio VoiceStudio não serve quando ele roda SEM JANELA: por dentro ele
# chama "http://127.0.0.1/transcribe" — sem a porta — e leva 403. É defeito dele, não nosso.
# Então quem ouve é o faster-whisper que o projeto já usa no `tempos.py` dos Poemas (Python
# 3.12; o `py` padrão virou 3.14 e não tem a biblioteca). Independente do motor que gerou o
# áudio, o juiz é sempre o mesmo — que é o que torna a comparação entre motores justa.
import json as _json       # noqa: E402
import subprocess          # noqa: E402

_OUVIR = r"""
import sys, json
from faster_whisper import WhisperModel
m = WhisperModel("small", device="cpu", compute_type="int8")
segs, _ = m.transcribe(sys.argv[1], language="pt", beam_size=5)
print(json.dumps({"texto": " ".join(s.text.strip() for s in segs)}, ensure_ascii=False))
"""


def ouvir(arquivo):
    lancador = ["py", "-3.12"] if os.name == "nt" else [sys.executable]
    r = subprocess.run([*lancador, "-c", _OUVIR, str(arquivo)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    linha = [l for l in (r.stdout or "").splitlines() if l.strip().startswith("{")]
    if not linha:
        raise RuntimeError("o whisper não devolveu nada: " + ((r.stderr or "").strip()[-200:] or "?"))
    return _json.loads(linha[-1]).get("texto", "").strip()


async def uma(texto, arquivo, voz_id):
    r = await V.falar(texto, arquivo, voz_id=voz_id, idioma="pt")
    return r, await asyncio.to_thread(ouvir, arquivo)


async def main():
    voz_id = None
    if "--voz" in sys.argv:
        voz_id = sys.argv[sys.argv.index("--voz") + 1]
    SAIDA.mkdir(parents=True, exist_ok=True)

    est = await V.estado()
    if not est["no_ar"]:
        print("O motor de voz não está no ar. " + str(est.get("detalhe"))[:160])
        return 1
    print("placa: %s" % est.get("gpu"))
    print("voz  : %s" % (voz_id or "(a padrão)"))
    print("=" * 68)

    bons = total = medidas = falhas = 0
    seg_audio = seg_placa = 0.0
    for n, txt in enumerate(FRASES, 1):
        arq = SAIDA / ("prova_%02d.wav" % n)
        try:
            r, ouvido = await uma(txt, arq, voz_id)
        except Exception as e:
            # Frase que NÃO deu para medir não entra na conta como se tivesse errado.
            # Contar falha de ferramenta como "0 palavras certas" foi o que fez esta prova
            # anunciar "EMBARALHADO" num áudio perfeito. Erro de medição não é resultado.
            falhas += 1
            print("%d) NÃO MEDI: %s" % (n, str(e)[:160]))
            print()
            continue
        medidas += 1
        razao, tam = acerto(txt, ouvido)
        bons += razao * tam
        total += tam
        seg_audio += r["segundos"] or 0
        seg_placa += r["demorou"]
        print("%d) %.2f s de áudio, gerado em %.2f s" % (n, r["segundos"] or 0, r["demorou"]))
        print("   escrito: %s" % txt)
        print("   ouvido : %s" % ouvido[:150])
        print("   acerto : %.0f%% do que foi escrito" % (100 * razao))
        print()

    print("=" * 68)
    if seg_audio:
        print("VELOCIDADE  : %.1f s de áudio em %.1f s de placa (%.2fx o tempo real)"
              % (seg_audio, seg_placa, seg_placa / seg_audio))
    if not medidas:
        print("NÃO DEU PARA MEDIR NENHUMA FRASE (%d falha(s) de ferramenta)." % falhas)
        print("Os áudios FORAM gerados e estão em %s — ouça-os." % SAIDA)
        print()
        print("VEREDITO: NENHUM. Sem transcrição não há prova, e chutar aqui seria pior")
        print("          que não medir: na primeira versão esta prova anunciou")
        print("          'EMBARALHADO' num áudio que estava perfeito.")
        return 2
    pct = 100 * bons / max(total, 1)
    print("ACERTO: %.0f%% das letras ditas  (em %d de %d frases)" % (pct, medidas, len(FRASES)))
    if falhas:
        print("        %d frase(s) não deram para medir e ficaram FORA da conta." % falhas)
    print()
    # O corte não é chute: abaixo de 85% sobrou palavra engolida o bastante para
    # o espectador ouvir errado, que é exatamente o defeito que a gente procura.
    if pct >= 95:
        print("VEREDITO: o português está LIMPO. Dá para usar.")
    elif pct >= 85:
        print("VEREDITO: dá para entender, mas engoliu palavra. Ouvir antes de confiar.")
    else:
        print("VEREDITO: EMBARALHADO. É o defeito que os vídeos mostraram — trocar de motor.")
    print("Arquivos em: %s" % SAIDA)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
