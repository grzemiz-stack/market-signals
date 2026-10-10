#!/bin/zsh
# Stan na żywo zgodny z repo (bramka [9] i tools/health.sh):
#  1) każdy plist (wyrenderowany z launchd/*.plist.template) zainstalowany w ~/Library/LaunchAgents bez różnic i załadowany;
#  2) Ollama tylko z naszego plista (usługa brew wyłączona — inaczej dwie instancje i niejawny adres);
#  3) jeśli Ollama działa: nasłuchuje WYŁĄCZNIE na 127.0.0.1 / ::1;
#  4) dashboard: nasłuch tylko 127.0.0.1:8501, żadnych połączeń TCP poza 127.0.0.1.
# Kod 0 = zgodne; inaczej lista problemów po polsku. Naprawa: tools/install_launchd.sh
set -u
cd "${0:A:h}/.."
LA=~/Library/LaunchAgents; D=gui/$(id -u); bad=0
problem() { print -r -- "PROBLEM: $*"; bad=1 }
/usr/bin/python3 tools/jobctl.py render build/launchd >/dev/null || { print "PROBLEM: nie da się wyrenderować plistów"; exit 1 }

for p in build/launchd/*.plist; do
  label=${p:t:r}
  if [ ! -f "$LA/${p:t}" ]; then problem "$label nie jest zainstalowany (tools/install_launchd.sh)"
  elif ! cmp -s "$p" "$LA/${p:t}"; then problem "$label: zainstalowany plist różni się od repo (tools/install_launchd.sh)"
  elif ! launchctl print "$D/$label" >/dev/null 2>&1; then problem "$label nie jest załadowany (tools/install_launchd.sh)"
  fi
done
[ -f "$LA/homebrew.mxcl.ollama.plist" ] && problem "usługa brew ollama nadal zainstalowana (brew services stop ollama)"

listen=$(lsof -nP -iTCP -sTCP:LISTEN -a -c ollama 2>/dev/null | awk 'NR>1 {print $9}' | sort -u)
if [ -n "$listen" ]; then
  for a in ${(f)listen}; do
    case $a in 127.0.0.1:*|\[::1\]:*) ;; *) problem "Ollama nasłuchuje na $a — dozwolone tylko 127.0.0.1";; esac
  done
fi
# dashboard: nasłuch tylko 127.0.0.1:8501 i żadnych połączeń wychodzących poza pętlę zwrotną
dpids=$(lsof -nP -t -iTCP:8501 -sTCP:LISTEN 2>/dev/null | sort -u)
for a in $(lsof -nP -iTCP:8501 -sTCP:LISTEN 2>/dev/null | awk 'NR>1 {print $9}' | sort -u); do
  case $a in 127.0.0.1:*|\[::1\]:*) ;; *) problem "dashboard nasłuchuje na $a — dozwolone tylko 127.0.0.1";; esac
done
for pid in ${(f)dpids}; do
  for c in $(lsof -nP -a -p "$pid" -iTCP -sTCP:ESTABLISHED 2>/dev/null | awk 'NR>1 {print $9}'); do
    remote=${c#*->}
    case $remote in 127.0.0.1:*|\[::1\]:*) ;; *) problem "dashboard (pid $pid) ma połączenie z $remote — dozwolone tylko 127.0.0.1";; esac
  done
done
[ $bad -eq 0 ] && print "konfiguracja na żywo zgodna z repo; Ollama: ${listen:-nie działa (nasłuch nie sprawdzony)}" | tr '\n' ' ' && echo
exit $bad
