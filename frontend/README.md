# DILG Voting Frontend (Vue + Vite)

This is the Vue frontend for the DILG voting system backend (`/api/...`).

## Prerequisites
- Node.js 20+
- Backend running at `http://localhost:8000/api/` (adjustable in `src/App.vue` via `API_BASE`)

## Setup
```bash
cd frontend
npm install
```

## Run dev server
```bash
npm run dev
# then open the printed localhost URL (e.g., http://localhost:5173)
```

## Build
```bash
npm run build
```

## What it does
- Log in with Voter ID + PIN (`/api/login/`)
- Keep session via `X-Session-Token` and `/api/me/`
- Browse positions and candidates (`/api/positions/`, `/api/candidates/`)
- Cast votes (`/api/vote/`)
- View live tally (`/api/tally/`)
- Staff/admin login with Django staff credentials (`/api/admin/login/`, `/api/admin/me/`, `/api/admin/logout/`)
