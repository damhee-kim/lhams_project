/* ===== 구현 현황 (SCR-06, LIVE) — 화면↔API 매핑 · 전환 지점 · 감사 로그 =====
 * 골격 마크업(표 3개 중 앞 2개는 전부 정적)은 views/dev.jsp에 있다 — renderView()가 로드·주입한다. */
views.dev = async () => {
  if(!await renderView('dev')) return;
  loadAudit();
};

async function loadAudit(){
  try{
    const r = await api('/api/v1/audit?limit=20');
    const tb = $('#auditRows'); if(!tb) return;
    tb.innerHTML = r.items.map(a=>`<tr>
      <td class="mono">${new Date(a.ts*1000).toLocaleTimeString('ko-KR',{hour12:false})}</td>
      <td>${a.actor}</td><td><span class="chip info">${a.action}</span></td>
      <td class="mono" style="font-size:11px">${a.target}</td><td>${a.result}</td></tr>`).join('') || '<tr><td colspan="5" class="empty">감사 로그가 없습니다.</td></tr>';
  }catch(e){ /* dev 탭 부가 정보이므로 실패해도 무시 */ }
}
