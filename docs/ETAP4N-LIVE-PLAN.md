# Etap 4N-live — agenci zbierający wiadomości (PLAN, bez kodu)

Stan: 2026-10-07, **zaakceptowany** (D1 ręcznie, D2 SEC z User-Agent <MS_CONTACT_EMAIL>, D9 AUTO, D10 ręcznie bez
maili; pozostałe wg rekomendacji). Rozszerzenie pokrycia: pkt 12. Cel: ruszyć ze **zbieraniem** jak najszybciej (dzień akceptacji), klasyfikacja
później. Zasady nadrzędne: tylko RSS albo publiczne API; blokad nie obchodzimy; tylko lokalnie (netpolicy); LLM
wyłącznie klasyfikuje, wpływ ocenia model liczbowy (DECISIONS 2026-10-06); wiadomości to wiedza z chwilą `known_at`.

---

## 1. Co etap robi, a czego nie

- Robi: co godzinę pobiera kanały RSS/API z listy, zapisuje surowy plik, wyciąga **tytuł, lead z RSS, URL, czas
  publikacji, moment pobrania, źródło, hash**; pokazuje ostatnie wiadomości na kartach aktywów w dashboardzie.
- Nie robi (teraz): klasyfikacji Qwenem — ta rusza dopiero po przejściu walidacji z 4N (E1–E4, progi w DECISIONS).
  Nie kopiuje pełnych artykułów, nie wchodzi na strony artykułów, nie obchodzi blokad (403, robots.txt, brak kanału).
- Wiadomości **nie są cechą** żadnego modelu w tym etapie (test jak dla `move_causes`).

## 2. Weryfikacja źródeł u źródła (2026-10-07, z tego Maca)

Sprawdzone: (1) odpowiedź kanału (HTTP, liczba pozycji, czy jest lead), (2) `robots.txt` **wg RFC 9309 (najdłuższa
pasująca reguła)** — biblioteka Pythona (pierwsza pasująca) błędnie przepuściła EIA, (3) warunki korzystania (ToS) —
strony prawne przeczytane 2026-10-07 (kopie robocze poza repo; rozstrzygające cytaty sprawdzone w zapisanych stronach,
wyjątki oznaczone). Zasada użytkownika: **ToS albo robots.txt zabraniające automatów → lista ręczna**, nawet jeśli
serwis publikuje RSS.

