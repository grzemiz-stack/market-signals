#!/bin/zsh
# Job „registry” (tools/run_job.sh registry; launchd <prefiks>.registry, 1. dnia miesiąca 06:00 + nadrabianie).
# Odświeża prognozy walk-forward (ta sama konfiguracja), potem ocena rejestru za ostatni pełny miesiąc + reguły.
# Kod wyjścia != 0, gdy padł którykolwiek krok.
set -u
cd "${0:A:h}/.."
UV="${UV:-$(command -v uv)}"
fail=0
step() { local name=$1 logf=$2; shift 2
  "$@" || { fail=1; osascript -e "display notification \"Sprawdź $logf\" with title \"market-signals: $name padł\"" } }
step eval_baselines logs/baselines.log "$UV" run --frozen src/eval_baselines.py
step train_gbm logs/gbm.log "$UV" run --frozen src/train_gbm.py --note monthly_refresh
step build_decomp logs/registry.log "$UV" run --frozen src/build_decomp.py
step eval_registry logs/registry.log "$UV" run --frozen src/eval_registry.py
step publish_view logs/registry.log "$UV" run --frozen src/publish_view.py
exit $fail
