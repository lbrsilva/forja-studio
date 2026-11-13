***Português** · [English](README.en.md) · [Español](README.es.md)*

# Estúdio Local

Um painel só para gerar **imagem, vídeo e narração** no seu próprio computador, com IA de
código aberto. Sem assinatura, sem crédito, sem nuvem. Você instala uma vez e usa para sempre.

Não é um projeto de IA nova. As IAs aqui são públicas e qualquer um baixa. **O que este
projeto entrega é a configuração** — quais IAs valem a pena, ajustadas como, ligadas entre si
numa tela só. Foi montado num computador de verdade, fazendo vídeo de verdade: em 40 dias,
**2.253 gerações, 98,7% concluídas**.

> ### 📦 Para instalar: **5 GB**
>
> A plataforma inteira — o painel, a tela de conta, tudo — cabe em **~5 GB**. Nenhum
> modelo de IA precisa ser baixado antes. Você instala, abre e já está usando.
>
> **As IAs vêm depois**, uma por uma, pelo botão **"Falta instalar"** que aparece no
> cartão de cada uma, dentro do programa. Você baixa só as que quiser, quando quiser, e
> só as que o seu computador aguentar — a mais leve são 16,9 GB.
>
> Reserve **50 GB livres** para começar com folga (plataforma + a primeira IA).

> **Mac (Apple Silicon):** siga o [INSTALAR-MAC.md](INSTALAR-MAC.md). O resto deste texto vale para os dois sistemas.

## Em que pé está

**Este painel está em desenvolvimento e é usado todo dia por quem o escreveu.** Não é um
produto acabado: é uma montagem de trabalho que funciona, publicada para quem quiser a mesma
coisa na própria máquina.

As melhorias vêm do uso real — o que atrapalha o trabalho do dia é o que é consertado em
seguida. Se você usar e achar uma pedra no caminho, **abra uma issue contando o que você
estava tentando fazer**: é assim que as coisas entram na fila.

## O que dá para fazer

| aba | o que faz |
|---|---|
| **Imagem** | foto realista, ilustração, e transformar uma imagem sua em outra coisa |
| **Vídeo** | texto ou imagem viram vídeo com som |
| **Pessoa falando** | uma foto de frente + um texto viram alguém falando, com a boca sincronizada |
| **Narração** | texto vira voz no seu computador, **de graça** — criar uma voz pela descrição ou clonar a sua |
| **Canal automático** | a esteira inteira: texto → cenas → imagens → voz → vídeo montado |

E tem a parte que quase ninguém sabe que dá para fazer: **pedir para uma IA de código
escrever o atalho que automatiza o seu trabalho** — e ele roda nas IAs que você baixou, sem
pagar por geração.

- [BAT-FEITO-PELA-IA.md](BAT-FEITO-PELA-IA.md) — a ideia, e como pedir
- [LOTE-DE-VIDEOS.md](LOTE-DE-VIDEOS.md) — **fazer muitos vídeos de uma vez**: como arrumar as
  pastas, o que escrever, e a conta de tempo antes de começar

## 🟢 Para começar: 5,6 GB, não 275

A ordem é esta, e **nenhum modelo precisa ser baixado antes de você ver o programa**:

```
1.  a PLATAFORMA   →  ~5,6 GB   abre em minutos, já dá para entrar e navegar
2.  as IAs         →  depois, uma por uma, pelo BOTÃO dentro da tela
```

Lá dentro, cada IA mostra o próprio estado:

```
Z-Image Turbo        Falta instalar — 19,3 GB     ← clica e baixa
Qwen-Image 2512      instalada
```

Você baixa **só as que quiser**, quando quiser, e só as que a sua máquina aguentar. O
download roda em segundo plano, dá para usar o estúdio enquanto isso, e **se parar no
meio continua de onde parou**.

| para | reserve |
|---|---|
| só experimentar (plataforma + 1 IA leve) | **50 GB** |
| imagem bem servido | ~90 GB |
| tudo | 270 GB |

Quem só quer fazer imagem baixa **19,3 GB** e acabou.

---

## O que você precisa

> **Antes de baixar, leia [REQUISITOS.md](REQUISITOS.md).** Lá está quanto de disco
> cada IA ocupa, quanto você precisa se quiser só imagem ou só vídeo, e o que foi
> realmente medido contra o que é estimativa. São 235,7 GB: vale os dois minutos.

**O painel em si não pesa nada.** Com tudo ligado e nada gerando, medido: **2 GB de RAM e
1,6 GB de placa** — o painel sozinho são 80 MB. Quem pesa é a IA que você carrega.

