# Publishing safely

## Never publish the experimental working tree directly

A `.gitignore` does not remove secrets from existing commits. The safest release process is:

1. create a fresh empty repository,
2. copy only reviewed source files,
3. run `./scripts/release-check.sh`,
4. inspect `git status --ignored`,
5. search for card UIDs and keys,
6. create the first public commit only after review.

## Files that must stay private

- `state.json`
- `*.bin`, `*.mfd`, `*.dump`, `*.mct`, `*.eml`
- `*.meta`, `*.log`, `*.csv`
- card-specific `.keys` files
- solver hashes and screenshots containing UIDs or keys

## Recommended checks

```bash
git status --ignored
git grep -n -iE '[0-9a-f]{8}|[0-9a-f]{12}'
find . -type f -size +500k -print
./scripts/clean.sh
./scripts/release-check.sh
```

Review every hexadecimal match manually because source code naturally contains constants.

## Release archive

Create the archive from Git, not from the working directory. Run the release check first:

```bash
./scripts/release-check.sh
git archive --format=zip --output=rc522-mfc-recovery.zip HEAD
```

This excludes ignored and untracked private artifacts.
