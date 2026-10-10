# Mapa zależności — co rusza cenami (hipotezy do testu)

Stan: 2026-10-06. Źródło: przegląd publikacji naukowych, banków centralnych, raportów branżowych (WGC, Silver Institute, EIA, IEA, OPEC) i źródeł praktyków. Każdy wiersz to **hipoteza z literatury**, nie fakt o dzisiejszym rynku. System sprawdza każdą na naszych danych (sekcja „Jak testujemy”). Kolumna „Status” jest wypełniana przez testy, nie ręcznie.

Oznaczenia: `[n]` = liczba niezweryfikowana w źródle pierwotnym, `[w]` = źródło wtórne (prasa/portal/praktyk).

## Zasady, które wynikają z literatury dla wszystkich aktywów

1. **Zależności zmieniają się z reżimem.** Stała beta to błąd. Liczymy beta kroczące z przedziałem i % okien z tym samym znakiem.
2. **Przy zdarzeniach liczy się niespodzianka, nie samo zdarzenie** (OPEC przewidywalny w ~66%, zapasy EIA = fakt − konsensus, FOMC = zmiana futures w dniu decyzji).
3. **Ten sam typ newsa może działać w obie strony** (wojna: ropa ↑ albo ↓, złoto ↑ albo ↓ przez Fed). Agenci muszą klasyfikować **kanał**, nie tylko „napięcie”.
4. **Dźwignia i pozycjonowanie mówią o skali ruchu, nie o kierunku i momencie.**
5. **Regresje na poziomach dają fałszywe R²** (M2, przepływy ETF). Testujemy na zmianach.

---

## Złoto (XAU)

