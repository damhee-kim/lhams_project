#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LHAMS Watchdog Control Tower
============================
- 파일 생성/수정/삭제/이동을 실시간 감지 (watchdog/inotify)
- auditd(ausearch) 연동: "어떤 사용자(auid)가, 어떤 프로세스로" 파일을
  교체/삭제했는지 실제 행위자 추적 (파일 소유자와 별개)
- ClamAV(clamdscan) 연동: 생성/수정 파일 즉시 악성코드 검사 및 격리
- 프론트엔드 대시보드용 JSON(lhams_audit.json) 실시간 적재 (최신 200건)
- TimedRotatingFileHandler: 자정마다 텍스트 감사 로그 일별 로테이션
- data/config.json 기반 감시 경로 다중 등록/삭제/on-off + 무시 규칙 편집을
  Flask 관리 API(/api/...)로 실행 중에 반영 (재시작 불필요)
- data/quarantine/_meta.json: 격리 파일의 원본 경로/시각/사유 기록 →
  관리자 UI에서 복원·영구삭제 가능
"""

import os
import re
import time
import json
import shutil
import logging
import threading
import subprocess
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

from flask import Flask, jsonify, request
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# pwd는 POSIX 전용 — RHEL 운영 환경 기준이며, 로컬 데모(Windows)에서는
# 사용자명 조회 없이 owner/actor="unknown"으로 성능 저하 없이 동작한다.
try:
    import pwd
except ImportError:
    pwd = None

# ──────────────────────────── 설정 ────────────────────────────
WATCH_DIR       = os.environ.get("LHAMS_WATCH_DIR",  "/mail/test_monitor")
JSON_LOG_FILE   = os.environ.get("LHAMS_JSON_LOG",   "/mail/lhams_project/frontend/public/lhams_audit.json")
TEXT_LOG_FILE   = os.environ.get("LHAMS_TEXT_LOG",   "/mail/lhams_project/data/logs/lhams_audit.log")
QUARANTINE_DIR  = os.environ.get("LHAMS_QUARANTINE", "/mail/lhams_project/data/quarantine")
CONFIG_FILE     = os.environ.get("LHAMS_CONFIG",     "/mail/lhams_project/data/config.json")
CHECKLIST_FILE  = os.environ.get("LHAMS_CHECKLIST",  "/mail/lhams_project/data/checklist.json")
ADMIN_AUDIT_FILE = os.environ.get("LHAMS_ADMIN_AUDIT", "/mail/lhams_project/data/admin_audit.json")
API_PORT        = int(os.environ.get("LHAMS_API_PORT", "8787"))
AUDIT_KEY       = "lhams_audit"      # auditd 규칙 태그 (-k)
MAX_JSON_EVENTS = 200                # 대시보드 유지 건수
MAX_ADMIN_AUDIT_EVENTS = 500         # 관리자 변경 이력 유지 건수
DEFAULT_IGNORE_SUFFIX = [".swp", ".swx", ".swpx", ".tmp", "~", ".part"]

QUARANTINE_META_FILE = os.path.join(QUARANTINE_DIR, "_meta.json")

# 프로젝트 구축 단계 체크리스트 — 신규 배포 서버마다 이 순서대로 진행
DEFAULT_CHECKLIST = [
    {"key": "env_setup",      "label": "환경 구성",
     "desc": "scripts/setup_env.sh 실행 — 커널 튜닝(inotify), 패키지, auditd, ClamAV 설치"},
    {"key": "systemd",        "label": "systemd 서비스 등록",
     "desc": "scripts/install_services.sh 실행 — lhams-watchdog / lhams-realtime 자가 치유 등록"},
    {"key": "auditd_rules",   "label": "auditd 규칙 적용",
     "desc": "scripts/auditd_rules.rules 반영 후 auditctl -l 로 확인"},
    {"key": "watchdog_up",    "label": "Watchdog 에이전트 기동 확인",
     "desc": "systemctl status lhams-watchdog, /api/config 정상 응답 확인"},
    {"key": "watch_paths",    "label": "감시 경로 등록",
     "desc": "관리자 > 감시 경로 탭에서 실제 운영 대상 경로 등록 및 활성화"},
    {"key": "frontend_build", "label": "프론트엔드 빌드",
     "desc": "frontend/ 에서 npm install && npm run build"},
    {"key": "nginx_deploy",   "label": "nginx 배포",
     "desc": "nginx/lhams.conf 적용 후 systemctl restart nginx"},
    {"key": "demo_check",     "label": "데모 점검",
     "desc": "README 데모 시나리오로 생성/수정/삭제/악성코드 이벤트가 대시보드에 반영되는지 확인"},
]

# ─────────────────────── 로거 (일별 로테이션) ───────────────────────
os.makedirs(os.path.dirname(TEXT_LOG_FILE), exist_ok=True)
logger = logging.getLogger("lhams")
logger.setLevel(logging.INFO)
_handler = TimedRotatingFileHandler(TEXT_LOG_FILE, when="midnight",
                                    backupCount=30, encoding="utf-8")
_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s",
                                        "%Y-%m-%d %H:%M:%S"))
logger.addHandler(_handler)
logger.addHandler(logging.StreamHandler())


# ─────────────────────────── 설정 저장소 ───────────────────────────
class ConfigStore:
    """data/config.json 로드/저장. 감시 경로 목록 + 무시 규칙을 관리한다."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            # 최초 실행: 기존 LHAMS_WATCH_DIR 하나로 시드 (하위호환)
            self.data = {
                "next_id": 2,
                "watch_paths": [
                    {"id": 1, "path": WATCH_DIR, "recursive": True, "enabled": True}
                ],
                "ignore_suffixes": list(DEFAULT_IGNORE_SUFFIX),
            }
            self._save()

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def save(self):
        with self._lock:
            self._save()

    @property
    def watch_paths(self):
        return self.data["watch_paths"]

    @property
    def ignore_suffixes(self):
        return self.data["ignore_suffixes"]

    def next_id(self):
        with self._lock:
            nid = self.data["next_id"]
            self.data["next_id"] += 1
            return nid


