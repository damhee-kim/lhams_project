"""SOS 실제 로그 수집 연동 지점 — 리스크 체크리스트 "성능/실장비 연동" 대응.

지금 `simulate.run_sos_job()`은 4대 물리 서버가 없어 각 노드의 진행 단계
(수집 명령 수신 → 로그 수집 → top·df 덤프 → 압축 및 전송)를 무작위 타이밍으로
시뮬레이션하고, `build_manifest()`가 진짜 내용이 아닌 표본 로그를 만들어 tar.gz로
묶는다. 이 파일은 그 시뮬레이션을 실제 Edge Agent 통신으로 바꿀 때의 유일한
연동 지점(seam)이 되도록 미리 인터페이스만 정의해 둔 것이다 — 아직 아무 코드도
이 파일을 호출하지 않는다(호출 시점은 아래 "전환 절차" 참고).

실장비 연동 전에 반드시 정해야 하는 것 (구축팀 확인 필요):
  1. 트리거 방향 — 중앙서버가 Agent에 직접 push(HTTP 호출)하는지, 아니면 Agent가
     주기적으로 폴링해 job을 가져가는 pull 방식인지. Zero-Impact 원칙(보안명세 §1)
     상 Agent가 인바운드 포트를 열지 않는 pull이 유리하지만, 그러면 SSE로 실시간
     진행률을 보여주는 지금 UX를 위해 중앙이 Agent 상태를 다시 폴링해야 한다.
  2. 인증 — 노드별 API Key(X-API-Key, 보안명세 §5.1)를 이 어댑터가 어디서 읽어올지.
     지금 `state.node_endpoints`에는 host/port만 있고 키가 없으므로 필드 추가가 먼저 필요.
  3. 진행 상태 보고 형식 — Agent가 단계 완료를 어떤 payload로 알리는지
     (지금 프론트가 기대하는 phase index 0~3, DONE/FAILED와 매핑되어야 함).
  4. 실패·타임아웃 처리 — Agent가 응답이 없을 때 몇 초 후 FAILED로 판정할지,
     재시도를 몇 번 할지.
  5. 실제 로그 파일 위치·시간 범위 파싱 — 각 솔루션의 로그 포맷(syslog vs ISO 등)이
     서로 다를 수 있어 patterns.yaml류의 노드별 설정이 필요할 수 있다(리스크 체크리스트
     "patterns.yaml 유지보수 체계" 항목과 연결).

전환 절차(연동 사양이 확정된 후):
  1. 아래 `collect_from_node()`의 MOCK 반환을 실제 HTTP/CLI 호출로 교체.
  2. `simulate.run_sos_job()`의 무작위 진행 루프를, 각 노드마다 이 함수를 호출하고
     반환되는 실제 진행 상황으로 `job.per_node[nid]`를 갱신하는 코드로 교체.
  3. `simulate.build_manifest()`가 `collect_from_node()`가 돌려준 실제 로그 바이트를
     tar.gz에 담도록 교체(지금은 `_fake_node_files()`가 표본 텍스트를 생성).
  4. `main.py`의 SSE 스트리밍·다운로드 엔드포인트는 무수정 — 이미 job 상태만 읽어
     내려주는 구조라 내부 구현이 바뀌어도 그대로 동작한다.
"""
from . import state


async def collect_from_node(node_id: str, start_time: str, end_time: str) -> tuple[bool, dict | None, str]:
    """단일 노드에서 지정 구간의 로그·리소스 덤프를 실제로 수집한다(아직 미구현).

    Returns:
        (성공 여부, {파일명: bytes} 또는 None, 사유 메시지)

    TODO(구축팀): 위 docstring의 "실장비 연동 전에 반드시 정해야 하는 것" 5가지가
    확정되면 이 함수 본문을 실제 Agent 호출로 채운다. 노드 주소는 이미
    ``state.node_endpoints[node_id]``에 있으므로 그대로 재사용 가능.
    """
    ep = state.node_endpoints.get(node_id)
    host_desc = f"{ep['host']}:{ep['port']}" if ep and ep.get("host") else "IP·Port 미설정"
    return False, None, (
        f"MOCK: {node_id}({host_desc}) 실제 Edge Agent 연동 미확정 — "
        f"simulate.run_sos_job()의 시뮬레이션 경로를 사용 중"
    )
