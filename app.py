"""Streamlit dashboard for the Spotify Review Discovery Engine.

Flow: Reviews -> AI classification -> Theme clustering -> Segment tagging
      -> Root causes -> RAG Q&A -> Insights

Run locally:   streamlit run app.py
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st

from config import CONFIG
from src.aggregation import build_dashboard
from src.analysis import Analyzer, RuleBasedAnalyzer
from src.cleaning import Cleaner
from src.clustering import ThemeClusterer
from src.collectors import AppStoreCollector, FileCollector, PlayStoreCollector
from src.models import RawReview

st.set_page_config(page_title="Spotify Discovery Engine", page_icon="🎧", layout="wide")

DATA_DIR = Path("data")

OBJECTIVE = (
    "Spotify has a strong recommendation system, but many users still listen to "
    "the same songs, artists, and playlists repeatedly. This engine analyzes user "
    "feedback from multiple sources to identify **why music discovery still feels "
    "difficult, risky, boring, repetitive, or low-effort** — what users *say*, what "
    "they *feel*, and which discovery problems repeat across platforms."
)


# --------------------------------------------------------------------------- #
# Pipeline helpers
# --------------------------------------------------------------------------- #

def _load_raw(source: str, **kw) -> list[RawReview]:
    if source == "Sample (bundled)":
        return FileCollector(DATA_DIR / "sample_reviews.json").collect()
    if source == "Saved: App Store (data/spotify_live.json)":
        return FileCollector(DATA_DIR / "spotify_live.json").collect()
    if source == "Saved: Play Store (data/spotify_play.json)":
        return FileCollector(DATA_DIR / "spotify_play.json").collect()
    if source == "Live: App Store":
        return AppStoreCollector(
            countries=[kw.get("country", "us")], max_pages=kw.get("pages", 3)
        ).collect()
    if source == "Live: Play Store":
        return PlayStoreCollector(
            country=kw.get("country", "us"),
            lang=kw.get("lang", "en"),
            count=kw.get("count", 150),
        ).collect()
    if source == "Upload JSON":
        records = json.loads(kw["uploaded"].decode("utf-8"))
        for i, r in enumerate(records):
            r.setdefault("id", f"{r.get('source','src')}-{i:04d}")
        return [RawReview.model_validate(r) for r in records]
    raise ValueError(source)


def run_pipeline(raw: list[RawReview], analyzer) -> dict:
    cleaner = Cleaner(short_review_chars=CONFIG.short_review_chars)
    cleaned = cleaner.clean(raw)
    analyzable = Cleaner.analyzable(cleaned)
    analyzed = analyzer.analyze(analyzable)
    dashboard = build_dashboard(analyzed)
    synthesis = analyzer.synthesize(dashboard)
    themes = ThemeClusterer().cluster(analyzed)
    return {
        "raw_count": len(raw),
        "dup": sum(1 for c in cleaned if c.duplicate_of is not None),
        "spam": sum(1 for c in cleaned if c.is_spam),
        "short": sum(1 for c in cleaned if c.is_short),
        "analyzed": analyzed,
        "dashboard": dashboard,
        "synthesis": synthesis,
        "themes": themes,
        "used_llm": isinstance(analyzer, Analyzer),
    }


def _bar(counter: dict, name: str, value_label: str = "count"):
    if not counter:
        st.info("No data.")
        return
    df = pd.DataFrame(
        {name: list(counter.keys()), value_label: list(counter.values())}
    ).set_index(name)
    st.bar_chart(df)


def _pct_bar(rows: list[dict], label_key: str, pct_key: str):
    if not rows:
        st.info("No data.")
        return
    df = pd.DataFrame(
        {r[label_key]: r[pct_key] for r in rows}.items(), columns=["item", "%"]
    ).set_index("item")
    st.bar_chart(df, horizontal=True)


# --------------------------------------------------------------------------- #
# Sidebar — controls
# --------------------------------------------------------------------------- #

st.sidebar.title("🎧 Discovery Engine")
st.sidebar.caption("Spotify review intelligence")

source_options = ["Sample (bundled)"]
if (DATA_DIR / "spotify_live.json").exists():
    source_options.append("Saved: App Store (data/spotify_live.json)")
if (DATA_DIR / "spotify_play.json").exists():
    source_options.append("Saved: Play Store (data/spotify_play.json)")
source_options += ["Live: App Store", "Live: Play Store", "Upload JSON"]

source = st.sidebar.selectbox("Data source", source_options)

kw: dict = {}
if source in ("Live: App Store", "Live: Play Store"):
    kw["country"] = st.sidebar.text_input("Country", "us")
if source == "Live: App Store":
    kw["pages"] = st.sidebar.slider("Pages (~50 reviews each)", 1, 10, 3)
if source == "Live: Play Store":
    kw["lang"] = st.sidebar.text_input("Language", "en")
    kw["count"] = st.sidebar.slider("Review count", 50, 500, 150, step=50)
if source == "Upload JSON":
    up = st.sidebar.file_uploader("Reviews JSON", type="json")
    kw["uploaded"] = up.getvalue() if up else None

has_key = CONFIG.has_api_key
mode = st.sidebar.radio(
    "Analysis engine",
    ["Offline (rule-based, no key)", "Claude (LLM)"],
    help="Claude needs a valid ANTHROPIC_API_KEY. Falls back to offline if invalid.",
)
want_llm = mode.startswith("Claude")
if want_llm and not has_key:
    st.sidebar.info("No ANTHROPIC_API_KEY set — will run offline.")

run = st.sidebar.button("▶ Run analysis", type="primary", use_container_width=True)
st.sidebar.caption(f"Model: `{CONFIG.model}`")

if run:
    if source == "Upload JSON" and not kw.get("uploaded"):
        st.sidebar.error("Please upload a JSON file first.")
    else:
        note = None
        analyzer = RuleBasedAnalyzer()
        if want_llm and has_key:
            with st.spinner("Validating Claude API key..."):
                candidate = Analyzer(model=CONFIG.model, workers=CONFIG.workers)
                ok, msg = candidate.validate()
            if ok:
                analyzer = candidate
            else:
                note = f"Claude unavailable ({msg}) Falling back to offline mode."
        try:
            with st.spinner("Collecting + analyzing reviews..."):
                raw = _load_raw(source, **kw)
                st.session_state["results"] = run_pipeline(raw, analyzer)
                st.session_state["source_label"] = source
                st.session_state["note"] = note
        except Exception as e:
            st.sidebar.error(f"Failed: {e}")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

st.title("🎧 Spotify Discovery — Review Intelligence")
st.caption(
    "Reviews → AI classification → Theme clustering → Segment tagging → "
    "Root causes → RAG Q&A → Insights"
)

with st.expander("ℹ️ About this engine (objective, sources, method)"):
    st.markdown("**Objective**")
    st.markdown(OBJECTIVE)
    st.markdown(
        "**Six AI analyses per review:** sentiment · topic cluster · listening "
        "intent · frustration · segment · unmet need.\n\n"
        "**Sources:** App Store, Play Store, Reddit, Spotify Community, social "
        "media (App Store + Play Store live; others via file/stub).\n\n"
        "**Cleaning:** duplicate removal, spam filtering, low-detail tagging; the "
        "AI layer normalizes language/emoji and separates app-bugs from discovery "
        "issues."
    )

if "results" not in st.session_state:
    st.info(
        "Pick a data source in the sidebar and click **Run analysis**. "
        "Offline mode needs no API key. Try the saved App Store / Play Store "
        "datasets for an instant demo."
    )
    st.stop()

R = st.session_state["results"]
analyzed = R["analyzed"]
dash = R["dashboard"]
syn = R["synthesis"]
engine = "Claude (LLM)" if R["used_llm"] else "Offline (rule-based)"

if st.session_state.get("note"):
    st.warning(st.session_state["note"])

st.markdown(f"> **Main problem:** {dash['main_problem']}")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Source", st.session_state.get("source_label", "—").split(":")[0])
c2.metric("Reviews", R["raw_count"])
c3.metric("Discovery / Bug", f"{dash['totals']['discovery_reviews']} / "
                              f"{dash['totals']['app_bug_reviews']}")
c4.metric("Cleaned out", R["dup"] + R["spam"])
c5.metric("Engine", engine)

tabs = st.tabs(
    ["📋 Reviews", "🧠 Classification", "🧩 Themes", "👥 Segments",
     "🧭 Root Causes", "💬 RAG Q&A", "📊 Insights"]
)

# --- 1. Reviews -------------------------------------------------------------
with tabs[0]:
    st.subheader("Reviews + AI classification")
    rows = [
        {
            "source": a.review.raw.source.value,
            "rating": a.review.raw.rating,
            "sentiment": a.analysis.sentiment.value,
            "frustration": a.analysis.frustration.value,
            "segment": a.analysis.segment.value,
            "topic": a.analysis.topic_cluster.value,
            "intent": a.analysis.listening_intent.value,
            "unmet_need": a.analysis.unmet_need.value,
            "app_bug": a.analysis.is_app_bug,
            "summary": a.analysis.normalized_summary,
        }
        for a in analyzed
    ]
    df = pd.DataFrame(rows)
    f1, f2 = st.columns(2)
    sources = f1.multiselect("Filter source", sorted(df["source"].unique()))
    frus = f2.multiselect("Filter frustration", sorted(df["frustration"].unique()))
    if sources:
        df = df[df["source"].isin(sources)]
    if frus:
        df = df[df["frustration"].isin(frus)]
    st.dataframe(df, use_container_width=True, height=460)

# --- 2. Classification ------------------------------------------------------
with tabs[1]:
    st.subheader("Classification distributions")
    a1, a2 = st.columns(2)
    with a1:
        st.caption("Sentiment")
        _bar(Counter(a.analysis.sentiment.value for a in analyzed), "sentiment")
        st.caption("Frustration")
        _bar(Counter(a.analysis.frustration.value for a in analyzed), "frustration")
    with a2:
        st.caption("Topic cluster")
        _bar(dash["distributions"]["topic_cluster"], "topic")
        st.caption("Listening intent")
        _bar(dash["distributions"]["listening_intent"], "intent")

# --- 3. Themes --------------------------------------------------------------
with tabs[2]:
    st.subheader("Emergent themes (TF-IDF + KMeans clustering)")
    st.caption("Complements the fixed taxonomy: what themes actually emerge here?")
    themes = R["themes"]
    if not themes:
        st.info("Not enough reviews to cluster.")
    for t in themes:
        with st.expander(f"🧩 {t.label}  —  {t.size} reviews"):
            st.write(f"**Keywords:** {', '.join(t.keywords) or '—'}")
            st.write(
                f"**Dominant topic:** {t.dominant_topic}  ·  "
                f"**Dominant segment:** {t.dominant_segment}"
            )
            for s in t.sample_summaries:
                st.write(f"- {s}")

# --- 4. Segments ------------------------------------------------------------
with tabs[3]:
    st.subheader("Segment tagging (18–30 daily listeners)")
    _bar(dash["distributions"]["segment"], "segment")
    st.caption("Main discovery issue per segment")
    seg_rows = [
        {"segment": s, "count": v["count"], "main_issue": v["main_issue"],
         "top_unmet_need": v["top_unmet_need"]}
        for s, v in dash["discovery_issue_by_segment"].items()
    ]
    st.dataframe(pd.DataFrame(seg_rows), use_container_width=True, hide_index=True)

# --- 5. Root Causes ---------------------------------------------------------
with tabs[4]:
    st.subheader("Discovery problem taxonomy — root causes")
    st.markdown(f"> **{dash['main_problem']}**")
    rc = dash["root_causes"]
    if not rc:
        st.info("No discovery problems detected in this batch.")
    else:
        _pct_bar(rc, "root_cause", "pct")
        st.dataframe(
            pd.DataFrame(
                [{"root_cause": r["root_cause"], "count": r["count"],
                  "% of problems": r["pct"], "explanation": r["explanation"]}
                 for r in rc]
            ),
            use_container_width=True, hide_index=True,
        )

# --- 6. RAG Q&A -------------------------------------------------------------
with tabs[5]:
    st.subheader("Ask the reviews (RAG)")
    st.caption(
        "Retrieves the most relevant reviews and answers from them. "
        + ("Claude writes the answer." if R["used_llm"] else
           "Offline: extractive answer from retrieved reviews.")
    )
    q = st.text_input("Question", placeholder="Why does discovery feel repetitive?")
    ex = st.selectbox("…or pick an example", [
        "", "What do users say about Discover Weekly?",
        "Why does discovery feel repetitive?",
        "What do mood-based listeners want?",
        "What playlist problems are reported?",
    ])
    question = q or ex
    if question:
        from src.rag import answer_question
        client = None
        if R["used_llm"] and has_key:
            import anthropic
            client = anthropic.Anthropic()
        with st.spinner("Retrieving + answering..."):
            res = answer_question(
                analyzed, question,
                client=client, model=CONFIG.model if client else None,
            )
        st.markdown("**Answer**")
        st.write(res["answer"])
        if res["sources"]:
            st.markdown("**Retrieved reviews**")
            st.dataframe(pd.DataFrame(res["sources"]), use_container_width=True,
                         hide_index=True)

# --- 7. Insights ------------------------------------------------------------
with tabs[6]:
    st.subheader("Insights dashboard")

    st.markdown("#### AI-generated insight")
    st.success(syn.executive_summary)

    i1, i2 = st.columns(2)
    with i1:
        st.caption("Top discovery complaints (% of feedback)")
        _pct_bar(dash["top_discovery_complaints"], "frustration", "pct_of_feedback")
        st.dataframe(pd.DataFrame(dash["top_discovery_complaints"]),
                     use_container_width=True, hide_index=True)
        st.caption("Sentiment by source (%)")
        sent = pd.DataFrame(
            [{"source": s, "positive": v["positive"], "negative": v["negative"],
              "neutral": v["neutral"], "mixed": v["mixed"]}
             for s, v in dash["sentiment_by_source"].items()]
        ).set_index("source")
        st.bar_chart(sent)
    with i2:
        st.caption("Opportunity scores (Freq × Severity × Impact → P0–P3)")
        st.dataframe(pd.DataFrame(dash["opportunity_scores"]),
                     use_container_width=True, hide_index=True)
        st.caption("Unmet needs → product opportunities")
        st.dataframe(pd.DataFrame(dash["unmet_needs"]),
                     use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### PM questions")
    for qa in syn.pm_answers:
        with st.expander(qa.question):
            st.write(qa.answer)

    st.markdown("#### Final product insight")
    st.info(syn.final_product_insight)

    st.download_button(
        "⬇ Download full JSON report",
        data=json.dumps(
            {
                "dashboard": dash,
                "synthesis": syn.model_dump(mode="json"),
                "themes": [t.to_dict() for t in R["themes"]],
            },
            indent=2,
        ),
        file_name="discovery_report.json",
        mime="application/json",
    )
