# rev-education-nexhacks
We're here to revolutionize research-based, interdisciplinary learning.

## Quick start

### 1) Set environment variables

Create `backend/.env`:

```env
VITE_SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
ANTHROPIC_API_KEY=your-anthropic-key
LLM_PROVIDER=auto
CLAUDE_MODEL=claude-sonnet-4-6
CLAUDE_SEARCH_ENABLED=true
PROBLEM_SEARCH_PROVIDER=openrouter
PROBLEM_PREFETCH_TOPICS=3
# Optional fallbacks
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
cd /home/briancatmaster/rev-learn-nexhacks/frontend
VITE_API_URL=http://127.0.0.1:8001 npm run dev -- --host 127.0.0.1 --port 3001 --strictPort

# Terminal 2
cd /home/briancatmaster/rev-learn-nexhacks/backend
source .venv/bin/activate
python -m uvicorn main:app --host 127.0.0.1 --port 8001
```

Frontend runs at `http://127.0.0.1:3001`, backend at `http://localhost:8001`.