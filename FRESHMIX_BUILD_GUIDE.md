# FreshMix AI — Step-by-Step Build Guide

A phase-by-phase, step-by-step playbook to build FreshMix AI on top of the
deployed Review Discovery Engine. Each step has **what to do**, a concrete
**artifact** (file / endpoint / schema), and a **done-when** check.

Data + evidence source:
`https://spotify-discovery-engine-cgdz6f8vcaxrmskv6gbtze.streamlit.app/`
(186 real reviews → the pain points FreshMix must beat.)

Build order: **P0 → P1 → … → P8**. Each phase depends only on the ones before it.

---

## Phase 0 — Foundation & evidence

**Goal:** lock the problem in numbers and stand up the data the agent will use.

1. **Pull the evidence** from the deployed engine (Insights tab / JSON export):
   - P0 frustration: bad recommendations 10.1% (score 108)
   - Low trust = 58% of root causes · context mismatch = 16%
   - Unmet needs: less-repetitive 6.7%, fresh-but-familiar 5.6%, control 2.2%
2. **Freeze the design rules** these imply (one line each):
   `explain every track` · `mood+activity inputs` · `freshness slider` ·
   `anti-repeat` · `fresh-but-familiar core`.
3. **Export the review-insight corpus** → `data/review_insights.jsonl`
   (one row per pain point: `{theme, example_text, segment, severity}`).
4. **Repo + env:** create `freshmix/` service package; `.env` with
   `ANTHROPIC_API_KEY`, `SPOTIFY_CLIENT_ID/SECRET`; reuse the engine's `config.py`
   pattern.
- **Done when:** `review_insights.jsonl` exists and the 5 design rules are written
  down with their evidence.

---

## Phase 1 — Frontend (FreshMix screen)

**Goal:** one screen that collects intent and renders a trusted queue.

1. **Scaffold** the screen (React Native / Flutter for app; the Streamlit
   dashboard `app.py` is the PM/analyst frontend already shipping).
2. **Build inputs, top → bottom:**
   1. Prompt box (free text) — placeholder *"Refresh my playlist, keep the vibe."*
   2. Mood chips: Focus / Gym / Chill / Travel (toggle, ≥1).
   3. Activity chips: Work / Commute / Workout.
   4. Freshness slider: 0–100, default **70**, labels Familiar↔Fresh.
   5. `Generate FreshMix` button — disabled until prompt OR ≥1 chip.
3. **Build result card component:** track name · **"Why this song?"** line ·
   `Save / Skip / Refresh` buttons.
4. **Wire the 5 states:** empty → input → loading (skeleton, stream 1st card
   < 1.5 s) → results → error (retry).
