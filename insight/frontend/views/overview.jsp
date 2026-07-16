<!-- 관제 현황(SCR-01) 골격 — 순수 마크업, 스크립틀릿/EL 없음(index.jsp 참고).
     동적 값·이벤트 바인딩은 js/view-overview.js가 로드 직후 채운다. -->
<div class="card node-endpoints-card">
  <h3>장비 연결 설정 (IP · Port) — 실제 TCP 연결로 통신 여부 판정</h3>
  <div id="nodeEndpointRows" class="ep-rows"></div>
  <div class="hint section-gap">웹메일·스팸브레이커·메일브레이커·아카이빙 4개 노드 모두 고객사마다 실제 장비의 IP·Port가 다르므로 직접 입력합니다. 저장하면 서버가 그 주소로 <b>실제 TCP 연결을 시도</b>해 통신 가능 여부를 판정하고, 이후 5초 주기로 계속 재확인합니다(연결이 끊기거나 복구되면 경보에도 기록됩니다). 고객사가 도입하지 않은 솔루션은 좌측 체크박스로 "사용 안 함" 처리하면 관제 현황·SOS·경보 평가 대상에서 제외됩니다.</div>
</div>
<div class="grid4" id="healthCards"></div>
<div class="grid2 section-gap">
  <div class="card">
    <h3>24시간 메일 처리량 · 차단 현황 (FR-07)</h3>
    <div class="chart" id="thruChart"></div>
    <div class="chart-x" id="thruX"></div>
    <div class="legend">
      <span><i style="background:var(--webmail)"></i>정상 처리</span>
      <span><i style="background:var(--crit)"></i>격리/차단</span>
    </div>
  </div>
  <div class="card">
    <h3>실시간 경보 피드 (FR-08 · Slack/Teams 연동)</h3>
    <div class="feed" id="alertFeed"></div>
  </div>
</div>
