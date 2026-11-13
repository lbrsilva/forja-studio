# -*- coding: utf-8 -*-
"""SETUP do Estudio Local: aplica a configuracao depois que voce baixou as IAs.

    python setup.py

O QUE ELE FAZ, E O QUE ELE NAO FAZ
----------------------------------
Este projeto NAO carrega as IAs: sao 165 GB, nao cabem num repositorio. O que ele carrega e
o painel e a configuracao -- quais IAs valem a pena, ajustadas como, ligadas entre si.

Entao sao dois momentos:

    1. voce baixa os modelos           (a lista esta em IAS-INSTALADAS.md)
    2. voce roda este setup            (ele poe a configuracao no lugar e confere tudo)

O setup NAO baixa modelo. Ele CONFERE o que voce baixou, diz o que falta e em que pasta cada
coisa tem que estar -- que e o erro mais comum de todos.

NADA DAQUI E DESTRUTIVO
-----------------------
Ele nunca sobrescreve um arquivo seu sem avisar, nunca apaga modelo e nunca mexe no que ja
estava funcionando. Se achar que vai estragar alguma coisa, ele para e explica.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
WIN = os.name == "nt"
MAC = sys.platform == "darwin"
PASTA_COMFY = "ComfyUI_windows_portable" if WIN else "ComfyUI_mac"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

OK, AVISO, ERRO = "  [ok] ", "  [!]  ", "  [X]  "
_problemas = []
_avisos = []


def titulo(n, t):
    print("\n%s\n%d. %s\n%s" % ("-" * 66, n, t, "-" * 66))


def falhou(msg):
    _problemas.append(msg)
    print(ERRO + msg)


def cuidado(msg):
    _avisos.append(msg)
    print(AVISO + msg)


# ---------------------------------------------------------------------- 1. a maquina
def conferir_maquina():
    titulo(1, "A sua maquina")
    v = sys.version_info
    if v < (3, 10):
        falhou("Python %d.%d e antigo demais; precisa de 3.10 ou mais novo." % (v.major, v.minor))
    else:
        print(OK + "Python %d.%d.%d" % (v.major, v.minor, v.micro))

    if MAC:
        chip = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True,
                              text=True).stdout.strip()
        mem = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True,
                                 text=True).stdout.strip() or 0) / 1024 ** 3
        print(OK + "chip: %s (%.0f GB de memoria unificada)" % (chip, mem))
        if "Apple" not in chip:
            cuidado("Mac com processador Intel: sem GPU utilizavel pela ComfyUI, tudo roda no processador.")
        elif mem < 16:
            cuidado("Com menos de 16 GB de memoria, as IAs de video nao cabem. "
                    "A parte de imagem leve funciona.")
        _checar_disco()
        return
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=20)
        linha = (r.stdout or "").strip().splitlines()
        if not linha:
            raise OSError("sem resposta")
        nome, mem = [x.strip() for x in linha[0].split(",")[:2]]
        gb = int("".join(c for c in mem if c.isdigit())) / 1024
        print(OK + "placa: %s (%.0f GB)" % (nome, gb))
        if gb < 15:
            cuidado("Com menos de 16 GB de placa, as IAs de video nao cabem. "
                    "A parte de imagem funciona.")
    except Exception:
        cuidado("Nao achei a nvidia-smi. Sem placa NVIDIA, so o que roda no processador "
                "vai funcionar -- e vai ser muito lento.")

    _checar_disco()


def _checar_disco():
    try:
        livre = shutil.disk_usage(AQUI).free / 1024 ** 3
        print(OK + "espaco livre aqui: %.0f GB" % livre)
        if livre < 170:
            cuidado("A trilha completa pede 165 GB de modelos. "
                    "Veja as trilhas menores em INSTALAR.md.")
    except OSError:
        pass


# ------------------------------------------------------------------- 2. a ComfyUI
def achar_comfy():
    titulo(2, "A ComfyUI")
    if os.environ.get("ESTUDIO_COMFY_DIR"):
        c = Path(os.environ["ESTUDIO_COMFY_DIR"])
        print(OK + "ESTUDIO_COMFY_DIR aponta para %s" % c)
    else:
        c = AQUI / PASTA_COMFY / "ComfyUI"
    if not (c / "main.py").is_file():
        falhou("Nao achei a ComfyUI em %s.\n"
               "       %s" % (c, "Rode ./instalar-mac.sh, ou aponte com ESTUDIO_COMFY_DIR." if not WIN else
                              "Descompacte a ComfyUI portatil aqui, ou aponte com ESTUDIO_COMFY_DIR."))
        return None
    print(OK + "achei em %s" % c)

    # 02/11/2026: eram 6. O segment-anything-2 e o controlnet_aux so serviam ao Wan Animate,
    # que saiu do pacote -- e o INSTALAR.md ja manda instalar 4. Aqui tambem tem que ser 4,
    # senao quem segue o manual direitinho e reprovado por um complemento que nao usa.
    NOS = ("ComfyUI-Easy-Media", "ComfyUI-GGUF", "ComfyUI-KJNodes", "ComfyUI_Fill-ChatterBox")
    faltam = [n for n in NOS if not (c / "custom_nodes" / n).is_dir()]
    if faltam:
        cuidado("Faltam %d complementos: %s\n"
                "       Instale pelo ComfyUI Manager (procure pelo nome). Sem eles as IAs\n"
                "       aparecem na tela mas nao rodam." % (len(faltam), ", ".join(faltam)))
    else:
        print(OK + "os %d complementos estao instalados" % len(NOS))
    return c


# -------------------------------------------------------------------- 3. os modelos
def conferir_modelos(comfy):
    titulo(3, "Os modelos que voce baixou")
    man = AQUI / "modelos.json"
    if not man.is_file():
        cuidado("Nao achei o modelos.json; pulei a conferencia.")
        return
    lista = json.loads(man.read_text(encoding="utf-8")).get("comfyui", {})
    if not comfy:
        cuidado("Sem a ComfyUI nao da para conferir os %d modelos." % len(lista))
        return
    tem, falta, lugar_errado = [], [], []
    raiz = comfy / "models"
    onde = {}
    for p, _, arqs in os.walk(raiz):
        for a in arqs:
            onde.setdefault(a, []).append(str(Path(p).relative_to(raiz)).replace("\\", "/"))
    for nome, info in sorted(lista.items()):
        if nome not in onde:
            falta.append((nome, info))
        elif info.get("pasta") and info["pasta"] not in onde[nome]:
            lugar_errado.append((nome, info["pasta"], onde[nome][0]))
        else:
            tem.append(nome)
    print(OK + "%d de %d modelos no lugar certo" % (len(tem), len(lista)))
    if lugar_errado:
        print(AVISO + "%d na PASTA ERRADA (por isso a IA nao aparece na lista):" % len(lugar_errado))
        for nome, certo, achado in lugar_errado:
            print("        %s\n           esta em models/%s  ->  tem que ir para models/%s"
                  % (nome, achado, certo))
        _avisos.append("%d modelos na pasta errada" % len(lugar_errado))
    if falta:
        gb = sum(i.get("bytes", 0) for _, i in falta) / 1024 ** 3
        print(AVISO + "%d ainda nao baixados (%.0f GB). As IAs que dependem deles vao" % (len(falta), gb))
        print("        aparecer como nao instaladas -- o painel funciona assim mesmo.")
        for nome, info in falta[:8]:
            print("        falta: %-58s -> models/%s" % (nome[:58], info.get("pasta", "?")))
        if len(falta) > 8:
            print("        ... e mais %d (a lista inteira esta em IAS-INSTALADAS.md)" % (len(falta) - 8))
        _avisos.append("%d modelos faltando" % len(falta))


# --------------------------------------------------------------- 4. as dependencias
def instalar_dependencias(comfy):
    titulo(4, "As 6 dependencias do Python")
    if "--conferir" in sys.argv:
        print(OK + "modo conferencia: nao instalei nada")
        return
    if WIN:
        py = (comfy.parent / "python_embeded" / "python.exe") if comfy else None
    else:
        py = (comfy.parent / "venv" / "bin" / "python") if comfy else None
    if not (py and py.is_file()):
        py = Path(sys.executable)
        cuidado("Nao achei o python da ComfyUI; vou usar %s." % py.name)
    req = AQUI / "requirements.txt"
    if not req.is_file():
        falhou("Nao achei o requirements.txt.")
        return
    print("  instalando com %s ..." % py)
    r = subprocess.run([str(py), "-m", "pip", "install", "-r", str(req)],
                       capture_output=True, text=True)
    if r.returncode:
        falhou("O pip falhou. As ultimas linhas:\n       "
               + "\n       ".join((r.stderr or r.stdout or "").strip().splitlines()[-4:]))
    else:
        print(OK + "instaladas")


# --------------------------------------------------------------- 5. a configuracao
def conferir_configuracao():
    titulo(5, "A nossa configuracao")
    est = AQUI / "estudio"
    if not (est / "server.py").is_file():
        falhou("Nao achei a pasta estudio aqui do lado.")
        return
    if (est / "presets.json").is_file():
        pres = json.loads((est / "presets.json").read_text(encoding="utf-8"))
        n = sum(len(v) for v in pres.values() if isinstance(v, list))
        wf = len(list((est / "presets").glob("*.api.json")))
        print(OK + "%d IAs configuradas, %d workflows ajustados" % (n, wf))
    elif (est / "presets.cofre").is_file():
        print(OK + "configuracao das IAs no cofre (abre com a sua conta, dentro do programa)")
    else:
        falhou("Nao achei os presets (estudio/presets.cofre).")
    if (est / "tempos.json").is_file():
        print(OK + "tempos medidos: o painel ja mostra quanto falta na primeira geracao")

    cfg = est / "config.json"
    if "--conferir" in sys.argv:
        pass
    elif cfg.is_file():
        print(OK + "config.json ja existe (e seu, nao mexi)")
    elif True:
        cfg.write_text(json.dumps({"canal_dir": "", "hermes_dir": ""}, indent=2), encoding="utf-8")
        print(OK + "criei o config.json vazio (as suas pastas vao aqui)")

    cl = AQUI / ".claude"
    if cl.is_dir():
        s = len(list((cl / "skills").glob("*"))) if (cl / "skills").is_dir() else 0
        a = len(list((cl / "agents").glob("*.md"))) if (cl / "agents").is_dir() else 0
        m = len(list((cl / "memory").glob("*.md"))) if (cl / "memory").is_dir() else 0
        print(OK + "Claude Code: %d skills, %d agentes, %d memorias "
                   "(apague a pasta .claude se nao usa)" % (s, a, m))


# --------------------------------------------------------------- o lugar padrao
#
# 12/11/2026. Nao e uma exigencia: e o lugar que a gente recomenda, e que a documentacao
# e o suporte assumem. Quem quiser outro, poe noutro - o estudio funciona igual. O que
# nao da e a gente nao ter UM lugar para escrever nas instrucoes.
LUGAR_PADRAO = r"C:\ForjaStudio"


def conferir_o_lugar():
    """Diz se o estudio esta no lugar recomendado, e por que o lugar importa."""
    titulo(0, "Onde o estudio esta instalado")
    atual = str(AQUI)
    print("  aqui: %s" % atual)
    if atual.lower().rstrip("\\") == LUGAR_PADRAO.lower():
        print(OK + "e o lugar padrao")
        return

    print("  padrao recomendado: %s" % LUGAR_PADRAO)
    motivos = []
    if " " in atual:
        motivos.append("tem ESPACO no nome, e caminho com espaco ja quebrou .bat aqui")
    if "onedrive" in atual.lower():
        motivos.append("esta dentro do OneDrive, que vai tentar SINCRONIZAR os modelos")
    elif "\\documents" in atual.lower() or "\\documentos" in atual.lower():
        motivos.append("esta no Documentos, que em muita maquina o OneDrive sincroniza - "
                       "e ai ele tentaria subir os 270 GB de modelos")
    if len(atual) > 60:
        motivos.append("e longo, e o Windows corta caminho em 260 caracteres")

    if motivos:
        for m in motivos:
            cuidado(m)
    else:
        print("  (funciona assim mesmo; o padrao e so para a documentacao bater)")
    print("\n       Para ir para o lugar padrao: clique em 'IR PARA O LUGAR PADRAO.bat'.")
    print("       Ele copia (nao move) e refaz o icone. Numa instalacao pesada ele")
    print("       recusa e explica como mover a mao - 270 GB nao se copia as cegas.")


# ------------------------------------------------------------------ 6. o atalho
def criar_atalho(comfy):
    """Os atalhos de abrir. Eles VEM prontos no pacote; aqui so conferimos e explicamos.

    Antes este trecho escrevia um .bat na hora, e ele tinha um defeito feio: mandava abrir
    o navegador ANTES de ligar o servidor. A primeira coisa que a pessoa via, depois de
    baixar 235 GB, era "nao foi possivel conectar" - e tinha de adivinhar sozinha que
    bastava atualizar a pagina. Os atalhos de agora esperam o estudio responder de verdade.
    """
    titulo(6, "Os atalhos para abrir")
    ext = ".bat" if WIN else ".command"
    principal = AQUI / ("Forja Studio" + ext)
    if not principal.is_file():
        cuidado("Nao achei o '%s' aqui do lado. Da para abrir na mao:\n"
                "       %s" % (principal.name, "ComfyUI_windows_portable\\python_embeded\\python.exe estudio\\server.py"
                               if WIN else "ComfyUI_mac/venv/bin/python estudio/server.py"))
        return None
    print(OK + "%-29s abre o painel (espera ficar pronto antes)" % principal.name)
    sistema = "Windows" if WIN else "Mac"
    extras = [("Criar o icone na Area de Trabalho.bat", "poe o icone na sua mesa"),
              ("IR PARA O LUGAR PADRAO.bat", "leva tudo para C:\\ForjaStudio")]
    if WIN:
        extras += [("Ligar com o Windows.bat", "abre sozinho quando voce entra no PC"),
                   ("Nao ligar com o Windows.bat", "desfaz o de cima"),
                   ("Desligar o estudio.bat", "fecha tudo e libera a placa de video")]
    else:
        extras += [(f"Ligar com o {sistema}{ext}", "abre sozinho quando voce entra no computador"),
                   (f"Nao ligar com o {sistema}{ext}", "desfaz o de cima"),
                   ("Desligar o estudio" + ext, "fecha tudo e libera a placa de video / memoria")]
    for extra, oque in extras:
        if (AQUI / extra).is_file():
            print(OK + "%-29s %s" % (extra, oque))

    # Icone na Area de Trabalho so se a pessoa quiser: mexer na area de trabalho dos
    # outros sem perguntar e falta de educacao.
    #
    # 04/11/2026: era um .bat e virou um .lnk de verdade. O .bat abria uma janela preta
    # antes de qualquer coisa, nao tinha icone proprio e parecia gambiarra. O .lnk aponta
    # para o pythonw.exe (o Python SEM console) rodando estudio\abrir.py: a pessoa clica e
    # ve o navegador, mais nada. Quem acha a Area de Trabalho e o atalho.py, que pergunta
    # ao Windows em vez de adivinhar "C:\Users\<nome>\Desktop" - quem usa OneDrive tem ela
    # redirecionada, e num Windows noutro idioma a pasta nem se chama "Desktop".
    if "--conferir" not in sys.argv and (WIN or MAC):
        try:
            sys.path.insert(0, str(AQUI / "estudio"))
            import atalho as _atalho
            mesa = _atalho._area_de_trabalho()
            if mesa and not (mesa / ("Forja Studio.lnk" if WIN else "Forja Studio.app")).exists():
                if input("\n   Quer o icone do Forja Studio na Area de Trabalho? (S/n): "
                         ).strip().lower() != "n":
                    feito = _atalho.criar(mesa)
                    if feito:
                        print(OK + "icone criado na Area de Trabalho")
                        print("       Clicar nele abre SO a pagina - nenhuma janela preta e")
                        print("       nenhuma IA ligada. As IAs voce liga pelos botoes la dentro,")
                        print("       uma de cada vez, do jeito que o seu computador aguentar.")
                    else:
                        cuidado("nao consegui criar o icone. Da para abrir pelo"
                                " '%s' aqui da pasta." % principal.name)
        except (OSError, EOFError, KeyboardInterrupt):
            pass
        except Exception as erro_icone:
            cuidado("nao consegui criar o icone (%s). Da para abrir pelo"
                    " '%s' aqui da pasta." % (erro_icone, principal.name))
    return principal


def _de_novo_depois():
    """A frase que diz como pedir o icone mais tarde. Numa constante porque aparece em
    tres lugares, e tres copias de um texto viram tres textos diferentes com o tempo."""
    print("       Da para pedir ele depois: clique em")
    print("       'Criar o icone na Area de Trabalho.bat', aqui nesta pasta.")


def _icone_na_area_de_trabalho():
    r"""O icone do Forja Studio na Area de Trabalho.

    12/11/2026 - POR QUE ISTO DEIXOU DE SER SO UMA PERGUNTA

    O Jerffeson instalou numa maquina nova, pelo GitHub, e o icone nao apareceu. Nenhum
    erro, em lugar nenhum. O trecho antigo pendurava o icone num `input()` e tinha, logo
    abaixo, um `except (OSError, EOFError, KeyboardInterrupt): pass` - ou seja: numa
    instalacao que nao consegue perguntar, o icone nao nascia E NINGUEM FICAVA SABENDO.

    Perguntar continua sendo o certo quando da para perguntar: mexer na Area de Trabalho
    dos outros sem avisar e falta de educacao. Mas nao conseguir perguntar nao e um "nao".
    Ele pediu o icone; na duvida, o icone nasce - e se ele nao quiser, tira num clique.
    """
    try:
        sys.path.insert(0, str(AQUI / "estudio"))
        import atalho as _atalho
    except Exception as exc:
        cuidado("nao consegui carregar o criador de icone (%s)." % exc)
        _de_novo_depois()
        return

    try:
        mesa = _atalho._area_de_trabalho()
    except Exception as exc:
        mesa = None
        cuidado("nao consegui achar a sua Area de Trabalho (%s)." % exc)

    if not mesa:
        cuidado("nao achei a sua Area de Trabalho, entao nao criei o icone.")
        _de_novo_depois()
        return

    if (mesa / "Forja Studio.lnk").exists():
        print(OK + "o icone do Forja Studio ja esta na Area de Trabalho")
        return

    quer = True
    try:
        quer = input("\n   Quer o icone do Forja Studio na Area de Trabalho? (S/n): "
                     ).strip().lower() != "n"
    except (EOFError, OSError):
        # Instalacao que nao tem como perguntar. Criar e o que ele pediu.
        print("\n   (nao deu para perguntar aqui - vou criar o icone; se nao quiser,"
              " e so apagar)")
    except KeyboardInterrupt:
        print("\n   Tudo bem, sem icone.")
        _de_novo_depois()
        return

    if not quer:
        print("   Tudo bem, sem icone.")
        _de_novo_depois()
        return

    try:
        feito = _atalho.criar(mesa)
    except Exception as exc:
        feito = None
        _atalho.ultimo_motivo = str(exc)

    if feito:
        print(OK + "icone criado na Area de Trabalho")
        print("       Clicar nele abre SO a pagina - nenhuma janela preta e")
        print("       nenhuma IA ligada. As IAs voce liga pelos botoes la dentro,")
        print("       uma de cada vez, do jeito que o seu computador aguentar.")
        return

    # Falhar aqui nao pode mais ser mudo: o motivo vai para a tela, inteiro.
    cuidado("nao consegui criar o icone.")
    print("       " + (getattr(_atalho, "ultimo_motivo", None) or "Nao sei dizer o motivo."))
    print("       Da para abrir o estudio pelo 'Forja Studio.bat', aqui da pasta.")
    _de_novo_depois()


def main():
    print("=" * 66)
    print("  SETUP DO ESTUDIO LOCAL")
    print("  Poe a configuracao no lugar. Nao baixa modelo e nao apaga nada.")
    if "--conferir" in sys.argv:
        print("  MODO CONFERENCIA: so olha, nao instala nem cria nada.")
    print("=" * 66)
    conferir_maquina()
    conferir_o_lugar()
    # Onde guardar os 235 GB. So pergunta na PRIMEIRA vez: quem ja escolheu nao quer ser
    # perguntado de novo toda vez que roda o setup so para conferir alguma coisa.
    if "--conferir" not in sys.argv and not (AQUI / ("caminhos.bat" if WIN else "caminhos.sh")).is_file():
        try:
            sys.path.insert(0, str(AQUI))
            import escolher_pasta
            escolher_pasta.escolher(AQUI)
        except (EOFError, KeyboardInterrupt):
            print("\n   Tudo bem, fica onde esta. Rode 'python escolher_pasta.py' quando quiser.")
        except Exception as exc:
            cuidado("Nao consegui perguntar onde instalar (%s). Fica onde esta." % exc)

    comfy = achar_comfy()
    conferir_modelos(comfy)
    instalar_dependencias(comfy)
    conferir_configuracao()
    bat = criar_atalho(comfy)

    print("\n" + "=" * 66)
    if _problemas:
        print("  PAREI EM %d PROBLEMA(S):" % len(_problemas))
        for p in _problemas:
            print("   - " + p.splitlines()[0])
        print("\n  Resolva e rode de novo: python setup.py")
        return 1
    if _avisos:
        print("  PRONTO, com %d aviso(s):" % len(_avisos))
        for a in _avisos:
            print("   - " + a.splitlines()[0])
        print("\n  Da para abrir assim mesmo: o que falta aparece como nao instalado.")
    else:
        print("  PRONTO. Esta tudo no lugar.")
    print("\n  Abra o painel:  %s" % (bat.name if bat else "python estudio/server.py"))
    print("  Depois:         http://127.0.0.1:8194")
    print("  Primeira vez?   leia USAR.md")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(main())
