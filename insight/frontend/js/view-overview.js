/* ===== 관제 현황 (SCR-01) — 장비 연결 설정 · 헬스 카드 · 처리량 차트 · 경보 피드 =====
 * 골격 마크업은 views/overview.jsp에 있다 — renderView()가 로드·주입한다. */
views.overview = async () => {
  if(!await renderView('overview')) return;
  renderNodeEndpointRows(); renderHealth(); renderFeed();
  fetchHourlyStats();
};

function connChip(nid){
  const c = nodeConnected[nid];
  if(!CONFIGURABLE_NODES.includes(nid)) return '';
  return c===true ? '<span class="chip pass">연결됨</span>'
       : c===false ? '<span class="chip crit">연결 끊김</span>'
       : '<span class="chip pending">확인 중</span>';
}

/* 저장하지 않은 채 다른 화면으로 이동했다가 관제 현황으로 돌아오면 views.overview()가
 * 이 뷰 전체를 새로 만든다 — 그러면 서버에 아직 저장 안 한 입력값은 원래 사라진다.
 * 이를 막기 위해 각 입력칸의 현재 값을 nodeEndpointDraft에 실시간으로 잡아두고,
 * 행을 다시 그릴 때 서버 확정값보다 초안(draft)을 우선한다. 저장에 성공하면
 * 그 노드의 초안은 지운다(서버 값이 곧 최신 값이 되었으므로). */
let nodeEndpointDraft = {};

/**
 * SSE 틱(3초/5초 주기 갱신)에서는 이 함수를 부르지 않는다 — host/port 입력칸을
 * 통째로 다시 그리면 사용자가 입력 중이던(아직 저장 안 한) 값이 사라진다.
 * 최초 진입·저장 성공 직후·화면 재진입 시에만 호출해 폼을 채운다.
 */
function buildNodeEndpointRow(nid){
  const n = nodeById(nid);
  const ep = nodeEndpoints[nid] || {host:'', port:''};
  const draft = nodeEndpointDraft[nid];
  const hostVal = draft ? draft.host : (ep.host || '');
  const portVal = draft ? draft.port : ((ep.port===null || ep.port===undefined) ? '' : ep.port);
  const enabled = draft ? draft.enabled : (nodeEnabled[nid] !== false);
  const row = el('div','ep-row'+(enabled?'':' ep-row-disabled'));
  row.dataset.node = nid;
  row.innerHTML = `
    <label class="ep-name" style="cursor:pointer"><input type="checkbox" data-f="enabled" ${enabled?'checked':''} style="margin-right:8px;vertical-align:-2px">
      <i class="ep-dot" style="background:${n.hex}"></i>${n.name}</label>
    <input class="ep-input" data-f="host" value="${hostVal}" placeholder="IP 또는 호스트명을 입력하세요 (예: 10.10.1.12)" spellcheck="false" ${enabled?'':'disabled'}>
    <input class="ep-input" data-f="port" type="number" min="1" max="65535" value="${portVal}" placeholder="Port" ${enabled?'':'disabled'}>
    <span data-badge>${!enabled ? '<span class="chip pending">사용 안 함</span>' : (ep.host ? connChip(nid) : '<span class="chip pending">미설정</span>')}</span>
    <button class="btn ghost" data-save>저장 · 연결 확인</button>`;
  const hostBox = row.querySelector('[data-f="host"]');
  const portBox = row.querySelector('[data-f="port"]');
  const enabledBox = row.querySelector('[data-f="enabled"]');
  const captureDraft = ()=>{
    nodeEndpointDraft[nid] = {host: hostBox.value, port: portBox.value, enabled: enabledBox.checked};
  };
  hostBox.oninput = captureDraft;
  portBox.oninput = captureDraft;
  enabledBox.onchange = ()=>{
    const on = enabledBox.checked;
    hostBox.disabled = !on;
    portBox.disabled = !on;
    row.classList.toggle('ep-row-disabled', !on);
    captureDraft();
  };
  row.querySelector('[data-save]').onclick = ()=> saveNodeEndpoint(nid, row);
  return row;
}

