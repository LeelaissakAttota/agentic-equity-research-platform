# Git Workflow

## Repository policy

- `main` is the primary branch unless the owner intentionally changes the strategy.
- Preserve existing remotes, branch protection, hooks, and user/global Git identity.
- Never invent a remote URL or overwrite identity/configuration.
- Do not commit directly, commit, push, force-push, tag, or open a pull request unless the active prompt explicitly authorizes it.
- Inspect `git status`, current branch, remotes, and relevant diff before and after work.

## Suggested branch names

Use short, issue/phase-aware names when branches are requested:

```text
phase-01/core-foundation
feat/company-resolution
fix/evidence-period-validation
docs/provider-policy
```

## Commit convention

Use Conventional Commit-style prefixes:

- `feat:` new user/domain capability
- `fix:` defect correction
- `docs:` documentation only
- `test:` test-only change
- `refactor:` behavior-preserving restructure
- `chore:` build/repository maintenance
- `perf:` measured performance improvement
- `security:` security hardening or vulnerability fix

Add a scope when useful, for example `fix(evidence): preserve amended filing period`. Keep commits cohesive; explain intent, important trade-offs, tests, breaking changes, and migration implications in the body.

Recommended Phase 0 commit message when a later prompt authorizes the commit:

```text
chore(phase-00): bootstrap financial intelligence platform
```

## Change workflow

1. Read the active phase and rules.
2. Inspect status, remotes, branch, and existing changes.
3. Create or use the owner-approved branch strategy.
4. Make scoped changes without disturbing unrelated work.
5. Run relevant tests and inspect the full diff for secrets/generated files.
6. Update documentation, decisions, status, and changelog when applicable.
7. Commit/push only when explicitly authorized.

## Review expectations

Reviews assess phase scope, architecture boundaries, evidence integrity, source authority, deterministic calculations, free-model enforcement, security, migrations/compatibility, observability, test quality, and documentation. Critical factual/security/cost failures block merging.

## Sensitive and generated content

Never stage `.env`, secrets, credentials, local databases, caches, downloaded source corpora, generated reports, or temporary artifacts. If sensitive data appears in history, stop and coordinate remediation; deleting a working-tree file is insufficient.

## History safety

Avoid rewriting shared history. Never use destructive reset/clean/force operations without explicit owner approval and exact scope verification. Prefer additive corrections and revert commits for shared changes.

## Releases

Release tags and semantic-version policy will be established before external releases. A tag requires accepted phase/release criteria, changelog, reproducible build, security checks, migration/rollback notes, and owner approval.
