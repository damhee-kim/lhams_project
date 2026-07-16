/* ===== SOS 로그 패키징 (SCR-03) — 노드 선택 · 진행률 SSE · 저장 설정 ===== */
let sosNodes = new Set(NODES.map(n=>n.id)), sosRunning=false, sosEventSource=null;

/* 골격 마크업은 views/sos.jsp에 있다 — renderView()가 로드·주입한다. */
views.sos = async () => {
  if(!await renderView('sos')) return;
  $('#sosStart').value = defaultStart();
  $('#sosEnd').value = defaultEnd();
  for(const nid of [...sosNodes]){ if(nodeEnabled[nid]===false) sosNodes.delete(nid); } // 사용 안 함 노드는 선택 해제
  renderSosPicks(); renderSosSteps();
  $('#sosRun').onclick = runSos;
  bindSosStorageCfg();
  loadSosSettings();
};

function defaultStart(){ const d=new Date(Date.now()-90*60000); return toLocalInput(d); }
function defaultEnd(){ return toLocalInput(new Date()); }
function toLocalInput(d){ const p=n=>String(n).padStart(2,'0'); return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`; }

async function loadSosSettings(){
  try{
    sosCfg = await api('/api/v1/settings/sos-storage');
    $('#sosDir').value = sosCfg.dir;
    $('#sosRetV').textContent = sosCfg.retention_days+'일';
    $('#sosCapV').textContent = sosCfg.max_gb+' GB';
    $('#sosRet').value = sosCfg.retention_days; $('#sosCap').value = sosCfg.max_gb;
    $('#sosUsageHint').innerHTML = `현재 저장 사용량 <b class="mono">${sosCfg.used_gb.toFixed(2)} GB</b> / 상한 ${sosCfg.max_gb} GB · 보관 ${sosCfg.retention_days}일 초과분은 자동 폐기됩니다 (Zero-Impact, 서버 실제 디스크 반영).`;
  }catch(e){ toast('저장 설정 조회 실패: '+e.message, 'err'); }
}

function bindSosStorageCfg(){
  $('#sosRet').oninput = e=>{ $('#sosRetV').textContent = e.target.value + '일'; };
  $('#sosCap').oninput = e=>{ $('#sosCapV').textContent = e.target.value + ' GB'; };
  const showMsg = (ok, text)=>{
    const m = $('#sosDirMsg');
    m.innerHTML = ok ? `<span class="chip pass">검증 통과</span> <span style="margin-left:8px">${text}</span>`
                     : `<span class="chip crit">검증 실패</span> <span style="margin-left:8px;color:#FFB4B4">${text}</span>`;
  };
  $('#sosDirCheck').onclick = async ()=>{
    try{
      const r = await api('/api/v1/settings/sos-storage/validate', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({dir: $('#sosDir').value})});
      showMsg(r.ok, r.message);
    }catch(e){ showMsg(false, e.message); }
  };
  $('#sosDirSave').onclick = async ()=>{
    try{
      const r = await api('/api/v1/settings/sos-storage', {method:'PUT', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({dir:$('#sosDir').value, retention_days:+$('#sosRet').value, max_gb:+$('#sosCap').value})});
      sosCfg = {...sosCfg, ...r};
      $('#sosDir').value = r.dir;
      showMsg(true, `<span class="mono">${r.dir}</span> 로 저장되었습니다.`);
      toast('PUT /api/v1/settings/sos-storage 저장 완료 → 감사 기록: admin.kim', 'ok');
      loadSosSettings();
    }catch(e){ showMsg(false, e.message); toast('저장 실패: '+e.message, 'err'); }
  };
}

function renderSosPicks(){
  const usable = NODES.filter(n => nodeEnabled[n.id] !== false);
  if(!usable.length){ $('#sosPicks').replaceChildren(el('div','empty','사용 중인 노드가 없습니다 — 관제 현황에서 최소 1개를 켜세요.')); return; }
  $('#sosPicks').replaceChildren(...usable.map(n=>{
    const b = el('button','npick'+(sosNodes.has(n.id)?' on':''));
    const discon = CONFIGURABLE_NODES.includes(n.id) && nodeConnected[n.id]===false;
    b.innerHTML = `<i class="nd" style="background:${n.hex}"></i>${n.name} <span class="mono" style="color:var(--dim)">${n.host}</span>${discon?' <span class="mono" style="color:var(--crit)">· 연결 끊김</span>':''}`;
    b.onclick = ()=>{ if(sosRunning) return; sosNodes.has(n.id)?sosNodes.delete(n.id):sosNodes.add(n.id); renderSosPicks(); renderSosSteps(); };
    return b;
  }));
}

const SOS_PHASE_LABELS = ['수집 명령 수신','로그 수집 (/var/log/*)','top · df 덤프','압축 및 전송'];
function renderSosSteps(perNode){
  $('#sosSteps').replaceChildren(...NODES.filter(n=>sosNodes.has(n.id)).map(n=>{
    const pn = perNode?.[n.id];
    const phase = pn ? pn.phase : -1;
    const box = el('div','sos-node');
    box.innerHTML = `<div class="nn"><i class="nd" style="width:9px;height:9px;border-radius:50%;background:${n.hex}"></i>${n.name}</div>
      <ul>${SOS_PHASE_LABELS.map((p,i)=>{
        const cls = phase===-2 ? 'failed' : (phase===99||phase>i ? 'done' : phase===i ? 'doing' : '');
        return `<li class="${cls}"><span class="ic"></span>${p}</li>`;
      }).join('')}</ul>`;
    return box;
  }));
}

async function runSos(){
  if(sosRunning) return;
  if(!sosNodes.size){ toast('수집 대상 노드를 1개 이상 선택하세요.','err'); return; }
  sosRunning = true; $('#sosRun').disabled = true; $('#sosResult').classList.remove('show','partial');
  const t0 = Date.now();
  const timerIv = setInterval(()=>{ $('#sosTimer').textContent = `경과 ${((Date.now()-t0)/1000).toFixed(1)}s`; }, 100);

  let job;
  try{
    job = await api('/api/v1/nodes/sos-package', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({start_time:$('#sosStart').value, end_time:$('#sosEnd').value, nodes:[...sosNodes]})});
  }catch(e){
    clearInterval(timerIv);
    toast('SOS 시작 실패: '+e.message, 'err');
    sosRunning=false; $('#sosRun').disabled=false;
    return;
  }
  toast('중앙서버 → 4개 Edge Agent 비동기 수집 명령 발송 (병렬)', 'ok');

  sosEventSource = new EventSource(`/api/v1/nodes/sos-package/${job.job_id}/events`);
  sosEventSource.onmessage = (ev)=>{ renderSosSteps(JSON.parse(ev.data).per_node); };
  sosEventSource.addEventListener('done', (ev)=>{
    const data = JSON.parse(ev.data);
    clearInterval(timerIv); sosEventSource.close();
    const took = ((Date.now()-t0)/1000).toFixed(1);
    if(data.state==='FAILED'){
      $('#sosTimer').textContent = `실패 · ${took}s`;
      toast('SOS 수집 전체 실패 — 재시도가 필요합니다.', 'err');
    } else {
      $('#sosTimer').textContent = `완료 · ${took}s`;
      $('#sosResultChip').textContent = data.state==='PARTIAL_DONE' ? '부분 완료' : '병합 완료';
      $('#sosResultChip').className = 'chip ' + (data.state==='PARTIAL_DONE' ? 'warn' : 'pass');
      $('#sosResult').classList.add('show', data.state==='PARTIAL_DONE' ? 'partial' : '');
      $('#sosFn').textContent = data.manifest;
      $('#sosFs').textContent = `SHA-256 ${data.sha256.slice(0,20)}… · ${(data.size_bytes/1024).toFixed(1)} KB · job ${job.job_id} · 저장 ${sosCfg.dir}`;
      $('#sosDl').onclick = ()=>{ window.location.href = `/api/v1/nodes/sos-package/${job.job_id}/download`; };
      toast(`SOS 패키지 ${data.state==='PARTIAL_DONE'?'부분 완료(일부 노드 실패)':'완료'} (${took}초) — 기존 40분 대비 대폭 단축`, data.state==='PARTIAL_DONE'?'warn':'ok');
      loadSosSettings();
    }
    sosRunning=false; $('#sosRun').disabled=false;
  });
}
