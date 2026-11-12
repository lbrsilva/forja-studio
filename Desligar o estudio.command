#!/bin/bash
# Fecha o estudio, a ComfyUI e a IA de texto deste projeto, e libera a memoria.
cd "$(dirname "$0")" || exit 1
RAIZ="$(pwd)"
[ -f caminhos.sh ] && . ./caminhos.sh
COMFY="${ESTUDIO_COMFY_DIR:-$RAIZ/ComfyUI_mac/ComfyUI}"

echo
echo "  Fechando o estudio e o que ele tiver ligado..."
echo
for padrao in "$RAIZ/estudio/server.py" "estudio/server.py" "$COMFY/main.py" "modelos_texto/modelos.ini"; do
  for pid in $(pgrep -f -- "$padrao"); do
    [ "$pid" = "$$" ] && continue
    echo "   fechando $pid"
    kill "$pid" 2>/dev/null
  done
done
sleep 3
for padrao in "estudio/server.py" "$COMFY/main.py" "modelos_texto/modelos.ini"; do
  for pid in $(pgrep -f -- "$padrao"); do
    [ "$pid" = "$$" ] && continue
    kill -9 "$pid" 2>/dev/null
  done
done
echo
echo "  Pronto. A memoria esta livre."
echo
read -r -p "  Enter para fechar..." _