| | mínimo | confortável |
|---|---|---|
| **Placa (VRAM)** | **12 GB** — só imagem | **16 GB** — o painel inteiro |
| **Memória (RAM)** | **16 GB** — só imagem | **32 GB**; com 64 GB nunca falta |
| **Disco** | **50 GB** para começar (plataforma + 1 IA) | **270 GB** com tudo |
| **Sistema** | Windows 10 ou 11 | |

Por que a placa de 12 GB roda um modelo de 20 GB: a ComfyUI **empurra para a RAM** o que não
cabe. Funciona — mas é a RAM que segura a conta, e por isso ela importa tanto quanto a placa.

O que cada IA carrega (medido nesta instalação):

| IA | soma dos modelos | maior arquivo |
|---|---|---|
| Krea 2 Turbo | 17,8 GB | 12,2 GB |
| LTX 2.5 | 28,3 GB | 14,3 GB |
| Apresentador | 27,6 GB | 15,5 GB |
| Qwen-Image 2512 | 29,6 GB | 19,0 GB |
| MiniMax H3 Referências | 41,4 GB | 19,5 GB |
| MiniMax H3 Fast | 40,6 GB | 20,6 GB |

> ⚠️ **Não economize na RAM.** Numa máquina de 16 GB de placa, rodar duas IAs grandes ao mesmo
> tempo fez uma cena de 1,5 minuto levar **58 minutos** — a máquina passou o tempo todo
> empurrando modelo entre a placa e o disco. Uma geração por vez, sempre.

> ⚠️ **Fale a verdade para si mesmo sobre o disco.** São 275 GB se você quiser tudo —
> mas você NÃO precisa de tudo para começar. Numa internet de
> 100 Mb isso é um dia inteiro. O instalador deixa você escolher trilhas menores.

## A máquina em que isto foi medido

Todo número deste repositório — tempo de geração, consumo de memória, peso de modelo — saiu
desta máquina, não de tabela de fabricante:

| | |
|---|---|
| **Placa** | NVIDIA GeForce RTX 5060 Ti **16 GB** (driver 616.92) |
| **Processador** | Intel Core i9-14900K (24 núcleos / 32 threads) |
| **Memória** | **64 GB** DDR5 a 6000 MHz (4 pentes) |
| **Disco** | SSD de 5,5 TB dedicado aos modelos |
| **Sistema** | Windows 11 Pro |

**A placa é o que manda**, e 16 GB é o ponto onde o painel inteiro funciona sem truque. O
processador e a RAM ajudam no que sobra para o sistema: a ComfyUI empurra para a RAM tudo que
não cabe na placa, então memória lenta ou pouca vira tempo de espera, não erro.

Se a sua máquina for menor, nada aqui quebra — só demora mais, e as IAs maiores podem não
caber. Comece pela trilha de imagem e vá subindo.

## Instalar

Em dois passos: **baixar os modelos** e **aplicar a configuração**.

- [INSTALAR.md](INSTALAR.md) — passo a passo, para fazer à mão. **O lugar padrão é `C:\ForjaStudio`:** `git clone https://github.com/JJatalaia/forja-studio.git C:\ForjaStudio`
- [INSTALAR-COM-IA.md](INSTALAR-COM-IA.md) — **o texto para colar no Claude Code, no Codex ou
  no Gemini CLI e deixar a IA baixar e conferir tudo para você**

**De onde vem cada coisa — todas as IAs e todos os repositórios — está em
[REPOSITORIOS.md](REPOSITORIOS.md).** São 19 repositórios no Hugging Face e 4 no GitHub;
**18 dos 19 abrem direto**, e só o `Lightricks/LTX-2.5` pede conta e aceitar a licença —
que é a causa do erro **401** no LTX 2.5.

Os links de download de todos os modelos estão em [IAS-INSTALADAS.md](IAS-INSTALADAS.md), com
o tamanho exato de cada arquivo e a pasta em que ele tem que cair.

## Usar

Está em [USAR.md](USAR.md) — aba por aba, com as armadilhas que custaram caro aqui.

## O que a gente aprendeu apanhando

[APRENDIZADOS.md](APRENDIZADOS.md) — custo medido de cada coisa, por que a imagem fica com
cara de IA, a armadilha de memória da ComfyUI, e a licença que pode te dar prejuízo. É
provavelmente a parte mais útil daqui: instalar qualquer um instala.

## A IA de código já vem instruída

O projeto traz um `CLAUDE.md` (e um `AGENTS.md` igual, para o Codex e o GPT). Quando você
abre uma IA de código nesta pasta, ela **lê isso sozinha** e já sabe: falar português, como
comandar o painel, quanto custa cada geração, e — o mais importante — **avisar você quando
um trabalho repetitivo pode virar um atalho**, em vez de deixar você gastando crédito
conversando toda vez.

