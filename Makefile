.PHONY: up down rebuild logs clean help restart stop build

COMPOSE_FILE := chatbot/docker-compose.yml

help:
	@echo "Prime Bank Chatbot - Docker Commands"
	@echo "===================================="
	@echo "make up       - Start all containers"
	@echo "make down     - Stop all containers"
	@echo "make rebuild  - Rebuild and start all containers"
	@echo "make restart  - Restart all containers"
	@echo "make stop     - Stop containers without removing"
	@echo "make logs     - View container logs (follow mode)"
	@echo "make build    - Build images without starting"
	@echo "make clean    - Remove stopped containers and images"
	@echo "make ps       - Show running containers"

up:
	@echo "🚀 Starting containers..."
	docker compose -f $(COMPOSE_FILE) up -d
	@echo "✅ Containers started"
	@make ps

down:
	@echo "🛑 Stopping containers..."
	docker compose -f $(COMPOSE_FILE) down
	@echo "✅ Containers stopped"

stop:
	@echo "⏸️  Stopping containers..."
	docker compose -f $(COMPOSE_FILE) stop
	@echo "✅ Containers stopped (not removed)"

rebuild:
	@echo "🔨 Rebuilding and starting containers..."
	docker compose -f $(COMPOSE_FILE) down
	docker compose -f $(COMPOSE_FILE) build --no-cache
	docker compose -f $(COMPOSE_FILE) up -d
	@echo "✅ Rebuild complete"
	@make ps

restart:
	@echo "🔄 Restarting containers..."
	docker compose -f $(COMPOSE_FILE) restart
	@echo "✅ Containers restarted"
	@make ps

build:
	@echo "🔨 Building images..."
	docker compose -f $(COMPOSE_FILE) build
	@echo "✅ Build complete"

logs:
	@echo "📋 Following container logs (Ctrl+C to exit)..."
	docker compose -f $(COMPOSE_FILE) logs -f

ps:
	@echo "📊 Container Status:"
	@docker compose -f $(COMPOSE_FILE) ps

clean:
	@echo "🧹 Cleaning up stopped containers and images..."
	docker compose -f $(COMPOSE_FILE) down -v
	@echo "✅ Cleanup complete"

# Additional utility targets
backend-logs:
	@echo "📋 Backend logs:"
	docker compose -f $(COMPOSE_FILE) logs -f backend

ollama-logs:
	@echo "📋 Ollama logs:"
	docker compose -f $(COMPOSE_FILE) logs -f ollama

health:
	@echo "🏥 Checking backend health..."
	@curl -s http://localhost:8000/health | python3 -m json.tool || echo "Backend not responding"

shell-backend:
	@echo "🐚 Opening backend shell..."
	docker compose -f $(COMPOSE_FILE) exec backend /bin/bash

shell-ollama:
	@echo "🐚 Opening ollama shell..."
	docker compose -f $(COMPOSE_FILE) exec ollama /bin/bash
