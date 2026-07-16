<!-- 사전 경보 설정(SCR-04) 골격 — 순수 마크업, 스크립틀릿/EL 없음(index.jsp 참고).
     임계치·Webhook·개인정보 값은 js/view-alert.js가 로드 직후 채운다. -->
<div class="card">
  <h3>임계치 설정 (FR-08 / FR-09) — Agent 10초 주기 평가</h3>
  <div class="th-grid">
    <div class="th-item"><label>디스크 사용률 초과 시 경보 <b id="thDiskV"></b></label>
      <input type="range" min="50" max="99" id="thDisk"></div>
    <div class="th-item"><label>메일 큐 대기 건수 초과 시 경보 <b id="thQueueV"></b></label>
      <input type="range" min="100" max="5000" step="100" id="thQueue"></div>
    <div class="th-item"><label>CPU 사용률 초과 시 경보 <b id="thCpuV"></b></label>
      <input type="range" min="50" max="99" id="thCpu"></div>
  </div>
  <div class="field" style="margin-top:20px"><label>알림 채널 (Slack / Teams Incoming Webhook)</label>
    <div class="webhook-row">
      <input id="webhookUrl" placeholder="https://hooks.slack.com/services/... (고객사별 Webhook URL 입력)" spellcheck="false">
      <button class="btn ghost" id="testHook">테스트 발송</button>
      <button class="btn" id="saveTh">설정 저장</button>
    </div>
    <div class="hint" style="margin-top:8px">중앙서버 경보 엔진이 임계치 도달 시 Webhook으로 경고 메시지를 발송합니다. 장비 다운 자체를 감지하는 Proactive 체계입니다.</div>
  </div>
</div>
<div class="card section-gap">
  <h3>개인정보 처리 설정 — 메일 여정 보관·마스킹 정책</h3>
  <div class="th-grid">
    <div class="th-item"><label>여정 보관 기간(일) — 초과 시 자동 폐기 <b id="privRetV"></b></label>
      <input type="range" min="1" max="365" id="privRet"></div>
    <div class="field" style="display:flex;align-items:center;gap:8px;margin-top:22px">
      <input type="checkbox" id="privMask" style="width:16px;height:16px">
      <label for="privMask" style="margin:0">메일 제목 마스킹 (목록·타임라인에 일부만 표시)</label>
    </div>
  </div>
  <div class="hint" style="margin-top:10px">메일 제목·발신/수신 주소는 개인정보이므로 무기한 보관하지 않습니다(기본 90일). 고객사 컴플라이언스 정책에 맞춰 조정하세요.</div>
  <button class="btn" id="savePriv" style="margin-top:12px">개인정보 설정 저장</button>
</div>
<div class="card section-gap">
  <h3>경보 발생 이력 (FR-10)</h3>
  <table class="alert-table">
    <thead><tr><th>발생 시각</th><th>노드</th><th>심각도</th><th>내용</th><th>발송 채널</th></tr></thead>
    <tbody id="alertRows"></tbody>
  </table>
</div>
