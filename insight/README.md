# Crinity Insight — 실행 가능한 데모 서비스

`docs/crinity_insight_admin.html`(정적 목업)과 `docs/Crinity_Insight_구현전환_보완명세.md`
(구현 전환 스펙)을 기반으로, 실제 HTTP/SSE 통신을 하는 로컬 데모 서비스로 구현한 모듈입니다.
LHAMS(파일 감사 관제) 프로젝트와는 완전히 독립된 별도 모듈입니다.

## 무엇이 실제이고 무엇이 시뮬레이션인가

Webmail / MailBreaker / SpamBreaker / Archiving (실제 메일 처리 순서) 4대 물리 서버가 이 개발 환경에는 없으므로
**Edge Agent가 보낼 이벤트만 백엔드 프로세스 내부에서 시뮬레이션**합니다. 그 외에는 전부 실제
동작입니다.

| 항목 | 상태 |
|---|---|
| 4개 노드 CPU·MEM·DISK·큐 수치, 신규 메일 발생 | 시뮬레이션 (실 장비 부재) |
| REST API (`/api/v1/...`), SSE 실시간 스트림(`/api/v1/stream`) | 실제 (FastAPI, 브라우저 Network 탭에서 확인 가능) |
| 메일 여정 검색·필터, 격리 해제 상태 변경 | 실제 (서버 메모리 상태를 실제로 변경) |
| SOS 패키지 — 대상 노드 선택 → 진행률 SSE → 완료 시 다운로드 | 실제 (`tar.gz` 생성, SHA-256 실계산, 로컬 디스크에 실제 저장) |
| SOS 저장 경로 검증(경로 주입·Path Traversal 차단, 쓰기 권한·여유공간 확인) | 실제 서버측 검증 + 실제 `mkdir`/`disk_usage` |
| 여정·경보·감사 로그·설정, 개인정보 보관기간 | 실제 (SQLite 1개 파일 — 아래 "데이터 저장" 참고, 재시작해도 유지) |
| 조작(POST/PUT) API 인증, 속도 제한, localhost 기본 바인딩 | 실제 (아래 "접근 통제" 참고) |
| 웹메일 포함 4개 노드 IP·Port, 연결 여부 판정, 사용 여부(enabled) | 실제 (아래 "장비 연결 설정" 참고) — 하드코딩된 기본 IP 없음 |
| 격리 해제·SOS 로그 수집의 실제 장비 연동 | 미확정 — `release_adapter.py`·`sos_agent_adapter.py`에 연동 지점만 준비(아래 "구현 전환 계획" 참고) |
| RBAC/로그인 | 없음 — PoC 범위이며 모든 조작이 `admin.kim`으로 고정 기록됨 |

## 데이터 저장 (SQLite) — 리스크 체크리스트 "DB 선정" 대응

고객사 현장은 이미 사용 중인 DB가 정해져 있어 별도 DB 엔진을 들여오기 어렵고, 방화벽 정책상
새 포트(예: PostgreSQL 5432)를 여는 것도 쉽지 않습니다. 그래서 **표준 라이브러리(`sqlite3`)만
사용하는 파일 기반 SQLite**를 택했습니다 — 별도 설치·서비스 계정·포트가 전혀 필요 없고,
`insight/backend/data/insight.db` **파일 하나**가 전부입니다.

- 여정(메일 사전 이력) · 경보 이력 · 감사 로그 · 모든 설정(임계치/Webhook/SOS 저장경로/장비
  IP·Port/개인정보 정책)이 이 파일에 저장되며, **재시작해도 사라지지 않습니다** (이전 버전은
  전부 인메모리라 재시작하면 초기화됐습니다).
- 인메모리 캐시(`state.journeys` 등)는 그대로 두어 기존 조회·필터 로직을 건드리지 않았습니다 —
  변경이 생기면 "인메모리 갱신 + SQLite write-through"를 함께 수행하는 구조입니다(`app/db.py`).
- 백업/이관은 `insight.db` 파일 하나만 복사하면 됩니다. 경로는 `INSIGHT_DB_PATH` 환경변수로
  고객사 정책에 맞는 위치(예: 이미 승인된 애플리케이션 데이터 디렉토리)로 바꿀 수 있습니다.
