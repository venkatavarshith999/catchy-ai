#!/usr/bin/env bash
# Run from repository root on the configured deployment host.
set -euo pipefail
image="${1:?Pass the immutable GHCR image tag}"
[[ "$image" =~ ^ghcr.io/[a-z0-9_.-]+/[a-z0-9_.-]+:[a-f0-9]{40}$ ]] || exit 1
compose=(docker compose --env-file deployment/.env -f deployment/compose.production.yaml)
previous=""
if [[ -f deployment/current-image ]]; then previous="$(cat deployment/current-image)"; fi
export CATCHY_IMAGE="$image"
"${compose[@]}" pull app
if "${compose[@]}" up -d --wait --wait-timeout 90; then
  printf '%s\n' "$image" > deployment/current-image
  echo 'Deployment healthy.'
else
  echo 'Deployment failed; restoring the previous application image.' >&2
  if [[ -n "$previous" ]]; then
    export CATCHY_IMAGE="$previous"
    "${compose[@]}" up -d --wait --wait-timeout 90
  fi
  exit 1
fi
