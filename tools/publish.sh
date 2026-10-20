#!/bin/bash
# Publish mfa-guide to https://perlamilk.github.io/gallery-guide/
#   tools/publish.sh "Commit message"
# Copies the app into a clone of the repo, bumps sw.js VERSION (so phones update), commits, pushes,
# then waits until the live site serves the new version.
#
# Safety: if the repo has commits this folder hasn't seen (a merged pull request, an edit on GitHub),
# it stops instead of overwriting them. Bring those changes into mfa-guide first, then run
#   FORCE_AFTER_MERGE=1 tools/publish.sh "message"
set -euo pipefail
APP="$(cd "$(dirname "$0")/.." && pwd)"
CLONE="${CLONE:-$HOME/.cache/gallery-guide-publish}"
MSG="${1:?commit message}"

if [ ! -d "$CLONE/.git" ]; then mkdir -p "$(dirname "$CLONE")"; gh repo clone perlamilk/gallery-guide "$CLONE" -- -q; fi
cd "$CLONE"
git pull -q --ff-only
head=$(git rev-parse HEAD)
last=$(cat .git/gg-last-publish 2>/dev/null || echo "$head")
if [ "$head" != "$last" ] && [ "${FORCE_AFTER_MERGE:-}" != "1" ]; then
  echo "Stopped: the repo has changes that aren't in $APP:"
  git log --oneline "$last..$head"
  echo "Bring them into the local folder first, then run with FORCE_AFTER_MERGE=1."
  exit 1
fi

old=$(sed -n "s/^const VERSION = 'v\([0-9]*\)';/\1/p" "$APP/sw.js")
remote=$(sed -n "s/^const VERSION = 'v\([0-9]*\)';/\1/p" sw.js)
[ "${remote:-0}" -gt "$old" ] && old=$remote
new="v$((old + 1))"
sed -i '' "s/^const VERSION = 'v[0-9]*';/const VERSION = '$new';/" "$APP/sw.js"

rsync -a --delete --exclude '.DS_Store' --exclude '.git' --exclude '__pycache__' "$APP/" ./
git add -A
git -c user.name=perlamilk -c user.email=331113409+perlamilk@users.noreply.github.com \
  commit -q -m "$MSG" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push -q
git rev-parse HEAD > .git/gg-last-publish
echo "pushed $(git log --oneline -1) as $new"

# wait for GitHub Pages to finish building this commit, then check the live version
sha=$(git rev-parse HEAD)
for i in $(seq 1 60); do
  build=$(gh api repos/perlamilk/gallery-guide/pages/builds/latest -q '.commit + " " + .status' 2>/dev/null || true)
  if [ "$build" = "$sha built" ] && curl -s "https://perlamilk.github.io/gallery-guide/sw.js?t=$RANDOM" | grep -q "VERSION = '$new'"; then
    echo "live: $new"; exit 0
  fi
  sleep 10
done
echo "pushed, but GitHub Pages hasn't finished publishing $new yet"
