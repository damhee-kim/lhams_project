"""Crinity Insight — 상태 저장소 (SQLite 영속화 + 인메모리 작업 캐시).

실제 Webmail/SpamBreaker/MailBreaker/Archiving 물리 서버가 없는 개발 환경이므로
Edge Agent가 보낼 이벤트를 이 프로세스 안에서 생성한다(simulate.py). 그 외
API 계약·검증 규칙·파일 I/O·SSE 스트리밍·DB 저장은 실제 동작이다.

영속화 전략: journeys/alerts/audit_log/settings는 db.py(SQLite)에 실제로
저장되고, 이 모듈은 그 값을 인메모리 리스트/딕셔너리에 캐시해 기존 계산 로직
(여정 조회·필터링·경보 평가 등)이 빠르게 동작하도록 한다. 변경이 생기면
"인메모리 갱신 + DB write-through"를 항상 함께 한다 — 재시작해도 데이터가
남는다(고객사 DB를 새로 들여오지 않고, 추가 포트도 열지 않는 SQLite 한 파일).
"""
import asyncio
import os
import time
from pathlib import Path

from . import db

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
# 실제 RHEL 배포 시 절대경로(/var/lib/insight/...)가 되는 SOS 저장 경로를
# 이 데모에서는 로컬 디스크 하위 샌드박스에 매핑해 mkdir·statvfs·용량 계산을
# 실제로 수행한다 (Windows 개발 환경에서도 동작하도록).
SANDBOX_ROOT = DATA_DIR / "sandbox_root"
SANDBOX_ROOT.mkdir(parents=True, exist_ok=True)

db.init_schema()

# ── 다중 고객사 배포 식별 — LHAMS의 LHAMS_SITE_NAME/SITE_ID 관례와 동일 패턴 ──
SITE_NAME = os.environ.get("INSIGHT_SITE_NAME", "").strip() or "미지정 사이트"
SITE_ID = os.environ.get("INSIGHT_SITE_ID", "").strip() or "default"

# 노드 식별자·표시명·색상만 고정값이다. IP·Port는 아래 node_endpoints에서
# 관리자가 직접 입력하며, 하드코딩된 주소를 절대 기본값으로 두지 않는다.
NODES = [
    {"id": "Webmail", "name": "웹메일", "hex": "#4C8DFF"},
    {"id": "MailBreaker", "name": "메일브레이커", "hex": "#FF5D5D"},
    {"id": "SpamBreaker", "name": "스팸브레이커", "hex": "#F7B32B"},
    {"id": "Archiving", "name": "아카이빙", "hex": "#35C98E"},
]
NODE_IDS = [n["id"] for n in NODES]

# 4개 노드(웹메일 포함) 전부 고객사마다 실제 IP·Port가 다르고, 고객사에 따라
# 아예 도입하지 않은 솔루션도 있다 — 그래서 4개 모두 (1) IP·Port 직접 입력,
# (2) 사용 여부(node_enabled) 토글을 동일하게 지원한다. 이름은 유지하되
# 더 이상 웹메일을 특별 취급하지 않는다.
CONFIGURABLE_NODES = list(NODE_IDS)


def node_by_id(nid):
    return next((n for n in NODES if n["id"] == nid), None)


def display_host(nid: str) -> str:
    """카드·SOS 화면 등에서 노드 주소를 표시할 때 쓰는 단일 소스."""
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
    "MailBreaker": {"cpu": 37, "mem": 70, "disk": 91, "queue": 88},
    "SpamBreaker": {"cpu": 41, "mem": 55, "disk": 68, "queue": 1024},
    "Archiving": {"cpu": 12, "mem": 48, "disk": 83, "queue": 5},
}

# ── 장비 연결 설정(IP·Port) — 웹메일·스팸브레이커·메일브레이커·아카이빙 전체 ──
# 하드코딩된 IP를 기본값으로 두지 않는다 — host/port는 빈 값으로 시작하며,
# 관리자가 대시보드에서 직접 입력해야 연결 확인(TCP)이 시작된다.
node_endpoints = db.get_setting("node_endpoints", {nid: {"host": "", "port": None} for nid in NODE_IDS})
for _nid in NODE_IDS:
    node_endpoints.setdefault(_nid, {"host": "", "port": None})  # 이전 버전 DB(웹메일 키 없음) 마이그레이션


def persist_node_endpoints():
    db.set_setting("node_endpoints", node_endpoints)


