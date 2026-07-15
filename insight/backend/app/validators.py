"""SOS 저장 경로 검증 — crinity_insight_admin.html의 validateSosPath()와 동일 규칙.

클라이언트 검증은 UX용 1차 방어일 뿐이며, 실제 방어선은 이 서버측 함수다
(Crinity_Insight_구현전환_보완명세.md §3.4/§5.3 참조).
"""
import re

FORBIDDEN = ["/", "/etc", "/boot", "/proc", "/sys", "/dev", "/run",
             "/bin", "/sbin", "/usr", "/lib", "/lib64", "/root"]
ALLOWED_CHARS = re.compile(r"^[A-Za-z0-9/_.\-]+$")


def validate_sos_path(raw: str) -> tuple[bool, str]:
    p = (raw or "").strip()
    if not p.startswith("/"):
        return False, "절대 경로(/로 시작)만 허용됩니다."
    if ".." in p:
        return False, "상위 이동 시퀀스('..')는 허용되지 않습니다 (Path Traversal 차단)."
    if not ALLOWED_CHARS.match(p):
        return False, "경로에는 영문·숫자·/ _ . - 만 사용할 수 있습니다 (명령 주입 차단)."
    if re.search(r"/{2,}", p):
        return False, "연속된 슬래시는 허용되지 않습니다."
    norm = p.rstrip("/") or "/"
    for f in FORBIDDEN:
        if norm == f or (f != "/" and norm.startswith(f + "/")):
            shown = "/".join(norm.split("/")[:2])
            return False, f"시스템 디렉토리({shown}) 하위에는 저장할 수 없습니다."
    if len(norm) > 200:
        return False, "경로가 너무 깊습니다 (200자 이하)."
    return True, norm
