# Prime Bank Chatbot - Setup & Deployment Guide

## 📋 Overview

A **local RAG-based chatbot** for Prime Bank customer support. Runs on a 16GB laptop using:
- **LLM**: Qwen3-1.7B Q4 (1.7B parameters, quantized)
- **Vector DB**: Chroma (in-process, lightweight)
- **Embeddings**: all-MiniLM-L6-v2 (22M parameters)
- **Backend**: FastAPI (Python)
- **Frontend**: Single HTML5 file

**Response Time**: 10-30 seconds per query (CPU-only inference)

---

## 🛠️ Prerequisites

### System Requirements
- **OS**: Linux/Mac/Windows with Python 3.9+
- **RAM**: 16GB minimum
- **Disk**: 5GB free space (for models + vector DB)
- **CPU**: Modern multi-core processor

### Software Requirements

1. **Python 3.9+**
   ```bash
   python3 --version
   ```

2. **Ollama** (for running Qwen3-1.7B locally)
   - Download: https://ollama.ai
   - Install and ensure `ollama serve` is accessible

3. **Git** (to clone repository)

---

## 📦 Installation

### Step 1: Set Up Python Environment

```bash
# Navigate to project directory
cd /mnt/sda1/Polygon/primebot/chatbot

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip
```

### Step 2: Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

**Installation time**: ~5-10 minutes (depends on internet speed)

### Step 3: Download & Setup Ollama + Qwen Model

```bash
# Start Ollama service (in a separate terminal)
ollama serve

# In another terminal, pull Qwen3-1.7B Q4
ollama pull qwen3-1.7b-q4

# Verify model is downloaded
ollama list
```

**Download size**: ~1.5 GB
**Time**: 5-15 minutes (depends on internet)

### Step 4: Verify Knowledge Base Structure

Your knowledge base should be organized as:
```
/mnt/sda1/Polygon/primebot/
├── knowledge_base/
│   ├── conventional/
│   │   └── credit/i_need_a_credit_card/
│   └── islami/
│       └── credit/i_need_a_credit_card/
└── chatbot/
    ├── backend/
    ├── frontend/
    └── data/
```

---

## 🚀 Running the Chatbot

### Terminal 1: Start Ollama Service

```bash
ollama serve
```

Wait for it to say "Listening on 127.0.0.1:11434"

### Terminal 2: Start Backend Server

```bash
cd /mnt/sda1/Polygon/primebot/chatbot/backend

# Ensure virtual environment is activated
source ../venv/bin/activate

# Run FastAPI server
python3 app.py
```

You should see:
```
Starting server at http://0.0.0.0:8000
API docs available at http://localhost:8000/docs
```

### Terminal 3: Open Frontend

```bash
# Open the HTML file in your browser
# Option A: Direct open
open /mnt/sda1/Polygon/primebot/chatbot/frontend/index.html

# Option B: Using Python HTTP server
cd /mnt/sda1/Polygon/primebot/chatbot/frontend
python3 -m http.server 8001
# Then open: http://localhost:8001/index.html
```

---

## 🧪 Testing the Chatbot

### Health Check
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

### First Query

In the web interface, try these queries:
- "Tell me about Visa Gold credit card"
- "Which Islamic banking options do you have?"
- "What are eligibility requirements for Platinum cards?"
- "Compare Visa Gold and Mastercard Platinum"

---

## ⚙️ Configuration

All settings in `config.yaml`:

### Chunking Settings
```yaml
chunking:
  chunk_size: 350        # Tokens per chunk
  chunk_overlap: 100     # Token overlap (20%)
```

### Vector DB
```yaml
vector_db:
  provider: "chroma"
  persist_directory: "./data/vector_db"
```

### RAG Settings
```yaml
rag:
  top_k: 5              # Chunks to retrieve
  similarity_threshold: 0.7  # Confidence cutoff (0-1)
  context_window: 2048  # Max tokens for context
```

### LLM Settings
```yaml
llm:
  provider: "ollama"
  model_name: "qwen3-1.7b-q4"
  base_url: "http://localhost:11434"
  max_tokens: 512
  temperature: 0.7      # Creativity (0=deterministic, 1=creative)
```

**Note**: Adjust `temperature` lower (0.3) for more factual answers, higher (0.9) for creative answers.

---

## 📊 Reindexing Knowledge Base

### Automatic (First Run)

On first run, `app.py` automatically chunks and indexes all markdown files.

### Manual Reindexing

If you add/update markdown files:

```bash
# Via API
curl -X POST http://localhost:8000/reindex \
  -H "Content-Type: application/json" \
  -d '{"force": true}'

# Or in Python
import requests
response = requests.post('http://localhost:8000/reindex', json={'force': true})
print(response.json())
```

---

## 🔍 Troubleshooting

### Issue: "Ollama not available"

**Solution:**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama if not running
ollama serve
```

### Issue: "Model not found"

**Solution:**
```bash
# Download model
ollama pull qwen3-1.7b-q4

# Verify
ollama list
```

### Issue: Out of Memory (OOM)

**Solution:**
- Reduce `context_window` in config.yaml (from 2048 to 1024)
- Reduce `top_k` (from 5 to 3)
- Use `qwen3-1.7b-q3` instead of q4 (smaller quantization)
- Close other applications

### Issue: Slow Response Times

**Normal** on CPU: 10-30 seconds

**If slower:**
- Check CPU usage: `top` or Task Manager
- Reduce `chunk_size` for faster retrieval
- Lower `max_tokens` for shorter responses

### Issue: Vector DB Not Indexing

**Solution:**
```bash
# Check vector DB directory
ls -la ./data/vector_db/