- 동시성: 요청마다 짧은 연결을 열고 닫으며(connect-per-call) WAL 모드로 잠금 경합을 최소화합니다
  — 이 서비스 규모(관리자 대시보드 1대)에서는 커넥션 풀보다 단순함이 더 안전합니다.

## 개인정보 처리 (리스크 체크리스트 "개인정보 처리 검토" 대응)

메일 제목·발신/수신 주소는 개인정보이므로 무기한 보관하지 않습니다.

- **보관기간**: 기본 90일, "사전 경보 설정" 화면에서 1~3650일 사이로 고객사 컴플라이언스에 맞춰
  조정합니다. 매시간 보관기간 초과 여정을 SQLite와 인메모리에서 함께 폐기합니다
  (`GET/PUT /api/v1/settings/privacy`).
- **제목 마스킹**: 기본은 끄져 있으며(고객사별 정책 결정 사항이라 임의로 켜지 않습니다), 켜면
  여정 목록·타임라인의 메일 제목이 `앞2글자***뒤2글자` 형태로 표시됩니다.
- RBAC가 아직 없어 화면 단위가 아니라 **사이트 전체 정책**으로 적용됩니다 — 화면별(VIEWER만
  마스킹) 차등 적용은 RBAC 도입 후 확장 지점입니다.

## 다중 고객사 배포 (리스크 체크리스트 "다중 고객사 배포 전략" 부분 대응)

LHAMS의 `LHAMS_SITE_NAME`/`LHAMS_SITE_ID` 관례와 동일하게, 인스턴스 식별용 환경변수를
지원합니다.

```bash
export INSIGHT_SITE_NAME="본사 메일서버"
export INSIGHT_SITE_ID="hq-01"
```

대시보드 상단 배지에 항상 표시되어 여러 고객사/서버를 나눠 구축·운영할 때 "지금 어느 사이트
화면을 보고 있는지" 혼동을 줄여줍니다(`GET /api/v1/site`). 라이선싱·설치 자동화·버전 호환
매트릭스 등 배포 프로세스 자체는 별도 결정이 필요한 사업적 의사결정 영역이라 이 항목은
사이트 식별까지만 다룹니다.

## 구현 전환 계획 — 격리 해제 · SOS 실행 (아직 MOCK인 두 조치 기능)

이 둘은 "화면·API는 다 만들어져 있지만, 실제 물리 장비와 통신하는 마지막 한 걸음이
남아 있다"는 점에서 같은 처지입니다. 아래는 각각 **지금 상태 / 무엇이 막고 있는지 /
확정되면 어디를 고치면 되는지**를 명확히 하기 위한 정리입니다.

### 1. 격리 해제 (`POST /api/v1/nodes/release`)

| 항목 | 내용 |
|---|---|
| 지금 상태 | `app/release_adapter.py`의 `release_on_device()`가 **항상 성공(MOCK)** 반환 — 로컬 DB 상태만 `PASS`로 바뀌고, 실제 MailBreaker/SpamBreaker 장비에는 아무 것도 요청하지 않음 |
| 막고 있는 것 | MailBreaker/SpamBreaker가 격리 해제를 어떤 인터페이스로 지원하는지 **벤더 확인 전** — REST API인지, CLI(SSH)인지, 격리 DB 레코드 직접 갱신인지조차 아직 모름 |
| 확정되면 할 일 | `release_adapter.py`의 `release_on_device()` 함수 본문만 교체. `main.py`의 `release_node()`, 프론트엔드, 감사 로그 포맷은 전부 무수정 — 이미 "성공/실패 + 사유 메시지"를 받아 그대로 처리하는 구조이기 때문 |
| 확인 방법 | 감사 로그(`GET /api/v1/audit`)에서 `RESULT` 값이 `SUCCESS: MOCK: ...`으로 남아 있으면 아직 실장비에 반영 안 된 것 |

### 2. SOS 로그 수집 (`POST /api/v1/nodes/sos-package`)

