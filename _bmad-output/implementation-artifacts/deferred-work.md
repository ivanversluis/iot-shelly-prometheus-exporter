- source_spec: `_bmad-output/implementation-artifacts/spec-cap-7-release-promotion.md`
  summary: Define whether ignored files should block release promotion.
  evidence: Git porcelain status excludes ignored files, while the release contract currently specifies tracked and untracked files; an explicit policy is needed before treating ignored local secrets or artifacts as blockers.
- source_spec: `_bmad-output/implementation-artifacts/spec-cap-7-release-promotion.md`
  summary: Harden project-version parsing and post-tag verification.
  evidence: The focused implementation uses a text replacement for the simple current TOML layout; duplicate declarations, unusual TOML formatting, and independent post-tag consistency checks remain outside this small release story.
