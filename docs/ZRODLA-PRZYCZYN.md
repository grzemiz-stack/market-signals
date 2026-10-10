# Źródła: przyczyny historycznych ruchów cen

Stan: 2026-10-06. Cel: etykiety „dzień / miesiąc → ruch ceny → przyczyna” do (1) wyjaśniania dużych ruchów w statusie, (2) nauki i sprawdzania klasyfikatora lokalnego LLM (Qwen), (3) badań zdarzeń w 4H.

**Najważniejszy wniosek z researchu:** nie istnieje darmowy, gotowy zbiór „ruch ceny surowca/krypto → przyczyna” dla lat 2004–2026. Trzeba go złożyć z trzech warstw: kalendarza zdarzeń, gotowych etykiet z badań i strumienia newsów tagowanego lokalnie. Taksonomię przyczyn bierzemy z Baker–Bloom–Davis–Sammon (jedyny duży, ręcznie kodowany zbiór przyczyn skoków).

Licencje: `CC BY` / domena publiczna = bez ograniczeń. `NC` = tylko użytek prywatny i badawczy; jeśli system kiedyś będzie sprzedawany komuś innemu, te zbiory trzeba wyciąć. Każde źródło dostaje kolumnę `license` w bazie, jak dotąd.

`[n]` = nie udało się otworzyć pliku, tylko stronę.

---

## Priorytet 1 — pobrać teraz (darmowe, bez rejestracji, czysta licencja)

