@AGENTS.md

# Claude Code instructions

- Use plan mode before editing a new phase, then execute the approved plan in the same session.
- Prefer read-only subagents for architecture, numerical-test, provenance, and claim-boundary review. Do not allow subagents to edit overlapping files.
- Keep the main writer responsible for integration and final test execution.
- When context is becoming crowded, write a complete stage checkpoint before compacting or starting a fresh session.
- Do not infer that a passing unit test establishes scientific validity.
- Do not mark a stage complete until the exact build and test commands have actually run.
