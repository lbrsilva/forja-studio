#!/bin/bash
# Abre o Forja Studio no Mac: liga o estudio se preciso, espera responder e abre a pagina.
# Se der errado a janela FICA aberta mostrando o erro.
cd "$(dirname "$0")" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
[ -f caminhos.sh ] && . ./caminhos.sh

PORTA="${ESTUDIO_PORTA:-8194}"
URL="http://127.0.0.1:$PORTA"

if [ -n "$ESTUDIO_COMFY_DIR" ]; then
  PY="$(dirname "$ESTUDIO_COMFY_DIR")/venv/bin/python"
else
  PY="ComfyUI_mac/venv/bin/python"
fi

if [ ! -x "$PY" ]; then
  echo
  echo "  Nao achei o Python da ComfyUI em:"
  echo "    $PY"
  echo
  echo "  Rode ./instalar-mac.sh primeiro (ou python3 setup.py se ja instalou a ComfyUI)."
  echo
  read -r -p "  Enter para fechar..." _
  exit 1
fi

ligado() { curl -fs --max-time 3 "$URL/api/ocupado" >/dev/null 2>&1; }

echo
echo "  Vendo se o estudio ja esta ligado..."
if ligado; then
  echo "  Ja estava ligado. Abrindo a pagina."
  open "$URL"
  exit 0
fi

echo "  Ligando o estudio..."
mkdir -p outputs
nohup "$PY" -s estudio/server.py >> outputs/estudio.log 2>&1 &
disown

echo "  Esperando ele responder (ate 60 segundos)..."
for _ in $(seq 1 30); do
  sleep 2
  if ligado; then
    echo "  Pronto. Abrindo $URL"
    open "$URL"
    exit 0
  fi
done

echo
echo "  O estudio nao respondeu em 60 segundos."
echo "  O erro esta no fim de outputs/estudio.log:"
echo
tail -n 20 outputs/estudio.log
echo
read -r -p "  Enter para fechar..." _
exit 1
