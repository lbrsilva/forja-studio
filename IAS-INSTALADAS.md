# As IAs do Estúdio Local

> Gerado por `_github/gerar_inventario.py` — lê os workflows e o disco, não é escrito à mão. Rode de novo depois de instalar qualquer IA nova.

| | modelos | peso |
|---|---|---|
| imagem e vídeo (ComfyUI) | 35 | **235.1 GB** |
| texto (llama.cpp) | 3 | **18.7 GB** |
| voz (VoiceStudio: 5 modelos + o aplicativo) | 5 | **22.0 GB** |
| **tudo** | **43** | **275.7 GB** |

## Cada IA, e o que ela pesa

O peso é do conjunto que aquela IA carrega. **Os totais por aba somam mais que o total geral**, porque IAs diferentes dividem o mesmo arquivo (o codificador de texto do Qwen serve a três delas, por exemplo). Quem baixa uma vez não baixa de novo.


### Imagem

| IA | peso | arquivos |
|---|---|---|
| Qwen-Image 2512 | 29.6 GB | 4 |
| Z-Image Turbo | 19.3 GB | 3 |
| Krea 2 - Transformar imagem | 17.9 GB | 5 |
| Krea 2 Turbo | 17.8 GB | 4 |

### Vídeo

| IA | peso | arquivos |
|---|---|---|
| MiniMax H3 - Referências (com áudio) | 41.4 GB | 5 |
| MiniMax H3 Fast (8 passos, com áudio) | 40.6 GB | 4 |
| LTX 2.3 (anterior, mantido) | 40.0 GB | 5 |
| LTX 2.5 - Imagem para vídeo (rápido, com áudio) | 28.3 GB | 5 |
| LTX 2.5 - Texto para vídeo (rápido, com áudio) | 28.3 GB | 5 |
| Apresentador (foto falando + voz) | 27.6 GB | 6 |
| Wan 2.2 5B | 16.9 GB | 3 |

> **De qual repositório vem cada coisa, e qual deles pede conta:**
> **[REPOSITORIOS.md](REPOSITORIOS.md)**. Dos 19 repositórios, 18 abrem direto; só o
> `Lightricks/LTX-2.5` pede conta e aceitar a licença — é a causa do erro **401**.

## Os arquivos, um por um

A coluna **pasta** é onde o arquivo tem que cair dentro de `ComfyUI/models/` — errar a pasta é o jeito mais comum de a IA não aparecer na lista.

