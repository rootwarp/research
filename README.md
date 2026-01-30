# Research Monorepo

A language-based monorepo for research projects and experiments.

## Directory Structure

```
research/
├── rust/       # Rust projects
├── go/         # Golang projects
├── python/     # Python projects
├── bash/       # Bash scripts and projects
├── docs/       # Shared documentation
└── scripts/    # Shared utility scripts
```

## Adding New Projects

1. Create a new directory under the appropriate language folder
2. Each project should have its own README explaining its purpose
3. Follow language-specific conventions for project structure:
   - **Rust**: Use `cargo new` to create new projects
   - **Go**: Follow standard Go module layout
   - **Python**: Include `requirements.txt` or `pyproject.toml`
   - **Bash**: Include usage comments at the top of scripts

## Shared Resources

- `docs/`: Cross-project documentation, architecture decisions, research notes
- `scripts/`: Utility scripts that can be used across projects
