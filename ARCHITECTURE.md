# Architecture — AI-Powered Review Discovery Engine

A phase-by-phase architecture for the system that ingests Spotify user feedback
from multiple platforms and turns it into ranked discovery problems, segments,
unmet needs, and a RAG Q&A surface — plus the forward-looking **FreshMix AI**
product agent the analysis points to.

Each phase states **the real problem it solves**, the **components**, the
**contract** (inputs → outputs), and its **tests / edge cases**.

---

## 0. The real problem

Spotify has strong recommendations, yet 18–30 daily listeners still loop the
same songs. Feedback explaining *why* is scattered across App Store, Play Store,
Reddit, the Spotify Community, and social media — messy, multilingual, noisy.

**What the system must do:** collect that feedback, clean it, classify it across
six dimensions, quantify the problems, and answer six PM questions with numbers —
reliably, cheaply, and with no single point of failure when a source or the LLM
is unavailable.

```
                          ┌──────────────────────────── FRONTEND ───────────────────────────┐
 SOURCES        BACKEND PIPELINE                                   Streamlit dashboard (app.py)
 ───────        ────────────────                                   ────────────────────────────
 App Store ─┐                                                      Reviews · Classification
 Play Store ─┤  collect ─► clean ─► analyze ─► aggregate ─► RAG    Themes · Segments · Root cause
 Reddit ─────┼─► (collectors) (cleaning) (Claude/   (dashboard) (rag)   RAG Q&A · Insights · Export
 Community ──┤                          rule-based)        │
 Social ─────┘                              │              │            ▲   exports
                                            ▼              ▼            │   ▼
                                   Agent API (Claude)   themes/scores   Excel / Google Sheet
                                   Agent Skill (taxonomy)
```

Repo: `https://github.com/vaghelapiyuah/spotify-discovery-engine` ·
Live: Streamlit Cloud.

---

## Phase 1 — Backend: data ingestion

**Problem:** five platforms, five wildly different APIs and access rules; some
free, some credential-gated, some blocked anonymously. A naive "fetch all" dies
on the first source that errors.

**Components** (`src/collectors/`)
- `Collector` (ABC) — single method `collect() -> list[RawReview]`.
- `FileCollector` — JSON file (sample data, saved fetches, uploads).
- `AppStoreCollector` — Apple iTunes RSS customer-reviews feed (no key; browser
  UA + ordered `id/page/sortBy` params required).
- `PlayStoreCollector` — `google-play-scraper` (`com.spotify.music`, no key).
- `RedditCollector` — official OAuth API (`client_credentials`); anonymous JSON
  is `403`-blocked, so needs `REDDIT_CLIENT_ID/SECRET`.
- `SocialMediaCollector` — YouTube Data API (`YOUTUBE_API_KEY`).
- `CommunityForumCollector` — Khoros is auth-gated → stub; load via export file.

**Contract**
```
collect() -> list[RawReview]    # RawReview: id, source, text, rating, date,
                                #            country, app_version, device, language
```

**Design decision — source-agnostic downstream.** Every collector emits the same
`RawReview` model (`src/models.py`), so cleaning/analysis never知道 which source
produced a row. Adding a source = one new `Collector`, zero downstream changes.

**Resilience:** `Pipeline.run()` wraps each `collect()` in try/except and *skips*
sources that fail (missing creds, network), logging the skip — one dead source
never aborts the run (`src/pipeline.py`).

**Edge cases**
| Case | Handling |
|---|---|
| Source has no credentials | Collector raises a clear `RuntimeError`; pipeline skips it |
| Apple feed returns empty for non-browser UA | Browser UA hard-coded |
| Play Store returns link-only / empty reviews | Skipped (empty text filtered) |
| Network timeout | `urlopen(timeout=30)`; failure → source skipped |
| Mixed languages | Carried through; normalized later by the agent |

---

## Phase 2 — Backend: cleaning & normalization

**Problem:** raw feedback is duplicated, spammy, terse, emoji/slang-laden, and
multilingual. Feeding it straight to the LLM wastes tokens and pollutes counts.

**Component** `src/cleaning/cleaner.py`

| Concern | Solution (deterministic, no LLM) |
|---|---|
| Duplicates | Normalized-text hash; later copies flagged `duplicate_of` |
| Spam / bots | Heuristics: URLs, promo phrases, repeated-char runs, symbol-only |
| Low-detail | Reviews `< short_review_chars` tagged `is_short` (kept, not dropped) |

