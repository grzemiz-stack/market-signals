# Rejestr modeli — 2026-09

Miesiąc oceny: 2026-09 (dni, których etykieta rozstrzyga się w tym miesiącu). **Miesiąc należy do okresu selekcji 3A — wynik informacyjny, reguły go nie liczą.**
Miesiące liczone przez reguły (po 2026-10-06): 0/6 — za mało, reguły awansu/degradacji jeszcze nie działają.
Próby w model_trials: 10 (nowe w tym uruchomieniu: brak).

Uwaga: wynik jednego miesiąca (~20 dni, często 0–2 zdarzenia) jest bardzo zaszumiony — BSS potrafi wynosić +0,8 albo −5. Reguły decydują wyłącznie na 6 połączonych miesiącach (bootstrap blokowy, n >= 100 dni).

## Aktywo × pytanie

| aktywo | pytanie | mistrz (wizytówka) | wynik mistrza w miesiącu | pretendenci: wynik w miesiącu |
|---|---|---|---|---|
| XAU | prob_up_5d | Odpowiada: GVZ skalibrowany. Przewaga nad częstością bazową: BSS +0,014 [-0,000; +0,029] (3A, okres selekcji (zawyżony przez selekcję)). Mistrz od: 2026-10-06. | +0,807 [+0,766; +0,865], n=21 | GARCH(1,1)-t +0,502; analogie (k=20) -0,011; stosunek zmienności 20d/5d do rocznej +0,066; HAR-RV +0,817; LightGBM -0,172; GVZ surowy +0,444 |
| XAU | prob_down_5d | Odpowiada: GVZ skalibrowany. Przewaga nad częstością bazową: BSS +0,014 [-0,000; +0,029] (3A, okres selekcji (zawyżony przez selekcję)). Mistrz od: 2026-10-06. | +0,008 [-0,030; +0,840], n=21 | GARCH(1,1)-t +0,013; HAR-RV +0,019; LightGBM -0,004; analogie (k=20) +0,170; stosunek zmienności 20d/5d do rocznej -0,004; GVZ surowy +0,029 |
| XAU | decomp_weekly | Odpowiada: dekompozycja GRAM (okno 260 tyg.). R² poza próbą: — [—; —] (brak miesięcy poza próbą). Mistrz od: 2026-10-06. | -2,411 [—; —], n=4 |  |
| XAG | prob_up_5d | Odpowiada: stosunek zmienności 20d/5d do rocznej. Przewaga nad częstością bazową: BSS +0,011 [-0,000; +0,023] (3A, okres selekcji (zawyżony przez selekcję)). Mistrz od: 2026-10-06. | +0,657 [+0,612; +0,697], n=21 | HAR-RV +0,982; LightGBM +0,000; analogie (k=20) -0,626; GARCH(1,1)-t +0,976 |
| XAG | prob_down_5d | Odpowiada: stosunek zmienności 20d/5d do rocznej. Przewaga nad częstością bazową: BSS +0,011 [-0,000; +0,023] (3A, okres selekcji (zawyżony przez selekcję)). Mistrz od: 2026-10-06. | +0,530 [+0,490; +0,564], n=21 | analogie (k=20) +0,693; HAR-RV +0,977; LightGBM -0,064; GARCH(1,1)-t +0,968 |
| XAG | decomp_weekly | Odpowiada: dekompozycja GRAM (okno 260 tyg.). R² poza próbą: — [—; —] (brak miesięcy poza próbą). Mistrz od: 2026-10-06. | -1,587 [—; —], n=4 |  |
| WTI | prob_up_5d | Odpowiada: OVX skalibrowany. Przewaga nad częstością bazową: BSS +0,048 [+0,016; +0,080] (3A, okres selekcji (zawyżony przez selekcję)). Mistrz od: 2026-10-06. | -0,049 [-0,062; +0,797], n=21 | HAR-RV -0,046; LightGBM -0,006; stosunek zmienności 20d/5d do rocznej -0,041; GARCH(1,1)-t -0,040; OVX surowy -0,018; analogie (k=20) +0,002 |
| WTI | prob_down_5d | Odpowiada: OVX skalibrowany. Przewaga nad częstością bazową: BSS +0,048 [+0,016; +0,080] (3A, okres selekcji (zawyżony przez selekcję)). Mistrz od: 2026-10-06. | -0,007 [-0,047; +0,711], n=21 | analogie (k=20) -0,152; LightGBM -0,011; OVX surowy -0,007; GARCH(1,1)-t -0,000; HAR-RV -0,008; stosunek zmienności 20d/5d do rocznej +0,022 |
| WTI | decomp_weekly | Odpowiada: dekompozycja GRAM (okno 260 tyg.). R² poza próbą: — [—; —] (brak miesięcy poza próbą). Mistrz od: 2026-10-06. | -0,056 [—; —], n=4 |  |
| BRENT | prob_up_5d | Odpowiada: OVX surowy. Przewaga nad częstością bazową: BSS +0,047 [+0,011; +0,078] (3A, okres selekcji (zawyżony przez selekcję)). Mistrz od: 2026-10-06. | -0,065 [-0,070; -0,025], n=21 | stosunek zmienności 20d/5d do rocznej -0,031; HAR-RV -0,077; LightGBM -0,026; OVX skalibrowany -0,092; GARCH(1,1)-t -0,023; analogie (k=20) +0,051 |
| BRENT | prob_down_5d | Odpowiada: OVX surowy. Przewaga nad częstością bazową: BSS +0,047 [+0,011; +0,078] (3A, okres selekcji (zawyżony przez selekcję)). Mistrz od: 2026-10-06. | +0,078 [+0,009; +0,836], n=21 | OVX skalibrowany +0,071; stosunek zmienności 20d/5d do rocznej +0,023; HAR-RV +0,043; analogie (k=20) +0,102; GARCH(1,1)-t +0,057; LightGBM +0,020 |
| BRENT | decomp_weekly | Odpowiada: dekompozycja GRAM (okno 260 tyg.). R² poza próbą: — [—; —] (brak miesięcy poza próbą). Mistrz od: 2026-10-06. | -0,246 [—; —], n=4 |  |
| BTC | prob_up_5d | Odpowiada: GARCH(1,1)-t. Przewaga nad częstością bazową: BSS +0,004 [-0,017; +0,024] (3A, okres selekcji (zawyżony przez selekcję)). Mistrz od: 2026-10-06. | -0,029 [-0,732; -0,007], n=30 | LightGBM -0,006; stosunek zmienności 20d/5d do rocznej -0,015; DVOL skalibrowany +0,000; DVOL surowy -0,020; HAR-RV -0,030; analogie (k=20) -0,049 |
| BTC | prob_down_5d | Odpowiada: GARCH(1,1)-t. Przewaga nad częstością bazową: BSS +0,004 [-0,017; +0,024] (3A, okres selekcji (zawyżony przez selekcję)). Mistrz od: 2026-10-06. | -0,279 [-0,583; +0,023], n=30 | stosunek zmienności 20d/5d do rocznej -0,002; DVOL skalibrowany +0,490; analogie (k=20) -5,369; LightGBM +0,191; DVOL surowy +0,590; HAR-RV -2,220 |
| BTC | decomp_weekly | Odpowiada: dekompozycja GRAM (okno 260 tyg.). R² poza próbą: — [—; —] (brak miesięcy poza próbą). Mistrz od: 2026-10-06. | -0,386 [—; —], n=4 |  |
| ETH | prob_up_5d | Odpowiada: stosunek zmienności 20d/5d do rocznej. Przewaga nad częstością bazową: BSS -0,004 [-0,008; -0,001] (3A, okres selekcji (zawyżony przez selekcję)). Mistrz od: 2026-10-06. | +0,010 [-0,076; +0,026], n=30 | DVOL surowy -0,004; LightGBM +0,004; DVOL skalibrowany -0,006; HAR-RV -0,015; GARCH(1,1)-t -0,029; analogie (k=20) +0,006 |
| ETH | prob_down_5d | Odpowiada: stosunek zmienności 20d/5d do rocznej. Przewaga nad częstością bazową: BSS -0,004 [-0,008; -0,001] (3A, okres selekcji (zawyżony przez selekcję)). Mistrz od: 2026-10-06. | -0,051 [-0,089; -0,010], n=30 | DVOL skalibrowany +0,267; HAR-RV -1,358; analogie (k=20) -3,267; GARCH(1,1)-t -0,358; DVOL surowy +0,623; LightGBM -0,198 |
| ETH | decomp_weekly | Odpowiada: dekompozycja GRAM (okno 260 tyg.). R² poza próbą: — [—; —] (brak miesięcy poza próbą). Mistrz od: 2026-10-06. | -0,150 [—; —], n=4 |  |

## Zmiany ról

Brak zmian.

## Event_response

Zarezerwowane na etap zdarzeń (GDELT) — brak modeli.

