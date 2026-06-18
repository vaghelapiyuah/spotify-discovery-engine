# FreshMix AI — Solution Architecture (phase by phase)

The **solution** to the discovery problem, built on evidence from the deployed
Review Discovery Engine. FreshMix AI turns mood, activity, language, and a
freshness control into a *fresh-but-familiar* queue the user can trust.

**Data source (the proof + the fuel):**
`https://spotify-discovery-engine-cgdz6f8vcaxrmskv6gbtze.streamlit.app/`
The engine analyzed 186 real App Store + Play Store reviews. Its output both
**justifies** FreshMix's design and **feeds** its RAG layer (avoid the exact pain
points users complain about).

| Evidence from the engine | FreshMix design decision |
|---|---|
| "Bad recommendations" = #1 frustration (10.1%, P0 score 108) | Rationale + feedback loop to raise relevance |
| Low trust = **58%** of root causes | "Why this song" explanation on every track |
| Context mismatch = **16%** of root causes | Mood + activity + language inputs |
| Want **control over freshness** (7.8%) | Familiar↔Fresh slider (default 70%) |
| **Fresh-but-familiar** unmet need (5.6%) + repetitive theme (11.2%) | Core "fresh-but-familiar" generation + anti-repeat filter |

```
 Discovery Engine (deployed)         FreshMix AI (this solution)
 ─────────────────────────          ───────────────────────────
 reviews → insights/RAG corpus ───►  Backend services ──► Agent (Claude) ──► queue
       (pain points, segments)         ▲        │                              │
                                       │        ▼                              ▼
                                  Spotify API   Frontend (mobile feature) ◄── "why this song"
                                                save / skip / refresh ──► feedback ──► loop
```

---

## Phase 1 — Frontend

**Problem it solves:** discovery is hidden and effortful; users want to *steer* it
in one screen (engine: effort + control + context themes).

**Surface:** a Spotify in-app feature screen, **FreshMix AI** (see wireframe).
Build target: React Native / Flutter for the app; the **Streamlit dashboard is
the analyst/PM frontend** that already ships in this repo (`app.py`).

**Screen anatomy (states, not just layout)**
- **Prompt box** — free-text intent: *"Refresh my playlist, keep the vibe."*
- **Mood chips** — Focus / Gym / Chill / Travel (single or multi-select).
- **Activity chips** — Work / Commute / Workout.
- **Freshness slider** — Familiar 30% ↔ Fresh 70% (the control users asked for).
- **Generate FreshMix** — primary action; disabled until min inputs present.
- **Result cards** — song name, **"Why this song?"** (similar mood + new artist),
  and **Save / Skip / Refresh** per track.
- **States:** empty → input → loading (skeleton) → results → feedback applied →
  error (graceful retry). Loading must stream first card < 1.5 s.

**Frontend responsibilities (thin):** collect inputs, render queue + rationale,
emit feedback events. **No ranking logic on device.**

**Accessibility/perf:** keyboard + screen-reader labels on chips/slider; queue
virtualized; offline cache of last queue.

---

## Phase 2 — Backend

**Problem it solves:** turn intent + context + taste into a safe queue, and learn
from feedback — server-side, testable, swappable model.

**Services (FastAPI, Python — same stack as the engine)**
| Service | Job |
|---|---|
| `intent` | Parse prompt + chips + slider → structured `DiscoveryRequest` (calls Agent, Phase 4) |
| `context` | Pull user music context from **Spotify API** (recent plays, saved, playlists, taste vector) |
| `rag` | Retrieve review **pain points** to avoid + similar-user signals from the engine corpus (vector store) |
| `recommend` | Candidate gen (Spotify recs/seeds) → **freshness blend** → **anti-repeat filter** → rank |
| `feedback` | Persist save/skip/refresh; update user freshness + taste weights |

**Recommendation algorithm (the core)**
1. **Candidates** from Spotify (seeds = taste vector + mood/activity → audio
   features: energy, valence, tempo).
2. **Freshness blend** = slider%: mix `novel` (new artists / unheard) vs
   `familiar` (adjacent to saved). 70% → 7 of 10 novel-but-adjacent.
