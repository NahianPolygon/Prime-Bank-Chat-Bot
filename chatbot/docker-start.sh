#!/bin/bash

# PrimeBot Docker Quick Start Script

set -e

echo "╔════════════════════════════════════════╗"
echo "║  PrimeBot Bank Chatbot - Docker Setup  ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker Desktop."
    exit 1
fi

echo "✓ Docker is installed"

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✓ .env created (customize if needed)"
fi

echo ""
echo "🔨 Building backend image..."
docker build -t primebot-backend -f Dockerfile .

echo ""
echo "🚀 Starting services..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

echo ""
echo "✓ Services started!"
echo ""
echo "═══════════════════════════════════════"
echo "🎯 Access Points:"
echo "═══════════════════════════════════════"
echo "  Backend API:    http://localhost:8000"
echo "  API Docs:       http://localhost:8000/docs"
echo "  Ollama:         http://localhost:11434"
echo ""
echo "Next steps:"
echo "1. Pull an LLM model:"
echo "   docker-compose exec ollama ollama pull mistral"
echo ""
echo "2. Initialize knowledge base:"
echo "   docker-compose exec backend python -c \"from vector_db import initialize_knowledge_base; initialize_knowledge_base('/app/knowledge_base')\""
echo ""
echo "3. View logs:"
echo "   docker-compose logs -f backend"
echo ""
echo "4. Stop services:"
echo "   docker-compose down"
echo ""
echo "Happy chatting! 🤖"
