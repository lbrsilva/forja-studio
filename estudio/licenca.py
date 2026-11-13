"""Conta e licenca do lado do painel (o que roda na maquina de quem usa).

O que este arquivo faz:
  1. monta a impressao digital da maquina a partir de TRES campos que nao mudam;
  2. fala com o servidor de contas para criar conta, entrar, sair e renovar;
  3. confere a ASSINATURA da licenca com a chave publica que vem no pacote.

As ferramentas locais sao de graca: entrar e para a conta existir (e para o dia em que
houver plano pago com API). Quem gera e a placa de quem usa, e isso nunca foi cobrado.

Por que a chave publica estar aqui a vista nao e descuido:
  ela so CONFERE assinatura, nunca cria. Fabricar uma licenca exige a chave PRIVADA, que
  mora no servidor e nunca sai de la. Criptografar este arquivo seria teatro: o painel
  precisa abrir a licenca, entao a chave de abrir estaria aqui do mesmo jeito.

O limite honesto: quem edita o codigo arranca qualquer verificacao daqui. O que protege o
plano pago nao e esta conferencia - e o fato de a chave da API ficar no servidor.
"""
import asyncio
import base64
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path

import plataforma

AQUI = Path(__file__).resolve().parent
ARQUIVO = AQUI / "licenca.json"
CHAVE_PUBLICA = AQUI / "chave_publica.pem"
# O servidor de contas do Forja. O endereco de verdade e o PADRAO, porque o pacote vai
# para maquinas que nao tem servidor nenhum rodando dentro. A variavel de ambiente e so
# para desenvolvimento: FORJA_CONTAS_URL=http://127.0.0.1:8196 fala com uma copia local.
# No ar desde 04/11/2026. Ver contas/vps/instalar.sh.
SERVIDOR = os.environ.get("FORJA_CONTAS_URL") or "https://jers.viverbemcomoesta.xyz"

# Tempero fixo da impressao digital. NAO e segredo (esta num projeto aberto): ele serve
# para o servidor nunca receber algo que volte ao numero de serie, e para o mesmo PC dar
# resumos diferentes em programas diferentes. O segredo do sistema e a chave privada.
TEMPERO = b"forja-studio/impressao/v1"

# Os campos da impressao digital, em ordem. Os tres primeiros sao do WMI (PowerShell); os
# dois ultimos, do registro do Windows. O servidor precisa conhecer esta mesma lista.
CAMPOS = ("placa_uuid", "placa_serie", "disco_serie", "windows_id", "instalacao_id")

# Como cada campo se chama em portugues, para a tela explicar o que faltou.
NOME_DO_CAMPO = {"placa_uuid": "o codigo da placa-mae",
                 "placa_serie": "a serie da placa-mae",
                 "disco_serie": "a serie do disco",
                 "windows_id": "o identificador do Windows",
                 "instalacao_id": "a instalacao do Windows"}

# Quantos dias o painel aguenta sem conseguir falar com o servidor depois de a licenca
# vencer.
#
# 11/11/2026: era 3 e virou ZERO, por decisao dele. A licenca passou a valer 24 HORAS
# (CONTAS_DIAS=1 no servidor), e a regra ficou assim: o painel fala com o servidor toda
# vez que abre e de 6 em 6 horas; quem passar de 24 horas sem conseguir falar fica
# travado e precisa ligar a internet.
#
# O que isso compra: a conta revogada para em UM DIA, nao em dez. O que isso custa: quem
# ficar um dia inteiro sem internet nao abre a configuracao. Foi a troca escolhida.
#
# Folga zero sozinha nao bastaria: a chave do cofre guardada aqui (DPAPI) abria os
# presets sem perguntar nada a ninguem. Ver abrir_cofre(), que agora exige licenca viva
# ANTES de usar a chave guardada - e esse o freio que de fato trava as 24 horas.
DIAS_DE_FOLGA = 0

# O recado da janela estourada. Fica numa constante porque aparece em tres lugares, e
# tres copias de um texto viram, com o tempo, tres textos diferentes - e a pessoa le o
# mais confuso dos tres.
SEM_FALAR_24H = ("Faz mais de 24 horas que o painel nao fala com o servidor. Ligue a "
                 "internet e abra o painel de novo para liberar as configuracoes.")