| źródło | aktywa | kanał | HTTP / pozycje | robots.txt | ToS (sedno) | status |
|---|---|---|---|---|---|---|
| Rigzone | WTI, BRENT | rigzone.com/news/rss/rigzone_latest.aspx | 200 / 20 | dozwolone | warunki RSS: „free service … for private, non-commercial use”; bez zmian treści, z przypisaniem źródła | **AUTO** |
| OilPrice | WTI, BRENT | oilprice.com/rss/main | 200 / 15 | dozwolone | „not use any robot, spider, other automatic device … to monitor or copy” | RĘCZNA (ToS) |
| EIA Today in Energy + komunikaty | WTI, BRENT | eia.gov/rss/todayinenergy.xml, press_rss.xml | 200 / 13, 12 | **zabronione** (`User-agent: *` → `Disallow: /rss`) | domena publiczna | RĘCZNA (robots; D1) |
| OPEC | WTI, BRENT | brak publicznego kanału (/rss → 403) | 403 | 403 | nie do otwarcia (402/403) | RĘCZNA |
| IEA | WTI, BRENT | brak kanału RSS (nagłówki strony bez RSS, /rss → 404) | 404 | — | CC BY 4.0 | RĘCZNA (brak kanału) |
| WGC (gold.org) | XAU | gold.org/rss.xml | 200 / 10 | dozwolone | „You are permitted to save, display or print out information contained on this Website only for your personal, non-commercial use.” (sprawdzone u źródła 2026-10-07); poza tym zakaz kopiowania/scrapowania | **AUTO** (kanał publikowany przez WGC, zapis do użytku osobistego) |
| Silver Institute | XAG | silverinstitute.org/feed/ | 200 / 10 (rzadko) | dozwolone | brak warunków dot. strony (tylko znaki towarowe, prywatność) | **AUTO** (D9) |
| Kitco News | XAU, XAG | brak kanału RSS (/rss → 404) | 404 | — | zakaz robotów i pobierania | RĘCZNA |
| Mining.com | XAU, XAG | mining.com/feed/ | **403** (też strona główna) | 403 | niejasne (link prowadzi do warunków siostrzanego serwisu) | RĘCZNA (403) |
| LBMA | XAU, XAG | brak kanału RSS | 404 | — | brak warunków strony | RĘCZNA |
| The Block | BTC, ETH | theblock.co/rss.xml | 200 / 19 | dozwolone | „…you may not share that feed or use it in any application other than an RSS feed reader.” oraz zakaz „systematic or automated data collection … data mining, data extraction” (sprawdzone u źródła 2026-10-07 przez WebFetch; nasz klient dostaje 403 na stronie warunków) | **AUTO tylko jako czytnik** — zapis i wyświetlanie; **wyłączony z klasyfikacji/analiz** |
| CoinDesk | BTC, ETH | coindesk.com/arc/outboundfeeds/rss/ | 200 / 25 | dozwolone | „not use any robot, spider, scraper, or other automated means … without our express written permission” | RĘCZNA (ToS) |
| Cointelegraph | BTC, ETH | cointelegraph.com/rss | 200 / 30 | dozwolone | „automated scraping … strictly prohibited without prior written authorization” | RĘCZNA (ToS) |
| SEC komunikaty | BTC, ETH | sec.gov/news/pressreleases.rss | 200 / 25 | dozwolone (`/news` niezablokowane) | domena publiczna; **wymagany User-Agent z nazwą i e-mailem**, ≤ 10 zapytań/s (bez tego 403 — sprawdzone) | **AUTO** (D2: User-Agent z <MS_CONTACT_EMAIL> tylko dla sec.gov) |
| Fed (Board) | makro | federalreserve.gov/feeds/press_all.xml | 200 / 20 | brak robots.txt (404) | domena publiczna | **AUTO** |
| EBC | makro | ecb.europa.eu/rss/press.html | 200 / 15 | dozwolone, **Crawl-delay 5 s** | „free use … the ECB must be cited as the source” | **AUTO** |
| NBP | makro (PLN) | brak kanału RSS (nbp.pl/feed/ → strona bez pozycji) | 200 / 0 | — | nie do otwarcia (ochrona przed botami) | RĘCZNA |

**Automatycznie od razu: 7 kanałów** — Rigzone, WGC, Silver Institute, The Block, SEC, Fed, EBC.
Uczciwie: przy ścisłej zasadzie pokrycie jest cienkie — ropa ma 1 źródło automatyczne (Rigzone), krypto 1–2 (The Block,
SEC), złoto 1 (WGC), srebro 0–1. Ropę i makro częściowo pokrywają dane, które już mamy (WPSR/STEO z API EIA, kalendarz
FOMC, GDELT). Lista ręczna: pkt 7. Prośba o zgodę (np. do CoinDesk/Cointelegraph) — tylko jeśli zdecydujesz (D10).

## 3. Zapis

- **Osobna baza `data/news.duckdb`** (D3) — job godzinowy nie może konkurować o blokadę `market.duckdb` ze snapshotem
  (sprawdzone 2026-10-07: blokady DuckDB między procesami). Dashboard czyta kopię `data/news_view.duckdb` publikowaną
  na końcu każdego przebiegu (jak market_view).
- Tabela `news_items` (append-only, jedna wersja na pozycję):
  `item_id` (hash = sha256 źródła + znormalizowanego URL, a gdy brak URL — guid), `source`, `feed_url`, `title`,
  `summary` (lead z RSS **dokładnie jak w kanale** — Rigzone zabrania zmian treści; do wyświetlenia tylko tytuł + link
  + nazwa źródła), `url`, `published_at` (UTC; NULL gdy brak),
  `published_at_raw`, `known_at` (**moment pierwszego pobrania**, UTC — zawsze), `published_missing` (flaga),
  `published_after_known` (flaga: czas publikacji późniejszy niż pobranie — błąd zegara źródła), `raw_file`, `run_id`.
