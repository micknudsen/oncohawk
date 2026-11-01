# Domain documentation

This is a single-context repository. Use the root `GLOSSARY.md` for domain vocabulary and `docs/adr/` for architectural decisions when ADRs exist.

Before domain-related exploration, read the glossary and any ADRs relevant to the affected area. If an optional document or ADR directory does not exist, continue without creating placeholders. Domain-modeling creates them when a real term or decision needs recording.

Use the glossary's terms consistently in specs, issues, tests, and implementation. Surface conflicts with an existing ADR instead of silently overriding it.

For milestone scope, consult `docs/requirements.md` and the accepted decisions in `docs/design.md`. Treat `docs/implementation-plan.md` as a proposed sequence and set of implementation choices, not a source of additional accepted requirements. Keep knowledge compilation, variant analysis, annotation, and reporting outside the alignment milestone.
