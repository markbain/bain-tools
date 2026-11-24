#!/usr/bin/env bash
#
# Install sync-stable.sh as this clone's post-commit, post-merge, post-rewrite
# and post-checkout hooks, and create the stable checkout if it is missing.
#
# The hooks are copies, not symlinks: a symlink into a working checkout would
# change whenever that checkout changes branch. Re-run after editing
# sync-stable.sh.

set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
# --git-common-dir can be relative to the directory git ran in, so resolve it there.
common=$(cd "$here" && cd "$(git rev-parse --git-common-dir)" && pwd)
repo=$(dirname "$common")
stable=$(git -C "$repo" config bain.stableWorktree || echo "${repo}-develop")

for hook in post-commit post-merge post-rewrite post-checkout; do
  if [[ -e "$common/hooks/$hook" ]] && ! cmp -s "$here/sync-stable.sh" "$common/hooks/$hook"; then
    echo "refusing to overwrite existing $common/hooks/$hook" >&2
    exit 1
  fi
  install -m 755 "$here/sync-stable.sh" "$common/hooks/$hook"
done
echo "hooks installed in $common/hooks"

if [[ ! -e "$stable/.git" ]]; then
  git -C "$repo" worktree add -q --detach "$stable" develop
  echo "stable checkout created at $stable"
fi
"$here/sync-stable.sh"
