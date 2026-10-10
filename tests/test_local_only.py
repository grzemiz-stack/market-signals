"""Zasada „tylko lokalnie” (DECISIONS 2026-10-07): sieć tylko do pobierania publicznych danych z listy ms.netpolicy,
LLM tylko przez ms.llm na 127.0.0.1, Ollama skonfigurowana na pętlę zwrotną. Stan na żywo (zainstalowane plisty,
nasłuch Ollamy): tools/check_runtime.sh w bramce."""

from __future__ import annotations

import plistlib
import re
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ms import llm, netpolicy  # noqa: E402

CODE = [p for d in ("src", "tools") for p in (ROOT / d).rglob("*") if p.suffix in (".py", ".sh", ".command")
        and "__pycache__" not in p.parts]
LLM_GATE = ROOT / "src" / "ms" / "llm.py"
POLICY = {LLM_GATE, ROOT / "src" / "ms" / "netpolicy.py"}  # bramka LLM i sama polityka (opis w docstringu)
URL = re.compile(r"https?://[A-Za-z0-9.\-\[\]:]+")
SEND = re.compile(r"[\w.\]\)]*\.(post|put|patch)\(|method\s*=\s*['\"](POST|PUT|PATCH|DELETE)|"
                  r"request\(\s*['\"](POST|PUT|PATCH|DELETE)", re.I)
# wywołania .put( itp., które NIE są siecią (sprawdzone ręcznie): plik -> dokładny tekst
NOT_NETWORK = {"src/gdelt_backfill.py": {"results.put("}}
LLM_REF = re.compile(r"11434|ollama|/api/generate|/api/chat|/v1/chat|/v1/completions", re.I)
LLM_LIBS = ("openai", "anthropic", "google.generativeai", "google.genai", "mistralai", "cohere", "litellm", "langchain",
            "ollama", "groq", "together", "replicate")
LLM_IMPORT = re.compile(r"^\s*(import|from)\s+(" + "|".join(re.escape(x) for x in LLM_LIBS) + r")\b", re.M)


def _text(p: Path) -> str:
    return p.read_text(errors="ignore")


def test_code_scanned():
    assert len(CODE) > 30 and LLM_GATE in CODE


def test_every_host_is_a_listed_data_source_or_local():
    bad = sorted({(p.relative_to(ROOT).as_posix(), u) for p in CODE for u in URL.findall(_text(p))
                  if not netpolicy.is_allowed(u)})
    assert not bad, f"host spoza ms.netpolicy.DATA_SOURCES: {bad}"


def test_no_sending_methods_outside_llm_gate():
    bad = [(r, m.group(0)) for p in CODE if p != LLM_GATE for r in [p.relative_to(ROOT).as_posix()]
           for m in SEND.finditer(_text(p)) if m.group(0) not in NOT_NETWORK.get(r, set())]
    assert not bad, f"wysyłanie danych (POST/PUT/…) poza ms.llm: {bad}"


def test_llm_only_through_gate():
    bad = [p.relative_to(ROOT).as_posix() for p in CODE if p not in POLICY and p.parent.name != "tools"
           and (LLM_REF.search(_text(p)) or LLM_IMPORT.search(_text(p)))]
    assert not bad, f"odwołanie do LLM poza ms.llm: {bad}"


def test_no_llm_client_libraries_in_dependencies():
    deps = " ".join(tomllib.loads((ROOT / "pyproject.toml").read_text())["project"].get("dependencies", [])).lower()
    assert not [x for x in LLM_LIBS if re.search(rf"(^|\s|\"){re.escape(x)}\b", deps)]


def test_llm_gate_posts_only_to_loopback(monkeypatch):
    src = _text(LLM_GATE)
    assert src.count("requests.post(") == 1 and 'requests.post(f"{base_url()}' in src
    assert netpolicy.is_local(llm.DEFAULT_URL)
    monkeypatch.setenv("MS_OLLAMA_URL", "http://10.0.0.5:11434")
    with pytest.raises(RuntimeError):
        llm.base_url()
    monkeypatch.setenv("MS_OLLAMA_URL", "https://api.example.com")
    with pytest.raises(RuntimeError):
        llm.base_url()
    monkeypatch.setenv("MS_OLLAMA_URL", "http://localhost:11434/")
    assert llm.base_url() == "http://localhost:11434"


def _jobctl():
    import importlib.util

    spec = importlib.util.spec_from_file_location("jobctl", ROOT / "tools" / "jobctl.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_ollama_plist_listens_on_loopback_only():
    plists = [plistlib.loads(t.encode()) for t in _jobctl().rendered().values()]
    oll = [d for d in plists if any("ollama" in a for a in d["ProgramArguments"])]
    assert len(oll) == 1, "dokładnie jeden plist Ollamy w launchd/"
    host = oll[0].get("EnvironmentVariables", {}).get("OLLAMA_HOST", "")
    assert host.split(":")[0] in netpolicy.LOOPBACK, host
    assert oll[0].get("RunAtLoad") and oll[0].get("KeepAlive")