| arquivo | pasta | peso | de onde vem |
|---|---|---|---|
| `ltx-2.3-22b-dev-fp8.safetensors` | `checkpoints` | 27.1 GB | [baixar](https://huggingface.co/Lightricks/LTX-2.3-fp8/resolve/main/ltx-2.3-22b-dev-fp8.safetensors) |
| `fastvideo_fasth3_8step_v2_pruned_int8_convrot.safetensors` | `diffusion_models` | 20.6 GB | [baixar](https://huggingface.co/FastVideo/FastVideo-FastH3-Comfy/resolve/main/diffusion_models/fastvideo_fasth3_8step_v2_pruned_int8_convrot.safetensors) |
| `minimax_h3_ref2va_pruned_int8_convrot.safetensors` | `diffusion_models` | 19.5 GB | [baixar](https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors) |
| `qwen_image_2512_fp8_e4m3fn.safetensors` | `diffusion_models` | 19.0 GB | [baixar](https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors) |
| `Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors` | `diffusion_models` | 15.5 GB | [baixar](https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/I2V/Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors) |
| `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | `text_encoders` | 14.6 GB | [baixar](https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors) |
| `gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors` | `text_encoders` | 14.3 GB | [baixar](https://huggingface.co/Lightricks/LTX-2.5/resolve/main/text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors)<br>🔑 **pede login e aceitar a licença** (veja INSTALAR.md) |
| `krea2_turbo_fp8_scaled.safetensors` | `diffusion_models` | 12.2 GB | [baixar](https://huggingface.co/Comfy-Org/Krea-2/resolve/main/diffusion_models/krea2_turbo_fp8_scaled.safetensors) |
| `z_image_turbo_bf16.safetensors` | `diffusion_models` | 11.5 GB | [baixar](https://huggingface.co/Comfy-Org/Z-Image-Turbo/resolve/main/split_files/diffusion_models/z_image_turbo_bf16.safetensors) |
| `ltx-2.5-22b-distilled-Q4_K_M.gguf` | `unet` | 11.4 GB | [baixar](https://huggingface.co/ruygar/LTX-2.5-Comfy-GGUF/resolve/main/ltx-2.5-22b-distilled-transformer-bf16-Q4_K_M.gguf)<br>⚠️ **renomeie para `ltx-2.5-22b-distilled-Q4_K_M.gguf`** |
| `wan2.2_ti2v_5B_fp16.safetensors` | `diffusion_models` | 9.3 GB | [baixar](https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors) |
| `gemma_3_12B_it_fp4_mixed.safetensors` | `text_encoders` | 8.8 GB | ⚠️ **falta confirmar** |
| `qwen_2.5_vl_7b_fp8_scaled.safetensors` | `text_encoders` | 8.7 GB | [baixar](https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors) |
| `qwen_3_4b.safetensors` | `text_encoders` | 7.5 GB | [baixar](https://huggingface.co/Comfy-Org/Z-Image-Turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors) |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | `text_encoders` | 6.3 GB | [baixar](https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors) |
| `qwen3vl_4b_fp8_scaled.safetensors` | `text_encoders` | 4.9 GB | [baixar](https://huggingface.co/Comfy-Org/Krea-2/resolve/main/text_encoders/qwen3vl_4b_fp8_scaled.safetensors) |
| `minimax_h3_video_vae_fp16.safetensors` | `vae` | 4.9 GB | [baixar](https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_video_vae_fp16.safetensors) |
| `wan2.1_infiniteTalk_multi_fp16.safetensors` | `model_patches` | 4.8 GB | [baixar](https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/model_patches/wan2.1_infiniteTalk_multi_fp16.safetensors) |
| `ltx_2.3_22b_distilled_1.1_lora_dynamic_fro09_avg_rank_111_bf16.safetensors` | `loras` | 2.6 GB | [baixar](https://huggingface.co/Comfy-Org/ltx-2.3/resolve/main/split_files/loras/ltx_2.3_22b_distilled_1.1_lora_dynamic_fro09_avg_rank_111_bf16.safetensors) |
| `minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors` | `loras` | 1.8 GB | [baixar](https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors) |
| `Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors` | `loras` | 1.6 GB | [baixar](https://huggingface.co/lightx2v/Qwen-Image-2512-Lightning/resolve/main/Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors) |
| `ltx-2.5-video-vae-bf16.safetensors` | `vae` | 1.4 GB | [baixar](https://huggingface.co/Lightricks/LTX-2.5/resolve/main/vae/ltx-2.5-video-vae-bf16.safetensors)<br>🔑 **pede login e aceitar a licença** (veja INSTALAR.md) |
| `wan2.2_vae.safetensors` | `vae` | 1.3 GB | [baixar](https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan2.2_vae.safetensors) |
| `ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors` | `latent_upscale_models` | 0.9 GB | [baixar](https://huggingface.co/unsloth/LTX-2.5-GGUF/resolve/main/latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors) |
| `ltx-2.3-spatial-upscaler-x2-1.1.safetensors` | `latent_upscale_models` | 0.9 GB | [baixar](https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-spatial-upscaler-x2-1.1.safetensors) |
| `lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors` | `loras` | 0.7 GB | [baixar](https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors) |
| `gemma-3-12b-it-abliterated_lora_rank64_bf16.safetensors` | `loras` | 0.6 GB | ⚠️ **falta confirmar** |
| `minimax_h3_audio_vae_fp32.safetensors` | `vae` | 0.6 GB | [baixar](https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_audio_vae_fp32.safetensors) |
| `krea2_darkbrush.safetensors` | `loras` | 0.4 GB | [baixar](https://huggingface.co/Comfy-Org/Krea-2/resolve/main/loras/krea2_darkbrush.safetensors) |
| `ltx-2.5-audio-vae-bf16.safetensors` | `vae` | 0.3 GB | [baixar](https://huggingface.co/unsloth/LTX-2.5-GGUF/resolve/main/vae/ltx-2.5-audio-vae-bf16.safetensors) |
| `ae.safetensors` | `vae` | 0.3 GB | [baixar](https://huggingface.co/Comfy-Org/Z-Image-Turbo/resolve/main/split_files/vae/ae.safetensors) |
| `Wan2_1_VAE_bf16.safetensors` | `vae` | 0.2 GB | [baixar](https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors) |
| `qwen_image_vae.safetensors` | `vae` | 0.2 GB | [baixar](https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors) |
| `wav2vec2-chinese-base_fp16.safetensors` | `audio_encoders` | 0.2 GB | [baixar](https://huggingface.co/Kijai/wav2vec2_safetensors/resolve/main/wav2vec2-chinese-base_fp16.safetensors) |
| `RealESRGAN_x4plus.pth` | `upscale_models` | 0.1 GB | [baixar](https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth) |

### Texto (llama.cpp)

| arquivo | peso | de onde vem |
|---|---|---|
| `Qwen3.6-35B-A3B-UD-IQ3_XXS.gguf` | 12.3 GB | https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF/resolve/main/Qwen3.6-35B-A3B-UD-IQ3_XXS.gguf |
| `Qwen3.5-9B-UD-Q4_K_XL.gguf` | 5.6 GB | https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/resolve/main/Qwen3.5-9B-UD-Q4_K_XL.gguf |
| `mmproj-F16.gguf` | 0.9 GB | https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/resolve/main/mmproj-F16.gguf |

### Voz (VoiceStudio)

| repositório | peso |
|---|---|
| [openbmb/VoxCPM2](https://huggingface.co/openbmb/VoxCPM2) | 4.6 GB |
| [k2-fsa/OmniVoice](https://huggingface.co/k2-fsa/OmniVoice) | 3.8 GB |
| [deepdml/faster-whisper-large-v3-turbo-ct2](https://huggingface.co/deepdml/faster-whisper-large-v3-turbo-ct2) | 3.0 GB |
| [csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8](https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8) | 1.2 GB |
| [csukuangfj/sherpa-onnx-whisper-tiny](https://huggingface.co/csukuangfj/sherpa-onnx-whisper-tiny) | 0.5 GB |

## ⚠️ Links que ainda faltam

**2 dos 35 arquivos** ainda não têm a origem confirmada. Enquanto faltar, o instalador não consegue baixar esses — e é por isso que eles aparecem marcados na tabela em vez de sumirem.

