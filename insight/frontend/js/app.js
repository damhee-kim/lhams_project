/* ===== 앱 진입점 — 내비게이션 · 실시간 스트림(SSE) · 부트스트랩 =====
 * 반드시 마지막에 로드된다: 이 시점엔 core.js + view-*.js가 정의한
 * views.*, render*, api() 등이 전부 준비돼 있어야 한다. */

$('#nav').querySelectorAll('button').forEach(b=>{
  b.onclick = async ()=>{
    $('#nav').querySelector('.active')?.classList.remove('active');
    b.classList.add('active');
    currentView = b.dataset.view;
    $('#viewTitle').textContent = VIEW_TITLES[currentView];
    await views[currentView]();
  };
});

setInterval(()=>{ $('#clock').textContent = new Date().toLocaleTimeString('ko-KR',{hour12:false}); }, 1000);

/* ===== 관리자 토큰 입력 · 가이드 · 검증 =====
 * 붙여넣은 토큰이 실제로 맞는지 그 자리에서 확인시켜준다 — 이전에는 값을 그냥
 * localStorage에 저장만 하고, 조작(격리 해제 등)을 시도할 때가 되어서야
 * 401로 틀렸다는 걸 알 수 있었다. */
const tokenInput = $('#adminTokenInput');
const tokenStatus = $('#tokenStatus');
tokenInput.value = getAdminToken();

$('#tokenHelpBtn').addEventListener('click', ()=>{ $('#tokenHelpBox').classList.toggle('show'); });

async function verifyAdminToken(token){
  if(!token){ tokenStatus.className='token-status'; tokenStatus.textContent='•'; tokenStatus.title='아직 확인되지 않음'; return; }
  tokenStatus.className='token-status'; tokenStatus.textContent='…'; tokenStatus.title='확인 중…';
  try{
    const res = await fetch('/api/v1/auth/verify', {headers:{'X-Admin-Token': token}});
    if(res.ok){
      tokenStatus.className='token-status ok'; tokenStatus.textContent='✓'; tokenStatus.title='유효한 토큰';
      toast('관리자 토큰이 확인되었습니다.', 'ok');
    }else{
      tokenStatus.className='token-status bad'; tokenStatus.textContent='✗'; tokenStatus.title='토큰이 일치하지 않음';
      toast('관리자 토큰이 올바르지 않습니다 — data/admin_token.txt 값을 다시 확인하세요.', 'err');
    }
  }catch(e){
    tokenStatus.className='token-status bad'; tokenStatus.textContent='✗'; tokenStatus.title='서버에 연결할 수 없음';
    toast('토큰 검증 요청 실패: '+e.message, 'err');
  }
}

tokenInput.addEventListener('change', ()=>{
  const v = tokenInput.value.trim();
  localStorage.setItem('insightAdminToken', v);
  verifyAdminToken(v);
});
if(tokenInput.value) verifyAdminToken(tokenInput.value);

/* ===== 실시간 스트림 (SSE) — 3초 폴링을 대체 =====
 * 뷰/탭 상태와 무관하게 계속 요청을 쏘던 기존 polling 대신, 연결 하나를 유지하며
 * 서버가 상태가 바뀔 때만 push한다. 탭이 백그라운드로 가면 연결을 끊어 자원을
 * 절약하고, 끊기면 사용자가 볼 수 있는 배지로 표시하며 지수 백오프로 재연결한다. */
let evtSource = null, reconnectDelay = 1000, journeysRefreshing = false;

function setConnStatus(status){
  const dot = $('#connDot'), label = $('#connLabel');
  if(!dot || !label) return;
  dot.style.animation = status==='online' ? '' : 'none';
  if(status==='online'){ dot.style.background='var(--pass)'; label.textContent='Edge Agent 4/4 연결 · 실시간 스트림'; }
  else if(status==='connecting'){ dot.style.background='var(--warn)'; label.textContent='실시간 연결 시도 중…'; }
  else{ dot.style.background='var(--crit)'; label.textContent=`연결 끊김 · ${Math.round(reconnectDelay/1000)}초 후 재시도`; }
}

function applyStreamPayload(p){
  if(p.connected) nodeConnected = {...nodeConnected, ...p.connected};
  if(p.health){ health = p.health; if(currentView==='overview'){ renderHealth(); updateNodeEndpointBadges(); } }
  if(p.hourly && currentView==='overview') renderChart(p.hourly);
  if(p.alerts){ alerts = p.alerts; if(currentView==='overview') renderFeed(); if(currentView==='alert') renderAlertRows(); }
}

async function maybeRefreshJourneys(){
  if(currentView!=='journey' || journeysRefreshing) return;
  journeysRefreshing = true;
  try{ await refreshJourneys(); } finally{ journeysRefreshing = false; }
}

function connectStream(){
  if(document.hidden) return; // 탭이 보이지 않으면 연결하지 않음 — 불필요한 서버 부하 방지
  setConnStatus('connecting');
  evtSource = new EventSource('/api/v1/stream');
  evtSource.addEventListener('snapshot', ev=>{ applyStreamPayload(JSON.parse(ev.data)); reconnectDelay=1000; setConnStatus('online'); });
  evtSource.addEventListener('tick', ev=>{ applyStreamPayload(JSON.parse(ev.data)); reconnectDelay=1000; setConnStatus('online'); });
  evtSource.addEventListener('journeys_changed', ()=>{ maybeRefreshJourneys(); });
  evtSource.onerror = ()=>{
    evtSource.close();
    setConnStatus('offline');
    setTimeout(connectStream, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay*2, 15000); // 지수 백오프, 최대 15초
  };
}

document.addEventListener('visibilitychange', ()=>{
  if(document.hidden){ evtSource?.close(); evtSource=null; }
  else if(!evtSource){ reconnectDelay=1000; connectStream(); }
});

async function boot(){
  try{
    const [al, th, wh, ne, priv, site] = await Promise.all([
      api('/api/v1/alerts?limit=50'), api('/api/v1/alerts/thresholds'), api('/api/v1/settings/webhook'),
      api('/api/v1/settings/node-endpoints'), api('/api/v1/settings/privacy'), api('/api/v1/site'),
    ]);
    alerts = al.items; thresholds = th; webhookCfg = wh; privacySettings = priv;
    nodeEndpoints = ne.endpoints; nodeConnected = {...nodeConnected, ...ne.connected};
    nodeEnabled = {...nodeEnabled, ...ne.enabled};
    applyNodeEndpointsToNodes();
    $('#siteBadge').textContent = `SITE: ${site.name} (${site.id})`;
  }catch(e){ toast('초기 데이터 로드 실패: '+e.message, 'err'); }
  await views.overview();
  connectStream();
}
boot();
