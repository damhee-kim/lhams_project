/* ===== 사전 경보 설정 (SCR-04) — 임계치 · Webhook · 개인정보 정책 · 이력 =====
 * 골격 마크업은 views/alert.jsp에 있다 — renderView()가 로드·주입한다. */
views.alert = async () => {
  if(!await renderView('alert')) return;
  $('#thDisk').value = thresholds.disk; $('#thDiskV').textContent = thresholds.disk+'%';
  $('#thQueue').value = thresholds.queue; $('#thQueueV').textContent = thresholds.queue.toLocaleString()+'건';
  $('#thCpu').value = thresholds.cpu; $('#thCpuV').textContent = thresholds.cpu+'%';
  $('#webhookUrl').value = webhookCfg.url;
  $('#privRet').value = privacySettings.journey_retention_days; $('#privRetV').textContent = privacySettings.journey_retention_days+'일';
  $('#privMask').checked = privacySettings.mask_subject;
  const bind = (id, key, fmt) => { $(id).oninput = e=>{ thresholds[key]=+e.target.value; $(id+'V').textContent = fmt(+e.target.value); }; };
  bind('#thDisk','disk',v=>v+'%'); bind('#thQueue','queue',v=>v.toLocaleString()+'건'); bind('#thCpu','cpu',v=>v+'%');
  $('#privRet').oninput = e=>{ $('#privRetV').textContent = e.target.value+'일'; };
  $('#saveTh').onclick = async ()=>{
    try{
      thresholds = await api('/api/v1/alerts/thresholds', {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(thresholds)});
      await api('/api/v1/settings/webhook', {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({url: $('#webhookUrl').value})});
      webhookCfg.url = $('#webhookUrl').value;
      toast(`임계치 저장 완료 → 디스크 ${thresholds.disk}% / 큐 ${thresholds.queue.toLocaleString()}건 / CPU ${thresholds.cpu}%`, 'ok');
    }catch(e){ toast('저장 실패: '+e.message, 'err'); }
  };
  $('#testHook').onclick = async ()=>{
    try{
      const r = await api('/api/v1/alerts/test-webhook', {method:'POST'});
      await refreshAlerts();
      toast(`테스트 경보 발송 완료 → ${r.channel}`, 'ok');
    }catch(e){ toast('테스트 발송 실패: '+e.message, 'err'); }
  };
  $('#savePriv').onclick = async ()=>{
    try{
      privacySettings = await api('/api/v1/settings/privacy', {method:'PUT', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({journey_retention_days:+$('#privRet').value, mask_subject:$('#privMask').checked})});
      toast(`개인정보 설정 저장 완료 → 보관 ${privacySettings.journey_retention_days}일 · 마스킹 ${privacySettings.mask_subject?'사용':'미사용'}`, 'ok');
    }catch(e){ toast('저장 실패: '+e.message, 'err'); }
  };
  renderAlertRows();
};
function renderAlertRows(){
  const tb = $('#alertRows'); if(!tb) return;
  tb.innerHTML = alerts.map(a=>`<tr>
    <td class="mono">${a.t}</td>
    <td><b>${nodeById(a.node)?.name||a.node}</b></td>
    <td><span class="chip ${a.sev==='CRITICAL'?'crit':a.sev==='WARNING'?'warn':'info'}">${a.sev}</span></td>
    <td>${a.msg}</td><td class="mono">${a.ch}</td></tr>`).join('') || '<tr><td colspan="5" class="empty">경보 이력이 없습니다.</td></tr>';
}
