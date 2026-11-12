#!/bin/bash
# Instala o que o Forja Studio precisa no Mac (Apple Silicon): ComfyUI, ambiente Python com
# PyTorch (Metal/MPS), os complementos da ComfyUI, ffmpeg e llama.cpp.
# Nao baixa modelo de IA: isso e feito depois, pelos botoes "Falta instalar" dentro do programa.
#
#   ./instalar-mac.sh            instala (pode rodar de novo: ele pula o que ja esta pronto)
set -u
cd "$(dirname "$0")" || exit 1
RAIZ="$(pwd)"
PASTA="ComfyUI_mac"
[ -f caminhos.sh ] && . ./caminhos.sh
if [ -n "${ESTUDIO_COMFY_DIR:-}" ]; then
  COMFY="$ESTUDIO_COMFY_DIR"
  BASE="$(dirname "$COMFY")"
else
  BASE="$RAIZ/$PASTA"
  COMFY="$BASE/ComfyUI"
fi
VENV="$BASE/venv"

ok()   { echo "  [ok] $*"; }
aviso(){ echo "  [!]  $*"; }
erro() { echo "  [X]  $*"; }
titulo(){ echo; echo "------------------------------------------------------------------"; echo "$*"; echo "------------------------------------------------------------------"; }

titulo "1. A sua maquina"
if [ "$(uname -s)" != "Darwin" ]; then erro "Este instalador e so para macOS."; exit 1; fi
if [ "$(uname -m)" != "arm64" ]; then
  aviso "Mac com processador Intel: a ComfyUI roda so no processador (muito lento). Recomendado: Apple Silicon."
else
  ok "Apple Silicon ($(sysctl -n machdep.cpu.brand_string))"
fi
MEM_GB=$(( $(sysctl -n hw.memsize) / 1024 / 1024 / 1024 ))
ok "memoria unificada: ${MEM_GB} GB"
[ "$MEM_GB" -lt 16 ] && aviso "Com menos de 16 GB, so as IAs de imagem mais leves cabem. Video exige 32 GB ou mais."
LIVRE_GB=$(df -g "$RAIZ" | awk 'NR==2{print $4}')
ok "espaco livre aqui: ${LIVRE_GB} GB"
[ "$LIVRE_GB" -lt 50 ] && aviso "Reserve ao menos 50 GB para a plataforma e a primeira IA."

titulo "2. Ferramentas (Homebrew)"
if ! command -v brew >/dev/null 2>&1; then
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && eval "$($b shellenv)"; done
fi
if ! command -v brew >/dev/null 2>&1; then
  erro "Homebrew nao encontrado. Instale em https://brew.sh e rode este script de novo."
  exit 1
fi
ok "Homebrew em $(command -v brew)"
for pacote in python@3.12 git ffmpeg llama.cpp; do
  if brew list --formula "$pacote" >/dev/null 2>&1; then
    ok "$pacote ja instalado"
  else
    echo "  instalando $pacote ..."
    brew install "$pacote" || { erro "Nao consegui instalar $pacote."; exit 1; }
  fi
done
PY312="$(brew --prefix python@3.12)/bin/python3.12"
[ -x "$PY312" ] || { erro "Nao achei o python3.12 do Homebrew."; exit 1; }

titulo "3. A ComfyUI"
mkdir -p "$BASE"
if [ -f "$COMFY/main.py" ]; then
  ok "ComfyUI ja esta em $COMFY"
else
  git clone --depth 1 https://github.com/comfyanonymous/ComfyUI "$COMFY" || { erro "git clone da ComfyUI falhou."; exit 1; }
  ok "ComfyUI baixada em $COMFY"
fi

titulo "4. Ambiente Python (PyTorch com Metal)"
if [ ! -x "$VENV/bin/python" ]; then
  "$PY312" -m venv "$VENV" || { erro "Nao consegui criar o ambiente em $VENV."; exit 1; }
fi
"$VENV/bin/python" -m pip install --upgrade pip >/dev/null
echo "  instalando PyTorch ..."
"$VENV/bin/python" -m pip install torch torchvision torchaudio || { erro "pip falhou no PyTorch."; exit 1; }
echo "  instalando as dependencias da ComfyUI ..."
"$VENV/bin/python" -m pip install -r "$COMFY/requirements.txt" || { erro "pip falhou nas dependencias da ComfyUI."; exit 1; }
echo "  instalando as dependencias do Forja Studio ..."
"$VENV/bin/python" -m pip install -r "$RAIZ/requirements.txt" || { erro "pip falhou nas dependencias do Forja Studio."; exit 1; }
if "$VENV/bin/python" -c "import torch,sys; sys.exit(0 if torch.backends.mps.is_available() else 1)"; then
  ok "PyTorch enxerga a GPU da Apple (MPS)"
else
  aviso "PyTorch nao enxergou o MPS: a ComfyUI vai rodar no processador."
fi

titulo "5. Complementos da ComfyUI"
mkdir -p "$COMFY/custom_nodes"
while read -r nome url; do
  if [ -d "$COMFY/custom_nodes/$nome" ]; then
    ok "$nome ja instalado"
  else
    if git clone --depth 1 "$url" "$COMFY/custom_nodes/$nome" >/dev/null 2>&1; then
      ok "$nome instalado"
    else
      aviso "Nao consegui baixar $nome ($url). Instale pelo ComfyUI Manager."
      continue
    fi
  fi
  [ -f "$COMFY/custom_nodes/$nome/requirements.txt" ] && \
    "$VENV/bin/python" -m pip install -r "$COMFY/custom_nodes/$nome/requirements.txt" >/dev/null 2>&1 || true
done <<NOS
ComfyUI-Easy-Media https://github.com/yolain/ComfyUI-Easy-Media
ComfyUI-GGUF https://github.com/city96/ComfyUI-GGUF
ComfyUI-KJNodes https://github.com/kijai/ComfyUI-KJNodes
ComfyUI_Fill-ChatterBox https://github.com/filliptm/ComfyUI_Fill-ChatterBox
NOS

titulo "6. Conferindo e criando os atalhos"
chmod +x ./*.command 2>/dev/null
"$VENV/bin/python" setup.py

echo
echo "  Para abrir: de dois cliques em 'Forja Studio.command' (ou use o icone da Mesa, se criou)."
