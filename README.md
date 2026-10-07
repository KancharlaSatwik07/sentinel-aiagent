# Sentinel — Safe AI Engineering Workspace

A Python code-review workspace that imports source, runs pytest evidence locally, asks OpenRouter for a focused repair, and keeps a proposed change only after tests pass without losing previously passing tests.

## Features

- Clean, editable Python workspace with browser-local persistence; no faulty demo or seeded failing test.
- Import public GitHub repositories by URL; only bounded UTF-8 `.py` files are fetched (maximum 50 files / 200 KB). No repository is cloned or executed automatically.
- Server-only OpenRouter API key and an explicit live connection test.
- Safe Python syntax diagnostics when no pytest suite exists; repairs add meaningful pytest regression tests and are accepted only after passing verification. Existing tests stay protected; test execution is local-only and gated; path/size limits, regression-aware acceptance, three proposal attempts, reviewable diffs, and Markdown evidence export.
- Hosted code execution is always blocked. Custom code testing is an explicit local opt-in and runs with the local user's OS permissions; it is **not** a security sandbox.

## Run locally

Requirements: Node.js 22+ and Python 3.10+.

```sh
npm ci
python3 -m venv .venv
.venv/bin/pip install -r requirements-lock.txt
cp .env.example .env
# Put OPENROUTER_API_KEY in .env on the API server only.
# Set ALLOW_TRUSTED_CODE=1 only when you trust all code you plan to run.
.venv/bin/python scripts/server.py
```

In a second terminal:

```sh
npm run dev
```

Open the local URL printed by Vite. The Python server binds to `127.0.0.1:8000`; Vite proxies `/api` to that address. `.env` is ignored by Git and never delivered to the browser. Restart the server after changing environment values.

Run checks:

```sh
npm test
npm run build
```

## OpenRouter setup and live check

Set `OPENROUTER_API_KEY` in the server environment or ignored local `.env`. The browser only receives configuration status and the model name. Click **Test connection** to send a small server-side chat-completions request; the token never reaches the browser. `OPENROUTER_MODEL` defaults to `openrouter/free`, which automatically selects an available free model. Free model availability and rate limits can change; an optional `OPENROUTER_FALLBACK_MODEL` must be a free model ID. On Vercel, add both `OPENROUTER_API_KEY` and `ENABLE_PUBLIC_AI=1` in **Project Settings → Environment Variables**, then redeploy. Do not enable public AI without authentication, rate limits, abuse monitoring, and spending controls.

Never commit credentials or place them in a `VITE_` variable. If an API key was pasted into a chat or shared log, revoke it in [OpenRouter key settings](https://openrouter.ai/settings/keys) and replace the local environment value.

Provider references: [OpenRouter quickstart](https://openrouter.ai/docs/quickstart) and [Free Models Router](https://openrouter.ai/docs/cookbook/get-started/free-models-router-playground). The router uses the `openrouter/free` model ID and can select among free models that support the request's features.

When you request a repair, the selected provider receives the task description, source files, test source, and bounded test output. Remove API keys, passwords, private customer data, and other secrets before importing or submitting code. Free-model routing and quotas can change over time.

## Importing projects

Paste a public repository root URL such as `https://github.com/owner/repository`. The importer reads the repository's default branch through the GitHub API, keeps regular Python source/test files, and rejects private repositories, non-GitHub hosts, oversized or truncated projects, and excessive file counts. It does not import binary assets or clone Git history. Add individual Python files from the editor when needed.

**Review imported code before testing it.** Python tests and package hooks can execute arbitrary code. The local runner is intentionally disabled by default; enable `ALLOW_TRUSTED_CODE=1` only for source you control and trust. Do not expose the loopback server to the internet. Hosted/Vercel functions refuse code execution regardless of this setting.

## API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/status` | Reports non-secret OpenRouter configuration and local execution availability. |
| `POST /api/openrouter-check` | Makes a small live OpenRouter request server-side. |
| `POST /api/import-github` | Imports bounded Python files from a public repository. |
| `POST /api/baseline` | Runs pytest only when explicitly enabled on localhost. |
| `POST /api/propose` | Requests a source-only OpenRouter repair. |
| `POST /api/verify` | Recomputes baseline and candidate test evidence before accepting edits. |

## Deployment and security boundary

`npm run build` emits the Vite frontend to `dist`; Python handlers are under `api/`. Vercel can serve the frontend and API shape, but **hosted test execution is deliberately unavailable** until a real isolated execution service is integrated. Do not enable public AI requests without authentication, abuse controls, and a budget policy; the browser must never contain the provider key. Public repository import is read-only, but serverless provider quotas still apply. Review `docs/DEPLOY.md` before publishing.

This project has no login, database, isolated execution service, persistent server-side project storage, or abuse-rate-limit service. Those are production deployment requirements for shared/public use. Local browser persistence is per browser profile. Passing tests provide evidence for the tested suite, not proof of universal correctness.
# sentinel-aiagent
