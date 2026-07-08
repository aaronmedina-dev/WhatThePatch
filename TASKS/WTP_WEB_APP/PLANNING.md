# WTP Web App - Technical Planning

**Status:** Planning
**Branch:** `feature/wtp-web-app`
**Created:** 2026-07-08
**Target:** Locally-run web application built on top of the existing WhatThePatch codebase

---

## 1. Goals

A self-hosted web UI (run locally, same ethos as the CLI) that adds what the CLI cannot do:

1. **Browse review history** - list, search, and read all past reviews instead of hunting through `~/pr-reviews` files.
2. **Trigger re-reviews** - re-run a review against the latest state of a PR (or with different engine/model/prompt/context) and keep every run as a version.
3. **Converse about a review** - a chat thread attached to each review where the user can ask follow-up questions, add more context, and attach files that get injected into the conversation.
4. **Post findings to the PR** - break the review into discrete finding items and post selected items as comments on the PR (GitHub/Bitbucket), inline where the finding maps to a file/line, otherwise as a general PR comment.

### Non-Goals (v1)

- Multi-user support, authentication, or remote hosting. This binds to `127.0.0.1` only.
- Replacing the CLI. The CLI remains the primary interface; the web app is an additive layer.
- Webhooks / automatic review on PR open (possible later, out of scope now).
- Editing config.yaml through the UI (view-only status page in v1; edits stay in `wtp` CLI / setup wizard).

---

## 2. What We Reuse (existing codebase)

The web app is a thin layer over the existing modules, imported as a library - **no rewrite**:

| Existing module | Reused for |
|---|---|
| `pr_providers.py` (`parse_pr_url`, `fetch_github_pr`, `fetch_bitbucket_pr`, `extract_ticket_id`) | Fetching PR data for new reviews and re-reviews |
| `engines/` registry (`get_engine`, `ENGINES`) + `BaseEngine.generate_review()` | Running reviews |
| `whatthepatch.py` (`load_config`, `load_prompt_template`) | Config and prompt loading (shared `~/.whatthepatch/config.yaml`) |
| `url_context.py` (`read_context_paths`, `fetch_url_content`, `format_context_content`, `check_context_size`) | Attachment/context ingestion for conversations and re-reviews |
| `output.py` (`convert_to_html`, `GITHUB_CSS`, `save_review`) | Rendering reviews in the browser; still writing files to the output dir for CLI parity |
| `commands.py` (`get_engine_config_status`, `get_engine_model`, `get_available_models`) | Status page, engine/model pickers on the re-review form |

**Key constraint discovered during codebase review:** `BaseEngine` is single-shot (`generate_review(pr_data, ticket_id, prompt_template, external_context) -> str`). Conversations require a new multi-turn capability (Section 6.3).

---

## 3. Tech Stack

### Recommended stack (decision)

| Layer | Choice | Rationale |
|---|---|---|
| Backend | **FastAPI** + **Uvicorn** | Python - imports the existing modules directly. Async-native for long-running review jobs and SSE streaming. Auto OpenAPI docs for free. |
| Database | **SQLite** (stdlib `sqlite3`, thin DAO layer - no ORM) | Zero-install, single file at `~/.whatthepatch/webapp.db`. Matches "self-hosted, no dependencies" project ethos. An ORM (SQLAlchemy) adds a heavy dependency for ~6 tables; plain SQL with a small DAO module is enough. |
| Frontend | **Jinja2 templates + htmx + SSE** (no build step) | Keeps the project pure Python - no Node toolchain, no bundler, nothing extra to install. htmx handles partial updates (review list, chat thread); SSE streams job progress and chat responses. |
| Styling | Single hand-written CSS file, dark theme reusing the visual language of `github-pages/assets/css/style.css` and `GITHUB_CSS` from `output.py` | Consistent look with existing docs site and HTML review output. |
| Background jobs | `asyncio` tasks + in-process job registry (dict of job records persisted to DB) | Reviews take 30s-3min. No Celery/Redis - single-user local app; an in-process queue with DB-persisted job status is sufficient and survives page reloads (not process restarts - acceptable, job is marked `failed/interrupted` on restart). |
| Markdown rendering | Existing `markdown` + `pygments` deps via `output.convert_to_html()` | Already in requirements.txt. |

**Alternative considered and rejected (for now):** React/Vite SPA. Better for a heavily interactive chat UI, but introduces a Node build chain into a pure-Python project and complicates the `setup.py`-copies-files install model. htmx covers the required interactivity (lists, forms, streaming chat) with server-rendered partials. If the UI outgrows htmx, the API layer (Section 7) is already JSON-first, so a SPA can be layered on later without backend changes.

