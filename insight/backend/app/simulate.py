"""Edge Agent/실장비 이벤트 생성 시뮬레이션.

실제 배포 시 이 모듈 전체가 4대 물리 서버의 Edge Agent(§2.1) + 그 이벤트를
수신하는 FastAPI ingest 로 대체된다. 그 외 이 파일 밖의 코드(검증, 저장,
SSE, 파일 I/O)는 실제 로직이다.
"""
import asyncio
import hashlib
import io
import os
import random
import tarfile
import time
import uuid
from datetime import datetime

from . import state

REVEAL_SCALE = 3.0  # 데모 관측성을 위해 노드 통과 반영을 몇 배 늘려서 화면에서 진행을 볼 수 있게 함

MAIL_TEMPLATES = [
    ("client@external.com", "user@crinity.com", "프로젝트 산출물 전달 건"),
    ("partner@vendor.co.kr", "sales@crinity.com", "7월 정기 견적서 송부"),
    ("promo@unknown-shop.biz", "user@crinity.com", "(광고) 최대 90% 특가 이벤트"),
    ("hr@crinity.com", "all@crinity.com", "[인사공지] 하반기 워크샵 일정안내"),
    ("dev@opensource.org", "cto@crinity.com", "Re: 라이선스 검토 요청"),
    ("finance@crinity.com", "bank@partner.com", "6월 결산 자료 첨부"),
    ("support@crinity.com", "vip@customer.co.kr", "장애 조치 완료 보고"),
    ("unknown@phish-test.io", "user@crinity.com", "[긴급] 계정 비밀번호 만료 안내"),
    ("newsletter@marketing.kr", "user@crinity.com", "이번주 뉴스레터"),
]

MAILBREAKER_BLOCK_REASONS = [
    "DLP 룰 매칭 → 주민등록번호 패턴 검출",
    "첨부파일 정책 위반 → 암호화되지 않은 .xlsx 외부 발송",
]
SPAM_BLOCK_REASONS = [
    "Spam Score: 9.8 → RBL 등재 발신 IP",
    "피싱 URL 패턴 탐지 → 발신 도메인 평판 하위 1%",
]
PASS_DETAIL = {
    "SpamBreaker": lambda: f"Spam Score: {round(random.uniform(0, 1.2), 1)}",
    "MailBreaker": lambda: "DLP 정책 통과",
    "Archiving": lambda: "WORM 스토리지 보관 완료",
}


def _plan_outcome():
    r = random.random()
    if r < 0.45:
        return "ARCHIVED", None
    if r < 0.65:
        return "QUARANTINED", "MailBreaker"
    if r < 0.85:
        return "QUARANTINED", "SpamBreaker"
    if r < 0.95:
        return "DELAYED", "SpamBreaker"
    return "ARCHIVED", None


def new_journey() -> dict:
    sender, recipient, subject = random.choice(MAIL_TEMPLATES)
    now = time.time()
    mid = f"<{time.strftime('%Y%m%d.%H%M%S', time.localtime(now))}.{uuid.uuid4().hex[:6]}@crinity.com>"
    outcome, block_node = _plan_outcome()
    block_idx = state.NODE_IDS.index(block_node) if block_node else None

    hops = []
    cumulative = 0.4
    for idx, nid in enumerate(state.NODE_IDS):
        if block_idx is not None and idx > block_idx:
            hops.append({"node": nid, "status": "PENDING", "reveal_at": None})
            continue
        if nid == "Webmail":
            status, detail, latency = "PASS", "SMTP 250 OK", 0
        elif idx == block_idx and outcome == "QUARANTINED" and nid == "MailBreaker":
            status, detail, latency = "QUARANTINED", random.choice(MAILBREAKER_BLOCK_REASONS), random.randint(1500, 2500)
        elif idx == block_idx and outcome == "QUARANTINED" and nid == "SpamBreaker":
            status, detail, latency = "QUARANTINED", random.choice(SPAM_BLOCK_REASONS), random.randint(1500, 2500)
        elif idx == block_idx and outcome == "DELAYED" and nid == "SpamBreaker":
            status, detail, latency = "DELAYED", "허니팟 탐지 → 다음 노드 미더미 재전송 지연 (대기 1,024건)", random.randint(1500, 2500)
        else:
            status, detail, latency = "PASS", PASS_DETAIL.get(nid, lambda: "정상 처리")(), random.randint(500, 1500)
        cumulative += (latency / 1000.0) * REVEAL_SCALE if latency else 0.6
        hops.append({
            "node": nid, "status": status, "detail": detail, "latency_ms": latency,
            "reveal_at": now + cumulative,
        })

    return {
        "message_id": mid,
        "created_at": now,
        "meta": {
            "sender": sender, "recipient": recipient, "subject": subject,
            "received_at": datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M:%S"),
        },
        "hops": hops,
        "released": False,
    }


