# Story of My Life — Environment Setup Proposal

Development environment for the Swarm-based MVP.

⸻

## 1. Overview

This document outlines the environment setup for developing and running Story of My Life using:
- **Python** — Core language
- **Openclaw** — Agent orchestration, scheduling, and notifications
- **Neo4j** — Graph database + vector storage
- **SQLite** — Document registry and audit log
- **OpenAI/Anthropic** — LLM inference

⸻

## 2. System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | macOS 12+, Linux, Windows 11 | macOS 14+ |
| Python | 3.11+ | 3.12 |
| RAM | 8GB | 16GB |
| Storage | 10GB | 50GB (for Neo4j) |
| Docker | 24.0+ | Latest |

⸻

## 3. Installation Steps

### 3.1 Clone Repository

```bash
git clone https://github.com/your-org/story-of-my-life.git
cd story-of-my-life
```

### 3.2 Install Python Environment

```bash
# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

### 3.3 Install Openclaw

```bash
# Install Openclaw globally
curl -fsSL https://openclaw.im/install.sh | bash

# Verify installation
openclaw --version
```

### 3.4 Start Neo4j (Docker)

```bash
# Create docker-compose.yml for Neo4j
cat > docker-compose.yml << 'EOF'
version: '3.8'
services:
  neo4j:
    image: neo4j:5.15-community
    ports:
      - "7474:7474"  # HTTP
      - "7687:7687"  # Bolt
    environment:
      - NEO4J_AUTH=neo4j/somlpassword
      - NEO4J_PLUGINS=["apoc"]
      - NEO4J_dbms_security_procedures_unrestricted=apoc.*
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs

volumes:
  neo4j_data:
  neo4j_logs:
EOF

# Start Neo4j
docker-compose up -d neo4j

# Wait for Neo4j to be ready
echo "Waiting for Neo4j..."
until curl -s http://localhost:7474 > /dev/null; do
  sleep 2
done
echo "Neo4j is ready!"
```

### 3.5 Configure Environment

```bash
# Create .env file
cat > .env << 'EOF'
# LLM Configuration
OPENAI_API_KEY=sk-your-key-here
# Or for Anthropic:
# ANTHROPIC_API_KEY=sk-ant-your-key-here

# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=somlpassword

# Storage Configuration
SOML_DATA_DIR=~/story-of-my-life

# Openclaw Configuration
OPENCLAW_SKILL_NAME=story-of-my-life
EOF

# Load environment
source .env
```

### 3.6 Initialize Data Directory

```bash
# Create data directory structure
mkdir -p ~/story-of-my-life/{people,projects,goals,events,notes,memories,.deleted,.index}

# Initialize SQLite registry
python -c "from soml.storage.registry import RegistryIndexer; RegistryIndexer('$HOME/story-of-my-life/.index/registry.sqlite')"
```

### 3.7 Initialize Neo4j Schema

```bash
# Run schema initialization
python scripts/init_neo4j.py
```

```python
# scripts/init_neo4j.py
from neo4j import GraphDatabase
import os

driver = GraphDatabase.driver(
    os.environ['NEO4J_URI'],
    auth=(os.environ['NEO4J_USER'], os.environ['NEO4J_PASSWORD'])
)

with driver.session() as session:
    # Create constraints
    session.run("CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE")
    
    # Create vector index for embeddings
    session.run("""
        CREATE VECTOR INDEX entity_embeddings IF NOT EXISTS
        FOR (e:Entity) ON e.embedding
        OPTIONS {indexConfig: {
            `vector.dimensions`: 1536,
            `vector.similarity_function`: 'cosine'
        }}
    """)
    
    # Create full-text index
    session.run("""
        CREATE FULLTEXT INDEX entity_content IF NOT EXISTS
        FOR (e:Entity) ON EACH [e.name, e.content]
    """)

driver.close()
print("Neo4j schema initialized!")
```

### 3.8 Register Openclaw Skill

```bash
# Create Openclaw skill configuration
cat > openclaw-skill.yaml << 'EOF'
name: story-of-my-life
description: Personal temporal knowledge graph with memory and agency
version: 0.1.0

entry_point: soml.interface.openclaw:skill_handler

