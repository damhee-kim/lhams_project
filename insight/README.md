# Crinity Insight — 실행 가능한 데모 서비스

`docs/crinity_insight_admin.html`(정적 목업)과 `docs/Crinity_Insight_구현전환_보완명세.md`
(구현 전환 스펙)을 기반으로, 실제 HTTP/SSE 통신을 하는 로컬 데모 서비스로 구현한 모듈입니다.
LHAMS(파일 감사 관제) 프로젝트와는 완전히 독립된 별도 모듈입니다.

## 무엇이 실제이고 무엇이 시뮬레이션인가

Webmail / SpamBreaker / MailBreaker / Archiving 4대 물리 서버가 이 개발 환경에는 없으므로
**Edge Agent가 보낼 이벤트만 백엔드 프로세스 내부에서 시뮬레이션**합니다. 그 외에는 전부 실제
동작입니다.

| 항목 | 상태 |
|---|---|
| 4개 노드 CPU·MEM·DISK·큐 수치, 신규 메일 발생 | 시뮬레이션 (실 장비 부재) |
| REST API (`/api/v1/...`), SSE 실시간 스트림(`/api/v1/stream`) | 실제 (FastAPI, 브라우저 Network 탭에서 확인 가능) |
| 메일 여정 검색·필터, 격리 해제 상태 변경 | 실제 (서버 메모리 상태를 실제로 변경) |
| SOS 패키지 — 대상 노드 선택 → 진행률 SSE → 완료 시 다운로드 | 실제 (`tar.gz` 생성, SHA-256 실계산, 로컬 디스크에 실제 저장) |
| SOS 저장 경로 검증(경로 주입·Path Traversal 차단, 쓰기 권한·여유공간 확인) | 실제 서버측 검증 + 실제 `mkdir`/`disk_usage` |
| 임계치·Webhook 설정, 경보 이력, 감사 로그 | 실제 (파일로 영속화) |
| 조작(POST/PUT) API 인증, 속도 제한, localhost 기본 바인딩 | 실제 (아래 "접근 통제" 참고) |
| 스팸브레이커·메일브레이커·아카이빙 IP·Port, 연결 여부 판정 | 실제 (아래 "장비 연결 설정" 참고) — 하드코딩된 기본 IP 없음 |
| RBAC/로그인 | 없음 — PoC 범위이며 모든 조작이 `admin.kim`으로 고정 기록됨 |

## 장비 연결 설정 (IP · Port)

스팸브레이커·메일브레이커·아카이빙은 고객사마다 실제 장비 주소가 다르므로 **하드코딩된 기본
IP를 두지 않는다.** `node_endpoints`는 `host=""`, `port=null`로 시작하며, 관리자가 관제 현황
화면 상단 "장비 연결 설정" 카드에서 직접 입력해야 한다(웹메일은 이 서버 자신이라 설정 불필요).

- 저장하면 서버가 그 주소로 **실제 TCP 연결(`asyncio.open_connection`)을 시도**해 통신 가능
  여부를 판정하고(`GET/PUT /api/v1/settings/node-endpoints/{node}`), 이후 5초 주기로 계속
  재확인한다. 연결이 끊기거나 복구되면 경보 이력에도 CRITICAL/INFO로 기록된다.
- 물리 장비가 없는 이 개발 환경에서는 대부분 연결 실패로 나타나는 게 정상이다 — 판정 로직 자체는
  진짜이므로, 실제 장비의 IP·Port를 입력하면(또는 `curl -X PUT .../MailBreaker -d
  '{"host":"127.0.0.1","port":8100}'`처럼 도달 가능한 아무 TCP 포트로 테스트하면) 즉시
  "연결됨"으로 바뀌는 것을 확인할 수 있다.
- 연결이 끊긴 노드는 CPU/MEM/큐 값의 시뮬레이션 드리프트를 멈추고 마지막 값을 그대로 유지한다
  (실데이터가 없다는 사실을 정직하게 표현하기 위함).

## 접근 통제 (보안)

처음 버전은 `/api/v1/alerts`를 뷰와 무관하게 3초마다 무조건 호출하는 단순 폴링이었고, 조작
API(POST/PUT)에 인증이 전혀 없었습니다. 아래와 같이 개선했습니다.

- **폴링 제거 → 단일 SSE 스트림(`/api/v1/stream`)**: health·alerts·hourly 통계를 서버가 상태
  변화 시점에만 push합니다. 브라우저 탭이 백그라운드로 가면 연결을 끊어 불필요한 트래픽을
  없애고, 다시 보이면 재연결합니다. 연결이 끊기면 지수 백오프(1s→2s→4s→…최대 15s)로 재시도하며,
  상단바의 연결 상태 배지(초록/노랑/빨강)로 지금 실시간 연결이 되어 있는지 바로 알 수 있습니다 —
  기존에는 에러가 나도 콘솔에만 조용히 남아 트러블슈팅이 어려웠습니다.