# Force reindex
curl -X POST http://localhost:8000/reindex \
  -H "Content-Type: application/json" \
  -d '{"force": true}'

# Check logs
tail -f ./logs/chatbot.log
```

---

## 📈 Performance Optimization

### For 16GB Laptop

**Memory Allocation**:
```
Total: 16GB
├── OS + System: 2GB
├── Ollama (Qwen3-1.7B Q4): 8-10GB
├── Vector DB + Embeddings: 2GB
└── FastAPI + Python: 2-3GB
```

**To Reduce Memory Usage:**
1. Use `qwen3-1.7b-q3` instead of q4
2. Reduce `embedding_batch_size` in vector_db.py
3. Use smaller embedding model (e.g., `all-MiniLM-L6-v2` is already small)

**To Improve Speed:**
1. Increase `top_k` for better results (trade-off: slower)
2. Lower `temperature` for faster deterministic generation
3. Reduce `max_tokens` for shorter responses

---

## 📚 API Endpoints

### POST /chat
Send a query to the chatbot.

**Request:**
```json
{
  "query": "Tell me about Visa Gold credit card",
  "session_id": "user_123"
}
```

**Response:**
```json
{
  "query": "Tell me about Visa Gold credit card",
  "answer": "Visa Gold offers...",
  "sources": [
    {
      "product": "Visa Gold Credit Card",
      "section": "Key Features",
      "confidence": "85%"
    }
  ],
  "confidence": 0.87,
  "timestamp": "2024-02-17T10:30:45",
  "success": true
}
```

### GET /health
Check system health.

**Response:**
```json
{
  "status": "healthy",
  "vector_db_size": 45,
  "model": "Qwen3-1.7B Q4 (via Ollama)"
}
```

### GET /stats
Get system statistics.

**Response:**
```json
{
  "collection_name": "bank_products",
  "total_chunks": 45,
  "embedding_model": "all-MiniLM-L6-v2",
  "llm_model": "Qwen3-1.7B Q4 (via Ollama)",
  "vector_db": "Chroma"
}
```

### POST /reindex
Reindex knowledge base.

**Request:**
```json
{
  "force": true
}
```

**Response:**
```json
{
  "status": "success",
  "chunks_indexed": 45,
  "message": "Successfully indexed 45 chunks"
}
```

---

## 🔐 Security Notes

### For Production Deployment

1. **Enable Authentication**
   - Add API key validation
   - Implement JWT tokens

2. **Rate Limiting**
   - Prevent abuse with request throttling
   - Use libraries like `slowapi`

3. **Input Validation**
   - Sanitize user inputs
   - Prevent prompt injection

4. **HTTPS**
   - Deploy with SSL/TLS certificates
   - Use reverse proxy (nginx, Apache)

5. **Logging & Monitoring**
   - Log all queries (anonymized)
   - Monitor resource usage
   - Set up alerts for errors

### Current Setup
- No authentication (localhost testing only)
- No rate limiting
- CORS enabled for all origins
- Suitable for **development & testing only**

---

## 📝 Adding New Products

### Step 1: Create Markdown File

Create a new markdown file in `knowledge_base/[banking_type]/[category]/[subcategory]/`

Example: `knowledge_base/conventional/loan/personal_loan/personal_loan_basic.md`

### Step 2: Add YAML Frontmatter

```yaml
---
product_id: LOAN_001
product_name: Personal Loan Basic
banking_type: conventional
category: loan
tier: basic
employment_suitable: ['salaried', 'business_owner']
keywords: []
use_cases: ['debt_consolidation', 'education', 'home_renovation']
---
```

### Step 3: Add Content

Use clear markdown structure:
```markdown
# Personal Loan Basic

**Tagline:** Your Financial Companion

## Overview
...

## Eligibility Requirements
...

## Key Features
...
```

### Step 4: Reindex

```bash
curl -X POST http://localhost:8000/reindex \
  -H "Content-Type: application/json" \
  -d '{"force": true}'
```

---

## 🎯 Next Steps & Future Improvements

### Phase 2 (Future)
- [ ] Multi-turn conversations with memory
- [ ] User authentication
- [ ] Admin dashboard for analytics
- [ ] Support for Bengali language
- [ ] Integration with CRM system
- [ ] Feedback collection & model fine-tuning

### Phase 3 (Future)
- [ ] Larger LLM (7B+ parameters with GPU acceleration)
- [ ] Document QA (upload custom PDFs)
- [ ] Scheduled reindexing
- [ ] A/B testing for response quality
- [ ] Multi-language support

---

## 📞 Support & Documentation

- **API Docs**: http://localhost:8000/docs (Swagger UI)
- **Logs**: `./logs/chatbot.log`
- **Config**: `./config.yaml`

---

## 📄 License & Notes

This chatbot is built specifically for Prime Bank Bangladesh products and internal use.

**Key Assumptions:**
- All product information is accurate as of knowledge base creation date
- Regular updates to KB are required for product changes
- 16GB RAM minimum recommended
- CPU-only inference (no GPU required)

---

## 🎓 Architecture Overview

```
User Query
    ↓
Frontend (HTML+JS)
    ↓
FastAPI Backend (port 8000)
    ├── Intent Analysis (rule-based)
    ├── Vector DB Search (Chroma)
    │   ├── Query Embedding (all-MiniLM-L6-v2)
    │   ├── Cosine Similarity Search
    │   └── Confidence Filtering
    ├── RAG Context Building
    └── LLM Generation (Qwen3-1.7B via Ollama)
        ↓
    Response with Sources
    ↓
Frontend Display
    ↓
User Sees Answer
```

---

**Happy chatting! 🚀**
