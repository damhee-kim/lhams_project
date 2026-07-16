"""Crinity Insight — 실행 가능한 데모 백엔드 (FastAPI).

crinity_insight_admin.html 프로토타입의 6개 화면이 요구하는 API 계약을
Crinity_Insight_구현전환_보완명세.md 기준으로 실제 구현한다. 4대 물리 서버
(Webmail/MailBreaker/SpamBreaker/Archiving — 실제 메일 처리 순서)의 Edge Agent만 시뮬레이션이고
(simulate.py), 그 외 API·검증·SSE·파일 저장은 실동작이다.
"""
import asyncio
import json
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, release_adapter, security, simulate, state
from .validators import validate_sos_path

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    security.announce_admin_token()
    tasks = [
        asyncio.create_task(simulate.health_and_alert_loop()),
        asyncio.create_task(simulate.journey_spawn_loop()),
        asyncio.create_task(simulate.retention_cleanup_loop()),
        asyncio.create_task(simulate.connectivity_check_loop()),
        asyncio.create_task(simulate.privacy_retention_loop()),
    ]
    # SQLite에 저장된 이력이 없는 최초 기동일 때만 화면 시연용 여정을 미리 생성한다
    # (재시작마다 데모 데이터를 덧붙이면 실제로 쌓인 이력과 섞여 버리므로 최초 1회만).
    if not state.journeys:
        for _ in range(6):
            j = simulate.new_journey()
            state.journeys.insert(0, j)
            for h in j["hops"]:
                if h.get("reveal_at"):
                    h["reveal_at"] -= 20  # 즉시 확인 가능하도록 과거로 당김
            db.upsert_journey(j)
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(title="Crinity Insight API", lifespan=lifespan)


@app.middleware("http")
async def global_rate_limit(request: Request, call_next):
    """폴링을 SSE로 줄였어도 오작동/재시도 폭주로부터 서버를 보호하는 전역 방어선."""
    ip = security.client_ip(request)
    if not security.GLOBAL_LIMIT.check(ip):
        return JSONResponse({"detail": "요청이 너무 많습니다. 잠시 후 다시 시도하세요."}, status_code=429)
    return await call_next(request)


@app.middleware("http")
async def no_cache_static(request: Request, call_next):
    """js/css를 자주 고치는 개발 단계라 브라우저가 예전 버전을 계속 쓰는 것을 막는다.

    Cache-Control 헤더가 없으면 브라우저가 휴리스틱으로 임의 캐싱해 버려서, 서버는
    이미 고친 파일을 서빙 중인데 브라우저 탭은 새로고침해도 옛 JS를 계속 실행하는
    현상이 생긴다 — no-cache(검증 후 재사용)로 매번 서버에 변경 여부를 확인하게 한다.
    """
    response = await call_next(request)
    if request.url.path.startswith("/static/") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache"
    return response


# ── 사이트 식별(다중 고객사 배포) — LHAMS의 LHAMS_SITE_NAME/SITE_ID 관례와 동일 ──
@app.get("/api/v1/site")
def get_site():
    return {"name": state.SITE_NAME, "id": state.SITE_ID}


@app.get("/api/v1/auth/verify", dependencies=[Depends(security.require_admin_token)])
def verify_admin_token():
    """대시보드가 입력란에 붙여넣은 토큰을 즉시 검증할 때 쓰는 가벼운 엔드포인트.

    require_admin_token 의존성이 이미 401을 던지므로, 여기까지 도달했다는 것
    자체가 토큰이 맞다는 뜻이다 — 본문은 그 사실을 다시 한번 명시하는 용도.
    """
    return {"ok": True}


# ── 헬스 / 처리량 ────────────────────────────────────────────────────────────
@app.get("/api/v1/health")
def get_health():
    return {"ts": time.time(), "nodes": state.health}


@app.get("/api/v1/stats/hourly")
def get_hourly_stats():
    return simulate.hourly_snapshot()


# ── 장비 연결 설정(IP·Port) · 사용 여부 — 웹메일·메일브레이커·스팸브레이커·아카이빙 전체 ──
_HOST_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.\-]*[A-Za-z0-9])?$")


