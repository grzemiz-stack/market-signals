"""Etap 4C: dashboard tylko lokalnie — konfiguracja (plik + plist), prawdziwy serwer: nasłuch 127.0.0.1, strona
i jej zasoby wyłącznie lokalne (zero CDN), brak połączeń wychodzących, telemetria wyłączona."""

import plistlib
import re
import shutil
import socket
import subprocess
import sys
import time
import tomllib
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CDN = re.compile(r"fonts\.googleapis|fonts\.gstatic|cdn\.jsdelivr|unpkg\.com|cdnjs|googletagmanager|google-analytics|segment\.(io|com)")


def test_config_file_local_no_telemetry():
    c = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text())
    assert c["server"]["address"] == "127.0.0.1" and c["server"]["headless"] is True
    assert c["browser"]["gatherUsageStats"] is False and c["browser"]["serverAddress"] == "127.0.0.1"


def test_service_plist_local_no_telemetry():
    import importlib.util

    spec = importlib.util.spec_from_file_location("jobctl", ROOT / "tools" / "jobctl.py")
    jobctl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(jobctl)
    d = plistlib.loads(jobctl.rendered()[f"{jobctl.PREFIX}dashboard.plist"].encode())
    args = d["ProgramArguments"]
    for flag in ("--server.address=127.0.0.1", "--server.port=8501", "--server.headless=true",
                 "--browser.gatherUsageStats=false"):
        assert flag in args, flag
    assert "src/dashboard/app.py" in args and d["RunAtLoad"] and d["KeepAlive"]


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    port = _free_port()
    tmp = tmp_path_factory.mktemp("dash")
    if (ROOT / "data" / "paper.duckdb").exists():
        shutil.copy(ROOT / "data" / "paper.duckdb", tmp / "p.duckdb")
    else:                                           # bez danych (kopia publiczna): pusta baza gry — test dotyczy sieci
        sys.path.insert(0, str(ROOT / "src"))
        from ms import paper as pp

        pp.connect(tmp / "p.duckdb").close()
    env = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin", "HOME": str(Path.home()), "MS_PAPER_DB": str(tmp / "p.duckdb")}
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "src/dashboard/app.py", "--server.address=127.0.0.1",
                             f"--server.port={port}", "--server.headless=true", "--browser.gatherUsageStats=false"],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(120):
        try:
            if urllib.request.urlopen(f"{base}/_stcore/health", timeout=1).status == 200:
                break
        except OSError:
            time.sleep(0.5)
    else:
        proc.kill()
        pytest.fail("serwer dashboardu nie wystartował")
    yield proc, base, port
    proc.terminate()
    proc.wait(10)


def _listeners(port: int) -> list[str]:
    out = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"], capture_output=True, text=True).stdout
    return [line.split()[8] for line in out.splitlines()[1:]]


def test_server_listens_on_loopback_only(server):
    _, _, port = server
    addrs = _listeners(port)
    assert addrs and all(a.startswith(("127.0.0.1:", "[::1]:")) for a in addrs), addrs


def test_page_and_assets_are_local_no_cdn(server):
    _, base, _ = server
    html = urllib.request.urlopen(base + "/", timeout=10).read().decode()
    refs = re.findall(r'(?:src|href)="([^"]+)"', html)
    assert refs, "strona bez zasobów?"
    for r in refs:
        assert not re.match(r"^(https?:)?//", r) or r.startswith(("http://127.0.0.1", "//127.0.0.1")), f"zasób spoza 127.0.0.1: {r}"
    assert not CDN.search(html)
    for r in refs:
        if r.endswith(".css"):
            css = urllib.request.urlopen(base + "/" + r.lstrip("./"), timeout=10).read().decode(errors="ignore")
            assert not CDN.search(css), f"CDN w {r}"
            assert not re.search(r"url\((['\"]?)https?://(?!127\.0\.0\.1)", css), f"zewnętrzny url() w {r}"
        if r.endswith((".js", ".css")):
            assert urllib.request.urlopen(base + "/" + r.lstrip("./"), timeout=10).status == 200


def test_no_outbound_connections(server):
    proc, base, _ = server
    urllib.request.urlopen(base + "/", timeout=10).read()
    time.sleep(1)
    out = subprocess.run(["lsof", "-nP", "-a", "-p", str(proc.pid), "-iTCP", "-sTCP:ESTABLISHED"],
                         capture_output=True, text=True).stdout
    remotes = [line.split()[8].split("->")[1] for line in out.splitlines()[1:] if "->" in line]
    assert all(r.startswith(("127.0.0.1:", "[::1]:")) for r in remotes), remotes