_impressao = None       # a leitura da maquina e lenta (~1 s): le uma vez por execucao
_motivo = None          # por que a ultima conferencia de licenca falhou (ver conferir())
_ultimo_erro = None
_no_ar = {"quando": 0, "valor": None}   # o servidor de contas respondeu? (guardado 60 s)


# ------------------------------------------------------- impressao digital da maquina
def _ler_maquina_windows():
    """Os tres campos, numa chamada so de PowerShell.

    MAC ficou de fora de proposito: medido nesta maquina em 03/11/2026, ela tem 6 MACs
    (2 ligados), um deles sorteado pelo proprio Windows por privacidade, outro do Hyper-V -
    e MAC se troca em dois cliques. Como trava, nao tranca nada.

    A serie do BIOS tambem ficou de fora: nesta maquina ela e literalmente "System Serial
    Number", o texto que vem de fabrica. Metade do mundo bate no mesmo valor.
    """
    ps = (
        "$ErrorActionPreference='SilentlyContinue';"
        "$p=Get-CimInstance Win32_ComputerSystemProduct;"
        "$b=Get-CimInstance Win32_BaseBoard;"
        "$d=Get-CimInstance Win32_DiskDrive | Where-Object {$_.Index -eq 0} | "
        "Select-Object -First 1;"
        "[pscustomobject]@{placa_uuid=$p.UUID; placa_serie=$b.SerialNumber; "
        "disco_serie=$d.SerialNumber} | ConvertTo-Json -Compress"
    )
    global _ultimo_erro
    try:
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-Command", ps],
            capture_output=True, text=True, timeout=25,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as exc:
        _ultimo_erro = f"O Windows nao deixou ler a identificacao da maquina: {exc}"
        return {}
    # 12/11/2026: o codigo de saida era IGNORADO. PowerShell que morria pela metade devolvia
    # stdout vazio, o json virava {} e os tres campos sumiam SEM MOTIVO NENHUM na tela.
    saida = (r.stdout or "").strip()
    if r.returncode != 0 and not saida:
        _ultimo_erro = ("O Windows nao respondeu a leitura da placa e do disco "
                        f"(codigo {r.returncode}). " + ((r.stderr or "").strip()[:160]))
        return {}
    try:
        return json.loads(saida or "{}")
    except ValueError:
        _ultimo_erro = "A leitura da placa e do disco veio ilegivel."
        return {}


