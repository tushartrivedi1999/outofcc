# Open Search Platform Documentation

Welcome to the full documentation set.

## Documentation map

- `docs/architecture.md` - deep architecture and Searx-first data flow
- `docs/apis.md` - API reference (`/v1/search`, `/v1/agent/context`, `/v1/agent/datasets/create`)
- `docs/search-console.md` - property verification and analytics workflows
- `docs/agent-context.md` - Tavily-style agent grounding design
- `docs/operations.md` - deployment, scaling, stress/load/monkey testing, production readiness checklist
- `docs/security.md` - auth, session, key and data handling controls
- `INTEGRATION_GUIDE.md` - step-by-step integration walkthrough

## Product principle

This project is **Searx-first**:
- all retrieval roots in Searx (`SEARX_BASE_URL`)
- search API, console analytics seeds, and agent-context enrichment are built on top of that retrieval model
- additional modules (console, agent studio, datasets, blog) are product layers over the same backend base
