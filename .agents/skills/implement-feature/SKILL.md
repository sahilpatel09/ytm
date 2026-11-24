---
name: implement-feature
description: Coordinate an end-to-end spec-driven feature workflow from GitHub issue creation through design spec, implementation plan, TDD execution, and pull request creation. Use when the user says "ship feature", "start spec workflow", or asks to build a feature end-to-end with specs and GitHub issues.
---

# Ship Feature Workflow

Coordinate the project's specialized skills in strict sequence. Do not skip stages or combine planning and coding in the same session.

## Stage 1: GitHub Issue and Spec (What and Why)

1. Invoke `create-github-issue` to capture a User Story, Problem Statement, and Acceptance Criteria in a GitHub issue. Record the issue number (`#<id>`).
2. Invoke `brainstorming` to resolve ambiguities and save the approved specification to `docs/specs/<issue-id>-spec.md`.
3. **Human Gate:** Stop and ask the user to approve the GitHub issue and `spec.md` before designing architecture.

## Stage 2: Technical Plan and Tasks (How)

1. Invoke `writing-plans` against `docs/specs/<issue-id>-spec.md` to create `docs/specs/<issue-id>-plan.md` with exact file paths, atomic tasks, and verification commands.
2. **Human Gate:** Stop and ask the user to approve the plan. Tell the user to start a fresh Codex session before Stage 3 so implementation runs with a clean context window.

## Stage 3: TDD Implementation (Fresh Session)

1. Read `docs/specs/<issue-id>-spec.md` and `docs/specs/<issue-id>-plan.md`.
2. Invoke `test-driven-development` and execute tasks one by one (failing test -> minimal implementation -> passing test).

## Stage 4: Spec Audit and Pull Request

1. Invoke `requesting-code-review` to verify `git diff` against every acceptance criterion in `docs/specs/<issue-id>-spec.md` and confirm the full test suite passes.
2. Invoke `yeet` (or `review`) to commit changes, include `Closes #<id>` in the PR description, and open the GitHub pull request.