3. **Anti-repeat filter** — drop tracks heard in last *N* days / already saved
   (directly answers the #1 complaint).
4. **Rationale** — Agent writes "why this song" per track (raises trust).
5. **Guardrails** — cap skip-risk (avoid too-random); enforce language/explicit
   prefs.

**Data stores:** Postgres (users, feedback, sessions); vector DB
(Pinecone/pgvector) for the **review-insight corpus** exported from the engine +
track embeddings; Redis (session queue cache).

**Contract**
```
POST /freshmix/generate   DiscoveryRequest  -> Queue{ tracks[], rationale[], freshness }
POST /freshmix/feedback   {track_id, action: save|skip|refresh} -> {ok, next?}
```

---

## Phase 3 — Frontend ↔ Backend linking

**Problem it solves:** keep the device thin and the contract stable across web +
mobile.

- **Transport:** HTTPS JSON REST (+ SSE/WebSocket for streamed first cards).
- **Auth:** Spotify OAuth (PKCE) on device → bearer token to backend; backend
  holds no user password.
- **Contract is the boundary** — the JSON above is the only coupling; frontend
  and backend deploy and scale independently.
- **In this repo today** the link is **in-process** (Streamlit imports the
  pipeline directly — `app.py` → `src/...`); the REST contract above is the
  production split of that same call graph (see `ARCHITECTURE.md` Phase 6).

```
device --OAuth--> backend /freshmix/generate --Agent API--> Claude
                       └--> Spotify API (context+candidates)
                       └--> vector store (engine review insights)
device <--SSE-- streamed tracks + "why this song"
device --POST /feedback--> loop updates taste + freshness
```

**Versioning:** `/v1/...`; additive fields only; contract tests guard breakage.

---

## Phase 4 — Agent API (Claude)

**Problem it solves:** natural-language intent + per-track rationale + balancing
familiar/fresh need reasoning, not rules alone.

**Provider:** Anthropic **Claude API** (Python SDK) — the same integration the
engine already uses (`src/analysis/analyzer.py`).
- **Model:** `claude-opus-4-8` (default); Haiku for high-volume rationale.
- **Structured outputs** (`messages.parse`) for `DiscoveryRequest` parsing and
  per-track rationale — validated against a Pydantic schema, so the backend never
  gets malformed agent output.
- **Two calls:**
  1. **Parse** — prompt+context → `DiscoveryRequest{mood, activity, language,
     freshness, seeds, constraints}`.
  2. **Rationale** — candidate tracks + user context → `[{track_id, why}]`
     grounded in mood match + novelty.
- **Tool use (optional, agentic):** expose `spotify_search`, `get_user_context`,
  `retrieve_review_insights` as tools so Claude composes the queue itself
  (Programmatic Tool Calling keeps intermediate data out of context).
- **Cost/latency:** prompt-cache the stable skill prompt; stream the rationale;
  batch rationale for the full queue in one call.

**Contract (parse)**
```
messages.parse(model, system=FRESHMIX_SKILL, output_format=DiscoveryRequest,
               messages=[user prompt + serialized context])  -> DiscoveryRequest
```

**Fallback:** if the key/API is unavailable, backend uses a **rule-based parser +
templated rationale** (mirrors the engine's `RuleBasedAnalyzer` pattern) so the
feature degrades, never dies.

---

## Phase 5 — Agent Skill

**Problem it solves:** make the agent a *specialist* at fresh-but-familiar
discovery, reusable and versioned — not a one-off prompt.

**The FreshMix discovery skill** = system prompt + I/O schema + tool list,
packaged as an Anthropic **Agent Skill** (`SKILL.md` + schema), portable to
Managed Agents.

- **Persona/instructions:** "Generate a queue that is fresh enough to feel new
  but familiar enough to trust. Respect mood, activity, language, and the
  freshness level. Never repeat recently-played or saved tracks. Explain each
  pick in one sentence." (Each clause traces to engine evidence.)
- **Inputs schema:** `mood`, `activity`, `language`, `freshness (0–100)`,
  `free_text`, `taste_vector`, `recent_track_ids`.
- **Outputs schema:** `tracks[{id, why}]`, `freshness_applied`, `avoided[]`.
- **Tools the skill may call:** `spotify_search`, `get_user_context`,
  `retrieve_review_insights` (the engine corpus), `check_repetition`.
- **Knowledge:** the engine's review-insight export is the skill's grounding
  corpus — it *knows* the pain points to avoid (repetition, wrong mood, randomness).
- **Versioning:** skill is pinned per release; A/B new prompts without breaking
  live sessions (Managed Agents version pinning).

---

## Phase 6 — Frontend deployment & Backend deployment

**Frontend**
- **PM/analyst dashboard (shipping now):** Streamlit on **Streamlit Community
  Cloud** — auto-deploys from GitHub `main`; permanent `*.streamlit.app` URL;
  secrets (`ANTHROPIC_API_KEY`, source keys, `[gcp_service_account]`) in the app
  Secrets. (This is the deployed engine the data comes from.)
- **Consumer mobile feature:** React Native build → TestFlight / Play Internal
  → staged rollout behind a feature flag; CDN for static assets.

**Backend**
- **Containerized FastAPI** (`Dockerfile`, `uvicorn`) → Cloud Run / Render / Fly;
  autoscale on request volume.
- **Async/batch:** rationale + nightly insight refresh via a worker queue;
  Anthropic **Batches API** (50% cost) for bulk rationale.
- **Managed data:** Postgres (managed), vector DB (Pinecone/pgvector), Redis.
- **CI/CD:** GitHub Actions — lint + `pytest` (Phase 7) on PR; deploy on merge;
  blue-green for the API; engine redeploys on push (current behavior).
- **Secrets/observability:** secrets manager (never in git; `.env` gitignored);
  request tracing, token-usage + cost dashboards, p95 latency + skip-rate alerts.

**Why this split:** Streamlit is monolithic and perfect for the analyst tool; the
consumer feature needs an independent, horizontally-scalable API — same Python
core, two deploy targets.

---

## Phase 7 — Test cases

Engine tests already run offline with zero tokens (`tests/test_offline.py`).
FreshMix adds:

| Layer | Test | Input → Expected |
|---|---|---|
| Agent parse | mood+activity+slider prompt | valid `DiscoveryRequest`, freshness=70 |
| Recommend | freshness=70 | ≥70% novel-but-adjacent tracks |
| Anti-repeat | recent/saved ids present | none appear in queue |
| Rationale | candidate tracks | one non-empty `why` per track |
| Feedback | save / skip / refresh | taste/freshness weights update; next queue differs |
| Linking | `/generate` contract | schema matches; SSE streams ≥1 card |
| RAG | "less repetitive" prompt | retrieves repetition pain points; influences filter |
| Offline | no API key | rule-based parser + templated rationale returns a full queue |
| Frontend | each state | empty/loading/results/error render; chips+slider accessible |

Patterns reuse the engine's `StubAnalyzer`/`MockCollector` approach so the whole
flow is testable without external calls.

---

## Phase 8 — Edge cases

| Class | Edge case | Handling |
|---|---|---|
| Input | Empty prompt, no chips | Use taste + default mood; nudge for a hint |
| Input | Conflicting prompt vs chips | Prompt (NL) wins; note assumption in rationale |
| Input | Unsupported language | Fall back to user locale; flag in response |
| Freshness | 100% fresh | Cap randomness via guardrail (avoid "too random" complaint) |
| Freshness | 0% familiar | Still inject ≥1 discovery so it's not pure replay |
| Catalog | Sparse taste / new user | Seed from mood/activity audio features only |
| Catalog | No candidates after anti-repeat | Widen window; relax adjacency before relaxing freshness |
| Agent | Invalid/missing key | Rule-based fallback (feature degrades, not dies) |
| Agent | Refusal / malformed | Schema validation rejects; retry once then fallback |
| Agent | Rate limit / 5xx | SDK backoff; serve cached/last queue meanwhile |
| Spotify | Token expired | Silent OAuth refresh; one retry |
| Spotify | API down | Serve last good queue from Redis; show stale badge |
| Feedback | Rapid skip-all | Detect dissatisfaction → regenerate with more familiar bias |
| Data | Engine corpus stale | Nightly refresh; version the corpus; never block on it |
| Scale | Viral load | Stateless API autoscale; batch rationale; cache by (mood,activity,freshness,taste-bucket) |
| Privacy | PII in prompts/feedback | Never store secrets/PII in prompts; redact logs; per-user data scoping |

---

## How this maps to the slides
- **Slide 08** — Metrics (North Star = Meaningful Discovery Rate) measures Phase 7
  outcomes.
- **Slide 09** — FreshMix AI feature = Phase 1 frontend + Phase 5 skill.
- **Slide 10** — Agent architecture = Phases 2–4 (engine → context → RAG → agent →
  recommendation → feedback loop).
- **This doc** — the full phase-by-phase solution behind those slides.
```
frontend (P1) ─ linking (P3) ─ backend (P2) ─ agent API (P4) ─ agent skill (P5)
            └─ deploy (P6) ─ tests (P7) ─ edge cases (P8) ─ fed by the deployed engine's data
```
