# Contributing to Token Atlas

Thank you for your interest in contributing to Token Atlas! This guide will help you get started.

## How to Contribute

### Reporting Bugs

1. Check the [existing issues](https://github.com/DuelistRaj/token-atlas/issues) to avoid duplicates.
2. Open a new issue using the **Bug Report** template.
3. Include clear reproduction steps, expected behavior, and actual behavior.

### Suggesting Features

1. Check the [existing issues](https://github.com/DuelistRaj/token-atlas/issues) for similar suggestions.
2. Open a new issue using the **Feature Request** template.
3. Describe the use case and the expected benefit.

### Submitting Changes

1. **Fork** the repository and create a branch from `main`.
2. Name your branch descriptively: `fix/issue-description` or `feat/feature-name`.
3. Make your changes in small, focused commits.
4. Ensure your changes do not break existing functionality.
5. Open a **Pull Request** against `main` with a clear description of the change.

## Development Setup

### Prerequisites

- Python 3.10+
- PowerShell (for the `pkf.ps1` wrapper)
- Git

### Getting Started

```bash
git clone https://github.com/DuelistRaj/token-atlas.git
cd token-atlas
```

### Repository Structure

| Path | Purpose |
|------|---------|
| `.agents/skills/token-atlas/` | Internal development copy for maintaining and benchmarking Token Atlas. |
| `skills/token-atlas/` | Public standalone skill package for installation into other projects. |
| `scripts/` | Developer tooling including `pkf.ps1` wrapper and `pkf_bench.py` benchmark runner. |

## Coding Standards

- Write clear, self-documenting code with meaningful names.
- Preserve existing comments and docstrings unrelated to your changes.
- Keep Markdown files well-structured and consistent with the existing style.
- Source-backed facts only — all knowledge in `.ai/` documents must cite verifiable source evidence.

## Commit Messages

Use clear, descriptive commit messages:

```
<type>: <short summary>

<optional body explaining the "why">
```

**Types:** `feat`, `fix`, `docs`, `refactor`, `chore`, `bench`

Examples:

```
feat: add simulation mode for changed paths
fix: correct token estimation in startup path validation
docs: update retrieval optimization thresholds
```

## Pull Request Guidelines

- Fill out the PR template completely.
- Reference related issues using `Closes #123` or `Fixes #123`.
- Keep PRs focused — one logical change per PR.
- Ensure the PR description explains *what* changed and *why*.
- Be responsive to review feedback.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold this code.

## Questions?

Open a [discussion](https://github.com/DuelistRaj/token-atlas/issues) or reach out by filing an issue.
