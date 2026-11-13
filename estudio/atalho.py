r"""Cria o icone "Forja Studio" na Area de Trabalho - um atalho .lnk de verdade.

Por que .lnk e nao .bat: um .bat na Area de Trabalho abre uma janela preta antes de
qualquer coisa, nao tem icone proprio e parece gambiarra. Um .lnk tem icone, tem nome
limpo e pode apontar para o `pythonw.exe` (o Python SEM console) - a pessoa clica e so
ve o navegador.

Feito pelo proprio Windows (WScript.Shell, via PowerShell) em vez de escrever os bytes
do .lnk na mao: o formato e cheio de detalhe e o Windows ja sabe faze-lo certo.

    python atalho.py            cria (ou refaz) o icone na Area de Trabalho
    python atalho.py --tirar    tira o icone
    python atalho.py --onde     so diz onde ele ficaria
"""
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

import plataforma

AQUI = Path(__file__).resolve().parent          # ...\estudio
RAIZ = AQUI.parent
NOME = "Forja Studio"

# Por que o ultimo `criar()` nao deu certo. Em portugues, para ir direto para a tela.
ultimo_motivo = None


def _area_de_trabalho():
    """Pergunta ao Windows onde fica a Area de Trabalho DESTA pessoa.

    Adivinhar C:\\Users\\<nome>\\Desktop erra em quem usa OneDrive (ela fica
    redirecionada), em Windows noutro idioma e em perfil fora do C:.
    """
    if not plataforma.WIN:
        p = Path.home() / "Desktop"
        return p if p.is_dir() else None
    # o pacote traz este modulo pronto; aqui no projeto ele pode nao estar do lado
    for pasta in (RAIZ, RAIZ / "_github" / "pacote", AQUI):
        if (pasta / "area_de_trabalho.py").is_file():
            sys.path.insert(0, str(pasta))
            try:
                from area_de_trabalho import area_de_trabalho
                m = area_de_trabalho()
                if m:
                    return Path(m)
            except Exception:
                pass
            break
    import ctypes
    import ctypes.wintypes

    class G(ctypes.Structure):
        _fields_ = [("a", ctypes.c_ulong), ("b", ctypes.c_ushort),
                    ("c", ctypes.c_ushort), ("d", ctypes.c_ubyte * 8)]

    g = G()
    ole32, shell32 = ctypes.windll.ole32, ctypes.windll.shell32
    if ole32.CLSIDFromString(ctypes.c_wchar_p("{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}"),
                             ctypes.byref(g)) != 0:
        return None
    caminho = ctypes.c_wchar_p()
    if shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, 0, ctypes.byref(caminho)) != 0:
        return None
    try:
        p = Path(caminho.value)
        return p if p.is_dir() else None
    finally:
        ole32.CoTaskMemFree(caminho)


def _pythonw():
    """O Python SEM console. Com ele, clicar no icone nao pisca janela preta nenhuma."""
    if not plataforma.WIN:
        proprio = plataforma.python_comfy(RAIZ)
        return proprio if proprio.is_file() else Path(sys.executable)
    base = RAIZ / "ComfyUI_windows_portable" / "python_embeded"
    for nome in ("pythonw.exe", "python.exe"):
        p = base / nome
        if p.is_file():
            return p
    atual = Path(sys.executable)
    sem = atual.with_name("pythonw.exe")
    return sem if sem.is_file() else atual


