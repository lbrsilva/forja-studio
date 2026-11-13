r"""Abre o Forja Studio sem nenhuma janela preta.

Isto e o alvo do icone da Area de Trabalho. Roda com `pythonw.exe` (o Python SEM
console), entao a pessoa clica no icone e ve o navegador - mais nada.

O que ele faz, nesta ordem:

 1. abre JA a tela de espera (`web/aguarde.html`), direto do disco. E um arquivo HTML
    comum: funciona com tudo desligado, sem servidor nenhum, porque o navegador le do
    disco. E a primeira coisa que a pessoa ve, em menos de um segundo;
 2. ve se o estudio ja esta no ar. Se estiver, a propria tela de espera entra sozinha;
 3. se nao estiver, liga o estudio ESCONDIDO e sai. A tela de espera fica batendo na
    porta e entra quando ele atender.

Por que a tela de espera existe: um arquivo .html aberto do disco NAO consegue ligar
programa nenhum - o navegador proibe, e ainda bem. Entao ela nao liga nada: quem liga
e este programa, e ela so mostra a cara bonita enquanto isso acontece e entra sozinha
quando fica pronto. Antes, clicar antes da hora dava o "nao foi possivel conectar" do
navegador, que parece defeito e nao e.

O estudio sozinho gasta ~44 MB e NAO acende a placa de video (medido em 04/11/2026,
com tudo ligado: ComfyUI 214 MB + placa, estudio 44 MB e fora da lista da placa).
Quem acende a placa sao as IAs, e elas so ligam quando a pessoa clica nos botoes.
"""
import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import plataforma

plataforma.completar_path()

AQUI = Path(__file__).resolve().parent          # ...\estudio
RAIZ = AQUI.parent                              # a pasta do projeto
PORTA = int(os.environ.get("ESTUDIO_PORTA") or 8194)
ENDERECO = f"http://127.0.0.1:{PORTA}"
ESPERA = AQUI / "web" / "aguarde.html"


def no_ar(porta=PORTA, segundos=0.6):
    """True se alguem atende nessa porta aqui na maquina."""
    try:
        with socket.create_connection(("127.0.0.1", porta), timeout=segundos):
            return True
    except OSError:
        return False


def python_do_projeto():
    """O python.exe que roda o estudio. Sem console: pythonw.exe quando existir."""
    if not plataforma.WIN:
        comfy = _ambiente().get("ESTUDIO_COMFY_DIR")
        proprio = (Path(comfy).parent / "venv" / "bin" / "python") if comfy else plataforma.python_comfy(RAIZ)
        return proprio if proprio.is_file() else Path(sys.executable)
    base = RAIZ / "ComfyUI_windows_portable" / "python_embeded"
    for nome in ("pythonw.exe", "python.exe"):
        p = base / nome
        if p.is_file():
            return p
    # fora do pacote (a maquina de desenvolvimento), vale o python que esta rodando isto
    atual = Path(sys.executable)
    semjanela = atual.with_name("pythonw.exe")
    return semjanela if semjanela.is_file() else atual


def _ambiente():
    env = dict(os.environ)
    caminhos = RAIZ / "caminhos.sh"
    if not plataforma.WIN and caminhos.is_file():
        for linha in caminhos.read_text(encoding="utf-8").splitlines():
            if linha.startswith("export ") and "=" in linha:
                chave, _, valor = linha[7:].partition("=")
                env[chave.strip()] = valor.strip().strip('"')
    return env


def mostrar(endereco):
    """Abre um endereco no navegador. Devolve True se ALGUEM aceitou abrir.

    O `webbrowser.open()` devolve True/False e a gente ignorava o retorno. Quando ele
    devolve False nao abre nada - e, sob `pythonw.exe`, isso vira "cliquei no icone e nao
    aconteceu nada", sem erro nenhum em lugar nenhum. Era o sintoma exato de 12/11/2026.

    Por isso ha um segundo caminho: o `os.startfile`, que e o proprio Windows abrindo o
    endereco com o programa padrao. Se os dois recusarem, quem chamou avisa a pessoa.
    """
    try:
        if webbrowser.open(endereco):
            return True
    except Exception:
        pass
    if os.name == "nt":
        try:
            os.startfile(endereco)      # noqa: S606 - e o Windows abrindo, nao um shell
            return True
        except (OSError, ValueError, AttributeError):
            pass
    return False