Ela sempre oferece as duas opções: ela monta o atalho, ou te explica e você monta.

## Skills e agentes para o Claude Code

[SKILLS-E-AGENTES.md](SKILLS-E-AGENTES.md) — a pasta `.claude/` traz 2 skills e 3 agentes
prontos (dramaturgo, diretor de fotografia e continuísta). Se você não usa Claude Code, pode
apagar: o painel funciona igual.

## As IAs

As 8 que ficaram no painel, o que cada uma pesa e onde cada arquivo tem que cair:
[IAS-INSTALADAS.md](IAS-INSTALADAS.md).

Elas não foram escolhidas por gosto. Foram **contadas** num histórico de 2.253 trabalhos: o
que tinha 10 ou mais usos em 30 dias ficou, o resto saiu. Nove IAs saíram do painel assim —
entre elas uma de **69 GB que tinha sido usada 4 vezes na vida**. Nenhuma foi apagada: estão
em `estudio/presets-extras.json`, com instrução de como ligar de volta.

## Segurança

O estúdio é um servidor que roda **na sua máquina**, e só nela: ele escuta em `127.0.0.1`,
nunca em `0.0.0.0`. Ninguém da sua rede, nem da internet, alcança ele.

**Não exponha esta porta na internet.** Nem com redirecionamento no roteador, nem atrás de
túnel, nem de proxy. Não existe senha nem conta aqui: quem alcança a porta manda no estúdio,
pode apagar seus arquivos e ocupar sua placa de vídeo. Para usar de outra máquina, use VPN
ou um túnel SSH — assim o estúdio continua achando que o pedido veio de dentro.

Escutar só em `127.0.0.1` **não basta por si só**, e vale saber por quê: o seu navegador
alcança `127.0.0.1`. Qualquer página aberta noutra aba poderia mandar um comando para cá.
Por isso o estúdio tem um **portão** (`portao`, em `estudio/server.py`): todo pedido que
muda alguma coisa só é aceito se vier da própria página do estúdio — pedido de outro site
leva 403. Script e atalho `.bat` continuam funcionando normalmente, porque o navegador se
identifica e script não.

O que o portão **não** faz: ele não protege de programa malicioso já rodando dentro da sua
máquina. Nenhum servidor local protege disso.

## Licença

**Gratuito, de código à vista, mas não é software livre.** Em três linhas (o texto
completo está em [LICENSE](LICENSE)):

- **Pode** baixar, instalar e usar de graça, inclusive para ganhar dinheiro.
- **Precisa** criar uma conta gratuita. É condição de uso.
- **Não pode** redistribuir, revender, nem usar a configuração do Forja em outro lugar.

**O que você produzir aqui é seu.** Imagens, vídeos, áudios e textos: o autor não
reivindica nada, não cobra participação e não precisa ser citado.

O código fica à vista de propósito — para você saber o que roda na sua máquina. Quer
fazer algo que a licença não permite? Pergunte: permissão por escrito libera.

O [NOTICE](NOTICE) lista os programas com que o Forja conversa e as licenças deles.

> Até 11/11/2026 este projeto saiu sob **Apache License 2.0**. Quem pegou uma cópia
> naquele período continua com os direitos daquela licença, sobre aquela cópia.

### ⚠️ Mas a licença dos MODELOS é outra história

Os modelos não vêm neste repositório: você baixa de quem os publicou, e **vale a licença de lá**.
E elas não são todas iguais:

| | licença | pode monetizar? |
|---|---|---|
| **VoxCPM 2** (voz) | Apache-2.0 | **sim** |
| **OmniVoice** (voz) | **CC-BY-NC** | **NÃO** — é o motor que vem ligado por padrão no VoiceStudio |
| VoiceStudio (o programa) | AGPL-3.0 | ver abaixo |

**Se você ganha dinheiro com os vídeos, troque o motor de voz para o VoxCPM 2 antes de
publicar.** O painel mostra a licença do motor ativo na aba Narração — confira lá.

Sobre o AGPL do VoiceStudio: este projeto **conversa com ele pela rede**, nunca copia o código
dele para dentro. É o que mantém este projeto com licença própria. Se você for mexer, mantenha
essa regra: **chamar, nunca copiar**.

## O que este projeto não faz

- **Não gera música.** A música aqui é outro projeto, separado. Se ele não estiver instalado,
  a aba simplesmente não aparece.
- **Não publica nada sozinho.** Não tem integração com YouTube, TikTok nem nada parecido.
- **Não manda nada para fora do seu computador** — a não ser que você ligue a ElevenLabs, que
  é paga e opcional, e aí você põe a sua própria chave.