def _ler_registro_windows():
    """Dois identificadores do proprio Windows, lidos SEM PowerShell e SEM WMI.

    Existem desde que o Windows foi instalado, nao precisam de administrador e nao passam
    pelo servico do WMI - que e justamente o que falha nas maquinas novas e nas virtuais.
    Sao a segunda perna da identificacao: com elas, o WMI inteiro pode cair e a pessoa
    continua conseguindo criar a conta.

    O que eles custam, dito na cara: dois PCs clonados da MESMA imagem do Windows nascem com
    os mesmos valores, e para a conta eles contam como UMA maquina. Quem clona ja clonava a
    placa-mae virtual junto, entao isso nao abriu porta nova - mas e bom estar escrito.
    """
    if os.name != "nt":
        return {}
    fora = {}
    try:
        import winreg
    except Exception:
        return fora

    def _ler(raiz, chave, valor):
        try:
            with winreg.OpenKey(raiz, chave, 0,
                                winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)) as k:
                v, _ = winreg.QueryValueEx(k, valor)
            return str(v).strip()
        except OSError:
            return None

    # o identificador da instalacao do Windows: existe em 100% das maquinas
    fora["windows_id"] = _ler(winreg.HKEY_LOCAL_MACHINE,
                              r"SOFTWARE\Microsoft\Cryptography", "MachineGuid")

    # um segundo, de origem diferente. Se ele nao existir, monta-se um a partir do numero
    # do produto mais a data da instalacao - que juntos ja nao se repetem a toa.
    segundo = _ler(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\SQMClient", "MachineId")
    if not segundo:
        nt = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
        produto = _ler(winreg.HKEY_LOCAL_MACHINE, nt, "ProductId")
        quando = _ler(winreg.HKEY_LOCAL_MACHINE, nt, "InstallDate")
        segundo = f"{produto}|{quando}" if produto and quando else None
    fora["instalacao_id"] = segundo
    return fora


# Valores de fabrica que aparecem em milhares de maquinas: se vier um destes, o campo nao
# identifica nada e e melhor descartar do que fingir que serve.
LIXO = {"", "none", "null", "0", "to be filled by o.e.m.", "to be filled by oem",
        "system serial number", "default string", "not specified", "not available",
        "o.e.m.", "unknown", "00000000-0000-0000-0000-000000000000", "123456789",
        "x.x.x", "base board serial number", "n/a", "invalid"}


def _vale(v):
    v = re.sub(r"\s+", " ", str(v or "")).strip()
    return v if len(v) >= 5 and v.lower() not in LIXO else None


def _resumir(v):
    return hashlib.sha256(TEMPERO + v.strip().lower().encode("utf-8", "replace")).hexdigest()


def impressao(recarregar=False):
    """Um resumo embaralhado de cada campo. O numero de serie nunca sai desta maquina.

    Campo que nao der para ler, ou que vier com valor de fabrica, vai como None. O servidor
    aceita a maquina com 2 campos batendo - entao trocar o HD nao tranca ninguem de fora.

    Os tres primeiros vem do WMI; os dois ultimos, do registro. Duas fontes de proposito:
    ate 11/11/2026 as tres vinham da MESMA chamada de PowerShell, e quando ela falhava a
    pessoa simplesmente nao conseguia criar conta no proprio computador.
    """
    global _impressao
    if _impressao is not None and not recarregar:
        return _impressao
    if plataforma.MAC:
        cru = plataforma.maquina_mac()
    else:
        cru = dict(_ler_maquina_windows())
        cru.update(_ler_registro_windows())
    _impressao = {campo: (_resumir(bom) if (bom := _vale(cru.get(campo))) else None)
                  for campo in CAMPOS}
    return _impressao


def quantos_campos():
    return sum(1 for v in impressao().values() if v)


def campos_lidos():
    """Quais campos deram e quais nao deram - para a tela poder DIZER o que faltou.

    A tela antiga so sabia contar. Quando dava menos de dois, ela mandava "abra o estudio
    do jeito de sempre e tente de novo", que nao ajuda ninguem a resolver nada.
    """
    imp = impressao()
    return {"lidos": [c for c in CAMPOS if imp.get(c)],
            "faltaram": [c for c in CAMPOS if not imp.get(c)],
            "total": len(CAMPOS)}


# ------------------------------------------------------------------ conferir assinatura
def _desb64(txt):
    txt = txt + "=" * (-len(txt) % 4)
    return base64.urlsafe_b64decode(txt.encode())


def conferir(licenca):
    """Devolve os dados da licenca se a assinatura for da nossa chave; senao, None.

    Importante: confere a assinatura sobre os BYTES que vieram, nunca sobre um JSON
    remontado aqui. Reescrever o JSON muda um espaco e a conferencia falha sem motivo.

    ⭐ 11/11/2026 - POR QUE ISTO GUARDA O MOTIVO AGORA

    Esta funcao tinha um `except Exception: return None` cego. Quando ela falhava, o
    painel ficava com "entrou = nao" para sempre e NINGUEM descobria por que: nem quem
    instalou, nem o log, nem o dono. A pessoa entrava, a tela voltava a pedir, ela
    entrava de novo.

    Foi o que aconteceu com o primeiro usuario de fora (11/11, 00:54-00:56): CINCO
    entradas no servidor, zero erro de senha, uma so maquina - e nenhuma das cinco
    sessoes foi usada depois de nascer. O login funcionava; o painel e que nao se
    considerava logado, calado.

    Engolir a excecao nao foi o defeito - foi o que escondeu o defeito. Agora cada
    motivo tem a sua frase, em portugues, e ela chega a tela e ao log.
    """
    global _motivo
    if not isinstance(licenca, dict):
        _motivo = "Nao ha licenca guardada nesta maquina."
        return None
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
    except Exception as exc:
        _motivo = ("Falta a biblioteca 'cryptography' nesta instalacao, e sem ela o "
                   "painel nao consegue conferir a licenca. Rode o instalador de novo. "
                   f"({exc.__class__.__name__})")
        return None
    try:
        pem = CHAVE_PUBLICA.read_bytes()
    except OSError as exc:
        _motivo = (f"Nao achei o arquivo da chave publica ({CHAVE_PUBLICA.name}) na pasta "
                   "do estudio. Baixe o pacote de novo. "
                   f"({exc.__class__.__name__})")
        return None
    try:
        pub = load_pem_public_key(pem)
    except Exception:
        _motivo = ("O arquivo da chave publica esta corrompido. Baixe o pacote de novo.")
        return None
    if "dados" not in licenca or "assinatura" not in licenca:
        _motivo = "A licenca guardada esta incompleta. Entre na conta de novo."
        return None
    try:
        cru = _desb64(licenca["dados"])
        assinatura = _desb64(licenca["assinatura"])
    except Exception:
        _motivo = "A licenca guardada esta ilegivel. Entre na conta de novo."
        return None
    try:
        pub.verify(assinatura, cru)
    except Exception:
        _motivo = ("A licenca desta maquina nao foi assinada pela chave deste pacote. "
                   "Quase sempre e pacote e servidor de versoes diferentes: baixe o "
                   "pacote de novo e entre na conta.")
        return None
    try:
        dados = json.loads(cru.decode("utf-8"))
    except Exception:
        _motivo = "A licenca abriu mas o conteudo nao faz sentido. Entre na conta de novo."
        return None
    _motivo = None
    return dados


def motivo_da_recusa():
    """Por que a ultima conferencia falhou, em portugues. None quando deu certo.

    Serve para a tela e para o log. Sem isto, "entrou = nao" nao se distingue de
    "nunca entrou", e os dois pedem coisas opostas a quem esta na frente do painel.
    """
    return _motivo


# ------------------------------------------------------------------ o arquivo na maquina
def ler():
    try:
        d = json.loads(ARQUIVO.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception as exc:
        print(f"[licenca] licenca.json ilegivel: {exc!r}", flush=True)
        return {}


def gravar(d):
    """Grava a licenca no disco. Levanta ErroDeConta, em portugues, se nao der.

    ⭐ 11/11/2026 - O SEGUNDO JEITO DE O LOGIN NAO COLAR

    Isto nao tratava erro nenhum. Se a pasta do estudio nao aceita escrita - e o caso
    classico e instalar dentro de "Arquivos de Programas", que pede administrador -,
    acontecia o seguinte:

      1. o servidor criava a sessao (ja esta la, contada no gerenciador);
      2. a gravacao aqui estourava PermissionError;
      3. o api_conta_entrar so pega ErroDeConta, entao subia um 500 cru;
      4. a tela dizia uma falha generica e continuava pedindo login;
      5. a pessoa entrava de novo. E de novo.

    Bate com o que o banco mostrou do primeiro usuario de fora: cinco sessoes criadas,
    NENHUMA usada depois de nascer, zero erro de senha. A sessao nascia e o painel nunca
    chegava a usa-la.

    Agora o erro vira recado: diz o caminho, o motivo e o que fazer.
    """
    tmp = ARQUIVO.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, ARQUIVO)
    except OSError as exc:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise ErroDeConta(
            f"Entrei na sua conta, mas nao consegui guardar a licenca em {ARQUIVO}: "
            f"{exc.strerror or exc}. Quase sempre e pasta que nao aceita escrita - por "
            "exemplo dentro de Arquivos de Programas. Instale o Forja numa pasta sua, "
            "como C:\\Forja Studio, e entre de novo.", 500) from exc


def apagar():
    try:
        ARQUIVO.unlink()
    except FileNotFoundError:
        pass


# ------------------------------------------------------------------------------ estado
def estado():
    """O que a tela precisa saber. Nunca devolve o token nem a senha."""
    guardado = ler()
    dados = conferir(guardado.get("licenca"))
    if not dados:
        # O motivo ESPECIFICO primeiro (ver conferir()): "nao confere com a nossa chave"
        # servia para tudo e nao ajudava ninguem - a pessoa so sabia que nao entrou.
        return {"entrou": False, "servidor": SERVIDOR,
                "campos_da_maquina": quantos_campos(),
                "maquina": campos_lidos(),
                "maquina_faltou": [NOME_DO_CAMPO[c] for c in campos_lidos()["faltaram"]],
                "tem_licenca": bool(guardado.get("licenca")),
                "motivo": (_motivo if guardado.get("licenca") else None) or _ultimo_erro}
    agora = int(time.time())
    vence_em = dados.get("validade", 0) - agora
    folga = DIAS_DE_FOLGA * 86400
    return {"entrou": vence_em > -folga,
            "nome": dados.get("nome"), "email": dados.get("email"),
            "plano": dados.get("plano", "gratis"),
            "vaga": dados.get("vaga"), "vagas": guardado.get("vagas"),
            "validade": dados.get("validade"),
            "dias": round(vence_em / 86400, 1),
            "vencida": vence_em <= 0,
            "na_folga": -folga < vence_em <= 0,
            "servidor": SERVIDOR, "campos_da_maquina": quantos_campos(),
            "maquina": campos_lidos()}


def precisa_renovar():
    """Renova quando falta menos de um terco da validade - nao em cima da hora."""
    dados = conferir(ler().get("licenca"))
    if not dados:
        return False
    total = max(1, dados.get("validade", 0) - dados.get("emitido", 0))
    return (dados["validade"] - int(time.time())) < total / 3


# ------------------------------------------------------------------ falar com o servidor
class ErroDeConta(Exception):
    def __init__(self, msg, status=400):
        super().__init__(msg)
        self.status = status


async def servidor_no_ar():
    """O servidor de contas respondeu nos ultimos 60 segundos?

    Isto existe por causa de quem BAIXA o estudio. Sem esta conferencia, a pessoa instala,
    abre, cai na tela de entrar - e nao consegue entrar, porque o servidor de contas nao
    existe na maquina dela. Ficaria trancada para fora do proprio computador por causa de
    uma tela que eu pus. Quando nao ha servidor, o estudio abre e avisa.

    O lado fraco e honesto: quem derrubar o servidor de proposito tambem passa por aqui.
    Nao tem conserto de verdade, porque o codigo roda na maquina dela. O que protege o
    plano pago nao e esta porta - e a chave da API ficar do lado de la.
    """
    import aiohttp
    agora = time.time()
    if agora - _no_ar["quando"] < 60 and _no_ar["valor"] is not None:
        return _no_ar["valor"]
    valor = False
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4)) as s:
            async with s.get(SERVIDOR + "/api/saude") as r:
                valor = r.status == 200
    except Exception:
        valor = False
    _no_ar.update({"quando": agora, "valor": valor})
    return valor


