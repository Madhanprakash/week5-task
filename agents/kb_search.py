"""Keyword search over the knowledge_base/ markdown files.

Kept free of AutoGen imports so it can be tested on its own.
"""
import re
from pathlib import Path

KB_DIR = Path(__file__).resolve().parent.parent / "knowledge_base"

# Words that carry no meaning for matching, including generic store words
# ("company", "customer") that would match almost every complaint.
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "is", "are", "was", "were", "be", "been",
    "do", "does", "did", "you", "your", "we", "our", "i", "me", "my", "it", "its",
    "to", "of", "in", "on", "at", "for", "with", "from", "this", "that", "there",
    "what", "how", "can", "get", "want", "need", "please", "hi", "hello", "thanks",
    "thank", "sorry", "not", "no", "yes", "so", "if", "as", "by", "just", "then",
    "than", "will", "would", "could", "should", "have", "has", "had", "t",
    "company", "store", "business", "customer", "sell", "sells", "selling",
}


def _stem(word: str) -> str:
    """Very small stemmer: enough to match 'arrives'/'arrive', 'refunds'/'refund'."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    if len(word) > 4 and word.endswith("ed"):
        return word[:-2]
    return word


def _terms(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {_stem(w) for w in words if w not in STOPWORDS and len(w) > 1}


def _load_sections():
    """Split every .md file into sections ('## heading' blocks)."""
    sections = []
    for path in sorted(KB_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for chunk in re.split(r"(?m)^## ", text)[1:]:
            heading, _, body = chunk.partition("\n")
            sections.append({
                "file": path.name,
                "heading": heading.strip(),
                "text": body.strip(),
            })
    return sections


def search(query: str, max_results: int = 3) -> list[dict]:
    """Return the sections that best match the query.

    A section must share at least two meaningful words with the query
    (or every word, if the query has only one) to count as a match.
    """
    query_terms = _terms(query)
    if not query_terms:
        return []
    min_hits = min(2, len(query_terms))

    scored = []
    for section in _load_sections():
        section_terms = _terms(section["heading"] + " " + section["text"])
        hits = query_terms & section_terms
        if len(hits) >= min_hits:
            scored.append((len(hits), section))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [section for _, section in scored[:max_results]]


def search_kb(query: str) -> str:
    """Search the company knowledge base (shipping, refunds, accounts and product FAQ).

    Use a short query made of the key problem words, for example
    'order late delivery' or 'refund window return'. Returns the matching
    passages with the file name each one came from, or NO_MATCH.
    """
    results = search(query)
    if not results:
        return "NO_MATCH: No knowledge base passage matches this query."
    parts = []
    for r in results:
        parts.append(f"[FILE: {r['file']} | SECTION: {r['heading']}]\n{r['text']}")
    return "\n\n".join(parts)