REGISTRO = AQUI / "nao_abriu.txt"
PAGINA_DE_ERRO = AQUI / "web" / "nao_abriu.html"


def contar_o_problema(titulo, detalhe, como_resolver):
    """Escreve o que houve e ABRE uma pagina dizendo. Sem console, e o unico jeito de falar.

    Antes isto nao existia: com `pythonw.exe` nao ha janela, e todo erro sumia. A pessoa
    clicava no icone e nao acontecia nada - nem erro, nem tela, nem arquivo.
    """
    try:
        REGISTRO.write_text(f"{titulo}\n\n{detalhe}\n\n{como_resolver}\n", encoding="utf-8")
    except OSError:
        pass

    def esc(s):
        return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    html = f"""<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<title>Forja Studio - nao consegui abrir</title>
<style>
 :root {{ color-scheme: dark; }}
 body {{ background:#14161a; color:#e8e8ea; font:16px/1.6 system-ui,sans-serif;
         margin:0; padding:48px 24px; display:flex; justify-content:center; }}
 main {{ max-width:720px; }}
 h1 {{ font-size:24px; margin:0 0 4px; color:#ff8a5c; }}
 p.sub {{ margin:0 0 28px; color:#9aa0a6; }}
 pre {{ background:#0d0f12; border:1px solid #2a2e35; border-radius:10px;
        padding:16px; overflow:auto; font-size:13px; color:#c9d1d9; white-space:pre-wrap; }}
 h2 {{ font-size:16px; margin:28px 0 8px; color:#d7f26a; }}
 code {{ background:#0d0f12; padding:2px 6px; border-radius:5px; font-size:13px; }}
</style>
<main>
<h1>{esc(titulo)}</h1>
<p class="sub">O Forja Studio tentou abrir e parou aqui. Isto nao e a sua tela normal.</p>
<h2>O que aconteceu</h2>
<pre>{esc(detalhe)}</pre>
<h2>Como resolver</h2>
<pre>{esc(como_resolver)}</pre>
<p class="sub" style="margin-top:28px">Este texto tambem ficou salvo em<br>
<code>{esc(REGISTRO)}</code></p>
</main></html>"""
    try:
        PAGINA_DE_ERRO.parent.mkdir(parents=True, exist_ok=True)
        PAGINA_DE_ERRO.write_text(html, encoding="utf-8")
        mostrar(PAGINA_DE_ERRO.as_uri())
    except OSError:
        pass
    return 1


FALTA_MESMO = ("aiohttp", "cryptography")


def faltando(py):
    """Quais bibliotecas do requirements.txt faltam NESTE Python. Lista vazia = tudo certo.

    Conferir antes vale a pena: sem isto, o `server.py` morre na primeira linha, o erro vai
    para o lixo e a tela de espera roda para sempre sem ninguem saber por que.
    """
    codigo = ("import importlib.util,sys;"
              "print(','.join(m for m in %r if importlib.util.find_spec(m) is None))"
              % (FALTA_MESMO,))
    try:
        r = subprocess.run([str(py), "-s", "-c", codigo], capture_output=True, text=True,
                           timeout=30,
                           creationflags=0x08000000 if os.name == "nt" else 0)
    except (OSError, subprocess.SubprocessError) as exc:
        return ["(nao consegui nem rodar este Python: %s)" % exc]
    if r.returncode != 0:
        return ["(este Python respondeu com erro: %s)" % (r.stderr or "").strip()[:300]]
    return [m for m in (r.stdout or "").strip().split(",") if m]


def ligar_escondido():
    """Liga o estudio sem abrir janela. Devolve o processo, ou None se nao deu."""
    py = python_do_projeto()
    servidor = AQUI / "server.py"
    if not servidor.is_file():
        return None

    criar = 0
    if plataforma.WIN:
        # CREATE_NO_WINDOW: nenhum console aparece, nem por um piscar.
        # DETACHED_PROCESS nao serve aqui: ele solta o processo do nosso e o estudio
        # morreria junto com algumas sessoes. CREATE_NO_WINDOW basta e e mais simples.
        criar = 0x08000000
    # O erro do servidor ia para DEVNULL - ou seja, para o lixo. Quando ele morria na
    # primeira linha (falta aiohttp, Python errado), ninguem nunca soube por que.
    try:
        registro = open(AQUI / "servidor_saida.txt", "w", encoding="utf-8", errors="replace")
    except OSError:
        registro = subprocess.DEVNULL
    try:
        return subprocess.Popen(
            [str(py), "-s", str(servidor)],
            cwd=str(RAIZ), env=_ambiente(), stdin=subprocess.DEVNULL, stdout=registro, stderr=subprocess.STDOUT,
            **({"creationflags": criar} if plataforma.WIN else {"start_new_session": True}))
    except OSError:
        return None


