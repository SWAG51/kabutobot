#!/bin/bash
# kabutobot — アップデートスクリプト
# ダッシュボードの「アップデート」ボタンまたは手動で実行
# 使い方: bash pi/update.sh

INSTALL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$INSTALL_DIR/kabutobot.log"
DOTENV="$INSTALL_DIR/.env"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"
}

log "========== アップデート開始 =========="
cd "$INSTALL_DIR"

# ─── gitリモート確認 ───
if ! git remote get-url origin > /dev/null 2>&1; then
    log "❌ gitリモートが設定されていません"
    exit 1
fi

# ─── 現在のコミットハッシュを保存 ───
OLD_HASH=$(git rev-parse HEAD)
OLD_SHORT="${OLD_HASH:0:7}"

# ─── git fetch + reset --hard（ローカル変更を強制上書き）───
log "git fetch + reset 実行中..."
git fetch origin master 2>&1 | tee -a "$LOG"
git reset --hard origin/master 2>&1 | tee -a "$LOG"

NEW_HASH=$(git rev-parse HEAD)
NEW_SHORT="${NEW_HASH:0:7}"

# ─── 変更なしの場合も再起動 ───
if [ "$OLD_HASH" = "$NEW_HASH" ]; then
    log "✅ 変更なし（最新: $NEW_SHORT）→ サービス再起動のみ実行"
    if systemctl --user restart kabutobot 2>&1 | tee -a "$LOG"; then
        log "  ✅ kabutobot 再起動完了"
    else
        log "  ❌ kabutobot 再起動失敗"
    fi
    log "========== 再起動完了 =========="
    exit 0
fi

log "✅ 更新あり: $OLD_SHORT → $NEW_SHORT"

# ─── 変更されたファイルを表示 ───
CHANGED=$(git diff "$OLD_HASH" "$NEW_HASH" --name-only)
log "変更ファイル:"
echo "$CHANGED" | while read -r f; do log "  - $f"; done

# ─── requirements.txt が変更された場合は pip install ───
if echo "$CHANGED" | grep -q "requirements.txt"; then
    log "requirements.txt変更検出 → pip install 実行..."
    pip3 install -r requirements.txt 2>&1 | tee -a "$LOG"
fi

# ─── Discord通知（.envからWEBHOOK_URLを取得）───
if [ -f "$DOTENV" ]; then
    WEBHOOK=$(grep "^DISCORD_WEBHOOK_URL=" "$DOTENV" | cut -d'=' -f2-)
    if [ -n "$WEBHOOK" ]; then
        curl -s -X POST "$WEBHOOK" \
            -H "Content-Type: application/json" \
            -d "{\"embeds\":[{\"title\":\"🔄 kabutobot アップデート完了\",\"description\":\"$OLD_SHORT → $NEW_SHORT\",\"color\":3066993,\"fields\":[{\"name\":\"変更ファイル\",\"value\":\"$(echo "$CHANGED" | head -5 | sed 's/^/• /' | tr '\n' '\\n')\",\"inline\":false}]}]}" \
            > /dev/null 2>&1
        log "Discord通知送信完了"
    fi
fi

# ─── サービス再起動 ───
log "サービス再起動中..."
if sudo systemctl restart kabutobot 2>&1 | tee -a "$LOG"; then
    log "  ✅ kabutobot 再起動完了"
else
    log "  ❌ kabutobot 再起動失敗"
fi

log "========== アップデート完了 =========="