def _ps(script):
    """Roda um PowerShell curto, escondido, e devolve (deu_certo, saida)."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
             "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, timeout=60,
            creationflags=0x08000000 if os.name == "nt" else 0)
        return r.returncode == 0, (r.stdout or r.stderr or "").strip()
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)


def _icone_icns(destino):
    """Converte o icone.ico em .icns com o sips do proprio macOS. False se nao der: o app fica sem icone."""
    ico = AQUI / "icone.ico"
    if not ico.is_file():
        return False
    try:
        r = subprocess.run(["/usr/bin/sips", "-s", "format", "icns", str(ico), "--out", str(destino)],
                           capture_output=True, timeout=30)
        return r.returncode == 0 and destino.is_file()
    except (OSError, subprocess.SubprocessError):
        return False


def _criar_app_mac(mesa):
    """Um Forja Studio.app que so chama o abrir.py: clicar abre a pagina, nada mais."""
    abrir = AQUI / "abrir.py"
    if not abrir.is_file():
        return None
    app = mesa / f"{NOME}.app"
    if app.exists():
        shutil.rmtree(app)
    macos, recursos = app / "Contents" / "MacOS", app / "Contents" / "Resources"
    macos.mkdir(parents=True)
    recursos.mkdir(parents=True)
    lancador = macos / "forja"
    lancador.write_text(
        "#!/bin/bash\n"
        'export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"\n'
        f'cd "{RAIZ}"\n'
        f'exec "{_pythonw()}" "{abrir}"\n', encoding="utf-8")
    lancador.chmod(0o755)
    info = {"CFBundleName": NOME, "CFBundleDisplayName": NOME, "CFBundleExecutable": "forja",
            "CFBundleIdentifier": "local.forjastudio.abrir", "CFBundlePackageType": "APPL",
            "CFBundleVersion": "1", "LSUIElement": True}
    if _icone_icns(recursos / "icone.icns"):
        info["CFBundleIconFile"] = "icone"
    with open(app / "Contents" / "Info.plist", "wb") as f:
        plistlib.dump(info, f)
    subprocess.run(["/usr/bin/touch", str(app)], capture_output=True)
    return app


def criar(mesa=None):
    """Cria o atalho. Devolve o caminho dele, ou None.

    Quando devolve None, o PORQUE fica em `ultimo_motivo` - em portugues, pronto para ir
    para a tela. Ver o cabecalho do arquivo: este era o ponto onde o icone sumia calado.
    """
    global ultimo_motivo
    ultimo_motivo = None
    if plataforma.MAC:
        mesa = Path(mesa) if mesa else _area_de_trabalho()
        if mesa and mesa.is_dir():
            return _criar_app_mac(mesa)
        ultimo_motivo = "Nao achei a sua Area de Trabalho."
        return None
    if os.name != "nt":
        ultimo_motivo = "O icone na Area de Trabalho so existe no Windows."
        return None
    mesa = Path(mesa) if mesa else _area_de_trabalho()
    if not mesa or not mesa.is_dir():
        ultimo_motivo = ("Nao achei a sua Area de Trabalho. Se ela estiver no OneDrive e "
                         "ele ainda nao tiver terminado de sincronizar, espere e tente "
                         "de novo.")
        return None

    alvo = mesa / f"{NOME}.lnk"
    py = _pythonw()
    abrir = AQUI / "abrir.py"
    icone = AQUI / "icone.ico"
    if not abrir.is_file():
        ultimo_motivo = (f"Falta o arquivo {abrir} na pasta do estudio. Baixe o pacote "
                         "de novo.")
        return None

    # o .lnk guarda o caminho; aspas duplas dentro do PowerShell viram ""
    def esc(p):
        return str(p).replace('"', '""')

    script = f'''
$a = (New-Object -ComObject WScript.Shell).CreateShortcut("{esc(alvo)}")
$a.TargetPath       = "{esc(py)}"
$a.Arguments        = '"{esc(abrir)}"'
$a.WorkingDirectory = "{esc(RAIZ)}"
$a.Description      = "Abre o Forja Studio. So a pagina: as IAs voce liga la dentro."
'''
    if icone.is_file():
        script += f'$a.IconLocation = "{esc(icone)},0"\n'
    else:
        # Sem isto, o atalho nasce com a CARA DO PYTHON em vez da nossa - e ninguem
        # entende por que o icone "nao e igual ao daqui". Falhava calado.
        print(f"  ATENCAO: nao achei {icone}. O atalho vai ficar com o icone do Python,")
        print("           nao com o nosso. Baixe o pacote de novo para ter o icone certo.")
    script += "$a.Save()\n"

    ok, saida = _ps(script)
    if ok and alvo.is_file():
        return alvo
    if not ok:
        ultimo_motivo = ("O Windows nao deixou criar o atalho. Costuma ser o antivirus ou "
                         "a politica de scripts do PowerShell. " + (saida or "")).strip()
    else:
        ultimo_motivo = (f"O PowerShell nao reclamou, mas o arquivo {alvo.name} nao "
                         "apareceu na Area de Trabalho. " + (saida or "")).strip()
    return None


def tirar(mesa=None):
    mesa = Path(mesa) if mesa else _area_de_trabalho()
    if not mesa:
        return False
    tirou = False
    for nome in (f"{NOME}.lnk", f"{NOME}.bat", f"{NOME}.app"):     # tira tambem o .bat antigo
        p = mesa / nome
        if p.exists():
            try:
                shutil.rmtree(p) if p.is_dir() else p.unlink()
                print(f"  tirei: {p}")
                tirou = True
            except OSError as e:
                print(f"  nao consegui tirar {p}: {e}")
    return tirou


def conferir(mesa=None):
    r"""Conta tudo sobre o atalho que EXISTE, para quem esta longe poder mandar o texto.

    Nasceu em 12/11/2026: o icone apareceu com a cara errada numa maquina de teste e nao
    abria, e daqui nao havia como saber por que. Adivinhar de longe custa um dia; uma tela
    de diagnostico custa um minuto.
    """
    mesa = Path(mesa) if mesa else _area_de_trabalho()
    print("=" * 64)
    print("  CONFERENCIA DO ICONE DO FORJA STUDIO")
    print("=" * 64)
    print(f"  pasta do estudio   : {RAIZ}")
    print(f"  Area de Trabalho   : {mesa}")

    abrir = AQUI / "abrir.py"
    icone = AQUI / "icone.ico"
    print(f"  estudio\\abrir.py   : {'esta la' if abrir.is_file() else 'FALTANDO'}")
    print(f"  estudio\\icone.ico  : "
          f"{str(icone.stat().st_size) + ' bytes' if icone.is_file() else 'FALTANDO'}")

    comfy = RAIZ / "ComfyUI_windows_portable" / "python_embeded" / "python.exe"
    print(f"  Python da ComfyUI  : {'esta la' if comfy.is_file() else 'nao instalada'}")
    print(f"  Python deste setup : {sys.executable}")
    escolhido = _pythonw()
    print(f"  o atalho usaria    : {escolhido}")
    if not Path(escolhido).is_file():
        print("                       ^^^ ESSE ARQUIVO NAO EXISTE - o atalho nao abriria")

    if not mesa:
        print("\n  Sem Area de Trabalho, nao da para conferir o atalho.")
        return 1

    alvo = mesa / f"{NOME}.lnk"
    print(f"\n  {NOME}.lnk        : {'existe' if alvo.is_file() else 'NAO EXISTE'}")
    if (mesa / f"{NOME}.bat").exists():
        print(f"  {NOME}.bat        : existe tambem (e o atalho ANTIGO; pode apagar)")
    if not alvo.is_file():
        print("\n  Rode 'Criar o icone na Area de Trabalho.bat' para criar.")
        return 1

    ok, saida = _ps(
        '$a = (New-Object -ComObject WScript.Shell).CreateShortcut("%s");'
        '"alvo=" + $a.TargetPath; "args=" + $a.Arguments;'
        '"pasta=" + $a.WorkingDirectory; "icone=" + $a.IconLocation'
        % str(alvo).replace('"', '""'))
    if not ok:
        print("  nao consegui ler o atalho:", saida)
        return 1
    dados = {}
    for linha in saida.splitlines():
        if "=" in linha:
            k, _, v = linha.partition("=")
            dados[k.strip()] = v.strip()
            print(f"    {k.strip():6}: {v.strip()}")

    problemas = []
    destino = dados.get("alvo", "")
    if destino and not Path(destino).is_file():
        problemas.append(f"o alvo '{destino}' NAO EXISTE nesta maquina - por isso nao abre")
    ico = (dados.get("icone") or "").rsplit(",", 1)[0]
    if not ico or ico == "," or not Path(ico).is_file():
        problemas.append("o atalho nao tem o NOSSO icone (por isso a carinha esta diferente)")
    if "abrir.py" not in (dados.get("args") or ""):
        problemas.append("o atalho nao aponta para o estudio\\abrir.py - foi feito a mao?")

    print()
    if problemas:
        for x in problemas:
            print("  [X] " + x)
        print("\n  Conserto: clique em 'Criar o icone na Area de Trabalho.bat'.")
        return 1
    print("  [OK] o atalho esta certo: aponta para o estudio e usa o nosso icone.")
    return 0


def main():
    mesa = _area_de_trabalho()
    if "--conferir" in sys.argv:
        return conferir(mesa)
    if "--onde" in sys.argv:
        print(f"  Area de Trabalho: {mesa}")
        return 0
    if "--tirar" in sys.argv:
        return 0 if tirar(mesa) else 1
    feito = criar(mesa)
    if feito:
        print(f"  icone criado: {feito}")
        print(f"    aponta para: {_pythonw().name} {AQUI / 'abrir.py'}")
        print("    clicar nele NAO abre janela preta e NAO acende a placa de video")
        return 0
    print("  nao consegui criar o icone.")
    print("  " + (ultimo_motivo or "Nao sei dizer o motivo."))
    print("\n  Enquanto isso, da para abrir pelo 'Forja Studio.bat' na pasta do estudio.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
