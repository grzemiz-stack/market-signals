#!/bin/zsh
# Commit tylko przy zielonej bramce (kod wyjścia bramka.sh, bez potoków, które go gubią).
# Użycie: tools/commit.sh "wiadomość" [pliki...]   (bez plików: wszystkie zmiany)
set -u
cd "${0:A:h}/.."
./tools/bramka.sh > logs/bramka.last 2>&1
rc=$?
tail -3 logs/bramka.last
if [ $rc -ne 0 ]; then
  echo "BRAMKA CZERWONA (rc=$rc) — brak commitu. Szczegóły: logs/bramka.last"
  exit $rc
fi
msg=$1; shift
if [ $# -gt 0 ]; then git add "$@"; else git add -A; fi || { echo "git add nie powiódł się — brak commitu (sprawdź ścieżki)"; exit 1; }
git commit -q -m "$msg" && git log --oneline -1
