"""격리 해제 실제 연동 지점 — 리스크 체크리스트 "격리 해제 API '보류' 상태 해소" 대응.

MailBreaker/SpamBreaker가 실제로 어떤 인터페이스(REST API, CLI, DB 직접 갱신 등)로
격리 해제를 지원하는지 아직 확정되지 않았다. 그 확정 전까지 이 파일이 유일한
연동 지점(seam)이다 — 구축팀은 실제 사양이 나오면 `release_on_device()` 함수
본문만 교체하면 되고, `main.py`의 `release_node()`를 포함한 나머지 코드는
전혀 손댈 필요가 없다.
"""
from . import state


async def release_on_device(node_id: str, message_id: str, detail: str) -> tuple[bool, str]:
    """실제 장비에 격리 해제를 요청한다.

    Returns:
        (성공 여부, 사유/에러 메시지) — main.py는 실패 시 로컬 상태를 바꾸지 않고 502를 반환한다.

    TODO(구축팀): 실제 연동 확정 시 아래 MOCK 분기를 걷어내고 예를 들어—
      - MailBreaker: ``POST https://{host}/api/quarantine/release`` 형태의 REST 호출
      - SpamBreaker: 벤더 제공 CLI 실행 또는 격리 DB 레코드 직접 갱신
      노드별 실제 주소는 이미 ``state.node_endpoints[node_id]``에 있으므로 그대로 재사용 가능.
    """
    ep = state.node_endpoints.get(node_id)
    if not ep or not ep.get("host"):
        return True, f"MOCK: {node_id} 실장비 연동 미확정 — 로컬 상태만 변경됨 (IP·Port 미설정)"
    return True, f"MOCK: {node_id}({ep['host']}:{ep['port']}) 실장비 연동 미확정 — 로컬 상태만 변경됨"