@app.get("/api/v1/settings/node-endpoints")
def get_node_endpoints():
    return {"endpoints": state.node_endpoints, "connected": state.node_connected, "enabled": state.node_enabled}


class NodeEndpointReq(BaseModel):
    host: str = ""
    port: int | None = None
    enabled: bool = True


@app.put(
    "/api/v1/settings/node-endpoints/{node_id}",
    dependencies=[Depends(security.require_admin_token), Depends(security.rate_limit_mutation)],
)
async def put_node_endpoint(node_id: str, req: NodeEndpointReq):
    if node_id not in state.CONFIGURABLE_NODES:
        raise HTTPException(400, f"설정 가능한 노드가 아닙니다: {node_id} (허용: {state.CONFIGURABLE_NODES})")
    host = req.host.strip()
    # 검증 자체를 "사용 여부"에 종속시킨다 — 사용 안 함으로 끈 노드는 형식 검증도
    # TCP 연결 확인도 건너뛰고 입력값을 그대로 저장한다(나중에 다시 켤 때 재입력 불필요).
    # 사용으로 켤 때만 IP·Port 형식이 맞아야 하고, 그 즉시 실제 연결도 확인한다.
    if req.enabled:
        if not host:
            raise HTTPException(400, "사용 설정 시 IP·Port를 입력해야 합니다.")
        if len(host) > 253 or not _HOST_RE.match(host):
            raise HTTPException(400, "호스트는 IP 또는 도메인 형식(영문·숫자·.·-)만 허용됩니다.")
        if not req.port or not (1 <= req.port <= 65535):
            raise HTTPException(400, "포트는 1~65535 사이여야 합니다.")
    state.node_endpoints[node_id] = {"host": host, "port": req.port if host else None}
    state.persist_node_endpoints()
    state.node_enabled[node_id] = req.enabled
    state.persist_node_enabled()
    state.audit_append(
        "SETTINGS_NODE_ENDPOINT",
        f"{node_id} → {host or '(미설정)'}:{req.port or '-'} · 사용={'예' if req.enabled else '아니오'}",
        "admin.kim", "SUCCESS",
    )
    # 저장 직후 사용자가 바로 결과를 볼 수 있도록 다음 5초 주기를 기다리지 않고 즉시 1회 확인
    connected = await simulate.check_node_endpoint_now(node_id) if (req.enabled and host) else None
    state.node_connected[node_id] = connected
    simulate.publish_tick()
    return {"ok": True, "node": node_id, "host": host, "port": req.port, "enabled": req.enabled, "connected": connected}


