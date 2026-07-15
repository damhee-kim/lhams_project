"""최소한의 접근 통제 — PoC라도 조작 API는 열어두지 않는다.

- 관리자 토큰: 상태를 바꾸는 모든 POST/PUT은 X-Admin-Token 헤더를 요구한다.
  로그인/세션 대신 공유 비밀(shared secret) 방식이며, 서버 기동 시 자동 생성되어
  콘솔과 data/admin_token.txt에 출력된다(운영자가 대시보드에 붙여넣어 사용).
- 속도 제한: IP별 슬라이딩 윈도우로 전체 요청과 조작(mutation) 요청을 분리해 제한한다.
- SSE 동시 연결 수 제한: 한 IP가 스트림 연결을 과도하게 열어 커넥션을 고갈시키는 것을 방지한다.
"""
import os
import secrets
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request

from . import state

_env_token = os.environ.get("INSIGHT_ADMIN_TOKEN")
ADMIN_TOKEN = _env_token or secrets.token_urlsafe(18)
TOKEN_WAS_GENERATED = _env_token is None


def announce_admin_token():
    print("=" * 64)
    if TOKEN_WAS_GENERATED:
        print("[Crinity Insight] INSIGHT_ADMIN_TOKEN 환경변수가 없어 임시 토큰을 생성했습니다.")
    else:
        print("[Crinity Insight] INSIGHT_ADMIN_TOKEN 환경변수를 관리자 토큰으로 사용합니다.")
    print(f"  관리자 토큰: {ADMIN_TOKEN}")
    print("  대시보드 좌측 하단 '관리자 토큰' 입력란에 붙여넣어야 조작(격리 해제/SOS 실행/설정 변경)이 가능합니다.")
    print("=" * 64)
    try:
        (state.DATA_DIR / "admin_token.txt").write_text(ADMIN_TOKEN, encoding="utf-8")
    except OSError:
        pass


def require_admin_token(x_admin_token: str | None = Header(default=None)):
    if not x_admin_token or not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(401, "관리자 토큰이 필요합니다 (X-Admin-Token 헤더가 없거나 일치하지 않습니다).")


class SlidingWindow:
    def __init__(self, max_hits: int, window_sec: float):
        self.max_hits = max_hits
        self.window_sec = window_sec
        self.hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str) -> bool:
        now = time.time()
        dq = self.hits[key]
        while dq and now - dq[0] > self.window_sec:
            dq.popleft()
        if len(dq) >= self.max_hits:
            return False
        dq.append(now)
        return True


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# 전역: 폴링을 SSE로 대체했어도 오작동 클라이언트·재시도 폭주로부터 서버를 보호
GLOBAL_LIMIT = SlidingWindow(max_hits=300, window_sec=60)
# 조작(mutation) 전용: 격리 해제·SOS 실행·설정 변경처럼 부수효과가 있는 호출은 더 빡빡하게
MUTATION_LIMIT = SlidingWindow(max_hits=20, window_sec=30)
# 스트림 연결 자체도 자원이므로 IP당 동시 연결 수 제한
STREAM_MAX_PER_IP = 5
_stream_conn_count: dict[str, int] = defaultdict(int)


def rate_limit_mutation(request: Request):
    if not MUTATION_LIMIT.check(client_ip(request)):
        raise HTTPException(429, "조작 요청이 너무 잦습니다. 잠시 후 다시 시도하세요.")


def stream_slot_acquire(ip: str) -> bool:
    if _stream_conn_count[ip] >= STREAM_MAX_PER_IP:
        return False
    _stream_conn_count[ip] += 1
    return True


def stream_slot_release(ip: str):
    _stream_conn_count[ip] = max(0, _stream_conn_count[ip] - 1)
