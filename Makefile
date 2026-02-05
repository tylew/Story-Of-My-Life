# Story of My Life - Development Commands
.PHONY: setup start stop restart logs test lint clean rebuild shell neo4j-shell dev dev-build

# ============================================
# Setup & Installation
# ============================================

setup:
	@echo "🚀 Setting up Story of My Life..."
	docker-compose build
	docker-compose up -d neo4j
	@echo "⏳ Waiting for Neo4j to be ready..."
	@sleep 15
	docker-compose run --rm app python scripts/init_neo4j.py
	@echo "✅ Setup complete!"

setup-dev:
	@echo "🚀 Setting up development environment..."
	docker-compose -f docker-compose.dev.yml build
	docker-compose -f docker-compose.dev.yml up -d neo4j
	@echo "⏳ Waiting for Neo4j to be ready..."
	@sleep 10
	docker-compose -f docker-compose.dev.yml run --rm api python scripts/init_neo4j.py
	@echo "✅ Dev setup complete! Run 'make dev' to start."

# ============================================
# Development Mode (Hot Reload)
# ============================================

dev:
	@echo "🔥 Starting development servers with hot reload..."
	docker-compose -f docker-compose.dev.yml up

dev-build:
	@echo "🔨 Rebuilding dev containers..."
	docker-compose -f docker-compose.dev.yml build

dev-stop:
	@echo "🔴 Stopping dev services..."
	docker-compose -f docker-compose.dev.yml down

dev-logs:
	docker-compose -f docker-compose.dev.yml logs -f

dev-logs-api:
	docker-compose -f docker-compose.dev.yml logs -f api

dev-logs-frontend:
	docker-compose -f docker-compose.dev.yml logs -f frontend

dev-shell:
	docker-compose -f docker-compose.dev.yml run --rm cli /bin/bash

dev-cli:
	docker-compose -f docker-compose.dev.yml run --rm cli python -m soml.cli $(ARGS)

# ============================================
# Service Management (Production)
# ============================================

start:
	@echo "🟢 Starting all services..."
	docker-compose up -d

stop:
	@echo "🔴 Stopping all services..."
	docker-compose down

restart: stop start

logs:
	docker-compose logs -f

logs-app:
	docker-compose logs -f app

logs-neo4j:
	docker-compose logs -f neo4j

# ============================================
# Development
# ============================================

shell:
	docker-compose run --rm app /bin/bash

neo4j-shell:
	docker-compose exec neo4j cypher-shell -u neo4j -p somlpassword123

# Run CLI commands
cli:
	docker-compose run --rm app python -m soml.cli $(ARGS)

# Run MCP server
mcp:
	docker-compose up mcp

# ============================================
# Testing & Linting
# ============================================

test:
	docker-compose run --rm app pytest tests/ -v --cov=soml

test-unit:
	docker-compose run --rm app pytest tests/unit/ -v

test-integration:
	docker-compose run --rm app pytest tests/integration/ -v

lint:
	docker-compose run --rm app ruff check src/ tests/
	docker-compose run --rm app ruff format --check src/ tests/

lint-fix:
	docker-compose run --rm app ruff check --fix src/ tests/
	docker-compose run --rm app ruff format src/ tests/

typecheck:
	docker-compose run --rm app mypy src/

# ============================================
# Data Management
# ============================================

# Rebuild indices from markdown (source of truth)
rebuild:
	docker-compose run --rm app python scripts/rebuild_indices.py

# Import from Obsidian vault
import-obsidian:
	docker-compose run --rm app python scripts/import_obsidian.py $(VAULT_PATH)

# Backup data
backup:
	@echo "📦 Creating backup..."
	docker-compose run --rm app tar -czvf /data/backup-$$(date +%Y%m%d-%H%M%S).tar.gz \
		/data/people /data/projects /data/goals /data/events /data/notes /data/memories

# ============================================
# Cleanup
# ============================================

clean:
	docker-compose down -v
	docker system prune -f

clean-data:
	@echo "⚠️  This will delete all data. Are you sure? [y/N]"
	@read -r confirm && [ "$$confirm" = "y" ] && \
		docker-compose down -v && \
		docker volume rm story-of-my-life_soml_data story-of-my-life_soml_index || true

# ============================================
# Development Helpers
# ============================================

# Watch for changes and run tests
watch-test:
	docker-compose run --rm app pytest-watch tests/ -v

# Generate test coverage report
coverage:
	docker-compose run --rm app pytest --cov=soml --cov-report=html tests/
	@echo "📊 Coverage report: open htmlcov/index.html"

# ============================================
# Production
# ============================================

build-prod:
	docker build -t soml:latest --target production .

# ============================================
# Help
# ============================================

help:
	@echo "Story of My Life - Available Commands"
	@echo ""
	@echo "═══════════════════════════════════════════════"
	@echo "  DEVELOPMENT (Hot Reload)"
	@echo "═══════════════════════════════════════════════"
	@echo "  make setup-dev      - First-time dev setup"
	@echo "  make dev            - Start with hot reload 🔥"
	@echo "  make dev-build      - Rebuild dev containers"
	@echo "  make dev-stop       - Stop dev services"
	@echo "  make dev-logs       - View dev logs"
	@echo "  make dev-shell      - Open dev shell"
	@echo ""
	@echo "═══════════════════════════════════════════════"
	@echo "  PRODUCTION"
	@echo "═══════════════════════════════════════════════"
	@echo "  make setup          - Initial setup"
	@echo "  make start          - Start all services"
	@echo "  make stop           - Stop all services"
	@echo "  make restart        - Restart all services"
	@echo "  make logs           - View all logs"
	@echo ""
	@echo "═══════════════════════════════════════════════"
	@echo "  CLI & TOOLS"
	@echo "═══════════════════════════════════════════════"
	@echo "  make shell          - Open app shell"
	@echo "  make cli ARGS='...' - Run CLI command"
	@echo "  make dev-cli ARGS=  - Run CLI in dev mode"
	@echo "  make mcp            - Start MCP server"
	@echo ""
	@echo "═══════════════════════════════════════════════"
	@echo "  TESTING"
	@echo "═══════════════════════════════════════════════"
	@echo "  make test           - Run all tests"
	@echo "  make lint           - Check linting"
	@echo "  make lint-fix       - Fix linting issues"
	@echo ""
	@echo "═══════════════════════════════════════════════"
	@echo "  DATA"
	@echo "═══════════════════════════════════════════════"
	@echo "  make rebuild        - Rebuild indices from markdown"
	@echo "  make backup         - Create data backup"
	@echo ""
	@echo "═══════════════════════════════════════════════"
	@echo "  Quick Start:"
	@echo "    1. make setup-dev"
	@echo "    2. make dev"
	@echo "    3. Open http://localhost:3000"
	@echo "═══════════════════════════════════════════════"

