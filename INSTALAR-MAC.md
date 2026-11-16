# Instalar no Mac (Apple Silicon)

Este guia cobre só o que muda no Mac. O resto (conta, IAs, como usar) é igual ao `INSTALAR.md` e ao `USAR.md`.

## O que você precisa

| item | mínimo | recomendado |
|---|---|---|
| Chip | Apple Silicon (M1 ou mais novo) | M-Pro / M-Max |
| Memória | 16 GB | 32 GB ou mais |
| Disco livre | 50 GB | 100 GB+ |
| Homebrew | [brew.sh](https://brew.sh) | |

A memória do Mac é unificada: a "placa de vídeo" é a própria RAM, e o Metal deixa a GPU usar cerca de 3/4 dela. O painel mostra esse limite no lugar da VRAM.

## Instalar

Duas formas, e as duas podem ser repetidas sem estragar nada.

**Pelo programa:** abra `Forja Studio.command` (só precisa do Homebrew) e use os botões de **Preparar esta máquina**, no Início. O painel instala o motor (ComfyUI), o ffmpeg, o llama.cpp e o VoiceStudio por ali, com barra de progresso. Os modelos de IA vêm depois, em **IAs aprovadas pelo projeto**.

**Pelo script:** roda a mesma coisa de uma vez só, no Terminal:

```bash
cd forja-studio
./instalar-mac.sh
```

O script instala, nesta ordem:

1. `python@3.12`, `git`, `ffmpeg` e `llama.cpp` pelo Homebrew;
2. a ComfyUI em `ComfyUI_mac/ComfyUI`;
3. um ambiente Python em `ComfyUI_mac/venv` com PyTorch (Metal/MPS) e as dependências;
4. os complementos da ComfyUI (Easy-Media, GGUF, KJNodes, Fill-ChatterBox);
5. roda o `setup.py`, que confere tudo e oferece o ícone `Forja Studio.app` na Mesa.

Nenhum modelo de IA é baixado aqui. Eles vêm depois, pelo botão **Falta instalar** dentro do programa.

Para guardar a ComfyUI e os modelos em outro disco, rode `python3 escolher_pasta.py` antes: ele grava `caminhos.sh`, que o instalador e os lançadores leem.

## Abrir e fechar

| arquivo | o que faz |
|---|---|
| `Forja Studio.command` | liga o estúdio, espera responder e abre a página (ou o ícone da Mesa) |
| `Desligar o estudio.command` | fecha o estúdio, a ComfyUI e a IA de texto; libera a memória |
| `Ligar com o Mac.command` | abre o estúdio sozinho quando você entra no Mac (LaunchAgent) |
| `Nao ligar com o Mac.command` | desfaz o de cima |

Na primeira vez o macOS pode bloquear um `.command` baixado. Clique com o botão direito, **Abrir**, e confirme. Se vier de um `git clone`, não há bloqueio.

O log do estúdio fica em `outputs/estudio.log`.

## IA de texto (llama.cpp)

No Mac um único `llama-server` (o do Homebrew, com Metal) atende os dois modos, "placa" e "processador". Se você colocar um binário em `_ferramentas/llama.cpp/`, ele tem prioridade. Os `.gguf` e o `modelos_texto/modelos.ini` seguem o que está em `IAS-INSTALADAS.md`.

## O que muda em relação ao Windows

- **GPU:** Metal (MPS) no lugar de CUDA. `PYTORCH_ENABLE_MPS_FALLBACK=1` é definido para que operações sem suporte no Metal rodem no processador em vez de falhar.
- **Flags da ComfyUI:** sem `--fast fp16_accumulation` e `--use-ck-attention` (são de NVIDIA/AMD no Windows).
- **ID da máquina e licença:** a conta continua obrigatória e funciona igual. A impressão digital usa o UUID e o serial da plataforma e o serial do SSD. É uma máquina nova para o seu plano.
- **Chave guardada para o modo offline:** no lugar do DPAPI do Windows, AES-GCM com chave derivada do UUID desta máquina e do seu usuário. Copiar `chave_presets.bin` para outro Mac não abre.
- **Processos filhos:** a IA de texto fecha junto com o estúdio (grupo de processos mais um vigia), como o Job do Windows fazia.

## Limites conhecidos

- Os presets e workflows foram ajustados no Windows com placa NVIDIA. Este port cobre o painel, a conta, os serviços e a instalação; a geração em si depende dos nós da ComfyUI terem suporte a Metal, e eu não testei geração de imagem ou vídeo (isso exige conta e modelos baixados). O tempo mostrado no painel vem de medidas do Windows, e modelos grandes (vídeo) podem não caber na sua memória. A conferência de memória do painel usa o teto de 3/4 da RAM.
- O VoiceStudio tem versão oficial para Mac (Apple Silicon): o botão de instalação baixa o `.zip` certo para a sua máquina, confere o SHA-256 e abre o app.
- Hermes funciona no Mac com a pasta `Hermes Agent/bin/hermes` do Windows. O encerramento dos processos usa `psutil` nos dois sistemas, sem `taskkill`, `wmic` ou PowerShell.
- O **Plano-sequência** depende de `projetos/fz_contexto/plano_sequencia.py`, que hoje não viaja no pacote e só roda no Windows: o caminho do Edge está fixo em `C:\Program Files\Microsoft\Edge\...` e o script usa PowerShell para fechar o navegador. Enquanto o script não existir, a aba fica escondida no painel. Quando a pasta chegar, ela precisa ser adaptada para macOS: o lado do servidor já escolhe o navegador e encerra por `psutil`.
- A escolha do navegador já existe em **Configurações → Navegador da automação**: Chrome (preferido), Edge, Brave, Chromium, Vivaldi ou Opera. Safari não serve: ele não aceita `--user-data-dir`/`--headless` e precisaria de safaridriver. O script adaptado receberá `ESTUDIO_NAVEGADOR` (id), `ESTUDIO_NAVEGADOR_BIN` (executável) e `ESTUDIO_NAVEGADOR_MARCADOR` (nome do perfil).
- O painel de música, a IA de texto e os scripts do Canal automático também funcionam no Mac.
- Formatos do Mac nos envios: foto `.heic`/`.heif` é convertida para PNG pelo `sips`; vídeo `.mov`/`.m4v` e áudio `.m4a`/`.aiff`/`.caf` passam pelo ffmpeg; a aba Música aceita AIFF, CAF e M4B além de WAV/MP3/FLAC/OGG/M4A/AAC/OPUS.
