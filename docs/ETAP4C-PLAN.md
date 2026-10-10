# Etap 4C — dashboard lokalny (PLAN, bez kodu)

Stan: 2026-10-07, **zrobiony** (kroki 1–5); zaakceptowany (D1–D7 zgodnie z rekomendacjami). Budowa po kroku 5 etapu 5 (strona Zalecenia
pokazuje oba konta „system”). Zasady nadrzędne: tylko lokalnie (DECISIONS 2026-10-07), dashboard niczego nie liczy
po swojemu — pokazuje to, co liczą joby i te same funkcje, których używa `paper.py status`.

---

## 1. Cel i granice

- Cel: jedno okno w przeglądarce zamiast terminala: moje konto, karty aktywów, zalecenia reguł etapu 5, zlecenie na sucho,
  stan systemu.
- Nie robi: własnych obliczeń (modeli, reguł, statystyk), zapisu do `market.duckdb`, żadnych połączeń poza 127.0.0.1.
- Technologia: Streamlit (nowa zależność przez `uv add streamlit` — pobranie publicznego pakietu, zgodne z zasadą
  „sieć tylko do pobierania”). Wykresy: wbudowane w Streamlit (Vega-Lite z paczki Streamlit, serwowane lokalnie) — bez
  dodatkowych bibliotek wykresów.

## 2. Ustalenie sprawdzone przed planem: blokady DuckDB

Sprawdzone 2026-10-07 na kopii: **połączenie tylko do odczytu w jednym procesie blokuje zapis w innym procesie
(i odwrotnie)** — „IO Error: Could not set lock on file”. Dashboard trzymający `market.duckdb` otwartą wywróciłby nocny
snapshot o 23:30, a w trakcie snapshotu dashboard nie mógłby nic pokazać.
→ **Dashboard czyta kopię `data/market_view.duckdb`**, nie bazę roboczą (D1):
- kopię publikuje ostatni krok każdego joba piszącego do bazy (snapshot, registry): kopiowanie do pliku tymczasowego
  i podmiana jednym `mv` (atomowo; otwarte odczyty widzą starą wersję do zamknięcia);
- dashboard otwiera kopię **tylko do odczytu, na czas jednego odświeżenia strony**, potem zamyka;
- na ekranie zawsze widać „dane z: {czas publikacji kopii}”.
- `paper.duckdb` (gra) to inna baza: zlecenie z formularza zapisuje do niej przez tę samą funkcję co CLI; połączenie
  otwierane na czas jednej operacji, przy blokadzie do 10 s ponowień, potem komunikat „baza gry zajęta, spróbuj za chwilę”.

## 3. Skąd biorą się liczby (D2)

- Nowy moduł **`src/ms/views.py`** = jedyne źródło danych do wyświetlenia: funkcje zwracające gotowe struktury
  (`account_view`, `asset_card`, `recommendations_view`, `backtest_summary`, `system_health`). Liczą wyłącznie to,
  co dziś liczy `paper.py status` (odtworzenie konta z dziennika zleceń, porównania, odczyt prognoz mistrzów z bazy,
  dekompozycji, `describe_day`), wołając istniejące funkcje `ms.paper`, `ms.prob`, `ms.causes`.
- **`src/ms/fmt.py`** = jedno formatowanie liczb (zł, %, przecinek dziesiętny) dla CLI i dashboardu.
- `src/paper.py status` przepisany tak, by drukował z `ms.views` — **wydruk statusu przed i po zmianie bajt w bajt
  identyczny** (test na kopii bazy).
- Modele, prognozy i reguły liczą **tylko joby** (predict_daily, registry, nowy krok rules_today). Dashboard ich nie
  uruchamia.

## 4. Strony

1. **Moje konto** (wybór konta: „gra 1”, a gdy powstanie — „system”): wartość i wynik od startu; wykres wartości na tle
   porównań (lokata, kup-i-trzymaj złoto, momentum_1m, równy podział) i konta „system”; pozycje (ilość, wartość w zł,
   koszt, wynik); zlecenia oczekujące; dziennik zleceń z powodami i poprawkami (`paper_journal`).
