# NLWeb Project Overview

NLWeb is a natural language search system that provides intelligent query processing, multi-source retrieval, and AI-powered response generation.

## Key Documentation

- **[systemmap.md](./systemmap.md)** - System architecture, APIs, data structures, and query flow
- **[codingrules.md](./codingrules.md)** - Code structure, naming conventions, and edge-case handling
- **[userworkflow.md](./userworkflow.md)** - UX flows, user paths, and failure states

## Quick Start

**Backend**: Python-based server in `code/python/` with main entry at `webserver/WebServer.py`
**Frontend**: Modern JavaScript UI in `static/` with main interface at `fp-chat-interface.js`

## Core Features

- Natural language query processing
- Multiple search modes (list, summarize, generate)
- Real-time streaming responses
- OAuth authentication (Google, Facebook, Microsoft, GitHub)
- Multi-turn conversations with context
- Support for multiple vector databases and LLM providers

## Recent Issues

- Generate mode bug was caused by merge conflicts in fp-chat-interface.js (now fixed)
- The nlws message handler properly renders AI-generated responses

## Development Notes

- Frontend uses ES6 modules with separation of concerns
- Backend uses async Python with streaming support
- Configuration via YAML files in config directory
- Extensive error handling and retry logic throughout