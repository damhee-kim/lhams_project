"""Crinity Insight — 인메모리 상태 저장소.

실제 Webmail/SpamBreaker/MailBreaker/Archiving 물리 서버가 없는 개발 환경이므로
Edge Agent가 보낼 이벤트를 이 프로세스 안에서 생성한다(simulate.py). 그 외
API 계약·검증 규칙·파일 I/O·SSE 스트리밍은 실제 동작이다 — Crinity_Insight_
구현전환_보완명세.md 의 MOCK→REAL 표를 참고해 어떤 부분이 여전히 시뮬레이션인지
각 함수 docstring에 명시한다.
"""
import asyncio
import json
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
# 실제 RHEL 배포 시 절대경로(/var/lib/insight/...)가 되는 SOS 저장 경로를
# 이 데모에서는 로컬 디스크 하위 샌드박스에 매핑해 mkdir·statvfs·용량 계산을
# 실제로 수행한다 (Windows 개발 환경에서도 동작하도록).
SANDBOX_ROOT = DATA_DIR / "sandbox_root"
SANDBOX_ROOT.mkdir(parents=True, exist_ok=True)

# 노드 식별자·표시명·색상만 고정값이다. IP·Port는 아래 node_endpoints에서
# 관리자가 직접 입력하며, 하드코딩된 주소를 절대 기본값으로 두지 않는다.
NODES = [
    {"id": "Webmail", "name": "웹메일", "hex": "#4C8DFF"},
    {"id": "SpamBreaker", "name": "스팸브레이커", "hex": "#F7B32B"},
    {"id": "MailBreaker", "name": "메일브레이커", "hex": "#FF5D5D"},
    {"id": "Archiving", "name": "아카이빙", "hex": "#35C98E"},
]
NODE_IDS = [n["id"] for n in NODES]

# 웹메일은 이 서버 자신(로컬)이라 항상 연결된 것으로 취급하고, 나머지 3개
# 장비는 고객사마다 실제 IP·Port가 다르므로 관리자가 직접 입력·검증한다.
CONFIGURABLE_NODES = ["SpamBreaker", "MailBreaker", "Archiving"]


def node_by_id(nid):
    return next((n for n in NODES if n["id"] == nid), None)


def display_host(nid: str) -> str:
    """카드·SOS 화면 등에서 노드 주소를 표시할 때 쓰는 단일 소스."""
    if nid == "Webmail":
        return "127.0.0.1 (로컬 · 이 서버 자신)"
    ep = node_endpoints.get(nid)
    if ep and ep.get("host") and ep.get("port"):
        return f"{ep['host']}:{ep['port']}"
    return "미설정 — IP·Port 입력 필요"


def sandbox_path(unix_path: str) -> Path:
    """검증을 통과한 유닉스 스타일 절대경로를 로컬 샌드박스 경로로 매핑."""
    rel = unix_path.lstrip("/")
    return SANDBOX_ROOT / rel if rel else SANDBOX_ROOT


# ── 노드 리소스 상태 (Edge Agent heartbeat 대체) ────────────────────────────
health = {
    "Webmail": {"cpu": 23, "mem": 61, "disk": 72, "queue": 12},
    "SpamBreaker": {"cpu": 41, "mem": 55, "disk": 68, "queue": 1024},
    "MailBreaker": {"cpu": 37, "mem": 70, "disk": 91, "queue": 88},
    "Archiving": {"cpu": 12, "mem": 48, "disk": 83, "queue": 5},
}

# ── 장비 연결 설정(IP·Port) — 스팸브레이커/메일브레이커/아카이빙 실제 통신 대상 ──
# 하드코딩된 IP를 기본값으로 두지 않는다 — host/port는 빈 값으로 시작하며,
# 관리자가 대시보드에서 직접 입력해야 연결 확인(TCP)이 시작된다.
NODE_ENDPOINTS_FILE = DATA_DIR / "node_endpoints.json"
node_endpoints = {
    "SpamBreaker": {"host": "", "port": None},
    "MailBreaker": {"host": "", "port": None},
    "Archiving": {"host": "", "port": None},
}
if NODE_ENDPOINTS_FILE.exists():
    saved_endpoints = json.loads(NODE_ENDPOINTS_FILE.read_text(encoding="utf-8"))
    for _nid in CONFIGURABLE_NODES:
        if _nid in saved_endpoints:
            node_endpoints[_nid].update(saved_endpoints[_nid])