function renderNodeEndpointRows(){
  const wrap = $('#nodeEndpointRows'); if(!wrap) return;
  wrap.replaceChildren(...CONFIGURABLE_NODES.map(buildNodeEndpointRow));
}

/**
 * 저장 성공 후 딱 그 노드의 행 하나만 서버 확정값으로 다시 그린다 — 전체를
 * renderNodeEndpointRows()로 다시 그리면 다른 행에서 아직 저장 안 하고
 * 입력 중이던 host/port 값까지 함께 날아간다(여러 행을 순서대로 입력·저장하는
 * 흐름에서 실제로 발생했던 버그).
 */
function refreshNodeEndpointRow(nid){
  const wrap = $('#nodeEndpointRows'); if(!wrap) return;
  const old = wrap.querySelector(`[data-node="${nid}"]`);
  const fresh = buildNodeEndpointRow(nid);
  if(old) old.replaceWith(fresh); else wrap.appendChild(fresh);
}

/**
 * 실시간 스트림(tick)에서 연결 상태만 가볍게 갱신한다 — host/port 입력칸,
 * 사용여부 체크박스는 절대 건드리지 않아 입력 중이던 값이 지워지지 않는다.
 */
function updateNodeEndpointBadges(){
  const wrap = $('#nodeEndpointRows'); if(!wrap) return;
  for(const nid of CONFIGURABLE_NODES){
    const row = wrap.querySelector(`[data-node="${nid}"]`); if(!row) continue;
    const badge = row.querySelector('[data-badge]'); if(!badge) continue;
    const enabledBox = row.querySelector('[data-f="enabled"]');
    const enabled = enabledBox ? enabledBox.checked : (nodeEnabled[nid] !== false);
    const hostNow = row.querySelector('[data-f="host"]')?.value.trim();
    badge.innerHTML = !enabled ? '<span class="chip pending">사용 안 함</span>'
      : (hostNow ? connChip(nid) : '<span class="chip pending">미설정</span>');
  }
}

