#!/bin/bash
# systemd 서비스 등록 (자가 치유: 비정상 종료 시 5초 내 재기동)
set -e
cp /mail/lhams_project/systemd/lhams-watchdog.service /etc/systemd/system/
cp /mail/lhams_project/systemd/lhams-realtime.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now lhams-watchdog lhams-realtime
systemctl status lhams-watchdog --no-pager
