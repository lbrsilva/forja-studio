# De onde vem cada coisa

Esta página responde uma pergunta só: **tudo o que o Forja Studio baixa, de qual
repositório vem, e o que preciso fazer para ter acesso.**

Nada aqui é nosso. Os modelos são públicos, publicados por quem os treinou, e cada um tem
dono e licença próprios. O que este projeto entrega é a configuração — quais usar, ajustados
de que jeito, ligados numa tela só.

---

## 🔑 O resumo, em quatro linhas

- São **19 repositórios** no Hugging Face e **4** no GitHub.
- **18 dos 19 abrem direto**, sem conta, sem nada.
- **Um só pede conta e aceitar a licença: [`Lightricks/LTX-2.5`](https://huggingface.co/Lightricks/LTX-2.5)** — e é
  por isso que o LTX 2.5 pode parar com **erro 401**.
- A ComfyUI e os complementos **não vêm no pacote**: são o Passo 0 do
  [INSTALAR.md](INSTALAR.md).

---

## ⚠️ O erro 401 do LTX 2.5, e o que fazer

**O que acontece:** você clica em instalar o LTX 2.5, ele baixa três arquivos e **para em
dois deles com erro 401**.

**Por quê:** esses dois vêm do repositório oficial da Lightricks, que está **fechado atrás de
um portão**. O servidor do Hugging Face responde 401 (*não autorizado*) para quem pede sem
estar logado — e o baixador do estúdio pede sem estar logado, porque ele não tem a sua conta.

Os dois arquivos são:

| arquivo | pasta | peso |
|---|---|---|
| `gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors` | `text_encoders` | 14,3 GB |
| `ltx-2.5-video-vae-bf16.safetensors` | `vae` | 1,4 GB |

### O caminho curto: pelo navegador

1. Crie uma conta em [huggingface.co/join](https://huggingface.co/join) (é de graça).
2. Abra **[huggingface.co/Lightricks/LTX-2.5](https://huggingface.co/Lightricks/LTX-2.5)** e
   **aceite a licença** no aviso que aparece no alto da página.
3. Pronto: agora os dois links da tabela do [IAS-INSTALADAS.md](IAS-INSTALADAS.md) baixam
   normalmente **no seu navegador**, enquanto você estiver logado.
4. Ponha cada arquivo na pasta que a tabela manda, dentro de `ComfyUI/models/`.

### O caminho de quem prefere baixar pela linha de comando

Depois de aceitar a licença, crie um **token de leitura** em
[huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) e use assim:

```bash
curl -L -H "Authorization: Bearer SEU_TOKEN" -o ltx-2.5-video-vae-bf16.safetensors "https://huggingface.co/Lightricks/LTX-2.5/resolve/main/vae/ltx-2.5-video-vae-bf16.safetensors"
```

### O caminho mais simples: deixar o painel baixar

Desde **11/11/2026** o botão **"Falta instalar"** resolve isso sozinho, se você der o token
a ele:

1. aceite a licença na página do repositório (passo 2 acima);
2. crie um **token de leitura** em
   [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens);
3. cole o token em **Configurações de API**, na tela de Início do próprio painel — ou,
   se preferir, salve-o sozinho na primeira linha do arquivo **`API\huggingface.txt`** dentro da
   pasta do projeto;
4. clique em instalar de novo.

> A seção **Configurações de API** fica na tela de Início e guarda também a chave do
> ElevenLabs. Ela **nunca mostra** o que já está guardado — só diz que existe.

> **O token só é mandado para o `huggingface.co`.** Para qualquer outro endereço o download
> sai sem identificação nenhuma — segredo não se entrega a quem não é dono dele.

Se preferir, dá no mesmo definir a variável de ambiente `HF_TOKEN`.

**E se você não puser token nenhum?** Nada quebra: os outros 18 repositórios continuam
baixando normalmente, e **só estes dois** param — agora com um recado que explica o que
fazer, em vez do número 401 sozinho.

### E se eu não quiser aceitar a licença?

Então **não use o LTX 2.5**, e está tudo bem. O painel tem outras IAs de vídeo que não pedem
nada: Wan 2.2 5B, MiniMax H3, LTX 2.3.

> **Não existe espelho "livre" desses arquivos que a gente possa indicar.** A Lightricks
> fechou o acesso de propósito. Contornar isso é passar por cima da licença dela, e este
> projeto não vai fazer isso nem ensinar a fazer.

---

## Os 19 repositórios do Hugging Face

A coluna **portão** foi **medida**, não suposta: cada repositório foi pedido sem
identificação nenhuma, e a coluna mostra o que o servidor respondeu
(`206` = entregou o arquivo; `401` = exigiu conta).

### Imagem

| repositório | o que vem de lá | portão |
|---|---|---|
| [`Comfy-Org/Qwen-Image_ComfyUI`](https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI) | Qwen-Image 2512 (3 arquivos) | aberto |
| [`Comfy-Org/Z-Image-Turbo`](https://huggingface.co/Comfy-Org/Z-Image-Turbo) | Z-Image Turbo (3 arquivos) | aberto |
| [`Comfy-Org/Krea-2`](https://huggingface.co/Comfy-Org/Krea-2) | Krea 2 Turbo e Krea 2 Transformar (3 arquivos) | aberto |
| [`lightx2v/Qwen-Image-2512-Lightning`](https://huggingface.co/lightx2v/Qwen-Image-2512-Lightning) | o LoRA que deixa o Qwen rápido | aberto |

### Vídeo

| repositório | o que vem de lá | portão |
|---|---|---|
| **[`Lightricks/LTX-2.5`](https://huggingface.co/Lightricks/LTX-2.5)** | **o codificador de texto e o VAE do LTX 2.5** | **🔑 pede conta e licença** |
| [`unsloth/LTX-2.5-GGUF`](https://huggingface.co/unsloth/LTX-2.5-GGUF) | o LTX 2.5 em GGUF (2 arquivos) | aberto |
| [`ruygar/LTX-2.5-Comfy-GGUF`](https://huggingface.co/ruygar/LTX-2.5-Comfy-GGUF) | o LTX 2.5 distilado em GGUF | aberto |
| [`Lightricks/LTX-2.3-fp8`](https://huggingface.co/Lightricks/LTX-2.3-fp8) | o LTX 2.3 (27,1 GB) | aberto |
| [`Lightricks/LTX-2.3`](https://huggingface.co/Lightricks/LTX-2.3) | o ampliador do LTX 2.3 | aberto |
| [`Comfy-Org/ltx-2.3`](https://huggingface.co/Comfy-Org/ltx-2.3) | o LoRA distilado do LTX 2.3 | aberto |
| [`Comfy-Org/MiniMax-H3`](https://huggingface.co/Comfy-Org/MiniMax-H3) | MiniMax H3, as duas versões (5 arquivos) | aberto |
| [`FastVideo/FastVideo-FastH3-Comfy`](https://huggingface.co/FastVideo/FastVideo-FastH3-Comfy) | o H3 Fast de 8 passos | aberto |
| [`Comfy-Org/Wan_2.2_ComfyUI_Repackaged`](https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged) | Wan 2.2 5B (2 arquivos) | aberto |
| [`Comfy-Org/Wan_2.1_ComfyUI_repackaged`](https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged) | o InfiniteTalk do Apresentador (2 arquivos) | aberto |
| [`Kijai/WanVideo_comfy`](https://huggingface.co/Kijai/WanVideo_comfy) | peças do Apresentador (2 arquivos) | aberto |
| [`Kijai/WanVideo_comfy_fp8_scaled`](https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled) | o Wan 2.1 I2V do Apresentador | aberto |
| [`Kijai/wav2vec2_safetensors`](https://huggingface.co/Kijai/wav2vec2_safetensors) | o que lê a fala para sincronizar a boca | aberto |

### Texto (a IA que escreve, pelo llama.cpp)

| repositório | o que vem de lá | portão |
|---|---|---|
| [`unsloth/Qwen3.6-35B-A3B-GGUF`](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF) | o modelo grande de texto | aberto |
| [`unsloth/Qwen3.5-9B-GGUF`](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF) | o modelo rápido e o que enxerga imagem | aberto |

### Voz (pelo VoiceStudio)

Estes o VoiceStudio baixa sozinho, na primeira vez que você usa cada motor.

| repositório | o que é | licença | monetiza? |
|---|---|---|---|
| [`openbmb/VoxCPM2`](https://huggingface.co/openbmb/VoxCPM2) | voz, 4,6 GB | Apache-2.0 | **sim** |
| [`k2-fsa/OmniVoice`](https://huggingface.co/k2-fsa/OmniVoice) | voz, 3,8 GB | **CC-BY-NC** | **NÃO** |
| [`deepdml/faster-whisper-large-v3-turbo-ct2`](https://huggingface.co/deepdml/faster-whisper-large-v3-turbo-ct2) | transcrição, 3,0 GB | MIT | sim |
| [`csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8`](https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8) | transcrição, 1,2 GB | Apache-2.0 | sim |
| [`csukuangfj/sherpa-onnx-whisper-tiny`](https://huggingface.co/csukuangfj/sherpa-onnx-whisper-tiny) | transcrição, 0,5 GB | Apache-2.0 | sim |

> ⚠️ **O OmniVoice é o que o VoiceStudio liga por padrão, e ele não deixa monetizar.** Se os
> seus vídeos dão dinheiro, troque para o VoxCPM 2 antes de publicar. A aba Narração mostra a
> licença do motor ativo.

---

## Os 4 repositórios do GitHub

Estes **não são modelos**: são programas. Nenhum deles vem dentro do pacote.

| repositório | o que é | quando instalar |
|---|---|---|
| [ComfyUI](https://github.com/comfyanonymous/ComfyUI) (versão portátil) | o motor que gera | **Passo 0, obrigatório** |
| [`yolain/ComfyUI-Easy-Media`](https://github.com/yolain/ComfyUI-Easy-Media) | complemento: MiniMax H3 e faixas de som | **obrigatório** |
| [`city96/ComfyUI-GGUF`](https://github.com/city96/ComfyUI-GGUF) | complemento: o LTX 2.5 em GGUF | **obrigatório** |
| [`debpalash/VoiceStudio`](https://github.com/debpalash/VoiceStudio) | a voz local, de graça | só se for usar Narração |

O [`xinntao/Real-ESRGAN`](https://github.com/xinntao/Real-ESRGAN) aparece na documentação
como referência do ampliador; ele chega junto da ComfyUI, não se instala à parte.

---

## ❓ "O instalador traz a ComfyUI junto?"

**Não. Hoje não traz.** Vale dizer isso com todas as letras, porque é a diferença entre o
que está escrito e o que a pessoa espera.

O que o pacote traz: o painel, a tela de conta, a configuração — **1,6 MB de código**.

O que a pessoa faz à mão, uma vez:

1. baixa a **ComfyUI portátil** e descompacta dentro da pasta do projeto;
2. instala os **2 complementos** (o jeito simples é pelo ComfyUI Manager, procurando pelo
   nome);
3. roda o `pip install -r requirements.txt` com o Python da ComfyUI.

O passo a passo está no [INSTALAR.md](INSTALAR.md), e tem também o
[INSTALAR-COM-IA.md](INSTALAR-COM-IA.md) — um texto para colar no Claude Code, no Codex ou no
Gemini CLI e deixar a IA fazer e conferir tudo isso por você.

---

## Como esta página se mantém honesta

A coluna **portão** não é opinião: cada repositório foi pedido sem identificação e a resposta
do servidor foi anotada. **Isso muda com o tempo** — quem publica um modelo pode fechar o
portão depois, e já aconteceu. Se um download parar com **401**, é esse o motivo: abra a
página do repositório, aceite a licença, e volte.

*Medido em 11/11/2026.*
