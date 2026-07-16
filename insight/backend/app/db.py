"""SQLite 영속화 계층 — 별도 DB 서버·포트 없이 파일 하나로 관리.

고객사 현장은 이미 사용 중인 DB가 정해져 있어 별도 DB 엔진을 들여오기 어렵고,
방화벽 정책상 새 포트(예: PostgreSQL 5432)를 여는 것도 쉽지 않다 — 리스크
체크리스트의 "DB 선정" 항목은 이 제약을 반영해 SQLite로 결론짓는다. 표준
라이브러리(`sqlite3`)만으로 동작하는 파일 기반 임베디드 DB라 추가 설치·포트·
서비스 계정이 전혀 필요 없다. 구축팀은 `INSIGHT_DB_PATH` 파일 하나만 백업·
이관하면 된다.

동시성 전략: 요청마다 짧은 연결을 열고 닫는다(connect-per-call). 이 서비스의
트래픽 규모(관리자 대시보드 1대, 초당 요청 수 건)에서는 커넥션 풀보다 단순함이
이득이며, WAL 모드로 읽기/쓰기 잠금 경합을 최소화하고 busy timeout으로 순간
경합도 완충한다.
"""
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BACKEND_DIR / "data" / "insight.db"
DB_PATH = Path(os.environ.get("INSIGHT_DB_PATH", str(DEFAULT_DB_PATH)))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def _session():
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_schema():
    with _session() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS journeys (
            message_id TEXT PRIMARY KEY,
            created_at REAL NOT NULL,
            meta_json TEXT NOT NULL,
            hops_json TEXT NOT NULL,
            released INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_journeys_created_at ON journeys(created_at DESC);

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            t TEXT NOT NULL,
            node TEXT NOT NULL,
            sev TEXT NOT NULL,
            msg TEXT NOT NULL,
            ch TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(ts DESC);

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            target TEXT NOT NULL,
            result TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts DESC);

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL
        );
        """)


# ── 메일 여정 ────────────────────────────────────────────────────────────
def upsert_journey(j: dict):
    with _session() as conn:
        conn.execute(
            "INSERT INTO journeys(message_id, created_at, meta_json, hops_json, released) "
            "VALUES (?,?,?,?,?) "
            "ON CONFLICT(message_id) DO UPDATE SET "
            "hops_json=excluded.hops_json, released=excluded.released",
            (j["message_id"], j["created_at"], json.dumps(j["meta"], ensure_ascii=False),
             json.dumps(j["hops"], ensure_ascii=False), int(bool(j.get("released")))),
        )


def load_journeys(limit: int = 500) -> list:
    with _session() as conn:
        rows = conn.execute(
            "SELECT message_id, created_at, meta_json, hops_json, released FROM journeys "
            "ORDER BY created_at DESC LIMIT ?", (limit,),
        ).fetchall()
    return [
        {"message_id": r[0], "created_at": r[1], "meta": json.loads(r[2]),
         "hops": json.loads(r[3]), "released": bool(r[4])}
        for r in rows
    ]


def purge_journeys_older_than(days: int) -> int:
    """개인정보(메일 제목·주소) 장기 보관 리스크 완화 — 보관기간 초과 여정을 DB에서 폐기."""
    cutoff = time.time() - days * 86400
    with _session() as conn:
        cur = conn.execute("DELETE FROM journeys WHERE created_at < ?", (cutoff,))
        return cur.rowcount


# ── 경보 ─────────────────────────────────────────────────────────────────
def insert_alert(entry: dict):
    with _session() as conn:
        conn.execute(
            "INSERT INTO alerts(ts, t, node, sev, msg, ch) VALUES (?,?,?,?,?,?)",
            (entry["ts"], entry["t"], entry["node"], entry["sev"], entry["msg"], entry["ch"]),
        )
        conn.execute(
            "DELETE FROM alerts WHERE id NOT IN (SELECT id FROM alerts ORDER BY ts DESC LIMIT 2000)"
        )


def load_alerts(limit: int = 300) -> list:
    with _session() as conn:
        rows = conn.execute(
            "SELECT ts, t, node, sev, msg, ch FROM alerts ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
    return [{"ts": r[0], "t": r[1], "node": r[2], "sev": r[3], "msg": r[4], "ch": r[5]} for r in rows]


# ── 감사 로그 ────────────────────────────────────────────────────────────
def insert_audit(entry: dict):
    with _session() as conn:
        conn.execute(
            "INSERT INTO audit_log(ts, actor, action, target, result) VALUES (?,?,?,?,?)",
            (entry["ts"], entry["actor"], entry["action"], entry["target"], entry["result"]),
        )
        conn.execute(
            "DELETE FROM audit_log WHERE id NOT IN (SELECT id FROM audit_log ORDER BY ts DESC LIMIT 5000)"
        )


def load_audit(limit: int = 500) -> list:
    with _session() as conn:
        rows = conn.execute(
            "SELECT ts, actor, action, target, result FROM audit_log ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
    return [{"ts": r[0], "actor": r[1], "action": r[2], "target": r[3], "result": r[4]} for r in rows]


# ── 설정 (키-값) — thresholds·webhook·sos_settings·node_endpoints 등을 한 곳에 ──
def get_setting(key: str, default: Any = None) -> Any:
    with _session() as conn:
        row = conn.execute("SELECT value_json FROM settings WHERE key=?", (key,)).fetchone()
    return json.loads(row[0]) if row else default


def set_setting(key: str, value: Any):
    with _session() as conn:
        conn.execute(
            "INSERT INTO settings(key, value_json) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json",
            (key, json.dumps(value, ensure_ascii=False)),
        )
