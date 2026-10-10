# Zasady inwestowania — co ma dowody, a co nie

Stan: 2026-10-06. Źródła: prace naukowe, banki centralne, regulatorzy, research branżowy (AQR, Man, Vanguard, Morningstar). Pełne listy linków na końcu. Każda zasada kończy się regułą dla market-signals.

`[n]` = liczba z omówienia albo nie do końca sprawdzona w oryginale.

---

## Część 1. Punkt wyjścia: większość traci

| Fakt | Liczby | Źródło |
|---|---|---|
| Day traderzy w Brazylii (futures na indeks) | z tych, którzy wytrwali > 300 dni: **97% straciło**, 0,4% zarobiło więcej niż płaca minimalna | Chague i in. |
| Day traderzy na Tajwanie | ~1% zarabia w sposób powtarzalny; w danym roku ~20% na plusie, głównie przez szczęście | Barber, Lee, Liu, Odean |
| CFD w UE | **74–89% rachunków traci** | ESMA 2018 |
| Inwestorzy krypto (95 krajów) | ponad 4/5 straciłoby przy zakupach po 100 USD/mies.; kupują na hossie | BIS Bulletin 69 |
| Najaktywniej handlujący | 11,4% rocznie vs rynek 17,9% (różnica = koszty i nadmierny obrót) | Barber & Odean 2000 |
| Luka „fundusz vs inwestor” | 1,2 pp rocznie; w ETF krypto **14 pp** (złe wejścia i wyjścia) | Morningstar „Mind the Gap” 2026 |

**Reguła:** zakładam brak przewagi, dopóki dane nie pokażą inaczej. To system musi udowodnić przewagę, nie rynek jej brak.

---

## Część 2. Strategie: co działa na naszych aktywach

| Strategia | Dowody | Dla nas (ETF/ETC, mały rachunek detaliczny) |
|---|---|---|
| **Trend / time-series momentum** | Jedyna z ponad 100 lat dowodów: Sharpe ~0,77 netto, max DD −26% (1880–2013, portfel ~60 rynków). Zarabia w kryzysach (2008 +21%, 2022 +27%), ale potrafi tracić rok (2024–25 −20%). | Dowody dotyczą szerokiego portfela. Na 4 aktywach to słabsza, niezbadana wersja. Sens ma **wolny filtr** (sygnał 6–12 mies., zmiana raz w miesiącu), nie częsty trading. |
| **Trend na BTC** | Najlepiej udokumentowana reguła w krypto; realnie Sharpe ~1, nie 2+. Główna korzyść: **ucina obsunięcia**, nie podnosi zwrotu. | Tak, prosta wersja (np. cena vs średnia N dni, kilka okien naraz). |
| **Mała stała pozycja krypto + rebalans** | 1–5% BTC w portfelu poprawiało wynik (badania głównie sprzedawców ETP, na danych z hossy). | Tak, najprostsza. Planować **−80% jako scenariusz bazowy**. |
| **Rebalans koszyka surowców** | Premia ~2,7% rocznie (12 surowców, 1982–2004) przy niskich korelacjach; częstotliwość prawie bez znaczenia. | Tak: kwartalnie albo przy odchyleniu wagi o > 20–25%. U nas równy podział z rebalansem już pobił momentum (backtest 4P). |
| Carry, basis-momentum, momentum przekrojowe | Działają tylko jako long-short na wielu futures; max DD −78/−80%; premie zjada tłok. | **Nie** do zrobienia ETF-ami. |
| Sezonowość | Brak wyniku po korekcie na wielokrotne testy (2016–2024). | **Nie.** |
| Wartość / „złoto jest drogie” | Wysoka realna cena złota → słabe 10 lat (Erb & Harvey), ale sygnał bolał w 2025–26. | Nie na pojedynczym aktywie. |
| On-chain (MVRV itd.) | Statystycznie coś jest, ekonomicznie ~0,3% rocznie; „3 cykle” to N=3. | Najwyżej pomocniczo. |
| Funding/basis carry w krypto | Był realny (Sharpe ~1,8), **zanika**, ujemny w 2025; ryzyko giełdy (FTX). | Nie. |
| DCA vs jednorazowo | Jednorazowo wygrywa w ~2/3 przypadków; DCA tylko zmniejsza żal i obsunięcie. | DCA wolno, ale nie dla zysku. |
| Dyskrecjonalne decyzje człowieka | Systematyczne fundusze macro: alfa 4,85% vs dyskrecjonalne 1,57% (1996–2014). | Dowody przeciw. |