| 항목 | 내용 |
|---|---|
| 지금 상태 | `simulate.run_sos_job()`이 노드별 진행 단계(수집 명령 수신→로그 수집→덤프→전송)를 **무작위 타이밍으로 시뮬레이션**하고, `_fake_node_files()`가 실제 로그가 아닌 표본 텍스트로 tar.gz를 만듦. 물리 서버 자체가 없으니 당연한 결과 |
| 막고 있는 것 | 격리 해제보다 결정할 게 더 많음 — `app/sos_agent_adapter.py` 상단 주석에 5가지를 정리해 뒀음: (1) 중앙→Agent 트리거가 push/pull 중 무엇인지, (2) Agent 인증(API Key)을 어디서 읽을지, (3) 진행 상태 보고 포맷, (4) 실패·타임아웃 처리, (5) 노드별 실제 로그 포맷(patterns.yaml류 필요 여부) |
| 확정되면 할 일 | `sos_agent_adapter.py`의 `collect_from_node()`를 실제 Agent 호출로 구현 → `simulate.run_sos_job()`의 무작위 루프를 이 함수 호출 결과로 교체 → `build_manifest()`가 실제 수집 바이트를 담도록 교체. `main.py`의 SSE 스트리밍·다운로드 엔드포인트는 job 상태만 읽어 보내므로 무수정 |
| 확인 방법 | SOS 패키지를 열어보면 각 노드 폴더 안 로그가 표본 문구(랜덤 타임스탬프)인지, 실제 서버 로그인지로 구분 가능 |

두 기능 모두 **코드 구조(연동 지점 seam)는 이미 준비돼 있고, 남은 건 벤더/실장비 확인
이후의 함수 본문 교체뿐**이라는 게 핵심입니다 — 지금 코드를 더 손대지 않아도 나중에
국소적으로만 바꾸면 됩니다.

## 장비 연결 설정 (IP · Port · 사용 여부)

웹메일·메일브레이커·스팸브레이커·아카이빙(실제 메일 처리 순서) **4개 노드 전부** 고객사마다 실제 장비 주소가
다르므로 **하드코딩된 기본 IP를 두지 않는다.** `node_endpoints`는 `host=""`, `port=null`로
시작하며, 관리자가 관제 현황 화면 상단 "장비 연결 설정" 카드에서 직접 입력해야 한다.

- 저장하면 서버가 그 주소로 **실제 TCP 연결(`asyncio.open_connection`)을 시도**해 통신 가능
  여부를 판정하고(`GET/PUT /api/v1/settings/node-endpoints/{node}`), 이후 5초 주기로 계속
  재확인한다. 연결이 끊기거나 복구되면 경보 이력에도 CRITICAL/INFO로 기록된다.
- 물리 장비가 없는 이 개발 환경에서는 대부분 연결 실패로 나타나는 게 정상이다 — 판정 로직 자체는
  진짜이므로, 실제 장비의 IP·Port를 입력하면(또는 `curl -X PUT .../Webmail -d
  '{"host":"127.0.0.1","port":8100,"enabled":true}'`처럼 도달 가능한 아무 TCP 포트로 테스트하면)
  즉시 "연결됨"으로 바뀌는 것을 확인할 수 있다.
- 연결이 끊긴 노드는 CPU/MEM/큐 값의 시뮬레이션 드리프트를 멈추고 마지막 값을 그대로 유지한다
  (실데이터가 없다는 사실을 정직하게 표현하기 위함).
- **사용 여부(`enabled`)**: 고객사에 따라 4개 솔루션 중 일부만 도입했을 수 있다. 각 노드 행의
  체크박스로 "사용 안 함"으로 표시하면 관제 현황 카드, SOS 대상 노드 목록, 경보 임계치 평가,
  주기적 연결 확인에서 전부 제외된다. 새로 생성되는 메일 여정도 그 시점에 사용 중인 노드만
  거치는 파이프라인으로 만들어진다(예: 아카이빙을 끄면 신규 여정은 메일브레이커까지만 진행).
  이미 만들어진 과거 여정은 그대로 유지된다.

## 접근 통제 (보안)

처음 버전은 `/api/v1/alerts`를 뷰와 무관하게 3초마다 무조건 호출하는 단순 폴링이었고, 조작
API(POST/PUT)에 인증이 전혀 없었습니다. 아래와 같이 개선했습니다.

