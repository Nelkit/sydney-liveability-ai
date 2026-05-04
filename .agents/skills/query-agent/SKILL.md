---
name: query-agent
description: 'Implement CrewAI agents in backend/agents/query/ with isolated run(input_data), DB-backed tools, graceful no-data handling, and model selection via get_agent_llm(agent_name). Use when creating or updating router/crime/sentiment/gis/comparator/synthesiser agents.'
argument-hint: 'Agent name and data source, e.g., gis from transport_scores + osm_scores'
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

# Query Agent Skill

## When To Use
- You need to create a new query agent in `backend/agents/query/`.
- You need to refactor an existing query agent to match project conventions.
- You need an agent implementation that is testable in isolation via `run(input_data)`.

## Context
- Agent files live in `backend/agents/query/`.
- LLM must come from `get_agent_llm(agent_name)` in `backend/config.py`.
- Valid agent keys: `router`, `crime`, `sentiment`, `gis`, `comparator`, `synthesiser`.
- Database access uses `get_session()` from `backend/db/postgres.py`.
- ORM models come from `backend/db/models.py`.

## Critical Patterns
- Never hardcode model IDs inside agent files.
- Always expose `run(input_data: dict[str, Any]) -> dict[str, Any]`.
- Always return graceful no-data outputs: `{"suburb": suburb, "error": "no data available"}`.
- Keep each agent focused on one concern and one data source family.
- Keep files under 150 lines; split helpers when needed.

## Standard Workflow
1. Identify the agent role and target data source/table.
2. Implement one `@tool` function that queries DB with `get_session()`.
3. Map ORM fields to a stable output dict.
4. Create `Agent` using `llm=get_agent_llm("<agent_name>")`.
5. Create `Task` with explicit expected output.
6. Implement `run(input_data)` with a standalone `Crew`.
7. Add `if __name__ == "__main__"` smoke test block.
8. Wire into `backend/crews/query_crew.py` once standalone behavior is verified.

## Decision Rules
- If table has no row for suburb: return no-data error dict, never raise for expected absence.
- If agent needs two suburbs (comparison): validate both inputs and return clear error when missing.
- If output schema changes: coordinate with synthesiser and API contracts before merge.
- If logic exceeds 150 lines: move parsing/formatting into local helpers.

## Quality Gates
- Uses `get_agent_llm("<agent>")` and never direct model strings.
- Uses `get_session()` and closes DB session safely.
- Has deterministic output keys for synthesiser compatibility.
- Provides standalone runnable `run()` path.
- Handles empty dataset or missing suburb gracefully.

## Template
```python
"""
agents/query/<name>.py
-----------------------
Owner: <team member name>

Input:  {"suburb": str, ...}
Output: {"suburb": str, "<data>": ..., ...}

This agent queries <table> from PostgreSQL and returns
<describe what it returns>.
"""

from typing import Any

from crewai import Agent, Crew, Task
from crewai.tools import tool

from config import get_agent_llm
from db.models import <ModelName>
from db.postgres import get_session


@tool("<tool_name>")
def <tool_name>(suburb: str) -> dict[str, Any]:
    with get_session() as session:
        row = session.query(<ModelName>).filter_by(suburb=suburb).first()
        if not row:
            return {"suburb": suburb, "error": "no data available"}
        return {
            "suburb": suburb,
            # map ORM fields here
        }


<name>_agent = Agent(
    role="<Role name>",
    goal="<What this agent is trying to accomplish>",
    backstory="<One sentence explaining why this agent exists>",
    tools=[<tool_name>],
    llm=get_agent_llm("<name>"),
    verbose=True,
)


<name>_task = Task(
    description="Query <data source> for {suburb} and return <describe output>.",
    expected_output="A dict with suburb and <describe fields>.",
    agent=<name>_agent,
)


def run(input_data: dict[str, Any]) -> dict[str, Any]:
    crew = Crew(
        agents=[<name>_agent],
        tasks=[<name>_task],
        verbose=True,
    )
    return crew.kickoff(inputs=input_data)


if __name__ == "__main__":
    print(run({"suburb": "Newtown"}))
```

## Commands
```bash
cd backend
python -m agents.query.<name>

# After wiring the agent into the query crew, run backend and test endpoint
uvicorn main:app --reload --port 8004
```

## Integration Notes
- When agent is ready, register execution in `backend/crews/query_crew.py`.
- Keep response structure compatible with synthesiser expectations.
- If adding new fields used by downstream endpoints, update API contract docs before merge.

## Prompt Starters
- "Use query-agent skill to implement backend/agents/query/crime.py from bocsar table."
- "Refactor backend/agents/query/gis.py with query-agent gates and isolated run()."
- "Create comparator agent with dual-suburb validation using query-agent skill."
