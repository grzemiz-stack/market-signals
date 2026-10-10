#!/bin/zsh
# Job „system” (tools/run_job.sh system; launchd <prefiks>.system, codziennie 23:50 + nadrabianie).
# 1) Konta „system” i „system_ostrozny”: decyzje reguł etapu 5 dla dni gotowych do decyzji + próg wyłączenia D9.
# 2) Gra: zlecenia z ceną zamknięcia z dnia wykonania -> status executed w bazie (jedyne miejsce zapisu wykonań;
#    dashboard tylko czyta — DECISIONS 2026-10-10).
# Czeka, aż snapshot skończy (blokada), żeby decydować na pełnych danych dnia.
set -u
cd "${0:A:h}/.."
UV="${UV:-$(command -v uv)}"
/usr/bin/lockf -k -s -t 7200 logs/locks/snapshot.lock /usr/bin/true || { echo "snapshot trzyma blokadę > 2 h"; exit 1; }
fail=0
"$UV" run --frozen src/system_accounts.py run || fail=1
"$UV" run --frozen src/paper.py sync || fail=1
exit $fail
