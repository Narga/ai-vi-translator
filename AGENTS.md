# AGENTS.md

## Project overview

Content Translator is a minimalist, local-only tool for one user. Its primary flow is: split source text into natural chunks, send each chunk to an explicitly selected AI provider/model, join the responses, and save the result atomically. `main.py` serves the WebUI and API; `run.py` provides the secondary CLI.

Before changing behavior, read `docs/00_PROJECT_MANIFESTO.md`. It is the project contract and wins over conflicting implementation details. If a change alters a config schema, error model, API, or path convention, update the governing documentation together with the code.

## Architecture and boundaries

- `main.py`: stdlib HTTP server, JSON API, SSE translation flow, and process restart.
- `run.py`: CLI translation flow and AI-client construction.
- `core/`: chunking, prompts, provider clients/configuration, safe file operations, quality checks, and SQLite metadata/logging.
- `web/`: vanilla HTML, CSS, and JavaScript. Keep the UI build-free.
- `prompts/`: prompt templates; adding a prompt is normally data-only.
- `tests/`: pytest suite with fake clients and temporary workspaces; tests must not call real provider APIs.
- `docs/`: product contracts, implementation plans, roadmap, and runbook.

Preserve these product constraints:

- The app is single-user and bound to localhost; do not introduce auth, multi-user infrastructure, or public-server complexity.
- Keep the backend on the standard library plus `httpx`; do not add provider SDKs or frameworks without an explicit requirement.
- Keep the frontend vanilla and offline-capable. Do not add npm, a build step, a required CDN, or a frontend framework.
- Provider and model selection is explicit. Never silently fall back to another model.
- Each key is attempted at most once per chunk after rate limiting. On terminal failure, stop the run; do not save partial output or add implicit resume/checkpoint behavior.
- Preserve path-traversal protections and atomic output writes.
- Preserve Unicode, especially Vietnamese text.

## Private and generated data

Never commit or expose user data or credentials. In particular, treat `config/providers.json`, `config/keys.json`, and all of `workspace/` as private even when they exist locally. Do not inspect their contents unless the task specifically requires it. Also avoid committing virtual environments, caches, IDE metadata, vendored/build output, or minified bundles covered by `.gitignore`.

Tests that touch configuration or project files must use temporary paths or restore any modified tracked configuration. Keep existing user worktree changes intact and do not rewrite unrelated files.

## Development workflow

Use Python 3.12 or newer. Prefer the existing virtual environment when available.

```bash
python -m pytest tests/ -q
python main.py
python run.py input.txt output.txt
```

For focused changes, run the narrowest relevant tests first, then the full suite before handoff. Tests should be deterministic, use mocks/fakes for AI providers, and avoid network access. When changing frontend behavior, update or add coverage in `tests/test_frontend_hygiene.py` where practical and manually verify the affected browser flow when possible.

## Implementation conventions

- Follow the existing straightforward Python style; prefer small functions and standard-library solutions.
- Use `pathlib.Path` and the existing safe file helpers for project-controlled paths.
- Reuse the canonical config normalization and provider manager rather than reading raw config dictionaries independently.
- Reuse the shared provider error taxonomy; do not classify provider failures ad hoc in individual callers.
- Keep API errors clear and stable, and maintain SSE event ordering and cancellation behavior.
- Keep JavaScript organized by the existing page/module layout and CSS based on existing variables/components.
- Avoid speculative abstractions, plugin frameworks, background services, and state that does not directly improve the send/receive translation flow.
- Add or update tests for bug fixes and behavior changes. Do not weaken assertions merely to make a failing test pass.

## Documentation and release hygiene

Update `README.md` when setup or user-facing workflows change. Update the relevant contract/specification under `docs/` when architecture or behavior changes. Record user-visible changes in `CHANGELOG.md`, following its existing Keep a Changelog format. Keep version strings synchronized where the repository currently asserts them, including the health endpoint and related tests.
