<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **my_agent** (5782 symbols, 12471 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/my_agent/context` | Codebase overview, check index freshness |
| `gitnexus://repo/my_agent/clusters` | All functional areas |
| `gitnexus://repo/my_agent/processes` | All execution flows |
| `gitnexus://repo/my_agent/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

---

# Project Overview

This repository is a FastAPI-based AI agent framework called `fastapi-general-framework`. It is built to support:
- a centralized FastAPI HTTP service entrypoint in `src/FastAPI_server.py`
- modular API routers under `src/routers/`
- business orchestration in `src/services/`
- agent/core planning, memory, execution, and tool integration in `src/core/`
- infrastructure adapters in `src/infra/`
- data models in `src/models/`
- exception handling and utilities in `src/exceptions/` and `src/utils/`

## Key development notes

- The framework targets Python `>=3.12`.
- Dependencies are declared in `pyproject.toml` and `environment.yaml`.
- Run the app in development with:
  - `uvicorn FastAPI_server:app --host 0.0.0.0 --port 8004 --reload`
- A production-style startup command is shown in `README.md` using `gunicorn` and `uvicorn.workers.UvicornWorker`.
- The app includes a `/health` endpoint and a global `ServiceException` handler.

## Important files and directories

- `src/FastAPI_server.py` — main service entry, middleware, router registration, startup/shutdown lifecycle.
- `src/routers/` — API route definitions for chat, agent, memory, task, video, image, prompt templates, and more.
- `src/services/` — business logic and background work orchestration.
- `src/core/` — agent engine, planning, memory system, tools, LLM adapters, execution environment, state.
- `src/infra/` — logging, config, scheduler, storage, message queue, connector lifecycle.
- `tests/` and `src/test/` — test files and example test artifacts.
- `design.md` — architecture and component design notes.

## Practical guidance for AI coding agents

When contributing or modifying this repository:
- Focus first on `src/FastAPI_server.py` and `src/routers/` for API behavior.
- Use `src/services/` for orchestrating business use cases and asynchronous tasks.
- Inspect `src/core/` for agent planning, memory, and tool/integration logic.
- Keep changes aligned with the repository's pattern of file-based memory, connector lifecycle startup, and environment presets for model downloads.
- Prefer adding or updating tests in `tests/` or `src/test/` when changing behavior.

## Suggested next customization

- Add a `.github/copilot-instructions.md` or `AGENT.md` with concise repo-specific editor instructions for code review, testing, and API changes.
- Create skill files for common tasks like "run local server", "find router endpoints", and "explain agent/core flow".

<!-- gitnexus:end -->
