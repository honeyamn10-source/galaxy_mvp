#!/bin/bash
# Phase VI Backup Script
# Backs up PostgreSQL database and blockchain data

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/backups}"
DATABASE_HOST="${DATABASE_HOST:-postgres}"
DATABASE_PORT="${DATABASE_PORT:-5432}"
DATABASE_USER="${DATABASE_USER:-postgres}"
DATABASE_NAME="${DATABASE_NAME:-galaxy}"
BLOCKCHAIN_DATA_DIR="${BLOCKCHAIN_DATA_DIR:-/data/authority-chain}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="galaxy_backup_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Create backup directory
mkdir -p "$BACKUP_DIR"

log_info "Starting backup process..."
log_info "Backup destination: $BACKUP_PATH"

# Create backup subdirectory
mkdir -p "$BACKUP_PATH"

# Backup PostgreSQL Database
log_info "Backing up PostgreSQL database..."
PGPASSWORD="${DATABASE_PASSWORD:-postgres}" pg_dump \
    -h "$DATABASE_HOST" \
    -p "$DATABASE_PORT" \
    -U "$DATABASE_USER" \
    -d "$DATABASE_NAME" \
    -F c \
    -f "$BACKUP_PATH/database.dump"

if [ $? -eq 0 ]; then
    log_info "Database backup completed successfully"
    SIZE=$(du -h "$BACKUP_PATH/database.dump" | cut -f1)
    log_info "Database dump size: $SIZE"
else
    log_error "Database backup failed"
    exit 1
fi

# Backup Blockchain Data
if [ -d "$BLOCKCHAIN_DATA_DIR" ]; then
    log_info "Backing up blockchain data from $BLOCKCHAIN_DATA_DIR..."
    tar -czf "$BACKUP_PATH/blockchain-data.tar.gz" \
        -C "$BLOCKCHAIN_DATA_DIR" .
    
    if [ $? -eq 0 ]; then
        log_info "Blockchain backup completed successfully"
        SIZE=$(du -h "$BACKUP_PATH/blockchain-data.tar.gz" | cut -f1)
        log_info "Blockchain data size: $SIZE"
    else
        log_warn "Blockchain backup failed (non-critical)"
    fi
else
    log_warn "Blockchain data directory not found: $BLOCKCHAIN_DATA_DIR"
fi

# Create backup metadata
cat > "$BACKUP_PATH/metadata.json" <<EOF
{
  "backup_timestamp": "$(date -Iseconds)",
  "backup_name": "$BACKUP_NAME",
  "database": {
    "host": "$DATABASE_HOST",
    "port": "$DATABASE_PORT",
    "name": "$DATABASE_NAME"
  },
  "blockchain_data_dir": "$BLOCKCHAIN_DATA_DIR",
  "retention_days": "$RETENTION_DAYS"
}
EOF

log_info "Backup metadata created"

# Compress entire backup
log_info "Compressing backup archive..."
tar -czf "${BACKUP_PATH}.tar.gz" -C "$BACKUP_DIR" "$BACKUP_NAME"

if [ $? -eq 0 ]; then
    log_info "Backup archive created successfully"
    TOTAL_SIZE=$(du -h "${BACKUP_PATH}.tar.gz" | cut -f1)
    log_info "Total backup size: $TOTAL_SIZE"
    
    # Remove uncompressed backup directory
    rm -rf "$BACKUP_PATH"
    log_info "Temporary backup directory removed"
else
    log_error "Backup compression failed"
    exit 1
fi

# Cleanup old backups (retention policy)
log_info "Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "galaxy_backup_*.tar.gz" -mtime +$RETENTION_DAYS -delete
log_info "Old backups removed"

# Final status
log_info "Backup completed successfully!"
log_info "Backup file: ${BACKUP_PATH}.tar.gz"
echo ""
