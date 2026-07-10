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

## 세미나 데모 시나리오

```bash
cd /mail/test_monitor

touch new_mail.txt                                   # 1) 생성 → Low
echo "update" > new_mail.txt                         # 2) 수정 → Low
mv new_mail.txt replaced_mail.txt                    # 3) 교체(이동) → Medium, 행위자 기록
rm replaced_mail.txt                                 # 4) 삭제 → High
wget https://secure.eicar.org/eicar.com -O test.com  # 5) 악성코드 → Critical + 자동 격리
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

## 운영 참고

- 로그: `/mail/lhams_project/data/logs/` — 자정마다 로테이션, 30일 보관
- 격리: `/mail/lhams_project/data/quarantine/`
- 커널 watch 한도: `fs.inotify.max_user_watches=524288` (setup_env.sh가 적용)
- `data/` 디렉토리는 Git 커밋 금지 (사내 GitLab 가이드 3.8 대용량/바이너리 금지 원칙)

## GitLab 등록 시 (사내 표준 준수)

- `.gitignore`에 `node_modules/`, `dist/`, `data/`, `*.log` 필수 등록 (첫 커밋 전)
- 줄바꿈: `git config --global core.autocrlf input` (사내 표준 LF)
- 커밋 메시지: 제목 50자 + 본문(변경 이유) + `Refs #WorkItem번호`
