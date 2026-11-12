#!/bin/bash
# Faz o Forja Studio subir sozinho quando voce entra no Mac (so o estudio, sem carregar IA).
# Para desfazer: "Nao ligar com o Mac.command".
cd "$(dirname "$0")" || exit 1
RAIZ="$(pwd)"
PLIST="$HOME/Library/LaunchAgents/local.forjastudio.plist"

echo
echo "  Isto faz o Forja Studio abrir sozinho toda vez que voce entra no Mac."
echo "  So o estudio (a pagina). A GPU continua so sendo usada quando voce pedir."
echo
read -r -p "  Pode criar? (s/N): " ok
case "$ok" in s|S) ;; *) exit 0 ;; esac

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>local.forjastudio</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$RAIZ/Forja Studio - silencioso.command</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>WorkingDirectory</key><string>$RAIZ</string>
</dict>
</plist>
PLISTEOF
launchctl unload "$PLIST" 2>/dev/null
launchctl load "$PLIST" && echo && echo "  Pronto. Da proxima vez que entrar no Mac a pagina ja vai estar de pe em http://127.0.0.1:8194"
echo
read -r -p "  Enter para fechar..." _
