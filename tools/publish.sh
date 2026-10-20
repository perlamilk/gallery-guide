#!/bin/bash
# Publish mfa-guide to https://perlamilk.github.io/gallery-guide/
#   tools/publish.sh "Commit message"
# Bumps sw.js VERSION (so phones update), copies the app into a clone of the repo, commits, pushes,
# then waits until the live site serves the new version.
set -euo pipefail
APP="$(cd "$(dirname "$0")/.." && pwd)"
CLONE="${CLONE:-$HOME/.cache/gallery-guide-publish}"
MSG="${1:?commit message}"

old=$(sed -n "s/^const VERSION = 'v\([0-9]*\)';/\1/p" "$APP/sw.js")
new="v$((old + 1))"
sed -i '' "s/^const VERSION = 'v$old';/const VERSION = '$new';/" "$APP/sw.js"

if [ ! -d "$CLONE/.git" ]; then mkdir -p "$(dirname "$CLONE")"; gh repo clone perlamilk/gallery-guide "$CLONE" -- -q; fi
cd "$CLONE"
git pull -q --ff-only
rsync -a --delete --exclude '.DS_Store' --exclude '.git' --exclude '__pycache__' "$APP/" ./
git add -A
git -c user.name=perlamilk -c user.email=331113409+perlamilk@users.noreply.github.com \
  commit -q -m "$MSG" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push -q
echo "pushed $(git log --oneline -1) as $new"

for i in $(seq 1 40); do
  if curl -s "https://perlamilk.github.io/gallery-guide/sw.js?t=$RANDOM" | grep -q "VERSION = '$new'"; then echo "live: $new"; exit 0; fi
  sleep 15
done
echo "pushed, but the live site isn't serving $new yet"
