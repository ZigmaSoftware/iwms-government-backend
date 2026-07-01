#!/bin/bash
set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

BACKEND_DIR="/home/admin/localserver/iwmsGovernment/iwms-government-backend"
LOG_DIR="/home/admin/localserver/iwmsGovernment/logs"
LOG="$LOG_DIR/backend_sync.log"
BRANCH="main"
SERVICE="django"
TOKEN_FILE="$HOME/Downloads/BP.txt"
PASSWORD_FILE="/home/admin/admin_password.txt"
USERNAME="ZigmaSoftware"
REPO_URL="https://github.com/ZigmaSoftware/iwms-government-backend.git"
LEGACY_VENV_DIR="/home/admin/localserver/iwms-backend/venv"

STASH_CREATED=0
PREV_COMMIT=""
AUTH_REPO_URL=""

resolve_venv_dir() {
    local candidate

    for candidate in "$BACKEND_DIR/.venv" "$BACKEND_DIR/venv" "$LEGACY_VENV_DIR"; do
        if [[ -x "$candidate/bin/python" ]]; then
            echo "$candidate"
            return 0
        fi
    done

    return 1
}

log() {
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $1" >> "$LOG"
}

ensure_origin_remote() {
    local current_remote=""

    if git remote get-url origin >/dev/null 2>&1; then
        current_remote=$(git remote get-url origin)
        if [[ "$current_remote" != "$REPO_URL" ]]; then
            git remote set-url origin "$REPO_URL"
            log "Updated origin to $REPO_URL."
        fi
    else
        git remote add origin "$REPO_URL"
        log "Added missing origin remote: $REPO_URL."
    fi
}

restore_stash() {
    if [[ "$STASH_CREATED" -eq 1 ]]; then
        if git stash pop >> "$LOG" 2>&1; then
            log "Restored stashed local changes."
        else
            log "Stash restore needs manual attention."
        fi
    fi
}

restart_service() {
    if [[ -f "$PASSWORD_FILE" ]]; then
        sudo -S systemctl restart "$SERVICE" < "$PASSWORD_FILE" >> "$LOG" 2>&1
    else
        sudo systemctl restart "$SERVICE" >> "$LOG" 2>&1
    fi
}

rollback() {
    if [[ -n "$PREV_COMMIT" ]]; then
        log "Rolling back to $PREV_COMMIT."
        git reset --hard "$PREV_COMMIT" >> "$LOG" 2>&1
        restart_service || true
    fi
}

install_requirements() {
    local venv_dir=""

    if venv_dir=$(resolve_venv_dir); then
        "$venv_dir/bin/pip" install -r requirements.txt >> "$LOG" 2>&1
    else
        python3 -m pip install --break-system-packages -r requirements.txt >> "$LOG" 2>&1
    fi
}

trap restore_stash EXIT

mkdir -p "$LOG_DIR"
log "Backend sync started."

if [[ ! -d "$BACKEND_DIR/.git" ]]; then
    log "Backend repo not found at $BACKEND_DIR."
    exit 1
fi

if [[ ! -r "$TOKEN_FILE" ]]; then
    log "Token file not found at $TOKEN_FILE."
    exit 1
fi

TOKEN=$(tr -d ' \n' < "$TOKEN_FILE")
if [[ -z "$TOKEN" ]]; then
    log "Token file is empty."
    exit 1
fi

AUTH_REPO_URL="https://${USERNAME}:${TOKEN}@github.com/ZigmaSoftware/iwms-government-backend.git"

cd "$BACKEND_DIR"

ensure_origin_remote

HAS_UNTRACKED=0
if [[ -n "$(git ls-files --others --exclude-standard)" ]]; then
    HAS_UNTRACKED=1
fi

if ! git diff --quiet || ! git diff --cached --quiet || [[ "$HAS_UNTRACKED" -eq 1 ]]; then
    git stash push --include-untracked -m "backend-sync-$(date +%s)" >> "$LOG" 2>&1
    STASH_CREATED=1
    log "Stashed local changes before sync."
fi

git fetch "$AUTH_REPO_URL" "$BRANCH:refs/remotes/origin/$BRANCH" >> "$LOG" 2>&1

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$BRANCH")

if [[ "$LOCAL" == "$REMOTE" ]]; then
    log "No backend updates."
    exit 0
fi

PREV_COMMIT="$LOCAL"

if ! git pull --rebase "$AUTH_REPO_URL" "$BRANCH" >> "$LOG" 2>&1; then
    log "Merge conflict. Aborting rebase."
    git rebase --abort >> "$LOG" 2>&1 || true
    exit 1
fi

CHANGED_FILES=$(git diff --name-only "$PREV_COMMIT" HEAD)
if [[ -n "$CHANGED_FILES" ]]; then
    log "Backend repo updated."

    if echo "$CHANGED_FILES" | grep -q '^requirements\.txt$'; then
        log "Installing Python dependencies."
        if ! install_requirements; then
            log "Dependency install failed."
            rollback
            exit 1
        fi
    fi

    log "Restarting backend service."
    if ! restart_service; then
        log "Backend restart failed."
        rollback
        exit 1
    fi
fi

log "Performing health check."
if curl -s --max-time 5 http://127.0.0.1:8000 >/dev/null; then
    log "Backend healthy."
else
    log "Backend unhealthy after sync."
    rollback
    exit 1
fi

AHEAD_COUNT=$(git rev-list --count "origin/$BRANCH..HEAD")
if [[ "$AHEAD_COUNT" -gt 0 ]]; then
    log "Local branch is ahead by $AHEAD_COUNT commit(s). Pushing to origin."
    if ! git push "$AUTH_REPO_URL" "$BRANCH" >> "$LOG" 2>&1; then
        log "Push failed after successful sync."
        exit 1
    fi
fi

log "Backend sync completed."
