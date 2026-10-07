# Test and verification record

Run locally:

```sh
npm test
npm run build
```

The Python suite covers path/size validation, protected tests, fail-closed execution, safe syntax-only baselines without pytest, exact syntax diagnostics, testless repair acceptance only with new passing regressions, prompt requirements for uncovered behavior, subprocess credential isolation, OpenRouter request/auth, free-model discovery/fallback, and bounded mocked GitHub imports. The current suite has **41 passing tests**.

On 2026-10-07, the TypeScript check/Vite production build succeeded. The live OpenRouter health endpoint returned HTTP 200 using `openrouter/free`. A testless synthetic `add` bug produced a root-cause explanation, a one-file source fix, and three new pytest regression cases from a live free model; all three passed verification, and the candidate was accepted. Never paste an API key into source code or commit `.env`.

A live GitHub import was attempted, but this execution environment could not connect to GitHub. The importer is covered by mocked API tests for filtering, limits, and URL validation; retry a public repository URL from the running local app if network access is available.