- **조작 API 인증(X-Admin-Token)**: 격리 해제, SOS 실행, 저장 경로/임계치/Webhook 변경 등
  상태를 바꾸는 모든 POST/PUT은 `X-Admin-Token` 헤더를 요구합니다. 토큰은 서버 기동 시
  자동 생성되어 **콘솔에 출력**되고 `data/admin_token.txt`에도 저장됩니다. 대시보드 좌측 하단
  입력란에 붙여넣어야 조작이 가능하며, 토큰 없이/틀리게 호출하면 `401`이 반환됩니다.
  고정 토큰을 쓰려면 `INSIGHT_ADMIN_TOKEN` 환경변수로 직접 지정하세요.
- **속도 제한(rate limit)**: IP별로 전역 300회/60초, 조작 API는 20회/30초로 제한하고 초과 시
  `429`를 반환합니다. SSE 동시 연결도 IP당 5개로 제한해 커넥션 고갈을 막습니다.
- **기본 바인딩은 localhost 전용**: 아래 실행 명령의 `--host 127.0.0.1`이 기본값이며, 같은
  네트워크의 다른 PC에서 접근하려면 `--host 0.0.0.0`을 의도적으로 지정해야 합니다(그 경우에도
  토큰은 그대로 필요).

SOS 저장 경로는 실배포 시 `/var/lib/insight/sos-packages`처럼 리눅스 절대경로이지만, 이 데모는
Windows 개발 환경에서도 동작해야 하므로 `insight/backend/data/sandbox_root/` 하위에 동일한
경로 구조로 매핑해 실제 디렉토리 생성·용량 계산을 수행합니다(검증 규칙 자체는 리눅스 배포 기준
그대로).

## 빠른 시작

```bash
# 1) 백엔드
cd insight/backend
python -m venv .venv
./.venv/Scripts/pip install -r requirements.txt      # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # macOS/Linux
./.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8100 --reload

# 2) 프론트엔드 스타일(SCSS → CSS) — 최초 1회 및 scss/ 수정 시마다
cd ../frontend
npm install
npm run build:css        # scss/main.scss → style.css 컴파일 (백엔드가 /static/style.css로 서빙)
# npm run watch:css       # 개발 중 자동 재컴파일하려면
```

기동하면 콘솔에 관리자 토큰이 출력됩니다 — 이 토큰을 대시보드 좌측 하단 "관리자 토큰"
입력란에 붙여넣어야 격리 해제·SOS 실행·설정 변경이 가능합니다(조회 전용 화면은 토큰 없이도
바로 보입니다).

브라우저에서 **http://localhost:8100** 접속 — 6개 화면(관제 현황 / 메일 사전 추적 / SOS 로그
패키징 / 사전 경보 설정 / 시스템 아키텍처 / 구현 현황)이 실시간으로 갱신됩니다.

- 관제 현황·경보 피드: 단일 SSE 연결(`/api/v1/stream`)로 상태가 바뀔 때마다 push
- 메일 사전 추적: 8~16초 간격으로 새 메일 여정이 서버에서 생성되어 목록에 나타나고, 노드별
  통과 시각이 몇 초에 걸쳐 순차적으로 공개됩니다 (탭을 열어두면 진행 과정을 직접 관찰 가능)
- SOS 로그 패키징: 실제 `POST` → `EventSource`(SSE)로 4개 노드 진행률 수신 → 완료 시 실제
  `tar.gz` 다운로드

## 디렉토리 구조

```
insight/
├── backend/
│   ├── app/
│   │   ├── main.py        # FastAPI 라우트 (REST + SSE + 정적 파일 서빙)
│   │   ├── state.py       # 인메모리 상태 + 파일 영속화 + SSE pub/sub
│   │   ├── simulate.py    # Edge Agent 대체 시뮬레이션 + SOS 잡 상태 머신
│   │   ├── security.py    # 관리자 토큰 인증 + 속도 제한 + SSE 연결 제한
│   │   └── validators.py  # SOS 경로 검증 규칙 (보완명세 §3.4/§5.3)
│   ├── requirements.txt
│   └── data/               # 실행 중 생성되는 런타임 데이터 (git 추적 안 함)
└── frontend/
    ├── index.html          # 단일 HTML — 실 API를 호출하도록 재작성한 대시보드 (구조/로직만, 스타일 없음)
    ├── scss/               # 화면별 SCSS 파티션 (main.scss가 전부 @forward)
    ├── style.css           # scss/ 컴파일 산출물 — /static/style.css로 서빙 (git 추적 안 함)
    └── package.json        # sass devDependency + build:css/watch:css 스크립트
```

## 알려진 제한 (PoC 범위)

- 재시작하면 여정·SOS 잡·경보 이력은 초기화됩니다(설정/감사 로그/SOS 저장 파일만 `data/`에
  영속화됨). 실서비스는 SQLite/PostgreSQL로 전환 필요(보완명세 §2.2).
- RBAC·세션 로그인 없음 — 모든 조치가 `admin.kim`으로 고정 기록됩니다.
- 시간대별 처리량 차트는 서버 기동 후 지난 시간대는 시연용 베이스라인이며, 현재 시간대만 실제
  집계치가 반영됩니다.
