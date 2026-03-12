# GraphMem

Graph-based long-term memory for Claude Code. Store, query, and traverse a temporal knowledge graph that persists across all your sessions and projects.

Built on [graphiti-core](https://github.com/getzep/graphiti) by [Zep](https://github.com/getzep) — the engine that does all the heavy lifting: entity extraction, temporal knowledge graphs, hybrid search, and fact invalidation. GraphMem is a CLI wrapper that makes it easy to use from Claude Code.

## Why GraphMem?

Claude Code's built-in memory (CLAUDE.md) is flat text. GraphMem gives you:

- **Cross-project, cross-session** — one graph shared across all your projects
- **Relationship-aware retrieval** — "What depends on the auth module?" traverses graph edges
- **Per-node RAG** — each entity has an embedding for semantic search, then graph traversal expands context
- **Temporal awareness** — tracks when facts were learned, when they became outdated, and why
- **Privacy** — all data stored locally on your machine

## Quick Start

```bash
# Install
pip install git+https://github.com/simonfallman/graphmem.git

# Interactive setup (picks DB, embedding provider, LLM provider)
graphmem init

# Test connectivity
graphmem ping

# Store a memory
graphmem add "The auth module uses JWT with RS256 signing"

# Search memories
graphmem query "how does authentication work?"

# Get expanded context via graph traversal
graphmem context "auth module" --depth 3

# Update (old conflicting facts auto-invalidated)
graphmem update "Switched from JWT to OAuth2 for authentication"
```

On first run, graphmem automatically:
- Installs the `/longmemory` slash command into Claude Code
- Appends proactive memory instructions to `~/.claude/CLAUDE.md`
- Sets up the live graph viewer at `~/.graphmem/graph-live.html`

## Installation

```bash
# Install from GitHub
pip install git+https://github.com/simonfallman/graphmem.git

# Or clone and install locally
git clone https://github.com/simonfallman/graphmem.git
cd graphmem
pip install -e ".[all]"

# Or install with specific providers only
pip install -e ".[openai]"        # OpenAI embeddings + LLM
pip install -e ".[bedrock]"       # AWS Bedrock
pip install -e ".[local]"         # Local sentence-transformers (offline)
pip install -e ".[anthropic]"     # Anthropic Claude API
```

## Configuration

Run `graphmem init` for interactive setup, or manually create `~/.graphmem/.env`:

```env
GRAPHMEM_DB_BACKEND=kuzu          # kuzu (local, default) or neo4j (server)
GRAPHMEM_DB_PATH=~/.graphmem/db
GRAPHMEM_EMBEDDER=openai          # openai, bedrock, or local
GRAPHMEM_LLM=openai               # openai, anthropic, bedrock, or ollama
OPENAI_API_KEY=sk-...
```

### Supported Providers

| Component | Options |
|-----------|---------|
| Graph DB | **Kuzu** (local, default) · Neo4j (server) |
| Embeddings | OpenAI · AWS Bedrock Titan · Local (sentence-transformers) |
| LLM (extraction) | OpenAI · Anthropic Claude · AWS Bedrock · Ollama (local) |

## CLI Commands

| Command | Description |
|---------|-------------|
| `graphmem init` | Interactive setup |
| `graphmem ping` | Test connectivity |
| `graphmem add "text"` | Store a memory (auto-extracts entities & facts) |
| `graphmem query "text"` | Hybrid search (semantic + keyword + graph) |
| `graphmem context "topic"` | Expanded graph traversal around a topic |
| `graphmem update "text"` | Add info that supersedes old facts |
| `graphmem remove <id>` | Remove an entity |
| `graphmem remove-edge <id>` | Remove a fact/edge |
| `graphmem list episodes` | List recent episodes |
| `graphmem list entities` | List entities |
| `graphmem status` | Graph stats |
| `graphmem export` | Export graph as JSON |
| `graphmem viz` | Live graph visualization (WebSocket server) |
| `graphmem viz --live` | Open serverless live viewer (no server required) |
| `graphmem install-command` | Install `/longmemory` slash command for Claude Code |

## Claude Code Integration

### Automatic setup

Just run any `graphmem` command. It silently installs three things into your Claude Code environment:

1. **`~/.claude/CLAUDE.md`** — global instructions telling Claude to proactively query and save memories in every session, across every project
2. **`~/.claude/commands/longmemory.md`** — the `/longmemory` slash command
3. **`~/.graphmem/graph-live.html`** — live graph viewer (open once in Chrome, stays live)

### `/longmemory` Slash Command

Use in any Claude Code session:
- `/longmemory query auth` — search memories
- `/longmemory add "JWT uses RS256"` — store a memory
- `/longmemory context "auth module"` — graph context
- `/longmemory status` — graph stats
- `/longmemory viz` — open live viewer

### Live Graph Viewer

Open `~/.graphmem/graph-live.html` in Chrome once. The graph updates automatically within 2 seconds of every `graphmem add` or `graphmem update` — no server, no refresh, no WebSocket. Uses dynamic script injection to reload `graph-data.js` from disk.

Or launch it directly:

```bash
graphmem viz --live
```

## How It Works

GraphMem wraps [graphiti-core](https://github.com/getzep/graphiti), which provides:

1. **Episode Ingestion** — when you `add` a memory, the LLM extracts entities and facts
2. **Temporal Knowledge Graph** — facts have validity windows (valid_at / invalid_at)
3. **Hybrid Search** — combines semantic embeddings, BM25 keyword search, and graph traversal
4. **Automatic Invalidation** — conflicting new facts mark old ones as invalid

## Acknowledgements

GraphMem is built on [graphiti-core](https://github.com/getzep/graphiti) by [Zep](https://www.getzep.com/), which provides the temporal knowledge graph engine — entity extraction, hybrid search, fact invalidation, and graph storage. All the hard graph problems are solved by Graphiti; GraphMem just wraps it in a CLI for Claude Code.

Graphiti is licensed under Apache 2.0.

## License

MIT