async def _pedir(caminho, corpo):
    import aiohttp
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=25)) as s:
            async with s.post(SERVIDOR + caminho, json=corpo) as r:
                txt = await r.text()
                if r.status >= 400:
                    raise ErroDeConta(txt.strip()[:300] or f"O servidor respondeu {r.status}.",
                                      r.status)
                return json.loads(txt)
    except ErroDeConta:
        raise
    except asyncio.TimeoutError:
        raise ErroDeConta("O servidor de contas nao respondeu. Veja a sua internet.", 504)
    except Exception as exc:
        raise ErroDeConta(f"Nao consegui falar com o servidor de contas: {exc}", 502)


def _guardar_resposta(r, token=None):
    dados = conferir(r.get("licenca"))
    if not dados:
        raise ErroDeConta("O servidor mandou uma licenca que nao confere com a nossa chave. "
                          "Por seguranca, nao vou guardar.", 502)
    guardado = ler()
    guardado.update({"licenca": r["licenca"], "servidor": SERVIDOR,
                     "vagas": (r.get("conta") or {}).get("vagas"),
                     "guardada_em": int(time.time())})
    if token:
        guardado["token"] = token
    gravar(guardado)
    return dados


async def criar_conta(nome, email, telefone, senha):
    if quantos_campos() < 2:
        raise ErroDeConta(_ultimo_erro or "Nao consegui identificar esta maquina.", 400)
    r = await _pedir("/api/conta/criar", {"nome": nome, "email": email, "telefone": telefone,
                                          "senha": senha, "maquina": impressao()})
    _guardar_resposta(r, r.get("token"))
    return estado()


