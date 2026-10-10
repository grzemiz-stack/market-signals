# Data sources and licenses

**No data is included in this repository.** Everything under `data/` (prices, macro series, news, GDELT, labels,
paper-trading accounts) is git-ignored and is downloaded or produced locally by the collectors. If you run the
collectors, you obtain the data yourself and you are responsible for each source's terms.

The "terms" column records what the project found when the source was added (2026-10). Licenses change — check them
yourself before use. The code stores a `license` value with every series (`observations.license`, `cause_events.license`).
Where it says *unconfirmed*, no explicit license was found and the data is treated as private/research use only.

## Market and macro data

| source | used for | collector | terms (as recorded) |
|---|---|---|---|
| FRED (St. Louis Fed) | rates, real yields, FX, CPI, balance sheet, NFCI, GDPNow | `src/ms/collectors/fred.py` | API key required; most series public domain; GVZ/OVX/VIX/NASDAQ (CBOE, Nasdaq): restricted by the original owner; EPU, IGREA, PCOPPUSDM: CC BY (per series in code) |
| EIA | WTI/Brent spot, futures, weekly petroleum status (WPSR), STEO | `eia_spot.py`, `eia_wpsr.py`, `eia_steo.py` | API key required; US government work, public domain |
| CFTC Commitments of Traders | positioning | `cot.py` | US government work, public domain |
| NBP (National Bank of Poland) | USD/PLN, reference rate | `nbp.py`, `nbp_rates.py` | free use with attribution (recorded as CC BY) |
| Yahoo Finance | daily prices, oil futures curve | `_yahoo.py`, `yf_metals.py`, `yf_oil.py`, `curve.py` | terms of service restrict redistribution (`tos_restricted`) |
| Stooq | long daily history of metals (downloaded manually) | `metals_stooq.py` | terms restrict redistribution (`tos_restricted`) |
| Binance (Vision archive, futures API) | BTC/ETH candles, open interest, funding | `binance_klines.py`, `binance_metrics.py`, `funding.py` | terms of service (`tos_restricted`) |
| Bybit | open interest, funding | `funding.py` | terms of service (`tos_restricted`) |
| Deribit | DVOL implied-volatility index | `dvol.py` | terms of service (`tos_restricted`) |
| Coin Metrics Community | on-chain metrics, stablecoin supply | `coinmetrics.py`, `coinmetrics_stables.py` | **CC BY-NC 4.0** (non-commercial) |
| alternative.me | Crypto Fear & Greed index | `fng.py` | free with attribution (recorded as CC BY) |
| Caldara–Iacoviello GPR, TPU | geopolitical / trade-policy risk indices | `gpr_tpu.py` | classic GPR/TPU: attribution (recorded as CC BY); AI-GPR: *unconfirmed* |
| Baumeister–Hamilton oil shocks | oil supply/demand shocks | `bh_shocks.py` | academic data, attribution (recorded as CC BY) |
| GDELT 2.0 events | geopolitical event features, news entries | `src/gdelt_backfill.py`, `src/e4hist_gdelt.py` | "unlimited and unrestricted use", citation required |
| COMEX, Baker Hughes | inventories, rig count (manual inbox `data/inbox/`) | `inbox.py` | manual download; owner's terms |

## Cause labels and validation sets (stage 4N)

| source | used for | where | terms (as recorded) |
|---|---|---|---|
| Baker, Bloom, Davis, Sammon — *What Triggers Stock Market Jumps?* | E1 test set (newspaper passages coded by humans), taxonomy categories | `src/ms/cause_sources.py` (downloads the authors' public sheet) | academic, *unconfirmed* — not redistributed; only category names appear in `ref/taxonomy.csv` |
| EIA *World Oil Market and Oil Price Chronologies 1970–2003* (via Wayback) | E3 input | `cause_sources.py` | public domain |
| Wikipedia *Chronology of world oil market events* (fixed revision) | E3 input | `cause_sources.py` | **CC BY-SA** — not redistributed |
| SF Fed monetary policy surprises; Jarociński–Karadi shocks; Känzig OPEC shocks | calendar candidates | `cause_sources.py`, `events_calendar.py` | public domain / academic (*unconfirmed* for JK) |
| Federal Reserve FOMC calendar, NOAA NHC hurricanes | calendar candidates | `events_calendar.py` | US government, public domain |
| DefiLlama hacks API | crypto hack days | `cause_sources.py` | DefiLlama terms, *unconfirmed* — not redistributed |
| World Gold Council — *Gold Market Commentary* | E2 test set | `ref/e2_wgc_index.csv` (month, URL, code, sentence position + SHA-256) | **personal, non-commercial use only** (gold.org terms). **Quotes are not included.** Save the pages yourself and run `uv run src/e2_wgc_restore.py` to rebuild `ref/e2_wgc_gold.csv` locally (git-ignored) |
| Hamilton (2011), Baumeister & Kilian (2016) | E3 oil episodes | `ref/oil_episodes.csv` | short attributed quotations with page references |
| Hand-entered crypto dates (halvings, depegs, ETF approvals) | calendar candidates | `ref/crypto_events.csv` | facts with links to sources |

## News feeds (stage 4N-live)

Only RSS feeds and official APIs, checked against robots.txt (RFC 9309, longest match) and each site's terms when added
(details: `docs/ETAP4N-LIVE-PLAN.md`, in Polish). Sources that forbid automated access are not fetched; nothing is
circumvented. Article pages are never downloaded; only title, link and the feed's own lead are stored, locally.

| feed | terms (as recorded) |
|---|---|
| Federal Reserve Board, SEC, CFTC, OFAC | US government, public domain (SEC requires a contact e-mail in the User-Agent: `MS_CONTACT_EMAIL`) |
| ECB, Bank of England, BIS | free use with attribution |
| World Gold Council, Silver Institute | site terms (personal use) |
| Rigzone | private, non-commercial use; lead must not be modified |
| gCaptain, Offshore Energy, Hellenic Shipping News | no explicit terms found / robots-dependent (Hellenic is skipped while its robots.txt is unavailable) |
| Bitcoin Magazine, SilverSeek, GoldSeek | **title and link only** (copying prohibited without consent) |
| The Block | RSS-reader use only; excluded from any analysis (`reader_only`) |
| GDELT DOC 2.0 API | disabled since 2026-10-10 (persistent HTTP 429) |

## What you may redistribute

The code is under the PolyForm Noncommercial License 1.0.0 (`LICENSE`). That license covers **only this repository's
own code and text**. It grants nothing for third-party data. Do not publish data collected with this code unless the
source's terms allow it.
