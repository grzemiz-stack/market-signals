#!/bin/zsh
# Generuje na pulpicie „market-signals START.command” i „market-signals STOP.command” (dwuklik w Finderze).
# Pliki są odtwarzalne z repo: zmiana -> edytuj TEN skrypt i uruchom go ponownie (nadpisuje oba pliki).
# Użycie: tools/install_desktop.sh [katalog_docelowy]   (domyślnie ~/Desktop; testy podają katalog tymczasowy)
set -eu
R="${0:A:h:h}"
DEST="${1:-$HOME/Desktop}"
UV="${UV:-$(command -v uv)}"
START="$DEST/market-signals START.command"
STOP="$DEST/market-signals STOP.command"
mkdir -p "$DEST"

cat > "$START" <<EOF
#!/bin/zsh
# market-signals START — WYGENEROWANE przez tools/install_desktop.sh; nie edytuj ręcznie.
# Uruchamia Ollamę i dashboard (127.0.0.1), ładuje joby launchd, nadrabia zaległe przebiegi, pokazuje stan,
# otwiera dashboard w przeglądarce. Można klikać wielokrotnie.
R="$R"
UV="$UV"
P="${MS_LAUNCHD_PREFIX:-local.market-signals}"
EOF
cat >> "$START" <<'EOF'
D=gui/$(id -u); errors=()
fail() { errors+=("$1") }
finish() {
  echo
  if (( ${#errors} )); then
    echo "=============================================="
    echo "NIE WSZYSTKO DZIAŁA:"
    for e in "${errors[@]}"; do echo "  - $e"; done
    echo "=============================================="
  else
    echo "Gotowe: system działa."
  fi
  echo; read -k1 "?Naciśnij dowolny klawisz, aby zamknąć okno… "; echo
  exit ${#errors}
}
cd "$R" 2>/dev/null || { fail "nie ma katalogu projektu $R"; finish; }

echo "== 1/5 Joby launchd i usługi (Ollama, dashboard)"
tools/install_launchd.sh || fail "ładowanie jobów launchd (komunikat powyżej); log jobów: $R/logs/jobs.log"

echo; echo "== 2/5 Ollama (tylko 127.0.0.1)"
ollama_ok() { curl -s -m 2 http://127.0.0.1:11434/api/version >/dev/null }
if ollama_ok; then echo "Ollama już działa."; else
  echo "Uruchamiam Ollamę…"
  launchctl kickstart "$D/$P.ollama" 2>/dev/null
  for i in {1..60}; do ollama_ok && break; sleep 1; done
  if ollama_ok; then echo "Ollama odpowiada."; else
    fail "Ollama nie odpowiada na 127.0.0.1:11434 po 60 s — log: /opt/homebrew/var/log/ollama.log"; fi
fi

echo; echo "== 3/5 Dashboard (tylko 127.0.0.1:8501)"
dash_ok() { curl -s -m 2 http://127.0.0.1:8501/_stcore/health >/dev/null }
if dash_ok; then echo "Dashboard już działa."; else
  echo "Uruchamiam dashboard…"
  launchctl kickstart "$D/$P.dashboard" 2>/dev/null
  for i in {1..90}; do dash_ok && break; sleep 1; done
  if dash_ok; then echo "Dashboard odpowiada."; else
    fail "dashboard nie odpowiada na 127.0.0.1:8501 po 90 s — log: $R/logs/dashboard.err.log"; fi
fi

echo; echo "== 4/5 Nadrabianie zaległych przebiegów"
for job in $(/usr/bin/python3 tools/jobctl.py list); do
  if /usr/bin/python3 tools/jobctl.py due "$job"; then
    # kickstart bez -k: gdy job już działa, nic nie robi; blokada w run_job.sh i tak nie dopuści podwójnego przebiegu
    if launchctl kickstart "$D/$P.$job"; then echo "$job: był zaległy — uruchomiony w tle (log: $R/logs/jobs.log)"
    else fail "$job: nie udało się uruchomić — log: $R/logs/jobs.log"; fi
  else
    echo "$job: aktualny"
  fi
done
sleep 2

echo; echo "== 5/5 Stan"
tools/health.sh || fail "tools/health.sh zgłosił problemy (lista „PROBLEMY” powyżej)"
echo
if [ -f logs/locks/snapshot.lock ] && ! /usr/bin/lockf -k -s -t 0 logs/locks/snapshot.lock /usr/bin/true; then
  echo "paper.py status pominięty: trwa aktualizacja bazy (snapshot). Kliknij START ponownie po jej zakończeniu."
else
  "$UV" run --frozen src/paper.py status || fail "paper.py status nie zadziałał (komunikat powyżej)"
fi
if dash_ok; then open "http://127.0.0.1:8501" && echo "Otworzono dashboard w przeglądarce: http://127.0.0.1:8501"; fi
finish
EOF

cat > "$STOP" <<EOF
#!/bin/zsh
# market-signals STOP — WYGENEROWANE przez tools/install_desktop.sh; nie edytuj ręcznie.
# Zatrzymuje joby, Ollamę i dashboard (launchctl bootout). NICZEGO nie kasuje: plisty, dane i logi zostają.
# Po ponownym zalogowaniu do Maca wszystko wystartuje samo (albo kliknij START).
R="$R"
P="${MS_LAUNCHD_PREFIX:-local.market-signals}"
EOF
cat >> "$STOP" <<'EOF'
D=gui/$(id -u); errors=()
cd "$R" 2>/dev/null || { echo "Nie ma katalogu projektu $R"; read -k1 "?Naciśnij dowolny klawisz… "; exit 1; }
for f in build/launchd/*.plist; do
  label=${f:t:r}; job=${label#$P.}
  if ! launchctl print "$D/$label" >/dev/null 2>&1; then echo "$job: już zatrzymany"; continue; fi
  if [ -f "logs/locks/$job.lock" ] && ! /usr/bin/lockf -k -s -t 0 "logs/locks/$job.lock" /usr/bin/true; then
    read -k1 "ans?$job właśnie działa. Przerwać go teraz? Przerwany przebieg nadrobi się przy następnym starcie. [t/N] "; echo
    [[ "$ans" == [tTyY] ]] || { echo "$job: zostawiam (zatrzymaj później)"; continue; }
  fi
  if launchctl bootout "$D/$label" 2>/dev/null; then echo "$job: zatrzymany"
  else errors+=("$job: nie udało się zatrzymać (launchctl bootout $D/$label)"); fi
done
echo
if (( ${#errors} )); then echo "NIE WSZYSTKO SIĘ UDAŁO:"; for e in "${errors[@]}"; do echo "  - $e"; done
else echo "Zatrzymane. Dane i konfiguracja nietknięte; START albo ponowne logowanie uruchomi wszystko z powrotem."; fi
echo; read -k1 "?Naciśnij dowolny klawisz, aby zamknąć okno… "; echo
EOF

chmod +x "$START" "$STOP"
echo "zapisano: $START"
echo "zapisano: $STOP"
