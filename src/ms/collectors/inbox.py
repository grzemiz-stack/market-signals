"""Skrzynki ręczne: pliki pobrane w przeglądarce -> data/raw/{źródło}/{data}/ + manifest.

| skrzynka              | co wrzucić                                              | dlaczego ręcznie |
|-----------------------|---------------------------------------------------------|------------------|
| data/inbox/wgc/       | WGC: zakupy banków centralnych (xlsx z gold.org)         | decyzja z planu etapu 1 (nie weryfikowano automatu) |
| data/inbox/bakerhughes/ | Baker Hughes: archiwum rig count (xlsx)                | Akamai 403 dla automatów |
| data/inbox/gld/       | SPDR GLD: archiwum holdingów (csv/xlsx)                 | link do CSV zwraca PDF, strona w JS |
| data/inbox/slv/       | iShares SLV: historia uncji w trustcie                  | API daje tylko bieżące holdingi |
| data/inbox/lbma/      | LBMA: London vault holdings (miesięczne)                | brak pliku danych na stronie |
| data/inbox/stooq/     | xauusd_d.csv, xagusd_d.csv (parsowane przez metals_stooq) | JS proof-of-work |

Tu tylko archiwizacja. Parser powstaje, gdy przyjdzie pierwszy plik — format znamy dopiero wtedy
(nie piszemy parsera na ślepo). Liczba plików czekających na parser -> log + raport.
"""

from __future__ import annotations

import logging

from ms.common import RAW, archive_inbox

NAME = "inbox"
BOXES = ("wgc", "bakerhughes", "gld", "slv", "lbma")
log = logging.getLogger("collect")


def collect(con, full: bool = False) -> int:
    for box in BOXES:
        archive_inbox(box)
        waiting = [p for p in (RAW / box).glob("*/*") if p.is_file()]
        if waiting:
            log.warning("skrzynka %s: %d plików w data/raw/%s/ czeka na parser", box, len(waiting), box)
    return 0
