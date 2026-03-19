---
name: "Spec"
description: "Write a clear feature specification from a vague idea or requirement. Produces a structured spec doc covering problem, goals, scope, user stories, and open questions."
---

# Spec Skill

Your job is to turn a rough idea or requirement into a precise, unambiguous feature specification. This is the first step before any research or implementation.

## Process

1. **Understand the request** — Ask the user 1-3 targeted clarifying questions if the requirement is too vague to spec. If enough context exists, proceed directly.

2. **Write the spec** using this structure:

```
## Feature: <name>

### Problem
What problem does this solve? Why does it matter?

### Goals
- Bullet list of what success looks like (measurable where possible)

### Non-Goals
- What is explicitly out of scope

### User Stories
- As a <user>, I want to <action> so that <outcome>
- (add as many as needed)

### Functional Requirements
1. Numbered list of concrete behaviours the system must exhibit
2. Each requirement should be independently verifiable

### Technical Constraints
- Known constraints (performance, compatibility, security, etc.)

### Open Questions
- Unresolved decisions that need answers before or during implementation
```

3. **Output the spec** as a markdown code block so the user can copy it.

4. **Suggest next step**: Tell the user to run `/research` to investigate unknowns, or `/plan` if the spec is clear enough to go straight to planning.

## Rules
- Be concrete. Avoid vague words like "should", "nice to have", "easy". Use "must", "will", "shall".
- Keep scope tight. A good spec says "no" clearly.
- Do NOT design the solution in the spec. That is for `/plan`.
- Do NOT look at code unless the user explicitly asks you to reference existing behaviour.
