#!/bin/zsh
# Job „snapshot” (tools/run_job.sh snapshot; launchd <prefiks>.snapshot, codziennie 23:30 + nadrabianie).
# 1) surowe snapshoty, 2) przyrostowa aktualizacja bazy, 3) GDELT, 4) przebudowa cech i etykiet,
# 5) prognozy mistrzów dla nowych dni, 6) zalecenia reguł, 7) test kompletności, 8) kopia bazy dla dashboardu.
# Awaria kroku -> powiadomienie, nie blokuje kolejnych; kod wyjścia != 0, gdy padł którykolwiek krok.
set -u
cd "${0:A:h}/.."
UV="${UV:-$(command -v uv)}"
# data snapshotu = dzień startu joba (kroki po północy nie zmieniają dnia; check_snapshot sprawdza właśnie ten dzień)
export MS_SNAPSHOT_DATE="${MS_SNAPSHOT_DATE:-$(date +%F)}"
fail=0
step() { local name=$1 logf=$2; shift 2
  "$@" || { fail=1; osascript -e "display notification \"Sprawdź $logf\" with title \"market-signals: $name padł\"" } }
step snapshot_raw logs/snapshot.log "$UV" run --frozen src/snapshot_raw.py
step kolektor logs/collect.log "$UV" run --frozen src/collect.py
# GDELT: przyrost dzienny (backfill zakończony 2026-10-06; skrypt pomija pliki już przetworzone; osobna baza)
# job news (co godzinę) też dopisuje do gdelt.duckdb — czekamy, aż skończy (jego blokada, do 10 min)
step gdelt logs/gdelt.log /usr/bin/lockf -k -s -t 600 logs/locks/news.lock "$UV" run --frozen src/gdelt_backfill.py
step build_features logs/features.log "$UV" run --frozen src/build_features.py
# prognozy mistrzów dla nowych dni (bez trenowania; trenowanie = comiesięczny job registry)
step predict_daily logs/predict_daily.log "$UV" run --frozen src/predict_daily.py
# zalecenia reguł etapu 5 na dziś (informacja dla dashboardu; nic nie składa)
step rules_today logs/snapshot.log "$UV" run --frozen src/rules_today.py
step check_snapshot logs/snapshot.log "$UV" run --frozen src/check_snapshot.py
# kopia bazy do odczytu przez dashboard (ostatni krok: dashboard nigdy nie otwiera market.duckdb)
step publish_view logs/snapshot.log "$UV" run --frozen src/publish_view.py
exit $fail
