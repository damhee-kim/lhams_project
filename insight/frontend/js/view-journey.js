/* ===== 메일 사전 추적 (SCR-02) — 검색 · 노선도 타임라인 · 격리 해제 =====
 * 골격 마크업은 views/journey.jsp에 있다 — renderView()가 로드·주입한다. */
let jFilter = 'ALL', jKeyword = '', selectedMsgId = null, JOURNEYS = [];
views.journey = async () => {
  if(!await renderView('journey')) return;
  $('#jSearch').value = jKeyword;
  $('#jFilters').querySelectorAll('.fchip').forEach(b=>{
    b.classList.toggle('on', b.dataset.f===jFilter);
    b.onclick = async ()=>{ jFilter=b.dataset.f; await views.journey(); };
  });
  $('#jSearchBtn').onclick = ()=>{ jKeyword=$('#jSearch').value.trim(); refreshJourneys(); };
  $('#jSearch').addEventListener('keydown', e=>{ if(e.key==='Enter'){ jKeyword=e.target.value.trim(); refreshJourneys(); }});
  refreshJourneys();
};

async function refreshJourneys(){
  try{
    const q = new URLSearchParams({keyword:jKeyword, status:jFilter, limit:'100'});
    const res = await api('/api/v1/journeys?'+q.toString());
    JOURNEYS = res.items;
  }catch(e){ toast('여정 목록 조회 실패: '+e.message,'err'); JOURNEYS = []; }
  if(!JOURNEYS.find(j=>j.message_id===selectedMsgId)) selectedMsgId = JOURNEYS[0]?.message_id ?? null;
  renderJList(); renderJDetail();
}

function miniLine(j){
  return `<div class="mini-line">${j.nodes.map((s,i)=>{
    const n=nodeById(s.node);
    const c = s.status==='PENDING' ? 'var(--line)' : s.status==='QUARANTINED' ? 'var(--crit)' : s.status==='DELAYED' ? 'var(--warn)' : n.color;
    const seg = i<j.nodes.length-1 ? `<i class="ms" style="background:${s.status==='PENDING'?'var(--line-soft)':c}"></i>` : '';
    return `<i class="md" style="background:${c};${s.status==='PENDING'?'opacity:.35':''}"></i>${seg}`;
  }).join('')}</div>`;
}

function renderJList(){
  const list = $('#jList'); if(!list) return;
  if(!JOURNEYS.length){ list.replaceChildren(el('div','empty','조건에 해당하는 메일 여정이 없습니다. 키워드나 상태 필터를 조정해 보세요.')); return; }
  list.replaceChildren(...JOURNEYS.map(j=>{
    const r = el('button','jrow'+(selectedMsgId===j.message_id?' sel':''));
    r.innerHTML = `
      <div>${stateChip(j.state)}</div>
      <div><div class="subj">${j.meta.subject}</div><div class="from">${j.meta.sender} → ${j.meta.recipient}</div></div>
      ${miniLine(j)}
      <div class="time">${j.meta.received_at}</div>`;
    r.onclick = ()=>{ selectedMsgId=j.message_id; renderJList(); renderJDetail(); };
    return r;
  }));
}

/**
 * 여정 상세 — 노드별 타임라인 렌더 (시그니처 컴포넌트)
 * @spec FR-02(타임라인)·FR-03(차단 사유)·FR-04(격리 해제)
 */
