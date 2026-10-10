# Etap 4N — nowe E4 (wiadomości RSS): plan

**Data planu: 2026-10-08.** Spisany PRZED zajrzeniem do treści wiadomości w `data/news.duckdb` (do planu użyto wyłącznie
liczby pozycji per źródło). Podstawa: DECISIONS 2026-10-08 (obecne E4 = wada testu: wejście GDELT filtrowane do konfliktów
nie dawało szansy na odpowiedź). Nowe E4 wchodzi do trzeciej próby (docs/ETAP4N-WALIDACJA-PLAN.md pkt 5). **Zaakceptowany 2026-10-08: D1 + D3, bez D4.**
Uzupełnienie 2026-10-08: E4-hist (pkt 7).

## 1. Które dni (wzorzec: przyczyna z kalendarza, nie z wiadomości)

Dzień D wchodzi do E4, gdy w kalendarzu jest zdarzenie z typów planu 4N, ustalone **niezależnie od treści wiadomości**:

| typ | źródło dnia | kod wzorca | dni w oknie 2026-10-07…2026-12-02 |
|---|---|---|---|
| FOMC | harmonogram Fed (federalreserve.gov/monetarypolicy/fomccalendars.htm, sprawdzony 2026-10-08; publikowany z wyprzedzeniem) — dzień komunikatu | `monetary` | **1** (2026-10-28; następne 2026-12-09, poza oknem) |
| hack ≥ 100 mln USD | DefiLlama /hacks (P7, już zbierane), `value ≥ 1e8` USD, data zdarzenia | `crypto_hack` | **~0–1** (2021–2025: średnio 6/rok; w 2025: 4) |
| OPEC | brak źródła automatycznego (Känzig kończy się 2025-12; opec.org → 403) | `oil_supply` | **0** bez decyzji D3 |
| ETF krypto | lista ręczna P8 (ostatni wpis 2024-07) | `crypto_etf` | **~0** |

**Spodziewane: 1–3 dni w oknie.** Lista FOMC zapisana z góry: `2026-10-28`. Hacki: wg DefiLlama w dniu
uruchomienia E4 (próg i źródło ustalone teraz). Kilka typów jednego dnia → każdy kod z tego dnia jest trafieniem.

## 2. Wejście

- **Źródła:** wszystkie kanały RSS z `ms.news.SOURCES` **oprócz The Block** (D11: tylko czytnik, wyłączony z
  klasyfikacji/analiz). Kanały „tylko tytuł i link” (Bitcoin Magazine, SilverSeek, GoldSeek) — sam tytuł. Tytuły GDELT DOC,
  jeśli API zacznie odpowiadać. **Bez** wpisów ze zdarzeń GDELT (`gdelt_ev_*`): nie mają tytułu ani leadu, to opis z kodów.
- **Okno:** pozycje z `known_at` (moment pierwszego pobrania) w **[D−1 22:00, D 22:00] UTC** — to samo okno co krok 3
  planu 4N (chwila decyzji D 22:00). Komunikat FOMC (18:00 UTC) mieści się w oknie.
- **Tekst:** tylko tytuł + lead z kanału (bez pełnych artykułów, bez wchodzenia na strony). Kolejność: `published_at`
  malejąco (brak → `known_at`); **najwyżej 300 pozycji** na dzień (najnowsze), numerowane do `evidence_ids`.
- **Bez wariantu zamaskowanego:** zdarzenia są po dacie odcięcia wiedzy modeli, pamięć nie pomaga.
- **Prompt:** prompt trzeciej próby (definicje z rozdzieleniem `macro` / `monetary`), pełna taksonomia, jeden przebieg,
  temp. 0, seed 20261007 — jak E1–E3.

## 3. Warunki jakości dnia (ustalone teraz; dzień niespełniający → wyłączony z powodem w raporcie)

- job news miał udane pobrania w **≥ 20 z 24 godzin** okna (manifest data/raw/news/manifest.jsonl) i w oknie nie ma
  luki z `news_gaps` dla kanałów Fed/EBC/BoE (dla FOMC) lub kanałów krypto (dla hacków/ETF);
- w oknie jest **≥ 5 pozycji** RSS (po wyłączeniu The Block).

## 4. Miara i próg

- **Trafienie:** kod modelu ∈ kody kalendarza dnia. **Miara:** odsetek trafień + przedział Wilsona 95%; w raporcie też
  wynik per typ dnia i odsetek `unknown`.
- **Próg (bez zmian względem planu 4N): ≥ 0,60.**
- **Minimum n = 20 dni** (decyzja D1). Przy n = 20 przedział Wilsona ma szerokość ok. ±0,21 — mniej nie odróżni modelu
  od przypadku. **Przy n < 20 E4 nie jest uruchamiane i nie daje werdyktu** (ani „zaliczone”, ani „niezaliczone”);
  `validated` pozostaje false.

## 5. Co, jeśli dni za mało (spodziewane)

Na 2026-12-02 będzie ~1–3 dni, czyli **E4 nie ruszy w grudniu**. Przy samych FOMC + hackach (~14 dni/rok) n = 20
osiągniemy ok. **wiosny 2028**. Decyzje do podjęcia teraz (przed danymi):

