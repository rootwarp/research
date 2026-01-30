# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a language-based research monorepo for experiments and projects in Rust, Go, Python, and Bash.

## Structure

- `rust/` - Rust projects (use `cargo new` for new projects)
- `go/` - Go projects (use standard Go module layout)
- `python/` - Python projects (include `requirements.txt` or `pyproject.toml`)
- `bash/` - Bash scripts (include usage comments at top of scripts)
- `docs/` - Cross-project documentation and research notes
- `scripts/` - Shared utility scripts

## Build Commands

Commands vary by language and project. Each project directory should have its own build instructions. Common patterns:

- **Rust**: `cargo build`, `cargo test`, `cargo run`
- **Go**: `go build`, `go test ./...`, `go run .`
- **Python**: `pip install -r requirements.txt`, `pytest`
- **Bash**: Scripts are directly executable

## Adding New Projects

Create a new directory under the appropriate language folder. Each project should be self-contained with its own README.