schedules:
  - name: detect_open_loops
    cron: "0 9 * * *"
    description: Daily open loop detection

  - name: synthesize_weekly
    cron: "0 10 * * 0"
    description: Weekly memory synthesis

  - name: scan_duplicates
    cron: "0 11 * * 0"
    description: Weekly entity resolution scan

tools:
  - name: recall
    description: Recall information from memory
  - name: add_note
    description: Add a new note to memory
  - name: timeline
    description: Get timeline of events
  - name: summarize
    description: Summarize a time period
EOF

# Register with Openclaw
openclaw skill register --config openclaw-skill.yaml
```

⸻

## 4. Project Structure

```
story-of-my-life/
├── .env                          # Environment variables (git-ignored)
├── .venv/                        # Python virtual environment
├── docker-compose.yml            # Neo4j container
├── openclaw-skill.yaml           # Openclaw skill config
├── pyproject.toml                # Python package config
├── README.md
├── SETUP.md                      # This file
│
├── docs/
│   ├── init.md                   # Product spec
│   ├── tech-arch-swarm.md        # Swarm architecture
│   └── agents/                   # Agent documentation
│       ├── orchestrator.md
│       ├── ingestion.md
│       ├── storage.md
│       ├── intelligence.md
│       └── interface.md
│
├── src/
│   └── soml/                     # Main package
│       ├── __init__.py
│       ├── cli.py                # CLI entry point
│       ├── mcp_server.py         # MCP server
│       ├── openclaw.py           # Openclaw skill handlers
│       │
│       ├── agents/               # Agent implementations
│       │   ├── __init__.py
│       │   ├── orchestrator.py
│       │   ├── ingestion/
│       │   │   ├── __init__.py
│       │   │   ├── time_extractor.py
│       │   │   ├── entity_extractor.py
│       │   │   ├── intent_classifier.py
│       │   │   └── relationship_proposer.py
│       │   ├── storage/
│       │   │   ├── __init__.py
│       │   │   ├── document_writer.py
│       │   │   ├── registry_indexer.py
│       │   │   ├── graph_builder.py
│       │   │   └── vector_embedder.py
│       │   ├── intelligence/
│       │   │   ├── __init__.py
│       │   │   ├── entity_resolver.py
│       │   │   ├── open_loop_detector.py
│       │   │   └── memory_synthesizer.py
│       │   └── interface/
│       │       ├── __init__.py
│       │       ├── query_agent.py
│       │       ├── conversation_agent.py
│       │       └── correction_agent.py
│       │
│       ├── core/                 # Core utilities
│       │   ├── __init__.py
│       │   ├── config.py
│       │   ├── context.py        # SwarmContext
│       │   └── types.py          # Shared types
│       │
│       └── storage/              # Storage layer
│           ├── __init__.py
│           ├── markdown.py       # Markdown I/O
│           ├── registry.py       # SQLite registry
│           ├── graph.py          # Neo4j client
│           └── audit.py          # Audit log
│
├── tests/
│   ├── conftest.py               # Pytest fixtures
│   ├── test_agents/
│   ├── test_storage/
│   └── test_integration/
│
└── scripts/
    ├── init_neo4j.py             # Initialize Neo4j schema
    ├── rebuild_indices.py        # Rebuild from markdown
    └── import_obsidian.py        # Import from Obsidian
```

⸻

## 5. Python Dependencies

```toml
# pyproject.toml
[project]
name = "soml"
version = "0.1.0"
description = "Story of My Life - Personal temporal knowledge graph"
requires-python = ">=3.11"
dependencies = [
    # Core
    "pydantic>=2.0",
    "python-dotenv>=1.0",
    
    # LLM
    "openai>=1.0",
    "anthropic>=0.18",
    
    # Storage
    "neo4j>=5.0",
    "pyyaml>=6.0",
    
    # NLP
    "dateparser>=1.2",
    "spacy>=3.7",
    
    # MCP
    "mcp>=0.1",
    
    # CLI
    "typer>=0.9",
    "rich>=13.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.0",
    "ruff>=0.2",
    "mypy>=1.8",
]

[project.scripts]
soml = "soml.interface.cli:app"
soml-mcp = "soml.interface.mcp_server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

⸻

## 6. Configuration

### 6.1 Core Configuration

