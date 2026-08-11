## Working rules

- **Two points of view, always.** On any design, analysis or planning question:
  state the position being proposed, then argue the strongest case against it.
  Take the better of the two, or the best parts of each. Never give one side only.
- **Do what was asked, nothing more.** No unrequested files, refactors,
  abstractions or scope. If something extra looks worth doing, name it in one
  line and wait to be asked.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
