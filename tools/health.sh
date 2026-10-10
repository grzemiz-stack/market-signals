#!/bin/zsh
# Jedno polecenie: czy działają joby i Ollama, kiedy był ostatni udany przebieg, czy coś jest zaległe.
# Kod 0 = wszystko w porządku; 1 = są problemy (wypisane na końcu, z logiem do sprawdzenia).
set -u
cd "${0:A:h}/.."
D=gui/$(id -u); P="${MS_LAUNCHD_PREFIX:-local.market-signals}"; problems=()
now=$(date +%s)
age_h() { [ "$1" = "—" ] && echo 99999 || echo $(( (now - $(date -j -f '%Y-%m-%d %H:%M' "$1" +%s)) / 3600 )) }

echo "== Joby ($(date '+%F %H:%M'))"
printf '%-9s %-12s %-17s %-20s %-17s %-8s %s\n' job launchd "ostatni start" wynik "ostatni udany" zaległy log
/usr/bin/python3 tools/jobctl.py status | while IFS='|' read -r job start res ok due logf; do
  if launchctl print "$D/$P.$job" >/dev/null 2>&1; then ld=załadowany; else ld=NIEZAŁADOWANY; fi
  if [ -f "logs/locks/$job.lock" ] && ! /usr/bin/lockf -k -s -t 0 "logs/locks/$job.lock" /usr/bin/true; then res="DZIAŁA TERAZ"; fi
  printf '%-9s %-12s %-17s %-20s %-17s %-8s %s\n' "$job" "$ld" "$start" "$res" "$ok" "$due" "$logf"
  [ "$ld" = NIEZAŁADOWANY ] && print -r -- "$job: job niezaładowany (tools/install_launchd.sh albo START.command)" >> "$TMPDIR/ms_health.$$"
  [[ "$res" == BŁĄD* ]] && print -r -- "$job: ostatni przebieg zakończony błędem — log: $logf i logs/jobs.log" >> "$TMPDIR/ms_health.$$"
  limit=$(case $job in registry) echo 840;; news) echo 3;; *) echo 48;; esac)   # rejestr 35 dni; wiadomości 3 h; reszta 2 doby
  [ "$(age_h "$ok")" -gt "$limit" ] && print -r -- "$job: ostatni udany przebieg $ok — za dawno (log: $logf)" >> "$TMPDIR/ms_health.$$"
done

echo; echo "== Usługi (tylko 127.0.0.1)"
/usr/bin/python3 tools/jobctl.py services | while IFS='|' read -r name label check logf; do
  if launchctl print "$D/$label" >/dev/null 2>&1; then ld=załadowana; else ld=NIEZAŁADOWANA
    print -r -- "$name: usługa niezaładowana (tools/install_launchd.sh albo START.command)" >> "$TMPDIR/ms_health.$$"; fi
  if curl -s -m 3 "$check" >/dev/null; then resp="odpowiada ($check)"; else resp="NIE ODPOWIADA ($check)"
    print -r -- "$name: nie odpowiada na $check — log: $logf" >> "$TMPDIR/ms_health.$$"; fi
  printf '%-10s %-14s %s\n' "$name" "$ld" "$resp"
done
if v=$(curl -s -m 3 http://127.0.0.1:11434/api/version); then
  echo "ollama: wersja $v; modele: $(curl -s -m 3 http://127.0.0.1:11434/api/tags | /usr/bin/python3 -c 'import json,sys; print(", ".join(m["name"] for m in json.load(sys.stdin)["models"]) or "brak")')"
fi
echo "dashboard: http://127.0.0.1:8501 — kopia bazy z $(/usr/bin/python3 -c 'import json; print(json.load(open("data/market_view.json"))["published_at"])' 2>/dev/null || echo 'BRAK') UTC"

echo; echo "== Wiadomości: stan źródeł (ostatnia próba)"
[ -f data/news_view.duckdb ] || echo "(brak data/news_view.duckdb — job news jeszcze nie działał)"
"${UV:-$(command -v uv)}" run --frozen python - <<'PY' 2>/dev/null
import duckdb
c = duckdb.connect("data/news_view.duckdb", read_only=True)
for s, st, ok, n in c.execute("""SELECT f.source, f.last_status, strftime(f.last_ok, '%Y-%m-%d %H:%M'),
        (SELECT count(*) FROM news_items i WHERE i.source = f.source AND i.known_at > now()::TIMESTAMP - INTERVAL 1 DAY)
        FROM news_fetch f ORDER BY 1""").fetchall():
    print(f"{s:17} {str(st)[:48]:48} ostatni udany {ok or '—':16} nowych/24 h {n}")
PY

echo; echo "== Konfiguracja na żywo vs repo"
out=$(tools/check_runtime.sh); echo "$out"
print -r -- "$out" | grep '^PROBLEM' | sed 's/^PROBLEM: //' >> "$TMPDIR/ms_health.$$"

echo; echo "== Ostatnie wpisy logs/jobs.log"
tail -5 logs/jobs.log 2>/dev/null || echo "(brak — joby nie biegły jeszcze przez run_job.sh)"

echo
if [ -s "$TMPDIR/ms_health.$$" ]; then
  echo "== PROBLEMY"; sed 's/^/- /' "$TMPDIR/ms_health.$$"; rm -f "$TMPDIR/ms_health.$$"; exit 1
fi
rm -f "$TMPDIR/ms_health.$$"; echo "WSZYSTKO DZIAŁA"