def resolve_journey(j: dict, now: float):
    """reveal_at 기준으로 지금 시점에 '도달'한 hop만 노출하고 journey 상태를 계산."""
    resolved = []
    for h in j["hops"]:
        if h["status"] == "PENDING" and h.get("reveal_at") is None:
            resolved.append({"node": h["node"], "status": "PENDING"})
            break
        if h["reveal_at"] is not None and now >= h["reveal_at"]:
            resolved.append({
                "node": h["node"], "status": h["status"],
                "time": datetime.fromtimestamp(h["reveal_at"]).strftime("%H:%M:%S"),
                "latency": h["latency_ms"], "detail": h["detail"],
            })
            if h["status"] in ("QUARANTINED", "DELAYED"):
                break
        else:
            resolved.append({"node": h["node"], "status": "PENDING"})
            break

    if j.get("released"):
        top_state = "RELEASED"
    elif not resolved:
        top_state = "PENDING"
    else:
        last = resolved[-1]
        if last["status"] in ("QUARANTINED", "DELAYED"):
            top_state = last["status"]
        elif len(resolved) == len(state.NODE_IDS) and last["status"] == "PASS":
            top_state = "ARCHIVED"
        else:
            top_state = "PENDING"
    return resolved, top_state


def serialize_journey(j: dict, now: float) -> dict:
    resolved, top_state = resolve_journey(j, now)
    return {
        "message_id": j["message_id"],
        "meta": j["meta"],
        "state": top_state,
        "nodes": resolved,
    }


def hourly_snapshot():
    now_hour = datetime.now().hour
    processed = list(state.HOURLY_SEED_PROCESSED)
    blocked = list(state.HOURLY_SEED_BLOCKED)
    processed[now_hour] = max(processed[now_hour], state.live_hourly_processed[now_hour])
    blocked[now_hour] = max(blocked[now_hour], state.live_hourly_blocked[now_hour])
    return {"hour": now_hour, "processed": processed, "blocked": blocked}


def publish_tick():
    """3초 폴링 대신 SSE로 push하는 현재 스냅샷 — /api/v1/stream 의 'tick'/'snapshot' 이벤트."""
    state.publish("tick", {
        "health": state.health, "alerts": state.alerts[:50], "hourly": hourly_snapshot(),
        "connected": state.node_connected,
    })


async def health_and_alert_loop():
    while True:
        await asyncio.sleep(3)
        for nid, h in state.health.items():
            # 연결이 끊긴 설정 가능 노드는 값을 얼려서(마지막 값 유지) "실데이터 없음"을 정직하게 표현
            if nid in state.CONFIGURABLE_NODES and not state.node_connected.get(nid):
                continue
            h["cpu"] = min(99, max(5, h["cpu"] + random.randint(-3, 3)))
            h["mem"] = min(99, max(20, h["mem"] + random.randint(-2, 2)))
            h["disk"] = min(99, max(20, h["disk"] + random.choice([-1, 0, 0, 0, 1])))
            h["queue"] = max(0, h["queue"] + random.randint(-18, 22))
        _evaluate_alert_rules()
        publish_tick()


async def _check_tcp(host: str, port: int, timeout: float = 2.0) -> bool:
    if not host or not port:
        return False
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


async def check_node_endpoint_now(node_id: str) -> bool:
    """설정 저장 직후 등, 다음 주기를 기다리지 않고 즉시 1회 확인할 때 사용."""
    ep = state.node_endpoints[node_id]
    ok = await _check_tcp(ep["host"], ep["port"])
    state.node_connected[node_id] = ok
    return ok


