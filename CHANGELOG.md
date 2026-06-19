# Changelog

## 0.20.1 (Unreleased)

## 0.20.0 — 2026-06-19

- Added shared `autoreview`, `crabbox`, `handoff`, `agent-transcript`, and `session-viewer` skills.
- Added structured autoreview workflows for Codex, Claude, Pi, Droid, Copilot, OpenCode, and Cursor, including panel review, streaming progress, heartbeat metrics, model defaults, and fallback handling.
- Hardened autoreview against reviewed-repository instructions, configuration, environment leakage, unsafe bundle inputs, and excessive closeout scope.
- Added local and remote review harnesses with cross-platform validation and self-tests.
- Added redacted agent transcript provenance and a searchable local HTML session viewer.
- Added the skills installer, Skills.sh catalog metadata, repository validation, and CI coverage.
- Improved Crabbox/Testbox guidance for installation, cache reuse, parallel warm-up, artifacts, and result reporting.
