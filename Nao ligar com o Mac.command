#!/bin/bash
# Desfaz o "Ligar com o Mac.command".
PLIST="$HOME/Library/LaunchAgents/local.forjastudio.plist"
echo
launchctl unload "$PLIST" 2>/dev/null
if [ -f "$PLIST" ]; then
  rm "$PLIST" && echo "  Pronto. O Forja Studio nao abre mais sozinho."
else
  echo "  Nao achei a abertura automatica: ela nunca foi criada."
fi
echo
read -r -p "  Enter para fechar..." _
