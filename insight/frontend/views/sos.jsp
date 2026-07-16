<!-- SOS 로그 패키징(SCR-03) 골격 — 순수 마크업, 스크립틀릿/EL 없음(index.jsp 참고).
     시작/종료 시각·저장 설정 값은 js/view-sos.js가 로드 직후(defaultStart/End, loadSosSettings) 채운다. -->
<div class="card">
  <h3>원클릭 SOS 로그 패키징 (FR-05 · POST /api/v1/nodes/sos-package)</h3>
  <div class="sos-form">
    <div class="field"><label>수집 시작 시각 (start_time)</label><input type="datetime-local" id="sosStart"></div>
    <div class="field"><label>수집 종료 시각 (end_time)</label><input type="datetime-local" id="sosEnd"></div>
  </div>
  <div class="field" style="margin-top:14px"><label>수집 대상 노드</label>
    <div class="node-picks" id="sosPicks"></div>
  </div>
  <div style="display:flex;gap:12px;align-items:center;margin-top:18px">
    <button class="btn" id="sosRun">SOS 수집 시작</button>
    <span class="timer" id="sosTimer"></span>
    <span class="hint">각 Agent가 해당 시간대 로그(/var/log/*), 프로세스 덤프(top), 디스크 상태(df)를 병렬 수집·압축합니다. 목표: 총 40분 → <b style="color:var(--pass)">1분 이내</b></span>
  </div>
  <div class="sos-steps" id="sosSteps"></div>
  <div class="sos-result" id="sosResult">
    <span class="chip pass" id="sosResultChip">병합 완료</span>
    <div style="flex:1"><div class="fn" id="sosFn"></div><div class="fs" id="sosFs"></div></div>
    <button class="btn" id="sosDl">패키지 다운로드</button>
  </div>
</div>

<div class="card section-gap">
  <h3>패키지 저장 설정 (M2-F9 · GET/PUT /api/v1/settings/sos-storage) — ADMIN 권한</h3>
  <div class="field"><label>운영서버 저장 경로 (병합 패키지 보관 위치)</label>
    <div class="webhook-row">
      <input id="sosDir" spellcheck="false" placeholder="/var/lib/insight/sos-packages">
      <button class="btn ghost" id="sosDirCheck">경로 검증</button>
      <button class="btn" id="sosDirSave">설정 저장</button>
    </div>
    <div class="hint" id="sosDirMsg" style="margin-top:8px">허용: 절대 경로, 영문·숫자·<span class="mono">/ _ . -</span> · 금지: <span class="mono">..</span>, 시스템 디렉토리(/etc, /usr, /root …). 서버가 쓰기 권한·여유 공간을 실제로 검증합니다.</div>
  </div>
  <div class="sos-form" style="margin-top:16px">
    <div class="field"><label>보관 기간 — 이후 패키지 자동 폐기 <b class="mono" id="sosRetV" style="color:var(--text)"></b></label>
      <input type="range" min="7" max="180" id="sosRet" style="width:100%;accent-color:var(--webmail)"></div>
    <div class="field"><label>저장 디스크 사용 상한 — 초과 시 신규 수집 거부 <b class="mono" id="sosCapV" style="color:var(--text)"></b></label>
      <input type="range" min="10" max="500" step="10" id="sosCap" style="width:100%;accent-color:var(--webmail)"></div>
  </div>
  <div class="hint" id="sosUsageHint">현재 저장 사용량 확인 중…</div>
</div>