### New runtime dependencies

Added to `requirements.txt` (or a separate `requirements-web.txt` - decide at implementation; separate file keeps the CLI install lean, recommended):

```
fastapi>=0.110.0
uvicorn>=0.29.0
jinja2>=3.1.0
python-multipart>=0.0.9   # file upload parsing
sse-starlette>=2.0.0      # SSE responses
```

htmx is a single static JS file vendored into `webapp/static/` (no CDN - works offline, matching self-hosted ethos).

---

## 4. Directory Structure (new code)

```
WhatThePatch/
├── webapp/                      # New package - the web application
│   ├── __init__.py
│   ├── app.py                   # FastAPI app factory, startup (DB init, config load)
│   ├── server.py                # Entry point: uvicorn runner, port/host args
│   ├── db.py                    # SQLite connection, schema migrations, DAO functions
│   ├── jobs.py                  # Async job registry (review runs, chat completions)
│   ├── findings.py              # Parse review output into discrete finding items
│   ├── chat.py                  # Conversation orchestration (history -> engine chat call)
│   ├── pr_comments.py           # Post findings as PR comments (GitHub/Bitbucket APIs)
│   ├── importer.py              # Index pre-existing reviews from output directory
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── reviews.py           # List/detail/trigger/re-review endpoints
│   │   ├── conversations.py     # Chat thread endpoints (messages, attachments)
│   │   ├── comments.py          # Post-to-PR endpoints
│   │   └── system.py            # Status, engines, health
│   ├── templates/               # Jinja2 templates
│   │   ├── base.html
│   │   ├── reviews_list.html
│   │   ├── review_detail.html   # Review render + findings panel + chat thread
│   │   └── partials/            # htmx fragments (review row, chat message, finding card, job progress)
│   └── static/
│       ├── htmx.min.js          # Vendored
│       └── style.css
├── engines/
│   └── base.py                  # MODIFIED: add optional generate_chat() capability (Section 6.3)
├── whatthepatch.py              # MODIFIED: add `--web` flag to launch the server
└── TASKS/WTP_WEB_APP/           # This planning doc + implementation task breakdowns
```

**Data locations (runtime, not in repo):**

```
~/.whatthepatch/
├── webapp.db                    # SQLite database
├── attachments/                 # Uploaded files, per conversation
│   └── <review_id>/<uuid>-<original_name>
└── config.yaml                  # Shared with CLI (unchanged)
```

---

## 5. Data Model (SQLite schema)

```sql
-- A PR being reviewed. One row per unique PR URL.
CREATE TABLE prs (
    id            INTEGER PRIMARY KEY,
    provider      TEXT NOT NULL,           -- 'github' | 'bitbucket'
    pr_url        TEXT NOT NULL UNIQUE,
    owner         TEXT NOT NULL,           -- org/workspace
    repo          TEXT NOT NULL,
    pr_number     INTEGER NOT NULL,
    title         TEXT,
    author        TEXT,
    source_branch TEXT,
    target_branch TEXT,
    ticket_id     TEXT,
    created_at    TEXT NOT NULL,           -- ISO 8601 UTC
    updated_at    TEXT NOT NULL
);

-- One row per review RUN (initial review and every re-review).
CREATE TABLE review_runs (
    id             INTEGER PRIMARY KEY,
    pr_id          INTEGER NOT NULL REFERENCES prs(id),
    run_number     INTEGER NOT NULL,       -- 1, 2, 3... per PR
    status         TEXT NOT NULL,          -- 'queued'|'running'|'completed'|'failed'|'interrupted'
    engine         TEXT NOT NULL,          -- engine id, e.g. 'claude-api'
    model          TEXT,
    prompt_name    TEXT,                   -- 'default' or template filename used
    external_context_summary TEXT,         -- human-readable list of context sources used
    diff_hash      TEXT,                   -- sha256 of the diff, to show "PR changed since last run"
    review_markdown TEXT,                  -- the raw review output
    error          TEXT,                   -- populated when status='failed'
    started_at     TEXT,
    finished_at    TEXT,
    created_at     TEXT NOT NULL,
    UNIQUE (pr_id, run_number)
);

-- Discrete finding items parsed from a review run's output.
CREATE TABLE findings (
    id           INTEGER PRIMARY KEY,
    run_id       INTEGER NOT NULL REFERENCES review_runs(id),
    ordinal      INTEGER NOT NULL,         -- order within the review
    severity     TEXT,                     -- as emitted by the prompt (e.g. critical/major/minor/info)
    title        TEXT NOT NULL,
    body_markdown TEXT NOT NULL,
    file_path    TEXT,                     -- nullable: only when finding maps to a file
    line_start   INTEGER,                  -- nullable: only when finding maps to a line
    line_end     INTEGER
);

-- Record of findings posted to the PR (idempotency + audit).
CREATE TABLE posted_comments (
    id           INTEGER PRIMARY KEY,
    finding_id   INTEGER NOT NULL REFERENCES findings(id),
    provider_comment_id TEXT NOT NULL,     -- id returned by GitHub/Bitbucket API
    comment_url  TEXT,
    posted_at    TEXT NOT NULL,
    posted_as    TEXT NOT NULL             -- 'inline' | 'general'
);

-- One conversation per PR (spans review runs; messages reference the run they discussed).
CREATE TABLE messages (
    id           INTEGER PRIMARY KEY,
    pr_id        INTEGER NOT NULL REFERENCES prs(id),
    run_id       INTEGER REFERENCES review_runs(id),  -- the run in context when sent
    role         TEXT NOT NULL,            -- 'user' | 'assistant' | 'system'
    content      TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

-- Files attached to the conversation (injected as context).
CREATE TABLE attachments (
    id           INTEGER PRIMARY KEY,
    pr_id        INTEGER NOT NULL REFERENCES prs(id),
    message_id   INTEGER REFERENCES messages(id),     -- message it was attached with
    original_name TEXT NOT NULL,
    stored_path  TEXT NOT NULL,            -- under ~/.whatthepatch/attachments/
    size_bytes   INTEGER NOT NULL,
    created_at   TEXT NOT NULL
);
```