**Instrumenty:** złoto i srebro tylko przez **fizyczne ETC** (bez kosztu rolowania; TER 0,12–0,20%). Ropa: koszt rolowania to główny wróg (USO przez 10 lat +55% vs BNO/Brent +281%) — wybierać Brent i sprawdzać sposób rolowania.

**Koszty w PL:** XTB 0% prowizji, ale **0,5% za przewalutowanie** w każdą stronę → ~1% za pełny cykl + spread. Przy 4–6 zmianach rocznie to 4–6% kosztu. Do tego 19% od każdego zrealizowanego zysku (krypto osobny koszyk). Częsty obrót karze podwójnie.

---

## Część 3. Ryzyko i wielkość pozycji — tu jest główna praca

1. **Kontrola ryzyka ważniejsza niż przewidywanie.** Błąd w szacunku średniego zwrotu waży ok. 20× więcej niż błąd w zmienności (MacLean–Thorp–Ziemba). Optymalizacja wag przegrywa z równym podziałem (DeMiguel i in. 2009). → **Nie liczę wag z prognoz zwrotu.**
2. **Wagi odwrotnie do zmienności (inverse-vol) z sufitem.** Zmienności naszych aktywów różnią się kilkukrotnie; równy podział w złotówkach oddaje większość ryzyka krypto (u nas BTC = 46% wartości, 61% ryzyka). → w_i ∝ 1/σ_i, σ z 60–250 dni; **sufit: krypto ≤ 25% kapitału**.
3. **Volatility targeting** na surowcach prawie nie podnosi Sharpe, ale **tnie skrajne straty i obsunięcia** (Man/Harvey i in. 2018; krytyka Cederburga: „alfa” znika poza próbą). → używam do kontroli ryzyka, nie do zysku. Tu przydaje się nasza jedyna zmierzona przewaga: **prognoza zmienności ropy (OVX)**.
4. **Kelly tylko jako sufit.** Pełny Kelly przy przeszacowanej przewadze prowadzi do ruiny, 2× Kelly daje zerowy wzrost; ½ Kelly daje ~75% wzrostu przy dużo mniejszym ryzyku. → realnie **≤ ¼–½ Kelly**, a przy braku udowodnionej przewagi Kelly = 0.
5. **Ciasne stop-lossy szkodzą**; pomagają tylko wolne reguły przy trendzie (Kaminski & Lo). → zamiast stopu dziennego wolny filtr trendu (miesięczny), wyjście do gotówki.
6. **Kontrola obsunięcia** (Grossman–Zhou): ekspozycja proporcjonalna do „poduszki” nad progiem, np. 80% szczytu.
7. **Korelacje w kryzysie rosną** (BTC–akcje z 0,01 do 0,36; złoto chroni ~15 dni). → stress test przy korelacji 0,8–1,0.
8. **Matematyka strat:** −50% wymaga +100%, −80% wymaga +400%. Przy zmienności 70–80% „opór zmienności” (σ²/2) zjada ~25–30 pp rocznie `[n]`. → najmocniejszy argument za małą wagą krypto.

---

## Część 4. Jak nie oszukać samego siebie (backtest i ocena)

| Zjawisko | Liczby | Reguła |
|---|---|---|
| Sharpe na żywo vs backtest | mediana **−73%**; tylko 8,4% strategii dorównało backtestowi; złożone tracą więcej (215 strategii z 17 banków) | Sharpe z backtestu **dzielę przez 3–4**; prostsze wygrywa |
| Anomalie po publikacji | −26% poza próbą, −58% po publikacji | spodziewam się połowy wyniku z literatury |
| Replikacja | 65–82% z 452 anomalii nie przechodzi | testuję z realnymi kosztami, na płynnych instrumentach |
| Wielokrotne testy | 10 prób bez przewagi → najlepszy Sharpe ~1,57 w backteście; 5 lat danych → max ~45 niezależnych konfiguracji | liczba prób w `runs` (już mamy), **Deflated Sharpe**, **PBO < 0,5**, próg **t > 3** |
| Dane odłożone | — | otwieram raz; zmiana po zobaczeniu = koniec testu poza próbą |
| Ile trzeba danych, żeby odróżnić umiejętność od szczęścia (95%) | Sharpe 2 → ~8 mies.; **Sharpe 1 → ~2,7 roku**; Sharpe 0,5 → ~11 lat; ×2–3 przy grubych ogonach | **3–6 miesięcy gry na sucho nie udowodni przewagi.** Udowodni proces i dyscyplinę |

---

## Część 5. Zachowanie — reguły dla mnie

