Story of My Life

Local-First Knowledge Agent for Human Memory, Time, and Meaning

⸻

1. User Promise (What this actually gives you)

The system guarantees three capabilities that do not exist together anywhere else:

Capability	Concrete outcome
Total recall	Ask: “When did I last talk to Alex and what did we decide?” and get an exact, sourced answer
Time coherence	Ask: “What was happening in my life when I started Brightfield?” and get a narrative across people, goals, and events
Self-continuity	Ask: “What have I been avoiding?” or “What patterns are repeating?” and get answers grounded in your own data

This is not a note-taking app.
It is a life state engine.

⸻

2. Local-First Guarantees

Property	Guarantee
Storage	All data stored in a user-owned directory (~/story-of-my-life/)
Format	Human-readable JSON + Markdown + SQLite
Portability	Can be mounted into any agent runtime

Local models optional. API-dependent (OpenAI, Anthropic) for most users.
No SaaS dependency on the data layer — the user owns their memory.

⸻

3. Core Ontology (What exists)

Everything in the system is one of these:

Primitives

Note         – raw user input
Event        – something that happened or will happen
Person       – someone in your life
Relationship – typed edge between entities
Goal         – personal desired future state
Project      – long-running effort involving multiple goals and potentially multiple stakeholders
Memory       – synthesized canonical summary

All objects share:

{
  "id": "uuid",
  "created_at": "timestamp",
  "updated_at": "timestamp",
  "source": "user | agent | import",
  "confidence": 0.0 – 1.0,
  "links": [ids of related objects]
}

Person objects additionally have:

{
  "name": "...",
  "disambiguator": "one-liner context, e.g. 'Cayden from Atitan board'"
}

Confidence Semantics

The confidence field (0.0–1.0) is computed from:
	•	Extraction certainty — NLP model confidence in the extraction
	•	Source reliability — user input = 1.0, agent inference = lower
	•	User confirmation — confirmed items boost to 1.0

Low confidence triggers confirmation prompts. Confidence affects retrieval ranking.


⸻

4. Ingestion Pipeline (How text becomes memory)

Every input passes through:

Raw text
 → Time extraction
 → Entity extraction
 → Intent classification
 → Object creation
 → Graph linking
 → Vector embedding
 → Persistent storage

Example

Input:

"Met with Cayden yesterday to discuss Atitan investment strategy. Determined we will seek a lead investor who can help guide our manufacturing and distribution activities as we just completed final prototypes of the splitR product."

Produces:
	•	Event(date=yesterday, type=meeting)
	•	Person(Cayden)
	•	Project(Atitan)
	•	Project(splitR)
	•	Goal(seek lead investor for manufacturing/distribution guidance)
	•	Relationship(user ↔ Cayden, collaborator)
	•	Relationship(Cayden ↔ Atitan, collaborator)
	•	Relationship(splitR ↔ Atitan, product)
	•	Relationship(Goal ↔ Atitan, strategic)
	•	Relationship(Goal ↔ splitR, strategic)
	•	Note(text=original input)
	•	Graph edges linking all of the above

Entity Resolution

When the system encounters a name (e.g., "Alex"), it must determine whether this refers to an existing Person or a new one.

The agent detects potential duplicates based on:
	•	Name similarity (exact match, nickname variants, partial matches)
	•	Context overlap (shared projects, relationships, topics)
	•	Temporal proximity (mentioned in same timeframe)

When ambiguous, the agent proposes via natural language:
	•	"Is this the same Alex from the Brightfield project, or someone new?"
	•	"I see two people named Sarah — Sarah Chen (coworker) and Sarah Miller (friend). Which one?"

The user confirms, and the system updates the disambiguator field to prevent future confusion.

Even with identical names, the system can track distinct people using the disambiguator and graph context.

⸻

5. Three-Layer Storage Architecture

Layer	Purpose	Contents
Markdown files	Source of truth	Canonical human-readable documents (portable)
SQLite	Registry + Index	Document registry, audit log, full-text search
Neo4j	Queryable cache	Graph relationships + vector embeddings

All objects have shared IDs across all three layers.

Edits propagate:
	•	Markdown update → re-index SQLite → re-embed Neo4j → old versions preserved

Storage Hierarchy

