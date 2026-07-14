# LHAMS — Linux Hybrid Mail Audit System

크리니티 웹메일 서버 환경에서 **"어떤 사람이, 몇 시에, 어떤 파일을 교체/삭제/실행했는지"**를
실시간으로 기록하고 관제하는 세미나 프로젝트입니다.

```
inotifywait (경량 트리거) ─┐
auditd     (커널 행위자 추적) ─┼─► Python Watchdog (컨트롤 타워) ─► lhams_audit.json
clamd      (악성코드 스캐너) ─┘            │                              │
                                일별 텍스트 로그 로테이션        React+SCSS 대시보드 (3초 폴링)
```

## 디렉토리 구성

```
lhams_project/
├── scripts/
│   ├── setup_env.sh          # OS 튜닝(inotify) + 패키지 + auditd + ClamAV 일괄 구성
│   ├── install_services.sh   # systemd 서비스 등록 (자가 치유)
│   ├── realtime_monitor.sh   # inotifywait + clamdscan 실시간 감시/격리 스크립트
│   └── auditd_rules.rules    # 커널 감사 규칙 (wa + execve)
├── agent/
│   ├── lhams_watchdog.py     # Python 컨트롤 타워 (auditd 행위자 추적 + JSON 적재)
│   └── requirements.txt
├── java/src/com/crinity/lhams/
│   └── FileAuditWatcher.java # 웹메일(Java/Tomcat) 임베딩용 대안 에이전트
├── systemd/                  # lhams-watchdog / lhams-realtime 유닛 파일
├── nginx/lhams.conf          # 프로덕션 배포 설정 (dist + JSON Alias)
└── frontend/                 # React 18 + Vite 5 + SCSS 관제 대시보드
```

## 빠른 시작 (RHEL 8.x)

```bash
# 0) 프로젝트 배치
sudo cp -r lhams_project /mail/

# 1) 환경 구성 (커널 튜닝, 패키지, auditd, clamd)
cd /mail/lhams_project/scripts
sudo bash setup_env.sh

# 2) systemd 서비스 등록 — 죽어도 5초 내 재기동 (Restart=always)
sudo bash install_services.sh

# 3) 프론트엔드 (Node.js 20.x 필요)
cd /mail/lhams_project/frontend
npm install
npm run dev -- --host        # 개발: http://서버IP:5173
# 또는 프로덕션:
npm run build
sudo cp ../nginx/lhams.conf /etc/nginx/conf.d/
sudo systemctl restart nginx  # http://서버IP
```

### 설정 방식 — `LHAMS_HOME` 한 줄로 배포

`lhams_watchdog.py`는 기본적으로 `/mail/lhams_project`를 홈으로 가정합니다. 다른 경로에
배치했다면 개별 `LHAMS_xxx` 환경변수를 일일이 지정하는 대신 `LHAMS_HOME` 하나만 지정하면
`data/`, `frontend/public/lhams_audit.json` 등 모든 하위 경로가 자동으로 구성됩니다
(개별 `LHAMS_WATCH_DIR` 등을 지정하면 그 값이 항상 우선합니다 — 하위호환 유지).

```bash
# systemd 유닛(Environment=) 또는 실행 전 export로 지정
export LHAMS_HOME=/mail/lhams_project

# 다중 서버 / SI 고객사 구축 시 이 인스턴스를 식별하는 이름표 (대시보드 헤더에 표시)
export LHAMS_SITE_NAME="본사 메일서버"
export LHAMS_SITE_ID="hq-01"
```

## 세미나 데모 시나리오

```bash
cd /mail/test_monitor

touch new_mail.txt                                   # 1) 생성 → Low
echo "update" > new_mail.txt                         # 2) 수정 → Low
mv new_mail.txt replaced_mail.txt                    # 3) 교체(이동) → Medium, 행위자 기록
rm replaced_mail.txt                                 # 4) 삭제 → High

# 5) 악성코드 → Critical + 자동 격리
# 폐쇄망(인터넷 차단) 환경 대응: 인터넷에서 내려받는 대신 EICAR 테스트 문자열을
# 로컬에서 직접 생성한다 (ClamAV가 시그니처로 인식하는 표준 테스트 문자열, 실제 악성코드 아님)
printf '%s' 'X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*' > test.com
```

대시보드에서 각 행 왼쪽의 **위험도 레일**(색 띠)과 함께 시각·이벤트·경로·**행위자(auditd auid)**·
프로세스가 3초 이내에 갱신됩니다.

## "누가 했는지"를 어떻게 아는가 (핵심 차별점)