2. **Karty moich aktywów** (BTC, ETH, XAG, WTI — `GAME_ASSETS`): wykres ceny (z cen znanych w chwili teraz), zmienność
   20 d vs roczna, szansa skoku w górę/w dół z plakietką przewagi mistrza („ma przewagę / brak przewagi / gorszy”),
   „zły tydzień” w zł dla kwoty z suwaka (`paper.bad_week_loss`), dekompozycja ostatniego tygodnia (`decomp_weekly`),
   „tego dnia było: …” z `move_causes` (`causes.describe_day`; kandydat nigdy jako przyczyna).
3. **Pozostałe aktywa** (XAU, BRENT): te same karty.
4. **Zalecenia**: wynik reguł etapu 5 na dziś z tabeli `rules_today` (wylicza job): wagi docelowe, ekspozycja trendu,
   σ i jej źródło, czy jest rebalans i dlaczego, lista zleceń w zł dla wybranego konta. Na górze: który wariant wykonuje
   konto „system” (reguła D7) i stan etapu 5 (np. „dane odłożone jeszcze nieotwarte”). Obok: skrót backtestu z
   `backtest_rules_dev` (Sharpe, po cięciu 2–4×, DSR, maks. obsunięcie, PBO) i stała ramka **D11: wynik backtestu nie
   uprawnia do prawdziwych pieniędzy**.
5. **Zlecenie na sucho**: formularz (konto, kupno/sprzedaż, aktywo, kwota zł albo ilość/wszystko, data decyzji,
   **powód — wymagany**). Przed wysłaniem pokazuje „zły tydzień” dla kwoty (jak CLI). Wysłanie woła tę samą funkcję co
   `paper.py buy/sell` — logikę CLI przenoszę do `ms.paper.order(...)`, CLI i formularz ją wołają (bez kopii kodu).
   Konto „system” odrzuca ręczne zlecenia (ta sama blokada co w CLI). Anulowanie i poprawka powodu — też przez funkcje
   `ms.paper` (cancel, add_note); nic się nie kasuje.
6. **Stan systemu**: wynik `tools/health.sh` (joby, ostatni udany przebieg, Ollama, konfiguracja na żywo) + czas
   publikacji kopii bazy.

## 5. Nowy krok joba: `rules_today` (po predict_daily w snapshot)

Dla dnia decyzji = ostatni znany dzień: `rules.target_weights` dla V1–V3 i cele równego podziału, `rebalance_triggers`
względem pozycji każdego konta gry, lista zleceń w zł (te same progi co w backteście: ±25%, 1% kapitału, wyjście do
zera). Zapis do tabeli `rules_today` (data, konto, wariant, aktywo, waga docelowa, ekspozycja, σ, źródło σ, powód
rebalansu, zlecenie zł). Kod reguł bez zmian (hash prerejestracji d9cb3a3a2da04caa nie może się zmienić — test).
Zalecenie to informacja: **nie składa zleceń** na koncie „gra 1”. Automatyczne wykonanie na koncie „system” = krok 5
etapu 5 (osobno).

## 6. Uruchamianie

- Usługa launchd **`<MS_LAUNCHD_PREFIX>.dashboard`** (RunAtLoad + KeepAlive, jak Ollama): `streamlit run` z
  `--server.address=127.0.0.1 --server.port=8501 --server.headless=true --browser.gatherUsageStats=false` oraz
  `.streamlit/config.toml` z tymi samymi wartościami (podwójnie: plik i argumenty).
- **START.command**: dotychczasowe kroki + czeka, aż `http://127.0.0.1:8501/_stcore/health` odpowie, i otwiera
  przeglądarkę (`open http://127.0.0.1:8501`). Błąd → komunikat po polsku + log `logs/dashboard.err.log`, okno zostaje.
- **STOP.command**: już zatrzymuje wszystkie plisty z `launchd/` — dashboard dochodzi automatycznie.
- `tools/jobctl.py`: rozróżnienie **jobów** (harmonogram, nadrabianie) i **usług** (ollama, dashboard: mają działać
  zawsze) — test zgodności plistów obejmuje oba rodzaje; `health.sh` pokazuje usługi osobno.

## 7. Testy (do bramki)

- **Tylko lokalnie (statycznie):** config.toml i plist: `server.address = 127.0.0.1`, `browser.gatherUsageStats = false`,
  `server.headless = true`; w kodzie dashboardu brak adresów spoza `ms.netpolicy` (istniejący test obejmie nowe pliki)
  i zakaz `streamlit.components` (osadzanie obcych stron/skryptów).
