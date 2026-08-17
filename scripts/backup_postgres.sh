#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$BACKUP_DIR"

docker compose -f "$ROOT_DIR/docker-compose.prod.yml" exec -T db \
  pg_dump -U "${POSTGRES_USER:-carbargains}" \
  -d "${POSTGRES_DB:-carbargains}" -Fc \
  > "$BACKUP_DIR/carbargains-$STAMP.dump"

find "$BACKUP_DIR" -type f -name 'carbargains-*.dump' \
  -mtime "+$RETENTION_DAYS" -delete

echo "Backup creado: $BACKUP_DIR/carbargains-$STAMP.dump"