Language translation, emoji/slang normalization, and *app-bug vs discovery*
classification are **deferred to the agent** (Phase 3) where context matters.

**Contract**
```
clean(list[RawReview]) -> list[CleanReview]      # adds is_short, is_spam, duplicate_of
analyzable(list[CleanReview]) -> list[CleanReview]   # drops spam + duplicates
```

**Edge cases:** emoji-only review → spam; all-duplicate batch → 1 canonical kept;
empty string → filtered. Short reviews are *tagged not dropped* (they still carry
sentiment).

---

## Phase 3 — Agent API + Agent Skill (the AI brain)

This is the heart, and maps directly to your "agent API" and "agent skill".

### 3a. Agent Skill — the structured review-analysis skill

**Problem:** the model must map free, messy text into a *fixed* taxonomy, or
aggregation is meaningless (two reviews that mean the same thing must land in the
same bucket).

The "skill" = **system prompt + controlled vocabularies + structured-output
schema** (`src/analysis/prompts.py`, `src/taxonomy.py`, `src/models.py`):
- **System prompt** instructs six analyses at once.
- **Taxonomy** (enums): `Sentiment`, `TopicCluster`, `ListeningIntent`,
  `Frustration`, `Segment`, `UnmetNeed`, `Severity`, `RootCause`.
- **Output schema** (`ReviewAnalysis` Pydantic model) — the model must return
  exactly these typed fields; values are validated against the enums.

Packaging note: this skill is portable. The same system prompt + schema can be
registered as an **Anthropic Agent Skill** (`SKILL.md` + schema) for Managed
Agents, or kept inline as it is today.

### 3b. Agent API — Claude integration

**Component** `src/analysis/analyzer.py` (`Analyzer`)
- Uses the **Anthropic Python SDK** (`client.messages.parse`) with
  `output_format=ReviewAnalysis` → validated structured output per review.
- Model: `claude-opus-4-8` (configurable; Haiku/Sonnet for volume).
- Prompt caching marker on the (stable) taxonomy system prompt.
- Parallelised across reviews with a `ThreadPoolExecutor`.
- `validate()` preflight: a 1-token call that catches an invalid key and lets the
  app fall back to offline mode instead of throwing a raw 401.
- `synthesize(aggregates)` — one run-level call (adaptive thinking) that answers
  the six PM questions + executive summary, grounded only in the aggregates.

### 3c. Offline agent — `RuleBasedAnalyzer`

**Problem:** no API key, or token budget = $0, must still produce a full report.

`src/analysis/rule_based.py` implements the **same interface** (`analyze` +
`synthesize`) with keyword rules + a data-grounded synthesis. The pipeline and
frontend are identical; only the analyzer instance differs.

**Contract (both analyzers)**
```
analyze(list[CleanReview]) -> list[AnalyzedReview]   # CleanReview + ReviewAnalysis
synthesize(dashboard: dict) -> Synthesis             # executive summary + 6 PM answers
```

**Edge cases:** model refusal / parse failure → `parsed_output is None` raises a
clear error per review; auth error → `validate()` flips to offline; one review
failing in the thread pool surfaces without corrupting others.

---

## Phase 4 — Backend: aggregation, scoring, clustering, RAG

**Problem:** per-review labels are not insight. PMs need ranked, quantified,
explainable output.

**Components**
- `src/aggregation/dashboard.py` — builds the dashboard dict:
  top complaints (% of feedback), sentiment by source, discovery issue by
  segment, unmet needs → opportunities, **root-cause taxonomy**, and
  **Opportunity Score = Frequency × Severity × Business impact → P0–P3**.
- `src/clustering/themes.py` — emergent themes via TF-IDF + KMeans (offline),
  complementing the fixed taxonomy ("what themes actually emerge here?").
- `src/rag/qa.py` — retrieval (TF-IDF cosine) + answer. With a key, Claude writes
  the answer from retrieved reviews; offline, an extractive answer is returned.

**Contract**
```
build_dashboard(list[AnalyzedReview]) -> dict           # JSON-serializable
ThemeClusterer().cluster(list[AnalyzedReview]) -> list[Theme]
answer_question(analyzed, question, client?, model?) -> {answer, sources}
```

