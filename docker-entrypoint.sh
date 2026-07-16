#!/bin/sh
set -e

chown -R appuser:appuser "${LLAMADECK_CONFIG_DIR:-/data}" 2>/dev/null || true

SOCKET="/var/run/docker.sock"
if [ -S "$SOCKET" ]; then
  GID=$(stat -c "%g" "$SOCKET" 2>/dev/null)
  if [ -n "$GID" ] && [ "$GID" -ne 0 ] 2>/dev/null; then
    groupadd -g "$GID" docker-host 2>/dev/null || true
    usermod -aG "$GID" appuser 2>/dev/null || true
  fi
fi

exec su appuser -c "python -m backend.main $*"
