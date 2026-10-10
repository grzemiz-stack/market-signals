"""Etap 4N: klasyfikator przyczyn (Qwen, lokalnie przez ms.llm na 127.0.0.1). LLM tylko KLASYFIKUJE tekst na kod
przyczyny — nie ocenia wpływu i nie widzi cen (DECISIONS 2026-10-06). Prompt v1: ref/prompt_v1.txt + ref/prompt_examples.csv
+ przykłady BBDS wyłącznie z lat 1900–1949 (E1 testuje 1950–2022). Walidacja: src/validate_causes.py, plan
docs/ETAP4N-WALIDACJA-PLAN.md. Bez `validated = true` (E1–E4) wyniki nie trafiają do statusu ani dashboardu.
"""

from __future__ import annotations

import hashlib
import json

import pandas as pd

from ms import db, llm

PROMPT_VERSION = "v2"   # trzecia próba (2026-10-08): rozdzielenie macro / monetary
TEMPLATE = db.ROOT / "ref" / "prompt_v1.txt"
EXAMPLES = db.ROOT / "ref" / "prompt_examples.csv"
TAXONOMY = db.ROOT / "ref" / "taxonomy.csv"
OPTIONS = {"temperature": 0, "seed": 20261007, "num_ctx": 32768}
FEWSHOT_YEARS = (1900, 1949)

# Definicje kodów: kolumna `prompt` w ref/taxonomy.csv (jedno źródło; prompt produkcyjny = prompt walidowany).
E3_CODES = {"supply": "oil supply shock (production disruption, OPEC, war in producers)",
            "global_demand": "global demand for oil and commodities (world business cycle)",
            "precautionary": "precautionary / inventory demand (fear of future shortages, speculative stockpiling)"}


def taxonomy() -> pd.DataFrame:
    return pd.read_csv(TAXONOMY, comment="#")


def bbds_map() -> dict[str, str]:
    return {b: r.code for r in taxonomy().itertuples() if isinstance(r.bbds, str) for b in r.bbds.split("|")}


def code_descriptions(codes: list[str]) -> dict[str, str]:
    t = taxonomy().set_index("code")["prompt"]
    return {c: E3_CODES[c] if c in E3_CODES else t[c] for c in codes}


def bbds_fewshots(con) -> list[tuple[str, str]]:
    """1 przykład na kod BBDS: najwcześniejszy dzień z cytatem z lat 1900–1949 (deterministycznie)."""
    b = con.execute("""SELECT date, coder, primary_cat, passage FROM bbds_codings
                       WHERE year(date) BETWEEN ? AND ? AND passage IS NOT NULL ORDER BY date, coder, row_no""",
                    list(FEWSHOT_YEARS)).df()
    m = bbds_map()
    b["code"] = b["primary_cat"].map(m)
    first = b.dropna(subset=["code"]).drop_duplicates("code")
    return [(r.code, f"[1] {r.passage.strip()}") for r in first.itertuples()]


def ext_fewshots() -> list[tuple[str, str]]:
    e = pd.read_csv(EXAMPLES, comment="#")
    return list(zip(e["code"], e["text"]))


def build_prompt(text_items: list[str], codes: list[str], examples: list[tuple[str, str]]) -> str:
    desc = code_descriptions(codes)
    ex = [(c, t) for c, t in examples if c in codes]
    return TEMPLATE.read_text().format(
        codes="\n".join(f"- {c}: {desc[c]}" for c in codes),
        examples="\n".join(f'Text: {t}\nAnswer: {{"cause": "{c}"}}' for c, t in ex) or "(none)",
        text="\n".join(f"[{i + 1}] {t}" for i, t in enumerate(text_items)))


def schema(codes: list[str]) -> dict:
    return {"type": "object", "properties": {
        "cause": {"type": "string", "enum": codes},
        "cause_secondary": {"type": ["string", "null"]},
        "confidence": {"type": "string", "enum": ["low", "med", "high"]},
        "evidence_ids": {"type": "array", "items": {"type": "integer"}}},
        "required": ["cause", "confidence", "evidence_ids"]}


def prompt_hash() -> str:
    """Hash szablonu, przykładów rozszerzeń, taksonomii (z definicjami `prompt`), opcji i reguły wyboru przykładów BBDS."""
    payload = (TEMPLATE.read_text() + EXAMPLES.read_text()
               + json.dumps(E3_CODES, sort_keys=True) + json.dumps(OPTIONS, sort_keys=True) + str(FEWSHOT_YEARS)
               + TAXONOMY.read_text())
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def classify(model: str, text_items: list[str], codes: list[str], examples: list[tuple[str, str]]) -> dict:
    """Jedna klasyfikacja. Niepoprawny JSON -> jedno ponowienie, potem cause=None z surową odpowiedzią."""
    prompt = build_prompt(text_items, codes, examples)
    raw = ""
    for _ in range(2):
        raw = llm.generate(model, prompt, format=schema(codes), **OPTIONS)
        try:
            out = json.loads(raw)
            if out.get("cause") in codes:
                out["raw"] = raw
                return out
        except json.JSONDecodeError:
            pass
    return {"cause": None, "raw": raw}
