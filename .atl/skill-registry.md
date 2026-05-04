# Skill Registry — sydney-liveability-ai

Generated: 2026-05-04

## Project Skills (`.claude/skills/`)

| Skill | Trigger Context | Path |
|-------|----------------|------|
| `query-agent` | Creating/updating agents in `backend/agents/query/` (router, gis, crime, sentiment, comparator, synthesiser) | `.claude/skills/query-agent/SKILL.md` |
| `ingest-script` | Creating/updating `backend/scripts/ingest_*.py` | `.claude/skills/ingest-script/SKILL.md` |
| `frontend-guard` | Editing `frontend/src/components/liveability/` or `frontend/src/app/` | `.claude/skills/frontend-guard/SKILL.md` |
| `chromadb-embed` | Embedding/upserting chunks into ChromaDB | `.claude/skills/chromadb-embed/SKILL.md` |
| `alembic-migration` | Changing `backend/db/models.py` or generating migrations | `.claude/skills/alembic-migration/SKILL.md` |
| `latex-report` | Editing `reports/AT2B_report.tex` | `.claude/skills/latex-report/SKILL.md` |

## User Skills (`~/.claude/skills/`)

| Skill | Trigger Context |
|-------|----------------|
| `sdd-explore` | Investigating a feature or problem before committing to a change |
| `sdd-propose` | Creating a change proposal |
| `sdd-spec` | Writing specifications with requirements and scenarios |
| `sdd-design` | Technical design with architecture decisions |
| `sdd-tasks` | Breaking a change into implementation tasks |
| `sdd-apply` | Implementing tasks from the change |
| `sdd-verify` | Validating implementation against specs |
| `sdd-archive` | Closing a completed change |
| `branch-pr` | Creating pull requests |
| `issue-creation` | Creating GitHub issues |
| `judgment-day` | Parallel adversarial review of changes |
| `graphify` | Any input → knowledge graph visualization |

## Compact Rules (injected into sub-agents)

### query-agent
- Always use `get_agent_llm(agent_name)` — never hardcode model strings
- Tools must query DB via `SessionLocal()` context manager
- Return `{"status": "no_data", ...}` when DB returns nothing — never fabricate
- Expose isolated `run(input_data: dict) -> dict` function for crew wiring
- Agent file lives in `backend/agents/query/{name}.py`

### ingest-script
- Scripts live in `backend/scripts/ingest_*.py`
- Use idempotent upserts (INSERT ... ON CONFLICT DO UPDATE)
- Always run `alembic upgrade head` before inserting
- Log counts: inserted, updated, skipped

### frontend-guard
- All shared state in `page.tsx` — child components receive props only
- Use existing Tailwind classes — no new CSS files
- Strict TypeScript: no `any`, explicit return types on all functions
- Coordinate order: Turf.js = [lng, lat], Leaflet = [lat, lng]

### alembic-migration
- Change `backend/db/models.py` first, then `alembic revision --autogenerate`
- Review generated migration before applying
- Never drop columns without team approval
- Run `make db-upgrade` to apply

### latex-report
- File: `reports/AT2B_report.tex`
- Compile with: `tectonic AT2B_report.tex` (from `reports/` dir)
- Academic C1 English — no bullet-point prose, no AI-speak
- Every claim needs a citation or notebook output reference

## Convention Files
- `AGENTS.md` — project rules, API contracts, architecture constraints (source of truth)
- `backend/Makefile` — dev, db-upgrade, db-revision commands
