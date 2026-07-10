#!/bin/bash
###############################################################################
# LHAMS 환경 구성 스크립트 (RHEL 8.x)
# - inotify 커널 리소스 확장, 패키지 설치, auditd 규칙, ClamAV 데몬 기동
# 실행: sudo bash setup_env.sh
###############################################################################
set -euo pipefail

WATCH_DIR="/mail/test_monitor"
PROJECT_ROOT="/mail/lhams_project"

echo "=== [1/6] 커널 inotify 리소스 확장 ==="
if ! grep -q "fs.inotify.max_user_watches" /etc/sysctl.conf; then
    echo "fs.inotify.max_user_watches=524288" >> /etc/sysctl.conf
fi
sysctl -p

echo "=== [2/6] 패키지 설치 (EPEL, inotify-tools, ClamAV, Python) ==="
dnf install -y --disableplugin=subscription-manager epel-release
dnf install -y --disableplugin=subscription-manager inotify-tools clamav clamav-update clamd audit python3 python3-pip
pip3 install watchdog

echo "=== [3/6] 디렉토리 구성 ==="
mkdir -p "$WATCH_DIR" \
         "$PROJECT_ROOT/data/quarantine" \
         "$PROJECT_ROOT/data/logs"

echo "=== [4/6] ClamAV 시그니처 갱신 및 데몬 기동 ==="
freshclam || echo "[WARN] freshclam 실패 - 네트워크 확인 필요"
# clamd 소켓 스캔 설정
sed -i 's/^Example/#Example/' /etc/clamd.d/scan.conf
sed -i 's|^#LocalSocket .*|LocalSocket /run/clamd.scan/clamd.sock|' /etc/clamd.d/scan.conf
systemctl enable --now clamd@scan

echo "=== [5/6] auditd 커널 감사 규칙 적용 ==="
cp "$(dirname "$0")/auditd_rules.rules" /etc/audit/rules.d/lhams.rules
augenrules --load
auditctl -l | grep lhams || true

echo "=== [6/6] SELinux / 방화벽 (Nginx 배포용) ==="
if command -v semanage >/dev/null 2>&1; then
    semanage fcontext -a -t httpd_sys_content_t "$PROJECT_ROOT/frontend/dist(/.*)?" 2>/dev/null || true
    restorecon -Rv "$PROJECT_ROOT/frontend/dist" 2>/dev/null || true
fi
firewall-cmd --permanent --add-service=http 2>/dev/null || true
firewall-cmd --reload 2>/dev/null || true

echo ""
echo "환경 구성 완료. 다음 단계:"
echo "  1) sudo bash install_services.sh   # systemd 서비스 등록"
echo "  2) cd $PROJECT_ROOT/frontend && npm install && npm run build"
