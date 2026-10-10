# Źródła wiadomości — lista ręczna (bez automatów)

Etap 4N-live (docs/ETAP4N-LIVE-PLAN.md). Źródła, których program **nie pobiera**: zakaz automatów (ToS albo robots.txt
wg RFC 9309), blokada (403) albo brak kanału RSS/API. Blokad nie obchodzimy (inny User-Agent, scrapowanie stron itp.).
Sprawdzone 2026-10-07. Warunek powrotu do automatu: pojawi się RSS/oficjalne API albo zmieni się robots.txt/ToS —
każda zmiana = ponowna weryfikacja i wpis w DECISIONS.

| źródło | aktywa | powód | co można zrobić ręcznie |
|---|---|---|---|
| EIA Today in Energy + komunikaty | ropa | robots.txt: `User-agent: *` → `Disallow: /rss` (D1) | dane liczbowe EIA mamy z API (WPSR, STEO); komentarze czytać na eia.gov |
| OPEC komunikaty | ropa | brak publicznego kanału; /rss i strona warunków → 403 | przegląd komunikatów przy posiedzeniach OPEC+ |
| IEA news | ropa | brak kanału RSS (treść CC BY 4.0, ale bez RSS) | Oil Market Report / news raz w miesiącu |
| OilPrice | ropa | ToS: zakaz robotów i automatycznego monitorowania (D10) | czytać w przeglądarce |
| Kitco News | złoto, srebro | ToS: zakaz robotów; brak kanału RSS | czytać w przeglądarce |
| Mining.com | złoto, srebro | 403 (także strona główna) | czytać w przeglądarce |
| LBMA | złoto, srebro | brak kanału RSS, brak warunków strony | komunikaty LBMA przy zmianach rynku |
| CoinDesk | krypto | ToS: zakaz automatów bez pisemnej zgody (D10, bez maili) | czytać w przeglądarce |
| Cointelegraph | krypto | ToS: zakaz automatycznego scrapowania i przechowywania (D10) | czytać w przeglądarce |
| NBP | makro (PLN) | brak kanału RSS; ochrona przed botami (Incapsula) | komunikaty RPP po posiedzeniach |
| IMF | makro | 403 (strony i /News/RSS) | przegląd przy publikacjach WEO/GFSR |
| Departament Skarbu USA (komunikaty) | makro, sankcje | jedyny kanał (home.treasury.gov/rss.xml) to FAQ programów, nie komunikaty | sankcje pokrywa kanał OFAC (automat) |
| Oil & Gas Journal | ropa | ToS (Endeavor): zakaz automatów, cache i archiwizacji | czytać w przeglądarce |
| World Oil | ropa | ToS (Gulf Energy): zakaz narzędzi automatycznych | czytać w przeglądarce |
| Energy Voice | ropa | 403 (strona, robots.txt, warunki) | czytać w przeglądarce |
| Hellenic Shipping News | ropa, żegluga | robots.txt zwraca 403 (wcześniej 200) — w SOURCES, wyłączone automatycznie; powrót, gdy robots.txt znów będzie dostępny i pozwoli | czytać w przeglądarce |
| Decrypt | krypto | ToS: zakaz automatów, obejmuje RSS | czytać w przeglądarce |
| CryptoSlate | krypto | ToS: zakaz botów, scrapowania, cache | czytać w przeglądarce |
| Sprott | srebro, złoto | brak RSS; ToS: zakaz scrapowania | komentarze kwartalne |
| BullionVault Gold News | złoto | brak kanału RSS | czytać w przeglądarce |
| Mining Weekly | złoto, srebro | brak kanału; warunki 403 | czytać w przeglądarce |
| Money Metals Exchange | srebro | 403 (strona, robots.txt, warunki) | czytać w przeglądarce |