1. **Wejście tylko z sygnału systemu.** Nic nie kupuję, bo jest o tym głośno (Barber & Odean: inwestorzy kupują to, co w newsach).
2. **Wyjścia ustalone przed wejściem i wykonywane automatycznie.** Samo „przypominanie sobie” nie działa; automat zwiększył realizację strat z 5,9% do 25,2% (Fischbacher i in.).
3. **Po stracie nie zwiększam pozycji i nie uśredniam w dół** (teoria perspektywy: po stratach ludzie ryzykują więcej).
4. **Limit transakcji** na tydzień/miesiąc. Nadmierny obrót = główne źródło strat.
5. **Dziennik prowadzi maszyna**, oceniam się tylko z niego. Ludzie pamiętają swoje wyniki lepszymi, niż były (Walters & Fernbach, PNAS 2021).
6. **Nie wyłączam systemu w obsunięciu z emocji.** Warunek wyłączenia ustalony z góry: np. obsunięcie > 1,5× najgorsze z backtestu.
7. **Przejście na prawdziwe pieniądze stopniowo:** 5–10% docelowej kwoty, bez dźwigni.

---

## Co z tego wynika dla market-signals (do etapu 5)

1. **Etap 5 = portfel regułowy, nie wybieranie zwycięzców:**
   - wagi inverse-vol z sufitem krypto ≤ 25%;
   - wolny filtr trendu na każdym aktywie (kilka okien 3–12 mies., zmiana raz w miesiącu, poza trendem → gotówka/lokata);
   - rebalans kwartalny albo progowy (±25%);
   - opcjonalnie: skalowanie ekspozycji ropy prognozą zmienności z OVX (nasza jedyna zmierzona przewaga);
   - koszty 1% za pełny cykl + podatek, jak w 4P.
2. **Porównania:** równy podział z rebalansem (już mamy), lokata, złoto, `momentum_1m`, plus nowe: inverse-vol bez filtra, inverse-vol z filtrem.
3. **Ocena:** Deflated Sharpe, PBO, cięcie wyniku backtestu 2–4×, maks. obsunięcie, liczba prób w `runs`.
4. **Gra na sucho:** obok konta „gra 1” (moje decyzje) uruchomić konto **„system”**, które samo wykonuje reguły z etapu 5. Za kilka miesięcy porównanie pokaże, czy moje decyzje dodają coś do reguł.
5. **Uczciwy horyzont:** przy Sharpe ~1 umiejętność od szczęścia odróżni dopiero ~2–3 lata. Wcześniej oceniam proces, nie wynik.

---

## Idee z kluczowych książek (tylko główne myśli, własnymi słowami)

- **Antti Ilmanen, „Expected Returns”** — zwroty z rynku pochodzą z kilku trwałych premii (akcje, trend, carry, wartość); każda ma długie okresy bólu, a dywersyfikacja premii jest jedynym „darmowym obiadem”.
- **Robert Carver, „Systematic Trading”** — prostota, wielkość pozycji według zmienności, kilka okien trendu naraz, ostrożne prognozowanie; najwięcej szkody robi przeoptymalizowanie i zbyt częsty handel.
- **Marcos López de Prado, „Advances in Financial Machine Learning”** — backtest nie jest narzędziem badawczym; liczyć próby, walidacja z purge i embargo (już mamy), Deflated Sharpe.
- **Daniel Kahneman, „Pułapki myślenia”** — nadmierna pewność siebie, awersja do strat, złudzenie kontroli; checklisty i reguły z góry chronią przed własnym mózgiem.
- **Nassim Taleb, „Zwiedzeni przez losowość”** — dobre wyniki krótkoterminowe częściej są szczęściem niż umiejętnością; liczy się przetrwanie złych scenariuszy.

---

## Źródła (otwierane przez research)

