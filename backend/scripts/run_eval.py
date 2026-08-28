"""
Runs every query in eval/test-queries.md against a live HelpBot backend
and prints the intent/handled_by/answer for each -- a quick way to
sanity-check the deployed system against the assignment's baseline
queries before submitting.

Usage:
    # backend must already be running (uvicorn app.main:app ...)
    python scripts/run_eval.py [--url http://localhost:8000]
"""
import argparse
import re
import sys
import time
from pathlib import Path

import requests

# Windows consoles default to a legacy codepage (cp1252) that can't encode
# characters some models emit (e.g. U+2011 non-breaking hyphen), which would
# otherwise crash this script's own print() calls mid-run.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

QUERY_RE = re.compile(r'^\d+\.\s+"(.+)"')


def load_queries(path: Path) -> list[str]:
    queries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = QUERY_RE.match(line.strip())
        if m:
            queries.append(m.group(1))
    return queries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument(
        "--queries",
        default=str(Path(__file__).resolve().parents[2] / "eval" / "test-queries.md"),
    )
    args = parser.parse_args()

    queries = load_queries(Path(args.queries))
    if not queries:
        print(f"No queries found in {args.queries}", file=sys.stderr)
        sys.exit(1)

    print(f"Running {len(queries)} baseline queries against {args.url}/chat\n")
    passed = 0
    for q in queries:
        try:
            resp = requests.post(f"{args.url}/chat", json={"query": q}, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            print(f"Q: {q}")
            print(f"   intent={data['intent']}  handled_by={data['handled_by']}")
            print(f"   -> {data['final_answer']}")
            if data.get("rag_citations"):
                cites = "; ".join(f"{c['source']} § {c['section']}" for c in data["rag_citations"])
                print(f"   citations: {cites}")
            print()
            passed += 1
        except Exception as e:  # noqa: BLE001 -- this is a dev sanity script
            print(f"Q: {q}\n   ERROR: {e}\n")
        time.sleep(3)  # stay under Groq free-tier tokens-per-minute limits across a full run

    print(f"{passed}/{len(queries)} queries returned a response without error.")
    print("This is NOT automated grading -- eyeball each answer against eval/test-queries.md's expectations.")


if __name__ == "__main__":
    main()