def main():
    # 1) a cara do produto aparece primeiro, mesmo com tudo desligado.
    #    Se por algum motivo o arquivo nao estiver aqui, vai direto no endereco: pior
    #    experiencia, mas nunca um clique que nao faz nada.
    if ESPERA.is_file():
        tela, onde = ESPERA.as_uri() + f"?porta={PORTA}", ENDERECO
    else:
        tela, onde = ENDERECO, ENDERECO
    if not mostrar(tela):
        # Nenhum navegador aceitou. Antes disto a funcao terminava com codigo 0 e a
        # pessoa ficava achando que o icone estava quebrado - sem nada para ler.
        return contar_o_problema(
            "Nao consegui abrir o seu navegador",
            "Pedi ao Windows para abrir:\n  %s\n\ne ele nao abriu. Isto costuma ser "
            "navegador padrao nao definido neste usuario do Windows." % tela,
            "Abra o seu navegador na mao e va em:\n  %s\n\nPara resolver de vez: "
            "Configuracoes do Windows > Aplicativos > Aplicativos padrao, e escolha um "
            "navegador." % onde)

    # 2) ja estava ligado? entao nao liga em dobro - a tela de espera entra sozinha.
    if no_ar():
        return 0

    # 3) antes de ligar: este Python tem o que o estudio precisa?
    py = python_do_projeto()
    falta = faltando(py)
    if falta:
        return contar_o_problema(
            "Falta instalar as bibliotecas do estudio",
            "O Python que o atalho usa e:\n  %s\n\nE nele falta: %s" % (py, ", ".join(falta)),
            "Abra o Prompt de Comando NA PASTA DO FORJA STUDIO e rode:\n\n"
            '  "%s" -m pip install -r requirements.txt\n\n'
            "Depois clique no icone de novo." % py)

    # 4) liga escondido. Daqui para a frente quem acompanha e a tela de espera.
    if ligar_escondido() is None:
        return contar_o_problema(
            "Nao consegui ligar o estudio",
            "Tentei ligar com:\n  %s\n\ne o Windows nao deixou o programa comecar." % py,
            "Veja se o antivirus bloqueou, e se o arquivo acima existe mesmo.")

    # Fica por perto so o suficiente para o processo filho se firmar. Sem isto, em
    # alguns casos o Windows derruba o filho junto com o pai que sai rapido demais.
    for _ in range(40):          # ate 20 s
        if no_ar(segundos=0.3):
            return 0
        time.sleep(0.5)

    # Ligou e nao atendeu em 20 s: o motivo esta na saida que agora a gente GUARDA.
    saida = ""
    try:
        saida = (AQUI / "servidor_saida.txt").read_text(encoding="utf-8",
                                                        errors="replace").strip()
    except OSError:
        pass
    return contar_o_problema(
        "O estudio ligou mas nao atendeu",
        "Esperei 20 segundos na porta %d e ninguem atendeu.\n\n"
        "Isto foi o que o estudio escreveu:\n\n%s" % (PORTA, saida or "(nada)"),
        "Se ai em cima aparecer 'ModuleNotFoundError', falta uma biblioteca: rode\n"
        "  pip install -r requirements.txt\n"
        "com o Python da pasta. Se aparecer 'Address already in use', ja ha outra\n"
        "coisa na porta %d." % PORTA)


if __name__ == "__main__":
    # Com pythonw.exe nao ha console: uma excecao solta somem sem deixar rastro, e o
    # clique no icone vira "nao acontece nada". Por isso TUDO passa por aqui.
    try:
        sys.exit(main())
    except Exception:
        import traceback
        sys.exit(contar_o_problema(
            "O Forja Studio tropecou ao abrir",
            traceback.format_exc(),
            "Mande este texto para quem cuida do estudio."))