**Strategie surowcowe:** [AQR Century of Trend](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing) · [MOP TSMOM](https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf) · [Cambridge Associates o trendzie 2024–25](https://www.cambridgeassociates.com/insight/does-trend-followings-recent-struggle-signal-that-the-strategy-is-structurally-broken/) · [Koijen i in. Carry](https://research-api.cbs.dk/ws/files/57294842/lasse_heje_pedersen_et_al_carry_acceptedmanuscript.pdf) · [Boons & Prado basis-momentum](https://4nations.albertjmenkveld.com/papers/boonsprado17.pdf) · [Erb & Harvey commodity futures](https://www.nber.org/papers/w11222) · [Erb & Harvey Golden Dilemma](https://www.nber.org/papers/w18706) · [Quantpedia crowding](https://quantpedia.com/crowding-in-commodity-factor-strategies/) · [Sezonowość arXiv](https://arxiv.org/abs/2609.12227) · [Man vs machine (Harvey i in.)](https://people.duke.edu/~charvey/Research/Published_Papers/P130_Man_vs_machine.pdf) · [USO vs BNO](https://finance.yahoo.com/markets/commodities/articles/uso-front-month-oil-strategy-173327031.html) · [XTB opłaty](https://www.xtb.com/pl/konto-i-oplaty)

**Krypto:** [Liu & Tsyvinski](https://www.nber.org/system/files/working_papers/w24877/w24877.pdf) · [Trend w krypto (CXO/Zarattini)](https://www.cxoadvisory.com/technical-trading/crypto-asset-trend-following-strategies/) · [Monash trend](https://www.monash.edu/business/mcfs/our-research/all-projects/investment-strategy/trend-following-strategies-for-crypto-investors) · [Survivorship w krypto (Ammann i in.)](https://alexandria.unisg.ch/handle/20.500.14171/108037) · [CoinShares alokacja](https://coinshares.com/insights/research-data/just-the-right-amount-of-bitcoin/) · [Vanguard DCA](https://www.nl.vanguard/professional/vanguard-365/cost-averaging) · [On-chain Guidolin & Ionta](https://iris.unibocconi.it/retrieve/ca0d5636-301d-4177-b28c-1e88a6b6cdb1/Guidolin%20and%20Ionta%20JIFMIM%202026.pdf) · [BIS carry WP1087](https://bis.org/publ/work1087.htm) · [BIS Bulletin 69 retail](https://www.bis.org/publ/bisbull69.htm) · [Przegląd 2014–2025 arXiv](https://arxiv.org/pdf/2510.14435)

**Ryzyko i wielkość pozycji:** [Moreira & Muir](https://www.nber.org/papers/22208) · [Cederburg i in.](https://www.lehigh.edu/~xuy219/research/COWY.pdf) · [Harvey i in. (Man) vol targeting](https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf) · [AQR risk parity](https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/Leverage-Aversion-and-Risk-Parity.pdf) · [DeMiguel 1/N](https://ideas.repec.org/a/oup/rfinst/v22y2009i5p1915-1953.html) · [Thorp Kelly](https://www.gwern.net/doc/statistics/decision/2006-thorp.pdf) · [MacLean–Thorp–Ziemba](https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf) · [Bernstein rebalans](https://www.efficientfrontier.com/ef/100/rebal100.htm) · [Kaminski & Lo stop-loss](https://dspace.mit.edu/bitstream/handle/1721.1/114876/Lo_When%20Do%20Stop-Loss.pdf) · [Longin & Solnik](https://repec.cepr.org/repec/cpr/ceprdp/Dp2538.pdf) · [Kitces volatility drag](https://www.kitces.com/blog/volatility-drag-variance-drain-mean-arithmetic-vs-geometric-average-investment-returns/)

**Zachowanie i backtesty:** [Barber & Odean 2000](https://ideas.repec.org/a/bla/jfinan/v55y2000i2p773-806.html) · [Boys will be boys](https://faculty.haas.berkeley.edu/odean/papers/gender/gender.html) · [Tajwan day traders](https://www.escholarship.org/content/qt7k75v0qx/qt7k75v0qx.pdf) · [Brazylia day traders](https://ideas.repec.org/p/fgv/eesptd/525.html) · [Odean dyspozycja](https://faculty.haas.berkeley.edu/odean/papers%20current%20versions/areinvestorsreluctant.pdf) · [Fischbacher i in. automatyczne wyjścia](https://www.twi-kreuzlingen.ch/wp-content/uploads/2017/12/twi-rps-089-fischbacher-hoffmann-schudy.pdf) · [Walters & Fernbach pamięć](https://www.colorado.edu/business/faculty-research/2025/07/03/investor-memory-past-performance-positively-biased-and-predicts-overconfidence) · [Morningstar Mind the Gap](https://www.morningstar.com/en-us/business/insights/research/mind-the-gap) · [ESMA CFD](https://www.esma.europa.eu/node/84933) · [Pseudo-mathematics (Bailey i in.)](https://carmamaths.org/jon/backtest.pdf) · [PBO](https://papers.ssrn.com/abstract=2326253) · [Deflated Sharpe](https://papers.ssrn.com/abstract=2460551) · [Harvey–Liu–Zhu t>3](https://www.nber.org/papers/w20592) · [Hou–Xue–Zhang](https://ideas.repec.org/a/oup/rfinst/v33y2020i5p2019-2133..html) · [Suhonen i in. (omówienie)](https://alphaarchitect.com/looking-at-alternatives-avoid-complexity-and-magical-backtests/) · [SLCG minimalna historia](https://www.slcg.com/files/practice-notes/sharpe-ratio.pdf)
