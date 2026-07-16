/* Crinity Insight — 공통 상태·DOM·네트워크 헬퍼 (구 §1 DATA / §2 UTIL)
 * 다른 모든 js/*.js 파일보다 먼저 로드되어야 한다(index.jsp의 <script> 순서 참고).
 * 여기 선언된 let/const는 일반 <script>(비-모듈)로 로드되므로 전역 스코프를 공유한다 —
 * 각 view-*.js 파일이 이 값들을 그대로 읽고 재할당할 수 있다. */

/* host는 하드코딩하지 않는다 — 4개 노드 전부 서버가 실제로 보관 중인 값
 * (GET /api/v1/settings/node-endpoints)으로 채워진다(applyNodeEndpointsToNodes 참고).
 * 로드 전까지는 "미설정"으로 표시. */
/* 실제 메일 처리 순서: 웹메일 발신 → 메일브레이커(DLP) → 스팸브레이커(스팸 필터) → 아카이빙 */
const NODES = [
  {id:"Webmail",     name:"웹메일",       host:"미설정", color:"var(--webmail)", hex:"#4C8DFF"},
  {id:"MailBreaker", name:"메일브레이커", host:"미설정", color:"var(--mailbrk)", hex:"#FF5D5D"},
  {id:"SpamBreaker", name:"스팸브레이커", host:"미설정", color:"var(--spam)",    hex:"#F7B32B"},
  {id:"Archiving",   name:"아카이빙",     host:"미설정", color:"var(--archive)", hex:"#35C98E"},
];
const nodeById = id => NODES.find(n=>n.id===id);
const CONFIGURABLE_NODES = ["Webmail","MailBreaker","SpamBreaker","Archiving"]; // 4개 전부 IP·Port·사용여부 설정 가능

let health = Object.fromEntries(NODES.map(n=>[n.id,{cpu:0,mem:0,disk:0,queue:0}]));
let nodeEndpoints = {}; // {Webmail:{host,port}, ...} — 서버에서 로드
let nodeConnected = {Webmail:null, MailBreaker:null, SpamBreaker:null, Archiving:null}; // null=아직 미확인
let nodeEnabled = {Webmail:true, MailBreaker:true, SpamBreaker:true, Archiving:true}; // 사용 여부 — 서버에서 로드
let alerts = [];
let thresholds = {disk:90, queue:1000, cpu:85};
let webhookCfg = {url:''};
let sosCfg = {dir:'/var/lib/insight/sos-packages', retention_days:30, max_gb:50, used_gb:0};
let privacySettings = {journey_retention_days:90, mask_subject:false};

function getAdminToken(){ return localStorage.getItem('insightAdminToken') || ''; }
function focusAdminTokenInput(){ $('#adminTokenInput')?.focus(); }

async function api(path, opts){
  opts = {...(opts||{})};
  const method = (opts.method || 'GET').toUpperCase();
  if(method !== 'GET'){
    opts.headers = {...(opts.headers||{}), 'X-Admin-Token': getAdminToken()};
  }
  const res = await fetch(path, opts);
  let body = null;
  try{ body = await res.json(); }catch(e){ /* no body */ }
  if(res.status===401){
    focusAdminTokenInput();
    throw new Error('관리자 토큰이 필요합니다 (좌측 하단에 입력하세요).');
  }
  if(res.status===429){
    throw new Error('요청이 너무 잦습니다 — 잠시 후 다시 시도하세요.');
  }
  if(!res.ok){ throw new Error((body && body.detail) || `HTTP ${res.status}`); }
  return body;
}

const $ = s => document.querySelector(s);
const el = (tag, cls, html) => {const e=document.createElement(tag); if(cls)e.className=cls; if(html!=null)e.innerHTML=html; return e;};
const stateChip = s => ({
  ARCHIVED:'<span class="chip pass">보관 완료</span>', PASS:'<span class="chip pass">통과</span>',
  QUARANTINED:'<span class="chip crit">격리됨</span>', DELAYED:'<span class="chip warn">지연</span>',
  PENDING:'<span class="chip pending">미도달</span>', RELEASED:'<span class="chip info">해제됨</span>',
}[s]||s);
function toast(msg, kind){ const t=el('div','toast-item '+(kind||''), msg); $('#toast').appendChild(t); setTimeout(()=>t.remove(), 3200); }
function sevColor(s){return s==='CRITICAL'?'var(--crit)':s==='WARNING'?'var(--warn)':'var(--webmail)';}

/* ================= 뷰 레지스트리 ================= */
const content = $('#content');
const VIEW_TITLES = {overview:"관제 현황", journey:"메일 사전 추적", sos:"SOS 로그 패키징", alert:"사전 경보 설정", arch:"시스템 아키텍처 (3-Tier)", dev:"구현 현황 (LIVE)"};
const views = {};
let currentView = 'overview';

/* 화면 골격 마크업은 js/view-*.js 문자열이 아니라 views/<name>.jsp 파일로 분리돼 있다
 * (index.jsp와 동일하게 순수 마크업 + 스크립틀릿/EL 없음). views.X는 이 두 헬퍼로
 * 골격을 fetch해 주입한 뒤, 그 다음 줄부터 기존처럼 동적 값 하이드레이션 · 이벤트
 * 바인딩 · 데이터 렌더링을 이어서 한다. */
const viewFragmentCache = {};
async function loadViewFragment(name){
  if(!viewFragmentCache[name]){
    const res = await fetch(`/static/views/${name}.jsp`);
    if(!res.ok) throw new Error(`화면 템플릿 로드 실패: ${name}.jsp (HTTP ${res.status})`);
    viewFragmentCache[name] = await res.text();
  }
  return viewFragmentCache[name];
}

let viewRenderToken = 0;
async function renderView(name){
  const token = ++viewRenderToken;
  let html;
  try{ html = await loadViewFragment(name); }
  catch(e){ toast(e.message, 'err'); return false; }
  if(token !== viewRenderToken) return false; // 대기 중 사용자가 다른 화면으로 이동함
  const v = el('div','view active');
  v.innerHTML = html;
  content.replaceChildren(v);
  return true;
}