# ── 노드 사용 여부 — 고객사에 따라 4개 솔루션 중 일부만 도입했을 수 있다 ──────
# 사용 안 함으로 표시된 노드는 관제 현황 카드·SOS 대상 목록·경보 평가·연결 확인
# 대상에서 전부 제외되고, 신규 메일 여정도 그 노드를 거치지 않는 것으로 생성된다.
node_enabled = db.get_setting("node_enabled", {nid: True for nid in NODE_IDS})
for _nid in NODE_IDS:
    node_enabled.setdefault(_nid, True)


def persist_node_enabled():
    db.set_setting("node_enabled", node_enabled)


def enabled_node_ids() -> list:
    """정의 순서(Webmail→MailBreaker→SpamBreaker→Archiving, 실제 메일 처리 순서)를
    유지한 채 사용 중인 노드만 반환한다 — 4개 전부 사용한다고 가정하지 않고,
    도입하지 않은 솔루션은 빠진 채로 나머지 순서 그대로 파이프라인을 구성한다."""
    return [n for n in NODE_IDS if node_enabled.get(n, True)]


# None = 아직 한 번도 확인되지 않음(기동 직후) — 이 상태에서는 연결 끊김 경보를 울리지 않는다.
node_connected = {nid: None for nid in NODE_IDS}

# ── 시간대별 처리량(FR-07) — 과거 시간대는 시연용 베이스라인, 현재 시간대만 실주행 반영 ──
HOURLY_SEED_PROCESSED = [42, 38, 30, 22, 18, 15, 20, 35, 62, 78, 85, 92, 88, 95, 90, 84, 80, 76, 70, 66, 58, 52, 48, 45]
HOURLY_SEED_BLOCKED = [3, 2, 2, 1, 1, 1, 1, 3, 6, 8, 9, 12, 9, 14, 10, 8, 7, 6, 5, 5, 4, 3, 3, 3]
live_hourly_processed = {h: 0 for h in range(24)}
live_hourly_blocked = {h: 0 for h in range(24)}

# ── 메일 여정(FR-01~04) — SQLite에서 재기동 시 복원(최신 500건), 신규/변경은 write-through ──
journeys: list = db.load_journeys(limit=500)  # 최신이 앞


def save_journey(j: dict):
    """신규 여정 생성 또는 격리 해제 등 변경 시 호출 — 인메모리는 호출자가 이미 갱신했다고 가정."""
    db.upsert_journey(j)


# ── 개인정보 처리 정책(리스크 체크리스트 "개인정보 처리 검토") ───────────────
# 메일 제목·주소를 담은 여정은 무기한 보관하지 않는다 — 기본 90일 보관 후 자동
# 폐기(고객사 컴플라이언스에 맞춰 조정 가능), 제목 마스킹은 고객사 정책에 따라
# 기본값을 끈 채로 두고 필요 시 켠다.
privacy_settings = db.get_setting("privacy_settings", {"journey_retention_days": 90, "mask_subject": False})


def persist_privacy_settings():
    db.set_setting("privacy_settings", privacy_settings)


def mask_subject(subject: str) -> str:
    if not privacy_settings.get("mask_subject"):
        return subject
    if len(subject) <= 4:
        return subject[:1] + "*" * (len(subject) - 1)
    return subject[:2] + "*" * (len(subject) - 4) + subject[-2:]


# ── 경보(FR-08~10) ──────────────────────────────────────────────────────────
alerts: list = db.load_alerts(limit=300)
alert_cooldowns: dict = {}  # (node_id, rule_key) -> last_fired epoch

thresholds = db.get_setting("thresholds", {"disk": 90, "queue": 1000, "cpu": 85, "cooldown_sec": 45})


def persist_thresholds():
    db.set_setting("thresholds", thresholds)


webhook = db.get_setting("webhook", {"url": ""})


def persist_webhook():
    db.set_setting("webhook", webhook)


# ── SOS 패키지 저장 설정(M2-F9) ──────────────────────────────────────────────
sos_settings = db.get_setting("sos_settings", {"dir": "/var/lib/insight/sos-packages", "retention_days": 30, "max_gb": 50})


def persist_sos_settings():
    db.set_setting("sos_settings", sos_settings)


sos_jobs: dict = {}  # job_id -> SosJob (진행 중인 잡만 다루므로 인메모리로 충분, 완료 결과는 audit_log에 남음)

# ── 감사 로그(NFR-08) — append-only, SQLite에 전량 보관 + 최근 500건 인메모리 캐시 ──
audit_log: list = db.load_audit(limit=500)


def audit_append(action: str, target: str, actor: str, result: str):
    entry = {"ts": time.time(), "actor": actor, "action": action, "target": target, "result": result}
    audit_log.insert(0, entry)
    del audit_log[500:]
    db.insert_audit(entry)
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