# ─────────────────────────── 감시 경로 관리 ───────────────────────────
class WatchManager:
    """Observer를 감싸서 런타임에 감시 경로를 추가/삭제/on-off 한다."""

    def __init__(self, observer: Observer, handler: FileSystemEventHandler, store: ConfigStore):
        self.observer = observer
        self.handler = handler
        self.store = store
        self._lock = threading.Lock()
        self._watches = {}  # id -> ObservedWatch (활성 상태인 경우만)

    def start_all(self):
        with self._lock:
            for entry in self.store.watch_paths:
                if entry["enabled"]:
                    self._schedule(entry)

    def _schedule(self, entry):
        if not os.path.isdir(entry["path"]):
            logger.error("감시 경로 없음, 건너뜀: %s", entry["path"])
            return
        watch = self.observer.schedule(self.handler, entry["path"], recursive=entry["recursive"])
        self._watches[entry["id"]] = watch

    def _unschedule(self, path_id):
        watch = self._watches.pop(path_id, None)
        if watch is not None:
            self.observer.unschedule(watch)

    def to_list(self):
        with self._lock:
            return [dict(e) for e in self.store.watch_paths]

    def add_path(self, path, recursive=True):
        path = os.path.normpath(path)
        if not os.path.isdir(path):
            raise ValueError(f"디렉토리가 존재하지 않습니다: {path}")
        with self._lock:
            if any(os.path.normcase(e["path"]) == os.path.normcase(path) for e in self.store.watch_paths):
                raise ValueError("이미 등록된 경로입니다")
            entry = {"id": self.store.next_id(), "path": path,
                      "recursive": bool(recursive), "enabled": True}
            self.store.watch_paths.append(entry)
            self._schedule(entry)
            self.store.save()
            return dict(entry)

    def remove_path(self, path_id):
        with self._lock:
            idx = next((i for i, e in enumerate(self.store.watch_paths) if e["id"] == path_id), None)
            if idx is None:
                raise KeyError("존재하지 않는 경로입니다")
            self._unschedule(path_id)
            self.store.watch_paths.pop(idx)
            self.store.save()

    def update_path(self, path_id, enabled=None, recursive=None):
        with self._lock:
            entry = next((e for e in self.store.watch_paths if e["id"] == path_id), None)
            if entry is None:
                raise KeyError("존재하지 않는 경로입니다")

            was_active = path_id in self._watches
            if enabled is not None:
                entry["enabled"] = bool(enabled)
            if recursive is not None:
                entry["recursive"] = bool(recursive)

            should_be_active = entry["enabled"]
            # 재귀 여부가 바뀌었거나 on/off가 바뀐 경우 재스케줄
            if was_active:
                self._unschedule(path_id)
            if should_be_active:
                self._schedule(entry)

            self.store.save()
            return dict(entry)