def persist_node_endpoints():
    NODE_ENDPOINTS_FILE.write_text(json.dumps(node_endpoints, ensure_ascii=False, indent=2), encoding="utf-8")


# None = 아직 한 번도 확인되지 않음(기동 직후) — 이 상태에서는 연결 끊김 경보를 울리지 않는다.
node_connected = {"Webmail": True, "SpamBreaker": None, "MailBreaker": None, "Archiving": None}

# ── 시간대별 처리량(FR-07) — 과거 시간대는 시연용 베이스라인, 현재 시간대만 실주행 반영 ──
HOURLY_SEED_PROCESSED = [42, 38, 30, 22, 18, 15, 20, 35, 62, 78, 85, 92, 88, 95, 90, 84, 80, 76, 70, 66, 58, 52, 48, 45]
HOURLY_SEED_BLOCKED = [3, 2, 2, 1, 1, 1, 1, 3, 6, 8, 9, 12, 9, 14, 10, 8, 7, 6, 5, 5, 4, 3, 3, 3]
live_hourly_processed = {h: 0 for h in range(24)}
live_hourly_blocked = {h: 0 for h in range(24)}

# ── 메일 여정(FR-01~04) ─────────────────────────────────────────────────────
journeys: list[dict] = []  # 최신이 앞

# ── 경보(FR-08~10) ──────────────────────────────────────────────────────────
alerts: list[dict] = []
alert_cooldowns: dict = {}  # (node_id, rule_key) -> last_fired epoch

THRESHOLDS_FILE = DATA_DIR / "thresholds.json"
thresholds = {"disk": 90, "queue": 1000, "cpu": 85, "cooldown_sec": 45}
if THRESHOLDS_FILE.exists():
    thresholds.update(json.loads(THRESHOLDS_FILE.read_text(encoding="utf-8")))


def persist_thresholds():
    THRESHOLDS_FILE.write_text(json.dumps(thresholds, ensure_ascii=False, indent=2), encoding="utf-8")


WEBHOOK_FILE = DATA_DIR / "webhook.json"
webhook = {"url": "https://hooks.slack.com/services/T0CRNT/B0OPS/xxxxxxxx"}
if WEBHOOK_FILE.exists():
    webhook.update(json.loads(WEBHOOK_FILE.read_text(encoding="utf-8")))


def persist_webhook():
    WEBHOOK_FILE.write_text(json.dumps(webhook, ensure_ascii=False, indent=2), encoding="utf-8")


# ── SOS 패키지 저장 설정(M2-F9) ──────────────────────────────────────────────
SOS_SETTINGS_FILE = DATA_DIR / "sos_settings.json"
sos_settings = {"dir": "/var/lib/insight/sos-packages", "retention_days": 30, "max_gb": 50}
if SOS_SETTINGS_FILE.exists():
    sos_settings.update(json.loads(SOS_SETTINGS_FILE.read_text(encoding="utf-8")))


def persist_sos_settings():
    SOS_SETTINGS_FILE.write_text(json.dumps(sos_settings, ensure_ascii=False, indent=2), encoding="utf-8")


sos_jobs: dict = {}  # job_id -> SosJob

# ── 감사 로그(NFR-08) — append-only, 최근 500건 ─────────────────────────────
AUDIT_FILE = DATA_DIR / "audit_log.json"
audit_log: list[dict] = []
if AUDIT_FILE.exists():
    audit_log = json.loads(AUDIT_FILE.read_text(encoding="utf-8"))


def audit_append(action: str, target: str, actor: str, result: str):
    entry = {"ts": time.time(), "actor": actor, "action": action, "target": target, "result": result}
    audit_log.insert(0, entry)
    del audit_log[500:]
    AUDIT_FILE.write_text(json.dumps(audit_log, ensure_ascii=False, indent=2), encoding="utf-8")
    return entry


# ── SSE pub/sub — 3초 폴링을 대체하는 단일 실시간 스트림(/api/v1/stream) ──────
# 폴링은 뷰와 무관하게 계속 요청을 보내 서버 부하·트러블슈팅 난이도를 높이므로,
# 백그라운드 루프가 상태를 바꿀 때만 연결된 구독자에게 push 한다.
subscribers: list[asyncio.Queue] = []


def publish(event_type: str, data: dict):
    for q in list(subscribers):
        try:
            q.put_nowait({"type": event_type, "data": data})
        except asyncio.QueueFull:
            pass  # 느린 구독자는 다음 스냅샷에서 따라잡음(끊기지 않도록 드롭)
