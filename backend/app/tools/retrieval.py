"""
Retrieval strategy: vectorless, reasoning-based (PageIndex-style) instead
of embedding + vector-DB similarity search.

Why vectorless here (see HLD.md for the full justification):
  - The whole knowledge base is 4 short markdown docs (~180 lines total).
    It comfortably fits in a single LLM context window, so there is
    nothing to gain from approximate nearest-neighbour search over chunk
    embeddings, and something to lose: embedding similarity is bad at
    exactly the thing this content pack tests for -- noticing that two
    *different* documents disagree on the same fact (the expense-claim
    deadline is 30 days in expense-policy.md but 45 days for onboarding
    claims in onboarding-guide.md). A reasoning-based pass that looks at
    every section can catch and flag that; top-k vector search over
    isolated chunks usually can't.
  - It also avoids standing up and paying for a vector DB (pgvector /
    Qdrant) just to index ~30 short sections, which doesn't fit well
    inside an AWS Free-Tier deployment.

The tradeoff: this approach doesn't scale to a large knowledge base
(too many tokens to pass the whole corpus to the LLM). If the KB grew
to hundreds of documents, we'd want a hybrid: cheap embedding-based
pre-filtering down to a candidate set, then this same LLM-reasoning
pass over just that candidate set (which is exactly what PageIndex
does at the section/tree-node level).
"""
import os
import re
from dataclasses import dataclass

from app.config import DOCS_DIR


@dataclass
class Chunk:
    doc: str          # source filename, used for citations
    heading: str       # section heading
    text: str          # section body


def _split_into_sections(filename: str, content: str) -> list[Chunk]:
    """Split a markdown doc into '## heading' sections (our retrieval unit)."""
    sections = re.split(r"\n(?=##\s)", content)
    chunks = []
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        lines = sec.splitlines()
        heading = lines[0].lstrip("# ").strip() if lines[0].startswith("#") else "Intro"
        chunks.append(Chunk(doc=filename, heading=heading, text=sec))
    return chunks


def load_corpus() -> list[Chunk]:
    chunks: list[Chunk] = []
    for fname in sorted(os.listdir(DOCS_DIR)):
        if not fname.endswith(".md"):
            continue
        with open(os.path.join(DOCS_DIR, fname), encoding="utf-8") as f:
            content = f.read()
        chunks.extend(_split_into_sections(fname, content))
    return chunks


def render_corpus_for_prompt(chunks: list[Chunk]) -> str:
    """Render every section, tagged with an id, for the LLM to reason over."""
    blocks = []
    for i, c in enumerate(chunks):
        blocks.append(f"[{i}] source={c.doc} | section={c.heading}\n{c.text}")
    return "\n\n---\n\n".join(blocks)


# Loaded once at import time -- the corpus is tiny and static.
CORPUS: list[Chunk] = load_corpus()
CORPUS_TEXT: str = render_corpus_for_prompt(CORPUS)
