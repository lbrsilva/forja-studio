r"""Pergunta onde o Forja Studio deve guardar as coisas pesadas.

Por que isto existe: sao 235,7 GB de modelos. A chance de o disco onde a pessoa
descompactou o projeto ser o disco onde ela QUER 235 GB e baixa - quase sempre o
projeto cai no C: por costume, e o C: e justamente o que nao tem espaco.

O que a pessoa escolhe:
  - a pasta da ComfyUI (onde moram os modelos; e o que pesa)
  - a pasta das criacoes (imagens e videos que ela fizer; cresce sem parar)

O que ela NAO escolhe: a pasta do codigo. Ele e 1,3 MB e fica onde ja esta.

O resultado vira `caminhos.bat` (Windows) ou `caminhos.sh` (macOS), que o lancador lê antes de abrir o estudio.
Arquivo de texto simples, de proposito: se der errado, a pessoa abre no bloco de
notas e conserta na mao, sem precisar de mim nem de ninguem.
"""
import ctypes
import os
import shutil
import string
import sys
from pathlib import Path

GB = 1024 ** 3
WIN = os.name == "nt"
PASTA_COMFY = "ComfyUI_windows_portable" if WIN else "ComfyUI_mac"
PRECISA_TUDO = 270      # os 235,7 GB de modelos + ComfyUI + folga (ver REQUISITOS.md)
PRECISA_IMAGEM = 100    # so a trilha de imagem


def discos():
    """Os discos da maquina, com o espaco livre. So Windows."""
    fora = []
    if sys.platform == "darwin":
        raizes = ["/"] + [str(Path("/Volumes") / n) for n in sorted(os.listdir("/Volumes"))
                          if (Path("/Volumes") / n).is_mount()] if Path("/Volumes").is_dir() else ["/"]
        for raiz in dict.fromkeys(raizes):
            try:
                u = shutil.disk_usage(raiz)
                fora.append({"letra": raiz, "raiz": raiz, "livre": u.free / GB, "total": u.total / GB})
            except OSError:
                continue
        return fora
    if not WIN:
        return fora
    bits = ctypes.windll.kernel32.GetLogicalDrives()
    for i, letra in enumerate(string.ascii_uppercase):
        if not (bits >> i) & 1:
            continue
        raiz = f"{letra}:\\"
        try:
            tipo = ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(raiz))
            if tipo != 3:        # 3 = disco fixo. Pendrive e rede ficam de fora:
                continue         # ninguem quer 235 GB num pendrive que vai ser removido.
            u = shutil.disk_usage(raiz)
            fora.append({"letra": letra, "raiz": raiz,
                         "livre": u.free / GB, "total": u.total / GB})
        except Exception:
            continue
    return fora


def perguntar(texto, padrao=""):
    try:
        r = input(texto).strip().strip('"')
    except (EOFError, KeyboardInterrupt):
        print()
        return padrao
    return r or padrao


def cabe(pasta, precisa_gb):
    """(cabe?, livre_gb). Sobe ate achar um pai que exista: pasta nova ainda nao tem disco."""
    p = Path(pasta)
    while not p.exists() and p.parent != p:
        p = p.parent
    try:
        livre = shutil.disk_usage(str(p)).free / GB
    except OSError:
        return None, 0
    return livre >= precisa_gb, livre


def escolher(aqui: Path):
    print("\n" + "=" * 66)
    print(" ONDE VOCE QUER GUARDAR AS COISAS PESADAS?")
    print("=" * 66)

    ds = discos()
    if ds:
        print("\n  Os discos desta maquina:\n")
        print(f"    {'disco':<7} {'livre':>10} {'tamanho':>10}   {'da para…'}")
        for d in ds:
            if d["livre"] >= PRECISA_TUDO:
                veredito = "tudo (235,7 GB de modelos)"
            elif d["livre"] >= PRECISA_IMAGEM:
                veredito = "so imagem (66,5 GB)"
            else:
                veredito = "nao cabe"
            print(f"    {d['raiz']:<7} {d['livre']:>8.0f} GB {d['total']:>8.0f} GB   {veredito}")
        melhor = max(ds, key=lambda d: d["livre"])
        print(f"\n  O mais folgado e o {melhor['raiz']} com {melhor['livre']:.0f} GB livres.")
        sugestao = f"{melhor['letra']}:\\ForjaStudio" if WIN else str(Path(melhor["raiz"]) / "ForjaStudio")
    else:
        sugestao = str(aqui)

    print("\n  Reserve 270 GB para o pacote completo, ou 100 GB se voce so quiser imagem.")
    print("  (a conta inteira esta em REQUISITOS.md)")

    print("\n  --- 1. A ComfyUI e os modelos (o que pesa) ---")
    print(f"  Hoje: {aqui / PASTA_COMFY}")
    print("  Enter para deixar aqui mesmo, ou escreva outra pasta.")
    comfy = perguntar("  Pasta: ", str(aqui / PASTA_COMFY))
    ok, livre = cabe(comfy, PRECISA_TUDO)
    if ok is None:
        print(f"  ! Nao consegui ler o espaco de {comfy}. Vou aceitar assim mesmo.")
    elif not ok:
        print(f"  ! Atencao: so {livre:.0f} GB livres ai, e o pacote completo pede {PRECISA_TUDO}.")
        if livre >= PRECISA_IMAGEM:
            print(f"    Da para a trilha de imagem ({PRECISA_IMAGEM} GB). Para tudo, nao da.")
        else:
            print(f"    Nao cabe nem a trilha de imagem ({PRECISA_IMAGEM} GB).")
        if perguntar("    Escolher outra pasta? (S/n): ", "s").lower() != "n":
            return escolher(aqui)
    else:
        print(f"  ok: {livre:.0f} GB livres")

    print("\n  --- 2. Onde salvar o que voce criar ---")
    print("  Imagem e video se acumulam rapido. Pode ser outro disco.")
    padrao_saidas = str(Path(comfy) / "ComfyUI" / "output")
    saidas = perguntar(f"  Pasta [{padrao_saidas}]: ", padrao_saidas)

    if WIN:
        arq = aqui / "caminhos.bat"
        arq.write_text(
            "@echo off\r\n"
            "rem Caminhos escolhidos na instalacao. E so texto: pode abrir no bloco de\r\n"
            "rem notas e corrigir na mao se voce mudar as pastas de lugar.\r\n"
            f'set "ESTUDIO_COMFY_DIR={Path(comfy) / "ComfyUI"}"\r\n'
            f'set "ESTUDIO_SAIDAS={saidas}"\r\n',
            encoding="utf-8")
        leitor = "Forja Studio.bat"
    else:
        arq = aqui / "caminhos.sh"
        arq.write_text(
            "# Caminhos escolhidos na instalacao. E so texto: edite aqui se mudar as pastas de lugar.\n"
            f'export ESTUDIO_COMFY_DIR="{Path(comfy) / "ComfyUI"}"\n'
            f'export ESTUDIO_SAIDAS="{saidas}"\n',
            encoding="utf-8")
        leitor = "Forja Studio.command"
    print(f"\n  Guardado em {arq}")
    print(f"  O atalho '{leitor}' le esse arquivo toda vez que abre.")
    print("=" * 66 + "\n")
    return {"comfy": comfy, "saidas": saidas}


if __name__ == "__main__":
    escolher(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent)