- PIT: wiadomość jest „znana” od `known_at`. Pozycje sprzed startu zbierania (zaległość w kanale) mają `known_at` =
  pierwsze pobranie, więc nigdy nie udają wcześniejszej wiedzy.
- Surowe pliki: `data/raw/news/{źródło}/{RRRR-MM-DD}/{HHMMSS}.xml` + wpis w `data/raw/manifest.jsonl` (sha256, status
  HTTP, ETag) — jak snapshoty; plik identyczny z poprzednim nie jest zapisywany drugi raz (wpis „unchanged”).
- Pełnych artykułów nie pobieramy; dane zostają w `data/` (poza gitem), tylko do użytku prywatnego (D8).

## 4. Pobieranie (grzecznie i sprawdzalnie)

- Jeden GET na kanał na godzinę, User-Agent identyfikujący program (`market-signals/0.1 (private personal RSS reader;
  1 request/hour)`), warunkowe GET (ETag / If-Modified-Since), limit czasu 20 s, odstęp z Crawl-delay (EBC 5 s).
- `robots.txt` każdego hosta sprawdzany **raz na dobę** (RFC 9309, najdłuższa reguła, grupa naszego UA albo `*`):
  gdy kanał stanie się zabroniony albo zwróci 401/403/451 → źródło wyłącza się samo, powiadomienie, wpis do listy ręcznej.
  Nigdy nie próbujemy innego User-Agenta ani obejścia.
- Luka: RSS trzyma tylko ostatnie N pozycji. Gdy żadna pozycja z poprzedniego pobrania nie występuje w nowym (kanał
  „przewinął się” — np. Mac był wyłączony), zapis w `news_gaps` (źródło, od, do) — luka oznaczona, nie wypełniana (D5).
- Każdy host w `src/ms/netpolicy.py` (opis: co pobieramy); test bramki obejmuje nowe moduły.

## 5. Job

- Job **`news`** co godzinę o :07 (launchd `StartCalendarInterval` z samą minutą), z `RunAtLoad`, nadrabianiem
  (zaległy = od ostatniego pełnego godzinowego terminu nie było udanego przebiegu) i blokadą lockf — jak pozostałe.
  `tools/jobctl.py`: nowy typ harmonogramu `("hourly", minuta)`.
- Udany przebieg = wszystkie kanały AUTO pobrane albo „unchanged”; padnięcie jednego kanału nie zatrzymuje reszty
  (kod ≠ 0 + powiadomienie). `health.sh`: ostatni udany przebieg i liczba pozycji z ostatniej doby per źródło.
- Koniec przebiegu: publikacja `news_view.duckdb`.

## 6. Dashboard

- Na każdej karcie aktywa: **ostatnie wiadomości z jego źródeł** (tytuł jako link, źródło, czas publikacji albo „czas
  pobrania” z flagą), domyślnie 5, przycisk „więcej”. Makro (Fed, EBC) w osobnej zwijanej sekcji na każdej karcie.
- Dane przez `ms.views.news_for_asset` z `news_view.duckdb` (tylko odczyt); linki otwierają się w przeglądarce
  (dashboard nie pobiera artykułów). Test pochodzenia liczb i lokalności obejmuje nowe elementy.

## 7. Lista ręczna (bez automatów, bez obchodzenia)

`docs/ZRODLA-RECZNE-NEWS.md`: źródło, powód (403 / robots / brak kanału / ToS), co ewentualnie robić ręcznie
(np. raz w tygodniu przejrzeć komunikaty OPEC i IEA), i warunek powrotu do automatu (pojawi się RSS/API, zmieni się
robots.txt). Uzupełnienie bez łamania zasad: makro i ropa są częściowo pokryte przez dane, które już mamy (kalendarz
FOMC, WPSR/STEO z API EIA, GDELT).

