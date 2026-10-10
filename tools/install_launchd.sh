#!/bin/zsh
# Renderuje plisty z szablonów launchd/*.plist.template (tools/jobctl.py render: MS_LAUNCHD_PREFIX, MS_REPO, UV) do
# build/launchd/, instaluje je do ~/Library/LaunchAgents i ładuje. Idempotentne: drugi raz z rzędu nic nie zmienia.
# Niczego nie kasuje poza wyłączeniem usługi brew ollama (zastępuje ją nasz plist z OLLAMA_HOST=127.0.0.1).
# Job w trakcie (blokada w logs/locks) nie jest przeładowywany — zmieniony plist czeka na następne uruchomienie skryptu.
set -u
cd "${0:A:h}/.."
LA=~/Library/LaunchAgents; D=gui/$(id -u); rc=0
mkdir -p "$LA" logs/locks
P="${MS_LAUNCHD_PREFIX:-local.market-signals}"
/usr/bin/python3 tools/jobctl.py render build/launchd >/dev/null || exit 1

if [ -f "$LA/homebrew.mxcl.ollama.plist" ]; then
  echo "wyłączam usługę brew ollama (zastępuje ją $P.ollama)"
  /opt/homebrew/bin/brew services stop ollama >/dev/null || { echo "BŁĄD: brew services stop ollama"; rc=1; }
fi

for p in build/launchd/*.plist; do
  label=${p:t:r}; dst="$LA/${p:t}"; job=${label#$P.}
  if ! cmp -s "$p" "$dst"; then
    if [ -f "logs/locks/$job.lock" ] && ! /usr/bin/lockf -k -s -t 0 "logs/locks/$job.lock" /usr/bin/true; then
      echo "UWAGA: $job właśnie działa — plist zaktualizuję przy następnym uruchomieniu"; rc=1; continue
    fi
    launchctl bootout "$D/$label" 2>/dev/null
    cp "$p" "$dst"
    echo "zainstalowano $label"
  fi
  if ! launchctl print "$D/$label" >/dev/null 2>&1; then
    launchctl bootstrap "$D" "$dst" && echo "załadowano $label" || { echo "BŁĄD: nie udało się załadować $label"; rc=1; }
  fi
done
exit $rc
