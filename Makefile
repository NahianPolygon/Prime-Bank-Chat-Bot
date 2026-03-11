.PHONY: up down rebuild logs clean help restart stop build restart-clean restart-tail backend-logs backend-logs-new backend-logs-recent ollama-logs health shell-backend shell-ollama ps

COMPOSE_FILE := chatbot/docker-compose.yml

help:
	@echo "Prime Bank Chatbot - Docker Commands"
	@echo "===================================="
	@echo "make up           - Start all containers"
	@echo "make down         - Stop all containers"
	@echo "make rebuild      - Rebuild and start all containers"
	@echo "make restart      - Restart all containers (shows recent logs)"
	@echo "make restart-clean - Restart and show last 20 logs only"
	@echo "make restart-tail  - Restart and follow new logs (Ctrl+C to exit)"
	@echo "make stop         - Stop containers without removing"
	@echo "make logs         - View container logs (follow mode)"
	@echo "make build        - Build images without starting"
	@echo "make clean        - Remove stopped containers and images"
	@echo "make ps           - Show running containers"
	@echo ""
	@echo "Log Commands:"
	@echo "make backend-logs        - Backend logs (all history)"
	@echo "make backend-logs-new    - Backend logs (new only)"
	@echo "make backend-logs-recent - Backend logs (last 50 lines + new)"
	@echo "make ollama-logs         - Ollama logs"

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
	@sleep 2
	@echo "✅ Containers restarted (showing last 10 logs):"
	@docker compose -f $(COMPOSE_FILE) logs --tail 10

restart-clean:
	@echo "🔄 Restarting containers (clean logs)..."
	docker compose -f $(COMPOSE_FILE) restart
	@echo "Waiting for startup..."
	@sleep 3
	@echo "✅ Containers restarted (showing last 20 logs):"
	@docker compose -f $(COMPOSE_FILE) logs --tail 20

restart-tail:
	@echo "🔄 Restarting containers (live tail mode)..."
	docker compose -f $(COMPOSE_FILE) restart
	@sleep 2
	@echo "✅ Following new logs (Ctrl+C to exit)..."
	@docker compose -f $(COMPOSE_FILE) logs -f --tail 0

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
	@echo "📋 Backend logs (all history):"
	docker compose -f $(COMPOSE_FILE) logs -f backend

backend-logs-new:
	@echo "📋 Backend logs (new only - Ctrl+C to exit):"
	docker compose -f $(COMPOSE_FILE) logs --tail 0 -f backend

backend-logs-recent:
	@echo "📋 Backend logs (last 50 lines + new - Ctrl+C to exit):"
	docker compose -f $(COMPOSE_FILE) logs --tail 50 -f backend

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