# ─────────────────────────── 격리소 관리 ───────────────────────────
class QuarantineStore:
    """격리된 파일의 원본 경로/시각/사유를 data/quarantine/_meta.json에 기록."""

    def __init__(self, meta_file: str):
        self.meta_file = meta_file
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(meta_file), exist_ok=True)
        if os.path.exists(meta_file):
            with open(meta_file, "r", encoding="utf-8") as f:
                self.entries = json.load(f)
        else:
            self.entries = []
            self._save()
        self._next_id = (max((e["id"] for e in self.entries), default=0) + 1)

    def _save(self):
        with open(self.meta_file, "w", encoding="utf-8") as f:
            json.dump(self.entries, f, ensure_ascii=False, indent=2)

    def record(self, filename, original_path, reason):
        with self._lock:
            entry = {
                "id": self._next_id,
                "filename": filename,
                "original_path": original_path,
                "quarantined_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "reason": reason,
            }
            self._next_id += 1
            self.entries.append(entry)
            self._save()
            return entry

    def list(self):
        with self._lock:
            return [dict(e) for e in self.entries]

    def restore(self, entry_id, quarantine_dir):
        with self._lock:
            entry = next((e for e in self.entries if e["id"] == entry_id), None)
            if entry is None:
                raise KeyError("존재하지 않는 격리 항목입니다")
            src = os.path.join(quarantine_dir, entry["filename"])
            if not os.path.isfile(src):
                raise FileNotFoundError("격리된 파일을 찾을 수 없습니다")
            dest_dir = os.path.dirname(entry["original_path"])
            os.makedirs(dest_dir, exist_ok=True)
            shutil.move(src, entry["original_path"])
            self.entries.remove(entry)
            self._save()

    def delete(self, entry_id, quarantine_dir):
        with self._lock:
            entry = next((e for e in self.entries if e["id"] == entry_id), None)
            if entry is None:
                raise KeyError("존재하지 않는 격리 항목입니다")
            path = os.path.join(quarantine_dir, entry["filename"])
            if os.path.isfile(path):
                os.remove(path)
            self.entries.remove(entry)
            self._save()


class AdminAuditLog:
    """관리자 페이지에서 발생한 설정 변경(누가/언제/무엇을)을 기록.

    파일 감사로그(lhams_audit.json)와는 별개로, '관리자 조작' 자체를
    감사 대상으로 삼는다 — 감시 경로 변경, 격리 복원/삭제, 체크리스트 등.
    """

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.entries = json.load(f)
        else:
            self.entries = []
            self._save()

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.entries, f, ensure_ascii=False, indent=2)

    def record(self, actor, action, target, detail=""):
        with self._lock:
            entry = {
                "id": int(time.time() * 1000),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "actor": (actor or "").strip() or "unknown",
                "action": action,
                "target": target,
                "detail": detail,
            }
            self.entries.insert(0, entry)
            self.entries = self.entries[:MAX_ADMIN_AUDIT_EVENTS]
            self._save()
            return entry

    def list(self):
        with self._lock:
            return [dict(e) for e in self.entries]


