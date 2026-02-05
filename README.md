# Story of My Life

A local-first personal temporal knowledge graph with Swarm-based multi-agent architecture.

## Overview

Story of My Life (SOML) is a personal knowledge system that captures, organizes, and surfaces your life's information. It uses a multi-agent Swarm architecture to:

- **Ingest** natural language input into structured knowledge
- **Store** everything as portable markdown files (source of truth)
- **Query** using semantic search and graph traversal
- **Proactively** detect open loops and surface insights

## Quick Start

### Prerequisites

- Docker 24.0+
- Python 3.12+
- OpenAI API key (or Anthropic)

### Setup

```bash
# Clone the repository
git clone https://github.com/your-org/story-of-my-life.git
cd story-of-my-life

# Copy environment template and add your API key
cp .env.example .env
# Edit .env and add SOML_OPENAI_API_KEY=sk-...

# Build and start
make setup

# Start all services
make start
```

### Basic Usage

```bash
# Add new content
make cli ARGS='add "Met with Cayden yesterday to discuss Atitan investment"'

# Ask questions
make cli ARGS='ask "When did I last meet with Cayden?"'

# List people
make cli ARGS='people'

# See open loops (things needing attention)
make cli ARGS='open-loops'

# Get weekly summary
make cli ARGS='summarize week'
```

## Architecture

### Swarm Agents

The system uses a multi-agent Swarm architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                       ORCHESTRATOR                           │
│                    (Routes requests)                         │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  INGESTION    │    │ INTELLIGENCE  │    │  INTERFACE    │
│  SWARM        │    │ SWARM         │    │  SWARM        │
├───────────────┤    ├───────────────┤    ├───────────────┤
│ • TimeExtract │    │ • EntityResolv│    │ • Query       │
│ • EntityExtract│   │ • OpenLoopDet │    │ • Conversation│
│ • IntentClass │    │ • MemorySynth │    │ • Correction  │
│ • RelProposer │    │               │    │               │
└───────┬───────┘    └───────┬───────┘    └───────┬───────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             ▼
                   ┌───────────────┐
                   │ STORAGE SWARM │
                   ├───────────────┤
                   │ • DocWriter   │
                   │ • Indexer     │
                   │ • GraphBuilder│
                   │ • Embedder    │
                   └───────────────┘
```

### Storage Hierarchy

**Markdown files are the canonical source of truth.** All other storage is derived and can be rebuilt.

| Layer | Purpose |
|-------|---------|
| Markdown | Source of truth (human-readable, portable) |
| SQLite | Document registry, audit log, full-text search |
| Neo4j | Graph relationships + vector embeddings |

### Core Entities

- **Person** — People in your life with disambiguation
- **Project** — Multi-stakeholder efforts with goals
- **Goal** — Personal desired outcomes
- **Event** — Specific occurrences in time
- **Note** — Captured observations and thoughts
- **Memory** — Synthesized summaries
- **Relationship** — Connections between entities

## CLI Commands

```bash
soml add "content"       # Add new content
soml ask "question"      # Query knowledge graph
soml people [name]       # List or look up people
soml projects            # List active projects
soml goals               # List active goals
soml timeline [--days N] # Show recent timeline
soml open-loops          # Things needing attention
soml summarize [period]  # Summarize day/week/month
soml status              # System status
soml init                # Initialize data directory
```

## MCP Integration

SOML can be used as an MCP (Model Context Protocol) server with Claude or Cursor:

```json
// ~/.config/claude/claude_desktop_config.json
{
  "mcpServers": {
    "story-of-my-life": {
      "command": "soml-mcp"
    }
  }
}
```

## Project Structure

```
story-of-my-life/
├── src/soml/
│   ├── agents/           # Swarm agents
│   │   ├── ingestion/    # Time, Entity, Intent, Relationship
│   │   ├── storage/      # DocWriter, Indexer, Graph, Embedder
│   │   ├── intelligence/ # EntityResolver, OpenLoop, Memory
│   │   └── interface/    # Query, Conversation, Correction
│   ├── storage/          # Storage layer (markdown, sqlite, neo4j)
│   ├── core/             # Types, config, context
│   ├── cli.py            # Command-line interface
│   ├── mcp_server.py     # MCP server
│   └── openclaw.py       # Openclaw integration
├── tests/                # Test suite
├── scripts/              # Utility scripts
├── docker-compose.yml    # Container orchestration
└── Makefile              # Development commands
```

## Data Portability

All data is stored as markdown files with YAML frontmatter:

```yaml
---
id: uuid
type: person
created_at: 2026-02-03T10:00:00
updated_at: 2026-02-03T10:00:00
source: agent
confidence: 0.9
links: []
tags: [investor, board]
---

# Cayden

_Atitan board member_

Key advisor for investment strategy...
```

Relationships are encoded as wikilinks: `[[uuid|Display Name]]`

**Reconstruction Guarantee:** The entire graph can be rebuilt from just the markdown files.

## Open Loop System

SOML proactively detects things that need your attention:

- **Quiet relationships** — Haven't connected in a while
- **Stalled projects** — No recent activity
- **Stalled goals** — No progress made
- **Open commitments** — Mentioned but not followed up

These are surfaced via `soml open-loops` or through Openclaw notifications.

## Development

```bash
# Run tests
make test

# Lint code
make lint

# Type check
make typecheck

# Open shell
make shell

# Rebuild indices from markdown
make rebuild
```

## Configuration

Environment variables (prefix with `SOML_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_DIR` | `~/story-of-my-life` | Data directory |
| `OPENAI_API_KEY` | - | OpenAI API key |
| `ANTHROPIC_API_KEY` | - | Anthropic API key |
| `DEFAULT_LLM` | `openai` | LLM provider |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection |
| `CONFIDENCE_THRESHOLD` | `0.8` | Auto-action threshold |

## License

MIT

