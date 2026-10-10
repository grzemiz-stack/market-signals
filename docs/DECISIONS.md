# Key decisions (summary)

A condensed English summary of the project's decision log (the full log is private and in Polish). Code comments and
the stage plans in `docs/` refer to dates here, e.g. "DECISIONS 2026-10-07". Each entry: what was decided, and why.

## Principles

| date | decision | why |
|---|---|---|
| 2026-10-06 | **Point-in-time everywhere.** Every value has `known_at`; a decision for day D uses only data known at D 22:00 UTC. Market prices are known at the session close; values created by a publication (rates, macro) are known at their release time. | Look-ahead bias is the most common way a backtest lies. |
| 2026-10-06 | **The LLM only classifies text** into structured events/causes. It never forecasts and never sees prices. Relationships "what moves what" are learned by numeric models. | An LLM's answer cannot be validated as a forecast; a classification can. |
| 2026-10-06 | **Changing a test definition (thresholds, windows, type) is a new trial** in the `runs` table (hash of the full definition), never a silent rerun. | The number of trials is needed to correct for multiple testing (Deflated Sharpe, BH). |
| 2026-10-07 | **Everything runs locally on one Mac.** Models via Ollama on 127.0.0.1; no data leaves the machine; the network is used only to download public data from an allowlist (`src/ms/netpolicy.py`). Enforced by tests and a live check of listening sockets. | Privacy and reproducibility; no hidden dependencies. |
| 2026-10-07 | **A backtest result does not justify real money** (D11). With ~10 years of data, t > 3 is out of reach. Real money would be decided only on live paper accounts. | Honest limits of the evidence. |

## Data

