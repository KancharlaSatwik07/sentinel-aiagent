# Verification model

Sentinel captures a real pytest baseline from the current Python workspace, asks OpenRouter for a source-only proposal, validates relative paths and immutable existing test files, and runs the candidate in a separate temporary copy. The baseline is recomputed at verification time. A candidate is accepted only when the suite is valid, no previously passing test regresses or disappears, and failing tests are reduced (or all tests pass). The browser retains the original files for rejected candidates and exports a Markdown evidence report.

The browser workspace persists in local storage. Public GitHub import retrieves Python source from a repository's default branch, subject to 50-file and 200 KB limits. It does not execute code during import.

OpenRouter credentials remain server-side. The connection action sends one small test prompt and reports success or a sanitized error. Unit tests mock the provider; a live API check requires a valid server-side key and network access.

Arbitrary Python execution is not sandboxed. It is disabled by default, can only be explicitly enabled for trusted code on the local loopback server, and is always blocked on hosted functions. Do not use the local runner with unknown code or expose it publicly. A shared/public deployment also needs authentication, abuse controls, and an isolated execution service before it should be treated as production-ready.
