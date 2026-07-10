#!/usr/bin/env bash
# Post-launch freeze: tag release and print branch-protection steps.
# Usage: ./scripts/release-freeze.sh [tag]
# Requires: git, clean validation, deployed production

set -euo pipefail

TAG="${1:-v1.0.0-beta}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "Tag $TAG already exists."
else
  git tag -a "$TAG" -m "VoxForge production beta launch"
  echo "Created tag $TAG"
  echo "Push with: git push origin $TAG"
fi

cat <<'EOF'

Branch protection (GitHub → Settings → Branches → Add rule for main):
  - Require a pull request before merging
  - Require status checks to pass (when CI is added)
  - Do not allow bypassing the above settings

Or via gh (after gh auth login):
  gh api repos/:owner/:repo/branches/main/protection \
    -f required_pull_request_reviews[required_approving_review_count]=1 \
    -f enforce_admins=true \
    -f required_linear_history=false \
    -f allow_force_pushes=false \
    -f allow_deletions=false
EOF