async def connectivity_check_loop():
    """스팸브레이커·메일브레이커·아카이빙에 실제 TCP 연결을 시도해 통신 여부를 판정한다.

    관리자가 대시보드에서 입력한 IP·Port를 그대로 사용하므로, 실제 장비를
    가리키면 진짜 연결 성공/실패가 그대로 반영된다(물리 장비가 없는 이 데모
    환경에서는 대개 실패하며, 그 사실 자체를 정직하게 보여주는 것이 목적).
    """
    while True:
        changed = False
        for nid in state.CONFIGURABLE_NODES:
            ep = state.node_endpoints[nid]
            was = state.node_connected.get(nid)
            now_ok = await _check_tcp(ep["host"], ep["port"])
            state.node_connected[nid] = now_ok
            if was is not None and now_ok != was:
                changed = True
                if now_ok:
                    _push_alert(nid, "INFO", f"{ep['host']}:{ep['port']} 연결 복구됨", "대시보드")
                else:
                    _push_alert(nid, "CRITICAL", f"{ep['host']}:{ep['port']} 연결 끊김 — 응답 없음(Timeout/Connection refused)", "대시보드")
        if changed:
            publish_tick()
        await asyncio.sleep(5)


def _push_alert(node_id, sev, msg, ch=None):
    now = time.time()
    entry = {
        "t": datetime.fromtimestamp(now).strftime("%H:%M:%S"),
        "ts": now, "node": node_id, "sev": sev, "msg": msg,
        "ch": ch or (state.webhook.get("url") and "Slack #ops-alert" or "대시보드"),
    }
    state.alerts.insert(0, entry)
    del state.alerts[300:]
    return entry


def _evaluate_alert_rules():
    now = time.time()
    th = state.thresholds
    cooldown = th.get("cooldown_sec", 45)
    for nid, h in state.health.items():
        if nid in state.CONFIGURABLE_NODES and not state.node_connected.get(nid):
            continue  # 연결 끊긴 노드는 이미 별도의 연결 끊김 경보로 다루므로 임계치 평가는 건너뜀
        checks = [
            ("disk", h["disk"], th["disk"], "CRITICAL", f"디스크 사용률 {h['disk']}% → 임계치({th['disk']}%) 초과"),
            ("queue", h["queue"], th["queue"], "WARNING", f"메일 큐 {h['queue']:,}건 대기 → 임계치({th['queue']:,}건) 초과"),
            ("cpu", h["cpu"], th["cpu"], "WARNING", f"CPU 사용률 {h['cpu']}% → 임계치({th['cpu']}%) 초과"),
        ]
        for key, val, threshold, sev, msg in checks:
            ck = f"{nid}:{key}"
            if val >= threshold:
                last = state.alert_cooldowns.get(ck, 0)
                if now - last >= cooldown:
                    state.alert_cooldowns[ck] = now
                    _push_alert(nid, sev, msg)
            else:
                state.alert_cooldowns.pop(ck, None)


async def journey_spawn_loop():
    while True:
        await asyncio.sleep(random.uniform(8, 16))
        j = new_journey()
        state.journeys.insert(0, j)
        del state.journeys[200:]
        hour = datetime.fromtimestamp(j["created_at"]).hour
        state.live_hourly_processed[hour] += 1
        # 최종 상태는 아직 미확정(순차 공개 중)이므로 대략적인 계획을 기준으로 카운트
        blocked_hint = any(h["status"] in ("QUARANTINED", "DELAYED") for h in j["hops"] if h.get("status") != "PENDING")
        if blocked_hint:
            state.live_hourly_blocked[hour] += 1
        # 폴링 대신 이벤트로 알림 — 여정 화면이 열려 있을 때만 프론트가 재조회한다
        state.publish("journeys_changed", {"reason": "new_journey"})


# ── SOS 패키지 ────────────────────────────────────────────────────────────
SOS_PHASES = ["수집 명령 수신", "로그 수집 (/var/log/*)", "top·df 덤프", "압축 및 전송"]


class SosJob:
    def __init__(self, job_id, nodes, start_time, end_time):
        self.job_id = job_id
        self.nodes = nodes
        self.start_time = start_time
        self.end_time = end_time
        self.per_node = {
            n: {"phase": -1, "state": "PENDING", "fail_at": random.randint(1, 3) if random.random() < 0.06 else None}
            for n in nodes
        }
        self.state = "DISPATCHED"
        self.created_at = time.time()
        self.manifest_name = None
        self.manifest_path = None
        self.sha256 = None
        self.size_bytes = None


