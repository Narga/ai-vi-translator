# Novel Translator - Development Plan

**Version**: 4.0.4  
**Last Updated**: 2026-02-15  
**Status**: Stable & Production Ready

---

## ✅ COMPLETED TASKS (v4.0.0 - v4.0.4)

### v4.0.0 - SDK Migration
- [x] Migrate from `google-generativeai` to `google-genai` SDK
- [x] Support `gemini-3-flash-preview` model
- [x] Add `thinking_level` parameter control
- [x] Plugin architecture implementation
- [x] Circuit Breaker pattern
- [x] Health Monitor (runtime/stall detection)
- [x] Emergency Stop mechanism

### v4.0.1 - Rate Limiting & CLI
- [x] `.env` support for API keys (python-dotenv)
- [x] GlobalRPMRateLimiter (15 RPM sliding window)
- [x] TokenBudgetLimiter (1M TPM)
- [x] Fix race condition in API key selection
- [x] Fix dead code (old SDK)
- [x] CLI with argparse (`cli.py`)
- [x] Checkpoint/Resume functionality
- [x] Async support (AsyncGenAIClient)

### v4.0.2 - LSP Fixes & Optimizations
- [x] Fix LSP/Type errors (genai_client, chunker, plugin)
- [x] Add tqdm progress bar
- [x] Multi-language support (CN/JP/KR)
- [x] Regex optimization (module-level constants)
- [x] Cache compression (gzip)
- [x] Memory optimization (chunk_text_generator)

### v4.0.3 - Web UI & uv Support
- [x] Web UI with Flask (real-time progress, form config)
- [x] Server-Sent Events (SSE) for live updates
- [x] Direct text input (no file upload needed)
- [x] pyproject.toml for uv package manager
- [x] Optional dependencies (epub, ocr, async, dev)

### v4.0.4 - WebUI Enhancements
- [x] Input Files List: click to load content
- [x] Cache Priority: check cache before API call
- [x] Download translated file
- [x] Prompt Editor with save functionality
- [x] Output Files list with download links
- [x] Auto-merge small files for minimum chunk size

---

## 🎯 UPCOMING TASKS (v4.1.0+)

### High Priority
- [ ] **Batch Translation**: Process multiple files in parallel using async
- [ ] **Advanced CLI**: Add more commands (list-checkpoints, clear-cache, etc.)
- [ ] **Progress Persistence**: Better checkpoint with JSON metadata
- [ ] **Translation Quality Metrics**: BLEU score or similar

### Medium Priority
- [ ] **PDF Export Plugin**: Generate formatted PDF output
- [ ] **Translation Memory**: Learn from previous translations
- [ ] **Auto-detection**: Detect source language automatically

### Low Priority
- [ ] **Docker Support**: Containerize the application
- [ ] **CI/CD Pipeline**: GitHub Actions for testing
- [ ] **Unit Tests**: Comprehensive test coverage
- [ ] **Performance Benchmarks**: Automated performance testing

### Documentation
- [ ] API Reference documentation
- [ ] Contributing guidelines
- [ ] Deployment guide
- [ ] Video tutorials

---

## 🔧 TECHNICAL DEBT

### Code Quality
- [ ] Add comprehensive docstrings to all public methods
- [ ] Implement proper error handling in edge cases
- [ ] Add input validation for all user-facing functions
- [ ] Reduce cyclomatic complexity in complex functions

### Performance
- [ ] Profile memory usage for large files (>50MB)
- [ ] Optimize regex patterns further
- [ ] Implement connection pooling for HTTP requests
- [ ] Add caching for prompt templates

### Security
- [ ] Encrypt API keys at rest (optional)
- [ ] Add rate limiting per IP (if deploying as service)
- [ ] Sanitize user inputs
- [ ] Add audit logging

---

## 🐛 KNOWN ISSUES

| Issue | Severity | Status | Notes |
|-------|----------|--------|-------|
| LSP warnings in genai_client | Low | Wontfix | SDK type stubs issue |
| Large file memory usage | Medium | Workaround | Use generator mode |
| Cache size grows unbounded | Low | Planned | Auto-cleanup needed |

---

## 📊 METRICS & TARGETS

### Performance Targets
- **Throughput**: 20 chunks/minute (with 30 keys)
- **Memory Usage**: <500MB for 10MB input file
- **Cache Hit Rate**: >70% for repeated translations
- **API Success Rate**: >95%

### Quality Targets
- **Translation Accuracy**: >90% (manual review)
- **Character Retention**: <1% Chinese chars remaining
- **Format Preservation**: 100% markdown structure

---

## 🗓️ RELEASE SCHEDULE

| Version | Planned Date | Focus |
|---------|-------------|-------|
| v4.0.3 | 2026-03-01 | Bug fixes, stability |
| v4.1.0 | 2026-03-15 | Batch processing, Web UI |
| v4.2.0 | 2026-04-01 | PDF export, quality metrics |
| v5.0.0 | 2026-06-01 | Major refactor, new features |

---

## 💡 IDEAS BACKLOG

- **Plugin Marketplace**: Allow third-party plugins
- **Translation API**: Expose as REST API
- **Mobile App**: Simple mobile interface
- **Collaborative Translation**: Multi-user support
- **AI-assisted Editing**: Post-translation editing suggestions

---

**Note**: This plan is living document. Priorities may change based on user feedback and technical constraints.
