<!-- 메일 사전 추적(SCR-02) 골격 — 순수 마크업, 스크립틀릿/EL 없음(index.jsp 참고).
     검색어 값·필터 active 상태는 js/view-journey.js가 로드 직후 채운다. -->
<div class="card">
  <div class="searchbar">
    <input type="text" id="jSearch" placeholder="Message-ID, 발신자, 수신자, 제목 키워드로 검색 (GET /api/v1/journeys?keyword=)">
    <button class="btn" id="jSearchBtn">여정 검색</button>
  </div>
  <div class="filters" id="jFilters">
    <button class="fchip" data-f="ALL">전체</button>
    <button class="fchip" data-f="QUARANTINED">격리</button>
    <button class="fchip" data-f="DELAYED">지연</button>
    <button class="fchip" data-f="ARCHIVED">정상 보관</button>
  </div>
  <div class="jlist" id="jList"></div>
</div>
<div class="card journey-detail" id="jDetail"></div>
