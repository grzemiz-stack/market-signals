# E2 (wzorzec z komentarzy WGC) — zasady mapowania, zapisane 2026-10-07 PRZED lekturą komentarzy

Źródło: World Gold Council, Gold Market Commentary (miesięczne), gold.org/goldhub/research/gold-market-commentary-*.
Warunki gold.org: „You are permitted to save, display or print out information contained on this Website only for your
personal, non-commercial use.” — strony zapisane jednorazowo (10 s odstępu) do data/raw/wgc_gmc/ (poza gitem); w repo
(prywatnym) tylko jedno zdanie na miesiąc + link.

Dla każdego komentarza (miesiąca):
1. **Cytat**: jedno zdanie, dosłownie (bez zmian, bez skrótów), w którym WGC podaje przyczynę ruchu ceny złota w tym
   miesiącu. Pierwszeństwo: zdanie z sekcji podsumowania/„highlights”, które łączy ruch ceny z czynnikiem
   („gold rose …, driven by …”). Gdy zdanie wymienia kilka czynników — kod pierwszego wymienionego jako główny.
2. **Kod** z ref/taxonomy.csv (bez zmian taksonomii) według tabeli:

| czynnik w zdaniu WGC | kod |
|---|---|
| stopy procentowe, rentowności, oczekiwania co do Fed/banków centralnych, polityka pieniężna | monetary |
| zakupy złota przez banki centralne | monetary (BBDS: „monetary policy and central banking”) |
| dolar (słabszy/mocniejszy), kursy walut | fx_capital (najbliższy kod; brak osobnego „dolar”) |
| ryzyko geopolityczne, wojna, konflikt zbrojny | sovmil |
| inflacja, wzrost, recesja, dane makro, perspektywy gospodarki | macro |
| cła, wojna handlowa | trade_policy |
| deficyt, dług, wydatki rządowe, podatki | fiscal |
| wybory, zmiany władzy | elections |
| wyprzedaż/wzrosty na rynkach akcji, wyniki spółek | corporate_foreign |
| fizyczny niedobór metalu, premie, zapasy | metal_shortage |
| regulacje (poza monetarnymi) | regulation |

3. **Wyłączenie** (bez kodu, w pliku z powodem): zdanie podaje jako przyczynę wyłącznie przepływy inwestycyjne / ETF /
   pozycjonowanie / „momentum”, których taksonomia nie ma, albo komentarz nie podaje przyczyny ruchu. Nie zgaduję kodu.
4. Mapowanie robi człowiek-redaktor (asystent), nie Qwen. Plik `ref/e2_wgc_gold.csv` w commicie PRZED przebiegiem Qwena (w kopii publicznej: `ref/e2_wgc_index.csv` bez cytatów; cytaty odtwarzane lokalnie przez `src/e2_wgc_restore.py`).
5. Kontrola: 20 losowych wierszy (seed 20261007) w `ref/e2_wgc_check20.csv`: cytat | kod | TAK/NIE — użytkownik
   ocenia, czy cytat mówi to, co kod.

Wejście Qwena w E2: ten sam cytat (wariant zwykły) i wariant zamaskowany (kraje/organizacje → znaczniki, bez lat i
miesięcy). Progi bez zmian: dokładność ≥ 0,75 i κ ≥ 0,60, wariant zamaskowany też musi przejść.
