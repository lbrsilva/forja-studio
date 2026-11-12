#!/bin/bash
# Versao sem pagina, usada pela abertura automatica do Mac (LaunchAgent).
# Liga o estudio e NAO abre navegador.
cd "$(dirname "$0")" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
[ -f caminhos.sh ] && . ./caminhos.sh

if [ -n "$ESTUDIO_COMFY_DIR" ]; then
  PY="$(dirname "$ESTUDIO_COMFY_DIR")/venv/bin/python"
else
  PY="ComfyUI_mac/venv/bin/python"
fi
[ -x "$PY" ] || exit 1
curl -fs --max-time 3 "http://127.0.0.1:${ESTUDIO_PORTA:-8194}/api/ocupado" >/dev/null 2>&1 && exit 0
mkdir -p outputs
exec "$PY" -s estudio/server.py >> outputs/estudio.log 2>&1