Schema versioning: a `schema_version` pragma/table and sequential migration functions in `db.py` (same pattern as many small tools; no Alembic).

---

## 6. Feature Design

### 6.1 Browse old reviews

- **List view:** all PRs with latest run status, engine, severity counts, repo/ticket filters, and free-text search (SQLite FTS5 over `review_runs.review_markdown` + `prs.title`).
- **Detail view:** rendered review (via `output.convert_to_html`), run-version switcher (run 1, 2, 3...), findings panel, and the conversation thread.
- **Import of pre-web history:** `importer.py` scans the configured output directory (`output.directory`, default `~/pr-reviews`) and indexes existing `.md`/`.html`/`.txt` files. Filename pattern `{repo}-{pr_number}` gives partial metadata; imported runs are flagged `imported=true` semantics via `prompt_name='imported'` and have no findings/diff hash. Best-effort - shown in the list, clearly labelled.
- New reviews triggered from the web app **also write files** via `output.save_review()` so CLI users see them in the output directory as before. DB is the source of truth for the app; files remain the CLI-compatible artifact.

### 6.2 Trigger review / re-review

- "New review" form: paste PR URL, pick engine/model (defaults from config), optional context paths/URLs, optional prompt template (from `prompt-templates/`).
- "Re-review" button on a review: pre-filled form; on submit creates the next `review_run` for that PR, re-fetches the PR (fresh diff), runs the engine in a background asyncio task.
- Progress via SSE: `queued -> fetching PR -> building prompt -> engine running -> parsing findings -> done`. The UI subscribes to `/api/runs/{id}/events`.
- `diff_hash` comparison surfaces "diff changed since previous run" in the run switcher.
- Engine calls are sync (existing code) - run them with `asyncio.to_thread()` so the event loop stays responsive.

### 6.3 Conversation about a review (NEW engine capability)

The single biggest codebase change. Design:

- Add to `BaseEngine`:

  ```python
  def supports_chat(self) -> bool:
      return False

  def generate_chat(self, messages: list[dict], system_prompt: str = "") -> str:
      """messages: [{'role': 'user'|'assistant', 'content': str}, ...]"""
      raise EngineError(f"{self.name} does not support conversations")
  ```

  Non-abstract with a safe default, so **all seven existing engines keep working untouched**.