- 파일 소유자(owner)는 결과일 뿐입니다. 예: root로 sudo 작업 시 owner는 root.
- LHAMS는 auditd가 커널에서 기록한 **auid(로그인 사용자)** 와 **comm/exe(실행 프로세스)** 를
  `ausearch -k lhams_audit -f <경로>` 로 조회해 이벤트에 결합합니다.
- 따라서 "kim.dev가 09:38에 rm으로 report_q2.eml을 삭제"처럼 행위 주체가 남습니다.

## Java 에이전트 (선택)

Python을 올릴 수 없는 웹메일 WAS에 임베딩할 때:

```bash
javac -d out java/src/com/crinity/lhams/FileAuditWatcher.java
java -cp out com.crinity.lhams.FileAuditWatcher /mail/test_monitor
```

Tomcat이라면 `ServletContextListener.contextInitialized()`에서 스레드로 기동하세요.

## 관리자 기능 (감시 경로 / 격리소 / 무시 규칙 / 체크리스트 / 변경 이력)

대시보드 상단 **관리자** 탭에서 서비스 재시작 없이 다음을 조작할 수 있습니다.

- **작업자 식별**: 관리자 탭 진입 시 이름/사번을 1회 입력(브라우저에 저장) — 이후 이 페이지에서 하는
  모든 변경에 작업자명이 함께 기록됩니다. 언제든 상단의 "변경" 버튼으로 다시 설정할 수 있습니다.
- **설치 체크리스트**: 신규 서버 구축 시 진행해야 할 단계(환경 구성 → systemd 등록 → auditd 규칙 →
  Watchdog 기동 확인 → 감시 경로 등록 → 프론트 빌드 → nginx 배포 → 데모 점검)를 체크박스로 추적합니다.
  완료 표시는 팀 전체에 공유되며 완료자·완료 시각이 함께 남아, 여러 개발자가 나눠서 구축을 진행해도
  누가 어디까지 했는지 한눈에 파악할 수 있습니다.
- **감시 경로**: 경로 추가/삭제, 개별 on/off, 하위 폴더 포함 여부 설정
- **격리소**: 악성코드로 격리된 파일 목록 확인, 오탐 시 원래 경로로 복원 또는 영구 삭제
- **무시 규칙**: 이벤트 기록에서 제외할 파일 확장자/패턴(`.bak` 등) 편집
- **관리자 변경 이력**: 위 조작(경로 추가/삭제/수정, 격리 복원/삭제, 무시 규칙 변경, 체크리스트 완료)이
  "언제·누가·무엇을·어떻게" 바꿨는지 시간 역순으로 표시됩니다.

내부적으로 `lhams_watchdog.py`가 Flask로 관리 API(`/api/...`, 기본 포트 `8787`)를 백그라운드 스레드로 함께 띄우고,
아래 파일에 상태를 영속화합니다.

| 파일 | 내용 |
|---|---|
| `data/config.json` | 감시 경로 목록, 무시 규칙 |
| `data/quarantine/_meta.json` | 격리 파일의 원본 경로/시각/사유 |
| `data/checklist.json` | 설치 체크리스트 진행 상태(완료자/완료 시각) |
| `data/admin_audit.json` | 관리자 변경 이력(최근 500건) — 파일 감사로그(`lhams_audit.json`)와는 별개로, "관리 조작 자체"를 감사 대상으로 기록 |
| `data/config_backups/` | `config.json` 변경 시마다 남는 자동 백업본 (최근 20개 보관) |

프론트엔드는 dev 환경에서 Vite 프록시로, 운영 환경에서는 `nginx/lhams.conf`의 `/api/` 리버스 프록시로 이 API에 접근합니다.

```bash
# 관리 API 포트 변경 (기본 8787)
export LHAMS_API_PORT=8787
```

### "누가 관리자 설정을 바꿨는지"에 대한 참고

관리자 탭의 작업자 식별은 로그인 없이 이름을 입력받는 경량 방식입니다(세미나/PoC 규모에 맞춘 선택).
브라우저 로컬 저장소에만 남기 때문에 신뢰 경계 안(사내망, 신뢰된 관리자만 접근)에서 "누가 바꿨다고
스스로 밝혔는지"를 기록하는 용도이며, 실제 계정 인증이 필요하면 `agent/lhams_watchdog.py`의
`actor_of()` 부분을 사내 SSO/계정 로그인 연동으로 교체하면 됩니다.

## 다중 서버 / SI 고객사 운영

여러 서버·고객사에 LHAMS를 나눠서 구축·운영할 때 필요한 기능들입니다.

- **사이트 식별**: `LHAMS_SITE_NAME`/`LHAMS_SITE_ID`로 인스턴스에 이름표를 붙이면, 대시보드
  헤더에 항상 표시되어 "지금 어느 서버 화면을 보고 있는지"를 혼동하지 않습니다.