class ChecklistStore:
    """data/checklist.json — 신규 서버 구축 시 진행 단계와 완료자를 기록."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.items = json.load(f)
        else:
            self.items = []
            self._save()
        self._seed_defaults()

    def _seed_defaults(self):
        """새 버전에서 체크리스트 항목이 추가되면 기존 파일에도 이어붙인다."""
        existing_keys = {i["key"] for i in self.items}
        next_id = max((i["id"] for i in self.items), default=0) + 1
        changed = False
        for step in DEFAULT_CHECKLIST:
            if step["key"] not in existing_keys:
                self.items.append({
                    "id": next_id, "key": step["key"], "label": step["label"],
                    "desc": step["desc"], "done": False, "done_by": None, "done_at": None,
                })
                next_id += 1
                changed = True
        if changed:
            self._save()

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.items, f, ensure_ascii=False, indent=2)

    def list(self):
        with self._lock:
            return [dict(i) for i in self.items]

    def set_done(self, item_id, done, actor):
        with self._lock:
            item = next((i for i in self.items if i["id"] == item_id), None)
            if item is None:
                raise KeyError("존재하지 않는 체크리스트 항목입니다")
            item["done"] = bool(done)
            item["done_by"] = ((actor or "").strip() or "unknown") if done else None
            item["done_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if done else None
            self._save()
            return dict(item)


class AuditdResolver:
    """ausearch를 통해 '실제 행위자'를 조회하는 헬퍼.

    파일 소유자(owner)는 결과일 뿐, 감사 목적에는 auditd가 기록한
    auid(로그인 사용자) / comm(실행 프로세스) 정보가 필요하다.
    """

    AUID_RE = re.compile(r"\bauid=(\d+)")
    UID_RE  = re.compile(r"\buid=(\d+)")
    COMM_RE = re.compile(r'\bcomm="([^"]+)"')
    EXE_RE  = re.compile(r'\bexe="([^"]+)"')

    @staticmethod
    def _uid_to_name(uid: int) -> str:
        if uid in (4294967295, -1):        # unset auid
            return "system"
        if pwd is None:
            return f"uid:{uid}"
        try:
            return pwd.getpwuid(uid).pw_name
        except KeyError:
            return f"uid:{uid}"

    def resolve(self, filepath: str) -> dict:
        """최근 5초 내 해당 파일 관련 auditd 레코드에서 행위자 추출."""
        info = {"actor": None, "process": None, "exe": None}
        try:
            out = subprocess.run(
                ["ausearch", "-k", AUDIT_KEY, "-f", filepath,
                 "--start", "recent", "--format", "raw"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, timeout=3
            ).stdout
            if not out:
                return info
            # 가장 마지막(최신) 레코드 사용
            last = out.strip().splitlines()[-20:]
            blob = "\n".join(last)
            m = self.AUID_RE.search(blob) or self.UID_RE.search(blob)
            if m:
                info["actor"] = self._uid_to_name(int(m.group(1)))
            m = self.COMM_RE.search(blob)
            if m:
                info["process"] = m.group(1)
            m = self.EXE_RE.search(blob)
            if m:
                info["exe"] = m.group(1)
        except Exception:
            pass
        return info


class LhamsAuditHandler(FileSystemEventHandler):
    def __init__(self, store: ConfigStore, quarantine_store: QuarantineStore):
        self.auditd = AuditdResolver()
        self.store = store
        self.quarantine_store = quarantine_store
        os.makedirs(os.path.dirname(JSON_LOG_FILE), exist_ok=True)
        os.makedirs(QUARANTINE_DIR, exist_ok=True)
        if not os.path.exists(JSON_LOG_FILE):
            with open(JSON_LOG_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)

    # ── 유틸 ──────────────────────────────────────────────
    @staticmethod
    def get_owner(filepath: str) -> str:
        if pwd is None:
            return "unknown"
        try:
            return pwd.getpwuid(os.stat(filepath).st_uid).pw_name
        except Exception:
            return "unknown"

    @staticmethod
    def scan_malware(filepath: str) -> bool:
        """clamd 소켓 통신 검사. FOUND 시 True."""
        try:
            r = subprocess.run(
                ["clamdscan", "--stream", "--fdpass", "--no-summary", filepath],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=30
            )
            return "FOUND" in r.stdout
        except Exception:
            return False

    def quarantine(self, filepath: str) -> bool:
        try:
            if os.path.isfile(filepath):
                dest = os.path.join(QUARANTINE_DIR, os.path.basename(filepath))
                shutil.move(filepath, dest)
                self.quarantine_store.record(
                    filename=os.path.basename(filepath),
                    original_path=filepath,
                    reason="MALWARE_DETECTED",
                )
                return True
        except Exception:
            pass
        return False

    # ── 핵심 로깅 ──────────────────────────────────────────
    def log_event(self, event_type: str, filepath: str, dest: str = None):
        ignore_suffix = tuple(self.store.ignore_suffixes)
        if filepath.endswith(ignore_suffix):
            return

        now = datetime.now()
        owner = self.get_owner(filepath) if os.path.exists(filepath) else "unknown"

        # auditd로 실제 행위자(누가) 조회
        who = self.auditd.resolve(filepath)
        actor = who["actor"] or owner

        # 악성코드 검사 (생성/수정/이동유입 시)
        is_malware = False
        if event_type in ("CREATED", "MODIFIED", "MOVED") and os.path.exists(filepath):
            is_malware = self.scan_malware(filepath)

        quarantined = False
        if is_malware:
            quarantined = self.quarantine(filepath)

        if is_malware:
            event_label, risk = "MALWARE_DETECTED", "Critical"
        elif event_type == "DELETED":
            event_label, risk = "DELETED", "High"
        elif event_type == "MOVED":
            event_label, risk = "MOVED", "Medium"
        else:
            event_label, risk = event_type, "Low"

        entry = {
            "id": int(time.time() * 1000),
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "event_type": event_label,
            "file_path": filepath,
            "dest_path": dest,
            "user": actor,                 # 실제 행위자 (auditd 기준)
            "owner": owner,                # 파일 소유자
            "process": who["process"],     # 어떤 프로세스로 작업했는지
            "exe": who["exe"],
            "risk_level": risk,
            "quarantined": quarantined,
        }

        logger.info("%s | %s | %s | actor=%s proc=%s | risk=%s",
                    event_label, filepath,
                    f"-> {dest}" if dest else "",
                    actor, who["process"], risk)
        self._append_json(entry)

    def _append_json(self, entry: dict):
        try:
            with open(JSON_LOG_FILE, "r+", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = []
                data.insert(0, entry)
                data = data[:MAX_JSON_EVENTS]
                f.seek(0)
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.truncate()
        except Exception as e:
            logger.error("JSON write error: %s", e)

    # ── watchdog 콜백 ─────────────────────────────────────
    def on_created(self, event):
        if not event.is_directory:
            self.log_event("CREATED", event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self.log_event("MODIFIED", event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            self.log_event("DELETED", event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self.log_event("MOVED", event.src_path, dest=event.dest_path)


# ─────────────────────────── 관리 API (Flask) ───────────────────────────
def create_api(watch_manager: WatchManager, config_store: ConfigStore, quarantine_store: QuarantineStore,
                checklist_store: ChecklistStore, admin_audit: AdminAuditLog):
    app = Flask("lhams_admin_api")

    def err(message, status=400):
        return jsonify({"error": message}), status

    def actor_of(body):
        return (body.get("actor") or "").strip() or "unknown"

    @app.get("/api/config")
    def get_config():
        return jsonify({
            "watch_paths": watch_manager.to_list(),
            "ignore_suffixes": config_store.ignore_suffixes,
        })

    @app.post("/api/paths")
    def add_path():
        body = request.get_json(silent=True) or {}
        path = (body.get("path") or "").strip()
        if not path:
            return err("경로를 입력하세요")
        try:
            entry = watch_manager.add_path(path, recursive=body.get("recursive", True))
            admin_audit.record(actor_of(body), "PATH_ADD", entry["path"],
                                f"하위 폴더 포함: {'예' if entry['recursive'] else '아니오'}")
            return jsonify(entry), 201
        except ValueError as e:
            return err(str(e))

    @app.patch("/api/paths/<int:path_id>")
    def patch_path(path_id):
        body = request.get_json(silent=True) or {}
        try:
            entry = watch_manager.update_path(
                path_id,
                enabled=body.get("enabled"),
                recursive=body.get("recursive"),
            )
            changes = []
            if body.get("enabled") is not None:
                changes.append(f"활성={'on' if entry['enabled'] else 'off'}")
            if body.get("recursive") is not None:
                changes.append(f"하위 폴더={'on' if entry['recursive'] else 'off'}")
            admin_audit.record(actor_of(body), "PATH_UPDATE", entry["path"], ", ".join(changes))
            return jsonify(entry)
        except KeyError as e:
            return err(str(e), 404)

    @app.delete("/api/paths/<int:path_id>")
    def delete_path(path_id):
        body = request.get_json(silent=True) or {}
        try:
            target = next((e["path"] for e in watch_manager.to_list() if e["id"] == path_id), f"id:{path_id}")
            watch_manager.remove_path(path_id)
            admin_audit.record(actor_of(body), "PATH_REMOVE", target)
            return "", 204
        except KeyError as e:
            return err(str(e), 404)

    @app.get("/api/quarantine")
    def list_quarantine():
        return jsonify(quarantine_store.list())

    @app.post("/api/quarantine/<int:entry_id>/restore")
    def restore_quarantine(entry_id):
        body = request.get_json(silent=True) or {}
        try:
            target = next((e["original_path"] for e in quarantine_store.list() if e["id"] == entry_id), f"id:{entry_id}")
            quarantine_store.restore(entry_id, QUARANTINE_DIR)
            admin_audit.record(actor_of(body), "QUARANTINE_RESTORE", target)
            return "", 200
        except (KeyError, FileNotFoundError) as e:
            return err(str(e), 404)

    @app.delete("/api/quarantine/<int:entry_id>")
    def delete_quarantine(entry_id):
        body = request.get_json(silent=True) or {}
        try:
            target = next((e["filename"] for e in quarantine_store.list() if e["id"] == entry_id), f"id:{entry_id}")
            quarantine_store.delete(entry_id, QUARANTINE_DIR)
            admin_audit.record(actor_of(body), "QUARANTINE_DELETE", target)
            return "", 204
        except KeyError as e:
            return err(str(e), 404)

    @app.put("/api/settings")
    def update_settings():
        body = request.get_json(silent=True) or {}
        suffixes = body.get("ignore_suffixes")
        if not isinstance(suffixes, list) or not all(isinstance(s, str) for s in suffixes):
            return err("ignore_suffixes는 문자열 배열이어야 합니다")
        config_store.data["ignore_suffixes"] = suffixes
        config_store.save()
        admin_audit.record(actor_of(body), "SETTINGS_UPDATE", "무시 규칙", ", ".join(suffixes) or "(빈 목록)")
        return jsonify({"ignore_suffixes": suffixes})

    @app.get("/api/checklist")
    def list_checklist():
        return jsonify(checklist_store.list())

    @app.patch("/api/checklist/<int:item_id>")
    def patch_checklist(item_id):
        body = request.get_json(silent=True) or {}
        done = body.get("done")
        if not isinstance(done, bool):
            return err("done은 boolean이어야 합니다")
        try:
            actor = actor_of(body)
            item = checklist_store.set_done(item_id, done, actor)
            admin_audit.record(actor, "CHECKLIST_DONE" if done else "CHECKLIST_UNDONE", item["label"])
            return jsonify(item)
        except KeyError as e:
            return err(str(e), 404)

    @app.get("/api/admin-audit")
    def list_admin_audit():
        return jsonify(admin_audit.list())

    return app


if __name__ == "__main__":
    config_store = ConfigStore(CONFIG_FILE)
    quarantine_store = QuarantineStore(QUARANTINE_META_FILE)
    checklist_store = ChecklistStore(CHECKLIST_FILE)
    admin_audit = AdminAuditLog(ADMIN_AUDIT_FILE)
    handler = LhamsAuditHandler(config_store, quarantine_store)

    observer = Observer()
    watch_manager = WatchManager(observer, handler, config_store)
    watch_manager.start_all()
    observer.start()

    api = create_api(watch_manager, config_store, quarantine_store, checklist_store, admin_audit)
    api_thread = threading.Thread(
        target=lambda: api.run(host="0.0.0.0", port=API_PORT, threaded=True, use_reloader=False),
        daemon=True,
    )
    api_thread.start()

    logger.info("[*] LHAMS Watchdog started. Watching %d path(s). Admin API on :%d",
                len(config_store.watch_paths), API_PORT)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