| ID | Czynnik / seria | Znak | Horyzont | Wielkość efektu (okres) | Stabilność | Źródło |
|---|---|---|---|---|---|---|
| G1 | Realne stopy 10Y (DFII10) | − | miesiące | +1 pp → −13% realnej ceny (1971–2021) | **Załamanie**: R² 84% (2005–21) → 3% (2022–23) → 7% (od 2024). Nasz decomp: beta −0,078 → −0,029 | [Chicago Fed CFL 464](https://www.chicagofed.org/-/media/publications/chicago-fed-letter/2021/cfl464-pdf.pdf), [RBC WM](https://www.rbcwealthmanagement.com/en-us/insights/golds-regime-change) |
| G2 | Oczekiwania inflacyjne (T10YIE) | + | miesiące–lata | +1 pp → +37% (przed 2001 dominujące) | słabnie; 2025–26 breakeven ~2,3% przy złocie +48% | Chicago Fed, [NIESR](https://niesr.ac.uk/blog/digging-into-the-debasement-trade) |
| G3 | Dolar (DTWEXBGS / koszyk GRAM) | − | dni–tygodnie | korelacja stale ujemna (1971–2018) | stabilne | [WGC](https://www.gold.org/goldhub/research/investment-update-gold-tracks-dollar-rates-take-back-seat) |
| G4 | Niespodzianka FOMC | sporny | 1–2 dni | badania nie zgadzają się co do znaku | niestabilne | [IRFA 2024](https://pure.kfupm.edu.sa/en/publications/how-do-the-gold-intra-day-returns-and-volatility-react-to-monetar/), Atlanta Fed `[w]` |
| G5 | Krach akcji / VIX | + | ~15 dni sesyjnych | „bezpieczna przystań” tylko ~15 dni po krachu (1995–2005) | 2025: BIS — złoto i akcje rosną razem spekulacyjnie | [Baur & Lucey via CXO](https://www.cxoadvisory.com/gold/gold-as-hedge-and-safe-haven/), [BIS via Swissinfo](https://www.swissinfo.ch/eng/gold-surge-sees-shift-to-speculative-asset-from-haven%2c-bis-says/90603008) `[w]` |
| G6 | Ryzyko geopolityczne (GPR) | + | tygodnie | +100 pkt GPR → ~+2,5%; dodaje tylko 1 pkt R² w GRAM | skoki krótkotrwałe; **kanał pośredni: wojna → ropa → inflacja → jastrzębi Fed → złoto ↓** (2026) | [WGC 2023](https://www.gold.org/goldhub/gold-focus/2023/10/you-asked-we-answered-whats-impact-of-geopolitics-on-gold) |
| G7 | Zakupy banków centralnych | + | kwartały | 100 t → ≥ +2,4% (Goldman); 20–30 t → ~+1% (WGC) | **nowy reżim od 2022**: >1000 t/rok vs 473 t (2010–21) | [Goldman](https://www.goldmansachs.com/insights/articles/gold-predicted-to-climb-higher-than-expected-as-records-shatter), [ECB](https://ecb.europa.eu/press/other-publications/ire/focus/html/ecb.irebox202506_01~f93400a4aa.en.html) |
| G8 | Sankcje / ryzyko zamrożenia rezerw | + | lata | 5 z 10 największych przyrostów rezerw złota od 1999 to kraje objęte sankcjami | punkt zwrotny: zamrożenie rezerw Rosji 2022 | [VoxEU/BdF 09.2026](https://cepr.org/voxeu/columns/fools-gold-how-geopolitical-risk-taking-some-shine-us-dollar), [SUERF 414](https://www.suerf.org/wp-content/uploads/2026/07/SUERF-Policy-Note-414_-Bindseil-Daskalova-Senner.pdf) |
| G9 | Przepływy do ETF (GLD, WGC) | + | tygodnie–miesiące | brak opublikowanej bety | zachodnie ETF reagują na stopy | [WGC 07.2026](https://www.gold.org/goldhub/research/gold-market-commentary-july-2026) |
| G10 | COT managed money | + przy narastaniu, skrajność → korekta | tygodnie | <100k → >250k kontraktów przy +40% (2018–20) | skrajności poprzedzają korekty `[w]` | [Perth Mint](https://www.perthmint.com/news/investor/market-research-and-analysis/what-managed-money-gold-positions-might-be-telling-us/) |
| G11 | Momentum 1–12 mies. | + | do ~12 mies., potem odwrócenie | TSMOM (1985–2009) | 07.2026 najsilniejszy składnik GRAM | [AQR](https://www.aqr.com/Insights/Datasets/Time-Series-Momentum-Original-Paper-Data) |
| G12 | Indie: cło, popyt jubilerski | − popytu przy wysokiej cenie | miesiące, sezon | cło 6% → 15% (05.2026) → −50–60 t | stabilizator, nie motor | [Business Today/WGC](https://www.businesstoday.in/latest/economy/story/indias-higher-gold-import-duty-could-cut-demand-by-up-to-60-tonnes-in-2026-wgc-540366-2026-07-01) |

**Wniosek dla złota:** strach przed kryzysem i wojną działa, ale głównie **przez banki centralne** (strukturalnie, kwartały–lata), a nie przez krótkie skoki strachu. Krótki efekt geopolityki jest mały (~2,5% na 100 pkt GPR) i może się odwrócić, gdy wojna podbija ropę i inflację. Tak było w 2026: szczyt 5 595 USD (29.01), potem −19% przy kryzysie w Ormuzie i jastrzębim Fedzie `[w]`.

---

## Srebro (XAG)

| ID | Czynnik / seria | Znak | Horyzont | Wielkość efektu (okres) | Stabilność | Źródło |
|---|---|---|---|---|---|---|
| S1 | Złoto | + | ciągły | beta ~1,0 (1972–95), ~0,35 (lata 90.), ~0,8 (od 2000) | kointegracja nieliniowa i niestabilna | [Brady, UC Denver](https://business.ucdenver.edu/jpmorgancenter/sites/default/files/attached-files/the_gold_to_silver_ratio_04032020_uc_denver_0.pdf), [Schweikert 2018](https://ideas.repec.org/a/eee/jbfina/v88y2018icp44-51.html) |
| S2 | Miedź / cykl (HG, PMI, IP) | + | miesiące | DCC srebro–miedź 0,41 (2006–11); model IP+ISM+TIPS+ETF R² ~80% na zmianach r/r (1990–2016) | komponent przemysłowy rośnie w 2026 `[w]` | [Tsiaras 2020](https://spoudai.unipi.gr/index.php/spoudai/article/download/2827/2713), [Goldmoney](https://www.goldmoney.com/research/silver-price-framework) |
| S3 | Makro monetarne | — | — | zmienności srebra **nie** tłumaczą zmienne monetarne (w przeciwieństwie do złota) | — | [Batten, Ciner, Lucey 2010](https://ideas.repec.org/a/eee/jrpoli/v35y2010i2p65-71.html) |
| S4 | Popyt PV (fotowoltaika) | + (słabnie) | lata | 197,5 Moz (2024) → 151 Moz (2026P, −19%) | **odwrócenie**: motor 2021–24, od 2025 spada; substytucja miedzią | [Mercom (WSS 2026)](https://mercomindia.com/silver-demand-forecast-to-drop-19-in-2026-on-lower-solar-cell-loadings) |
| S5 | Podaż kopalń | słabo reaguje | lata | ~75% podaży to produkt uboczny Pb/Zn/Cu/Au | zależy od cen innych metali | [Silver Institute WSS 2026](https://silverinstitute.org/?p=20226) |
| S6 | Deficyt rynku | + przez zapasy | rok | 2025: 95 Moz (interim) → 40,3 Moz po rewizji `[w]`; 2026P 46,3 Moz | szósty rok deficytu, ale liczby mocno rewidowane | WSS 2026, [Interim 2025](https://silverinstitute.org/wp-content/uploads/2025/11/Silver_Institute_Silver_Interim_2025.pdf) |
| S7 | Free float LBMA, lease rate, spread Londyn–NY | ciasno → + (squeeze) | zdarzenie, tygodnie | lease 1M ~39% (10.2025) vs norma <1%; free float ~136 Moz | wyzwalacz squeezów 2025–26 `[w]` | [In Gold We Trust](https://ingoldwetrust.report/journal/the-great-silver-squeeze-of-october-2025-when-physical-reality-took-control/?lang=en), [Kitco](https://www.kitco.com/opinion/2026-04-23/londons-silver-running-out-room) |
| S8 | Cła USA / lista critical minerals | + (premia US) | zdarzenie | srebro na liście USGS od 6.11.2025; Section 232 bez ceł (01.2026), dalej otwarte | reżim od 12.2024 | [USGS](https://www.usgs.gov/news/science-snippet/interior-department-releases-final-2025-list-critical-minerals), [Thompson Hine](https://www.thompsonhinesmartrade.com/2026/01/no-section-232-tariff-now-on-processed-critical-minerals-and-their-derivative-products/) |
| S9 | ETF (SLV i inne) | + | tygodnie | brak opublikowanej elastyczności | ETF blokują free float w Londynie | Interim 2025 |
| S10 | Indie (import, festiwale X–XI) | + | sezon | import 2024 ~225 Moz | wyzwalacz squeezu 10.2025 `[w]` | [Kitco/Reuters](https://www.kitco.com/news/off-the-wire/2025-09-16/indias-silver-imports-gain-momentum-strong-investment-demand) |
| S11 | Marginesy CME | podwyżka → − | dni | ATH 121,6 USD (29.01.2026), potem −13% i −21% w dwie sesje; 3 podwyżki marginesu | od 13.01.2026 marginesy procentowe | [S&P Global](https://www.spglobal.com/market-intelligence/en/news-insights/research/2026/02/the-rise-and-fall-of-the-silver-price) |
| S12 | Gold/silver ratio | wysoki → srebro lepsze (teza praktyków) | miesiące–lata | — | **brak dowodu akademickiego** na powrót do średniej | Brady, [HB Wealth](https://hbwealth.com/wp-content/uploads/2026/08/8.26.2026-Silvers-Dual-Identity-May-Shine-Through-as-Secular-Meets-Cyclical.pdf) `[w]` |
| S13 | COT managed money | skrajność → odwrócenie | tygodnie | **brak badania akademickiego dla srebra** | — | [Saxo](https://home.saxo/en-gb/content/articles/commodities/cot-on-commodities-18052020) `[w]` |

**Wniosek dla srebra:** to dwa aktywa w jednym (monetarne + przemysłowe), a w ostatnich latach do tego **fizyka rynku**: brak metalu w Londynie, przepływy do NY przez cła, Indie. Te rzeczy ruszały ceną bardziej niż makro. Twoja pozycja w grze (srebro po −6%) leży dokładnie w tym obszarze.

---

## Ropa (WTI / Brent)

| ID | Czynnik / seria | Znak | Horyzont | Wielkość efektu (okres) | Stabilność | Źródło |
|---|---|---|---|---|---|---|
| O1 | Szok podażowy | spadek podaży → + | szybko, częściowo wraca | elastyczność podaży 0,15, popytu −0,35 (1975–2016) | spór Kilian vs Baumeister–Hamilton | [Kilian 2009](https://www.nber.org/papers/w15002), [B–H AER](https://www.aeaweb.org/doi/10.1257/aer.20151569) |
| O2 | Popyt globalny (IGREA, fracht) | + | opóźnienie ~6 mies., trwały | główny motor wzrostów od 2003 (Kilian) | stabilne | [Dallas Fed IGREA](https://www.dallasfed.org/research/igrea) |
| O3 | Popyt zapobiegawczy (strach) | + przy strachu | natychmiast, z przestrzeleniem | kanał geopolityki Bliskiego Wschodu | zależy od identyfikacji | [St. Louis Fed](https://www.stlouisfed.org/on-the-economy/2015/january/oil-prices-is-supply-or-demand-behind-the-slump) |
| O4 | GPR: energetyczny vs reszta | energ. → +, nieenerg. → − | ~2 kwartały | szok podażowy kalibrowany na −10% akcji → ~+30% ropy (1990–2026) | **działa w obie strony** | [ECB EB 4/2026](https://www.ecb.europa.eu/press/economic-bulletin/focus/2026/html/ecb.ebbox202604_02~7d79ce3c90.en.html) |
| O5 | Niespodzianka OPEC+ (zmiana futures w dniu komunikatu) | cięcie → + | natychmiast | 119 komunikatów (1983–2017); decyzje przewidywalne w 66% | dyscyplina członków zmienna | [Känzig/AEA](https://www.aeaweb.org/research/charts/oil-supply-news-opec-announcements), [IMF WP 22/183](https://ideas.repec.org/p/imf/imfwpa/2022-183.html) |
| O6 | Zapasy EIA vs konsensus | build ponad oczekiwania → − | tylko dzień publikacji | 1% niespodzianki → −0,48%; po 2009 −0,23% | efekt zmalał | [Halova/Kurov/Kucher](https://www.skidmore.edu/economics/documents/NoisyInventoryAnnouncementsAndEnergyPrices.pdf) |
| O7 | Krzywa terminowa (backwardation/contango) | backwardation = ciasno (+) | ciągły | spread spada przy wzroście zapasów OECD | najlepsza ciągła miara ciasnoty | [EIA](https://www.hydrocarbonengineering.com/refining/29012015/changing-futures-price-spreads-134/) |
| O8 | Zapasy globalne | spadek → + | miesiące | 2026: −400 mln bbl od początku roku | reżim kryzysowy 2026 | [EIA STEO 09/2026](https://www.eia.gov/outlooks/steo/archives/sep26.pdf) |
| O9 | COT managed money | trend; skrajność → ryzyko odwrócenia | tygodnie | akademicko brak istotnej roli spekulacji 2003–08 | sygnał ryzyka, nie kierunku | [OIES](https://www.oxfordenergy.org/?p=28178) |
| O10 | Marże rafineryjne (crack 3-2-1) | + | tygodnie | brak liczbowej elastyczności | — | [EIA](https://www.eia.gov/todayinenergy/detail.php?id=44656) |
| O11 | Chiny: import i magazynowanie | + | miesiące | ~0,9 mb/d do zapasów (I–VIII 2025) podparło cenę | Chiny nie publikują zapasów | [JPT/EIA](https://jpt.spe.org/chinas-expanding-crude-storage-supports-global-oil-prices) |
| O12 | Dolar | klasycznie −, ostatnio bywa + | ciągły | brak stałego współczynnika | **niestabilny od ~2019** (USA eksporterem netto) | [BIS Bull. 74](https://www.bis.org/publ/bisbull74.pdf) |
| O13 | Huragany (VI–XI) | ropa umiarkowanie +, produkty mocniej | zdarzenie | scenariusz EIA: +4 USD/bbl | — | [EIA](https://www.eia.gov/outlooks/steo/report/perspectives/2023/07-hurricanes/article.php) |
| O14 | Ormuz / Morze Czerwone | zakłócenie → mocno + | zdarzenie | Ormuz 20 mb/d (~20% konsumpcji); 2026: wyłączenia 6,7 mb/d | **bieżący reżim kryzysowy** | [EIA](https://eia.gov/todayinenergy/detail.php?id=65504), STEO 09/2026 |
| O15 | Sankcje (Rosja, Iran) | głównie dyskonta i trasy | miesiące | dyskonto Urals 32 USD: 15 transport + 17 siła negocjacyjna | shadow fleet osłabia skutek | [Dallas Fed WP 2401](https://www.dallasfed.org/research/papers/2024/wp2401) |
| O16 | SPR (rezerwy strategiczne) | uwolnienie → − | miesiące | 2022: 180 mln bbl → benzyna −17–42 c/gal | szacunek Treasury | [Treasury](https://mondovisione.com/media-and-resources/news/the-price-impact-of-the-strategic-petroleum-reserve-release-by-us-assistant-se-2022726/) |
| O17 | Łupki USA (rigi, breakeven) | wysoka cena → więcej podaży | 6–12 mies. `[n]` | breakeven: nowy odwiert 66 USD, istniejące 43 USD (Dallas Fed 1Q26) | miękki sufit i podłoga | [Dallas Fed DES](https://www.dallasfed.org/research/surveys/des/2026/2601) |
| O18 | OVX | reżim, nie kierunek | ciągły | — | u nas: jedyny model z przewagą (BSS +0,048) | Cboe |

**Wniosek dla ropy:** przy każdym ruchu najpierw trzeba ustalić **typ szoku**: podaż (przejściowy), popyt globalny (opóźniony, trwały) czy strach (natychmiast, z przestrzeleniem). Rok 2026 to reżim kryzysu Ormuz/Iran. To tłumaczy +14,5 pp „niewyjaśnionego” ruchu w tym tygodniu: nasza dekompozycja nie ma takich czynników.

---

## Krypto (BTC / ETH)

| ID | Czynnik / seria | Znak | Horyzont | Wielkość efektu (okres) | Stabilność | Źródło |
|---|---|---|---|---|---|---|
| C1 | Momentum tygodniowe | + | 1–4 tyg. | BTC: +1 SD → +3,16% w następnym tygodniu; ETH słabo (2011–2018) | próba sprzed instytucjonalizacji, **do replikacji 2020–26** | [Liu & Tsyvinski, RFS 2021](https://www.nber.org/system/files/working_papers/w24877/w24877.pdf) |
| C2 | Google Trends | + | 1–3 tyg. | BTC: +1 SD → +1,8–2,3%; ETH +4,4% (do 2018) | do replikacji | Liu & Tsyvinski |
| C3 | Hacki / negatywna uwaga | − | 1 tydz. | −2,75% na 1 SD (do 2018) | — | Liu & Tsyvinski |
| C4 | Akcje (Nasdaq, S&P) | + | dziennie | korelacja 0,01 (2017–19) → 0,36 (2020–21), szczyt 0,87 (2024) | **zmiana reżimu 2020**; asymetryczna: rośnie przy szokach, znika w spokoju | [IMF 2022](https://www.imf.org/en/blogs/articles/2022/01/11/crypto-prices-move-more-in-sync-with-stocks-posing-new-risks) |
| C5 | Fed (zacieśnianie) | − | dni–miesiące | przed 2020 znak dodatni, po 2020 ujemny | **zmiana znaku 2020** | [Karau, JIMF 2023](https://ideas.repec.org/a/eee/jimfin/v137y2023ics0261560623000815.html) |
| C6 | Globalna płynność / M2 | + | miesiące | korelacja 4-letnia 0,4–0,6 | **rozjechało się 2025–26**; regresja na poziomach — ostrożnie | [CF Benchmarks](https://www.cfbenchmarks.com/blog/the-m2-bitcoin-relationship-what-the-data-actually-shows) |
| C7 | Dolar | − | dni–tygodnie | brak liczb | — | CoinDesk `[w]` |
| C8 | Przepływy do spot ETF | + | szczyt po 3–4 dniach | Granger p=0,004; tłumaczą <10% zmian; szok → +1,2% (2024) | przyczynowość w obie strony | [FalconX](https://www.falconx.io/newsroom/what-can-spot-etf-flows-tell-us-about-the-trajectory-of-bitcoin-prices-a-preliminary-statistical-investigation) |
| C9 | Emisja stablecoinów | sporna | godziny–dni | Griffin & Shams vs Lyons: raczej skutek niż przyczyna | — | [VoxEU](https://cepr.org/voxeu/columns/stable-coins-dont-inflate-crypto-markets) |
| C10 | Regulacje | zaostrzenie −, ramy prawne + | 2 h – 10 dni | 24 h: dobre +1,52%, złe −3,12%; ograniczenia banków/ETF −6,4 pp w 10 dni (2015–18) | **złe newsy ważą ~2x więcej** | [BIS QR 09.2018](https://bis.org/publ/qtrpdf/r_qt1809f.htm) |
| C11 | Funding rate | skrajnie wysoki → ryzyko spadku | dni–tygodnie | próg „>15% APR” to heurystyka bez testu `[n]` | — | [He i in.](https://arxiv.org/html/2212.06888v5) |
| C12 | Open interest / likwidacje | wysoki OI + jednostronne longi → większy spadek po szoku | minuty–miesiące | 10.10.2025: >19 mld USD likwidacji, BTC −14,5% | wzmacniacz, nie sygnał czasu | [CoinGecko](https://www.coingecko.com/learn/october-10-crypto-crash-explained) `[w]` |
| C13 | Fear & Greed | zgodny w tym samym okresie; kontrariański słabo | 1–24 mies. | kupno przy „Extreme Fear” gorsze niż losowe na 30–90 dni `[n]` | — | [Huang i in. 2024](https://virtusinterpress.org/How-does-the-Bitcoin-Sentiment-Index-of-Fear-Greed-affect-Bitcoin-returns.html) |
| C14 | Geopolityka (GPR) | ≈0 średnio, − na starcie | dni | korelacja −0,03 (2014–2024); Ukraina: −4,1% po 3 dniach, +13,8% po 7 | **„cyfrowe złoto” się nie potwierdza** | [WisdomTree](https://www.wisdomtree.com/dk/insights/blog/is-bitcoin-a-safe-haven-asset-in-a-geopolitically-uncertain-world), [Aysan 2019](https://ideas.repec.org/a/eee/riibaf/v47y2019icp511-518.html) |
| C15 | Halving | + słabo | ~3 mies. | 2024 ~+24,6% ponad kontrolę; 2020 nieistotny | jeden preprint | [arXiv 2511.05512](https://arxiv.org/pdf/2511.05512) |
| C16 | ETH: ETF i spółki trzymające ETH | + | tygodnie | od 06.2025 ~9,4 mld USD napływu; ETH +70% vs BTC +9% | reżim od 2025 | [The Block](https://www.theblock.co/post/367602/eth-btc-ratio-2025-etfs-treasuries-ethereum) `[w]` |

**Wniosek dla krypto:** od 2020 BTC zachowuje się jak aktywo ryzykowne (Nasdaq, Fed), a nie jak „cyfrowe złoto”. Geopolityka na starcie konfliktu **obniża** BTC. Najlepiej udokumentowane krótkie predyktory (momentum, Google Trends) pochodzą z danych do 2018, więc trzeba je sprawdzić na nowszych.

---

## Jak testujemy (system, nie my)

Dla każdego ID z tabel:
1. **Beta krocząca** na zmianach tygodniowych (okno 52 i 156 tyg.), z przedziałem ±2SE i % okien z tym samym znakiem co w literaturze.
2. **Badanie zdarzeń** dla wierszy zdarzeniowych (FOMC, OPEC, EIA, regulacje, skoki GPR): zwrot w oknach [0,+1], [0,+5], [0,+20] względem okien losowych.
3. **Status**: `potwierdzona` (znak zgodny, CI bez zera, stabilna w ostatnich 3 latach) / `osłabła` / `odwrócona` / `brak danych` / `nie do sprawdzenia` / `niepotwierdzona` (na naszych danych nigdy nie była istotna).
4. **Korekta wielokrotnych testów** (Benjamini-Hochberg) dla całej tabeli i zapis liczby prób w `runs`.
5. Tylko hipotezy `potwierdzone` mogą wejść jako cechy do modeli z rejestru, i nadal muszą tam pobić mistrza.

## Czego agenci informacyjni mają szukać (wynika z mapy)

- **Ropa:** komunikaty OPEC+ (z wynikiem vs oczekiwania), Ormuz/Morze Czerwone/tankowce, sankcje, SPR, huragany, decyzje Chin o imporcie.
- **Złoto:** zakupy banków centralnych (WGC, PBoC miesięcznie), sankcje i zamrożenia rezerw, FOMC, cła w Indiach.
- **Srebro:** lease rate i stan skarbców LBMA, cła/Section 232, marginesy CME, import Indii, dane PV z Chin.
- **Krypto:** regulacje (USA: CLARITY, SEC), hacki giełd, przepływy ETF, zmiany marginesów i duże likwidacje.
- **Każdy wpis klasyfikowany po kanale** (podaż / popyt / strach / polityka monetarna / regulacja / fizyczny niedobór), nie tylko po „napięciu”.

<!-- STATUS:START -->
## Status testów (generowane przez src/test_hypotheses.py — nie edytować ręcznie)

Stan: 2026-10-06. Raport: reports/hipotezy-2026-10-06.md. Test główny: ostatnie 3 lata; obok cała historia.

| ID | aktywo | Status | beta 3 lata | beta cała historia | uwagi |
|---|---|---|---|---|---|
| G1 | XAU | osłabła | -0,006 | -0,041 | cała historia (2003–): istotna −; 3 lata: nieistotna → działała w całej historii, w ostatnich 3 latach przestała [p surowe < 0,05] |
| G2 | XAU | niepotwierdzona | -0,021 | +0,034 | cała historia (2003–): istotna +; 3 lata: nieistotna → działała w całej historii, w ostatnich 3 latach przestała [p surowe < 0,05] |
| G3 | XAU | potwierdzona · kandydat | -1,185 | -1,366 | cała historia (1999–): istotna −; 3 lata: istotna − → działa w obu okresach (beta 3 lata = 87% bety z całej historii) [p surowe < 0,05] |
| G4 | XAU | potwierdzona · kandydat | -0,100 | -0,087 | 227 zdarzeń od 2000: beta CAR na wielkości zdarzenia -0.0872 (p=1.87e-05); ostatnie 3 lata: -0.1003 (26 zdarzeń); znak sporny w literaturze; u nas − |
| G5 | XAU | niepotwierdzona | +0,022 | +0,003 | 69 zdarzeń od 1979: średni CAR ponad losowe +0.0030 (p=0.553); ostatnie 3 lata: +0.0216 (3 zdarzeń) |
| G6 [B] | XAU | niepotwierdzona | -0,000 | +0,000 | cała historia (1985–): nieistotna; 3 lata: nieistotna → nieistotna w obu okresach [p surowe < 0,05] |
| G6 [Z] | XAU | niepotwierdzona | -0,003 | +0,001 | 226 zdarzeń od 1985: średni CAR ponad losowe +0.0009 (p=0.558); ostatnie 3 lata: -0.0025 (17 zdarzeń) |
| G7 | XAU | brak danych | — | — | tylko ręcznie: skrzynka / lista do dostarczenia |
| G8 | XAU | brak danych | — | — | sankcje: GDELT ma kod 163, ale zamrożenie rezerw 2022 to jedno zdarzenie — do decyzji, czy testować sankcje ogólnie |
| G9 | XAU | brak danych | — | — | tylko ręcznie: skrzynka / lista do dostarczenia |
| G10 | XAU | niepotwierdzona | +0,105 | +0,098 | cała historia (2006–): istotna +; 3 lata: nieistotna → działała w całej historii, w ostatnich 3 latach przestała [p surowe < 0,05] |
| G11 | XAU | niepotwierdzona | -0,042 | +0,032 | cała historia (1971–): istotna +; 3 lata: nieistotna → działała w całej historii, w ostatnich 3 latach przestała [p surowe < 0,05] |
| G12 | XAU | nie do sprawdzenia | — | — | dane roczne albo ≤ 3 zdarzenia |
| S1 | XAG | potwierdzona · kandydat | +1,577 | +1,108 | cała historia (1970–): istotna +; 3 lata: istotna + → działa w obu okresach (beta 3 lata = 142% bety z całej historii) [p surowe < 0,05] |
| S2 | XAG | niepotwierdzona | +1,387 | +0,394 | cała historia (1980–): istotna +; 3 lata: istotna + → działa w obu okresach (beta 3 lata = 352% bety z całej historii) [p surowe < 0,05]; istotna, ale niestabilna (znak zgodny w 0% okien 52-tyg. z 3 lat); miesięczna, wartości wg daty obserwacji (makro z opóźnieniem publikacji) — jako cecha wymaga wersji PIT |
| S3 | XAG | niepotwierdzona | +0,030 | -0,064 | cała historia (2003–): istotna −; 3 lata: nieistotna → działała w całej historii, w ostatnich 3 latach przestała [p surowe < 0,05]; efekt nieistotny, ale przedział zbyt szeroki, by uznać go za mały |
| S4 | XAG | nie do sprawdzenia | — | — | dane roczne albo ≤ 3 zdarzenia |
| S5 | XAG | nie do sprawdzenia | — | — | dane roczne albo ≤ 3 zdarzenia |
| S6 | XAG | nie do sprawdzenia | — | — | dane roczne albo ≤ 3 zdarzenia |
| S7 | XAG | brak danych | — | — | tylko ręcznie: skrzynka / lista do dostarczenia |
| S8 | XAG | nie do sprawdzenia | — | — | dane roczne albo ≤ 3 zdarzenia |
| S9 | XAG | brak danych | — | — | tylko ręcznie: skrzynka / lista do dostarczenia |
| S10 | XAG | niepotwierdzona | +0,003 | -0,001 | cała historia (1964–): nieistotna; 3 lata: nieistotna → nieistotna w obu okresach [p surowe < 0,05] |
| S11 | XAG | brak danych | — | — | tylko ręcznie: skrzynka / lista do dostarczenia |
| S12 | XAG | niepotwierdzona | +0,016 | +0,012 | cała historia (1971–): nieistotna; 3 lata: nieistotna → nieistotna w obu okresach [p surowe < 0,05] |
| S13 | XAG | niepotwierdzona | +0,025 | +0,001 | cała historia (2007–): nieistotna; 3 lata: nieistotna → nieistotna w obu okresach [p surowe < 0,05] |
| O1 | BRENT | osłabła | -0,051 | -0,043 | cała historia (1987–): istotna −; 3 lata: istotna − → działa w obu okresach (beta 3 lata = 117% bety z całej historii) [p surowe < 0,05] (dane BH do 2023-04: „3 lata” = 2020-05…2023-04); miesięczna, wartości wg daty obserwacji (makro z opóźnieniem publikacji) — jako cecha wymaga wersji PIT |
| O1 | WTI | osłabła | -0,047 | -0,034 | cała historia (1986–): istotna −; 3 lata: istotna − → działa w obu okresach (beta 3 lata = 139% bety z całej historii) [p surowe < 0,05] (dane BH do 2023-04: „3 lata” = 2020-05…2023-04); miesięczna, wartości wg daty obserwacji (makro z opóźnieniem publikacji) — jako cecha wymaga wersji PIT |
| O2 | BRENT | niepotwierdzona | -0,001 | +0,000 | cała historia (1987–): nieistotna; 3 lata: nieistotna → nieistotna w obu okresach [p surowe < 0,05]; miesięczna, wartości wg daty obserwacji (makro z opóźnieniem publikacji) — jako cecha wymaga wersji PIT |
| O2 | WTI | niepotwierdzona | -0,000 | +0,000 | cała historia (1986–): nieistotna; 3 lata: nieistotna → nieistotna w obu okresach [p surowe < 0,05]; miesięczna, wartości wg daty obserwacji (makro z opóźnieniem publikacji) — jako cecha wymaga wersji PIT |
| O3 | BRENT | niepotwierdzona | +0,006 | -0,004 | 54 zdarzeń od 2015: średni CAR ponad losowe -0.0042 (p=0.407); ostatnie 3 lata: +0.0064 (19 zdarzeń) |
| O3 | WTI | niepotwierdzona | -0,003 | -0,007 | 54 zdarzeń od 2015: średni CAR ponad losowe -0.0067 (p=0.241); ostatnie 3 lata: -0.0028 (19 zdarzeń) |
| O4 (energetyczne) | BRENT | niepotwierdzona | +0,025 | -0,005 | 54 zdarzeń od 2015: średni CAR ponad losowe -0.0049 (p=0.796); ostatnie 3 lata: +0.0254 (19 zdarzeń) |
| O4 (pozostałe) | BRENT | niepotwierdzona | +0,008 | +0,003 | 45 zdarzeń od 2015: średni CAR ponad losowe +0.0030 (p=0.836); ostatnie 3 lata: +0.0075 (14 zdarzeń) |
| O4 (energetyczne) | WTI | niepotwierdzona | +0,020 | -0,005 | 54 zdarzeń od 2015: średni CAR ponad losowe -0.0047 (p=0.774); ostatnie 3 lata: +0.0199 (19 zdarzeń) |
| O4 (pozostałe) | WTI | niepotwierdzona | +0,005 | -0,015 | 45 zdarzeń od 2015: średni CAR ponad losowe -0.0150 (p=0.415); ostatnie 3 lata: +0.0052 (14 zdarzeń) |
| O5 | BRENT | potwierdzona | +0,009 | +0,012 | 169 zdarzeń od 1983: beta CAR na wielkości zdarzenia +0.0116 (p=0.0118); ostatnie 3 lata: +0.0090 (20 zdarzeń); test poza próbą: NIEZALICZONY — za mało zdarzeń w 2024–2026 do testu (17 < 20) — testu nie da się wykonać |
| O5 | WTI | potwierdzona | +0,007 | +0,011 | 169 zdarzeń od 1983: beta CAR na wielkości zdarzenia +0.0109 (p=0.00063); ostatnie 3 lata: +0.0075 (20 zdarzeń); test poza próbą: NIEZALICZONY — za mało zdarzeń w 2024–2026 do testu (17 < 20) — testu nie da się wykonać |
| O6 | WTI/BRENT | brak danych | — | — | konsensus płatny; badanie zdarzeń na proxy (zmiana − sezon) nie było w zakresie tej partii |
| O7 | BRENT | niepotwierdzona | -0,552 | -0,339 | cała historia (1987–): istotna −; 3 lata: nieistotna → działała w całej historii, w ostatnich 3 latach przestała [p surowe < 0,05] (futures EIA do 2024-04: „3 lata” = 2021-04…2024-04) |
| O7 | WTI | niepotwierdzona | -0,737 | -0,368 | cała historia (1986–): istotna −; 3 lata: nieistotna → działała w całej historii, w ostatnich 3 latach przestała [p surowe < 0,05] (futures EIA do 2024-04: „3 lata” = 2021-04…2024-04) |
| O8 | BRENT | niepotwierdzona | -0,000 | -0,001 | cała historia (2003–): nieistotna; 3 lata: nieistotna → nieistotna w obu okresach [p surowe < 0,05]; miesięczna, wartości wg daty obserwacji (makro z opóźnieniem publikacji) — jako cecha wymaga wersji PIT |
| O8 | WTI | niepotwierdzona | -0,000 | -0,001 | cała historia (2003–): nieistotna; 3 lata: nieistotna → nieistotna w obu okresach [p surowe < 0,05]; miesięczna, wartości wg daty obserwacji (makro z opóźnieniem publikacji) — jako cecha wymaga wersji PIT |
| O9 | BRENT | niepotwierdzona | +0,009 | -0,011 | cała historia (2013–): istotna −; 3 lata: nieistotna → działała w całej historii, w ostatnich 3 latach przestała [p surowe < 0,05] |
| O9 | WTI | potwierdzona | -0,017 | +0,004 | cała historia (2007–): nieistotna; 3 lata: istotna − → pojawiła się dopiero w ostatnich 3 latach [p surowe < 0,05]; test poza próbą: NIEZALICZONY — znak/istotność w 2024–2026 nie spełnia progu |
| O10 | BRENT | niepotwierdzona | +0,007 | +0,002 | cała historia (1988–): nieistotna; 3 lata: nieistotna → nieistotna w obu okresach [p surowe < 0,05] |
| O10 | WTI | niepotwierdzona | +0,004 | +0,003 | cała historia (1987–): nieistotna; 3 lata: nieistotna → nieistotna w obu okresach [p surowe < 0,05] |
| O11 | WTI/BRENT | nie do sprawdzenia | — | — | dane roczne albo ≤ 3 zdarzenia |
| O12 | BRENT | odwrócona | +1,778 | -1,025 | cała historia (1999–): istotna −; 3 lata: istotna + → znak się odwrócił [p surowe < 0,05] |
| O12 | WTI | odwrócona | +1,965 | -1,048 | cała historia (1999–): istotna −; 3 lata: istotna + → znak się odwrócił [p surowe < 0,05] |
| O13 | BRENT | niepotwierdzona | +0,015 | -0,003 | 84 zdarzeń od 1987: średni CAR ponad losowe -0.0035 (p=0.605); ostatnie 3 lata: +0.0150 (9 zdarzeń) |
| O13 | WTI | niepotwierdzona | +0,019 | -0,002 | 85 zdarzeń od 1986: średni CAR ponad losowe -0.0025 (p=0.712); ostatnie 3 lata: +0.0194 (9 zdarzeń) |
| O14 | BRENT | niepotwierdzona | +0,038 | +0,013 | 62 zdarzeń od 2015: średni CAR ponad losowe +0.0133 (p=0.171); ostatnie 3 lata: +0.0379 (20 zdarzeń) |
| O14 | WTI | niepotwierdzona | +0,054 | +0,018 | 62 zdarzeń od 2015: średni CAR ponad losowe +0.0184 (p=0.085); ostatnie 3 lata: +0.0544 (20 zdarzeń) |
| O15 | WTI/BRENT | brak danych | — | — | sankcje: jak G8; dyskonto Urals płatne |
| O16 | BRENT | niepotwierdzona | +0,000 | +0,000 | cała historia (1987–): istotna +; 3 lata: nieistotna → działała w całej historii, w ostatnich 3 latach przestała [p surowe < 0,05] |
| O16 | WTI | niepotwierdzona | +0,000 | +0,000 | cała historia (1986–): istotna +; 3 lata: nieistotna → działała w całej historii, w ostatnich 3 latach przestała [p surowe < 0,05] |
| O17 | WTI/BRENT | brak danych | — | — | tylko ręcznie: skrzynka / lista do dostarczenia |
| O18 | BRENT | potwierdzona | — | — | ; z 3A: najlepszy model implied vol BSS +0,047 [+0,011; +0,078] (wybór na okresie testowym) |
| O18 | WTI | potwierdzona | — | — | ; z 3A: najlepszy model implied vol BSS +0,048 [+0,016; +0,080] (wybór na okresie testowym) |
| C1 | BTC | niepotwierdzona | +0,086 | +0,073 | cała historia (2017–): nieistotna; 3 lata: nieistotna → nieistotna w obu okresach [p surowe < 0,05] |
| C1 | ETH | niepotwierdzona | +0,120 | +0,079 | cała historia (2017–): nieistotna; 3 lata: nieistotna → nieistotna w obu okresach [p surowe < 0,05] |
| C2 | BTC/ETH | brak danych | — | — | tylko ręcznie: skrzynka / lista do dostarczenia |
| C3 | BTC/ETH | brak danych | — | — | tylko ręcznie: skrzynka / lista do dostarczenia |
| C4 | BTC | potwierdzona · kandydat | +0,629 | +0,804 | cała historia (2017–): istotna +; 3 lata: istotna + → działa w obu okresach (beta 3 lata = 78% bety z całej historii) [p surowe < 0,05] |
| C4 | ETH | potwierdzona · kandydat | +1,152 | +1,282 | cała historia (2017–): istotna +; 3 lata: istotna + → działa w obu okresach (beta 3 lata = 90% bety z całej historii) [p surowe < 0,05] |
| C5 | BTC | niepotwierdzona | -0,208 | -0,071 | 78 zdarzeń od 2017: beta CAR na wielkości zdarzenia -0.0709 (p=0.36); ostatnie 3 lata: -0.2076 (26 zdarzeń) |
| C5 | ETH | niepotwierdzona | -0,321 | -0,132 | 78 zdarzeń od 2017: beta CAR na wielkości zdarzenia -0.1319 (p=0.242); ostatnie 3 lata: -0.3207 (26 zdarzeń) |
| C6 | BTC/ETH | brak danych | — | — | nie zaplanowano |
| C7 | BTC | niepotwierdzona | -0,290 | -1,362 | cała historia (2017–): nieistotna; 3 lata: nieistotna → nieistotna w obu okresach [p surowe < 0,05] |
| C7 | ETH | niepotwierdzona | -0,577 | -2,492 | cała historia (2017–): istotna −; 3 lata: nieistotna → działała w całej historii, w ostatnich 3 latach przestała [p surowe < 0,05] |
| C8 | BTC/ETH | brak danych | — | — | tylko ręcznie: skrzynka / lista do dostarczenia |
| C9 | BTC | niepotwierdzona | +0,885 | +0,027 | cała historia (2017–): nieistotna; 3 lata: nieistotna → nieistotna w obu okresach [p surowe < 0,05] |
| C9 | ETH | niepotwierdzona | +1,069 | +0,158 | cała historia (2017–): nieistotna; 3 lata: nieistotna → nieistotna w obu okresach [p surowe < 0,05] |
| C10 | BTC/ETH | brak danych | — | — | tylko ręcznie: skrzynka / lista do dostarczenia |
| C11 | BTC | niepotwierdzona | +0,002 | +0,001 | cała historia (2020–): nieistotna; 3 lata: nieistotna → nieistotna w obu okresach [p surowe < 0,05] |
| C11 | ETH | niepotwierdzona | +0,003 | +0,004 | cała historia (2020–): nieistotna; 3 lata: nieistotna → nieistotna w obu okresach [p surowe < 0,05] |
| C12 | BTC | potwierdzona · kandydat | +0,135 | +0,039 | cała historia (2020–): nieistotna; 3 lata: istotna + → pojawiła się dopiero w ostatnich 3 latach [p surowe < 0,05]; test poza próbą: zaliczony |
| C12 | ETH | niepotwierdzona | +0,043 | +0,059 | cała historia (2021–): nieistotna; 3 lata: nieistotna → nieistotna w obu okresach [p surowe < 0,05] |
| C13 | BTC | konstrukcyjna | +0,004 | +0,005 | cała historia (2018–): istotna +; 3 lata: istotna + → działa w obu okresach (beta 3 lata = 90% bety z całej historii) [p surowe < 0,05]; F&G liczony m.in. z ceny i zmienności BTC — zależność konstrukcyjna |
| C13 | ETH | konstrukcyjna | +0,005 | +0,005 | cała historia (2018–): istotna +; 3 lata: istotna + → działa w obu okresach (beta 3 lata = 93% bety z całej historii) [p surowe < 0,05]; F&G liczony m.in. z ceny i zmienności BTC — zależność konstrukcyjna |
| C14 | BTC | niepotwierdzona | +0,000 | +0,000 | cała historia (2017–): nieistotna; 3 lata: nieistotna → nieistotna w obu okresach [p surowe < 0,05]; efekt nieistotny, ale przedział zbyt szeroki, by uznać go za mały |
| C14 (zdarzenia) | BTC | niepotwierdzona | -0,006 | +0,017 | 39 zdarzeń od 2017: średni CAR ponad losowe +0.0173 (p=0.213); ostatnie 3 lata: -0.0057 (13 zdarzeń) |
| C14 | ETH | niepotwierdzona | -0,000 | -0,000 | cała historia (2017–): nieistotna; 3 lata: nieistotna → nieistotna w obu okresach [p surowe < 0,05]; efekt nieistotny, ale przedział zbyt szeroki, by uznać go za mały |
| C14 (zdarzenia) | ETH | niepotwierdzona | -0,017 | +0,033 | 39 zdarzeń od 2017: średni CAR ponad losowe +0.0330 (p=0.08); ostatnie 3 lata: -0.0174 (13 zdarzeń) |
| C15 | BTC/ETH | nie do sprawdzenia | — | — | dane roczne albo ≤ 3 zdarzenia |
| C16 | BTC/ETH | brak danych | — | — | tylko ręcznie: skrzynka / lista do dostarczenia |
<!-- STATUS:END -->