Markdown files    → Canonical source of truth (human-readable, portable)
SQLite            → Document registry, audit log, full-text search index
Neo4j             → Graph relationships + vector embeddings (queryable cache)

The system guarantees that Neo4j and SQLite can be fully reconstructed from markdown files alone. A capable agent with access only to the markdown directory can rebuild the entire graph and index.

⸻

6. Portable Document Format

Every entity in the system is stored as a markdown file with structured YAML frontmatter.

YAML Frontmatter

---
id: uuid
type: person | project | goal | event | note | memory
created_at: ISO timestamp
updated_at: ISO timestamp
source: user | agent | import
confidence: 0.0-1.0
links: [list of related document ids]
tags: [topic tags]
---

Wikilinks

Relationships between documents are encoded as wikilinks within the content body:

[[document-id|display name]]

Example: "Met with [[person-cayden|Cayden]] to discuss [[proj-atitan|Atitan]]."

These links are parseable by any agent for graph reconstruction without requiring database access.

Content Body

The remainder of the file is human-readable markdown containing the actual data. This ensures:
	•	Human readability without tooling
	•	Version control compatibility (git-friendly)
	•	Tool-agnostic portability

Hierarchical Document Splitting

When a document grows too large (agent judgment, typically ~500+ lines), it splits into parent and child documents.

Parent Document (e.g., projects/atitan.md):

---
id: proj-atitan
type: project
children:
  - proj-atitan-timeline
  - proj-atitan-goals
  - proj-atitan-meetings
---
# Atitan

Overview content...

## Sections
- [[proj-atitan-timeline|Timeline]]
- [[proj-atitan-goals|Goals]]
- [[proj-atitan-meetings|Meetings]]

Child Document (e.g., projects/atitan/timeline.md):

---
id: proj-atitan-timeline
type: project-section
parent: proj-atitan
---
# Atitan Timeline
...

This allows projects like Atitan to scale indefinitely — meetings can further split by date, goals can split by quarter, etc. — while maintaining a navigable structure.

⸻

7. Document Registry

SQLite maintains an index of all markdown documents:

Field	Purpose
id	UUID matching frontmatter
path	Filesystem path to markdown file
type	Document type (person, project, etc.)
parent_id	For hierarchical documents
checksum	Content hash for change detection
last_indexed	When graph/vector were last synced

The registry enables:
	•	Fast lookup without parsing all files
	•	Change detection for incremental re-indexing
	•	Parent-child relationship tracking

Directory Structure

~/story-of-my-life/
├── people/
│   ├── cayden.md
│   └── marcus.md
├── projects/
│   ├── atitan.md
│   └── atitan/
│       ├── timeline.md
│       ├── goals.md
│       └── meetings/
│           ├── 2026-01-15.md
│           └── 2026-02-01.md
├── goals/
├── events/
├── notes/
├── memories/
├── .deleted/
└── .index/
    └── registry.sqlite

The .index/ folder contains derived data (SQLite registry). The .deleted/ folder holds soft-deleted files awaiting hard delete or recovery.

⸻

8. Data Lifecycle

Soft Delete

Default deletion is soft delete:
	•	Markdown file moved to .deleted/ folder with timestamp suffix
	•	Object marked as deleted in SQLite registry
	•	Neo4j node marked as deleted
	•	Cascades to linked objects (also soft deleted)
	•	Fully recoverable until hard delete

Hard Delete

User-initiated permanent removal:
	•	Markdown file removed from filesystem
	•	Removes object from all stores (Neo4j + SQLite registry)
	•	Cascaded deletions also become permanent
	•	Audit log entry preserved (records that deletion occurred, not the content)

Corrections

When a user corrects an object:
	•	Original version preserved in audit log
	•	Correction propagates: re-embed → update graph edges
	•	Confidence boosted to 1.0 (user-confirmed)

Audit Log

All mutations logged with:
	•	Timestamp
	•	Before state
	•	After state
	•	Source (user correction, agent inference, import)

Reconstruction Guarantee

The system guarantees:
	•	Any agent with access to the markdown directory can reconstruct the full graph
	•	No data exists only in Neo4j or SQLite — they are derived caches
	•	Document edits update the markdown first, then propagate to indices
	•	Loss of Neo4j or SQLite is recoverable; loss of markdown is not

⸻

9. Time & Truth Model

Every Event has:

{
  "time": { "start": "...", "end": "..." },
  "state": "observed | planned | cancelled | revised | uncertain",
  "revisions": [previous versions]
}

So the system knows:
	•	What really happened
	•	What was planned but didn’t
	•	How beliefs evolved

⸻

10. Relationship Intelligence

Relationship Types

Relationships are organized into categories, each with extensible types:

Personal (user ↔ person):
	•	friend | partner | coworker | family | mentor | mentee | acquaintance | unknown

Structural (entity ↔ entity):
	•	depends_on | related_to | part_of | created_by | owns | product_of | strategic

Users can extend types within categories via natural language.

Each Relationship maintains:

{
  "category": "personal | structural",
  "type": "...",
  "strength": 0–100,
  "last_interaction": "...",
  "shared_projects": [...],
  "sentiment": -1.0 to +1.0
}

Strength is computed from:
	•	Interaction frequency
	•	Recency
	•	Emotional tone
	•	Shared context

Decay applies over time.

Graph Building

Relationships are rigid by default — the system does not auto-create or modify relationship types without user involvement.

The agent proposes new relationships through natural language dialogue:
	•	"It looks like Cayden is involved with Atitan — should I track them as a collaborator?"
	•	"You've mentioned Sarah in several family contexts. Want me to mark her as family?"

The user confirms, rejects, or refines. This builds the graph state collaboratively over time.

Manual editing is supported (users can directly add/modify relationships), but this is not the normal flow. The primary interface is conversational.

This allows:
	•	Who matters now
	•	Who is fading
	•	Who belongs to which chapter of life

⸻

11. Goals & Projects

Goal vs Project

A Goal is a personal desired future state — something the user wants to achieve or maintain.

A Project is a large effort comprised of multiple goals. Projects can involve multiple stakeholders and span extended timeframes.

Example:
	•	Project: "Launch splitR"
	•	Goals within: "Complete prototype", "Secure lead investor", "Establish distribution"

Each Goal has:

{
  "why": "...",
  "metric": "...",
  "cadence": "daily | weekly | monthly",
  "next_action": "...",
  "status": "active | stalled | abandoned",
  "parent_project": "optional project id"
}

Each Project has:

{
  "name": "...",
  "stakeholders": [person ids],
  "goals": [goal ids],
  "status": "active | stalled | completed | abandoned"
}

The agent proposes goals by detecting:
	•	Repeated desires
	•	Avoidance patterns
	•	Stress clusters
	•	Unclosed loops

Hard safety boundary:
No diagnosis, no medical or psychological treatment claims.

⸻

12. Open Loop System

The agent maintains its own internal scheduling layer — not surfaced to the user by default.

It continuously identifies open loops:
	•	Relationships that have gone quiet
	•	Projects without recent activity
	•	Goals with stalled progress
	•	Commitments mentioned but not followed up
	•	Questions asked but never answered

Based on this analysis, the agent schedules itself to re-query the user at appropriate intervals:
	•	"You mentioned checking in with Marcus about the partnership — any update?"
	•	"It's been 3 weeks since you last mentioned the fitness goal. Still on track?"
	•	"Cayden came up a lot in January but hasn't appeared since. Everything okay there?"

The user doesn't manage this schedule. The agent determines timing based on:
	•	Relationship strength and decay curves
	•	Project urgency and stated deadlines
	•	Historical patterns of user engagement
	•	Emotional weight of the loop

This creates a sense of continuity — the system remembers what's unfinished and gently resurfaces it.

Openclaw Integration

