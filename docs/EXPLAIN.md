# Sentinel explained for first-time students

The browser is the coordinator. Python does the measuring. Gemini suggests a change. None of these roles should be confused: a convincing explanation is not proof that code works.

## File-by-file map
- `src/main.tsx`: React UI, project selection, editable source, task field, step orchestration, timeline, diff, report download. Original files are held in memory; only an accepted candidate replaces them.
- `src/style.css`: colors, spacing, layout, responsive breakpoints, focus indicators, and reduced-motion handling. The dark workspace and green verification accent are original styling.
- `index.html`: browser entry and page metadata.
- `public/favicon.svg`: shield icon for the browser tab.
- `data/demos.json`: three demo variants, original source, tests, recorded fixes, explanations, expected test counts.
- `agent/core.py`: validates files and proposals, executes pytest, collects test identities, compares baseline/candidate, generates unified diffs. Its execution allowlist is separate from acceptance logic.
- `agent/model.py`: decides offline/live mode, calls the official Gemini SDK, chooses source context, handles JSON and retries, discovers replacement Flash models after a 404.
- `agent/http.py`: small JSON request handler; bounds input; dispatches to baseline, propose, and verify. No database or sessions.
- `agent/__init__.py`: makes agent a Python package.
- `api/baseline.py`, `api/propose.py`, `api/verify.py`, `api/status.py`: Vercel entrypoints sharing the same handler.
- `scripts/server.py`: loopback-only local API server on port 8000.
- `tests/test_agent.py`: meaningful acceptance, regression, malformed-response, model-retry, secrets, and demo end-to-end tests.
- `package.json` / `package-lock.json`: frontend commands and pinned dependency graph.
- `requirements.txt` / `requirements-lock.txt`: Python direct dependencies and resolved environment versions.
- `tsconfig.json`: strict TypeScript compilation settings.
- `vite.config.ts`: frontend development server with API proxy.
- `vercel.json`: build output and Python function duration/packaging.
- `.env.example`: safe variable names and placeholders; not loaded automatically locally.
- `.gitignore`: keeps generated files, local environments and secrets out of Git.
- `LICENSE`: MIT reuse terms.
- `README.md`: complete operating instructions, reproducible counts, assumptions and honest limits.
- `docs/DEPLOY.md`: login-dependent steps to publish and configure the model.
- `docs/EXPLAIN.md`: this walkthrough.
- `docs/TEST_RESULTS.md`: results recorded during development.

## Follow one cart repair
The original add method replaces a quantity instead of increasing it. Total also adds a discount. Three tests pass and two fail. The agent receives the files, failing output and task. In offline mode it retrieves a recorded fix; live mode asks Gemini. Validation rejects changes to tests and escaping file paths. A fresh candidate folder receives the proposed source. Pytest reports five passing tests. All original passing IDs are still passing, so the gate accepts. React updates the working files and lets the presenter export the evidence.

If a fix causes a regression, the candidate is discarded. The next attempt starts from the original files with feedback from the rejected candidate. After three rejected attempts, the original remains unchanged. Verify recomputes the baseline to prevent forged browser counts.

## What we built vs what the AI model does
We built the interface, request orchestration, path validation, pytest runner, evidence collection, regression gate, retry policy, deterministic demos, and reports. Gemini provides an explanation and proposed source content. It does not decide acceptance. Offline mode does not call Gemini at all. Codex assisted development of both the application and tests.

## Fifteen likely judge questions
1. **What makes this safe?** It preserves existing tests and rejects regressions, but it is not a proof of correctness or an arbitrary-code sandbox.
2. **How do you identify regressions?** Compare pytest node IDs: every baseline passing ID must still pass.
3. **Can the model delete a test to win?** Existing test edits are rejected. Missing or skipped baseline IDs also fail the gate.
4. **What if a new test fails?** It appears in candidate failures; acceptance requires fewer failures and no lost baseline tests.
5. **Do you know the hidden tests?** No. Minimal changes and existing behavior preservation help but cannot guarantee them.
6. **How many retries?** Three repair attempts in the browser; provider calls have separate transient-error retries.
7. **Are demo numbers fabricated?** No. Counts come from real pytest subprocesses. Offline source patches are prerecorded and explicitly labeled.
8. **Where is the API key?** Only the backend environment. It is not passed to child test processes or the browser.
9. **What if the model name changes?** On 404, list available models and choose a Flash model that supports generation.
10. **What if the model is overloaded?** Backoff, fallback, and clear failure. A timed-out request never commits a candidate.
11. **How are large projects handled?** Up to 50 files/200 KB; above 30,000 source characters, ask the model to select at most six source files.
12. **Why separate endpoints?** To keep pytest and model work independently observable and reduce individual request duration.
13. **Can someone upload malicious Python?** Public mode rejects everything except reviewed snapshots. Trusted local mode is not safe for adversarial code.
14. **Can it run completely offline?** No model access is required for built-in demos. Fonts use the network but have system fallbacks; dependencies must be installed first.
15. **What would you build next?** A genuinely isolated test-execution service, then persistent reports, authenticated quotas, and broader languages.
