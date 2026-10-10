#!/bin/zsh
# Uruchamia job (tools/jobctl.py JOBS) z blokadą i nadrabianiem. Wołane przez launchd (RunAtLoad + StartCalendarInterval)
# i przez START.command. Użycie: tools/run_job.sh JOB [--force]
#  - blokada pliku (lockf): drugi równoległy przebieg tego samego joba kończy się od razu, bez pracy;
#  - bez --force job rusza tylko, gdy jest zaległy (przegapiony termin) — RunAtLoad przy każdym logowaniu nic nie dubluje;
#  - stan ostatniego przebiegu: logs/state/JOB.json; dziennik startów i końców: logs/jobs.log.
set -u
cd "${0:A:h}/.."
job=${1:?podaj nazwę joba}; force=${2:-}
PY=/usr/bin/python3
mkdir -p logs/locks logs/state
JOBLOG=${MS_JOBS_LOG:-logs/jobs.log}   # testy podają własny plik
log() { print -r -- "$(date '+%F %T') [$job] $*" >> "$JOBLOG" }

if [ -z "${MS_JOB_LOCKED:-}" ]; then
  MS_JOB_LOCKED=1 /usr/bin/lockf -k -s -t 0 "logs/locks/$job.lock" /bin/zsh "$0" "$@"
  rc=$?
  if [ $rc -eq 75 ]; then log "już działa — pomijam (blokada)"; exit 0; fi
  exit $rc
fi

info=$($PY tools/jobctl.py show "$job") || { log "nieznany job"; exit 2; }
script=${${info#*|}%%|*}; joblog=${info##*|}
if [ "$force" != "--force" ] && ! $PY tools/jobctl.py due "$job"; then
  log "nie zaległy — pomijam"; exit 0
fi
# po starcie Maca sieć bywa jeszcze niegotowa: czekam do 5 min na trasę domyślną
for i in {1..60}; do /sbin/route -n get default >/dev/null 2>&1 && break; sleep 5; done
log "start"
$PY tools/jobctl.py start "$job"
/bin/zsh "$script"
rc=$?
$PY tools/jobctl.py end "$job" $rc
log "koniec, kod $rc"
if [ $rc -ne 0 ]; then
  osascript -e "display notification \"Sprawdź logs/jobs.log i $joblog\" with title \"market-signals: job $job zakończony błędem\""
fi
exit $rc
