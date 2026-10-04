#!/usr/bin/env bash
# Default: preview only. --apply: create ONE independent PRIVATE repository.
# No forks, PRs, overwrites, global Git changes or force pushes.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OWNER='kisisjrlly'
NAME='quadruped-clutter-traversal'
TARGET="${OWNER}/${NAME}"
MODE="${1:---dry-run}"
if [[ $# -gt 1 || ( "$MODE" != '--dry-run' && "$MODE" != '--apply' ) ]]; then
  echo 'Usage: bash scripts/publish_github.sh [--dry-run|--apply]' >&2
  exit 2
fi
if [[ "$MODE" == '--dry-run' ]]; then
  printf 'PREVIEW ONLY. No local or remote changes.\nTarget: %s\nVisibility: private\nBranch: main\nSource: %s\n' "$TARGET" "$ROOT"
  echo 'Apply requires authenticated gh, Git author settings, tests, and a fresh directory outside any Git worktree.'
  exit 0
fi
for tool in git gh python; do
  command -v "$tool" >/dev/null 2>&1 || { echo "Missing tool: $tool" >&2; exit 1; }
done
python -c 'import sys; assert sys.version_info >= (3,10), "Python >=3.10 required"'
LOGIN="$(gh api --hostname github.com user --jq '.login')"
[[ "$LOGIN" == "$OWNER" ]] || { echo "Refusing: logged in as $LOGIN, expected $OWNER." >&2; exit 1; }
if git -C "$ROOT" rev-parse --show-toplevel >/dev/null 2>&1 || [[ -e "$ROOT/.git" ]]; then
  echo 'Refusing: source is already a Git worktree (or inside one). Inspect existing history/remotes manually.' >&2
  exit 1
fi
[[ -n "$(git -C "$ROOT" config user.name || true)" && -n "$(git -C "$ROOT" config user.email || true)" ]] || {
  echo 'Configure your own Git author name/email first. This script never invents an author identity.' >&2; exit 1;
}
cd "$ROOT"
python -m unittest discover -s tests -v
python scripts/check_project.py
if gh repo view "github.com/$TARGET" --json nameWithOwner >/dev/null 2>&1; then
  echo "Refusing: $TARGET already exists and is accessible. No overwrite or reuse is automatic." >&2
  exit 1
fi
# A failed view does not prove absence. The create endpoint will reject an existing name.
# Create an EMPTY PRIVATE repo, verify metadata BEFORE any source files are pushed.
GH_HOST=github.com gh repo create "$TARGET" --private --disable-wiki \
  --description 'Research on perception-aware whole-body quadruped traversal through dense, easily disturbed clutter.'
META="$(gh repo view "github.com/$TARGET" --json nameWithOwner,isPrivate,isFork)"
printf '%s' "$META" | python -c 'import json,sys; d=json.load(sys.stdin); assert d["nameWithOwner"]=="kisisjrlly/quadruped-clutter-traversal" and d["isPrivate"] is True and d["isFork"] is False, "Unexpected repository identity/visibility/fork status; no files pushed"'
git init -b main
git add -- .
git commit -m 'Initialize research charter, benchmark, evidence protocol and evaluation scaffold'
git remote add origin "https://github.com/${TARGET}.git"
# Uses the user's normal configured Git authentication; may fail if HTTPS auth is not set up.
GIT_TERMINAL_PROMPT=0 git push --set-upstream origin main
LOCAL_SHA="$(git rev-parse HEAD)"
REMOTE_SHA="$(gh api --hostname github.com "repos/${TARGET}/git/ref/heads/main" --jq '.object.sha')"
[[ "$LOCAL_SHA" == "$REMOTE_SHA" ]] || { echo 'Remote SHA mismatch: publication not verified.' >&2; exit 1; }
META="$(gh repo view "github.com/$TARGET" --json nameWithOwner,isPrivate,isFork,url,defaultBranchRef)"
printf '%s' "$META" | python -c 'import json,sys; d=json.load(sys.stdin); assert d["isPrivate"] is True and d["isFork"] is False and d["defaultBranchRef"]["name"]=="main", "Final metadata mismatch"; print(json.dumps(d,indent=2))'
printf 'Verified main commit: %s\n' "$REMOTE_SHA"
echo 'The initial STATUS.md is a delivery snapshot; update its remote-publication row with this verified evidence.'
