# Sentinel · Safe AI Software Engineering Agent

HNX26PSI09 · Karunya HACKNEX ’26. An evidence-first coding workspace: **never trade one bug for another.**

## What it does
Give a small Python project and a task to the agent. It records actual pytest results, proposes minimal source edits, verifies a candidate copy, and keeps it only when failures decrease (or all tests pass) without losing a previously passing test. Three attempts maximum. The browser retains the original files until verification accepts a candidate.

## How it works
1. Run pytest; record the passing and failing node IDs, skipped tests, collection errors, and raw output.
2. Include all non-test source below 30,000 characters; otherwise ask Gemini to select at most six files using paths, task, and failure output.
3. Request JSON `{ "explanation": "…", "edits": [{ "file": "relative.py", "content": "full content" }] }`.
4. Validate relative Python paths, content limits, and edit shape. Existing tests are immutable; new test files are permitted by validation.
5. Apply to a temporary candidate copy and run pytest with an eight-second timeout.
6. Accept only with zero regressions, no missing baseline tests, valid collection, and fewer failures or all passing. Otherwise discard and send feedback; retry up to three times.
7. Show a timeline, root cause, before/after counts, unified diff, and downloadable Markdown evidence including each attempt.
8. If no safe fix is found, retain the original code and say so.

```text
Original files → Baseline → Proposal → Validate → Candidate tests
                              ↑                       │
                              └── reject + feedback ──┤
                                                      └─ accept → Keep + report
```

## Live demo URL
Deployment is being connected to https://github.com/KancharlaSatwik07/hacknex-aiagent. See [deployment instructions](docs/DEPLOY.md). The project ZIP contains source, lockfiles, tests and documentation.

## Tech stack and models
React + TypeScript + Vite, custom CSS, Motion for timeline transitions, Lucide icons. Python serverless handlers, pytest, official `google-genai` client. No database or login. Gemini default: `gemini-flash-latest`; fallback: `models/gemini-3.7-flash`, as requested in the brief. These names are configuration defaults, not a claim of model availability. On 404, list available models and choose a Flash model supporting `generateContent`.

429/503 responses retry after 0, 3, and 8 seconds per model, then fallback. JSON parsing handles fences and retries malformed proposals. Provider errors are sanitized. Provider retries share a 48-second soft deadline with six-second per-call timeouts and SDK automatic retries disabled; frontend reports failure without accepting changes. Model listing or network overhead may still exceed host limits. Propose is configured for 60 seconds; older host plans may require reducing retries or an asynchronous queue.

