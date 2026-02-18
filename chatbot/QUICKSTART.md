# ⚡ Quick Start Guide - Prime Bank Chatbot

## 🚀 Get Running in 5 Minutes

### Prerequisites
- Python 3.9+
- Ollama installed
- 16GB RAM
- ~5GB free disk space

---

## Step 1: Download Ollama + Qwen Model

```bash
# Download Ollama from: https://ollama.ai
# Then run in terminal:

ollama serve
# Keep this terminal open!
```

In another terminal:
```bash
ollama pull qwen3-1.7b-q4
# Downloads ~1.5GB model
```

---

## Step 2: Setup Backend (First Time Only)

```bash
cd /mnt/sda1/Polygon/primebot/chatbot

# Linux/Mac:
bash run.sh setup

# Windows:
run.bat
# Select option 1
```

This installs all Python dependencies (~2-3 min).

---

## Step 3: Start Backend Server

**Terminal 1** (Ollama - keep running):
```bash
ollama serve
```

**Terminal 2** (Backend):
```bash
cd /mnt/sda1/Polygon/primebot/chatbot

# Linux/Mac:
source venv/bin/activate
cd backend
python3 app.py

# Windows:
venv\Scripts\activate
cd backend
python app.py
```

Wait for:
```
Starting server at http://0.0.0.0:8000
```

---

## Step 4: Open Frontend

**Option A**: Direct file (easiest)
```bash
# Linux/Mac:
open /mnt/sda1/Polygon/primebot/chatbot/frontend/index.html

# Windows:
start /mnt/sda1/Polygon/primebot/chatbot/frontend/index.html

# Or copy-paste in browser:
file:///mnt/sda1/Polygon/primebot/chatbot/frontend/index.html
```

**Option B**: Via HTTP Server (Terminal 3)
```bash
cd /mnt/sda1/Polygon/primebot/chatbot/frontend
python3 -m http.server 8001

# Open: http://localhost:8001/index.html
```

---

## ✅ Done!

Start chatting! Try:
- "Tell me about Visa Gold"
- "What Islamic options do you have?"
- "Best card for travel?"

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| "Ollama not available" | Run `ollama serve` in another terminal |
| "Model not found" | Run `ollama pull qwen3-1.7b-q4` |
| "Cannot connect to backend" | Check backend is running at step 3 |
| "Out of memory" | Close other apps, reduce context in config.yaml |
| "Very slow responses" | Normal on CPU (10-30s). GPU would be faster |

---

## 📁 Project Structure

```
chatbot/
├── backend/
│   ├── app.py              # FastAPI server
│   ├── rag_pipeline.py     # RAG orchestration
│   ├── vector_db.py        # Chroma integration
│   ├── chunker.py          # Knowledge base processing
│   ├── requirements.txt    # Python dependencies
│   └── logs/               # Server logs
├── frontend/
│   └── index.html          # Single-file UI
├── data/
│   └── vector_db/          # Embeddings storage
├── config.yaml             # Configuration
├── README.md               # Full documentation
├── run.sh                  # Linux/Mac startup
└── run.bat                 # Windows startup
```

---

## 🔧 Customization

Edit `config.yaml` to adjust:

```yaml
chunking:
  chunk_size: 350          # Bigger = more context, slower
  chunk_overlap: 100       # Overlap between chunks

rag:
  top_k: 5                 # More = better accuracy, slower
  similarity_threshold: 0.7 # Lower = more permissive

llm:
  temperature: 0.7         # Lower = factual, higher = creative
  max_tokens: 512          # Longer = slower responses
```

---

## 📚 Adding New Products

1. Create markdown file in `knowledge_base/` 
2. Add YAML frontmatter with metadata
3. Write content in markdown
4. Run reindex: `curl -X POST http://localhost:8000/reindex`

See [README.md](README.md) for details.

---

## 📊 Check Status Anytime

```bash
# Health check
curl http://localhost:8000/health

# Statistics
curl http://localhost:8000/stats

# API documentation
open http://localhost:8000/docs
```

---

## 🎯 Next Steps

After verifying everything works:

1. **Add more products** to knowledge_base/
2. **Customize system prompt** in config.yaml
3. **Adjust response quality** settings
4. **Deploy to server** when ready for production

---

## ❓ FAQ

**Q: Why is it slow?**
A: Running 1.7B parameter LLM on CPU. Normal: 10-30s per response. For speed, need GPU.

**Q: Can I use different model?**
A: Yes. In config.yaml, change `model_name` to any Ollama model.

**Q: Does it remember previous conversations?**
A: No. Session-level only (stateless). Add history in future version.

**Q: Can I deploy this?**
A: Yes. Push to server with similar specs (16GB+ RAM). Use Nginx/Apache as reverse proxy.

**Q: What about privacy?**
A: Data stays local. No cloud calls. Perfect for sensitive banking info.

---

**🎉 Enjoy your chatbot!**

For help, see [README.md](README.md) or check logs at `backend/logs/chatbot.log`