async def entrar(email, senha):
    if quantos_campos() < 2:
        raise ErroDeConta(_ultimo_erro or "Nao consegui identificar esta maquina.", 400)
    r = await _pedir("/api/conta/entrar", {"email": email, "senha": senha,
                                           "maquina": impressao()})
    _guardar_resposta(r, r.get("token"))
    return estado()


async def renovar():
    """Volta True se renovou, False se nao deu para falar com o servidor (e a licenca
    velha continua valendo ate vencer). Levanta ErroDeConta quando o servidor RECUSA -
    conta revogada, maquina bloqueada, licenca copiada de outro PC."""
    guardado = ler()
    if not guardado.get("token"):
        return False
    try:
        r = await _pedir("/api/licenca/renovar", {"token": guardado["token"],
                                                  "maquina": impressao()})
    except ErroDeConta as exc:
        if exc.status in (401, 403):
            # o servidor disse NAO. Apaga a licenca: a tela volta a pedir login.
            apagar()
            raise
        return False
    _guardar_resposta(r)
    return True


async def abrir_cofre():
    """Pega a chave dos presets no servidor e abre o cofre. True se abriu.

    Ordem de propósito:
      1. se nao existe cofre (maquina de desenvolvimento), nao ha o que abrir;
      2. com a licenca VIVA, tenta a chave guardada aqui - e o que faz o painel abrir
         rapido e sem internet dentro da janela de 24 horas;
      3. licenca vencida, ou sem chave guardada: pede ao servidor, e guarda para a proxima.

    A chave guardada passa pelo DPAPI do Windows: presa a esta conta nesta maquina.
    Copiar o arquivo para outro PC nao adianta. Ver cofre.py.
    """
    import cofre

    if not cofre.existe():
        return True
    if cofre.aberto():
        return True

    # ⭐ 11/11/2026 - A JANELA DE 24 HORAS.
    #
    # Antes, a chave guardada aqui abria o cofre sem perguntar nada: bastava entrar na
    # conta UMA vez e o painel abria a configuracao para sempre, mesmo sem internet,
    # mesmo com a conta revogada - a licenca vencia e ninguem olhava.
    #
    # Agora a chave guardada so vale enquanto a licenca estiver viva. Licenca de 24 h +
    # folga zero = quem passar um dia sem falar com o servidor nao abre a configuracao,
    # e a tela diz por que. Com internet a renovacao acontece sozinha (ao abrir e de 6 em
    # 6 horas) e a pessoa nao ve nada disso.
    e = estado()
    # Com folga ZERO, "nao entrou" e "vencida" querem dizer a mesma coisa; os dois ficam
    # escritos porque a folga pode voltar a ser maior que zero um dia.
    fora_da_janela = (not e.get("entrou")) or bool(e.get("vencida"))
    if fora_da_janela:
        # A chave guardada vai embora JUNTO: se ficasse, bastaria abrir o painel offline
        # na proxima vez para ela servir de novo, e a janela nao valeria nada.
        cofre.esquecer_chave()
        cofre.trancar()
        # Nao sai aqui: se houver internet AGORA, o pedido abaixo renova e abre na hora.
    else:
        guardada = cofre.chave_guardada()
        if guardada and cofre.abrir(guardada):
            return True

    g = ler()
    if not g.get("token"):
        cofre._erro = ("Entre na sua conta para o painel carregar as configuracoes."
                       if not fora_da_janela else SEM_FALAR_24H)
        return False
    try:
        # 11/11/2026: diz QUAL cofre esta aqui. Cada montagem tem a sua chave, e o
        # cabecalho do cofre carrega o identificador dela desde 04/11 (so que ninguem
        # usava). Sem isto o servidor teria de ter uma chave unica e eterna - e, com o
        # arquivo cifrado publico no GitHub, uma chave eterna vazada abre tudo para
        # sempre. Ver chave_do_chaveiro() em contas/servidor.py.
        quem = cofre.id_do_cofre()
        r = await _pedir("/api/presets/chave",
                         {"token": g["token"], "maquina": impressao(),
                          "cofre_id": quem.hex() if quem else None})
    except ErroDeConta as exc:
        # Fora da janela, o motivo que importa e a janela - nao o texto da falha de rede.
        # Sem isto a tela diria "nao consegui falar com o servidor" e a pessoa nao
        # entenderia que o painel ficou travado porque passou de um dia.
        cofre._erro = SEM_FALAR_24H if fora_da_janela else str(exc)
        return False
    try:
        chave = _desb64(r.get("chave") or "")
    except Exception:
        cofre._erro = "O servidor mandou uma chave que eu nao entendi."
        return False
    if not cofre.abrir(chave):
        return False
    cofre.guardar_chave(chave)
    return True


async def sair():
    guardado = ler()
    if guardado.get("token"):
        try:
            await _pedir("/api/conta/sair", {"token": guardado["token"]})
        except ErroDeConta:
            pass  # sair da maquina nao pode depender de o servidor estar no ar
    apagar()
    # saiu da conta, perdeu as configuracoes: sem isto bastaria entrar uma vez e sair
    # para ficar com os presets abertos para sempre.
    try:
        import cofre
        cofre.trancar()
        cofre.esquecer_chave()
    except Exception:
        pass
    return {"ok": True}
