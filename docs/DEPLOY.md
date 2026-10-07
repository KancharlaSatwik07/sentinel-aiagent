# Publish on GitHub and Vercel Hobby

No deployment was performed because authenticated GitHub/Vercel tooling was unavailable. No host runtime incompatibility has been observed, so switching hosts would not resolve the login requirement.

1. Sign into GitHub. Create a **public**, empty repository named `hacknex-psi09-agent-web`. Do not initialize another README.
2. From this project, run (substitute your GitHub username):
   ```sh
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/hacknex-psi09-agent-web.git
   git push -u origin main
   ```
   If starting from the ZIP with no Git history: `git init`, `git add .`, `git commit -m "Build Sentinel agent workspace"`, then the commands above. `.gitignore` excludes secrets.
3. Sign into Vercel, choose a personal **Hobby** account, Add New → Project → import that repository.
4. Framework: Vite. Build: `npm run build`. Output: `dist`. Leave root at the repository root. Python functions live under `/api`. Use a supported Python 3.12 runtime if configurable.
5. For offline demo, leave GEMINI_API_KEY absent. Click Deploy. Copy the resulting public production URL into README.md.
6. Open it, verify the banner says **Offline demo mode**, select Shop cart, click Run agent. Expect 3 passing / 2 failing → 5 passing / 0 failing, zero regressions. Test String utilities: 4/1 → 5/0. Export the report.
7. To enable live proposals: **Vercel dashboard → project → Settings → Environment Variables → Add Environment Variable**. Name `GEMINI_API_KEY`; value your Gemini key; select Production (and Preview only if desired). Save. Add `GEMINI_MODEL=gemini-3.8-flash` and `GEMINI_FALLBACK_MODEL=models/gemini-3.7-flash` or current available Flash IDs. Then **Deployments → latest deployment → … → Redeploy**. Never put the key into frontend code, chat, or a VITE_ variable.
8. Public execution intentionally remains demo-allowlisted. General live repair needs a true isolated execution service; setting the key does not make arbitrary execution safe. Do not enable ALLOW_TRUSTED_CODE on a public server.

## Local live AI verification
Export your key in your own terminal without saving it in source. Export `ALLOW_TRUSTED_CODE=1` only for trusted local inputs; start the loopback API. Run each demo through the UI and inspect actual results. Live AI fixes need not match the offline recorded fix, so results are not promised in advance.

## If Vercel Python packaging fails
Read build logs first: ensure `requirements.txt`, `agent/`, and `data/demos.json` are included. Server functions must import `agent.http`; their working directory must contain the project package. The project includes a 60-second function configuration; use the maximum your free plan supports. A tested deployment is required before claiming a live URL. Netlify and Hugging Face also require account access and platform-specific packaging; those adapters are not implemented or claimed tested here.
