"""Job „news” (co godzinę): pobiera kanały z ms.news.SOURCES i tematy GDELT do data/news.duckdb, potem publikuje kopię
data/news_view.duckdb dla dashboardu. Kod wyjścia != 0, gdy któryś kanał padł albo został pominięty (robots/odmowa);
limit GDELT (429 / komunikat limitu) to nie awaria — stan każdego źródła pokazuje tools/health.sh.

uv run src/collect_news.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ms import db, news  # noqa: E402
from publish_view import publish  # noqa: E402

log = logging.getLogger("news")
VIEW = db.ROOT / "data" / "news_view.duckdb"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(db.ROOT / "logs" / "news.log"), logging.StreamHandler()])
    con = news.connect()
    before = dict(con.execute("SELECT source, last_status FROM news_fetch").fetchall())
    res = news.collect(con)
    res += news.build_gdelt_events(con, db.GDELT_PATH, news.now_utc(), f"news-gdelt-ev-{news.now_utc():%Y%m%dT%H%M%S}")
    for r in res:
        log.info("%s: %s, pozycji %d, nowych %d%s", r.source, r.status, r.items, r.new, " — LUKA (oznaczona)" if r.gap else "")
    con.close()
    publish(news.NEWS_DB, VIEW, VIEW.with_suffix(".json"))
    limited = [r for r in res if r.status.startswith("LIMIT") or r.status == "POMINIĘTE: limit GDELT w tym przebiegu"]
    busy = [r for r in res if r.status.startswith("POMINIĘTE: gdelt.duckdb zajęta")]   # snapshot pisze — następna godzina
    # robots.txt zabrania / niedostępny albo odmowa 401/403/451: źródło wyłączone (bez obejścia). Powiadomienie RAZ,
    # przy zmianie stanu (nie co godzinę); stan stale w tools/health.sh.
    blocked = [r for r in res if (r.status.startswith("POMINIĘTE: robots") or r.status.startswith("ODMOWA")) and r not in busy]
    changed = [r for r in blocked if (before.get(r.source) or "")[:12] != r.status[:12]]
    if changed:
        import subprocess
        text = "; ".join(f"{r.source}: {r.status[:60]}" for r in changed)
        subprocess.run(["osascript", "-e", f'display notification "{text}" with title "market-signals: źródło wiadomości wyłączone"'],
                       check=False)
    disabled = [r for r in res if r.status.startswith("WYŁĄCZONE")]   # decyzja (enabled=False), nie awaria — bez logu co godzinę
    bad = [r for r in res if not (r.status.startswith("OK") or r.status.startswith("304"))
           and r not in limited + busy + blocked + disabled]
    for r in limited:
        log.warning("%s: %s — limit dostawcy, ponowienie za godzinę (widoczne w tools/health.sh)", r.source, r.status)
    for r in bad:
        log.warning("%s: %s", r.source, r.status)
    for r in blocked:
        log.warning("%s: %s — źródło wyłączone (robots/odmowa), ponowna kontrola robots.txt co dobę", r.source, r.status)
    return 1 if bad else 0          # limit GDELT, źródła wyłączone (robots/odmowa, enabled=False) nie są awarią joba


if __name__ == "__main__":
    sys.exit(main())
