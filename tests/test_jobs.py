"""Joby launchd: plisty zgodne z tools/jobctl.py, nadrabianie tylko zaległych terminów, blokada przed podwójnym przebiegiem."""

from __future__ import annotations

import importlib.util
import os
import plistlib
import subprocess
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("jobctl", ROOT / "tools" / "jobctl.py")
jobctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jobctl)

ALL_PLISTS = {p: plistlib.loads(t.encode()) for p, t in jobctl.rendered().items()}   # z szablonów launchd/*.plist.template
JOB_PLISTS = {p: d for p, d in ALL_PLISTS.items() if d["Label"].removeprefix(jobctl.PREFIX) not in jobctl.SERVICES}


def test_services_match_plists():
    svc = {d["Label"].removeprefix(jobctl.PREFIX): d for d in ALL_PLISTS.values()}
    assert set(jobctl.SERVICES) <= set(svc), "usługa bez plista"
    for name in jobctl.SERVICES:
        assert svc[name].get("RunAtLoad") is True and svc[name].get("KeepAlive") is True, name
    assert {d["Label"].removeprefix(jobctl.PREFIX) for d in ALL_PLISTS.values()} == set(jobctl.JOBS) | set(jobctl.SERVICES)


def test_every_job_plist_matches_jobctl():
    jobs = set()
    for p, d in JOB_PLISTS.items():
        job = d["Label"].removeprefix(jobctl.PREFIX)
        jobs.add(job)
        assert d["ProgramArguments"][1:] == [str(ROOT / "tools" / "run_job.sh"), job], p
        assert d.get("RunAtLoad") is True, f"{p}: brak RunAtLoad"
        sch, cal = jobctl.JOBS[job]["schedule"], d["StartCalendarInterval"]
        if sch[0] == "hourly":
            assert cal == {"Minute": sch[1]}, p
        elif sch[0] == "daily":
            assert cal == {"Hour": sch[1], "Minute": sch[2]}, p
        else:
            assert cal == {"Day": sch[1], "Hour": sch[2], "Minute": sch[3]}, p
        assert (ROOT / jobctl.JOBS[job]["script"]).exists()
    assert jobs == set(jobctl.JOBS), "każdy job w JOBS ma plist i odwrotnie"


def test_last_scheduled():
    ls = jobctl.last_scheduled
    assert ls(("daily", 23, 30), datetime(2026, 10, 7, 8, 0)) == datetime(2026, 10, 6, 23, 30)
    assert ls(("daily", 23, 30), datetime(2026, 10, 7, 23, 30)) == datetime(2026, 10, 7, 23, 30)
    assert ls(("monthly", 1, 6, 0), datetime(2026, 10, 1, 5, 59)) == datetime(2026, 9, 1, 6, 0)
    assert ls(("monthly", 1, 6, 0), datetime(2026, 1, 1, 5, 0)) == datetime(2025, 12, 1, 6, 0)
    assert ls(("monthly", 1, 6, 0), datetime(2026, 10, 7, 12, 0)) == datetime(2026, 10, 1, 6, 0)


def test_hourly_schedule():
    ls, due = jobctl.last_scheduled, jobctl.is_due
    assert ls(("hourly", 7), datetime(2026, 10, 7, 10, 30)) == datetime(2026, 10, 7, 10, 7)
    assert ls(("hourly", 7), datetime(2026, 10, 7, 10, 5)) == datetime(2026, 10, 7, 9, 7)
    assert not due("news", datetime(2026, 10, 7, 10, 30), {"last_ok": "2026-10-07T10:08:00"})
    assert due("news", datetime(2026, 10, 7, 11, 8), {"last_ok": "2026-10-07T10:08:00"})


def test_due_only_after_missed_term():
    due = jobctl.is_due
    ok_last_night = {"last_start": "2026-10-06T23:30:00", "last_ok": "2026-10-06T23:34:00"}
    assert not due("snapshot", datetime(2026, 10, 7, 8, 0), ok_last_night)        # rano po starcie Maca: nic
    assert due("snapshot", datetime(2026, 10, 7, 23, 31), ok_last_night)           # termin dzisiejszy
    assert due("snapshot", datetime(2026, 10, 8, 9, 0), ok_last_night)             # Mac był wyłączony 7.10 23:30
    assert due("snapshot", datetime(2026, 10, 8, 9, 0), {})                        # nigdy nie biegł
    # przerwany (STOP) albo zakończony błędem po terminie -> nadal zaległy
    interrupted = {"last_start": "2026-10-07T23:30:00", "last_end": None, "last_ok": "2026-10-06T23:34:00"}
    assert due("snapshot", datetime(2026, 10, 8, 9, 0), interrupted)
    failed = {"last_start": "2026-10-07T23:30:00", "last_rc": 1, "last_ok": "2026-10-06T23:34:00"}
    assert due("snapshot", datetime(2026, 10, 8, 9, 0), failed)
    assert not due("registry", datetime(2026, 10, 20), {"last_ok": "2026-10-01T06:20:00"})
    assert due("registry", datetime(2026, 11, 3), {"last_ok": "2026-10-01T06:20:00"})


def test_lock_prevents_second_run(tmp_path):
    env = {**os.environ, "MS_JOBS_LOG": str(tmp_path / "jobs.log")}
    lock = ROOT / "logs" / "locks" / "test_lock.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    holder = subprocess.Popen(["/usr/bin/lockf", "-k", "-s", str(lock), "/bin/sleep", "5"])
    try:
        time.sleep(0.5)
        t0 = time.time()
        r = subprocess.run(["/bin/zsh", str(ROOT / "tools" / "run_job.sh"), "test_lock"], capture_output=True, env=env)
        assert r.returncode == 0 and time.time() - t0 < 3        # drugi przebieg kończy się od razu, bez pracy
        assert "test_lock] już działa" in (tmp_path / "jobs.log").read_text().splitlines()[-1]
    finally:
        holder.kill()
        holder.wait()
    r = subprocess.run(["/bin/zsh", str(ROOT / "tools" / "run_job.sh"), "test_lock"], capture_output=True, env=env)
    assert r.returncode == 2                                     # wolna blokada -> dochodzi do joba (nieznany)


def test_desktop_files_generated_valid_and_idempotent(tmp_path):
    gen = [str(ROOT / "tools" / "install_desktop.sh"), str(tmp_path)]
    subprocess.run(gen, check=True, capture_output=True)
    files = {n: tmp_path / f"market-signals {n}.command" for n in ("START", "STOP")}
    first = {n: p.read_bytes() for n, p in files.items()}
    subprocess.run(gen, check=True, capture_output=True)
    for n, p in files.items():
        assert os.access(p, os.X_OK), f"{n} niewykonywalny"
        assert subprocess.run(["/bin/zsh", "-n", str(p)]).returncode == 0, f"{n}: błąd składni"
        assert p.read_bytes() == first[n], f"{n}: drugie generowanie zmieniło plik"
        assert f'R="{ROOT}"' in p.read_text()
    start, stop = files["START"].read_text(), files["STOP"].read_text()
    assert "tools/install_launchd.sh" in start and "tools/health.sh" in start and "paper.py status" in start
    assert "jobctl.py due" in start and "127.0.0.1:11434" in start and "read -k1" in start
    assert "127.0.0.1:8501/_stcore/health" in start and 'open "http://127.0.0.1:8501"' in start   # dashboard
    assert "bootout" in stop and not any(x in stop for x in ("rm ", "rm -", "unlink", "delete"))