## 8. Klasyfikacja (później, osobno)

- Dopiero po przejściu walidacji 4N (E1, E3, E4 — progi w DECISIONS): Qwen klasyfikuje `news_items` na kanał
  (podaż, popyt, strach, polityka monetarna, regulacja, fizyczny niedobór), aktywo, kierunek — tabela `news_class`
  z modelem, wersją promptu, czasem klasyfikacji. Wpływu nie ocenia LLM, tylko model liczbowy z walidacją.
- Wywołania wyłącznie przez `ms.llm` (127.0.0.1). Do tego czasu: tylko zbieranie.

## 9. Testy (do bramki)

- Parser: RSS 2.0 i Atom (próbki z prawdziwych kanałów zapisane w `tests/fixtures/news/`), lead bez zmian, strefy
  czasowe → UTC, brak daty → flaga.
- Idempotencja: dwa pobrania tego samego pliku → zero nowych wierszy; `known_at` = pierwsze pobranie.
- robots.txt wg RFC 9309: przypadek EIA (`Allow`/`Disallow` w grupie `*`) → zabronione; kanał zabroniony nie jest
  pobierany (test na sztucznym serwerze 127.0.0.1).
- Luka: kanał bez wspólnych pozycji z poprzednim → wpis w `news_gaps`.
- Job: plist zgodny z jobctl, harmonogram godzinowy i nadrabianie.
- PIT: kod prognoz nie czyta tabel `news_*` (rozszerzenie testu z 4N); netpolicy obejmuje hosty kanałów.
- Każdy test ochronny sprawdzony mutacją.

## 10. Kolejność (każdy krok: bramka + commit)

1. Akceptacja → DECISIONS, `docs/ZRODLA-RECZNE-NEWS.md`.
2. Kolektor + baza + job godzinowy + testy → **zbieranie startuje tego samego dnia**.
3. Wiadomości na kartach dashboardu.
4. (Później, osobny plan) klasyfikacja po walidacji 4N.

## 11. Decyzje (zaakceptowane 2026-10-07)

| | pytanie | decyzja |
|---|---|---|
| D1 | EIA: kanały działają, treść w domenie publicznej, ale robots.txt zabrania `/rss` wszystkim automatom | uszanować — EIA na liście ręcznej (dane liczbowe EIA i tak mamy z API) |
| D2 | SEC wymaga adresu e-mail w User-Agent (bez niego 403) | SEC tak; User-Agent `market-signals/0.1 <MS_CONTACT_EMAIL>` wyłącznie dla sec.gov |
| D3 | Gdzie zapisywać | osobna baza data/news.duckdb + kopia news_view.duckdb dla dashboardu |
| D4 | Ile tekstu | tytuł + lead z RSS bez zmian + link; bez pełnych artykułów; na ekranie tytuł, link, nazwa źródła |
| D5 | Godziny, gdy Mac był wyłączony | bez uzupełniania; luka oznaczona w news_gaps |
| D6 | Źródła z 403 / bez RSS (OPEC, Mining.com, IEA, Kitco, LBMA, NBP) | lista ręczna; bez scrapowania stron |
| D7 | Pora | co godzinę o :07 |
| D8 | Licencje | wyłącznie użytek prywatny, dane w data/ (poza gitem), nic nie jest udostępniane dalej; przypisanie źródła na ekranie (Rigzone, EBC) |
| D9 | Silver Institute: robots pozwala, kanał publikowany, warunków dot. strony brak | AUTO (brak zakazu, publikowany kanał WordPress) |
| D10 | OilPrice, CoinDesk, Cointelegraph: ToS zabrania automatów, choć publikują RSS | lista ręczna, bez maili do serwisów |
| D11 | The Block: RSS tylko w czytniku, zakaz automatycznego zbierania/ekstrakcji | AUTO jako czytnik (zapis + wyświetlanie); wyłączony z przyszłej klasyfikacji i analiz |