- **폴링 제거 → 단일 SSE 스트림(`/api/v1/stream`)**: health·alerts·hourly 통계를 서버가 상태
  변화 시점에만 push합니다. 브라우저 탭이 백그라운드로 가면 연결을 끊어 불필요한 트래픽을
  없애고, 다시 보이면 재연결합니다. 연결이 끊기면 지수 백오프(1s→2s→4s→…최대 15s)로 재시도하며,
  상단바의 연결 상태 배지(초록/노랑/빨강)로 지금 실시간 연결이 되어 있는지 바로 알 수 있습니다 —
  기존에는 에러가 나도 콘솔에만 조용히 남아 트러블슈팅이 어려웠습니다.
- **조작 API 인증(X-Admin-Token)**: 격리 해제, SOS 실행, 저장 경로/임계치/Webhook 변경 등
  상태를 바꾸는 모든 POST/PUT은 `X-Admin-Token` 헤더를 요구합니다. 이 값은 로그인 계정이나
  고정 비밀번호가 아니라 **서버가 발급하는 값**이며, 확인 방법은 둘 중 하나입니다:
  1. 서버를 기동한 콘솔/터미널 출력 맨 위에서 `관리자 토큰: ...` 줄을 확인
  2. 서버가 이미 떠 있는 상태라면 `insight/backend/data/admin_token.txt` 파일을 직접 열어 확인

  이 값을 대시보드 좌측 하단 "관리자 토큰" 입력란에 붙여넣어야 조작이 가능하며, 토큰 없이/
  틀리게 호출하면 `401`이 반환됩니다. **한 번 생성된 토큰은 서버를 재시작해도 그대로 유지**
  됩니다(`admin_token.txt`가 있으면 재사용, 없을 때만 새로 생성) — 개발 중 서버를 자주
  재시작해도 대시보드에 붙여넣은 토큰이 매번 무효화되지 않습니다. 완전히 새 토큰을 강제로
  받고 싶으면 `admin_token.txt`를 지우고 재시작하거나, `INSIGHT_ADMIN_TOKEN` 환경변수로
  원하는 값을 직접 고정하세요.
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
│   │   ├── main.py             # FastAPI 라우트 (REST + SSE + 정적 파일 서빙)
│   │   ├── state.py            # 인메모리 작업 캐시 + SQLite 로드/조회 진입점 + SSE pub/sub
│   │   ├── db.py                # SQLite 영속화 계층 (journeys/alerts/audit_log/settings)
│   │   ├── simulate.py         # Edge Agent 대체 시뮬레이션 + SOS 잡 상태 머신
│   │   ├── security.py         # 관리자 토큰 인증 + 속도 제한 + SSE 연결 제한
│   │   ├── release_adapter.py  # 격리 해제 실제 장비 연동 지점(seam) — 아직 MOCK
│   │   ├── sos_agent_adapter.py # SOS 실제 로그 수집 연동 지점(seam) — 아직 미구현/미호출
│   │   └── validators.py       # SOS 경로 검증 규칙 (보완명세 §3.4/§5.3)
│   ├── requirements.txt
│   └── data/               # SQLite(insight.db)·SOS 샌드박스 등 런타임 데이터 (git 추적 안 함)
└── frontend/
    ├── index.jsp           # 마크업만 — 스타일·스크립트는 전부 외부 파일 참조 (아래 "프론트엔드 구조" 참고)
    ├── js/                 # 화면별 JS 파티션 (core.js가 공통 상태, app.js가 진입점)
    ├── scss/               # 화면별 SCSS 파티션 (main.scss가 전부 @forward)
    ├── style.css           # scss/ 컴파일 산출물 — /static/style.css로 서빙 (git 추적 안 함)
    └── package.json        # sass devDependency + build:css/watch:css 스크립트
