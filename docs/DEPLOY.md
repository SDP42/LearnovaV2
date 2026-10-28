# Deploying Learnova

Learnova needs three things a plain serverless host does not give: LibreOffice (PowerPoint → PDF), Tesseract (OCR) and
jobs that run for a minute or more. So the back end runs as one Docker container; the same container also serves the web app.

## Option A — one container on Render (recommended for a demo)
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
