#!/bin/bash
###############################################################################
# LHAMS 실시간 악성코드 감시 스크립트 (inotifywait + clamdscan)
# 사용법: ./realtime_monitor.sh <감시_디렉토리>
###############################################################################

WATCH_DIR="$1"
BASE_DIR="/mail/lhams_project/data"
LOG_FILE="$BASE_DIR/logs/realtime_scan_$(date '+%Y-%m-%d').log"
QUARANTINE_DIR="$BASE_DIR/quarantine"

if [ -z "$WATCH_DIR" ]; then
    echo "Usage: $0 <directory_to_watch>"
    echo "Example: $0 /mail/test_monitor"
    exit 1
fi

mkdir -p "$(dirname "$LOG_FILE")" "$QUARANTINE_DIR"

echo "=== LHAMS ClamAV Real-time Monitoring ==="
echo "Watching:  $WATCH_DIR"
echo "Log file:  $LOG_FILE"
echo "Press Ctrl+C to stop"
echo ""

# Vim swap/숨김 파일 제외, 생성/쓰기완료/이동유입 이벤트 감시
inotifywait -m -r -e create,close_write,moved_to \
    --exclude '\.(swp|swx|swpx)$|/\.' \
    "$WATCH_DIR" --format '%w%f' | while read -r FILE
do
    [ -f "$FILE" ] || continue

    # 날짜 변경 대응 (자정 로테이션)
    LOG_FILE="$BASE_DIR/logs/realtime_scan_$(date '+%Y-%m-%d').log"
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$TIMESTAMP] Detected: $FILE" | tee -a "$LOG_FILE"

    # clamd 소켓 통신 검사 (메모리 상주 시그니처, 저부하)
    SCAN_RESULT=$(clamdscan --stream --fdpass --no-summary "$FILE" 2>&1)

    if echo "$SCAN_RESULT" | grep -q "FOUND"; then
        echo "[$TIMESTAMP] MALWARE DETECTED: $FILE" | tee -a "$LOG_FILE"
        echo "$SCAN_RESULT" | tee -a "$LOG_FILE"

        if [ -f "$FILE" ]; then
            mv "$FILE" "$QUARANTINE_DIR/" 2>/dev/null \
                && echo "[$TIMESTAMP] Quarantined to: $QUARANTINE_DIR" | tee -a "$LOG_FILE" \
                || echo "[$TIMESTAMP] Quarantine failed: $FILE" | tee -a "$LOG_FILE"
        else
            echo "[$TIMESTAMP] File vanished before quarantine: $FILE" | tee -a "$LOG_FILE"
        fi
    else
        echo "[$TIMESTAMP] Clean: $FILE" | tee -a "$LOG_FILE"
    fi
done