## 12. Rozszerzenie pokrycia (zlecone 2026-10-07; te same zasady)

- **GDELT DOC 2.0 API**: tytuły i linki artykułów wg tematów per aktywo (ropa i OPEC, złoto i srebro, bitcoin i ethereum,
  sankcje, Fed), co godzinę, z limitem zapytań z dokumentacji/odpowiedzi API. Do sprawdzenia u źródła: robots.txt
  api.gdeltproject.org, warunki GDELT, limit.
- Kanały do sprawdzenia: CFTC press, Departament Skarbu USA, OFAC (sankcje), Bank of England, BIS, IMF — dopisane te,
  które przejdą (RSS/oficjalne API, robots RFC 9309, ToS).
- Wynik: tabela pokrycia per aktywo.

### 12a. Wynik rozszerzenia (2026-10-07)

| źródło | kanał | HTTP / pozycje | robots.txt (RFC 9309) | ToS | status |
|---|---|---|---|---|---|
| CFTC komunikaty | cftc.gov/RSS/RSSGP/rssgp.xml | 200 / 10 | dozwolone | rząd federalny USA (17 U.S.C. §105); strona polityk 404, zakazów brak | **AUTO** |
| CFTC egzekucja | cftc.gov/RSS/RSSENF/rssenf.xml | 200 / 10 | dozwolone | j.w. | **AUTO** |
| OFAC (sankcje) | ofac.treasury.gov/rss.xml | 200 / 10 | dozwolone | rząd federalny USA; „Site Policies” bez zakazów | **AUTO** |
| Departament Skarbu | home.treasury.gov/rss.xml | 200 / 10 | dozwolone | j.w. | nie dodany — kanał to FAQ programów, nie komunikaty |
| Bank of England | bankofengland.co.uk/rss/news | 200 / 50 | dozwolone | „download, display or print … for personal use … non-commercial” | **AUTO** |
| BIS | bis.org/doclist/all_pressrels.rss | 200 / 10 | dozwolone | „download, display, print … for non-commercial purposes”, cytować BIS | **AUTO** |
| IMF | imf.org/en/News/RSS | **403** (także strony) | — | — | RĘCZNA |
| GDELT DOC 2.0 API | api.gdeltproject.org/api/v2/doc/doc (5 tematów) | **429** | brak robots.txt (404) | „unlimited and unrestricted use …”, cytować GDELT przy redystrybucji | **wyłączone 2026-10-10** (`enabled: False`, DECISIONS: stały limit 429; gdelt_fed i gdelt_krypto 0 udanych pobrań). Wcześniej: w jobie, ale **nieaktywny**: 429 z komunikatem „one every 5 seconds” już przy pierwszym zapytaniu i przy pojedynczym zapytaniu po 2 min przerwy. Job wysyła najwyżej 1 zapytanie/h (po limicie reszta tematów pominięta); ruszy sam, gdy limit zniknie. Bez obchodzenia. |

GDELT: `published_at` = `seendate` (moment zauważenia przez GDELT, nie publikacji). Alternatywa zgodna z zasadami, gdy
DOC API pozostanie zablokowane: źródłowe URL-e ze zdarzeń GDELT 2.0, które już zbieramy codziennie (data/gdelt.duckdb,
bez tytułów) — osobna decyzja.

### 12b. Zdarzenia GDELT jako wiadomości i druga runda źródeł (2026-10-07)

**Zdarzenia GDELT 2.0** (już zbierane; przyrost co godzinę w jobie news, ~15 s; snapshot czeka na blokadę news przed
swoim krokiem GDELT): wpis na (temat, adres źródła) — adres, CAMEO, kraje, ton, Goldstein, wzmianki, `published_at` =
DATEADDED, `known_at` = chwila zbudowania wpisu. Bez wchodzenia na strony artykułów, bez par USA–USA. Tematy → aktywa
z mapy zależności i definicji 4H: ropa (producenci ropy wg `ms.hyp_events.PRODUCERS` — w tym IRN, RUS — albo Ormuz /
Morze Czerwone; O3, O4, O14) → WTI, BRENT; sankcje (CAMEO 163; O15, G8) → WTI, BRENT, XAU, makro; konflikt zbrojny
(CAMEO 18–20; G6, C14) → XAU, BTC, ETH. Srebro: brak tematu w mapie — nie przypisujemy. DOC API zostaje (1 zapytanie/h).

