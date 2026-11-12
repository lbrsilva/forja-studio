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

```bash
cd forja-studio
./instalar-mac.sh
```

O script pode ser rodado de novo sem estragar nada. Ele instala, nesta ordem:

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
- O VoiceStudio é um aplicativo de Windows. No Mac a narração local usa o Chatterbox pela ComfyUI.
- Hermes, os painéis de música (YuE2, ACE-Step) e os scripts do Canal automático (`fazer_tudo.py`) são extras da máquina de origem e só aparecem se as pastas existirem.
