# Operacje: snapshoty, harmonogram, warstwa danych, bramka (notatki po polsku)

## Snapshoty surowe (`src/snapshot_raw.py`)

Codziennie zapisuje dane, których historii nie da się odtworzyć później. Bez parsowania.

- Pliki: `data/raw/{source}/{YYYY-MM-DD}/{nazwa}` — treść 1:1.
- Manifest: `data/raw/manifest.jsonl` — `source, filename, url, fetched_at (UTC), snapshot_date, http_status, bytes, sha256, unchanged, path`.
  Nieudane pobrania też trafiają do manifestu (pole `error`, bez `sha256`).
- Jeśli sha256 = ostatnie pobranie tego samego (source, filename) → tylko wpis `unchanged: true`, plik nie jest zapisywany.
- Log: `logs/snapshot.log`. Jedno źródło: `uv run src/snapshot_raw.py gpr tpu`.

| source | skąd | uwagi |
|---|---|---|
| `comex` | **ręcznie, opcjonalnie** → `data/inbox/comex/` | CME blokuje automaty (403 „IP blocked… scraping prohibited”, Data Terms of Use). Plik wrzucony do skrzynki trafia do raw; brak nie jest sprawdzany. |
| `curve` | yfinance, `CL?YY.NYM` / `BZ?YY.NYM`, miesiące 1–6 | CSV z `history(period="1mo")` (jedyna serializacja — yfinance nie daje pliku). Roll wg reguł NYMEX (tylko weekendy, bez świąt), mapa w `curve_map.json`. ≥1 s między zapytaniami, backoff przy 429, cache dzisiejszych plików. |
| `gpr` | matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls | cały plik (ogon rewidowany) |
| `tpu` | matteoiacoviello.com/tpu_files/tpu_web_latest.xlsx | arkusz `TPU_DAILY` w środku |
| `bakerhughes` | **ręcznie** → `data/inbox/bakerhughes/` | rigcount.bakerhughes.com blokuje automaty (Akamai 403/timeout); brak próby automatycznej |
| `coinmetrics` | `initial/`: btc.csv, eth.csv z github.com/coinmetrics/data (przypięte do commita, jednorazowo, dane do 2026-05-24); `backfill/`: Community API 2026-05-20…2026-10-06 (jednorazowo); dziennie: Community API, metryki community 1d, ostatnie 10 dni | ≤10 req / 6 s. `ReferenceRate*` w darmowym API tylko ~7 dni wstecz → luka 2026-05-25…09-29 dla tych 4 metryk. |

## Harmonogram (launchd)

`tools/snapshot_daily.sh` (snapshot + `src/check_snapshot.py`) o 23:30 czasu lokalnego. Uśpiony Mac → zadanie odpala się po wybudzeniu.

```sh
tools/install_launchd.sh      # renderuje launchd/*.plist.template (MS_LAUNCHD_PREFIX, MS_REPO, UV) do build/launchd/ i ładuje
P=${MS_LAUNCHD_PREFIX:-local.market-signals}
launchctl kickstart -k gui/$(id -u)/$P.snapshot   # test ręczny
launchctl print gui/$(id -u)/$P.snapshot | grep -E 'state|last exit'
# zdjęcie: launchctl bootout gui/$(id -u)/$P.snapshot
```

`check_snapshot.py`: w dzień roboczy (pn–pt, bez świąt) brak krzywej (6×CL, 6×BZ), gpr, tpu albo dziennego przyrostu Coin Metrics (btc, eth) → powiadomienie macOS + exit 1. COMEX i Baker Hughes nie są sprawdzane.

## Warstwa danych (etap 1)

`data/market.duckdb` — tabela `observations` (source, series_id, observed_at, known_at, value, vintage, ingested_at, license, flags),
`series` (częstotliwość, licencja), `releases` (daty publikacji FRED), `events` (GDELT, etap 1b).
Czasy w UTC. Jedna obserwacja może mieć wiele wersji (rewizje, vintage ALFRED, kolejne snapshoty).

- Import / aktualizacja: `uv run src/collect.py [kolektor ...] [--full]` (log: logs/collect.log).
- Odczyt dla modelu: **tylko** `SELECT * FROM as_of(TIMESTAMP '…')` albo `ms.db.panel_asof(con, serie, chwile)`.
- Raport pokrycia: `uv run src/report.py`.
- Próby na kopii bazy: `MS_DB=/ścieżka/dev.duckdb uv run src/collect.py …`.
- Plan, decyzje i źródła: `docs/ETAP1-PLAN.md`; stan: poza kopią publiczną.

## Bramka

`./tools/bramka.sh` — składnia, plist, gitignore, reguły rolowania, `check_snapshot`, idempotentność Store, pytest (rdzeń + testy na prawdziwej bazie; w bramce `MS_REQUIRE_DB=1`: brak bazy = błąd; samo `pytest` bez danych pomija testy `data` z powodem).
