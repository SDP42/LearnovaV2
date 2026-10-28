# Deploying Learnova

Learnova needs three things a plain serverless host does not give: LibreOffice (PowerPoint → PDF), Tesseract (OCR) and
jobs that run for a minute or more. So the back end runs as one Docker container; the same container also serves the web app.

## Which free host can run everything?

| Host | Free plan | Runs the whole project? | Catch |
|---|---|---|---|
| **Hugging Face Spaces (Docker)** | 2 vCPU, 16 GB RAM, free | **Yes** — API, web app, LibreOffice, Tesseract | sleeps after ~48 h idle; disk resets on restart |
| Render (Docker web service) | 0.1 CPU, 512 MB RAM | Yes for small decks | sleeps after 15 min; 512 MB is tight for LibreOffice; disk resets |
| Koyeb | 0.1 vCPU, 512 MB | Small decks only | same memory limit |
| Oracle Cloud Always Free VM | up to 4 ARM cores, 24 GB RAM | Yes, permanently | needs a card for verification; you manage the VM |
| Google Cloud Run | free monthly quota | Yes | needs a billing account; cold starts |
| Vercel | serverless functions, 250 MB, short timeouts | **Web app only** | cannot run LibreOffice or minute-long jobs |

Recommendation for the review: **Hugging Face Spaces** for the whole project (most memory for free), or Vercel for the web
app with the API on Spaces/Render (option B).

## Option 0 — whole project on Hugging Face Spaces (free, recommended)
1. Create a Space at huggingface.co → **New Space → SDK: Docker → Blank**, hardware *CPU basic (free)*.
2. In the Space's README front matter set `app_port: 8000` (our container listens there).
3. Push this repository to the Space (`git remote add space https://huggingface.co/spaces/<user>/learnova` then
   `git push space main`), or link the GitHub repository.
4. In **Settings → Variables and secrets** add `GEMINI_API_KEYS` (and optionally `GROQ_API_KEY`, `NVIDIA_API_KEY`),
   plus `OTP_DEV_MODE=1` so the sign-in code is shown on screen.
5. The Space builds the Dockerfile (about 10 minutes) and opens at `https://<user>-learnova.hf.space`.

## Option A — one container on Render
1. Push this repository to GitHub (already done).
2. On render.com: **New → Blueprint**, pick the repository. `render.yaml` creates one Docker web service.
3. Fill the secret variables when asked: `GEMINI_API_KEYS` (comma-separated pool), optionally `GROQ_API_KEY`, `NVIDIA_API_KEY`.
4. Wait for the build (about 8–10 minutes the first time), open the service URL, sign in with the OTP shown on screen
   (`OTP_DEV_MODE=1`), upload a small PPTX.

Free-plan limits: the service sleeps after 15 minutes idle (first request then takes ~1 minute), 512 MB RAM, and no
persistent disk, so saved decks disappear on restart. Keep demo decks small (under ~30 slides) and set
`LEARNOVA_AI_DIAGRAM_MAX` low (12) so a build finishes inside the free-tier memory.

## Option B — web app on Vercel, API on Render
Deploy the API as in option A, then on vercel.com import the repository with **Root directory = `frontend`**.
Edit `frontend/vercel.json` and replace `YOUR-LEARNOVA-API.onrender.com` with the Render URL; Vercel then forwards every
`/api/…` call to the API, so no CORS setup is needed.

## Option C — local, for the review
```bash
docker build -t learnova .
docker run -p 8000:8000 --env-file .env learnova
```
Then open http://localhost:8000. Without Docker: `uvicorn apps.api.main:app --port 8000` and `npm --prefix frontend run dev`.

## After the demo
Rotate the Gemini, Groq and NVIDIA keys (they were shared during development) and set `OTP_DEV_MODE=0` with a real SMS
provider before inviting other users.
