# Rev Education - Setup Guide

## Prerequisites

- **Node.js** v18+
- **Python** 3.11+
- **Supabase** account
- **Google AI Studio** account (for Gemini API)

---

## 1. Clone & Navigate

```bash
git clone <your-repo-url>
cd rev-education-nexhacks
```

---

## 2. Environment Variables

### Backend (`backend/.env`)

Create `backend/.env`:

```env
# Supabase
VITE_SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# Gemini AI
GEMINI_API_KEY=your-gemini-api-key
```

**Where to get these:**

| Variable | Location |
|----------|----------|
| `VITE_SUPABASE_URL` | Supabase Dashboard → Settings → API → Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Dashboard → Settings → API → `service_role` key (secret!) |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) |

⚠️ **Important:** Use the `service_role` key, NOT the `anon` key for the backend.

---

### Frontend (`frontend/.env.local`)

Create `frontend/.env.local`:

```env
# Supabase (Vite requires VITE_ prefix)
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```

**Where to get these:**

| Variable | Location |
|----------|----------|
| `VITE_SUPABASE_URL` | Same as backend |
| `VITE_SUPABASE_ANON_KEY` | Supabase Dashboard → Settings → API → `anon` public key |

---

## 3. Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate   # macOS/Linux
# or
.\venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt
```

---

## 4. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install
```

---

## 5. Start the App

### Terminal 1 - Backend

```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

Backend runs at: `http://localhost:8000`

### Terminal 2 - Frontend

```bash
cd frontend
npm run dev
```

Frontend runs at: `http://localhost:5173`

---

## 6. Quick Reference

| Command | Purpose |
|---------|---------|
| `uvicorn main:app --reload` | Start backend (dev mode) |
| `npm run dev` | Start frontend (dev mode) |
| `npm run build` | Build frontend for production |
| `npm run preview` | Preview production build |

---

## Troubleshooting

**Backend won't start?**
- Check Python version: `python3 --version`
- Ensure venv is activated
- Verify `.env` file exists and has correct keys

**Frontend won't connect to Supabase?**
- Confirm `VITE_` prefix on all frontend env vars
- Restart dev server after changing `.env.local`

**API errors?**
- Check backend terminal for error logs
- Verify `SUPABASE_SERVICE_ROLE_KEY` is the service role (not anon)

---

## Project Structure

```
rev-education-nexhacks/
├── backend/
│   ├── main.py          # FastAPI app
│   ├── requirements.txt
│   └── .env             # Backend secrets
├── frontend/
│   ├── src/
│   ├── package.json
│   └── .env.local       # Frontend config
└── SETUP.md
```
