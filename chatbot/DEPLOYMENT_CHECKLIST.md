# ✅ Deployment Checklist

## Pre-Deployment

### System Requirements
- [ ] Python 3.9+ installed
- [ ] Ollama installed from ollama.ai
- [ ] 16GB RAM available
- [ ] 5GB free disk space
- [ ] Stable internet (for model download)

### Knowledge Base
- [ ] Knowledge base files at `/mnt/sda1/Polygon/primebot/knowledge_base/`
- [ ] All markdown files have YAML frontmatter
- [ ] Product IDs are unique
- [ ] Metadata is populated (banking_type, tier, etc.)

---

## Setup Phase

### Initial Setup (First Time Only)

```bash
cd /mnt/sda1/Polygon/primebot/chatbot

# Linux/Mac
bash run.sh setup

# Windows
run.bat
# Select option 1
```

Checklist:
- [ ] Python environment created (`venv/` directory exists)
- [ ] Dependencies installed (check `pip list` shows chromadb, torch, etc.)
- [ ] No errors during installation

### Model Download

```bash
# Terminal 1
ollama serve

# Terminal 2
ollama pull qwen3-1.7b-q4
```

Checklist:
- [ ] Ollama running on localhost:11434
- [ ] Model downloaded (check `ollama list`)
- [ ] Model size ~1.5 GB

---

## Launch Phase

### Start Services (In Order)

**Terminal 1: Ollama**
```bash
ollama serve
```
- [ ] Output shows "Listening on 127.0.0.1:11434"
- [ ] Keep this running during entire session

**Terminal 2: Backend**
```bash
cd /mnt/sda1/Polygon/primebot/chatbot
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows
cd backend
python3 app.py  # or: python app.py on Windows
```

Expected output:
```
✓ Vector DB initialized
✓ RAG pipeline initialized successfully
Starting server at http://0.0.0.0:8000
```

Checklist:
- [ ] No error messages
- [ ] Server running on port 8000
- [ ] Can see FastAPI startup messages

**Terminal 3: Frontend (Optional)**
```bash
cd /mnt/sda1/Polygon/primebot/chatbot/frontend
python3 -m http.server 8001
```

Checklist:
- [ ] HTTP server running on port 8001
- [ ] No address-already-in-use errors

### Open Web Interface

**Option A: Direct File**
```bash
open /mnt/sda1/Polygon/primebot/chatbot/frontend/index.html
# or: file:///mnt/sda1/Polygon/primebot/chatbot/frontend/index.html
```

**Option B: Via HTTP Server**
```bash
http://localhost:8001/index.html
```

Checklist:
- [ ] Browser opens without errors
- [ ] UI loads completely
- [ ] Status shows "Ready"
- [ ] Input field is enabled

---

## Validation Phase

