"""Retrieval-augmented Q&A over analyzed reviews.

retrieve()  -> TF-IDF cosine similarity, returns the most relevant reviews.
answer_question() -> grounds an answer in those reviews. Uses Claude when a key
is available; otherwise returns an extractive answer (relevant snippets + a
quick breakdown of their frustrations/segments/needs) so RAG works offline too.
"""

from __future__ import annotations

from collections import Counter

from ..models import AnalyzedReview


def _docs(analyzed: list[AnalyzedReview]) -> list[str]:
    return [
        f"{a.analysis.normalized_summary or ''} {a.review.raw.text or ''}".strip()
        for a in analyzed
    ]


def retrieve(
    analyzed: list[AnalyzedReview], question: str, k: int = 6
) -> list[tuple[float, AnalyzedReview]]:
    """Return up to k (score, review) pairs most relevant to the question."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel

    docs = _docs(analyzed)
    if not any(docs) or not question.strip():
        return []

    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    matrix = vectorizer.fit_transform(docs + [question])
    sims = linear_kernel(matrix[-1], matrix[:-1]).flatten()
    ranked = sims.argsort()[::-1][:k]
    return [(float(sims[i]), analyzed[i]) for i in ranked if sims[i] > 0]


def _extractive_answer(question: str, hits: list[tuple[float, AnalyzedReview]]) -> str:
    if not hits:
        return ("No relevant reviews found for that question. Try different "
                "keywords (e.g. 'mood', 'repetitive', 'playlist', 'skip').")

    frustrations = Counter(h.analysis.frustration.value for _, h in hits)
    segments = Counter(h.analysis.segment.value for _, h in hits)
    needs = Counter(
        h.analysis.unmet_need.value for _, h in hits
        if h.analysis.unmet_need.value != "none"
    )

    lines = [
        f"Based on {len(hits)} relevant reviews:",
        f"  Most common frustration: {frustrations.most_common(1)[0][0]}",
        f"  Most common segment: {segments.most_common(1)[0][0]}",
    ]
    if needs:
        lines.append(f"  Top unmet need: {needs.most_common(1)[0][0]}")
    lines.append("\nRepresentative reviews:")
    for score, h in hits[:4]:
        src = h.review.raw.source.value
        summary = h.analysis.normalized_summary or h.review.raw.text
        lines.append(f"  - [{src}] {summary[:160]}")
    return "\n".join(lines)


def _llm_answer(question, hits, client, model) -> str:
    context = "\n".join(
        f"[{i+1}] ({h.review.raw.source.value}) "
        f"{h.analysis.normalized_summary or h.review.raw.text}"
        for i, (_, h) in enumerate(hits)
    )
    prompt = (
        "You are a Spotify product analyst. Answer the question using ONLY the "
        "reviews below. Cite review numbers like [1]. If they don't address it, "
        "say so.\n\n"
        f"REVIEWS:\n{context}\n\nQUESTION: {question}"
    )
    resp = client.messages.create(
        model=model,
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in resp.content if b.type == "text")


def answer_question(
    analyzed: list[AnalyzedReview],
    question: str,
    k: int = 6,
    client=None,
    model: str | None = None,
) -> dict:
    """Answer a question over the reviews. Returns {answer, sources}.

    If `client` (an anthropic.Anthropic) and `model` are given, Claude writes the
    answer from retrieved context; otherwise an extractive answer is returned.
    """
    hits = retrieve(analyzed, question, k=k)

    if client is not None and model and hits:
        try:
            answer = _llm_answer(question, hits, client, model)
        except Exception as e:  # fall back gracefully
            answer = (
                f"(LLM answer failed: {e}; showing retrieved evidence)\n\n"
                + _extractive_answer(question, hits)
            )
    else:
        answer = _extractive_answer(question, hits)

    sources = [
        {
            "score": round(score, 3),
            "source": h.review.raw.source.value,
            "rating": h.review.raw.rating,
            "frustration": h.analysis.frustration.value,
            "segment": h.analysis.segment.value,
            "text": h.analysis.normalized_summary or h.review.raw.text,
        }
        for score, h in hits
    ]
    return {"answer": answer, "sources": sources}