| date | decision | why |
|---|---|---|
| 2026-10-06 | Metal labels come only from one stitched series; COMEX and Baker Hughes only via a manual inbox; Stooq downloaded manually once a quarter. | One source of truth per series; respect sources without an API. |
| 2026-10-06 | FRED market observations (FX at 12:00 ET; VIX/GVZ/OVX at 16:15 ET) are known on the trading day; Treasury yields and derived series keep their publication time. | Correct PIT for the decision at 22:00 UTC. |
| 2026-10-06 | GDELT: broad filter (USA among actors), USA–USA pairs removed in features. | Domestic US noise dominates otherwise. |
| 2026-10-07 | News: RSS and official APIs only; robots.txt per RFC 9309 (longest match — Python's robotparser gets this wrong); sources whose terms forbid automated access go to a manual list; nothing is circumvented. | Legal and polite collection. |
| 2026-10-10 | GDELT DOC API disabled (persistent HTTP 429; two topics had zero successful downloads). GDELT event files unaffected. | A source that never answers is noise in the health check. |

## Models

| date | decision | why |
|---|---|---|
| 2026-10-06 | Probability of a large 5-day move (p_up/p_down) = the best simple baseline per asset (implied/realized volatility, GARCH-t). **LightGBM withdrawn** from this role (code and report kept). | LightGBM did not beat the baselines on any asset and was worse on four. |
| 2026-10-06 | **Model registry**: modules ask `registry.champion(asset, question)`; nothing is hard-coded. Promotion only if the 95% block-bootstrap CI of the difference over 6 out-of-sample months is above zero with n ≥ 100 days; demotion to the base rate symmetrically. Rules count only months after 2026-10-06 (first possible change: 2027-05-01). | Champions were selected on the test period (inflated by selection); only future data can confirm them. |
| 2026-10-06 | Analog search is a learning tool only, not a signal. | No edge over the base rate on any asset. |
| 2026-10-06 | Hypotheses from the literature are tested with Benjamini–Hochberg correction; only `confirmed` ones may become feature candidates, and they still have to beat the champion. | Avoid promoting chance findings. |

## Stage 5 — rule-based portfolio

| date | decision | why |
|---|---|---|
| 2026-10-07 | Rules frozen before the first computation: pre-registration in `runs` with hash `d9cb3a3a2da04caa` (definition + rule code; a test fails if the code changes). | No tuning after seeing results. |
| 2026-10-07 | Winner rule (D7): the simplest variant unless a more complex one has a higher Sharpe and no worse drawdown on the development period, and it must beat equal weight at costs ×1 and ×2. Result: **equal weight of 4 assets** (no inverse-volatility variant beat it). | Simplicity by default. |
| 2026-10-07 | Holdout 2024-10-06 … 2026-10-05 opened **once**, after the winner was fixed, with a note that this period had been seen by earlier stages (4P, 3A). No rule changes afterwards. | A holdout opened twice is not a holdout. |
| 2026-10-07 | Two live paper accounts from 2026-10-07: "system" (equal weight) and "system_ostrozny" (OVX-filtered inverse volatility, chosen **after** seeing all results, so judged only on future data). Shutdown threshold = 1.5 × worst development drawdown; alarms (−30% from peak, −15% in a week) are information only, not trading rules. | The only clean test is the future. |

## Stage 4N — cause classifier (local LLM)

| date | decision | why |
|---|---|---|
| 2026-10-06 | Calendar labels (FOMC, OPEC, hacks, ETF approvals …) are **candidates** (`validated = false`), shown only as "on this day: …". A cause needs text evidence from a validated classifier or a human. | A date match is not proof of cause. |
| 2026-10-07 | E1 threshold frozen before any model run: human–human κ on the BBDS codings = 0.795 [0.771; 0.819] → model must reach κ ≥ 0.695. | The model should be nearly as consistent as two human coders. |
| 2026-10-07 | E2 reference set switched from user labels to World Gold Council monthly commentaries (user does not know the causes). Mapping rules written before reading; an independent sub-agent checked 20 rows (round 1: 7 "no" → rows relying on "first mappable factor" removed; round 2: 0 "no"). | A reference set must be checked by someone without access to the mapper's reasoning. |
| 2026-10-07 | Code conventions (dollar → fx_capital, yields and central-bank gold buying → monetary) moved into the production definitions **before** E2. | The prompt that is validated must be the prompt that is used. |
| 2026-10-08 | Third and final trial: prompt v2 (macro vs monetary split), E4 replaced by E4-hist (full GDELT export + mentions for the same 42 calendar days). | Trials 1–2 failed E1 and E4; E4's input gave the model no chance. |
| 2026-10-08 | **Validation closed after 3 trials: classifier NOT validated** (best E1 κ 0.628 < 0.695; E4-hist 0/42). The LLM is not used in the status or the dashboard. | Pre-registered limit of 3 trials. |

## Operations

| date | decision | why |
|---|---|---|
| 2026-10-07 | Jobs via launchd with RunAtLoad and catch-up (a job runs after login only if it missed its scheduled time or the last run failed); `lockf` prevents double runs. | A laptop sleeps; schedules must survive that. |
| 2026-10-07 | Dashboard (Streamlit, 127.0.0.1 only) reads a read-only published copy of the database; every number comes from `ms.views` (a provenance test checks this). | DuckDB cross-process locks; one source of numbers. |
| 2026-10-10 | Paper-order executions are written only by the nightly job; the dashboard opens the game database read-only (tests: job → `executed`; page views leave the file hash unchanged). | Viewing must never change state. |
| 2026-10-10 | Account page: the value chart uses explicit axes (y fitted to the data, not from zero; daily x axis). The order journal takes executions from the same replay as positions and pending orders: an order with an execution price but not yet saved by the nightly job is shown as "executed (saved by the nightly job)". The database is not changed. | Streamlit's default line chart started y at zero and used 12-hour ticks, so series around 1000 PLN looked empty. The journal read the raw DB status while the rest of the page used the replay. |
| 2026-10-10 | Asset cards: price charts use the same explicit-axis chart (y not from zero). X-axis ticks depend on the range: daily up to 31 days, monthly up to a year, quarterly beyond (`time_axis`). | Two years of daily prices with daily ticks would crowd the axis; prices were flattened by a zero-based y axis. |
