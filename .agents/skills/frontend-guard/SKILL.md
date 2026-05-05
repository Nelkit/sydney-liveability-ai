---
name: frontend-guard
description: >
  Keep frontend contributions aligned with the existing Tailwind design system,
  strict TypeScript typing, and current component architecture in Sydney Liveability AI.
  Trigger: Use when creating or updating React/Next components, frontend data models,
  or UI states in frontend/src/app and frontend/src/components/liveability.
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

# Frontend Guard Skill

## When to Use
- You add a new component in `frontend/src/components/liveability/`.
- You modify UI behavior in `frontend/src/app/page.tsx`.
- You add or change frontend data structures, API payload handling, or view models.
- You refactor existing UI while preserving current visual identity.

## Critical Patterns
- Keep visual consistency with existing Tailwind usage and component spacing rhythm.
- Prefer reusing established visual patterns before introducing new class combinations.
- Never use `any`; define explicit TypeScript interfaces/types for props, state, and API payloads.
- Keep shared state in `frontend/src/app/page.tsx`; pass data/callbacks via props.
- Respect map coordinate conventions: Turf uses `[lng, lat]`, Leaflet uses `[lat, lng]`.
- Preserve existing API response contracts expected by frontend integration.

## Standard Workflow
1. Inspect nearby components in `frontend/src/components/liveability/` to match style and structure.
2. Define or update TypeScript types before implementing JSX logic.
3. Implement UI using Tailwind classes consistent with existing patterns.
4. Wire component integration from `frontend/src/app/page.tsx` using typed props.
5. Validate empty/loading/error states with explicit typed branches.
6. Run lints and resolve issues before finishing.

## Decision Rules
| Scenario | Rule |
|---|---|
| New reusable component | Create typed props interface and keep component presentational when possible |
| New API field used in UI | Extend corresponding TypeScript type first, then render logic |
| New visual variation | Reuse existing utility patterns first; only add new pattern if repeated use is clear |
| Complex conditional UI | Move branch-specific rendering to small typed helper components |
| Temporary mock data | Keep shape aligned with real backend contracts |

## Quality Gates
- No `any` in new/changed frontend code.
- Every new prop/state object has a named type or interface.
- Tailwind classes follow established visual language in liveability components.
- Component works in both desktop and mobile breakpoints already used in the project.
- Loading/error/empty states are present for async or optional data.
- `npm run lint` passes for the frontend project.

## Commands
```bash
cd frontend
npm run lint
```

## Prompt Starters
- "Use frontend-guard to create a new liveability card component with typed props and existing Tailwind style."
- "Apply frontend-guard to refactor this component without changing the current design language."
- "Use frontend-guard to add a new API field to UI with strict typing and safe fallback states."
