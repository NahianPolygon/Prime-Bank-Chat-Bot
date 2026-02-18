# PrimeBot Bank Chatbot - Docker Setup Guide

Complete containerized setup for the bank chatbot with backend API, local LLM, and optional frontend.

## Prerequisites

- Docker Desktop (v20.10+)
- Docker Compose (v2.0+)
- At least 8GB RAM available for Docker
- 20GB disk space (for LLM models)

## Quick Start

### 1. Clone and Setup

```bash
cd /mnt/sda1/Polygon/primebot/chatbot
cp .env.example .env  # Optional: customize if needed
```

### 2. Build and Start Services

```bash
# Build backend image
docker-compose build

# Start all services in background
docker-compose up -d

# Or start with logs visible
docker-compose up
```

### 3. Initialize Knowledge Base (First Time Only)

```bash
# Connect to backend container
docker-compose exec backend bash

# Inside container:
cd /app/backend
python -c "from vector_db import initialize_knowledge_base; initialize_knowledge_base('/app/knowledge_base')"

# Exit
exit
```

### 4. Pull LLM Model

```bash
# Connect to Ollama
docker-compose exec ollama ollama pull mistral

# Or pull other models:
# docker-compose exec ollama ollama pull llama2
# docker-compose exec ollama ollama pull neural-chat
```

### 5. Access Services

- **Backend API**: http://localhost:8000
- **Ollama**: http://localhost:11434
- **Frontend** (if running): http://localhost:3000
- **API Docs**: http://localhost:8000/docs

## Docker Compose Services

### Backend
- **Image**: Built from Dockerfile
- **Port**: 8000
- **Environment**: Configured for Ollama integration
- **Volumes**: 
  - Backend code (hot-reload)
  - Knowledge base
  - ChromaDB data persistence
  - Prompts folder

### Ollama
- **Image**: ollama/ollama:latest
- **Port**: 11434
- **Volume**: Model storage persistence

### Frontend (Optional)
- **Image**: node:20-alpine
- **Port**: 3000
- **Note**: Requires Node.js setup in frontend folder

## Useful Commands

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f ollama
```

### Stop Services
```bash
docker-compose down
```

### Stop and Remove Data
```bash
docker-compose down -v
```

### Rebuild Backend
```bash
docker-compose build --no-cache backend
```

### Run Commands in Container
```bash
# Backend shell
docker-compose exec backend bash

# Ollama commands
docker-compose exec ollama ollama list
docker-compose exec ollama ollama pull llama2
```

### Health Check
```bash
# Check if backend is healthy
curl http://localhost:8000/health

# Check if Ollama is running
curl http://localhost:11434/api/tags
```

## Project Structure

```
chatbot/
├── Dockerfile              # Backend container definition
├── docker-compose.yml      # Service orchestration
├── .dockerignore           # Docker build exclusions
├── .env.example            # Environment template
├── backend/
│   ├── app.py             # FastAPI application
│   ├── requirements.txt    # Python dependencies
│   ├── agents/            # Modular agents (6 files)
│   ├── tools/             # Tool utilities
│   ├── vector_db/         # ChromaDB integration
│   ├── pipelines/         # RAG & CrewAI pipelines
│   └── prompts/           # LLM prompt templates
├── frontend/              # React/Vue frontend
├── knowledge_base/        # Product markdown files
└── README.md
```

## Development Workflow

### Make Code Changes
The backend volume is mounted with `--reload`, so changes auto-reload:

```bash
# Edit backend code
vim backend/app.py

# Changes apply automatically
# Check logs: docker-compose logs backend
```

### Add Python Dependencies
```bash
# 1. Add to requirements.txt
echo "new-package==1.0.0" >> backend/requirements.txt

# 2. Rebuild image
docker-compose build backend

# 3. Restart service
docker-compose up backend
```

### Access Database

```bash
# Inside backend container
cd /app/data/chroma
ls -la  # View ChromaDB files
```

## Troubleshooting

### Backend Won't Start
```bash
docker-compose logs backend
# Check for Python import errors or missing dependencies
```

### Ollama Not Responding
```bash
docker-compose logs ollama
# Ensure ollama service started successfully

# Restart Ollama
docker-compose restart ollama
```

### Out of Memory
```bash
# Increase Docker memory in Docker Desktop settings
# Or run selective services:
docker-compose up backend ollama  # Skip frontend if not needed
```

### Port Already in Use
```bash
# Change ports in docker-compose.yml
# Or stop conflicting services:
lsof -i :8000  # Find process using port
kill -9 <PID>
```

### Slow Performance
- Increase Docker resources in Desktop settings
- Use smaller LLM model (neural-chat vs llama2)
- Check disk space availability

## Production Considerations

### Security
- Use `.env` file with secure variables
- Set `DEBUG=false` in production
- Use reverse proxy (nginx) in front
- Enable CORS restrictions

### Performance
- Use GPU acceleration (nvidia-docker)
- Implement request queuing
- Add caching layer (Redis)
- Use production ASGI server (gunicorn)

### Persistence
- Set proper volume mount permissions
- Regular backups of ChromaDB data
- Monitor disk usage

### Monitoring
- Add health checks to all services
- Implement logging aggregation
- Use container orchestration (Kubernetes)

## API Examples

### Health Check
```bash
curl http://localhost:8000/health
```

### Chat Endpoint
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "I need a credit card"}'
```

### API Documentation
```
http://localhost:8000/docs
```

## Support & Issues

For issues or questions:
1. Check Docker logs: `docker-compose logs -f`
2. Verify all services are running: `docker-compose ps`
3. Ensure ports are available
4. Check disk space and memory