- Implement `generate_chat()` for API engines first: `claude_api` (Messages API), `openai_api` (chat completions), `gemini_api` (multi-turn chat), `ollama_api` (`/api/chat`). These are natively multi-turn - low risk.
- CLI engines (`claude-cli`, `openai-codex-cli`, `gemini-cli`): defer to Phase 4. Fallback strategy if implemented: replay the transcript into a single prompt per turn (stateless), which is token-hungry but functional. UI disables the chat box with an explanatory message when `supports_chat()` is false.
- **Conversation context construction** (`chat.py`): system prompt assembled from the PR metadata + diff + the current run's review + formatted attachments (via `url_context.format_context_content`). Follow-up turns send the message history. Context size guarded with `check_context_size()`; when the diff is huge, truncate diff before truncating the review text.
- **Attachments:** uploaded via the chat box (multipart), stored under `~/.whatthepatch/attachments/<pr_id>/`, read with the same file-reading logic as `--context`, and injected into the system context from that message onward. Size cap (default 5 MB/file, configurable) and text-only in v1 (reject binaries other than by extension whitelist).
- A conversation can end with "Re-review with this context" - one click carries the attachments + a summary of user guidance from the thread into the next run's `external_context`.

### 6.4 Post findings as PR comments

- **Findings extraction** (`findings.py`): two-tier approach.
  1. **Structured (preferred):** extend the review flow so the engine emits, after the markdown review, a fenced `json` block with an array of findings (`severity`, `title`, `body`, `file`, `line_start`, `line_end`). Implemented as an *additional instruction appended by the web app at generation time* - the user's `prompt.md` is untouched, and the JSON block is stripped from the stored/displayed markdown. Parse and store into `findings`.
  2. **Fallback (markdown parsing):** for imported/legacy reviews and engines that ignore the JSON instruction (known Ollama limitation - documented as such, do NOT try to fix Ollama compliance in code), parse `##`/`###` sections + severity emoji conventions from the default prompt into coarse findings. Clearly mark these lower-confidence (no file/line anchoring).
- **Posting** (`pr_comments.py`), reusing tokens from `config.yaml` (`tokens.github`, `tokens.bitbucket_*`):
  - GitHub inline: `POST /repos/{owner}/{repo}/pulls/{n}/comments` with `commit_id` (head SHA captured at fetch time), `path`, `line`, `side=RIGHT`. GitHub general: `POST /issues/{n}/comments`.
  - Bitbucket inline: `POST /2.0/repositories/{ws}/{repo}/pullrequests/{id}/comments` with `inline: {path, to}`. Bitbucket general: same endpoint without `inline`.
  - **Line-anchor validation:** before posting inline, verify `file_path:line` exists in the stored diff hunks; if not (model hallucinated a line, or PR moved on), degrade to a general comment quoting the file/line. Never fail the whole batch on one bad anchor.
  - Idempotency: `posted_comments` table prevents double-posting; UI shows per-finding posted state with a link to the comment.
- UI: checkbox per finding + "Post selected to PR", per-finding edit-before-post (the posted body is editable), and a mandatory confirm dialog showing exactly what will be posted where (posting is outward-facing and irreversible-ish).

### 6.5 Launching

- `wtp --web [--port 8321]` added to `whatthepatch.py` argument parser -> `webapp.server.run()`. Default port 8321, host hard-coded `127.0.0.1`.
- Also runnable as `python -m webapp.server` for development.
- `setup.py` manifest/`manifest.json` updated so the self-update mechanism ships `webapp/` files to `~/.whatthepatch/`.

---

## 7. API Surface (JSON-first, htmx consumes HTML partials from the same routes via content negotiation or `/partials/*` twins)

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Reviews list page |
| GET | `/reviews/{pr_id}` | Review detail page (latest run) |
| GET | `/api/prs` | List PRs + latest run summary (filters: repo, status, q) |
| POST | `/api/reviews` | Trigger new review `{pr_url, engine?, model?, context?[], prompt_template?}` -> `{run_id}` |
| POST | `/api/prs/{pr_id}/rereview` | Trigger re-review (same payload minus URL) |
| GET | `/api/runs/{run_id}` | Run status + result |
| GET | `/api/runs/{run_id}/events` | SSE progress stream |
| GET | `/api/prs/{pr_id}/messages` | Conversation history |
| POST | `/api/prs/{pr_id}/messages` | Send chat message (multipart; may include attachments) -> SSE/htmx swap of assistant reply |
| GET | `/api/runs/{run_id}/findings` | Parsed findings |
| POST | `/api/findings/{id}/post-comment` | Post one finding to the PR `{body_override?}` |
| POST | `/api/runs/{run_id}/post-comments` | Batch post `{finding_ids[], }` |
| GET | `/api/system/status` | Engines, models, config status (reuses `get_engine_config_status`) |

---

## 8. Security Considerations (local app, still worth doing)

