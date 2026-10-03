# Local masking rollback authorization follow-up

- Independent P2: HTTP → local edit retains URL and active flag; dropping backend during downgrade reauthorizes the former HTTP destination in old code.
- Reviewer PoC and original evidence under `.claude/review-local-security/` are read-only.
- Scope: reverse migration 0032 and regression tests/configuration documentation only.
- All tests use synthetic isolated databases and fake provider transports; no git staging/commit or live provider requests.
- Red regression is recorded before changing the migration.

## Final

- Permanent regression: 1 test failed before the migration edit; preserved in red-regression.txt.
- Frozen old-code probe: red 1 failure, green 0 failures; five socket/DNS guards observed zero attempts in both runs.
- Existing HTTP control still sends once through its fake transport; former local sends zero after downgrade.
- Focused migration/configuration gate: 9 tests OK, 2.322 seconds, exit 0.
- Only migration 0032, integration regression and task 28 changed; no staging or commit.
