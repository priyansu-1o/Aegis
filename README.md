# AEGIS

AEGIS is a financial safety layer for seniors and caregivers. It evaluates transfers for scam signals, pauses suspicious payments during a cooling-off window, and gives a connected caregiver the opportunity to approve or block them.

## Architecture

- `backend/`: Flask and Flask-SocketIO API, authentication, risk engine, and Supabase data access
- `frontend/frontend/`: Unified Vite React application with landing, authentication, senior, and caregiver routes
- `backend/supabase_schema.sql`: Supabase tables and indexes
- Supabase is the only supported data store. SQLite has been removed.

## Requirements

- Python 3.10+
- Node.js 18+
- npm
- A Supabase project

## Setup

### Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

The API runs at `http://localhost:5000`.

On macOS/Linux, activate the environment with `source venv/bin/activate`.

### Supabase

Run [backend/supabase_schema.sql](backend/supabase_schema.sql) in the Supabase SQL editor, then create `backend/.env`:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-server-side-supabase-key
JWT_SECRET_KEY=replace-with-a-long-random-secret
FRONTEND_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
COOKIE_SECURE=false
COOKIE_SAMESITE=Lax
```

For the deployed application, set these values in Render instead:

```env
FRONTEND_ORIGINS=https://aegis2-five.vercel.app
COOKIE_SECURE=true
COOKIE_SAMESITE=None
```

`SUPABASE_SERVICE_ROLE_KEY` or `SUPABASE_ANON_KEY` may be used instead of `SUPABASE_KEY`. Keep all Supabase keys in the backend environment and never expose them through the frontend.

The backend fails at startup when Supabase credentials or the `supabase` package are missing. It does not fall back to local storage.

Render uses Python 3.12.8, pinned in the repository-root `runtime.txt`. This avoids the current Gevent/OpenSSL incompatibility on Python 3.14.

### Frontend

In a second terminal:

```powershell
cd frontend/frontend
npm install
npm run dev
```

The Vite server normally runs at `http://localhost:5173`. It uses `http://localhost:5000` as the default API URL. To override it, create `frontend/frontend/.env`:

```env
VITE_API_BASE=http://localhost:5000
```

## Routes

| Route | Purpose |
|---|---|
| `/` | Public landing page |
| `/login` | Sign in for either role |
| `/signup` | Create a senior or caregiver account |
| `/senior` | Senior balance and transfer dashboard |
| `/caregiver` | Caregiver pending-payment review dashboard |

Signup returns a generated permanent User ID. Caregivers can optionally enter a senior's User ID as the link code, or connect later.

## API

Authenticated requests use the `aegis_token` HTTP-only cookie.

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/signup` | Create an account with `name`, `email`, `password`, `role`, and optional `link_code` |
| `POST` | `/api/login` | Authenticate with email and password |
| `POST` | `/api/logout` | Clear the auth cookie |
| `GET` | `/api/me` | Return the authenticated user |
| `GET` | `/api/health` | Check API and Supabase status |
| `POST` | `/api/transfer` | Submit a senior transfer for risk evaluation |
| `GET` | `/api/transactions` | List the current senior's transactions |
| `GET` | `/api/transactions/<id>` | Get one transaction |
| `GET` | `/api/transactions/pending` | List pending transactions for the current caregiver |
| `POST` | `/api/resolve/<id>` | Approve or block a pending transaction |
| `GET` | `/api/transactions/<id>/audit` | View transaction audit events |

## Demo Flow

1. Start the backend and frontend.
2. Create a senior account at `/signup` and note its User ID.
3. Create a caregiver account using that User ID as the optional link code.
4. Sign in as the senior and submit a suspicious or unusually large transfer.
5. Sign in as the caregiver and approve or block the held transaction.

## Validation

Backend:

```powershell
cd backend
python -m compileall -q .
python -m pytest -q
```

Frontend:

```powershell
cd frontend/frontend
npm run build
npm run lint
```

## Deployment

The backend `Procfile` runs Gunicorn with a threaded worker. This avoids the Gevent/OpenSSL monkey-patching issue on Render:

```text
web: gunicorn --worker-class gthread --threads 4 --workers 1 --bind 0.0.0.0:$PORT app:app
```

For production, configure a strong `JWT_SECRET_KEY`, set the deployed frontend in `FRONTEND_ORIGINS`, use `COOKIE_SECURE=true` over HTTPS, and keep Supabase credentials server-side.

## Scope

Bank transfers are simulated. Risk decisions are deterministic and configured in `backend/config.py`; AEGIS is a prototype and does not replace bank fraud controls or financial advice.