**Edge cases:** zero discovery reviews → empty tables (no divide-by-zero, guarded
`_pct`); < 4 reviews → clustering returns a single theme; empty query → RAG
returns a helpful prompt; all-`none` frustrations → opportunity table empty.

---

## Phase 5 — Frontend (Streamlit)

**Problem:** stakeholders need to explore, filter, ask, and export — not read
JSON.

**Component** `app.py` — a single Streamlit app, 8 tabs mirroring the chain:
Reviews · Classification · Themes · Segments · Root Causes · RAG Q&A · Insights ·
Export. Sidebar selects **data source** (sample / saved / live / upload / all)
and **engine** (offline vs Claude). KPI metric row, charts (`st.bar_chart`),
filterable tables, expandable PM answers, downloads.

**Why Streamlit:** the frontend and backend are the *same* Python process — the
UI imports the pipeline directly (Phase 6). Fastest path to a deployable,
interactive PM tool with zero JS.

**Edge cases:** no run yet → guidance + `st.stop()`; invalid Claude key → warning
banner + auto-fallback; upload without file → inline error; long URLs/labels
handled by responsive columns.

---

## Phase 6 — Frontend ↔ Backend linking

**Problem:** keep the UI thin and the logic testable; never duplicate pipeline
logic in the view.

**Pattern:** the frontend calls backend modules **in-process** (no HTTP):
```
app.py
  └─ _load_raw(source)        -> collectors.collect()
  └─ run_pipeline(raw, analyzer)
       ├─ Cleaner().clean / analyzable          (src.cleaning)
       ├─ analyzer.analyze                       (src.analysis: Claude OR rule-based)
       ├─ build_dashboard                        (src.aggregation)
       ├─ analyzer.synthesize                    (src.analysis)
       └─ ThemeClusterer().cluster               (src.clustering)
  └─ answer_question(...)      (src.rag, on demand in the RAG tab)
  └─ to_excel_bytes / export_to_google_sheet     (src.export)
```
- **Dependency injection:** `Pipeline(config, analyzer=...)` and
  `run_pipeline(raw, analyzer)` accept the analyzer, so the UI (and tests) choose
  Claude vs offline without touching pipeline code.
- **State:** results cached in `st.session_state` so RAG/filter interactions
  don't recompute the whole pipeline.
- **Serialization boundary:** every backend output is JSON-safe
  (`model_dump(mode="json")`) so it crosses to the UI, exports, and the wire
  identically.

**Decoupled alternative (for scale):** wrap `run_pipeline` behind a FastAPI
service (`POST /analyze`, `POST /ask`) returning the same JSON; the Streamlit (or
any) frontend then calls it over HTTP. The contracts above are already the API
shape — only the transport changes.

---

## Phase 7 — Export (analysis out)

**Problem:** PMs live in spreadsheets; insights must leave the app.

**Component** `src/export/sheets.py`
- `to_excel_bytes(frames)` — multi-tab `.xlsx` in memory (zero setup).
- `export_to_google_sheet(frames, creds, title, share_email)` — live Google Sheet
  via `gspread` + service account; one tab per table; link-shareable.

**Edge cases:** no Google creds → Excel still works, UI explains setup; tab-name
sanitization (Excel/Sheets forbidden chars, 31-char cap, uniqueness); empty
frame → "no data" sheet.

---

## Phase 8 — Deployment (frontend + backend)

Because Streamlit is monolithic, **frontend and backend deploy together** today;
a split path is documented for scale.

### 8a. Current — single deploy (Streamlit Community Cloud)
- **Build:** `requirements.txt` (anthropic, pydantic, streamlit, scikit-learn,
  pandas, google-play-scraper, gspread, google-auth, openpyxl, reportlab).
- **Config:** `.streamlit/config.toml` (headless, CORS/XSRF off for proxying);
  `.devcontainer/` for Codespaces.
- **Deploy:** push to GitHub `main` → Streamlit Cloud auto-builds `app.py` →
  permanent `https://<app>.streamlit.app`. Auto-redeploys on every push.
- **Secrets:** `ANTHROPIC_API_KEY`, `REDDIT_CLIENT_ID/SECRET`, `YOUTUBE_API_KEY`,
  `[gcp_service_account]` set in the app's Secrets (never in git; `.env` is
  gitignored).
- **Frontend-only quick share:** `cloudflared tunnel --url localhost:8501` for an
  instant temporary URL during dev.