- **시스템 진단 (`GET /api/health`)**: 사이트명/ID, 버전, 에이전트 가동 시간, 감시 경로
  활성/전체 개수, 격리 파일 수, 마지막 이벤트 수신 시각을 한 번에 반환합니다. 요약 탭에서
  실시간으로 보여주며, 별도 모니터링 시스템(Zabbix/Prometheus 등)에서 헬스체크 용도로도
  그대로 호출할 수 있습니다.
- **감시 경로 상태 표시**: 등록은 됐지만 실제 디렉토리가 없어졌거나 권한 문제로 감시가 안 되고
  있는 경로를 관리자 탭에서 "⚠ 경로가 존재하지 않습니다" 배지로 즉시 확인할 수 있습니다
  (이전에는 서버 로그를 봐야만 알 수 있었던 실패가 조용히 묻히는 문제를 해결).
- **설정 자동 백업**: `data/config.json`이 바뀔 때마다 `data/config_backups/`에 타임스탬프
  이름으로 스냅샷이 남습니다(최근 20개 보관, 자동 정리). 실수로 잘못 바꿔도 되돌릴 근거가 남습니다.
- **설정 내보내기 / 가져오기**: 관리자 탭 "설정 백업/이전"에서 현재 감시 경로·무시 규칙을 JSON
  파일로 내려받거나, 다른 서버에서 받은 JSON을 그대로 업로드해 동일하게 적용할 수 있습니다.
  신규 고객사에 표준 설정을 그대로 복제 배포할 때 유용합니다. (누가 가져오기를 했는지도
  관리자 변경 이력에 `CONFIG_IMPORT`로 남습니다.)

## 폐쇄망(에어갭) 배포 가이드

이 프로젝트는 런타임에 외부 인터넷 호출이 전혀 없습니다 (Flask 에이전트·React 대시보드 모두
로컬 통신만 사용, CDN 폰트/스크립트 없음). 인터넷 접속이 차단된 고객사 환경에 반입하려면
**빌드는 인터넷이 되는 환경에서, 배포는 폐쇄망에서** 하는 방식을 권장합니다.

```bash
# ── 인터넷이 되는 빌드 서버에서 ──────────────────────────────
cd frontend
npm install && npm run build          # dist/ 생성 — 이후 이 산출물만 반입

# Python 의존성도 미리 내려받아 오프라인 설치 패키지로 준비
pip download -r ../agent/requirements.txt -d ../agent/vendor

# ── 폐쇄망 반입 대상 (USB/사내 자료전송시스템 등) ─────────────
lhams_project/
├── agent/            # lhams_watchdog.py, requirements.txt, vendor/ (오프라인 wheel)
├── frontend/dist/     # 빌드 산출물만 반입 (frontend/src, node_modules 불필요)
├── nginx/, scripts/, systemd/

# ── 폐쇄망 서버에서 ──────────────────────────────────────────
pip install --no-index --find-links=agent/vendor -r agent/requirements.txt
sudo bash scripts/setup_env.sh          # 패키지 저장소(yum/dnf)도 사내 미러 필요
sudo bash scripts/install_services.sh
sudo cp nginx/lhams.conf /etc/nginx/conf.d/ && sudo systemctl restart nginx
```

체크할 점:

- 위 "세미나 데모 시나리오"의 악성코드 테스트는 이미 `wget` 없이 로컬에서 EICAR 문자열을
  생성하도록 되어 있어 폐쇄망에서도 그대로 동작합니다.
- `setup_env.sh`가 설치하는 OS 패키지(auditd, clamav 등)는 별도로 사내 yum/dnf 미러가
  필요합니다 — 이 저장소 자체의 책임 범위 밖이므로 사내 인프라팀과 사전 협의하세요.
- 리포지토리 루트의 `package.json`/`package-lock.json`(`@anthropic-ai/sdk`)은 LHAMS 서비스와
  무관한 별도 파일이므로 폐쇄망 반입 목록에서 제외해도 됩니다.

## 운영 참고

- 로그: `/mail/lhams_project/data/logs/` — 자정마다 로테이션, 30일 보관
- 격리: `/mail/lhams_project/data/quarantine/`
- 커널 watch 한도: `fs.inotify.max_user_watches=524288` (setup_env.sh가 적용)
- `data/` 디렉토리는 Git 커밋 금지 (사내 GitLab 가이드 3.8 대용량/바이너리 금지 원칙)

## GitLab 등록 시 (사내 표준 준수)

- `.gitignore`에 `node_modules/`, `dist/`, `data/`, `*.log` 필수 등록 (첫 커밋 전)
- 줄바꿈: `git config --global core.autocrlf input` (사내 표준 LF)
- 커밋 메시지: 제목 50자 + 본문(변경 이유) + `Refs #WorkItem번호`
