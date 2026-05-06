#!/usr/bin/env bash
set -euo pipefail

UDID="${UDID:-DB367B59-DFC1-4DE9-B1AF-C5FDD2F5985F}"
SESSION="${SESSION:-zagrajmy-ios-modal}"
BASE_URL="${BASE_URL:-https://test.zagrajmy.net}"

COMMON=(--platform ios --udid "$UDID" --session "$SESSION")

echo "Opening Safari at $BASE_URL on iOS simulator $UDID..."
agent-device open Safari "$BASE_URL" "${COMMON[@]}"

# Open first past event.
echo "Opening first past event..."
agent-device wait text "Sesje RPG w Mistrzu i Małgorzacie" 10000 "${COMMON[@]}"
agent-device press 'label="Sesje RPG w Mistrzu i Małgorzacie"' "${COMMON[@]}"

# Find and open the target session card.
echo "Scrolling to Przygoda w Mieście Neonów..."
for _ in {1..8}; do
  if agent-device find "Open details for Przygoda w Mieście Neonów" click --first "${COMMON[@]}"; then
    break
  fi
  agent-device scroll down "${COMMON[@]}"
done

# Work around iOS Safari's initial modal scroll position.
echo "Swiping down to reveal modal content..."
agent-device swipe 200 250 200 700 "${COMMON[@]}"

# Demonstrate that the Close button is present, then try it.
echo "Trying to close the modal..."
agent-device wait 'label="Close"' 5000 "${COMMON[@]}"
agent-device press 'label="Close"' "${COMMON[@]}"

echo "Final snapshot:"
agent-device snapshot -i "${COMMON[@]}"