### 8b. Scale path — split deploy
- **Backend:** containerize the pipeline behind FastAPI (`Dockerfile`,
  `uvicorn`), deploy to Render / Fly / Cloud Run; horizontal scale by review
  volume; long jobs via the Anthropic **Batches API** (50% cost) or a queue.
- **Frontend:** keep Streamlit (or a static SPA) calling the backend over HTTPS;
  deploy separately; CORS allow-list the frontend origin.
- **Agent path:** elevate the inline Claude calls to **Managed Agents** — the
  Agent Skill (Phase 3a) registered once, sessions per analysis run, server-side
  tool execution and compaction.

**Edge cases:** cold-start cache miss (prompt caching mitigates); datacenter IPs
blocked by Apple/Reddit (use the credentialed collectors); secret missing in prod
→ app degrades to offline mode, never crashes.

---

## Phase 9 — Test cases

**Component** `tests/` (`pytest` or `python tests/test_offline.py`) with a
`StubAnalyzer` (= the real `RuleBasedAnalyzer`) so the full pipeline is tested
**offline, zero tokens**.

### Implemented
| Test | Input | Expected |
|---|---|---|
| `test_cleaner_flags_dup_spam_short` | 8 reviews incl. dup/spam/short | dup→`duplicate_of`, spam→`is_spam`, "ok"→`is_short`; analyzable excludes dup+spam |
| `test_build_dashboard_scoring` | analyzed sample | app-bug split out; opportunity scores ranked desc; every row P0–P3 + score > 0; JSON-serializable; sentiment % in 0–100 |
| `test_pipeline_end_to_end_offline` | MockCollector + StubAnalyzer | raw count, dup/spam counts, 6 PM answers, full result JSON-serializes |

### Recommended additions (same patterns)
| Area | Case |
|---|---|
| Collectors | `FileCollector` parses/auto-IDs; gated collectors raise clear errors w/o creds |
| Analyzer | mock Anthropic client → `analyze` maps to schema; `validate()` returns `(False, …)` on 401 |
| Clustering | < 4 reviews → single theme; keywords non-empty on real text |
| RAG | known query retrieves expected review; empty query → guidance |
| Export | `to_excel_bytes` opens as valid workbook with expected tabs |
| Aggregation | root-cause mapping (frustration→cause, topic fallback) |

---

## Phase 10 — Edge cases & resilience (cross-cutting)

| Class | Edge case | Handling |
|---|---|---|
| Data | Empty / zero reviews | Guarded `_pct`; empty tables; UI shows guidance |
| Data | All spam or all duplicates | Filtered; analyzable may be empty → handled |
| Data | Non-English / emoji / slang | Agent normalizes to `normalized_summary`; offline keeps raw |
| Data | App-bug vs discovery | `is_app_bug` splits them; bugs excluded from discovery % |
| Source | One source down / no creds | Skipped per-collector; run continues |
| Source | Apple/Reddit block | Browser UA / OAuth; documented |
| LLM | Invalid/missing key | `validate()` → offline fallback + banner |
| LLM | Refusal / parse fail | Per-review error surfaced; not silent |
| LLM | Rate limit / 5xx | SDK auto-retries w/ backoff |
| Scale | Thousands of reviews | Thread pool + prompt caching; Batches API for split deploy |
| Output | Floats / enums in JSON | `mode="json"`, `Math.round`-equivalent rounding |
| Deploy | Secret absent in prod | Degrades to offline, never crashes |

---

## File map (where each phase lives)

```
config.py                     # model, workers, env
app.py                        # Phase 5/6 frontend + linking
src/
  models.py                   # Phase 1/3 schemas (RawReview … Synthesis)
  taxonomy.py                 # Phase 3a agent skill vocab + scoring weights
  collectors/                 # Phase 1 ingestion
  cleaning/                   # Phase 2 cleaning
  analysis/                   # Phase 3 agent API (analyzer) + skill (prompts) + offline
  aggregation/                # Phase 4 dashboard + scoring + root causes
  clustering/                 # Phase 4 emergent themes
  rag/                        # Phase 4 RAG Q&A
  export/                     # Phase 7 Excel + Google Sheet
  pipeline.py                 # orchestration (collect→clean→analyze→aggregate→synth)
tests/                        # Phase 9 offline tests
.streamlit/ , .devcontainer/  # Phase 8 deployment config
slides/                       # decks (insights, 08, 09, 10)
```