```

## 프론트엔드 구조 — HTML/CSS/JS 분리

관리하기 쉽도록 마크업·스타일·로직을 완전히 분리했습니다. `index.jsp`에는 이제 순수 HTML
마크업만 남아 있고, 스타일(`scss/` → `style.css`)과 로직(`js/*.js`)은 전부 외부 파일입니다.

- **왜 `.jsp`인가**: 실제 배포 대상(고객사 웹메일 WAS)이 Java/Tomcat 기반일 수 있어, 나중에
  그 서버에 그대로 올릴 수 있도록 확장자를 맞췄습니다. 지금 이 페이지는 서버측 스크립틀릿
  (`<% %>`)이나 EL을 전혀 쓰지 않는 순수 마크업이라 **FastAPI가 정적 파일로 그대로 서빙해도,
  나중에 Tomcat이 서빙해도 동일하게 동작**합니다. 실제 데이터는 항상 `/api/v1/*` REST 호출로
  받아오므로(SSE 포함), 백엔드가 FastAPI인지 Java servlet인지는 프론트 코드 입장에서 무관합니다.
- **`js/` 로드 순서가 곧 의존관계**입니다 (`index.jsp`의 `<script src>` 순서와 동일):
  1. `core.js` — 공통 상태(NODES, health, alerts, thresholds …), `api()` 네트워크 헬퍼, `$`/`el`/`toast` DOM 헬퍼, 뷰 레지스트리(`views`)
  2. `view-overview.js` / `view-journey.js` / `view-sos.js` / `view-alert.js` / `view-arch.js` / `view-dev.js` — 화면 1개당 파일 1개, 그 화면의 `views.xxx` 렌더 함수와 이벤트 핸들러를 전부 담음
  3. `app.js` — 내비게이션 바인딩, SSE 스트림 연결·재연결, `boot()` 진입점 (반드시 마지막에 로드)
  - 모듈(`import`/`export`)이 아니라 **일반 `<script src>` 다중 로드**를 택했습니다 — 기존
    단일 파일 스크립트와 완전히 동일한 전역 스코프·재할당 방식을 유지해 리팩터링 위험 없이
    파일만 나눌 수 있었습니다. 화면을 추가할 때는 `js/view-신규.js`를 만들고 `index.jsp`에
    `<script src="/static/js/view-신규.js">` 한 줄만 추가하면 됩니다.

## 폐쇄망(에어갭) 배포 가이드

이 서비스는 런타임에 외부 인터넷 호출이 전혀 없습니다(CDN·외부 API 없음, SQLite도 파일
기반이라 별도 서버 접속이 없습니다). LHAMS 본 프로젝트와 동일하게 **빌드는 인터넷이 되는
환경에서, 배포는 폐쇄망에서** 하는 방식을 권장합니다.

```bash
# ── 인터넷이 되는 빌드 서버에서 ────────────────────────────────
cd insight/backend
pip download -r requirements.txt -d vendor        # 오프라인 설치용 wheel 모음

cd ../frontend
npm install && npm run build:css                   # style.css 생성 — 이후 이 산출물만 반입

# ── 폐쇄망 반입 대상 (USB/사내 자료전송시스템 등) ─────────────
insight/
├── backend/
│   ├── app/, requirements.txt, vendor/            # vendor/는 오프라인 wheel
└── frontend/
    ├── index.jsp, js/, style.css                  # scss/·node_modules/ 불필요 (빌드 산출물만)

# ── 폐쇄망 서버에서 ────────────────────────────────────────────
cd insight/backend
python -m venv .venv
./.venv/Scripts/pip install --no-index --find-links=vendor -r requirements.txt
./.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8100
```

체크할 점:

- SQLite는 `sqlite3` 표준 라이브러리만 사용하므로 추가 wheel이 필요 없습니다.
- `INSIGHT_ADMIN_TOKEN`을 환경변수로 고정하면 기동할 때마다 새 토큰이 콘솔에 출력되는 것을
  피하고, 구축팀이 사전에 배포 문서에 토큰을 기록해 둘 수 있습니다.
- 이 서비스가 필요한 포트는 대시보드 자체 포트(기본 8100) **하나뿐**입니다 — SQLite는 별도
  포트가 없고, 4개 노드의 IP·Port 설정은 그 장비들과의 통신 대상이지 이 서비스가 여는 포트가
  아닙니다.

## 알려진 제한 (PoC 범위)

- RBAC·세션 로그인 없음 — 모든 조치가 `admin.kim`으로 고정 기록됩니다.
- 격리 해제의 실제 장비 연동, patterns.yaml 같은 Edge Agent 패턴 버전관리 체계, 대량 트래픽
  부하 검증은 아직 결정/실행되지 않았습니다 — 자세한 내용은 각 섹션 및 원본 스펙의
  "리스크 및 오픈 이슈" 체크리스트를 참고하세요.
- 시간대별 처리량 차트는 서버 기동 후 지난 시간대는 시연용 베이스라인이며, 현재 시간대만 실제
  집계치가 반영됩니다.
