#!/usr/bin/env bash
# Run the test suite inside the project's pygame container.
#
# The container (default: angry_goodall, image rpg_map) has pygame installed
# and bind-mounts the host home directory at /home/user, so the project is
# visible at the path below. Any extra arguments are passed to unittest.
set -euo pipefail

CONTAINER="${MONOPOLY_CONTAINER:-angry_goodall}"
PROJECT_IN_CONTAINER="/home/user/Claude/PHY199RAP/monopoly_oligarchy"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "Container '$CONTAINER' is not running. Start it with: docker start $CONTAINER" >&2
  exit 1
fi

docker exec \
  -e SDL_VIDEODRIVER=dummy \
  -e PYTHONDONTWRITEBYTECODE=1 \
  "$CONTAINER" \
  bash -lc "cd '$PROJECT_IN_CONTAINER' && python3 -m unittest discover -s tests -t . ${*:-}"
