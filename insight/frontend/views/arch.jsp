<!-- 시스템 아키텍처(SCR-05) 골격 — 순수 마크업, 스크립틀릿/EL 없음(index.jsp 참고).
     이 화면은 런타임 값이 전혀 없는 정적 도해라 js/view-arch.js는 그대로 주입만 한다. -->
<div class="card arch-wrap">
  <h3>Edge → Central → Frontend 3-Tier 마이크로아키텍처 · Zero-Impact 원칙</h3>
  <svg class="arch-svg" viewBox="0 0 820 410" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="3티어 아키텍처 다이어그램">
    <defs><marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="none" stroke="#8A97B5"/></marker></defs>
    <g transform="translate(285,20)">
      <rect width="250" height="70" rx="12" fill="#0F1526" stroke="#4C8DFF" stroke-opacity=".6"/>
      <text x="20" y="30" fill="#E8EDF7" font-size="14" font-weight="800">브라우저 관리자 대시보드</text>
      <text x="20" y="52" fill="#8A97B5" font-size="11">단일 HTML · EventSource(SSE) 실시간 스트림 · fetch(조작 시)</text>
    </g>
    <path d="M410 142 L410 90" stroke="#4C8DFF" stroke-width="2" marker-end="url(#arr)"/>
    <text x="424" y="122" fill="#56618A" font-size="10" font-family="monospace">REST /api/v1 (JSON)</text>
    <g transform="translate(240,142)">
      <rect width="340" height="82" rx="12" fill="#131A2C" stroke="#F7B32B" stroke-opacity=".55"/>
      <text x="20" y="28" fill="#E8EDF7" font-size="14" font-weight="800">FastAPI 중앙서버 (uvicorn, 비동기 I/O)</text>
      <text x="20" y="48" fill="#8A97B5" font-size="11">Message-ID Join·캐싱 / Timeout 병목 감지</text>
      <text x="20" y="66" fill="#8A97B5" font-size="11">SOS 잡 상태머신 / 경보 룰 엔진 → Webhook</text>
    </g>
    <text x="30" y="270" fill="#56618A" font-size="10" font-family="monospace">내부망(Private IP) 가정 · 경량 JSON push</text>

    <g transform="translate(30,300)">
      <rect width="150" height="86" rx="12" fill="#0F1526" stroke="#4C8DFF" stroke-opacity=".55"/>
      <circle cx="20" cy="24" r="5" fill="#4C8DFF"/>
      <text x="34" y="29" fill="#E8EDF7" font-size="13" font-weight="700">웹메일</text>
      <text x="18" y="50" fill="#8A97B5" font-size="10" font-family="monospace">10.10.1.11</text>
      <text x="18" y="68" fill="#56618A" font-size="10">Edge Agent (시뮬레이션)</text>
    </g>
    <path d="M 105 300 C 105 260, 410 250, 410 224" stroke="#4C8DFF" stroke-opacity=".5" stroke-width="2" fill="none" marker-end="url(#arr)"/>

    <g transform="translate(230,300)">
      <rect width="150" height="86" rx="12" fill="#0F1526" stroke="#F7B32B" stroke-opacity=".55"/>
      <circle cx="20" cy="24" r="5" fill="#F7B32B"/>
      <text x="34" y="29" fill="#E8EDF7" font-size="13" font-weight="700">스팸브레이커</text>
      <text x="18" y="50" fill="#8A97B5" font-size="10" font-family="monospace">10.10.1.12</text>
      <text x="18" y="68" fill="#56618A" font-size="10">Edge Agent (시뮬레이션)</text>
    </g>
    <path d="M 305 300 C 305 260, 410 250, 410 224" stroke="#F7B32B" stroke-opacity=".5" stroke-width="2" fill="none" marker-end="url(#arr)"/>

    <g transform="translate(430,300)">
      <rect width="150" height="86" rx="12" fill="#0F1526" stroke="#FF5D5D" stroke-opacity=".55"/>
      <circle cx="20" cy="24" r="5" fill="#FF5D5D"/>
      <text x="34" y="29" fill="#E8EDF7" font-size="13" font-weight="700">메일브레이커</text>
      <text x="18" y="50" fill="#8A97B5" font-size="10" font-family="monospace">10.10.1.13</text>
      <text x="18" y="68" fill="#56618A" font-size="10">Edge Agent (시뮬레이션)</text>
    </g>
    <path d="M 505 300 C 505 260, 410 250, 410 224" stroke="#FF5D5D" stroke-opacity=".5" stroke-width="2" fill="none" marker-end="url(#arr)"/>

    <g transform="translate(630,300)">
      <rect width="150" height="86" rx="12" fill="#0F1526" stroke="#35C98E" stroke-opacity=".55"/>
      <circle cx="20" cy="24" r="5" fill="#35C98E"/>
      <text x="34" y="29" fill="#E8EDF7" font-size="13" font-weight="700">아카이빙</text>
      <text x="18" y="50" fill="#8A97B5" font-size="10" font-family="monospace">10.10.1.14</text>
      <text x="18" y="68" fill="#56618A" font-size="10">Edge Agent (시뮬레이션)</text>
    </g>
    <path d="M 705 300 C 705 260, 410 250, 410 224" stroke="#35C98E" stroke-opacity=".5" stroke-width="2" fill="none" marker-end="url(#arr)"/>

    <text x="30" y="404" fill="#56618A" font-size="10">Zero-Impact: 실제 배포 시 Agent 리소스 상한 CPU 5% / MEM 100MB — 이 데모의 백엔드 프로세스는 그 원칙만 문서화, 실제 측정은 실장비 배포 후 수행</text>
  </svg>
  <div class="hint" style="margin-top:12px">
    · Edge Agent: OS 내장 Python 3 + Bash, <b>CPU &lt; 5% / MEM &lt; 100MB</b> — 이 데모에서는 4대 물리 서버가 없어 서버 프로세스 내부 시뮬레이션으로 대체(§5 참고)<br>
    · Backend: FastAPI 비동기 I/O — Message-ID 기준 Join·캐싱, Timeout 병목 감지, SOS 잡 상태 머신, 경보 룰 엔진 — <b>실제 동작 중</b><br>
    · 저장: SOS 패키지·감사 로그·설정 파일은 로컬 디스크에 실제로 기록됨(샌드박스 경로, §5 개발 가이드 참고)
  </div>
</div>
