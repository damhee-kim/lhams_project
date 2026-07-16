<!--
  Crinity Insight — 관리자 대시보드.

  .jsp 확장자로 두어 향후 고객사 Tomcat/Java WAS(예: 웹메일 WAS와 동일 서버)에
  그대로 배포할 수 있게 한다. 이 페이지 자체는 서버측 스크립틀릿(<% %>)이나
  EL(${...})을 전혀 쓰지 않는 순수 마크업 + 외부 JS라서, 실행 환경이 무엇이든
  (지금의 FastAPI StaticFiles든, 나중의 Tomcat이든) 그대로 정적 서빙된다 —
  실제 데이터는 항상 /api/v1/* REST 호출로 받아온다(js/core.js의 api() 참고).

  실제 Tomcat/JSP 컨테이너에 배포할 때는 이 주석 위에 아래 한 줄을 추가해서
  JSP 기본 인코딩(ISO-8859-1)이 한글을 깨뜨리지 않도록 하라 — 지금은 FastAPI가
  그대로 정적 서빙하므로 이 지시어가 있으면 브라우저에 원문 그대로 노출되어 뺐다:
    <%@ page contentType="text/html;charset=UTF-8" pageEncoding="UTF-8" %>
-->
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Crinity Insight — 통합 메일 사전 관제 (Live)</title>
<link rel="stylesheet" href="/static/style.css">
</head>
<body>
<div class="app">

  <aside class="sidebar">
    <div class="logo">
      <div class="brand">Crinity <b>Insight</b></div>
      <div class="sub">Meta Control Tower v2.0 · LIVE</div>
    </div>
    <nav class="nav" id="nav">
      <button data-view="overview" class="active"><i class="dot"></i><span class="lb">관제 현황</span></button>
      <button data-view="journey"><i class="dot"></i><span class="lb">메일 사전 추적</span></button>
      <button data-view="sos"><i class="dot"></i><span class="lb">SOS 로그 패키징</span></button>
      <button data-view="alert"><i class="dot"></i><span class="lb">사전 경보 설정</span></button>
      <button data-view="arch"><i class="dot"></i><span class="lb">시스템 아키텍처</span></button>
      <button data-view="dev"><i class="dot"></i><span class="lb">구현 현황</span></button>
    </nav>
    <div class="side-foot">
      접속 계정 <span class="role">ENGINEER</span><br>
      admin.kim@crinity.com<br>
      <span style="font-family:var(--mono)">RBAC: 조치 권한 보유</span>
      <div style="margin-top:10px">
        <div class="token-label-row">
          <label style="font-size:10.5px;color:var(--dim)">관리자 토큰 (X-Admin-Token)</label>
          <button type="button" id="tokenHelpBtn" class="token-help-btn" title="토큰은 어디서 구하나요?">?</button>
        </div>
        <div class="token-input-row">
          <input id="adminTokenInput" type="password" placeholder="토큰 값 붙여넣기"
            style="flex:1;min-width:0;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:6px 8px;font-family:var(--mono);font-size:11px;color:var(--text)">
          <span id="tokenStatus" class="token-status" title="아직 확인되지 않음">•</span>
        </div>
        <div style="font-size:10px;color:var(--dim);margin-top:4px">격리 해제·SOS 실행·설정 변경 시 필요</div>
        <div id="tokenHelpBox" class="token-help-box">
          <ol>
            <li>서버 최초 기동 시 콘솔에 <b>관리자 토큰</b>이 출력됩니다.</li>
            <li>또는 파일에서 직접 확인:<code>insight/backend/data/admin_token.txt</code></li>
            <li>재시작해도 같은 값이 계속 재사용됩니다(바뀌지 않음).</li>
            <li>위 입력란에 붙여넣으면 자동으로 검증하고 결과를 알림으로 알려드립니다.</li>
          </ol>
        </div>
      </div>
    </div>
  </aside>

  <div class="main">
    <div class="topbar">
      <h1 id="viewTitle">관제 현황</h1>
      <span class="env">LIVE BACKEND · FastAPI</span>
      <span class="env" id="siteBadge" style="background:rgba(76,141,255,.10);color:var(--webmail);border-color:rgba(76,141,255,.3)">SITE: 확인 중…</span>
      <div class="top-right">
        <div class="live"><i class="pulse" id="connDot"></i><span id="connLabel">실시간 연결 시도 중…</span></div>
        <div class="clock" id="clock">--:--:--</div>
      </div>
    </div>
    <div class="content" id="content"></div>
  </div>
</div>
<div id="toast"></div>

<!-- 기능별로 분리된 JS — 로드 순서가 의존관계다: core(공통 상태·헬퍼) 먼저,
     화면별 view-*.js, 그리고 내비게이션·SSE·부트스트랩을 담당하는 app.js가 마지막. -->
<script src="/static/js/core.js"></script>
<script src="/static/js/view-overview.js"></script>
<script src="/static/js/view-journey.js"></script>
<script src="/static/js/view-sos.js"></script>
<script src="/static/js/view-alert.js"></script>
<script src="/static/js/view-arch.js"></script>
<script src="/static/js/view-dev.js"></script>
<script src="/static/js/app.js"></script>
</body>
</html>
