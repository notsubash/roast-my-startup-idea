# Roast My Startup — frontend

Next.js App Router frontend for the editorial verdict experience. See
`docs/specs/frontend-spec.md` for the full product spec.

## Prerequisites

- Node.js 20+
- Python backend running on port 8000 (for API + type generation)

## Setup

```bash
cd web
npm install
cp .env.example .env.local
```

Edit `.env.local` if your API is not at `http://127.0.0.1:8000`.

## Generate API types

With the backend up:

```bash
uvicorn api.app:app --app-dir src --reload --port 8000
```

In another terminal:

```bash
cd web
npm run gen:types
```

This writes `src/lib/api/types.ts` from the live OpenAPI schema. The committed
file is a snapshot so CI/build work without a running API; regenerate when the
backend schema changes.

## Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The footer health dot
turns green when `GET /health` succeeds.

## Scripts

| Script              | Purpose                             |
| ------------------- | ----------------------------------- |
| `npm run dev`       | Next.js dev server                  |
| `npm run build`     | Production build                    |
| `npm run lint`      | ESLint                              |
| `npm run format`    | Prettier write                      |
| `npm run gen:types` | Regenerate OpenAPI TypeScript types |

## Stack

Next.js 16 · TypeScript · Tailwind CSS v4 · Sonner · openapi-typescript

Fonts (via `next/font`): Newsreader (display), Public Sans (UI), JetBrains Mono
(mono).
