#!/bin/bash
# Phase VI Restore Script
# Restores PostgreSQL database and blockchain data from backup

set -e

# Configuration
BACKUP_FILE="${1}"
DATABASE_HOST="${DATABASE_HOST:-postgres}"
DATABASE_PORT="${DATABASE_PORT:-5432}"
DATABASE_USER="${DATABASE_USER:-postgres}"
DATABASE_NAME="${DATABASE_NAME:-galaxy}"
BLOCKCHAIN_DATA_DIR="${BLOCKCHAIN_DATA_DIR:-/data/authority-chain}"
TEMP_RESTORE_DIR="/tmp/galaxy_restore_$$"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $1"
}

# Cleanup function
cleanup() {
    log_info "Cleaning up temporary files..."
    rm -rf "$TEMP_RESTORE_DIR"
}

# Register cleanup to run on exit
trap cleanup EXIT

# Validation
if [ -z "$BACKUP_FILE" ]; then
    log_error "Backup file not specified"
    echo "Usage: $0 <backup-file.tar.gz>"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    log_error "Backup file not found: $BACKUP_FILE"
    exit 1
fi

log_info "Starting restore process..."
log_info "Backup file: $BACKUP_FILE"
log_debug "Temporary restore directory: $TEMP_RESTORE_DIR"

# Create temporary extraction directory
mkdir -p "$TEMP_RESTORE_DIR"
log_info "Created temporary restore directory"

# Extract backup archive
log_info "Extracting backup archive..."
tar -xzf "$BACKUP_FILE" -C "$TEMP_RESTORE_DIR"

if [ $? -ne 0 ]; then
    log_error "Failed to extract backup archive"
    exit 1
fi

# Find the backup name
BACKUP_NAME=$(find "$TEMP_RESTORE_DIR" -maxdepth 1 -type d -name "galaxy_backup_*" | basename $(ls -1d $(find "$TEMP_RESTORE_DIR" -maxdepth 1 -type d -name "galaxy_backup_*") | head -1))

if [ -z "$BACKUP_NAME" ]; then
    log_error "Could not find valid backup directory in archive"
    exit 1
fi

BACKUP_SOURCE="$TEMP_RESTORE_DIR/$BACKUP_NAME"
log_info "Found backup: $BACKUP_NAME"

# Validate backup contents
if [ ! -f "$BACKUP_SOURCE/database.dump" ]; then
    log_error "Database dump not found in backup"
    exit 1
fi
log_info "Backup validation passed"

# Restore PostgreSQL Database
log_warn "This will OVERWRITE the existing database. Continue? (yes/no)"
read -r CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    log_info "Restore cancelled"
    exit 0
fi

log_info "Restoring PostgreSQL database..."
# Drop existing database and recreate
PGPASSWORD="${DATABASE_PASSWORD:-postgres}" psql \
    -h "$DATABASE_HOST" \
    -p "$DATABASE_PORT" \
    -U "$DATABASE_USER" \
    -c "DROP DATABASE IF EXISTS $DATABASE_NAME;" || true

PGPASSWORD="${DATABASE_PASSWORD:-postgres}" psql \
    -h "$DATABASE_HOST" \
    -p "$DATABASE_PORT" \
    -U "$DATABASE_USER" \
    -c "CREATE DATABASE $DATABASE_NAME;"

# Restore from dump
PGPASSWORD="${DATABASE_PASSWORD:-postgres}" pg_restore \
    -h "$DATABASE_HOST" \
    -p "$DATABASE_PORT" \
    -U "$DATABASE_USER" \
    -d "$DATABASE_NAME" \
    -F c \
    "$BACKUP_SOURCE/database.dump"

if [ $? -eq 0 ]; then
    log_info "Database restore completed successfully"
else
    log_error "Database restore failed"
    exit 1
fi

# Restore Blockchain Data
if [ -f "$BACKUP_SOURCE/blockchain-data.tar.gz" ]; then
    log_info "Restoring blockchain data..."
    
    # Backup existing blockchain data
    if [ -d "$BLOCKCHAIN_DATA_DIR" ]; then
        log_info "Backing up existing blockchain data..."
        EXISTING_BACKUP="${BLOCKCHAIN_DATA_DIR}.backup.$(date +%s)"
        mv "$BLOCKCHAIN_DATA_DIR" "$EXISTING_BACKUP"
        log_info "Existing blockchain data saved to $EXISTING_BACKUP"
    fi
    
    # Create blockchain data directory
    mkdir -p "$BLOCKCHAIN_DATA_DIR"
    
    # Extract blockchain data
    tar -xzf "$BACKUP_SOURCE/blockchain-data.tar.gz" \
        -C "$BLOCKCHAIN_DATA_DIR"
    
    if [ $? -eq 0 ]; then
        log_info "Blockchain data restore completed successfully"
    else
        log_error "Blockchain data restore failed"
        if [ -d "$EXISTING_BACKUP" ]; then
            log_info "Restoring previous blockchain data..."
            rm -rf "$BLOCKCHAIN_DATA_DIR"
            mv "$EXISTING_BACKUP" "$BLOCKCHAIN_DATA_DIR"
        fi
        exit 1
    fi
else
    log_warn "Blockchain data backup not found in archive (non-critical)"
fi

# Display metadata
if [ -f "$BACKUP_SOURCE/metadata.json" ]; then
    log_info "Backup metadata:"
    cat "$BACKUP_SOURCE/metadata.json" | sed 's/^/  /'
fi

log_info "Restore completed successfully!"
log_warn "Please verify the restored data and restart your services"
echo ""
