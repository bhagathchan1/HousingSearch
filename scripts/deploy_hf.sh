#!/usr/bin/env bash
# Deploy HousingSearch to a Hugging Face Docker Space.
#
#   HF_TOKEN=hf_xxx scripts/deploy_hf.sh <hf-username> [space-name]
#
# - Creates the Space (Docker SDK, public) if it doesn't exist yet.
# - Exports the last *committed* version of this repo (git archive HEAD), so
#   uncommitted edits are never deployed.
# - Leaves out the PNG screenshots (Hugging Face rejects binary files pushed without
#   Xet/LFS) and points README images at the GitHub copies instead.
# - Force-pushes that snapshot to the Space; Hugging Face then builds the Dockerfile.
#
# Get a token with "write" access at https://huggingface.co/settings/tokens
# Set DRY_RUN=1 to build the export without creating or pushing anything.
set -euo pipefail

HF_USER=${1:?"usage: HF_TOKEN=hf_xxx $0 <hf-username> [space-name]"}
SPACE=${2:-HousingSearch}
GITHUB_REPO=${GITHUB_REPO:-bhagathchan1/HousingSearch}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
SPACE_URL="https://huggingface.co/spaces/$HF_USER/$SPACE"

if [ -z "${DRY_RUN:-}" ] && [ -z "${HF_TOKEN:-}" ]; then
  echo "Set HF_TOKEN to a Hugging Face token with write access (https://huggingface.co/settings/tokens)" >&2
  exit 1
fi

EXPORT=$(mktemp -d)
trap '[ -z "${DRY_RUN:-}" ] && rm -rf "$EXPORT"' EXIT

echo "→ Exporting committed files from $(git -C "$ROOT" rev-parse --short HEAD)"
git -C "$ROOT" archive HEAD | tar -x -C "$EXPORT"
rm -rf "$EXPORT/docs/screenshots"
sed -i.bak "s#](docs/screenshots/#](https://raw.githubusercontent.com/$GITHUB_REPO/main/docs/screenshots/#g" "$EXPORT/README.md"
rm -f "$EXPORT/README.md.bak"

# Fail early if anything binary slipped in (Hugging Face would reject the push).
BIN=$(cd "$EXPORT" && find . -type f -exec file --mime-encoding {} + | grep -v -E ':[[:space:]]+(us-ascii|utf-8)$' || true)
if [ -n "$BIN" ]; then
  echo "Binary files would be rejected by Hugging Face:" >&2
  echo "$BIN" >&2
  exit 1
fi

if [ -n "${DRY_RUN:-}" ]; then
  echo "DRY_RUN: export ready at $EXPORT (nothing created or pushed)"
  exit 0
fi

echo "→ Creating Space $HF_USER/$SPACE (skipped if it already exists)"
RESP=$(mktemp)
CODE=$(curl -sS -o "$RESP" -w '%{http_code}' -X POST https://huggingface.co/api/repos/create \
  -H "Authorization: Bearer $HF_TOKEN" -H "Content-Type: application/json" \
  -d "{\"type\":\"space\",\"name\":\"$SPACE\",\"sdk\":\"docker\",\"private\":false}")
case "$CODE" in
  200|201) echo "  created" ;;
  409)     echo "  already exists" ;;
  *)       echo "  failed (HTTP $CODE): $(cat "$RESP")" >&2; exit 1 ;;
esac
rm -f "$RESP"

echo "→ Pushing to $SPACE_URL"
cd "$EXPORT"
git init -q -b main
git add -A
git -c user.name="HousingSearch deploy" -c user.email="deploy@users.noreply.huggingface.co" \
  commit -q -m "Deploy $(git -C "$ROOT" rev-parse --short HEAD) from $GITHUB_REPO"
AUTH=$(printf '%s:%s' "$HF_USER" "$HF_TOKEN" | base64 | tr -d '\n')
git -c credential.helper= -c "http.extraHeader=Authorization: Basic $AUTH" \
  push -q --force "https://huggingface.co/spaces/$HF_USER/$SPACE" main

echo
echo "✓ Deployed. Hugging Face is now building the image (about 2–4 minutes)."
echo "  Space page : $SPACE_URL"
echo "  Direct app : https://$(echo "$HF_USER-$SPACE" | tr '[:upper:]_.' '[:lower:]--').hf.space"