Story of My Life integrates with Openclaw (https://openclaw.im/) as a skill/plugin.

The system exposes open loops as structured data:

{
  "loop_id": "...",
  "type": "relationship | project | goal | commitment | question",
  "entity_id": "...",
  "urgency": 0–100,
  "suggested_timing": "timestamp",
  "prompt": "..."
}

Openclaw handles:
	•	Scheduling and cron execution
	•	Triggering the skill at appropriate times
	•	Delivering prompts to the user via configured channels (WhatsApp, Telegram, etc.)

On trigger, Openclaw invokes the Story of My Life skill, which surfaces the relevant prompt and awaits user response.

⸻

13. Memory Synthesis

The agent periodically runs:

Notes → Events → Weekly summaries → Monthly summaries → Life chapters

It collapses redundancy into Memory objects.

Example:
	•	48 notes about CES
→ one Memory:

“CES 2026 was the first public demo of splitR and marked Atitan’s transition from prototype to product.”

⸻

14. Agent Interface (MCP-ready)

The backend exposes:

recall(query, time_range, people)
timeline(range, facets)
summarize(period, focus)
people(person_id)
relationship_graph(person_id)
goals()
projects()
what_changed()
what_am_I_avoiding()
open_loops()                         — returns scheduled open loops for Openclaw
correct(object_id, correction)       — applies user correction, propagates changes

Internally retrieval is:

vector search
 → graph expansion
 → document grounding
 → answer


⸻

15. UX Scope (v1)
	•	Quick capture (text)
	•	Timeline view
	•	People view
	•	Ask mode (chat/search)

No social feed. No cloud dashboard.

⸻

16. Deployment

Runs as:
	•	Local daemon
	•	CLI
	•	MCP server
	•	Embedded library inside other agents
	•	Openclaw skill (for scheduling and notifications)

Same data. Same brain.

⸻

17. Implementation Strategy

Build vs Integrate vs Delegate

The system is built with clear boundaries between custom logic (core IP) and external integrations.

Build (Core IP)

Component	Reasoning
Relationship Proposer	Confidence thresholds, proposal logic, graph building rules
Open Loop Detector	Decay curves, urgency scoring, loop identification
Memory Synthesizer	Note collapse logic, summary generation, hierarchy
Answer Grounding	Source citation, response formatting, retrieval ranking
Correction Propagation	Audit log, cascade updates, confidence adjustment
Document Schema	Frontmatter spec, wikilink format, directory structure

Integrate (Use Libraries/APIs)

Component	Tool/Library
Time parsing	dateparser, parsedatetime
Entity extraction	spaCy NER or LLM structured output
Entity resolution	dedupe, recordlinkage libraries
Embeddings	OpenAI text-embedding-3-small, Cohere
Vector storage	Neo4j vector index or LanceDB
Graph database	Neo4j
Document database	SQLite
LLM inference	OpenAI, Anthropic APIs

Delegate to Openclaw

Component	Reasoning
Scheduling/Cron	Openclaw has robust job scheduling
Message routing	Multi-platform (WhatsApp, Telegram, Discord, etc.)
Conversation state	Multi-turn context management
Notification delivery	Push to user's preferred channel
Skill triggering	Event-driven invocation of agents

Service Architecture

┌─────────────────────────────────────────────────────────────────────┐
│                        APPLICATIONS                                  │
├─────────────────────────────────────────────────────────────────────┤
│  CLI App              MCP Clients            Openclaw Skill          │
│  (soml-cli)           (Claude, Cursor)       (scheduling/notifs)     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      MCP SERVER (soml-mcp)                          │
├─────────────────────────────────────────────────────────────────────┤
│  recall()  timeline()  summarize()  correct()  open_loops()         │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      CORE LIBRARY (soml-core)                       │
├─────────────────────────────────────────────────────────────────────┤
│  Ingestion  │  Storage  │  Intelligence  │  Query                   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA LAYER                                    │
├─────────────────────────────────────────────────────────────────────┤
│  Markdown (source of truth)  │  SQLite (registry)  │  Neo4j (cache) │
└─────────────────────────────────────────────────────────────────────┘

Package Structure

soml-core	Python library with all business logic
soml-mcp	MCP server wrapping soml-core
soml-cli	Command-line interface

⸻

18. Future Improvements

The following capabilities are planned for future versions:

Additional Import Sources
	•	Apple Notes
	•	Notion
	•	Google Keep
	•	Roam Research
	•	Logseq
	•	Calendar imports (Google Calendar, Apple Calendar)
	•	Contact imports

Note: Obsidian import is supported in v1.

Encryption at Rest
	•	AES-256 encryption with user-held key
	•	Key never transmitted off device
	•	Transparent encryption/decryption layer

Cloud Sync
	•	Optional, pluggable sync backends
	•	Supported targets: iCloud, Syncthing, Git, S3
	•	End-to-end encrypted sync (requires encryption layer)
	•	Conflict resolution for multi-device scenarios

⸻

What this actually is

This is not a journaling app.
This is a personal temporal knowledge graph with memory and agency.

It lets a human have something machines already have:
persistent internal state across time.