- **Tylko lokalnie (na żywo, `check_runtime.sh`):** nasłuch na porcie 8501 wyłącznie 127.0.0.1; proces dashboardu bez
  połączeń TCP do adresów spoza 127.0.0.1 (lsof).
- **Zero CDN:** test uruchamia serwer na wolnym porcie 127.0.0.1, pobiera stronę główną i wszystkie wskazane w niej
  skrypty/style — każdy adres względny albo 127.0.0.1.
- **Tylko odczyt bazy:** dashboard otwiera wyłącznie `market_view.duckdb` z `read_only=True` (próba zapisu → błąd);
  w kodzie dashboardu brak `db.connect(`/`duckdb.connect(` poza `ms.views`; przy otwartym dashboardzie job może pisać
  do `market.duckdb` (test blokady z pkt 2).
- **Każda liczba z tej samej funkcji co `paper.py status`:** Streamlit AppTest uruchamia każdą stronę na kopii bazy;
  test zbiera wszystkie liczby z ekranu i sprawdza, że każda jest w zbiorze wartości z `ms.views` sformatowanych przez
  `ms.fmt` — a `paper.py status` drukuje z tych samych struktur (test bajt w bajt z pkt 3).
- **Formularz:** bez powodu → odmowa; z powodem → wiersz w `paper_orders` identyczny jak z CLI dla tych samych danych;
  konto „system” → odmowa.
- **rules_today:** wagi = `rules.target_weights` dla tego samego dnia; hash prerejestracji bez zmian; PIT (perturbacja
  przyszłych cen nie zmienia zaleceń).
- Każdy test ochronny sprawdzony mutacją (pamiętając o pułapce `.pyc` z mapy).

## 8. Kolejność pracy (każdy krok: bramka + commit)

1. Akceptacja → wpisy do DECISIONS.
2. `ms.fmt` + `ms.views` + `ms.paper.order`; `paper.py` drukuje z nich (wydruk bez zmian, test bajt w bajt).
3. Publikacja kopii bazy (krok jobów) + `rules_today` + rozróżnienie jobów i usług w jobctl/health.
4. Dashboard: strony, config, plist usługi, testy (lokalność, CDN, odczyt, liczby, formularz).
5. START/STOP, `check_runtime.sh`, mapa stanu.

## 9. Decyzje (zaakceptowane 2026-10-07)

| | pytanie | decyzja |
|---|---|---|
| D1 | Jak czytać bazę bez blokowania jobów | kopia `data/market_view.duckdb` publikowana na końcu jobów (atomowo), dashboard otwiera ją tylko do odczytu na jedno odświeżenie; czas danych widoczny na ekranie |
| D2 | „Dashboard nie liczy sam” | dashboard woła tylko `ms.views` (te same funkcje co `paper.py status`: odtworzenie konta, porównania, odczyt prognoz); modele i reguły liczą wyłącznie joby. Alternatywa: joby zapisują gotowe widoki do tabel — wtedy konto po złożeniu zlecenia byłoby nieaktualne do następnego joba |
| D3 | Kiedy działa serwer | usługa launchd startująca przy logowaniu (jak Ollama); START tylko otwiera przeglądarkę, STOP zatrzymuje |
| D4 | Zalecenia: dla którego konta | lista zleceń dla każdego konta gry (wybór na stronie); dla „gra 1” to tylko informacja — nic nie jest składane automatycznie |
| D5 | Który wariant na stronie Zalecenia | wariant wskazany regułą D7 (dziś `rowny_podzial_4`) na pierwszym planie; V1–V3 obok jako „nie wybrane”, z adnotacją, że dane odłożone są jeszcze nieotwarte (etap 5 krok 4 czeka) |
| D6 | Port | 8501 (domyślny Streamlit), tylko 127.0.0.1 |
| D7 | Zapis z dashboardu | tylko do `paper.duckdb` (zlecenia, anulowania, poprawki powodu) przez funkcje `ms.paper`; nigdy do `market.duckdb` |

## 10. Zależność od etapu 5

Etap 5 stoi na kroku 4 (otwarcie danych odłożonych — czeka na decyzję). Dashboard nie zależy od tej decyzji: strona
Zalecenia pokazuje stan etapu 5 takim, jaki jest, a konto „system” pojawi się na stronach automatycznie po kroku 5.