function renderJDetail(){
  const d = $('#jDetail'); if(!d) return;
  const j = JOURNEYS.find(x=>x.message_id===selectedMsgId);
  if(!j){ d.innerHTML='<div class="empty">목록에서 메일을 선택하면 사전 타임라인이 표시됩니다.</div>'; return; }

  const stations = j.nodes.map((s)=>{
    const n = nodeById(s.node);
    const cls = s.status==='QUARANTINED' ? 'blocked' : s.status==='PENDING' ? 'pending' : 'reached';
    const st = el('div',`station ${cls}`);
    st.style.setProperty('--sc', s.status==='DELAYED' ? 'var(--warn)' : n.color);
    st.innerHTML = `<div class="s-dot"></div>
      <div class="s-name" style="${cls!=='pending'?`color:${s.status==='QUARANTINED'?'var(--crit)':s.status==='DELAYED'?'var(--warn)':'inherit'}`:''}">${n.name}</div>
      <div class="s-time">${s.time||'—'}</div>
      <div class="s-detail">${s.detail||'이벤트 미수신'}</div>`;
    return st.outerHTML;
  });

  const segs = j.nodes.slice(0,-1).map((s,i)=>{
    const next = j.nodes[i+1];
    const dead = next.status==='PENDING';
    const c1 = nodeById(s.node).hex, c2 = dead?'#223052':nodeById(next.node).hex;
    const lat = (!dead && next.latency!=null) ? `<span class="lat ${next.latency>=2000?'slow':''}">+${(next.latency/1000).toFixed(1)}s</span>` : '';
    return `<div class="segment ${dead?'dead':''}" style="--c1:${c1};--c2:${c2}"><div class="track"></div>${lat}</div>`;
  });

  const lineHTML = j.nodes.map((_,i)=> stations[i] + (segs[i]||'')).join('');

  let reason = '';
  const blocked = j.nodes.find(s=>s.status==='QUARANTINED');
  const delayed = j.nodes.find(s=>s.status==='DELAYED');
  if(blocked){
    reason = `<div class="reason-card">
      <span class="chip crit">차단 사유</span>
      <div class="rc-body">
        <div class="rc-title">${nodeById(blocked.node).name}에서 격리되었습니다</div>
        <div class="rc-desc">${blocked.detail}<br>고객사 담당자는 이 화면으로 차단 사유를 즉시 확인할 수 있으며(FR-03), 조치 권한 보유 관리자는 아래 버튼으로 격리를 해제할 수 있습니다.</div>
      </div>
      <button class="btn danger" id="releaseBtn">격리 강제 해제</button>
    </div>`;
  } else if(delayed){
    reason = `<div class="reason-card warn">
      <span class="chip warn">병목 감지</span>
      <div class="rc-body">
        <div class="rc-title">${nodeById(delayed.node).name} 구간 정체 (Timeout 엔진 재시도)</div>
        <div class="rc-desc">${delayed.detail}<br>다음 노드 미더미 상태가 지속되어 백엔드 Timeout 엔진이 지연으로 판정했습니다. 관제 현황의 큐 지표를 함께 확인하세요.</div>
      </div>
    </div>`;
  } else if(j.state==='PENDING'){
    reason = `<div class="reason-card warn">
      <span class="chip pending">처리 중</span>
      <div class="rc-body"><div class="rc-title">파이프라인 진행 중</div>
      <div class="rc-desc">아직 모든 노드를 통과하지 않았습니다. 3초 후 자동 갱신되며, 다음 노드 이벤트가 도착하면 타임라인이 이어집니다.</div></div>
    </div>`;
  } else {
    reason = `<div class="reason-card ok">
      <span class="chip pass">정상</span>
      <div class="rc-body">
        <div class="rc-title">전 구간 통과 · 아카이빙 보관 완료</div>
        <div class="rc-desc">총 소요 ${(j.nodes.reduce((a,s)=>a+(s.latency||0),0)/1000).toFixed(1)}초 — 4개 노드 모두 정상 통과했습니다.</div>
      </div>
    </div>`;
  }

  d.innerHTML = `
    <div class="jd-head"><div class="subj">${j.meta.subject}</div>${stateChip(j.state)}</div>
    <div class="jd-meta">
      <div><div class="k">Message-ID</div><div class="v">${j.message_id.replace('<','&lt;').replace('>','&gt;')}</div></div>
      <div><div class="k">발신자</div><div class="v">${j.meta.sender}</div></div>
      <div><div class="k">수신자</div><div class="v">${j.meta.recipient}</div></div>
      <div><div class="k">최초 수신</div><div class="v">${j.meta.received_at}</div></div>
    </div>
    <div class="transit"><div class="t-line">${lineHTML}</div></div>
    ${reason}`;

  const rb = $('#releaseBtn');
  if(rb) rb.onclick = async ()=>{
    rb.disabled = true;
    try{
      await api('/api/v1/nodes/release', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({message_id: j.message_id})});
      toast(`POST /api/v1/nodes/release → ${blocked.node} 격리 해제 완료 (감사 로그 기록: admin.kim)`, 'ok');
      await refreshJourneys();
    }catch(e){ toast('해제 실패: '+e.message, 'err'); rb.disabled=false; }
  };
}