## Declared resources
- Gemini API and official Google Gen AI Python SDK (`google-genai`), only when a server-side key is configured.
- pytest; Python standard library (`subprocess`, `http.server`, `tempfile`, `difflib`, `json`, `pathlib`).
- React, React DOM, Motion, Lucide React; TypeScript and Vite; React type declarations. Exact direct versions are in package.json; resolved dependencies in package-lock.json. Python resolved dependencies are in requirements-lock.txt.
- Google Fonts: DM Sans and IBM Plex Mono, loaded through CSS, with local system fallbacks.
- Vercel Python Functions / GitHub as intended hosting and source providers, not connected in this session.
- Design references: [Anime.js](https://animejs.com), [Motion](https://motion.dev), [Kokonut UI](https://kokonutui.pro), [Bklit](https://bklit.com), [shadcn/ui](https://ui.shadcn.com). Original implementation; no paid component source copied. Only Motion is installed from these references.
- OpenAI Codex was used to write and test the implementation. Offline fixes are recorded demonstration data, not model inference.

## Install and run locally
Node 22.12+ (or compatible later LTS), Python 3.10+.

```sh
npm ci
python3 -m venv .venv
.venv/bin/pip install -r requirements-lock.txt
.venv/bin/python scripts/server.py
```
In a second terminal, `npm run dev`, then open the printed localhost URL. The Vite proxy forwards `/api` to port 8000. The Python server deliberately binds only to loopback.

```sh
npm run build
.venv/bin/python -m pytest tests -q
```

## Environment variables
Set variables in the terminal that starts the Python server, or the host environment. `.env.example` is a template; local Python does not automatically load `.env`.

| Variable | Default | Purpose |
|---|---|---|
| GEMINI_API_KEY | absent | Server-only key. Missing key means explicitly labeled offline mode. |
| GEMINI_MODEL | gemini-flash-latest | Primary model; availability checked by API. |
| GEMINI_FALLBACK_MODEL | models/gemini-3.7-flash | Fallback before discovery. |
| ALLOW_TRUSTED_CODE | 0 | Set to 1 **locally only** for custom trusted code; ignored on Vercel. |

Never use `VITE_` for the API key. Never commit secrets. They are not sent to the browser or inherited by test processes.

## How to reproduce the demo results
Leave GEMINI_API_KEY unset. Select each project, click Run agent, and export the report. Reset before another run.

| Demo | Baseline | Accepted result | Regressions |
|---|---|---|---|
| Shop cart | 3 passing / 2 failing | 5 passing / 0 failing | 0 |
| Shop cart · add a feature | 3 passing / 3 failing | 6 passing / 0 failing | 0 |
| String utilities | 4 passing / 1 failing | 5 passing / 0 failing | 0 |

Offline mode requires the exact original files **and task**; it does not pretend to understand arbitrary requests. Counts come from real pytest subprocesses, not hardcoded UI results. The expected numbers in demo data are only fixtures for automated tests.

## Sample input and output
Input: Shop cart project, task “Fix the failing tests. Keep the existing cart behavior and make the smallest safe change.”
Output: 3/2 → 5/0, accepted, zero regressions. Root cause: add overwrote the previous quantity and total added instead of subtracting the discount. Changed file: cart.py. The report contains the full unified diff.

## Safety features
- Max 50 Python files / 200,000 UTF-8 bytes; bounded HTTP body and returned logs.
- Relative path validation, duplicate-edit rejection, protected existing tests, no new conftest.py hooks.
- Temporary directories only under `/tmp`; no shell=True; eight-second subprocess timeout; pytest cache disabled.
- Child environment excludes provider credentials and disables automatic pytest plugin loading.
- Verify recomputes the original baseline server-side so browser-supplied counts cannot forge acceptance. This means two runs per verify request, potentially up to 16 seconds plus overhead, rather than a strict ten-second endpoint.
- Default execution accepts **only exact bundled original or reviewed-fixed snapshots**. Arbitrary generated code is rejected on public hosting. Merely using subprocess is not isolation.
- No network sandbox, container isolation, authentication, rate limiting, or adversarial-code guarantee. Trusted local custom execution has the privileges of your user and must never process unknown code. Do not expose that local server.

## Scope note
**MVP built:** three demo variants across two codebases; editable project files and tasks; add Python file; real pytest baseline/verification; Gemini integration; offline mode; three-attempt browser loop; reviewable diff/root cause; evidence export; responsive keyboard-accessible UI; reduced motion; regression and validation tests; Vercel configuration.

**Not built:** isolated arbitrary-code execution service, automatic test generation, non-Python support, large-repository semantic search, persistent history, uploads, production authentication/rate limiting. On public hosting Gemini selects and explains a reviewed demo repair; executable content must exactly match that approved snapshot. General live repair is a trusted-local capability until a real sandbox is integrated. Test success is evidence, not proof of universal correctness.

## Limitations
Public hosting and real-key model integration were not verified in this session. No API key was available. Automated tests cover model retry/discovery with mocks. Hidden tests are not known; unchanged visible test files cannot prove hidden correctness. Ordinary feature requests for a suite that already fully passes are intentionally short-circuited as “No repair needed”; add a failing feature test first. Network denial is not implemented; public execution is restricted to reviewed snapshots. Browser state is lost on reload. Code editor is a lightweight textarea, not a full IDE.

## Assumptions
- Your explicit Vercel/Python architecture takes priority over Sites hosting.
- React/Vite is the fastest suitable frontend; custom CSS keeps the design small without installing several overlapping UI libraries.
- Security takes precedence over accepting untrusted Python in an unsandboxed public function.
- Skipped or missing baseline tests count against acceptance, including previously failing tests becoming skipped.
- Three attempts are counted even if the provider returns an error.
- Built-in tests are editable before a baseline but protected from the repair agent afterward; modified demos need trusted-local execution.

## Team placeholder
Team name: ______ · Members and roles: ______ · Institution: Karunya · Problem: HNX26PSI09.
