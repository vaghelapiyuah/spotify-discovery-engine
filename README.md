# AI-Powered Review Discovery Engine for Spotify

An LLM-powered feedback intelligence system that analyzes reviews, discussions, and
social conversations to identify **why Spotify users repeat familiar music** and
**what product opportunities** can make discovery feel fresh, easy, and trusted.

The AI analysis layer is powered by the **Claude API** (Anthropic).

## What it does

For every piece of feedback, the engine runs **six analyses at once** (one
structured Claude call per review) and maps each into a fixed taxonomy:

| # | Analysis        | Output |
|---|-----------------|--------|
| A | Sentiment       | positive / neutral / negative / mixed |
| B | Topic cluster   | repetitive recs, weak genre exploration, poor mood understanding, … |
| C | Listening intent| activity / mood / similar-but-fresh / deep / low-effort / social |
| D | Frustration     | same songs, same artists, bad recs, too many skips, wrong mood, … |
| E | Segment         | habitual repeaters, mood listeners, social listeners, genre explorers, … |
| F | Unmet need      | fresh-but-familiar, better control, mood-aware, social proof, … |

It then aggregates the results into a dashboard, scores opportunities
(`Frequency × Severity × Business impact → P0–P3`), and makes one final Claude
call to synthesize an **executive summary** and answers to the six PM questions.

## Architecture

```
collect ─▶ clean ─▶ analyze (Claude) ─▶ aggregate + score ─▶ synthesize (Claude) ─▶ report
```

```
Engine/
├── run.py                     # CLI entry point + console report
├── config.py                  # model / workers, reads .env
├── app.py                     # Streamlit dashboard (the full chain, interactive)
├── data/sample_reviews.json   # 18 sample reviews (5 sources, multi-language)
├── tests/                     # offline tests + StubAnalyzer (no API tokens)
└── src/
    ├── taxonomy.py            # controlled vocabularies + scoring weights
    ├── models.py              # Pydantic schemas (RawReview … Synthesis)
    ├── collectors/            # File + live App Store/Play Store + source stubs
    ├── cleaning/              # dedup, spam filter, low-detail tagging
    ├── analysis/              # Claude + rule-based analyzers, prompts, synthesis
    ├── clustering/            # emergent theme clustering (TF-IDF + KMeans)
    ├── rag/                   # RAG Q&A over the reviews (retrieval + answer)
    ├── aggregation/           # dashboard tables + opportunity scoring
    └── pipeline.py            # end-to-end orchestration
```

Why fixed enums? Two reviews that *mean* the same thing land in the same bucket,
which is what makes counting, ranking, and scoring meaningful. The LLM maps free
text into the taxonomy; aggregation is then plain arithmetic.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env          # then add your ANTHROPIC_API_KEY
```

## Run

```bash
python run.py                            # analyze data/sample_reviews.json
python run.py --input my_reviews.json    # your own reviews
python run.py --model claude-haiku-4-5   # cheaper, for high-volume runs
```

Output: a console report plus `output/discovery_report.json` containing the
per-review classifications, dashboard, opportunity scores, and synthesis.

### Offline mode (no API key, no tokens)

Don't have an Anthropic key? Run the whole pipeline with the built-in rule-based
analyzer. Cleaning, the six analyses, the dashboard, opportunity scoring, and a
data-grounded synthesis all run on real reviews — classifications are coarser
than the LLM's, but it's a complete, free end-to-end report.

```bash
python run.py --input data/spotify_live.json --offline
```

Add a key later (`.env`) and drop `--offline` for the full LLM-quality analysis.

## Dashboard (Streamlit)

An interactive dashboard walks the whole chain:
**Reviews → AI classification → Theme clustering → Segment tagging → RAG Q&A → Insights.**

```bash
streamlit run app.py
```

Tabs: a filterable **Reviews** table, **AI Classification** distribution charts,
emergent **Themes** (TF-IDF + KMeans), **Segment** tagging, a **RAG Q&A** box
(ask the reviews in natural language), and an **Insights** dashboard (top
complaints, opportunity scores, unmet needs, executive summary, PM answers,
JSON download). Pick the data source and engine (Offline or Claude) in the
sidebar. Works fully offline; add a key for LLM-quality classification and
LLM-written RAG answers.

### Share a public URL (any device)

**Permanent (recommended):** push this repo to GitHub and deploy free on
[Streamlit Community Cloud](https://share.streamlit.io) — set the main file to
`app.py`. You get a stable `https://<app>.streamlit.app` URL for everyone.
Add `ANTHROPIC_API_KEY` under the app's *Secrets* if you want Claude mode.

**Instant / temporary:** expose the local server with a tunnel (no account):

```bash
streamlit run app.py            # terminal 1
cloudflared tunnel --url http://localhost:8501   # terminal 2 -> prints a public https URL
```

The tunnel URL works on any device but only while your machine and both
processes stay running.

## Pull live Spotify reviews

The App Store and Play Store collectors fetch **real Spotify reviews** with no
API key (App Store uses Apple's public RSS feed; Play Store uses
`google-play-scraper`).

```bash
# Fetch + analyze live reviews
python run.py --source appstore --count 100
python run.py --source playstore --country us --lang en --count 200
python run.py --source both

# Fetch only — save Spotify reviews to a file, no Claude tokens spent
python run.py --source both --fetch-only --save-input data/spotify_live.json
# ...then analyze whenever you want:
python run.py --input data/spotify_live.json
```

| Flag | Meaning |
|------|---------|
| `--source` | `file` (default) · `appstore` · `playstore` · `both` |
| `--country` | country code(s); comma-separated for App Store (default `us`) |
| `--lang` | Play Store review language (default `en`) |
| `--count` | Play Store reviews to fetch (default 200) |
| `--pages` | App Store RSS pages/country, ~50 each (default 5) |
| `--fetch-only` | collect only, no analysis |
| `--save-input` | with `--fetch-only`, write collected reviews to JSON |

Spotify is pre-configured (App Store id `324684580`, package `com.spotify.music`).

## Tests (offline — no API tokens)

A `StubAnalyzer` mimics the Claude analysis layer with keyword rules, so the
cleaning, aggregation, scoring, and pipeline wiring can be validated for free.

```bash
pytest                       # or, with no pytest installed:
python tests/test_offline.py
```

### Input format

A JSON list of objects; `source` and `text` are required, the rest optional:

```json
[
  {
    "source": "app_store",
    "text": "Discover Weekly feels random now.",
    "rating": 2,
    "date": "2026-05-02",
    "country": "US",
    "app_version": "8.9.30"
  }
]
```

`source` must be one of: `app_store`, `play_store`, `reddit`,
`community_forum`, `social_media`.

## Model & cost notes

- Defaults to **`claude-opus-4-8`** (most capable). Override with
  `ANTHROPIC_MODEL` or `--model` — `claude-haiku-4-5` is a good high-volume choice.
- The taxonomy system prompt is marked for **prompt caching** (`cache_control`).
  It's identical across every review in a run, so once the prompt exceeds the
  model's cache minimum (e.g. as you extend the taxonomy), only the short review
  text is billed at full input price; below the minimum the marker is a harmless
  no-op.
- Per-review analyses run in parallel (`ENGINE_WORKERS`, default 6).

## Connecting live sources

`src/collectors/live_sources.py` contains documented stubs for App Store, Play
Store, Reddit, Spotify Community, and social media. Implement `collect()` to
return `RawReview` objects and pass the collector to the pipeline — every layer
downstream is source-agnostic.
