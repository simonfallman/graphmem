---
description: "Graph-based long-term memory — setup, query, add, explore"
---

# /memory — GraphMem

The user wants to interact with their graph-based long-term memory (GraphMem).

Parse the user's argument to determine the action:

## Setup (first-time install)

`/memory setup`

Run these steps in order:

1. Check if `graphmem` is installed:
```bash
which graphmem
```

2. If NOT installed, install it:
```bash
pip install graphmem
```

3. Check if GraphMem is configured:
```bash
test -f ~/.graphmem/.env && echo "configured" || echo "not configured"
```

4. If NOT configured, run interactive setup:
```bash
graphmem init
```

5. Test connectivity:
```bash
graphmem ping
```

6. Check if the current project's CLAUDE.md already has GraphMem instructions:
```bash
grep -l "graphmem" CLAUDE.md 2>/dev/null
```

7. If CLAUDE.md does NOT already mention graphmem, append the following block to CLAUDE.md (create the file if it doesn't exist):

```
## Long-Term Memory

This project uses `graphmem` for persistent graph-based memory across sessions.

**Before answering architecture or domain questions**, check memory:
graphmem query "relevant topic"

**When making or learning about decisions**, store them:
graphmem add "Decided to use X because Y"

**When information changes**, update it:
graphmem update "Switched from X to Y because Z"

**For deep context on a topic**:
graphmem context "topic" --depth 3

### When to Use Memory
- Starting a new task → query for existing context
- Making an architectural decision → store it
- Discovering a code pattern → store it
- Fixing a bug → store what caused it and the fix
- User corrects you → update the memory
```

Tell the user setup is complete and memory is ready to use.

## Regular Commands

### Query (default if no action specified)
`/memory query <topic>` or `/memory <topic>`
```bash
graphmem query "<user's topic>"
```

### Add
`/memory add <text>`
```bash
graphmem add "<user's text>"
```

### Context
`/memory context <topic>`
```bash
graphmem context "<user's topic>" --depth 2
```

### Update
`/memory update <text>`
```bash
graphmem update "<user's text>"
```

### Status
`/memory status`
```bash
graphmem status
```

### List
`/memory list`
```bash
graphmem list entities --limit 20
```

### Viz
`/memory viz`
```bash
graphmem viz
```

If the user provides just a topic without an action (e.g., `/memory auth module`), default to `query`.

Show the output to the user. If the query returns no results, suggest adding memories with `/memory add`.
