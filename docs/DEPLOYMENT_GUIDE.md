# From code to live demo, step by step ($0)

Everything below uses free tiers. Steps marked **(you)** need your own account, so only you can do
them. Budget about 2 hours for deployment, plus the training run on Kaggle.

---

## 0. Run it on your computer first

**Needs:** Python 3.11+ and Node.js 20+.
**Windows only:** ONNX Runtime also needs the Microsoft Visual C++ Redistributable. If the API log
says `DLL load failed while importing onnxruntime_pybind11_state`, install it from
https://aka.ms/vs/17/release/vc_redist.x64.exe and restart the terminal.

Terminal 1 (API):

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

Terminal 2 (web app):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 and drop in a photo. The status line under the headline says whether a
model is installed.

Run the tests any time:

```bash
cd backend && pytest --cov          # API: unit + integration tests
cd frontend && npm run test:e2e     # web app: Playwright end-to-end tests
```

---

## 1. Put the code on GitHub (you)

1. Create a free account at https://github.com and a new **public** repository named `TraceLens` (no README, you already have one).
2. In the `TraceLens` folder:

```bash
git init
git add .
git commit -m "TraceLens v1"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/TraceLens.git
git push -u origin main
```

The **Actions** tab will start the CI workflow (backend tests, frontend build and e2e, Docker build).

---

## 2. Train the model on Kaggle (you)

**Before you start:** your GitHub repo from step 1 must be **public**, because the notebook
downloads the code from it.

### 2.1 Account and phone verification (one time)

1. Sign up at https://www.kaggle.com.
2. Click your profile picture (top right) → **Settings** → **Phone verification** → verify.
   Without this, the GPU and Internet options stay greyed out.

### 2.2 Load the TraceLens notebook (not a blank one)

A new blank notebook contains Kaggle's sample code, which you don't need.

1. In the notebook's top menu click **File → Import Notebook**.
2. Choose **Browse files**, pick `TraceLens\training\notebooks\tracelens_kaggle.ipynb` on your PC, and click **Import**.
3. The page now shows cells starting with the heading "TraceLens: train the AI image classifier".
4. Rename it (click the name at the top left, e.g. `notebook2f401e3392`) to `tracelens-training`.

### 2.3 Turn on the GPU and Internet

