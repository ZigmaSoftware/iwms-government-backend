#!/bin/bash
set -e

BACKEND_DIR="/home/admin/localserver/iwms-backend"
LOG="/home/admin/backend_sync.log"
BRANCH="main"
SERVICE="django"
TOKEN_FILE="$HOME/Downloads/BP.txt"
USERNAME="ZigmaSoftware"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$TIMESTAMP] Backend sync started" >> "$LOG"

cd "$BACKEND_DIR"

# Load token
TOKEN=$(cat "$TOKEN_FILE" | tr -d ' \n')

# Ensure authenticated remote URL
REMOTE_URL=$(git remote get-url origin)
if [[ "$REMOTE_URL" != https://$USERNAME:* ]]; then
    NEW_URL="https://$USERNAME:$TOKEN@${REMOTE_URL#https://}"
    git remote set-url origin "$NEW_URL"
    echo "[$TIMESTAMP] Updated Git remote with credentials." >> "$LOG"
fi

git stash --include-untracked >> "$LOG" 2>&1 || true
git fetch origin "$BRANCH" >> "$LOG" 2>&1

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/$BRANCH)

if [ "$LOCAL" = "$REMOTE" ]; then
    echo "[$TIMESTAMP] No backend updates." >> "$LOG"
    exit 0
fi

PREV_COMMIT=$(git rev-parse HEAD)

# Try merging
if ! git pull --rebase >> "$LOG" 2>&1; then
    echo "[$TIMESTAMP] Merge conflict. Aborting rebase." >> "$LOG"
    git rebase --abort >> "$LOG" 2>&1 || true
    git stash pop >> "$LOG" 2>&1 || true
    exit 1
fi

# Detect if backend files changed (exclude frontend)
if git diff --name-only $PREV_COMMIT HEAD | grep -qv "frontend"; then
    echo "[$TIMESTAMP] Backend files changed." >> "$LOG"

    # Activate the virtual environment
    source "$BACKEND_DIR/venv/bin/activate"

    # Install dependencies only when requirements.txt changed
    if git diff --name-only $PREV_COMMIT HEAD | grep -q "requirements.txt"; then
        echo "[$TIMESTAMP] Installing pip dependencies..." >> "$LOG"

        if ! pip install --break-system-packages -r requirements.txt >> "$LOG" 2>&1; then
            echo "[$TIMESTAMP] pip install failed. Rolling back..." >> "$LOG"
            deactivate
            git reset --hard "$PREV_COMMIT" >> "$LOG"
            sudo systemctl restart "$SERVICE"
            exit 1
        fi
    fi

    deactivate

    echo "[$TIMESTAMP] Performing health check..." >> "$LOG"

    # Server health check
    if curl -s --max-time 5 http://127.0.0.1:8000 >/dev/null; then
        echo "[$TIMESTAMP] Backend healthy. No restart needed." >> "$LOG"
    else
        echo "[$TIMESTAMP] Backend DOWN. Restarting service..." >> "$LOG"

        if ! sudo systemctl restart "$SERVICE" >> "$LOG" 2>&1; then
            echo "[$TIMESTAMP] Restart FAILED. Rolling back code..." >> "$LOG"
            git reset --hard "$PREV_COMMIT" >> "$LOG"
            sudo systemctl restart "$SERVICE"
            exit 1
        fi

        sleep 3
        if curl -s --max-time 5 http://127.0.0.1:8000 >/dev/null; then
            echo "[$TIMESTAMP] Backend recovered after restart." >> "$LOG"
        else
            echo "[$TIMESTAMP] Backend still unhealthy. Rolling back..." >> "$LOG"
            git reset --hard "$PREV_COMMIT" >> "$LOG"
            sudo systemctl restart "$SERVICE"
            exit 1
        fi
    fi
fi

git push origin $BRANCH >> "$LOG" 2>&1
echo "[$TIMESTAMP] Backend sync completed." >> "$LOG"