| | opcja | skutek |
|---|---|---|
| D2 | czekać na n ≥ 20 tylko z FOMC + hacków (+ ETF z listy ręcznej) | ~wiosna 2028 |
| D3 | dodać dni OPEC+: z ogłoszonego **z wyprzedzeniem** terminu posiedzenia (źródło publiczne zapisane przed posiedzeniem; bez opec.org 403) | +~8–12 dni/rok → n = 20 ok. jesieni 2027 |
| D4 | dodać dni publikacji danych USA o dużej niespodziance (CPI, payrolls; kalendarz wydań FRED, który już mamy) jako `macro` — reguła niespodzianki jak WPSR w 4N (górne 10%, tylko przeszłość) | +~5–8 dni/rok; uwaga: związek „dane → ruch” słabszy niż przy FOMC |

**Decyzja (2026-10-08): D1 (n ≥ 20) + D3, bez D4.** D3: lista posiedzeń OPEC+ w `ref/e4_opec_meetings.csv`
(data, źródło publiczne z zapowiedzią, data zapisu wpisu) — wpis tylko PRZED posiedzeniem; wpis po fakcie nie wchodzi do E4. D4 zmieniałby charakter testu z „czy model rozpoznaje zdarzenie” na
„czy model zgaduje, które dane ruszyły rynkiem”.

## 6. Kolejność

1. Akceptacja planu (D1–D4) → DECISIONS. 2. Ewentualnie (D3) lista dni OPEC+ prowadzona z wyprzedzeniem w `ref/`.
3. Gdy n ≥ 20: przebieg w ramach trzeciej próby, raport. Treść wiadomości do tego czasu nikt nie ogląda w kontekście E4
   (dashboard pokazuje bieżące wiadomości — to nie jest dobór dni ani wzorca).

## 7. E4-hist — opcja trzeciej próby (dopisane 2026-10-08, przed jakimkolwiek przebiegiem)

Cel: sprawdzić stare 42 dni bez wady wejścia (dotąd: GDELT filtrowany do zdarzeń konfliktowych z USA wśród aktorów).

- **Dni i wzorzec: bez zmian** — te same 42 dni co stare E4 (FOMC 26, OPEC 12, hack 2, ETF 2; 2016-01-27…2026-03-18),
  trafienie = kod modelu ∈ kody kalendarza dnia. **Próg 0,60.** Minimum n spełnione (42).
- **Dane:** pełne pliki GDELT 2.0 **export + mentions** z okna [D−1 22:00, D 22:00] UTC (po DATEADDED / MentionTimeDate),
  bez filtra do konfliktów. Wykonalność (sprawdzona na metadanych masterfilelist, bez pobierania i otwierania plików):
  **8 046 plików (4 023 export + 4 023 mentions), 1,17 GB zip** (export 0,44 GB, mentions 0,73 GB); 89–96 plików na dzień
  (GDELT ma luki); dysk: 721 GB wolne; czas: pobranie ~10–20 min (kilka wątków, jak backfill), ekstrakcja kilka minut.
  Licencja jak dotąd: GDELT „unlimited and unrestricted use … for any academic, commercial, or governmental use” (cytowanie
  przy redystrybucji; tu brak redystrybucji). robots.txt data.gdeltproject.org: 404 (brak ograniczeń). Surowe zip-y:
  `data/raw/gdelt_e4/` (+ md5 z masterfilelist), wyciąg: `data/gdelt_e4.duckdb` (URL, slug, CAMEO, aktorzy, liczba wzmianek).
- **Filtr USA–USA: NIE stosujemy w E4-hist.** Ocena: filtr wprowadzono 2026-10-06 dla cech, żeby wyciąć krajowy szum USA;
  w dniu FOMC zdarzenia o Fed są w GDELT kodowane zwykle z aktorem 1 = USA (bank centralny / rząd) i aktorem 2 = USA
  (gospodarka, banki, rynki) — filtr usuwałby właśnie sygnał, który E4 ma znaleźć. Diagnostyka (ustalona teraz, liczona po
  pobraniu, bez wpływu na wynik): odsetek pozycji USA–USA wśród wybranych 600 per typ dnia.
- **Wejście (pozycja = jeden adres artykułu):** pula = `SOURCEURL` z export ∪ `MentionIdentifier` (MentionType = 1, web)
  z mentions w oknie; dla adresu zdarzenia powiązane przez GlobalEventID. Tekst pozycji: `slug URL | CAMEO <EventCode>
  <Actor1CountryCode>→<Actor2CountryCode>` (zdarzenie o najwyższym NumMentions); slug wg reguł starego E4 (≥ 12 znaków,
  nie same cyfry). Bez tytułów i treści stron (nie wchodzimy na strony).
- **Limit: 600 pozycji na dzień** (jak stare E4), ranking: max NumMentions powiązanych zdarzeń malejąco, przy remisie URL
  rosnąco (deterministycznie).
- **Prompt:** trzeciej próby; pełna taksonomia; jeden przebieg; bez wariantu zamaskowanego (to samo co E4 na RSS).
- **Rola w bramce:** E4-hist i E4 na RSS są dwoma wariantami E4 trzeciej próby; który z nich (albo oba) jest bramką —
  decyzja D5 przed przebiegiem trzeciej próby.