@app.get("/api/v1/stream")
async def stream(request: Request):
    """health·alerts·journeys 변경을 push하는 단일 SSE 스트림.

    3초 폴링을 이 하나의 연결로 대체한다 — 요청 수가 줄고, 연결이 끊기면
    프론트가 즉시(EventSource onerror) 알 수 있어 트러블슈팅이 쉬워진다.
    """
    ip = security.client_ip(request)
    if not security.stream_slot_acquire(ip):
        raise HTTPException(429, "이 IP에서 동시에 열 수 있는 실시간 연결 수를 초과했습니다.")

    q: asyncio.Queue = asyncio.Queue(maxsize=20)
    state.subscribers.append(q)

    async def gen():
        try:
            snapshot = {
                "health": state.health, "alerts": state.alerts[:50], "hourly": simulate.hourly_snapshot(),
                "connected": state.node_connected,
            }
            yield f"event: snapshot\ndata: {json.dumps(snapshot, ensure_ascii=False)}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"event: {ev['type']}\ndata: {json.dumps(ev['data'], ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"  # 연결 유지 + 프록시/타임아웃 방지
        finally:
            if q in state.subscribers:
                state.subscribers.remove(q)
            security.stream_slot_release(ip)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


# ── 여정(FR-01~04) ───────────────────────────────────────────────────────────
@app.get("/api/v1/journeys")
def list_journeys(keyword: str = "", status: str = "ALL", cursor: int = 0, limit: int = 50):
    now = time.time()
    out = []
    for j in state.journeys:
        serialized = simulate.serialize_journey(j, now)
        st = serialized["state"]
        if status != "ALL" and not (st == status or (status == "QUARANTINED" and st == "RELEASED")):
            continue
        if keyword:
            hay = f"{j['message_id']} {j['meta']['sender']} {j['meta']['recipient']} {j['meta']['subject']}".lower()
            if keyword.lower() not in hay:
                continue
        out.append(serialized)
    page = out[cursor:cursor + limit]
    return {"items": page, "next_cursor": cursor + limit if cursor + limit < len(out) else None, "total": len(out)}


class ReleaseReq(BaseModel):
    message_id: str


@app.post("/api/v1/nodes/release", dependencies=[Depends(security.require_admin_token), Depends(security.rate_limit_mutation)])
async def release_node(req: ReleaseReq):
    j = next((x for x in state.journeys if x["message_id"] == req.message_id), None)
    if not j:
        raise HTTPException(404, "해당 Message-ID의 여정을 찾을 수 없습니다.")
    _, top_state = simulate.resolve_journey(j, time.time())
    if top_state != "QUARANTINED":
        raise HTTPException(400, "격리 상태의 여정만 해제할 수 있습니다.")
    blocked_hop = next(h for h in j["hops"] if h["status"] == "QUARANTINED")
    # 실제 MailBreaker/SpamBreaker 연동이 확정되기 전까지의 연동 지점(seam) — release_adapter.py 참고
    ok, adapter_msg = await release_adapter.release_on_device(blocked_hop["node"], req.message_id, blocked_hop.get("detail", ""))
    if not ok:
        state.audit_append("RELEASE", req.message_id, "admin.kim", f"FAILED: {adapter_msg}")
        raise HTTPException(502, f"장비 격리 해제 실패: {adapter_msg}")
    blocked_hop["status"] = "PASS"
    blocked_hop["detail"] = (blocked_hop.get("detail") or "") + " → 관리자 해제(admin.kim)"
    j["released"] = True
    db.upsert_journey(j)
    state.audit_append("RELEASE", req.message_id, "admin.kim", f"SUCCESS: {adapter_msg}")
    state.publish("journeys_changed", {"reason": "release"})
    return {"ok": True, "message_id": req.message_id}


# ── SOS 패키지(FR-05/06) ─────────────────────────────────────────────────────
class SosCreateReq(BaseModel):
    start_time: str
    end_time: str
    nodes: list[str]


@app.post("/api/v1/nodes/sos-package", dependencies=[Depends(security.require_admin_token), Depends(security.rate_limit_mutation)])
async def create_sos_job(req: SosCreateReq):
    if not req.nodes:
        raise HTTPException(400, "수집 대상 노드를 1개 이상 선택하세요.")
    unknown = [n for n in req.nodes if n not in state.NODE_IDS]
    if unknown:
        raise HTTPException(400, f"알 수 없는 노드: {unknown}")
    disabled = [n for n in req.nodes if not state.node_enabled.get(n, True)]
    if disabled:
        raise HTTPException(400, f"사용 안 함으로 표시된 노드는 SOS 대상으로 선택할 수 없습니다: {disabled}")
    used_gb = simulate.sos_dir_usage_gb()
    if used_gb >= state.sos_settings["max_gb"]:
        raise HTTPException(
            409,
            f"저장 공간 초과 ({used_gb:.2f}GB / {state.sos_settings['max_gb']}GB) — "
            f"Zero-Impact 정책에 따라 신규 SOS 수집이 거부되었습니다.",
        )
    job_id = f"SOS-{time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
    job = simulate.SosJob(job_id, req.nodes, req.start_time, req.end_time)
    state.sos_jobs[job_id] = job
    asyncio.create_task(simulate.run_sos_job(job))
    state.audit_append("SOS_PACKAGE_START", job_id, "admin.kim", "STARTED")
    return {"job_id": job_id}


@app.get("/api/v1/nodes/sos-package/{job_id}/events")
async def sos_events(job_id: str):
    job = state.sos_jobs.get(job_id)
    if not job:
        raise HTTPException(404, "job_id를 찾을 수 없습니다.")

    async def gen():
        while True:
            per_node = {}
            for n, pn in job.per_node.items():
                phase = pn["phase"]
                if phase == 99:
                    label = "완료"
                elif phase == -2:
                    label = "실패"
                elif phase < 0:
                    label = "대기"
                else:
                    label = simulate.SOS_PHASES[phase]
                per_node[n] = {"phase": phase, "label": label, "state": pn["state"]}
            payload = {"job_id": job_id, "state": job.state, "per_node": per_node}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            if job.state in ("DONE", "PARTIAL_DONE", "FAILED"):
                done_payload = {
                    "job_id": job_id, "state": job.state,
                    "manifest": job.manifest_name, "sha256": job.sha256, "size_bytes": job.size_bytes,
                }
                yield f"event: done\ndata: {json.dumps(done_payload, ensure_ascii=False)}\n\n"
                break
            await asyncio.sleep(0.4)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/v1/nodes/sos-package/{job_id}/download")
def sos_download(job_id: str):
    job = state.sos_jobs.get(job_id)
    if not job or not job.manifest_path:
        raise HTTPException(404, "다운로드 가능한 패키지가 없습니다.")
    return FileResponse(job.manifest_path, filename=job.manifest_name, media_type="application/gzip")


# ── SOS 저장 경로 설정(M2-F9) ────────────────────────────────────────────────
@app.get("/api/v1/settings/sos-storage")
def get_sos_storage():
    used_gb = simulate.sos_dir_usage_gb()
    return {**state.sos_settings, "used_gb": round(used_gb, 3)}


class SosValidateReq(BaseModel):
    dir: str


@app.post("/api/v1/settings/sos-storage/validate", dependencies=[Depends(security.require_admin_token), Depends(security.rate_limit_mutation)])
def validate_sos_storage(req: SosValidateReq):
    ok, msg = validate_sos_path(req.dir)
    if not ok:
        return {"ok": False, "message": msg}
    real_path = state.sandbox_path(msg)
    try:
        real_path.mkdir(parents=True, exist_ok=True)
        import shutil
        _total, _used, free = shutil.disk_usage(real_path)
        free_gb = free / (1024 ** 3)
        return {"ok": True, "message": f"{msg} · 쓰기 가능 확인 · 파티션 여유 {free_gb:.1f}GB"}
    except OSError as e:
        return {"ok": False, "message": f"서버 디렉토리 생성/쓰기 실패: {e}"}


class SosSettingsReq(BaseModel):
    dir: str
    retention_days: int
    max_gb: int


@app.put("/api/v1/settings/sos-storage", dependencies=[Depends(security.require_admin_token), Depends(security.rate_limit_mutation)])
def put_sos_storage(req: SosSettingsReq):
    ok, msg = validate_sos_path(req.dir)
    if not ok:
        raise HTTPException(400, msg)
    if not (7 <= req.retention_days <= 180):
        raise HTTPException(400, "보관 기간은 7~180일 사이여야 합니다.")
    if not (10 <= req.max_gb <= 500):
        raise HTTPException(400, "용량 상한은 10~500GB 사이여야 합니다.")
    real_path = state.sandbox_path(msg)
    try:
        real_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise HTTPException(400, f"디렉토리 생성 실패: {e}")
    state.sos_settings = {"dir": msg, "retention_days": req.retention_days, "max_gb": req.max_gb}
    state.persist_sos_settings()
    state.audit_append("SETTINGS_SOS_STORAGE", msg, "admin.kim", "SUCCESS")
    return {"ok": True, **state.sos_settings}


# ── 사전 경보(FR-08~10) ───────────────────────────────────────────────────────
@app.get("/api/v1/alerts")
def get_alerts(limit: int = 50):
    return {"items": state.alerts[:limit]}


@app.get("/api/v1/alerts/thresholds")
def get_thresholds():
    return state.thresholds


class ThresholdsReq(BaseModel):
    disk: int
    queue: int
    cpu: int


@app.put("/api/v1/alerts/thresholds", dependencies=[Depends(security.require_admin_token), Depends(security.rate_limit_mutation)])
def put_thresholds(req: ThresholdsReq):
    if not (50 <= req.disk <= 99 and 100 <= req.queue <= 5000 and 50 <= req.cpu <= 99):
        raise HTTPException(400, "임계치 범위를 벗어났습니다.")
    state.thresholds.update({"disk": req.disk, "queue": req.queue, "cpu": req.cpu})
    state.persist_thresholds()
    state.audit_append("THRESHOLDS_UPDATE", json.dumps(state.thresholds, ensure_ascii=False), "admin.kim", "SUCCESS")
    return state.thresholds


@app.get("/api/v1/settings/webhook")
def get_webhook():
    return state.webhook


class WebhookReq(BaseModel):
    url: str


@app.put("/api/v1/settings/webhook", dependencies=[Depends(security.require_admin_token), Depends(security.rate_limit_mutation)])
def put_webhook(req: WebhookReq):
    state.webhook["url"] = req.url
    state.persist_webhook()
    state.audit_append("SETTINGS_WEBHOOK", req.url, "admin.kim", "SUCCESS")
    return state.webhook


@app.post("/api/v1/alerts/test-webhook", dependencies=[Depends(security.require_admin_token), Depends(security.rate_limit_mutation)])
def test_webhook():
    ch = "Slack #ops-alert" if state.webhook.get("url") else "대시보드(URL 미설정)"
    simulate._push_alert("MailBreaker", "INFO", "[테스트] Webhook 연동 확인 메시지", ch)
    state.audit_append("WEBHOOK_TEST", state.webhook.get("url") or "(미설정)", "admin.kim", "SUCCESS")
    state.publish("tick", {"health": state.health, "alerts": state.alerts[:50], "hourly": simulate.hourly_snapshot()})
    return {"ok": True, "channel": ch}


# ── 개인정보 처리 설정(리스크 체크리스트 "개인정보 처리 검토") ───────────────────
@app.get("/api/v1/settings/privacy")
def get_privacy_settings():
    return state.privacy_settings


class PrivacySettingsReq(BaseModel):
    journey_retention_days: int
    mask_subject: bool


@app.put("/api/v1/settings/privacy", dependencies=[Depends(security.require_admin_token), Depends(security.rate_limit_mutation)])
def put_privacy_settings(req: PrivacySettingsReq):
    if not (1 <= req.journey_retention_days <= 3650):
        raise HTTPException(400, "보관 기간은 1~3650일 사이여야 합니다.")
    state.privacy_settings = {"journey_retention_days": req.journey_retention_days, "mask_subject": req.mask_subject}
    state.persist_privacy_settings()
    state.audit_append("SETTINGS_PRIVACY", json.dumps(state.privacy_settings, ensure_ascii=False), "admin.kim", "SUCCESS")
    state.publish("journeys_changed", {"reason": "privacy_settings"})
    return state.privacy_settings


# ── 감사 로그(NFR-08) ────────────────────────────────────────────────────────
@app.get("/api/v1/audit")
def get_audit(limit: int = 30):
    return {"items": state.audit_log[:limit]}


# ── 정적 프론트엔드 서빙 ─────────────────────────────────────────────────────
@app.get("/")
def index():
    # .jsp 확장자는 Python mimetypes에 없어 media_type을 명시하지 않으면
    # application/octet-stream으로 내려가 브라우저가 다운로드를 시도한다 — 명시 필수.
    return FileResponse(FRONTEND_DIR / "index.jsp", media_type="text/html; charset=utf-8")


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


if __name__ == "__main__":
    import uvicorn

    # 기본값은 localhost 전용 — 같은 네트워크의 다른 호스트에서 접근하려면
    # 의도적으로 INSIGHT_HOST=0.0.0.0 을 지정해야 한다(그 경우에도 관리자 토큰은 필요).
    host = os.environ.get("INSIGHT_HOST", "127.0.0.1")
    port = int(os.environ.get("INSIGHT_PORT", "8100"))
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
