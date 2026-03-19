# Workspace Optimization & Project Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate all translation workflows into the Project model, eliminate legacy directories, and unify technical documentation.

**Architecture:** 
- Introduce a `default-project` for "Direct Translation" and CLI fallback.
- Refactor WebUI and CLI to interact with the project system.
- Centralize data storage into `workspace/projects/<slug>`.
- Automated migration script for legacy data.

**Tech Stack:** Python, Flask, Jinja2, Pathlib.

---

### Task 1: Initialize Default Project Logic

**Files:**
- Modify: `webui/helpers.py`
- Modify: `webui/__init__.py`

- [ ] **Step 1: Implement `ensure_default_project()` in helpers**
Add a function to check if `default-project` exists and create it if not.

- [ ] **Step 2: Trigger initialization on App start**
Call `ensure_default_project()` in `create_app()` within `webui/__init__.py`.

- [ ] **Step 3: Commit**
```bash
git add webui/helpers.py webui/__init__.py
git commit -m "feat: ensure default-project exists on startup"
```

### Task 2: Refactor WebUI Direct Translation

**Files:**
- Modify: `webui/routes/translation.py`

- [ ] **Step 1: Redirect direct translation to default-project**
Update `translate_worker` and `start_translation` to use the `default-project` paths instead of `workspace/input|output`.

- [ ] **Step 2: Remove legacy directory creation**
Remove the loop that creates `input`, `output`, `done` in the `index()` route.

- [ ] **Step 3: Commit**
```bash
git add webui/routes/translation.py
git commit -m "refactor: use default-project for direct translations"
```

### Task 3: Refactor CLI and Main

**Files:**
- Modify: `cli.py`
- Modify: `main.py`

- [ ] **Step 1: Update CLI to be project-aware**
Add `--project` (`-p`) argument. Default to `default-project` if omitted. Update help text.

- [ ] **Step 2: Update `main.py` directory resolution**
Use project-based paths for input and output instead of global `workspace/input`.

- [ ] **Step 3: Commit**
```bash
git add cli.py main.py
git commit -m "refactor: make CLI and main.py project-aware"
```

### Task 4: Legacy Data Migration Script

**Files:**
- Create: `scripts/migrate_legacy_data.py`

- [ ] **Step 1: Implement migration logic**
Move files from `workspace/input` to `default-project/sources`, `workspace/output` to `default-project/translated`, and merge global TM.

- [ ] **Step 2: Run migration**
Execute the script and verify file placement.

- [ ] **Step 3: Commit**
```bash
git add scripts/migrate_legacy_data.py
git commit -m "feat: add legacy data migration script"
```

### Task 5: Final Cleanup

**Files:**
- Modify: `config/app.ini`
- Delete: Redundant workspace folders

- [ ] **Step 1: Update `app.ini`**
Remove `INPUT_DIR` and `OUTPUT_DIR` from `[DIRECTORIES]`.

- [ ] **Step 2: Delete legacy folders**
Remove `workspace/input`, `workspace/output`, `workspace/done`, `workspace/translation_memory`.

- [ ] **Step 3: Commit**
```bash
git add config/app.ini
git commit -m "chore: remove legacy directory configurations and folders"
```
