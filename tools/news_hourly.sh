#!/bin/zsh
# Job „news” (tools/run_job.sh news; launchd <prefiks>.news, co godzinę o :07 + nadrabianie).
# Kanały RSS z ms.news.SOURCES -> data/news.duckdb + kopia data/news_view.duckdb. Osobna baza: nie czeka na snapshot.
set -u
cd "${0:A:h}/.."
UV="${UV:-$(command -v uv)}"
# przyrost zdarzeń GDELT 2.0 (pliki co 15 min, ~15 s) — tylko gdy snapshot nie pisze do gdelt.duckdb (jego blokada)
if /usr/bin/lockf -k -s -t 0 logs/locks/snapshot.lock /usr/bin/true; then
  "$UV" run --frozen src/gdelt_backfill.py >> logs/gdelt.stdout.log 2>&1 || echo "gdelt_backfill padł (log: logs/gdelt.log)"
else
  echo "trwa snapshot — przyrost GDELT w następnej godzinie"
fi
"$UV" run --frozen src/collect_news.py
