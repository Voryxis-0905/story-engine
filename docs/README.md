# Story Engine documentation

Read these documents in order:

1. [README](../README.md) — setup, local development, and validation.
2. [Design principles](DESIGN-PRINCIPLES.md) — player and creator authority, world knowledge, events, and checkpoints.
3. [Codebase map](CODEBASE.md) — module responsibilities and where to begin making a change.
4. [Contribution guide](../CONTRIBUTING.md) — change workflow and required checks.
5. [Agent backlog](AGENT-BACKLOG.md) — planned tasks, dependencies, acceptance criteria, and example prompts. It was created at commit `fc55b72`; review it against the current code before implementing an item.

## Design and history

- [Initial review](REVIEW-VA-BRAINSTORM.md) records issues and possible directions. It is not a list of completed features.
- [Architecture](Architecture/) contains design material written before the codebase refactor. Some paths and proposals may no longer match the implementation.
- [Tasks and reports](Tasks_and_Reports/) contains implementation history, validation notes, and decisions. It is retained for traceability and should not be treated as the current specification.

When behavior changes, update the relevant design documentation in the same pull request. When code moves, update the codebase map.