**Druga runda** (kanał, robots.txt RFC 9309, ToS — cytaty sprawdzone w zapisanych stronach):

| źródło | aktywa | kanał | robots | ToS (sedno) | status |
|---|---|---|---|---|---|
| Hellenic Shipping News | WTI, BRENT | /feed/ (200 / 20) | przy sondzie dozwolone, **potem 403** | strona RSS: czytnik wiadomości, „proper format and attribution”; zakaz republikacji | w SOURCES, **wyłączone** (robots.txt 403; kontrola co dobę, bez obejścia) |
| gCaptain | WTI, BRENT | /feed/ (200 / 12) | dozwolone | brak warunków (tylko prywatność) | **AUTO** |
| Offshore Energy | WTI, BRENT | /feed/ (200 / 50) | dozwolone | brak warunków (tylko prywatność) | **AUTO** |
| Bitcoin Magazine | BTC | /feed (200 / 10) | dozwolone | „Unauthorized reproduction, distribution, or modification is prohibited…”; o automatach nic | **AUTO, tylko tytuł i link** |
| SilverSeek (kandydat własny) | XAG | /rss.xml (200 / 10) | dozwolone | „Any copying, reproduction and/or redistribution … without the express written consent … is strictly prohibited” | **AUTO, tylko tytuł i link** |
| Oil & Gas Journal | ropa | RSS (200 / 25) | dozwolone | „use robots, spiders, scripts … using automated means … cache or archive the Content” zakazane | RĘCZNA (ToS) |
| Decrypt | krypto | /feed (200 / 37) | dozwolone | Services obejmują „RSS feeds”; zakaz „automated means”, „cache or archive” | RĘCZNA (ToS) |
| CryptoSlate | krypto | /feed/ (200 / 10) | dozwolone | zakaz „scrape, crawl, harvest, cache”, botów i narzędzi automatycznych | RĘCZNA (ToS) |
| World Oil (kandydat własny) | ropa | RSS (200 / 10) | robots 404 | „Any use of automated tools, bots, or scripts for data collection or extraction is strictly prohibited” | RĘCZNA (ToS) |
| Sprott | srebro, złoto | brak kanału RSS | — | zakaz „scraping or data-mining” | RĘCZNA |
| BullionVault Gold News | złoto | brak kanału RSS | — | warunki handlowe, nic o treści | RĘCZNA (brak kanału) |
| Mining Weekly | złoto, srebro | brak kanału (404); warunki 403 | — | nie do otwarcia | RĘCZNA |
| Energy Voice (kandydat własny) | ropa | 403 (strona i robots) | 403 | nie do otwarcia | RĘCZNA |
| Money Metals Exchange (kandydat własny) | srebro | 403 (strona i robots) | 403 | nie do otwarcia | RĘCZNA |

Źródło wyłączone przez robots/odmowę: powiadomienie raz przy zmianie stanu, nie awaria joba; stan w tools/health.sh.

### 12c. GoldSeek i sortowanie zdarzeń (2026-10-07)

- **GoldSeek** (złoto): goldseek.com/rss.xml 200 / 10; robots.txt dozwolone (RFC 9309); stopka: „Any copying,
  reproduction and/or redistribution … without the express written consent of GoldSeek.com … is strictly prohibited”;
  strona „Full disclaimer” → 404; o automatach nic → **AUTO, tylko tytuł i link** (jak SilverSeek).
- Karty dashboardu: wpisy ze zdarzeń GDELT z ostatnich 24 h sortowane po liczbie wzmianek (`num_mentions`, kolumna
  `news_items.mentions`); kanały RSS bez zmian (po czasie).
