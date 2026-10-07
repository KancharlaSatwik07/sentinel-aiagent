# Deployment and operations

## Local development

1. Install Node.js 22+ and Python 3.10+.
2. Run `npm ci` and `.venv/bin/pip install -r requirements-lock.txt` after creating a virtual environment.
3. Copy `.env.example` to `.env`, set the server-only OpenRouter key, use `OPENROUTER_MODEL=openrouter/free` for automatic free-model routing, and leave `ALLOW_TRUSTED_CODE=0` unless you intentionally test source you trust.
4. Run `.venv/bin/python scripts/server.py` and `npm run dev` in separate terminals. The API binds only to loopback.
5. Validate with `npm test` and `npm run build`.

The `.env` file is ignored by Git. Restart the Python process after changing it. Do not put a secret in frontend environment variables or source files.

## Vercel

The repo contains Vite output configuration and Python function entry points under `api/`. Configure `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` in Vercel's server-side project environment and deploy a preview first. Vercel does not run this project's test runner: hosted execution is rejected in all cases because subprocess execution is not a security boundary. Run frontend build and Python unit tests before promoting a deployment.

Hosted OpenRouter requests are disabled unless `ENABLE_PUBLIC_AI=1`. In Vercel, set `OPENROUTER_API_KEY` and `ENABLE_PUBLIC_AI=1` under **Project Settings → Environment Variables** for the Production environment, then redeploy. Do not enable that flag publicly without authentication, reliable rate limiting, abuse monitoring, and spending controls. `openrouter/free` selects from the available free model pool; availability and rate limits vary, so this is suitable for experiments and low-volume use rather than a reliability guarantee. Public GitHub import is read-only but unauthenticated GitHub API quotas apply. The current project intentionally has no shared-user authentication or persistence, so treat any deployment as a preview until these controls are added.

## GitHub import behavior

The import endpoint accepts only `https://github.com/owner/repository` and `.git` root URLs. It uses the default branch, fetches regular `.py` files only, ignores hidden/vendor/build folders and symlinks, and rejects truncated trees, more than 50 files, or more than 200 KB of Python content. It does not run imported content. Git history, private repositories, submodules, and GitHub Enterprise are not supported.

## Execution security

The local runner executes code with the permissions of the local OS user. The opt-in is a trust acknowledgement, **not isolation**. Never expose the local API server on a public interface or run untrusted code. Hosted execution remains fail-closed even if `ALLOW_TRUSTED_CODE=1`; production remote execution requires an independently isolated, resource-limited sandbox and authenticated access.