| # | Źródło | Co daje | Okres | Licencja | URL |
|---|---|---|---|---|---|
| P1 | **Baker–Bloom–Davis–Sammon „What Triggers Stock Market Jumps”** | ~6–8 tys. skoków z ręcznie przypisaną przyczyną (commodities, macro, monetary, sovmil, terror, trade policy, regulation, elections, unknown) + zakładka `key_passages` (cytaty z gazet) + pewność dziennikarza | USA od 1900, 16–19 krajów | akademicka, bez podanej licencji | [Google Sheet](https://docs.google.com/spreadsheets/d/1fkIIishR6LsAtZSv-_cpvyJtuSytemiVYjGUiRgYvNI), [strona](https://sites.google.com/view/stock-market-jumps/home) |
| P2 | **AI-GPR + Oil GPR** (Caldara–Iacoviello 2026) | dzienny indeks ryzyka geopolitycznego z podziałem na typ (wojna, terror, sankcje, zamach, nuklearne), 200 krajów; **osobny Oil GPR**: zagrożenia vs akty | od 1960, aktualizacja 30.09.2026 | klasyczny GPR CC BY; AI-GPR licencja niepodana | [AI-GPR](https://www.matteoiacoviello.com/ai_gpr.html) `[n]` plik |
| P3 | **Niespodzianki FOMC** (SF Fed Bauer–Swanson; Jarociński–Karadi) | wielkość niespodzianki w oknie 30 min wokół komunikatu; JK rozdziela szok stopy od szoku informacyjnego | 1988–2026 | publiczne | [SF Fed xlsx](https://www.frbsf.org/wp-content/uploads/monetary-policy-surprises-data.xlsx), [JK GitHub](https://github.com/marekjarocinski/jkshocks_update_fed_202401) |
| P4 | **EIA „World Oil Market and Oil Price Chronologies 1970–2003”** | ~350–400 wpisów: data + opis zdarzenia (embargo, wojny, decyzje OPEC) | 1970–2003 | domena publiczna | [kopia](https://laohamutuk.org/OilWeb/Finances/PetFund/PFPassage/PFPaper/EIA%20Chronology.htm) |
| P5 | **Wikipedia „Chronology of world oil market events”** | >300 wpisów data + zdarzenie, ze źródłami (DJ, FT, WSJ, Platt's) | 1970–~2005 | CC BY-SA | [link](https://en.wikipedia.org/wiki/Chronology_of_world_oil_market_events) |
| P6 | **Nazer & Pescatori, IMF WP/22/183** | 101 spotkań OPEC z typem decyzji (cięcie / bez zmian / podwyżka) | 1987–2019 | darmowy PDF (tabela do wyciągnięcia) | [PDF](https://www.imf.org/-/media/Files/Publications/WP/2022/English/wpiea2022183-print-pdf.ashx) |
| P7 | **DefiLlama hacks API** | ~500+ hacków: data, kwota, typ ataku, łańcuch | od 2011 | darmowe API | [api.llama.fi/hacks](https://api.llama.fi/hacks) |
| P8 | **Daty stałe do wpisania ręcznie** | halvingi (28.11.2012, 9.07.2016, 11.05.2020, 20.04.2024); depegi (DAI 12.03.2020, IRON 16.06.2021, UST 7–13.05.2022, USDT 12.05.2022, USDC 10–13.03.2023, FDUSD 2.04.2025); spot ETF BTC 10.01.2024, ETH 23.07.2024; FTX 11.2022; chińskie zakazy 09.2017 i 05–09.2021 | — | fakty | — |

Już mamy w bazie: Känzig OPEC (169 dat), szoki Baumeister–Hamilton, GPR klasyczny, EPU, GDELT, kalendarz FOMC i huraganów.

## Priorytet 2 — wartościowe, ale wymagają pracy

| # | Źródło | Co daje | Problem |
|---|---|---|---|
| W1 | **WGC Gold Market Commentary** (archiwum od 2013) | ~150 miesięcy tekstu „dlaczego złoto się ruszyło”, nowsze z wykresem GRAM | scrapowanie i parsowanie; T&C WGC (użytek prywatny) |
| W2 | **WGC GRAM** | miesięczny wkład 5 czynników w zwrot złota — gotowe etykiety liczbowe | darmowa rejestracja; czy jest eksport `[n]` |
| W3 | **WGC: banki centralne (xlsx) i przepływy ETF** | miesięczne zakupy od 2002, przepływy ETF tygodniowo | darmowa rejestracja → ręczna skrzynka `data/inbox/wgc/` |
| W4 | **SlowMist Hacked** | 2299 hacków do 10.2026, najpełniejsza lista | brak eksportu, trzeba scrapować |
| W5 | **Farside ETF flows** (BTC od 01.2024, ETH od 07.2024) | dzienne przepływy na ETF | tylko tabela HTML |
| W6 | **World Silver Survey** (roczne) | jedyna narracja przyczyn dla srebra | PDF przez formularz; tylko rocznie |
| W7 | **Hamilton „Historical Oil Shocks”** (9 epizodów) i **Baumeister–Kilian „Forty Years”** (~9 epizodów z podziałem podaż/popyt/zapasy) | mały, wzorcowy zbiór testowy do sprawdzania wyjaśnień | ręczne przepisanie (~20 wierszy) |
| W8 | **Forex Factory Calendar** (HF) | actual vs forecast dla danych makro 2007–2025 → darmowa „niespodzianka makro” | dane zeskrapowane, pochodzenie niepewne |

## Priorytet 3 — korpusy newsów do nauki klasyfikatora (licencje NC)

| # | Zbiór | Rozmiar | Etykieta | Licencja |
|---|---|---|---|---|
| N1 | **CryptoVision** (Mendeley) | 188 tys. newsów 2017–2025 + cena w oknie 15 min po publikacji | kierunek ruchu po newsie | `[n]` (Mendeley zwykle CC BY) |
| N2 | **Gold news headlines** (Sinha & Khandait) | 10,5 tys. nagłówków 2000–2021 | ręczne: kierunek ceny, sentyment (kappa > 0,85) | CC BY-NC-ND |
| N3 | **CrudeOilNews Corpus** (LREC 2022) | 425 artykułów, ~11 tys. zdarzeń | 18–19 typów zdarzeń ropy (oversupply, embargo, tensions…) | MIT (tylko adnotacje) |
| N4 | **EGPBD** (Mendeley) | 8 tys. dni 2001–2022, złoto + makro | kategorie zdarzeń 0–5 z newsów | `[n]` |
| N5 | **Financial News Multisource** (HF) | 57 mln nagłówków 1990–2025, 24 źródła, czas do minuty | brak (surowy strumień) | NC |
| N6 | **DLT-Sentiment-News** / **CoinDesk 2019–2025** (HF) | 23 tys. / 229 tys. artykułów krypto | sentyment społeczności / brak | CC BY-NC |

---

## Jak z tego zrobić etykiety przyczyn (pipeline)

1. **Duże ruchy:** dni z |zwrot| > 2,5σ (σ z 252 dni, tylko przeszłość) dla każdego aktywa.
2. **Najpierw kalendarz** (deterministycznie, bez LLM): FOMC + niespodzianka (P3), OPEC (Känzig + typ z P6), EIA WPSR, huragan, halving/depeg/ETF (P8), hack > 100 mln USD (P7), skok Oil GPR / AI-GPR (P2). Dzień dostaje etykietę `kalendarz:<typ>`.
3. **Reszta dni:** lokalny Qwen czyta nagłówki z okna [t−1, t] (GDELT + N5) i przypisuje przyczynę według **taksonomii BBDS (P1)** rozszerzonej o: `podaż_ropy`, `popyt_globalny`, `fizyczny_niedobór_metalu`, `krypto_regulacja`, `krypto_hack`, `krypto_etf`, `dźwignia_likwidacje`. Few-shoty z zakładki `key_passages` BBDS.
4. **Walidacja klasyfikatora przed użyciem** (zasada: LLM tylko klasyfikuje):
   - ropa 1970–2003: zgodność z chronologią EIA/Wikipedii (P4, P5);
   - złoto 2013–2026: zgodność z komentarzami WGC (W1);
   - wzorcowe epizody (W7) — ręcznie sprawdzone;
   - wynik: % zgodności na zbiorze testowym, zapisany w `runs`. Bez progu zgodności klasyfikator nie trafia do statusu.
5. **PIT:** etykieta przyczyny jest wiedzą *po fakcie* — służy do wyjaśniania i do badań zdarzeń, **nigdy jako cecha prognozy dla tego samego dnia**.
