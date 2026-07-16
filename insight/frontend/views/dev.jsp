<!-- 구현 현황(SCR-06) 골격 — 순수 마크업, 스크립틀릿/EL 없음(index.jsp 참고).
     세 표 중 앞 두 개는 전부 정적이고, 감사 로그 표만 js/view-dev.js가 로드 직후(loadAudit) 채운다. -->
<div class="card">
  <h3>화면 ↔ 요구사항 ↔ API 매핑 (실제 엔드포인트)</h3>
  <table class="alert-table">
    <thead><tr><th>화면</th><th>충족 요구사항</th><th>핵심 API</th><th>비고</th></tr></thead>
    <tbody>
      <tr><td>관제 현황</td><td>FR-07, FR-10</td><td><span class="mono">GET /api/v1/health · /api/v1/stats/hourly · /stream</span></td><td>SSE 실시간 push, 실제 서버 상태</td></tr>
      <tr><td>장비 연결 설정</td><td>신규</td><td><span class="mono">GET/PUT /api/v1/settings/node-endpoints/{node}</span></td><td>실제 TCP 연결 시도로 통신 여부 판정</td></tr>
      <tr><td>메일 사전 추적</td><td>FR-01~04, FR-11</td><td><span class="mono">GET /api/v1/journeys · POST /api/v1/nodes/release</span></td><td>서버가 실제 상태 변경</td></tr>
      <tr><td>SOS 로그 패키징</td><td>FR-05, FR-06</td><td><span class="mono">POST /nodes/sos-package + SSE + /download</span></td><td>실제 tar.gz 생성·SHA-256</td></tr>
      <tr><td>사전 경보 설정</td><td>FR-08~10</td><td><span class="mono">GET/PUT thresholds · webhook · test-webhook</span></td><td>파일 영속화</td></tr>
    </tbody>
  </table>
  <div class="hint" style="margin-top:10px">이 표의 모든 엔드포인트는 실제로 응답합니다 — 브라우저 개발자 도구의 Network 탭에서 왕복을 직접 확인할 수 있습니다.</div>
</div>

<div class="card section-gap">
  <h3>여전히 시뮬레이션인 부분 — 실장비 연동 전환 지점</h3>
  <table class="alert-table">
    <thead><tr><th>항목</th><th>시뮬레이션 이유</th><th>실배포 시 대체 방법</th></tr></thead>
    <tbody>
      <tr><td>CPU·MEM·큐 수치 자체</td><td>Webmail/SpamBreaker/MailBreaker/Archiving 물리 서버 부재</td><td>각 서버에 Edge Agent(Python) 배치 → 실 heartbeat 수신</td></tr>
      <tr><td>(참고) 연결 여부 판정 자체는 실제</td><td>장비가 없어 대개 연결 실패로 나타나지만, 판정 로직은 시뮬레이션 아님</td><td>실제 장비의 IP·Port를 입력하면 그대로 연결 성공 확인 가능</td></tr>
      <tr><td>메일 여정 발생</td><td>실제 메일 트래픽 부재</td><td>Edge Agent가 실 로그 tail → Message-ID 이벤트 push</td></tr>
      <tr><td>SOS 로그 원본</td><td>/var/log/* 실 로그 부재 · 트리거 방식(push/pull)·인증 등 5가지 미확정</td><td>sos_agent_adapter.py의 collect_from_node() 구현 → run_sos_job() 교체(README "구현 전환 계획" 참고)</td></tr>
      <tr><td>RBAC/로그인</td><td>PoC 범위 밖(세션 없이 admin.kim 고정)</td><td>SSO/LDAP 연동 + 서버측 RBAC 미들웨어 추가</td></tr>
      <tr><td>격리 해제 실제 장비 반영</td><td>MailBreaker/SpamBreaker 연동 인터페이스 미확정</td><td>release_adapter.py의 release_on_device() 교체(코드 나머지는 무수정)</td></tr>
    </tbody>
  </table>
</div>

<div class="card section-gap">
  <h3>접근 통제 · 안정성 · 데이터 저장 (실제 적용됨)</h3>
  <table class="alert-table">
    <thead><tr><th>항목</th><th>적용 내용</th></tr></thead>
    <tbody>
      <tr><td>조작 API 인증</td><td>격리 해제·SOS 실행·설정 변경 등 모든 POST/PUT은 X-Admin-Token 헤더 필요 (서버 기동 시 발급·재사용, data/admin_token.txt). 좌측 사이드바 "?" 가이드 버튼 + GET /api/v1/auth/verify로 입력 즉시 유효성 검증·토스트 알림</td></tr>
      <tr><td>속도 제한</td><td>IP별 전역 300회/60초, 조작 API는 20회/30초 — 초과 시 429</td></tr>
      <tr><td>실시간 연결 제한</td><td>SSE 스트림은 IP당 동시 5개까지, 탭이 백그라운드면 자동 해제</td></tr>
      <tr><td>기본 바인딩</td><td>127.0.0.1(localhost)만 허용 — LAN 노출은 INSIGHT_HOST 명시적 설정 필요</td></tr>
      <tr><td>데이터 저장(신규)</td><td>고객사 DB를 새로 들이거나 포트를 열 필요 없는 SQLite 파일 1개(insight.db) — 여정·경보·감사로그·모든 설정 영속화</td></tr>
      <tr><td>개인정보 보관(신규)</td><td>메일 제목·주소는 기본 90일 후 자동 폐기, 제목 마스킹 토글 지원 (사전 경보 설정 화면)</td></tr>
      <tr><td>다중 고객사 식별(신규)</td><td>INSIGHT_SITE_NAME/SITE_ID 환경변수 → 상단 SITE 배지에 표시 (LHAMS 관례와 동일)</td></tr>
    </tbody>
  </table>
</div>

<div class="card section-gap">
  <h3>최근 감사 로그 (실 데이터, GET /api/v1/audit)</h3>
  <table class="alert-table">
    <thead><tr><th>시각</th><th>조작자</th><th>액션</th><th>대상</th><th>결과</th></tr></thead>
    <tbody id="auditRows"><tr><td colspan="5" class="empty">불러오는 중…</td></tr></tbody>
  </table>
</div>