1. Top menu **Settings → Accelerator → GPU T4 x2** (or **GPU P100**). Confirm the popup.
2. Top menu **Settings → Internet → On** (on some layouts it's a toggle in the right panel under **Session options**).
3. Your free quota is about 30 GPU hours a week, shown at the top of the right panel.

### 2.4 Add the dataset

1. In the right panel under **Input** click **+ Add Input**.
2. Search `cifake`. Pick **CIFAKE: Real and AI-Generated Synthetic Images** (by *birdy654*) and click the **+** (Add) button.
3. Close the search box. The dataset now appears under **Input**.
4. Optional, for a stronger model: search `genimage` and add a subset that has **one folder per generator**. Do this on a later run; start with CIFAKE only.

Note: CIFAKE images are tiny (32×32), so a CIFAKE-only model is a working first version but will
be weak on real phone photos. Adding GenImage and your holdout set (2.8) is what makes it good.

### 2.5 Find the real dataset path

Click **+ Code** to add a cell at the top, paste this, and press **Shift+Enter**:

```python
!ls /kaggle/input
!find /kaggle/input -maxdepth 3 -type d | head -30
```

You should see something like `/kaggle/input/cifake-real-and-ai-generated-synthetic-images/train/REAL`.
The part **before** `/train` is your CIFAKE path. (Kaggle sometimes uses a longer path like
`/kaggle/input/datasets/...`; use exactly what the command prints.)

### 2.6 Edit the two settings cells

1. **First code cell:** replace `YOUR-USERNAME` in `REPO_URL` with your GitHub username.
2. **Second code cell:** set `CIFAKE = "..."` to the path from 2.5. Leave `GENIMAGE`, `HOLDOUT` and `CASIA` as `None` for now.
3. **For a quick first run** (about 15 minutes), make it smaller:
   * in the same cell change `--limit-per-class 15000` to `--limit-per-class 3000`
   * in the EfficientNet cell change `--epochs 8` to `--epochs 2`
   * skip the ResNet50 cell (click it, then the scissors icon, or just don't run it)

### 2.7 Run it

* **Quick test:** click **Run All** and watch the cells. Keep the tab open; interactive sessions stop if left idle.
* **Full run (recommended once the quick test works):** click **Save Version** (top right) → **Save & Run All (Commit)** → **Save**. It runs in the background, so you can close the browser. Check progress under **View Versions** (the version number next to the notebook name).

What you should see:
* prepare_data prints a table of image counts (train / val / test, real / ai)
* the baseline prints `test: acc=... auc=...`
* training prints one line per epoch: `epoch 1/8 val_acc=0.9... val_auc=0.9...`
* export prints `ONNX saved ... max PyTorch vs ONNX difference ...e-07` (anything under 1e-3 is fine)
* evaluate prints a table with Accuracy and AUC

### 2.8 Download the results

1. When it finishes, open the **Output** section (right panel, or the version's **Output** tab).
2. Download `model_export` (it contains `tracelens.onnx` and `model_meta.json`) and `mlflow_logs.zip`.
3. To use the model on your PC: copy both files into `TraceLens\backend\models\` and restart the API. The status line on the website will show the model name.

Your own holdout set (the part interviewers remember): take 100+ photos with your phone, make
100+ images with a free AI image generator, and arrange them like this:

```
holdout/
  real/        your phone photos
  ai/
    flux/      AI images, one folder per generator
```

Zip it, then on Kaggle go to **Datasets → + New Dataset**, upload the zip, keep it **Private**,
add it to the notebook with **+ Add Input** (under *Your Work*), and set `HOLDOUT` to its path.
It is never used for training, so it measures real-world accuracy.

### If something goes wrong

| Error | Fix |
|---|---|
| `fatal: repository ... not found` | Repo is private or the URL is wrong. Make it public on GitHub (Settings → Danger Zone → Change visibility) |
| `Could not resolve host: github.com` | Internet is off (2.3), or your phone isn't verified (2.1) |
| `no images found; pass at least one dataset folder` | The `CIFAKE` path is wrong; redo 2.5 and copy the exact path |
| `device=cpu` in the training output | GPU is off (2.3). Training on CPU will be very slow |
| `CUDA out of memory` | Change `--batch-size 64` to `--batch-size 32` |
| Session stopped halfway | Use **Save Version → Save & Run All** so it runs in the background |

---

## 3. Publish the model on Hugging Face (you)

1. Create a free account at https://huggingface.co.
2. **Settings → Access Tokens → Create new token → Write**. Copy it.
3. In Kaggle: **Add-ons → Secrets → Add** `HF_TOKEN` = your token, and tick it for the notebook.
4. In the last notebook cell set `HF_MODEL_REPO = "YOUR-USERNAME/tracelens-detector"` and run it.

---

## 4. Deploy the API to a Hugging Face Space (you, then automatic)

1. On Hugging Face: **New → Space**. Name `tracelens-api`, SDK **Docker**, hardware **CPU basic (free)**, public.
2. Space **Settings → Variables and secrets**:
   * Variable `HF_MODEL_REPO` = `YOUR-USERNAME/tracelens-detector`
   * Variable `CORS_ORIGINS` = your Vercel URL from step 5 (you can add it after step 5), for example `https://tracelens.vercel.app`
   * Secret `GEMINI_API_KEY` = key from step 6 (optional)
3. On GitHub, your repo **Settings → Secrets and variables → Actions**:
   * **Secrets** tab: `HF_TOKEN` = your Hugging Face write token
   * **Variables** tab: `HF_SPACE` = `YOUR-USERNAME/tracelens-api`
   * **Variables** tab: `API_URL` = `https://YOUR-USERNAME-tracelens-api.hf.space` (used by the keep-warm ping)
4. Push any commit (or **Actions → Deploy API to Hugging Face Spaces → Run workflow**). The workflow uploads `backend/` to the Space, which builds the Docker image.
5. Check `https://YOUR-USERNAME-tracelens-api.hf.space/api/v1/health`. `"loaded": true` means the model downloaded.

---

## 5. Deploy the web app to Vercel (you)

1. Sign in at https://vercel.com with GitHub (Hobby plan is free).
2. **Add New → Project →** import `TraceLens`.
3. **Root Directory:** `frontend`. Framework is detected as Next.js.
4. **Environment Variables:** `NEXT_PUBLIC_API_URL` = `https://YOUR-USERNAME-tracelens-api.hf.space`
5. **Deploy.** Then add the Vercel URL to the Space's `CORS_ORIGINS` (step 4.2) and restart the Space.

---

## 6. Gemini summaries (optional, you)

1. Go to https://aistudio.google.com, sign in, **Get API key → Create API key**.
2. Add it as the `GEMINI_API_KEY` secret on the Space. Without it, summaries use the built-in template, and everything else works the same.

---

## 7. Finish the portfolio

* Copy the numbers from `artifacts/evaluation.md` (in the Kaggle output) into the README table and `docs/MODEL_CARD.md`.
* Record a short demo GIF of an analysis and add it to the README.
* Put the live links in the README table at the top.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Web app says "server is unreachable" | Check `NEXT_PUBLIC_API_URL` on Vercel and `CORS_ORIGINS` on the Space, then redeploy both |
| First request is slow | Free Spaces sleep when idle; the keep-warm workflow pings every 6 hours |
| Health shows `"loaded": false` | Check `HF_MODEL_REPO` spelling and that the model repo is public (or add `HF_TOKEN` as a Space secret) |
| `429 Too many requests` | Rate limit working as intended; raise `RATE_LIMIT_ANALYZE` on the Space if needed |
| Summaries say "Generated from the signals" | No Gemini key, or the free quota ran out; this is the designed fallback |