5. **Emit events** (don't compute on device): `onGenerate(request)`,
   `onFeedback(track_id, action)`.
6. **A11y/perf:** labels on chips/slider; virtualize the list; cache last queue.
- **Done when:** screen renders all states with mock data; no ranking logic on
  device.

---

## Phase 2 — Backend (services + algorithm)

**Goal:** turn request + context into a fresh-but-familiar, anti-repeat queue.

1. **Create FastAPI app** `freshmix/api.py`; routers per service.
2. **`context` service** — `get_user_context(user)`:
   1. Spotify OAuth token in.
   2. Fetch recent plays, saved tracks, top artists, playlists.
   3. Build `taste_vector` (avg audio features) + `recent_track_ids`.
3. **`rag` service** — `retrieve_insights(request)`:
   1. Embed the prompt; query the vector store of `review_insights.jsonl`.
   2. Return pain points to **avoid** (e.g. repetition, wrong mood).
4. **`recommend` service** — the core pipeline:
   1. **Candidates:** Spotify recommendations seeded by taste + mood/activity →
      target audio features (energy/valence/tempo).
   2. **Freshness blend:** `novel = round(slider/100 * N)`; rest familiar-adjacent.
   3. **Anti-repeat filter:** drop `recent_track_ids` + saved (last N days).
   4. **Guardrails:** language/explicit prefs; cap "too random".
   5. Return ranked `tracks[]` (+ ids for rationale in P4).
5. **`feedback` service** — persist save/skip/refresh; update freshness + taste
   weights; return `next?` track on Refresh.
6. **Data stores:** Postgres (users, feedback) · vector DB (insights + track
   embeddings) · Redis (session queue cache).
7. **Define contracts** (`freshmix/schemas.py`, Pydantic):
   ```
   DiscoveryRequest { mood[], activity[], language, freshness:int, free_text,
                      taste_vector, recent_track_ids }
   Queue { tracks:[{id,name,artist,why}], freshness_applied, avoided[] }
   ```
8. **Endpoints:**
   ```
   POST /v1/freshmix/generate  DiscoveryRequest -> Queue
   POST /v1/freshmix/feedback  {track_id, action} -> {ok, next?}
   ```
- **Done when:** `POST /generate` returns ≥70% novel tracks with zero repeats on a
  seeded test user.

---

## Phase 3 — Frontend ↔ Backend linking

**Goal:** thin device, stable contract, independent scaling.

1. **Transport:** HTTPS JSON REST; **SSE** for streaming the first cards.
2. **Auth:** Spotify OAuth (PKCE) on device → bearer token to backend; backend
   stores no password.
3. **Client SDK** on device: `generate(request)` and `sendFeedback(...)` calling
   the P2 endpoints; map JSON → UI models.
4. **Streaming:** open SSE on Generate; render each track as it arrives; attach
   "why" when present.
5. **Versioning:** prefix `/v1`; additive-only changes; add **contract tests**
   (Phase 7) so a backend change can't silently break the app.
6. **Repo-today note:** the link is currently **in-process** (`app.py` imports
   `src/...`); these endpoints are the production split of that same call graph.
- **Done when:** device drives a full generate→render→feedback loop against the
  deployed backend over HTTPS.

---

## Phase 4 — Agent API (Claude)

**Goal:** use Claude for intent parsing + per-track rationale (trust).

1. **Init client** (Anthropic Python SDK) — reuse the engine's pattern
   (`src/analysis/analyzer.py`); model `claude-opus-4-8`.
2. **Step A — parse intent** (structured output):
   ```
   messages.parse(model, system=FRESHMIX_SKILL,
                  output_format=DiscoveryRequest,
                  messages=[prompt + serialized context])  -> DiscoveryRequest
   ```
3. **Step B — write rationale** (one batched call for the queue):
   ```
   input: candidate tracks + user context
   output: [{track_id, why}]   # "similar focus mood, new indie artist"
   ```
4. **Optional agentic mode:** expose tools `spotify_search`,
   `get_user_context`, `retrieve_review_insights`, `check_repetition`; let Claude
   compose the queue (Programmatic Tool Calling keeps intermediates out of
   context).
5. **Cost/latency:** prompt-cache the stable skill prompt; stream rationale;
   batch the whole queue in one call; Haiku for high-volume rationale.
6. **Fallback:** if key/API down → rule-based parser + templated rationale
   (mirror `src/analysis/rule_based.py`).
- **Done when:** a messy prompt ("like this but less repetitive, for the gym")
  yields a valid `DiscoveryRequest` and one non-empty `why` per track.

---

## Phase 5 — Agent Skill

**Goal:** package the agent as a reusable, versioned discovery specialist.

1. **Write `SKILL.md`** — persona + rules, each traced to evidence:
   *"Fresh enough to feel new, familiar enough to trust. Respect mood/activity/
   language/freshness. Never repeat recent or saved tracks. Explain each pick."*
2. **Define I/O schema:** inputs (`mood, activity, language, freshness, free_text,
   taste_vector, recent_track_ids`) → outputs (`tracks[{id,why}],
   freshness_applied, avoided[]`).
3. **Declare tools** the skill may call (the four from P4).
4. **Attach grounding corpus:** `review_insights.jsonl` so the skill *knows* the
   pain points to avoid.
5. **Register & version:** keep as inline system prompt now; promote to an
   Anthropic **Agent Skill** for Managed Agents; pin version per release; A/B new
   prompts without breaking live sessions.
- **Done when:** the skill runs identically whether called inline or as a
  registered skill, and version is pinned.

---

## Phase 6 — Deployment (frontend + backend)

**Goal:** ship both, independently, with CI/CD.

**Backend steps**
1. `Dockerfile` (python + uvicorn) for `freshmix/api.py`.
2. Deploy to Cloud Run / Render / Fly; autoscale on RPS.
3. Managed Postgres + vector DB (Pinecone/pgvector) + Redis.
4. Worker queue for async rationale + nightly insight refresh; Anthropic
   **Batches API** (50% cost) for bulk rationale.
5. Secrets in a secrets manager (never git; `.env` gitignored).

**Frontend steps**
1. PM/analyst dashboard: push to GitHub `main` → **Streamlit Community Cloud**
   auto-deploy (already live); set keys in app Secrets.
2. Mobile feature: build → TestFlight / Play Internal → staged rollout behind a
   feature flag.

**CI/CD**
1. GitHub Actions: lint + `pytest` on every PR.
2. Deploy on merge; blue-green for the API.
3. Dashboards: token cost, p95 latency, skip-rate alerts.
- **Done when:** a merge to `main` ships the API (blue-green) and the dashboard
  redeploys automatically.

---

## Phase 7 — Test cases (step by step)

**Goal:** every layer testable, much of it offline/zero-token.

1. **Agent parse** — input mood+activity+slider → expect `freshness=70`, valid
   `DiscoveryRequest`.
2. **Freshness blend** — `freshness=70` → expect ≥70% novel-but-adjacent.
3. **Anti-repeat** — recent/saved ids present → expect none in queue.
4. **Rationale** — candidates in → expect one non-empty `why` each.
5. **Feedback** — save/skip/refresh → expect taste/freshness weights change and
   next queue differs.
6. **Linking/contract** — `/generate` response matches schema; SSE streams ≥1
   card.
7. **RAG** — "less repetitive" prompt → expect repetition pain points retrieved
   and applied to the filter.
8. **Offline fallback** — no API key → expect rule-based parser + templated
   rationale returns a full queue.
9. **Frontend states** — assert empty/loading/results/error render; chips+slider
   accessible.
- Reuse the engine's `StubAnalyzer` / `MockCollector` so the flow runs with no
  external calls. **Done when:** `pytest` green in CI.

---

## Phase 8 — Edge cases (with the fix)

| Step | Edge case | Fix |
|---|---|---|
| 1 | Empty prompt, no chips | Use taste + default mood; nudge for a hint |
| 2 | Prompt contradicts chips | Prompt (NL) wins; note assumption in rationale |
| 3 | Unsupported language | Fall back to locale; flag in response |
| 4 | Freshness 100% | Guardrail caps randomness (avoid "too random") |
| 5 | Freshness 0% | Still inject ≥1 discovery (never pure replay) |
| 6 | New user / sparse taste | Seed from mood/activity audio features only |
| 7 | No candidates after anti-repeat | Widen window → relax adjacency → last, relax freshness |
| 8 | Invalid/missing API key | Rule-based fallback (degrade, don't die) |
| 9 | Agent refusal/malformed | Schema rejects → retry once → fallback |
| 10 | Rate limit / 5xx | SDK backoff; serve cached queue |
| 11 | Spotify token expired | Silent refresh + one retry |
| 12 | Spotify API down | Serve last good queue (Redis) + stale badge |
| 13 | Rapid skip-all | Detect dissatisfaction → regenerate with familiar bias |
| 14 | Stale insight corpus | Nightly refresh; version it; never block on it |
| 15 | Viral load | Stateless autoscale; batch rationale; cache by (mood,activity,freshness,taste-bucket) |
| 16 | PII in prompts/feedback | Never store secrets/PII in prompts; redact logs; per-user scoping |

---

## One-glance build map
```
P0 evidence/data ─► P1 frontend ─► P2 backend ─► P3 linking ─► P4 agent API
        │                                                          │
        └───────────── P5 agent skill ◄────────────────────────────┘
P6 deploy (frontend + backend) ─► P7 tests ─► P8 edge cases
            ▲ fed throughout by the deployed engine's review data ▲
```
Companion docs: `ARCHITECTURE.md` (analysis engine) · `FRESHMIX_ARCHITECTURE.md`
(solution overview) · this file (step-by-step build).