### System Health Check

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "vector_db_size": 45,
  "model": "Qwen3-1.7B Q4 (via Ollama)"
}
```

Checklist:
- [ ] HTTP 200 response
- [ ] status = "healthy"
- [ ] vector_db_size > 0

### Test Query

Try in the web UI:
- Query: "Tell me about Visa Gold credit card"
- Expected: Answer within 10-30 seconds
- Should see sources cited

Checklist:
- [ ] Query sent successfully
- [ ] Loading spinner appears
- [ ] Response generated (may take 30s on CPU)
- [ ] Response contains relevant information
- [ ] Sources are cited
- [ ] No error messages

### Test Multiple Queries

Try these:
- [ ] "What Islamic banking options do you have?"
- [ ] "Which card is best for travel?"
- [ ] "What are the eligibility requirements?"
- [ ] "Compare Visa Gold and Mastercard Platinum"

Expected: All queries return relevant answers

---

## Post-Deployment

### Performance Verification

Typical metrics:
- [ ] Response time: 10-30 seconds (CPU normal)
- [ ] Memory usage: ~10-11 GB peak (within 16GB limit)
- [ ] No crashes or warnings
- [ ] UI responsive

### Check Logs

```bash
tail -f /mnt/sda1/Polygon/primebot/chatbot/backend/logs/chatbot.log
```

Checklist:
- [ ] No ERROR or CRITICAL messages
- [ ] Queries logged with responses
- [ ] No unhandled exceptions

### API Documentation

```
http://localhost:8000/docs
```

Checklist:
- [ ] Swagger UI loads
- [ ] Can see all 3 endpoints: /chat, /health, /reindex
- [ ] Try-it-out button works

---

## Troubleshooting Checklist

### If Backend Won't Start

- [ ] Is Ollama running? → `ollama serve`
- [ ] Is port 8000 free? → Check `lsof -i :8000`
- [ ] Is Python venv activated? → Check `which python`
- [ ] Are dependencies installed? → Check `pip list`
- [ ] Check error messages in terminal

### If Vector DB Won't Initialize

- [ ] Is knowledge base path correct? → Check `config.yaml`
- [ ] Do markdown files exist? → `ls knowledge_base/*/`
- [ ] Do markdown files have frontmatter? → Check first file
- [ ] Is `data/` directory writable? → Check permissions

### If Queries Are Slow

- [ ] Is this first run? → First inference is slower (~1min)
- [ ] Is Ollama using 100% CPU? → Normal on CPU
- [ ] Try reducing `max_tokens` in config.yaml
- [ ] Check if other apps consuming CPU

### If No Results Found

- [ ] Is confidence threshold too high? → Check `config.yaml` (default 0.7)
- [ ] Is vector DB properly indexed? → Call `/stats` endpoint
- [ ] Try simpler query with fewer keywords
- [ ] Reindex KB: `curl -X POST http://localhost:8000/reindex`

---

## Optimization Checklist

After verifying everything works:

### Memory Optimization
- [ ] Adjust `rag.context_window` based on available RAM
- [ ] Monitor peak memory usage during queries
- [ ] Consider lighter quantization if needed

### Speed Optimization
- [ ] Note typical response times
- [ ] Reduce `top_k` if too slow (3 instead of 5)
- [ ] Reduce `max_tokens` for shorter responses
- [ ] Increase `temperature` for faster generation

### Quality Optimization
- [ ] Adjust `similarity_threshold` for better recall
- [ ] Test response quality with different temp values
- [ ] Verify source citations are accurate

---

## Production Deployment Checklist

When ready to deploy beyond localhost:

### Security
- [ ] Add API authentication (API keys or JWT)
- [ ] Enable CORS restrictions (not "*")
- [ ] Setup HTTPS/SSL certificates
- [ ] Implement rate limiting
- [ ] Sanitize user inputs

### Operations
- [ ] Setup log rotation
- [ ] Configure monitoring/alerting
- [ ] Document troubleshooting procedures
- [ ] Create backup strategy for vector DB
- [ ] Plan KB update schedule

### Infrastructure
- [ ] Deploy to production server
- [ ] Use process manager (PM2, systemd, etc.)
- [ ] Setup reverse proxy (Nginx, Apache)
- [ ] Configure auto-restart on failure
- [ ] Setup health check endpoints

### Testing
- [ ] Load test with concurrent users
- [ ] Test error scenarios
- [ ] Verify data privacy compliance
- [ ] Document known limitations

---

## Daily Operations

### Before Starting

- [ ] Ensure Ollama service will start (check systemd/startup)
- [ ] Verify backend startup script is executable
- [ ] Check disk space is available (> 1GB)

### Morning Startup

```bash
# Terminal 1
ollama serve

# Terminal 2
cd /mnt/sda1/Polygon/primebot/chatbot
source venv/bin/activate
cd backend
python3 app.py

# Terminal 3
cd /mnt/sda1/Polygon/primebot/chatbot/frontend
python3 -m http.server 8001
```

- [ ] All services started
- [ ] No error messages
- [ ] System responding to health checks

### Monitoring

- [ ] Check logs periodically: `tail -f backend/logs/chatbot.log`
- [ ] Monitor memory usage: `top` or Task Manager
- [ ] Test with sample query: "Test query" in UI
- [ ] Verify response times are normal

### Updates

When updating KB:
1. Add/modify markdown files in `knowledge_base/`
2. Trigger reindex: `curl -X POST http://localhost:8000/reindex`
3. Verify new content is searchable
4. Test related queries

---

## Shutdown Checklist

When done for the day:

- [ ] Close browser/UI
- [ ] Stop backend server (Ctrl+C in Terminal 2)
- [ ] Stop HTTP server if running (Ctrl+C in Terminal 3)
- [ ] Stop Ollama (Ctrl+C in Terminal 1)
- [ ] Verify all processes stopped: `ps aux | grep python`

---

## Weekly Maintenance

- [ ] Review logs for errors: `cat backend/logs/chatbot.log`
- [ ] Check disk usage: `du -sh data/`
- [ ] Verify vector DB integrity: `curl http://localhost:8000/stats`
- [ ] Test query quality with sample questions
- [ ] Update KB if products changed

---

## Emergency Procedures

### If System Crashes

1. Kill all Python processes: `pkill -f python`
2. Kill Ollama: `pkill -f ollama`
3. Check system resources: `free -h`, `df -h`
4. Restart from "Shutdown Checklist" above
5. Restart from "Morning Startup" above

### If Vector DB Corrupted

```bash
# 1. Stop backend
# 2. Delete corrupted DB
rm -rf data/vector_db/*

# 3. Restart backend (auto-reindex)
python3 app.py
```

### If Model Won't Download

```bash
# Check internet connection
ping ollama.ai

# Try again
ollama pull qwen3-1.7b-q4

# If still fails, use alternative model
ollama pull qwen3-1.7b-q3  # Slightly smaller
```

---

## Success Indicators ✅

When everything is working:

- ✅ Ollama serving at localhost:11434
- ✅ Backend running at localhost:8000
- ✅ Frontend responsive at localhost:8001
- ✅ Health check returns "healthy"
- ✅ Queries return answers in 10-30s
- ✅ Sources are cited in responses
- ✅ No error messages in logs
- ✅ Memory usage stable (~10-11GB)
- ✅ UI shows user-friendly responses

**If all ✅ checked → System is ready!**

---

**Status: Ready for Use 🚀**

For questions, see:
- QUICKSTART.md - Fast setup
- README.md - Full documentation  
- IMPLEMENTATION_SUMMARY.md - Architecture details
