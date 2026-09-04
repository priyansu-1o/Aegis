# Aegis — Elder Escrow & Anomaly Engine

A senior-guardian escrow layer that intercepts high-risk bank transactions and routes them through caregiver approval + a cooling-off period, built to counter "digital arrest" scam fund transfers.

Full PRD: see `docs/Aegis_prd_readme.md`
Pitch script: see `docs/Aegis_pitch_script.md`

---

## Project Structure
```
Aegis/
├── backend/              # Flask API — risk engine + escrow state machine
├── frontend-senior/      # React app — Senior device view
├── frontend-caregiver/   # React app — Caregiver device view
└── docs/                 # PRD, pitch script, API contract
```

## Prerequisites
- Python 3.10+
- Node.js 18+
- npm

---

## Setup

### 1. Backend (Flask)
```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Backend runs at `http://localhost:5000`

### 2. Senior App
```bash
cd frontend-senior
npm install
npm start
```
Runs at `http://localhost:3000`

### 3. Caregiver App
```bash
cd frontend-caregiver
npm install
npm start
```
Runs at `http://localhost:3001` (set `PORT=3001` in `.env` or `package.json` script to avoid clashing with the Senior app)

---

## Running the Demo Locally (one laptop)
1. Start backend first (`python app.py`)
2. Start both frontend apps in separate terminals
3. Open Senior app in one browser window, Caregiver app in another
4. Submit a high-risk transfer on Senior app → watch it appear on Caregiver app within a few seconds

## Running Across Two Physical Devices (stage demo)
1. Find your laptop's local IP: `ipconfig` (Windows) / `ifconfig` or `ipconfig getifaddr en0` (Mac)
2. Update `api.js` in both frontend apps to point to `http://<your-laptop-ip>:5000` instead of `localhost`
3. Connect both phones to the same WiFi as the laptop, open the frontend URLs in mobile browser
4. If WiFi is unreliable, run `ngrok http 5000` and point both frontends at the ngrok URL instead

---

## API Contract
See `docs/api_contract.md` for exact request/response JSON shapes. Backend and frontend teams should agree on this before building against it (hour 2 sync point — see PRD).

Core endpoints:
| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/transaction` | Senior submits a transfer |
| GET | `/transaction/<id>` | Poll status of a transaction |
| GET | `/pending/<caregiver_id>` | Caregiver fetches pending approvals |
| POST | `/transaction/<id>/resolve` | Caregiver approves/blocks |

---

## Environment Variables
Create `backend/.env`:
```
RISK_THRESHOLD=50
COOLING_OFF_SECONDS=60
```

---

## Known Limitations (hackathon scope)
- No real bank integration — Senior app is a self-contained mock
- No auth — user/caregiver IDs are hardcoded for demo purposes
- Polling-based sync by default (swap in Flask-SocketIO for real push if time allows)
- SQLite/in-memory storage — not production-grade persistence

## Team
| Member | Role |
|---|---|
| A | Backend Lead |
| B | Risk Engine Dev |
| C | Senior App Dev |
| D | Caregiver App Dev |
| E | Integration + Demo Lead |
