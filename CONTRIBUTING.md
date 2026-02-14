# Contributing to Trade Nexus

Thank you for your interest in contributing to Trade Nexus! This document provides guidelines and instructions for contributing.

## Getting Started

### Prerequisites

- **Frontend**: [Bun](https://bun.sh) (v1.0+)
- **Backend**: [Python 3.11+](https://python.org) with [uv](https://docs.astral.sh/uv/)
- **Git**: For version control

### Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/iamtxena/trade-nexus.git
   cd trade-nexus
   ```

2. **Frontend setup**
   ```bash
   cd frontend
   bun install
   cp .env.example .env.local  # Configure environment variables
   bun dev
   ```

3. **Backend setup**
   ```bash
   cd backend
   uv sync
   cp .env.example .env  # Configure environment variables
   uv run uvicorn src.main:app --reload
   ```

## Development Workflow

### Branch Naming

Use descriptive branch names:
- `feature/add-portfolio-charts` - New features
- `fix/prediction-timeout` - Bug fixes
- `docs/api-endpoints` - Documentation
- `refactor/agent-structure` - Code refactoring

### Commit Messages

Write clear, concise commit messages:
- Use present tense: "Add feature" not "Added feature"
- Use imperative mood: "Fix bug" not "Fixes bug"
- Keep the first line under 72 characters

Examples:
```
Add LSTM model for price prediction
Fix memory leak in data service
Update API documentation for /predict endpoint
```

### Code Style

**TypeScript (Frontend)**
- Run `bun lint` before committing
- Run `bun typecheck` for type verification
- Follow the import order defined in [AGENTS.md](./AGENTS.md)

**Python (Backend)**
- Run `uv run ruff check .` for linting
- Run `uv run mypy src` for type checking
- Follow PEP 8 conventions

### Documentation Workflow

Documentation updates are required for architecture, contract, and user workflow changes.

1. Update relevant portal pages under `docs/portal/`.
2. Regenerate API reference when contract changes:
   - `npm --prefix docs/portal-site run api:build`
3. Run docs validations locally:
   - `python3 scripts/docs/check_frontmatter.py`
   - `python3 scripts/docs/check_links.py`
   - `python3 scripts/docs/check_stale_references.py`
   - `npm --prefix docs/portal-site run build`
4. Ensure `.github/workflows/docs-governance.yml` is green in PR.

## Pull Request Process

1. **Create a feature branch** from `main`
2. **Make your changes** with clear commits
3. **Test your changes**
   - Frontend: `bun lint && bun typecheck`
   - Backend: `uv run pytest`
4. **Push your branch** and create a PR
5. **Fill out the PR template** completely
6. **Request review** from maintainers

### PR Requirements

- All CI checks must pass
- Code must be reviewed by at least one maintainer
- Update documentation if adding new features
- Add tests for new functionality

## Architecture and Contract Proposals

Use the dedicated issue templates before opening architecture or API contract PRs:

- Architecture changes:
  - `.github/ISSUE_TEMPLATE/architecture_change.yml`
- API contract changes:
  - `.github/ISSUE_TEMPLATE/api_contract_change.yml`

For breaking API proposals, include an explicit architecture approval comment URL in the issue before merge.

## Project Structure

See [AGENTS.md](./AGENTS.md) for detailed architecture and code patterns.

## Getting Help

- Open an issue for bugs or feature requests
- Check existing issues before creating new ones
- Be respectful and constructive in discussions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
