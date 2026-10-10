"""Joby launchd: harmonogram, „czy zaległy”, stan ostatniego przebiegu. Tylko biblioteka standardowa (python3 systemowy).

Zaległy = od ostatniego planowego terminu (<= teraz) nie było UDANEGO przebiegu (last_ok). Po starcie Maca job rusza
tylko wtedy, gdy przegapił termin (Mac wyłączony / uśpiony) albo ostatni przebieg padł lub został przerwany (STOP),
a nie przy każdym logowaniu.
Stan: logs/state/<job>.json (last_start, last_end, last_rc, last_ok). Blokada: logs/locks/<job>.lock (lockf w run_job.sh).

python3 tools/jobctl.py due JOB          -> kod 0 gdy zaległy, 1 gdy nie
python3 tools/jobctl.py start JOB        -> zapis startu
python3 tools/jobctl.py end JOB RC       -> zapis końca (RC 0 = udany)
python3 tools/jobctl.py list             -> nazwy jobów
python3 tools/jobctl.py show JOB         -> label|skrypt|log
python3 tools/jobctl.py status           -> tabela dla tools/health.sh
python3 tools/jobctl.py services         -> usługi: nazwa|label|adres kontroli|log
python3 tools/jobctl.py render DIR       -> plisty z szablonów launchd/*.plist.template do DIR (<prefiks>.<nazwa>.plist)

Szablony: __PREFIX__ = MS_LAUNCHD_PREFIX (domyślnie local.market-signals), __REPO__ = MS_REPO (domyślnie katalog repo),
__UV__ = UV (domyślnie `uv` z PATH).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "logs" / "state"
PREFIX_NAME = os.environ.get("MS_LAUNCHD_PREFIX", "local.market-signals")
PREFIX = PREFIX_NAME + "."
TEMPLATES = ROOT / "launchd"


def rendered() -> dict[str, str]:
    """{plik plist: treść} z szablonów launchd/*.plist.template — jedno źródło dla instalacji, kontroli i testów."""
    uv = os.environ.get("UV") or shutil.which("uv")
    if not uv:
        raise SystemExit("brak uv: ustaw UV=/ścieżka/do/uv albo dodaj uv do PATH")
    repo = os.environ.get("MS_REPO", str(ROOT))
    out = {}
    for t in sorted(TEMPLATES.glob("*.plist.template")):
        name = t.name.removesuffix(".plist.template")
        out[f"{PREFIX}{name}.plist"] = (t.read_text().replace("__PREFIX__", PREFIX_NAME).replace("__REPO__", repo)
                                        .replace("__UV__", uv))
    return out

# Każdy nowy job launchd -> wpis tutaj + plist w launchd/ (test: tests/test_jobs.py).
# schedule: ("hourly", min), ("daily", godz, min) albo ("monthly", dzień, godz, min) — jak StartCalendarInterval w pliście.
JOBS = {
    "snapshot": {"script": "tools/snapshot_daily.sh", "schedule": ("daily", 23, 30), "log": "logs/snapshot.log"},
    "registry": {"script": "tools/registry_monthly.sh", "schedule": ("monthly", 1, 6, 0), "log": "logs/registry.log"},
    "system": {"script": "tools/system_daily.sh", "schedule": ("daily", 23, 50), "log": "logs/system.log"},
    "news": {"script": "tools/news_hourly.sh", "schedule": ("hourly", 7), "log": "logs/news.log"},
}
# Usługi: działają cały czas (RunAtLoad + KeepAlive), bez harmonogramu i nadrabiania. Każda -> plist w launchd/.
SERVICES = {"ollama": {"check": "http://127.0.0.1:11434/api/version", "log": "/opt/homebrew/var/log/ollama.log"},
            "dashboard": {"check": "http://127.0.0.1:8501/_stcore/health", "log": "logs/dashboard.err.log"}}


def last_scheduled(schedule: tuple, now: datetime) -> datetime:
    """Ostatni planowy termin <= now."""
    if schedule[0] == "daily":
        _, h, m = schedule
        t = now.replace(hour=h, minute=m, second=0, microsecond=0)
        return t if t <= now else t - timedelta(days=1)
    if schedule[0] == "hourly":
        _, m = schedule
        t = now.replace(minute=m, second=0, microsecond=0)
        return t if t <= now else t - timedelta(hours=1)
    if schedule[0] == "monthly":
        _, d, h, m = schedule
        t = now.replace(day=d, hour=h, minute=m, second=0, microsecond=0)
        if t <= now:
            return t
        y, mo = (now.year, now.month - 1) if now.month > 1 else (now.year - 1, 12)
        return t.replace(year=y, month=mo)
    raise ValueError(schedule)


def load(job: str) -> dict:
    p = STATE / f"{job}.json"
    return json.loads(p.read_text()) if p.exists() else {}


def save(job: str, st: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    tmp = STATE / f"{job}.json.tmp"
    tmp.write_text(json.dumps(st, indent=1))
    tmp.replace(STATE / f"{job}.json")


def is_due(job: str, now: datetime | None = None, st: dict | None = None) -> bool:
    now = now or datetime.now()
    st = load(job) if st is None else st
    if not st.get("last_ok"):
        return True
    return datetime.fromisoformat(st["last_ok"]) < last_scheduled(JOBS[job]["schedule"], now)


def _fmt(s: str | None) -> str:
    return s[:16].replace("T", " ") if s else "—"


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "status"
    now = datetime.now().replace(microsecond=0)
    if cmd in ("show", "due", "start", "end") and (len(argv) < 2 or argv[1] not in JOBS):
        print(f"nieznany job: {argv[1:] or '(brak)'}; znane: {', '.join(JOBS)}", file=sys.stderr)
        return 2
    if cmd == "services":
        print("\n".join(f"{n}|{PREFIX}{n}|{v['check']}|{v['log']}" for n, v in SERVICES.items()))
        return 0
    if cmd == "list":
        print("\n".join(JOBS))
        return 0
    if cmd == "render":
        d = Path(argv[1])
        d.mkdir(parents=True, exist_ok=True)
        for f in d.glob("*.plist"):
            f.unlink()
        for name, text in rendered().items():
            (d / name).write_text(text)
        print(d)
        return 0
    if cmd == "show":
        j = argv[1]
        print(f"{PREFIX}{j}|{JOBS[j]['script']}|{JOBS[j]['log']}")
        return 0
    if cmd == "due":
        return 0 if is_due(argv[1], now) else 1
    if cmd == "start":
        st = load(argv[1])
        st.update(last_start=now.isoformat(), last_end=None, last_rc=None)
        save(argv[1], st)
        return 0
    if cmd == "end":
        st, rc = load(argv[1]), int(argv[2])
        st.update(last_end=now.isoformat(), last_rc=rc)
        if rc == 0:
            st["last_ok"] = now.isoformat()
        save(argv[1], st)
        return 0
    if cmd == "status":
        for j in JOBS:
            st = load(j)
            rc = st.get("last_rc")
            res = "w trakcie/przerwany" if st.get("last_start") and st.get("last_end") is None else (
                "—" if rc is None else ("OK" if rc == 0 else f"BŁĄD (kod {rc})"))
            print(f"{j}|{_fmt(st.get('last_start'))}|{res}|{_fmt(st.get('last_ok'))}|"
                  f"{'TAK' if is_due(j, now, st) else 'nie'}|{JOBS[j]['log']}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