```python
# src/soml/core/config.py
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    # Data
    data_dir: Path = Path.home() / "story-of-my-life"
    
    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    
    # LLM
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    default_llm: str = "openai"  # or "anthropic"
    
    # Embeddings
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    
    # Agent settings
    confidence_threshold: float = 0.8
    relationship_decay_days: int = 14
    project_decay_days: int = 7
    
    class Config:
        env_file = ".env"
        env_prefix = "SOML_"

settings = Settings()
```

### 6.2 Logging Configuration

```python
# src/soml/core/logging.py
import logging
import sys

def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("soml.log")
        ]
    )
```

⸻

## 7. Development Workflow

### 7.1 Running Locally

```bash
# Terminal 1: Start Neo4j
docker-compose up neo4j

# Terminal 2: Start MCP server (for Claude/Cursor integration)
soml-mcp

# Terminal 3: Use CLI
soml add "Met with Cayden today to discuss Atitan"
soml ask "When did I last talk to Cayden?"
soml people
soml projects
```

### 7.2 Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=soml --cov-report=html

# Specific tests
pytest tests/test_agents/test_ingestion.py -v
```

### 7.3 Linting

```bash
# Format code
ruff format src tests

# Check linting
ruff check src tests

# Type checking
mypy src
```

⸻

## 8. Openclaw Integration

### 8.1 Start Openclaw Daemon

```bash
# Start Openclaw
openclaw start

# Check status
openclaw status

# View logs
openclaw logs -f
```

### 8.2 Test Skill Locally

```bash
# Test skill invocation
openclaw skill test story-of-my-life --function detect_open_loops

# Simulate scheduled run
openclaw skill run story-of-my-life detect_open_loops
```

### 8.3 Configure Messaging

```bash
# Connect Telegram (or other platform)
openclaw connect telegram

# Set preferred channel for notifications
openclaw config set story-of-my-life.notification_channel telegram
```

⸻

## 9. MCP Integration

### 9.1 Claude Desktop Integration

```json
// ~/Library/Application Support/Claude/claude_desktop_config.json
{
  "mcpServers": {
    "story-of-my-life": {
      "command": "soml-mcp",
      "args": []
    }
  }
}
```

### 9.2 Cursor Integration

```json
// .cursor/mcp.json
{
  "servers": {
    "story-of-my-life": {
      "command": "soml-mcp"
    }
  }
}
```

⸻

## 10. Quick Start Commands

```bash
# One-liner setup (after cloning)
make setup

# Start all services
make start

# Stop all services
make stop

# Run full test suite
make test

# Rebuild indices from markdown
make rebuild
```

### Makefile

```makefile
# Makefile
.PHONY: setup start stop test rebuild

setup:
	python -m venv .venv
	.venv/bin/pip install -e ".[dev]"
	docker-compose up -d neo4j
	sleep 10
	python scripts/init_neo4j.py
	mkdir -p ~/story-of-my-life/{people,projects,goals,events,notes,memories,.deleted,.index}

start:
	docker-compose up -d
	openclaw start

stop:
	docker-compose down
	openclaw stop

test:
	pytest --cov=soml

rebuild:
	python scripts/rebuild_indices.py

import-obsidian:
	python scripts/import_obsidian.py $(VAULT_PATH)
```

⸻

## 11. Troubleshooting

### Neo4j Connection Issues

```bash
# Check if Neo4j is running
docker-compose ps

# View Neo4j logs
docker-compose logs neo4j

# Reset Neo4j data
docker-compose down -v
docker-compose up -d neo4j
```

### Openclaw Issues

```bash
# Check Openclaw status
openclaw status

# Restart Openclaw
openclaw restart

# View skill logs
openclaw logs story-of-my-life
```

### Missing Dependencies

```bash
# Download spaCy model
python -m spacy download en_core_web_sm

# Verify all imports
python -c "from soml import *"
```

⸻

## 12. Next Steps

After setup is complete:

1. **Import existing notes** (if using Obsidian):
   ```bash
   make import-obsidian VAULT_PATH=~/Documents/Obsidian/MyVault
   ```

2. **Add your first note**:
   ```bash
   soml add "Starting Story of My Life today"
   ```

3. **Test queries**:
   ```bash
   soml ask "What have I captured so far?"
   ```

4. **Enable Openclaw notifications**:
   ```bash
   openclaw connect telegram
   ```

5. **Start using with Claude/Cursor** via MCP integration

⸻

## 13. Support

- **Documentation**: See `docs/` folder
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions

