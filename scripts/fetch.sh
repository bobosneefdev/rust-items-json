#!/usr/bin/env bash
# Downloads the Rust files the extractor needs into ./game.
# Server bundles are anonymous; client bundles need STEAM_USERNAME, STEAM_PASSWORD and
# STEAM_SHARED_SECRET (an account that owns Rust, with a Steam Guard mobile authenticator).
set -euo pipefail
cd "$(dirname "$0")/.."
DD=${DD:-./depotdownloader/DepotDownloader}

"$DD" -app 258550 -depot 258554 -filelist scripts/server-files.txt -dir game/server

# -no-mobile makes DepotDownloader ask for a TOTP code on stdin instead of waiting for app approval.
uv run --quiet scripts/steam_totp.py | "$DD" -app 252490 -depot 252494 -no-mobile \
  -username "$STEAM_USERNAME" -password "$STEAM_PASSWORD" \
  -filelist scripts/client-files.txt -dir game/client