def _fake_node_files(nid, start_time, end_time):
    host_label = state.display_host(nid)
    lines_mail = [
        f"{time.strftime('%b %d %H:%M:%S')} {host_label} postfix/smtpd[{random.randint(1000,9999)}]: "
        f"connect from mail-gw.crinity.com[{host_label}]"
        for _ in range(12)
    ]
    lines_top = [
        "top - load average: 0.42, 0.38, 0.31",
        f"%Cpu(s): {random.uniform(3,40):.1f} us,  {random.uniform(1,10):.1f} sy",
        f"MiB Mem : total, {random.uniform(20,70):.1f}% used",
    ]
    lines_df = [
        "Filesystem      Size  Used Avail Use% Mounted on",
        f"/dev/mapper/root 200G  {random.randint(60,190)}G   {random.randint(5,140)}G  {random.randint(30,95)}% /",
    ]
    return {
        f"maillog.{start_time}_{end_time}.log": "\n".join(lines_mail).encode("utf-8"),
        f"top_{nid.lower()}.txt": "\n".join(lines_top).encode("utf-8"),
        f"df_{nid.lower()}.txt": "\n".join(lines_df).encode("utf-8"),
    }


def build_manifest(job: SosJob, done_nodes: list[str]):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        readme = (
            f"# Crinity Insight SOS Package\n"
            f"# job_id: {job.job_id}\n"
            f"# range: {job.start_time} ~ {job.end_time}\n"
            f"# nodes: {', '.join(done_nodes)}\n"
        ).encode("utf-8")
        info = tarfile.TarInfo(name="README.txt")
        info.size = len(readme)
        tar.addfile(info, io.BytesIO(readme))
        for nid in done_nodes:
            for fname, data in _fake_node_files(nid, job.start_time, job.end_time).items():
                info = tarfile.TarInfo(name=f"{nid}/{fname}")
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
    raw = buf.getvalue()
    sha = hashlib.sha256(raw).hexdigest()
    fn = f"sos_package_{time.strftime('%Y%m%d_%H%M%S', time.localtime(job.created_at))}.tar.gz"
    dest_dir = state.sandbox_path(state.sos_settings["dir"])
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / fn
    dest.write_bytes(raw)
    job.manifest_name = fn
    job.manifest_path = str(dest)
    job.sha256 = sha
    job.size_bytes = len(raw)


async def run_sos_job(job: SosJob):
    while True:
        await asyncio.sleep(0.6)
        all_done = True
        for n in job.nodes:
            pn = job.per_node[n]
            if pn["phase"] in (99, -2):
                continue
            if pn["fail_at"] is not None and pn["phase"] >= pn["fail_at"]:
                pn["phase"] = -2
                pn["state"] = "FAILED"
                continue
            if random.random() > 0.35:
                pn["phase"] += 1
                if pn["phase"] >= len(SOS_PHASES):
                    pn["phase"] = 99
                    pn["state"] = "DONE"
            if pn["phase"] not in (99, -2):
                all_done = False
        if all_done:
            break

    done_nodes = [n for n in job.nodes if job.per_node[n]["state"] == "DONE"]
    if not done_nodes:
        job.state = "FAILED"
    elif len(done_nodes) < len(job.nodes):
        job.state = "PARTIAL_DONE"
    else:
        job.state = "DONE"
    if done_nodes:
        build_manifest(job, done_nodes)
    state.audit_append("SOS_PACKAGE", job.job_id, "admin.kim", job.state)


def sos_dir_usage_gb() -> float:
    d = state.sandbox_path(state.sos_settings["dir"])
    if not d.exists():
        return 0.0
    total = 0
    for root, _dirs, files in os.walk(d):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total / (1024 ** 3)


async def retention_cleanup_loop():
    """보관 기간(retention_days) 초과 SOS 패키지 자동 폐기 — 60초 주기(데모 축약)."""
    while True:
        await asyncio.sleep(60)
        d = state.sandbox_path(state.sos_settings["dir"])
        if not d.exists():
            continue
        max_age = state.sos_settings["retention_days"] * 86400
        now = time.time()
        for f in d.glob("*.tar.gz"):
            try:
                if now - f.stat().st_mtime > max_age:
                    f.unlink()
                    state.audit_append("SOS_RETENTION_PURGE", f.name, "system", "DELETED")
            except OSError:
                pass
