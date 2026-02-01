# rev-education-nexhacks
We're here to revolutionize research-based, interdisciplinary learning.

## Quick start

### 1) Set environment variables

Create `backend/.env`:

```env
VITE_SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
OPENROUTER_API_KEY=your-openrouter-key
GEMINI_API_KEY=your-gemini-key
TOKEN_COMPANY_API_KEY=your-token-company-key
FIRECRAWL_API_KEY=your-firecrawl-key
ZOTERO_CLIENT_KEY=your-zotero-consumer-key
ZOTERO_CLIENT_SECRET=your-zotero-consumer-secret
YOUTUBE_API_KEY=your-yt-api-key
FRONTEND_URL=http://localhost:3000
```

Create `frontend/.env.local`:

```env
VITE_API_URL=http://127.0.0.1:8000
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```

### 2) Install dependencies

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd ../frontend
npm install
```

### 3) Run the app

```bash
# Terminal 1
cd backend
source .venv/bin/activate
python3 main.py
[OLD] uvicorn main:app --reload --port 8000

# Terminal 2
cd frontend
npm run dev
```

Frontend runs at `http://localhost:3000`, backend at `http://localhost:8000`.
