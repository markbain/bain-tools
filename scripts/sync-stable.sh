#!/usr/bin/env bash
#
# Keep the stable checkout of bain-tools at the tip of develop.
#
# Projects that consume files from bain-tools (templates, scripts) read them from
# the stable checkout, never from a working checkout whose branch changes. The
# stable checkout is a worktree detached at develop; git will not check out the
# same branch in two worktrees, so it cannot hold develop itself.
#
# Installed as post-commit, post-merge, post-rewrite and post-checkout hooks by
# install-hooks.sh. Safe to run by hand. Git 2.25 has no reference-transaction
# hook, so a develop moved by `git branch -f` or `git fetch x:develop` is only
# picked up by the next hook run, or by running this script.
#
# Location: `git config bain.stableWorktree <path>`, default the sibling
# directory <repo>-develop.

# Hooks run with GIT_DIR, GIT_INDEX_FILE and friends set for the calling
# worktree. Clear them, or the commands below act on the wrong tree.
unset $(git rev-parse --local-env-vars 2>/dev/null)

common=$(cd "$(git rev-parse --git-common-dir)" && pwd) || exit 0
repo=$(dirname "$common")
stable=$(git -C "$repo" config bain.stableWorktree || echo "${repo}-develop")

git -C "$repo" rev-parse -q --verify refs/heads/develop >/dev/null || exit 0

if [[ ! -e "$stable/.git" ]]; then
  echo "sync-stable: no stable checkout at $stable (git worktree add --detach $stable develop)" >&2
  exit 0
fi

target=$(git -C "$repo" rev-parse refs/heads/develop)
[[ "$(git -C "$stable" rev-parse HEAD)" == "$target" ]] && exit 0

if [[ -n "$(git -C "$stable" status --porcelain)" ]]; then
  echo "sync-stable: $stable has local changes; not moving it to develop" >&2
  exit 0
fi

git -C "$stable" checkout -q --detach "$target" \
  && echo "sync-stable: $stable now at develop ($(git -C "$stable" rev-parse --short HEAD))" >&2
exit 0