- Bind `127.0.0.1` only; no `--host` override in v1 (documented decision - exposing it would ship API keys' capabilities to the LAN).
- CSRF: same-site cookie + custom header check on mutating routes (htmx sends `HX-Request`; still add a per-session token because localhost pages can be targeted by drive-by requests from other websites).
- Attachment handling: extension/size whitelist, stored outside webroot, never executed, served back only as text with proper `Content-Type: text/plain`.
- Review markdown is model output -> render through the existing markdown pipeline and sanitize the resulting HTML (the current `convert_to_html` output is trusted-ish for local files, but a web origin raises the bar: add HTML sanitization, e.g. strip script/event handlers - evaluate `nh3` as the one extra dependency vs. a strict-mode markdown config).
- Tokens/API keys are read from existing `config.yaml`, never rendered into pages or logged.

---

## 9. Implementation Phases

Each phase is a working increment, PR'd separately into `feature/wtp-web-app` (or stacked PRs to main once stable).

### Phase 1 - Foundation + Browse (no engine changes)
- `webapp/` skeleton, FastAPI app, DB schema + DAO, base templates/styles.
- `wtp --web` launch flag.
- Importer for existing output-directory reviews.
- Reviews list + detail rendering, run-version switcher.
- **Acceptance:** can browse and read all previous reviews in the browser.

### Phase 2 - Trigger review / re-review
- Job registry + SSE progress.
- New-review and re-review forms wired to `pr_providers` + engines.
- Reviews also saved to output dir (CLI parity). `diff_hash` change detection.
- **Acceptance:** full review lifecycle from the browser matches CLI output for the same PR.

### Phase 3 - Findings + post to PR
- Findings JSON instruction + parser + markdown fallback parser.
- `pr_comments.py` GitHub/Bitbucket posting with anchor validation, idempotency, confirm dialog.
- **Acceptance:** post an inline and a general comment to a real test PR on both providers.

### Phase 4 - Conversations + attachments
- `BaseEngine.generate_chat()` + 4 API-engine implementations (claude/openai/gemini/ollama).
- Chat UI with SSE streaming replies, attachment upload + context injection.
- "Re-review with this context" bridge.
- CLI-engine chat: evaluate transcript-replay fallback; ship only if quality is acceptable, else keep disabled with message.
- **Acceptance:** hold a grounded conversation about a review, attach a file, and trigger a context-enriched re-review.

### Phase 5 - Polish + release
- FTS search, severity filters, empty states, error surfaces.
- `manifest.json` + `setup.py` + `install.sh` updates so `wtp --update` ships the web app.
- Docs: `README.md` section, `docs/web-app.md`, `IGNORE/CODEBASE.md` updates (mandatory per repo rules), github-pages page.
- Version bump (minor: `1.4.0`).

---

## 10. Risks & Open Questions

| # | Risk / question | Mitigation / decision needed |
|---|---|---|
| 1 | **CLI engines can't chat** (claude-cli, codex-cli, gemini-cli are one-shot subprocess calls) | Phase 4 fallback = transcript replay per turn; otherwise feature-flagged off per engine via `supports_chat()`. Accepted limitation at launch. |
| 2 | **Finding line-anchors may be wrong** (model output) | Validate against stored diff before inline posting; degrade to general comment. |
| 3 | **Ollama won't emit the findings JSON reliably** (documented model-capability gap - must not try to "fix" in code) | Markdown-fallback parser; findings from Ollama runs marked low-confidence, inline posting disabled for them. |
| 4 | **Large diffs blow the chat context** | `check_context_size()` + truncation order (diff first, review last); surface a warning chip in the UI. |
| 5 | **Install model**: webapp adds ~5 deps CLI users don't need | Separate `requirements-web.txt`; `wtp --web` prints install hint if FastAPI missing. Confirm at Phase 5 whether to fold into main requirements. |
| 6 | **Repo copy vs installed copy divergence** (`~/.whatthepatch/` is a snapshot) | Development runs from the repo (`python -m webapp.server`); release ships via existing manifest/update mechanism. |
| 7 | **Concurrent runs on the same PR** | Serialize per-PR (queue), allow parallel across PRs. |
| 8 | Conversation scope: per-PR (chosen) vs per-run | Chosen per-PR with `run_id` tagging on messages - keeps one continuous thread as the PR evolves. Revisit if confusing. |

---

## 11. Out-of-Scope Ideas (parking lot)

- Webhook/scheduled auto-review on PR open or push.
- Review diffing between runs ("what did the re-review change").
- Team mode (shared DB, auth) - would change nearly every assumption above.
- Exporting a conversation summary into the PR description.

---

## Document History

| Date | Change |
|---|---|
| 2026-07-08 | Initial planning document |
