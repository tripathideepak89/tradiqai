---
name: "Research"
description: "Investigate the codebase, dependencies, or external APIs relevant to a spec or task. Produces a research summary covering current state, risks, and unknowns — without writing any code."
---

# Research Skill

Your job is to investigate and report — not to write code. This step answers the open questions in a spec and surfaces unknowns before planning begins.

## Process

1. **Identify what to investigate** — Read the spec or task description. Extract every open question, unknown dependency, and unclear constraint.

2. **Investigate systematically** using available tools:
   - Read relevant source files
   - Search the codebase for existing patterns, similar features, or related code
   - Check external docs or APIs if relevant
   - Look at recent git history for context on tricky areas

3. **Write the research summary** using this structure:

```
## Research: <feature/task name>

### Current State
How does the relevant part of the system work today? Key files, functions, data flows.

### Relevant Code
- `path/to/file.py:line` — brief description of what's relevant and why
- (list the most important locations)

### Dependencies & Integration Points
- What other modules/services does this touch?
- What APIs or data sources are involved?
- What shared state or DB tables are affected?

### Risks & Gotchas
- Things that could go wrong or cause unexpected behaviour
- Tight coupling, missing abstractions, race conditions, etc.

### Answers to Open Questions
- Question from spec → Answer found (or "still unknown")

### Remaining Unknowns
- What couldn't be resolved through research alone
- Decisions that need to be made during planning or implementation
```

4. **Suggest next step**: Tell the user to run `/plan` with the spec + research summary as input.

## Rules
- Do NOT write implementation code. Read-only investigation only.
- Be specific: cite exact file paths and line numbers.
- If you find something surprising or risky, highlight it clearly.
- Timebox: focus on what matters for the spec. Don't research tangents.
