# amara_os / PropVision V1 — Land Console

A land-focused real-estate feasibility tool with a Node.js/Postgres backend and React desktop UI.

---

## Project Structure

```
propvision/
├── backend/                  Node.js + Fastify + Drizzle ORM
│   ├── migrations/
│   │   └── 001_create_land_parcels.sql
│   ├── src/
│   │   ├── db/
│   │   │   ├── client.ts     Drizzle + pg pool
│   │   │   └── schema.ts     Drizzle table definition
│   │   ├── api/
│   │   │   ├── parcels.ts    REST routes
│   │   │   └── assistant.ts  AI stub endpoint
│   │   ├── services/
│   │   │   └── feasibility.ts  Scoring logic
│   │   ├── middleware/
│   │   │   └── validation.ts   Zod schemas
│   │   └── server.ts
│   ├── .env.example
│   ├── package.json
│   └── tsconfig.json
│
└── frontend/                 React + TypeScript + Vite
    ├── src/
    │   ├── api/client.ts     Typed API wrapper
    │   ├── types/parcel.ts   TypeScript types
    │   ├── hooks/
    │   │   └── useParcels.ts Debounced filter hook
    │   ├── components/
    │   │   ├── FilterBar.tsx + .module.css
    │   │   ├── ParcelTable.tsx + .module.css
    │   │   ├── MapView.tsx   Leaflet map
    │   │   ├── ParcelDetail.tsx + .module.css
    │   │   └── AssistantPanel.tsx + .module.css
    │   ├── App.tsx + App.module.css
    │   └── main.tsx
    ├── index.html
    ├── vite.config.ts
    └── package.json
```

---

## Quick Start

### 1. Prerequisites

- Node.js 20+
- PostgreSQL (local or AWS RDS)

### 2. Backend

```bash
cd backend
cp .env.example .env
# Edit DATABASE_URL, PORT, CORS_ORIGIN in .env

npm install

# Run the migration (creates land_parcels table + indexes + trigger)
npm run migrate
# Or manually: psql $DATABASE_URL -f migrations/001_create_land_parcels.sql

# Development (hot reload)
npm run dev

# Production
npm run build && npm start
```

Backend runs on `http://localhost:3001` by default.

### 3. Frontend

```bash
cd frontend
npm install

# Development (proxies /parcels and /assistant to localhost:3001)
npm run dev

# Production build
npm run build
npm run preview
```

Frontend runs on `http://localhost:5173` by default.

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/parcels` | List parcels with filters + pagination |
| GET | `/parcels/:id` | Full parcel record |
| POST | `/parcels` | Create parcel (auto-computes feasibility) |
| POST | `/parcels/:id/recompute-feasibility` | Re-score and update parcel |
| POST | `/assistant/query` | AI assistant (stub → wire in Perplexity) |
| GET | `/health` | Health check |

### GET /parcels — Query Parameters

| Param | Type | Notes |
|-------|------|-------|
| `city` | string | ilike match |
| `state` | string | exact |
| `county` | string | ilike match |
| `zip` | string | exact |
| `min_acres` / `max_acres` | number | range |
| `zoning_codes` | string | comma-separated |
| `allowed_use_categories` | string | comma-separated |
| `min_est_max_lot_count` / `max_est_max_lot_count` | int | range |
| `feasibility_min` / `feasibility_max` | int 0–100 | range |
| `recommendations` | string | `GO,MAYBE,PASS` (comma-sep) |
| `distress` | string | `tax_delinquent,code_violation,preforeclosure,vacant` |
| `page` | int | default 1 |
| `limit` | int | default 50, max 200 |

---

## Environment Variables

### Backend `.env`

```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/propvision
PORT=3001
HOST=0.0.0.0
NODE_ENV=development
CORS_ORIGIN=http://localhost:5173

# Wire in when ready:
PERPLEXITY_API_KEY=
OPENAI_API_KEY=
```

---

## Wiring in Real AI

1. Open `backend/src/api/assistant.ts`
2. Replace `stubAIQuery` with a call to your AI provider.
3. The function signature `(message: string, context: string) => Promise<string>` must stay the same.
4. On the frontend, `AssistantPanel.tsx` contains a `sendToAI` wrapper — swap the implementation there if you want the frontend to call the AI directly (not recommended; keep keys server-side).

---

## AWS Deployment Notes

- **ECS/Fargate**: Build Docker image from `backend/`, set `DATABASE_URL` as a secret in ECS Task Definition.
- **RDS**: Use `postgresql://...@<rds-endpoint>:5432/propvision?sslmode=require`
- **ALB**: Route `/parcels*` and `/assistant*` to backend target group; serve frontend via S3 + CloudFront or a separate ECS service.
- **API Gateway**: Can be used instead of ALB for Lambda deployments — wrap Fastify with `aws-lambda-fastify`.
