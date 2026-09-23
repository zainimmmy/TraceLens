# TraceLens web app

Next.js + Tailwind front end for the TraceLens API.

```bash
npm install
cp .env.example .env.local     # set NEXT_PUBLIC_API_URL if the API is not on localhost:8000
npm run dev                    # http://localhost:3000
```

| Command | What it does |
|---|---|
| `npm run build` | Production build |
| `npm run lint` | ESLint |
| `npm run test:e2e` | Playwright end-to-end tests (desktop + mobile, API mocked) |

Pages: `/` (single image analysis), `/batch` (up to 20 images or a ZIP), `/about` (method, ethics, privacy).
Deployed on Vercel with the project root set to `frontend/`.
