#!/bin/bash
# Publish committed Gallery Guide files to GitHub Pages.
# Usage: tools/publish.sh [--dry-run] "Commit message"
# The source must be a clean Git checkout containing the current remote main.
# No clone-local marker or FORCE_AFTER_MERGE override is trusted.
set -euo pipefail
APP="$(cd "$(dirname "$0")/.." && pwd -P)"
CLONE="${CLONE:-$HOME/.cache/gallery-guide-publish}"
dry_run=0
if [ "${1:-}" = "--dry-run" ]; then dry_run=1; shift; fi
MSG="${1:?commit message}"
stop() { echo "Stopped: $*" >&2; exit 1; }

# A loose folder (or a directory inside another repository) cannot prove that it
# incorporated upstream changes. Require explicit Git history and committed files.
root=$(git -C "$APP" rev-parse --show-toplevel 2>/dev/null) || stop "source must be a Git checkout; clone the repository and commit your changes first."
[ "$(cd "$root" && pwd -P)" = "$APP" ] || stop "source must be the repository root."
[ -z "$(git -C "$APP" status --porcelain --untracked-files=all)" ] || stop "source has uncommitted or untracked files; review and commit them first."
source_head=$(git -C "$APP" rev-parse HEAD)
# Submodule worktrees are not captured by a normal checkout of the parent commit.
[ -z "$(git -C "$APP" ls-tree -r "$source_head" | awk '$1 == "160000" {print}')" ] || stop "submodules are not supported for publication."

if [ ! -d "$CLONE" ]; then
  mkdir -p "$(dirname "$CLONE")"
  gh repo clone perlamilk/gallery-guide "$CLONE" -- -q
fi
CLONE="$(cd "$CLONE" && pwd -P)"
[ "$CLONE" != "$APP" ] || stop "CLONE must be separate from the source checkout."
git -C "$CLONE" rev-parse --git-dir >/dev/null
# Fetch the actual publication branch, regardless of the cache's branch/HEAD or
# gg-last-publish contents. A failed/offline fetch is fatal.
git -C "$CLONE" fetch -q --no-tags origin refs/heads/main
remote_head=$(git -C "$CLONE" rev-parse FETCH_HEAD)
git -C "$CLONE" fetch -q --no-tags "$APP" "$source_head"
git -C "$CLONE" merge-base --is-ancestor "$remote_head" "$source_head" || \
  stop "source does not contain remote main ($remote_head). Fetch and merge/rebase main into the source, review the result, and commit before retrying."

# Work only on the verified commit in an isolated worktree. No rsync --delete,
# copied ignored files, source mutations, or changes to a cached checkout.
staging=$(mktemp -d)
cleanup() {
  git -C "$CLONE" worktree remove --force "$staging/tree" >/dev/null 2>&1 || true
  rm -rf "$staging"
}
trap cleanup EXIT
git -C "$CLONE" worktree add -q --detach "$staging/tree" "$source_head"
cd "$staging/tree"
# Fail closed on malformed versions; use portable sed (macOS and Linux).
[ -f sw.js ] && [ ! -L sw.js ] || stop "sw.js must be a regular tracked file."
old=$(sed -n "s/^const VERSION = 'v\([0-9]*\)';/\1/p" sw.js)
case "$old" in ''|*[!0-9]*) stop "invalid sw.js VERSION.";; esac
remote=$(git show "$remote_head:sw.js" | sed -n "s/^const VERSION = 'v\([0-9]*\)';/\1/p")
case "$remote" in ''|*[!0-9]*) stop "invalid remote sw.js VERSION.";; esac
[ "$remote" -le "$old" ] || old=$remote
new="v$((10#$old + 1))"
sed "s/^const VERSION = 'v[0-9]*';/const VERSION = '$new';/" sw.js > "$staging/sw.js"
cat "$staging/sw.js" > sw.js
git add sw.js
git -c user.name=perlamilk -c user.email=331113409+perlamilk@users.noreply.github.com \
  commit -q -m "$MSG"
sha=$(git rev-parse HEAD)
git diff --stat "$remote_head" "$sha"
if [ "$dry_run" = 1 ]; then
  echo "Dry run: validated $source_head against $remote_head; candidate $sha ($new). Nothing pushed."
  exit 0
fi
# The candidate descends from the fetched main. The lease also rejects ANY
# concurrent remote movement (including a rewind), rather than overwriting it.
git push -q --force-with-lease="refs/heads/main:$remote_head" origin "$sha:refs/heads/main"
echo "pushed $sha as $new"

for i in $(seq 1 60); do
  build=$(gh api repos/perlamilk/gallery-guide/pages/builds/latest -q '.commit + " " + .status' 2>/dev/null || true)
  if [ "$build" = "$sha built" ] && curl -s "https://perlamilk.github.io/gallery-guide/sw.js?t=$RANDOM" | grep -q "VERSION = '$new'"; then
    echo "live: $new"; exit 0
  fi
  sleep 10
done
echo "pushed, but GitHub Pages hasn't finished publishing $new yet"