async function saveNodeEndpoint(nid, row){
  const btn = row.querySelector('[data-save]');
  const host = row.querySelector('[data-f="host"]').value.trim();
  const port = +row.querySelector('[data-f="port"]').value || null;
  const enabled = row.querySelector('[data-f="enabled"]').checked;
  btn.disabled = true; btn.textContent = '확인 중…';
  try{
    const r = await api(`/api/v1/settings/node-endpoints/${nid}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({host, port, enabled})});
    nodeEndpoints[nid] = {host:r.host, port:r.port};
    nodeConnected[nid] = r.connected;
    nodeEnabled[nid] = r.enabled;
    delete nodeEndpointDraft[nid]; // 서버가 확정한 값이 곧 최신값이므로 초안은 더 이상 필요 없음
    applyNodeEndpointsToNodes();
    refreshNodeEndpointRow(nid); renderHealth();
    const statusMsg = !r.enabled ? '사용 안 함으로 설정됨' : (r.connected?'연결됨':'연결 안 됨(응답 없음)');
    toast(`${n_name(nid)} 저장 완료 → ${r.host||'(미설정)'}${r.port?':'+r.port:''} · ${statusMsg}`, !r.enabled?'warn':(r.connected?'ok':'warn'));
  }catch(e){ toast('저장 실패: '+e.message, 'err'); }
  finally{ btn.disabled=false; btn.textContent='저장 · 연결 확인'; }
}
function n_name(nid){ return nodeById(nid)?.name || nid; }

function applyNodeEndpointsToNodes(){
  for(const nid of CONFIGURABLE_NODES){
    const n = nodeById(nid), ep = nodeEndpoints[nid];
    if(n) n.host = (ep && ep.host) ? `${ep.host}:${ep.port}` : '미설정';
  }
}

function renderHealth(){
  const wrap = $('#healthCards'); if(!wrap) return;
  const shown = NODES.filter(n => nodeEnabled[n.id] !== false);
  if(!shown.length){ wrap.replaceChildren(el('div','empty','사용 중인 노드가 없습니다 — 위 "장비 연결 설정"에서 최소 1개를 켜세요.')); return; }
  wrap.replaceChildren(...shown.map(n=>{
    const h = health[n.id];
    const disconnected = CONFIGURABLE_NODES.includes(n.id) && nodeConnected[n.id]===false;
    const unknown = CONFIGURABLE_NODES.includes(n.id) && nodeConnected[n.id]===null;
    const cls = p => p>=90?'hot':p>=80?'warm':'';
    const qcls = h.queue>=1000?'hot':h.queue>=500?'warm':'';
    const card = el('div','card node-card');
    card.style.setProperty('--nc', n.color);
    if(disconnected) card.style.opacity = '.55';
    const statusChip = disconnected ? '<span class="chip crit">연결 끊김</span>'
      : unknown ? '<span class="chip pending">확인 중</span>'
      : (h.disk>=90||h.queue>=1000?'<span class="chip crit">경보</span>':h.disk>=80?'<span class="chip warn">주의</span>':'<span class="chip pass">정상</span>');
    card.innerHTML = `
      <div class="name">${n.name}<span class="st">${statusChip}</span></div>
      <div class="host">${n.id} · ${n.host}</div>
      <div class="gauges">
        ${[['CPU',h.cpu],['MEM',h.mem],['DISK',h.disk]].map(([k,p])=>`
          <div class="gauge"><span class="lbl">${k}</span>
            <div class="bar"><i class="${cls(p)}" style="width:${p}%"></i></div>
            <span class="val">${p}%</span></div>`).join('')}
      </div>
      <div class="queue-line"><span class="hint">메일 큐 대기</span><span class="q ${qcls}">${h.queue.toLocaleString()}<small style="font-size:11px;color:var(--dim)"> 건</small></span></div>
      ${disconnected?'<div class="hint" style="margin-top:8px;color:var(--crit)">IP·Port 응답 없음 — 마지막 확인된 값입니다</div>':''}`;
    return card;
  }));
}

async function fetchHourlyStats(){
  try{
    const s = await api('/api/v1/stats/hourly');
    renderChart(s);
  }catch(e){ /* 차트는 실패해도 나머지 화면에 영향 없음 */ }
}

function renderChart(s){
  const c = $('#thruChart'), x=$('#thruX'); if(!c) return;
  const data = s.processed, blk = s.blocked;
  const max = Math.max(...data, 1);
  c.replaceChildren(...data.map((d,i)=>{
    const col = el('div','col');
    const dh = Math.max(3, d/max*100), bh = Math.max(blk[i]?2:0, blk[i]/max*100);
    col.innerHTML = `<div class="b blk" style="height:${bh}%"></div><div class="b" style="height:${dh}%"></div>`;
    col.title = `${i}시 → 처리 ${d}건 / 격리 ${blk[i]}건`;
    if(i===s.hour) col.style.outline = '1px dashed var(--webmail)';
    return col;
  }));
  x.replaceChildren(...data.map((_,i)=> el('span',null, i%4===0? String(i).padStart(2,'0') : '')));
}

function renderFeed(){
  const f = $('#alertFeed'); if(!f) return;
  if(!alerts.length){ f.replaceChildren(el('div','empty','아직 발생한 경보가 없습니다.')); return; }
  f.replaceChildren(...alerts.slice(0,20).map(a=>{
    const it = el('div','feed-item');
    it.innerHTML = `<i class="sev" style="background:${sevColor(a.sev)}"></i>
      <div><b>[${a.sev}] ${nodeById(a.node)?.name||a.node}</b> → ${a.msg}
      <div class="t">${a.t} · 발송: ${a.ch}</div></div>`;
    return it;
  }));
}
