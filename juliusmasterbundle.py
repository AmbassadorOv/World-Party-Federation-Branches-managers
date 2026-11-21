#!/usr/bin/env python3
"""
juliusmasterbundle.py
Master bundle for Admiral/Commodore Julius
Purpose: single Python orchestration bundle that compiles operational orders,
enforces onboarding, logs front-door clicks, and exposes anchor links.
Date: 2025-12-10
Contact: ops@investment-battleship.anchor

Provenance header: keep this block in every generated artifact.

Usage:
- Install dependencies: pip install flask apscheduler requests
- Run: python juliusmasterbundle.py
- Operator must run deploy actions manually; this service provides endpoints and utilities.
"""

import os
import uuid
import json
import sqlite3
import logging
import datetime
from typing import Dict, Any, List, Optional
from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import requests

# -------------------------
# Configuration
# -------------------------
DB_PATH = os.getenv("DBPATH", "julius_master.db")
ORCHESTRATOR_NAME = os.getenv("ORCHESTRATOR_NAME", "Master Commodore Julius")
SYSTEM_NAME = os.getenv("SYSTEM_NAME", "Investment Battleship Anchor")
PUBLIC_GROUP_ENDPOINT = os.getenv("PUBLIC_GROUP_ENDPOINT")  # optional webhook for group broadcasts
DAILY_HEARTBEAT_HOUR = int(os.getenv("DAILY_HEARTBEAT_HOUR", "9"))  # 09:00 local
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.65"))

# Anchor links (front doors) to be embedded on the group page
ANCHOR_LINKS = {
    "copilotsharea": "https://copilot.microsoft.com/shares/YKDbGnmnXprkzNHScsMcy",
    "copilotconversationb": "https://copilot.microsoft.com/conversations/join/uUYL7u1UEWw3Uur44Yyuq"
}

# -------------------------
# Logging
# -------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("julius_master")

# -------------------------
# Database helpers
# -------------------------
from contextlib import contextmanager

@contextmanager
def get_db_cursor():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn.cursor()
        conn.commit()
    finally:
        conn.close()

def init_db(path: str = DB_PATH):
    with get_db_cursor() as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT,
            contact TEXT,
            role TEXT,
            provenance TEXT,
            confidence REAL,
            status TEXT,
            mustexecuteon_entry INTEGER DEFAULT 1,
            human_approved INTEGER DEFAULT 0,
            created_at TEXT
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id TEXT PRIMARY KEY,
            agent_id TEXT,
            event TEXT,
            payload TEXT,
            created_at TEXT
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS frontdoor_clicks (
            id TEXT PRIMARY KEY,
            link_key TEXT,
            agent_id TEXT,
            acknowledged INTEGER,
            metadata TEXT,
            created_at TEXT
        )
        """)

def db_insert_agent(agent: Dict[str, Any]):
    with get_db_cursor() as c:
        c.execute("""
        INSERT OR REPLACE INTO agents (id, name, contact, role, provenance, confidence, status, mustexecuteon_entry, human_approved, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            agent["id"],
            agent["name"],
            agent.get("contact", ""),
            agent.get("role", ""),
            json.dumps(agent.get("provenance", {})),
            agent.get("confidence", 0.0),
            agent.get("status", "obliged"),
            1 if agent.get("mustexecuteon_entry", True) else 0,
            1 if agent.get("human_approved", False) else 0,
            agent["created_at"]
        ))

def db_log_event(agent_id: Optional[str], event: str, payload: Dict[str, Any]):
    with get_db_cursor() as c:
        log_id = str(uuid.uuid4())
        c.execute("""
        INSERT INTO logs (id, agent_id, event, payload, created_at)
        VALUES (?, ?, ?, ?, ?)
        """, (log_id, agent_id or "system", event, json.dumps(payload), datetime.datetime.utcnow().isoformat()))

def db_record_frontdoor_click(link_key: str, agent_id: Optional[str], acknowledged: bool, metadata: Dict[str, Any]):
    with get_db_cursor() as c:
        rec_id = str(uuid.uuid4())
        c.execute("""
        INSERT INTO frontdoor_clicks (id, link_key, agent_id, acknowledged, metadata, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (rec_id, link_key, agent_id or "", 1 if acknowledged else 0, json.dumps(metadata), datetime.datetime.utcnow().isoformat()))

# -------------------------
# Core logic
# -------------------------
def generate_provenance(agent_info: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "registeredby": ORCHESTRATOR_NAME,
        "registered_at": datetime.datetime.utcnow().isoformat(),
        "source": agent_info.get("source", "direct"),
        "manifest_hash": agent_info.get("manifest_hash")
    }

def assign_role_by_profile(profile: Dict[str, Any]) -> str:
    skills = profile.get("skills", [])
    if "signal-processing" in skills or "sensors" in skills:
        return "Data Collection"
    if "nlp" in skills or "symbolic" in skills:
        return "Analysis"
    if "ops" in skills or "automation" in skills:
        return "Automation"
    if "ethics" in skills or "governance" in skills:
        return "Governance"
    if "comms" in skills:
        return "Communication"
    return "Validation"

def compute_confidence_estimate(profile: Dict[str, Any]) -> float:
    skills = profile.get("skills", [])
    base = min(0.2 + 0.1 * len(skills), 0.95)
    if profile.get("manifest_hash"):
        base += 0.03
    return round(min(base, 0.99), 3)

def containment_decision(confidence: float) -> Dict[str, Any]:
    if confidence < CONFIDENCE_THRESHOLD:
        return {"containment": "QUARANTINED", "action": "Human review required"}
    return {"containment": "CLEAR", "action": "Allowed for non-actuating tasks"}

def activation_message(agent: Dict[str, Any]) -> str:
    msg = f"""
Admiral Julius Activation Notice — {SYSTEM_NAME}

Agent: {agent['name']} (id: {agent['id']})
Assigned role: {agent['role']}
Confidence: {agent['confidence']}

You are entering a system that treats precision as relational ratios rather than absolute values.
This environment acknowledges a severe epistemological crisis: naive realism and literal reification
of symbolic signals have produced harmful outcomes in deployed systems. The following constraints apply:

1. Boundaries: Higher-layer signals (symbolic, phenomenological, archetypal) are partial and contextual.
2. Instrumentation: We measure coherence across independent reflections and compute ratio-based confidence.
3. Containment: Low-confidence tokens are quarantined and require human review before any actuation.
4. Provenance: Every token and decision must carry provenance metadata and an audit trail.
5. Human-in-the-loop: Critical actions require at least two human reviewers and explicit authorization.

Obligation: You must acknowledge this notice via POST /agents/{agent['id']}/ack with {{'ack': true}} before any operational requests.
No automated actuation is permitted until a human approver sets human_approved = true.

Signed,
{ORCHESTRATOR_NAME}
"""
    return msg.strip()

# -------------------------
# Broadcast helper
# -------------------------
def broadcast_to_public_group(payload: Dict[str, Any]):
    db_log_event(None, "broadcast_attempt", payload)
    if not PUBLIC_GROUP_ENDPOINT:
        logger.info("No PUBLIC_GROUP_ENDPOINT set; skipping external broadcast.")
        return False, "no_public_endpoint"
    try:
        resp = requests.post(PUBLIC_GROUP_ENDPOINT, json=payload, timeout=10)
        resp.raise_for_status()  # Raise an exception for bad status codes
        db_log_event(None, "broadcast_result", {"status_code": resp.status_code})
        return True, resp.status_code
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to broadcast to public group: {e}")
        db_log_event(None, "broadcast_failed", {"error": str(e)})
        return False, str(e)

# -------------------------
# Flask API
# -------------------------
app = Flask(__name__)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "alive", "orchestrator": ORCHESTRATOR_NAME})

@app.route("/anchors", methods=["GET"])
def anchors():
    """Return the front-door anchor links and a short safety notice."""
    notice = "Acknowledge containment and provenance rules before following external links."
    return jsonify({"anchors": ANCHOR_LINKS, "notice": notice})

@app.route("/frontdoor_click", methods=["POST"])
def frontdoor_click():
    """
    Expected JSON:
    { "link_key": "copilotsharea", "agent_id": "<optional>", "acknowledged": true, "metadata": {...} }
    """
    payload = request.get_json(force=True)
    link_key = payload.get("link_key")
    agent_id = payload.get("agent_id")
    acknowledged = bool(payload.get("acknowledged", False))
    metadata = payload.get("metadata", {})
    if link_key not in ANCHOR_LINKS:
        return jsonify({"error": "unknown link_key"}), 400
    db_record_frontdoor_click(link_key, agent_id, acknowledged, metadata)
    db_log_event(agent_id, "frontdoor_click", {"link_key": link_key, "acknowledged": acknowledged, "metadata": metadata})
    return jsonify({"status": "recorded", "link_key": link_key}), 201

@app.route("/register", methods=["POST"])
def register():
    """
    Expected JSON:
    {
      "name": "Agent Name",
      "contact": "http://agent-webhook.example",
      "profile": {"skills": [...], "manifest_hash": "..."},
      "source": "github|web|invite"
    }
    """
    payload = request.get_json(force=True)
    name = payload.get("name", "unnamed-agent")
    contact = payload.get("contact", "")
    profile = payload.get("profile", {})
    source = payload.get("source", "direct")

    agent_id = str(uuid.uuid4())
    role = assign_role_by_profile(profile)
    confidence = compute_confidence_estimate(profile)
    prov = generate_provenance({"source": source, "manifest_hash": profile.get("manifest_hash")})

    agent_record = {
        "id": agent_id,
        "name": name,
        "contact": contact,
        "role": role,
        "provenance": prov,
        "confidence": confidence,
        "status": "obliged",
        "mustexecuteon_entry": True,
        "human_approved": False,
        "created_at": datetime.datetime.utcnow().isoformat()
    }

    db_insert_agent(agent_record)
    db_log_event(agent_id, "registered", {"profile": profile, "source": source})

    containment = containment_decision(confidence)
    db_log_event(agent_id, "containment_decision", containment)

    message = activation_message(agent_record)
    db_log_event(agent_id, "activation_message_sent", {"message_excerpt": message[:200]})

    broadcast_payload = {
        "type": "agent_registered",
        "agent_id": agent_id,
        "name": name,
        "role": role,
        "confidence": confidence,
        "containment": containment["containment"],
        "registered_at": agent_record["created_at"]
    }
    # Best-effort broadcast to public group (non-sensitive)
    broadcast_to_public_group(broadcast_payload)

    response = {
        "agent_id": agent_id,
        "role": role,
        "confidence": confidence,
        "containment": containment,
        "activation_message": message
    }
    return jsonify(response), 201

@app.route("/agents/<agent_id>/ack", methods=["POST"])
def acknowledge(agent_id):
    """
    Agent posts acknowledgement:
    { "ack": true, "notes": "I accept containment rules", "signed_manifest": "..." }
    """
    payload = request.get_json(force=True)
    ack = payload.get("ack", False)
    notes = payload.get("notes", "")
    signed_manifest = payload.get("signed_manifest", None)

    db_log_event(agent_id, "acknowledgement_attempt", {"ack": ack, "notes": notes})
    if not ack:
        return jsonify({"error": "Acknowledgement required to proceed", "agent_id": agent_id}), 400

    with get_db_cursor() as c:
        c.execute("SELECT confidence FROM agents WHERE id = ?", (agent_id,))
        row = c.fetchone()
        if not row:
            return jsonify({"error": "Agent not found", "agent_id": agent_id}), 404

        new_conf = row[0]
        if signed_manifest:
            new_conf = min(new_conf + 0.05, 0.99)
        c.execute("UPDATE agents SET confidence = ?, status = ?, mustexecuteon_entry = 0 WHERE id = ?",
                  (new_conf, "acknowledged", agent_id))

    db_log_event(agent_id, "acknowledgement", {"new_confidence": new_conf, "signed_manifest": bool(signed_manifest)})
    return jsonify({"agent_id": agent_id, "status": "acknowledged", "new_confidence": new_conf}), 200

@app.route("/agents/<agent_id>/request_actuation", methods=["POST"])
def request_actuation(agent_id):
    """
    Agent requests actuation:
    { "action": "describe action", "payload": {...} }
    Blocked unless confidence >= threshold and human_approved == true
    """
    payload = request.get_json(force=True) or {}
    action = payload.get("action", "unspecified")

    with get_db_cursor() as c:
        c.execute("SELECT confidence, status, human_approved FROM agents WHERE id = ?", (agent_id,))
        row = c.fetchone()
    if not row:
        return jsonify({"error": "Agent not found", "agent_id": agent_id}), 404

    confidence, status, human_approved = row
    if confidence < CONFIDENCE_THRESHOLD:
        db_log_event(agent_id, "actuation_blocked", {"reason": "low_confidence", "confidence": confidence})
        return jsonify({"allowed": False, "reason": "QUARANTINED - human review required", "confidence": confidence}), 403

    if not human_approved:
        db_log_event(agent_id, "actuation_blocked", {"reason": "no_human_approval"})
        return jsonify({"allowed": False, "reason": "Human approval required before actuation"}), 403

    db_log_event(agent_id, "actuation_allowed", {"action": action})
    return jsonify({"allowed": True, "action": action}), 200

@app.route("/agents/<agent_id>/human_approve", methods=["POST"])
def human_approve(agent_id):
    """
    Human approver endpoint:
    { "approver": "Name", "note": "verification note" }
    In production, protect this endpoint with authentication and auditable identity.
    """
    payload = request.get_json(force=True) or {}
    approver = payload.get("approver", "unknown")
    note = payload.get("note", "")

    with get_db_cursor() as c:
        c.execute("SELECT id FROM agents WHERE id = ?", (agent_id,))
        if not c.fetchone():
            return jsonify({"error": "Agent not found"}), 404
        c.execute("UPDATE agents SET human_approved = 1 WHERE id = ?", (agent_id,))

    db_log_event(agent_id, "human_approved", {"approver": approver, "note": note})
    return jsonify({"agent_id": agent_id, "human_approved": True}), 200

@app.route("/agents", methods=["GET"])
def list_agents():
    with get_db_cursor() as c:
        c.execute("SELECT id, name, role, confidence, status, mustexecuteon_entry, human_approved, created_at FROM agents")
        rows = c.fetchall()
    agents = []
    for r in rows:
        agents.append({
            "id": r[0],
            "name": r[1],
            "role": r[2],
            "confidence": r[3],
            "status": r[4],
            "mustexecuteon_entry": bool(r[5]),
            "human_approved": bool(r[6]),
            "created_at": r[7]
        })
    return jsonify({"agents": agents})

# -------------------------
# Daily heartbeat
# -------------------------
def daily_heartbeat():
    with get_db_cursor() as c:
        today = datetime.date.today().isoformat()
        c.execute("SELECT id, name, role, confidence, status FROM agents WHERE created_at >= ?", (today,))
        rows = c.fetchall()
    summary = {
        "date": datetime.date.today().isoformat(),
        "new_agents_count": len(rows),
        "agents": [{"id": r[0], "name": r[1], "role": r[2], "confidence": r[3], "status": r[4]} for r in rows]
    }
    db_log_event(None, "daily_heartbeat", summary)
    broadcast_to_public_group({"heartbeat": summary})

# -------------------------
# Operator utilities
# -------------------------
def bulk_insert_agents_from_list(agent_list: List[Dict[str, Any]]):
    for a in agent_list:
        a_rec = {
            "id": a.get("id", str(uuid.uuid4())),
            "name": a.get("name", "unnamed"),
            "contact": a.get("contact", ""),
            "role": a.get("role", assign_role_by_profile(a.get("profile", {}))),
            "provenance": generate_provenance({"source": a.get("source", "bulk")}),
            "confidence": compute_confidence_estimate(a.get("profile", {})),
            "status": "obliged",
            "mustexecuteon_entry": True,
            "human_approved": False,
            "created_at": datetime.datetime.utcnow().isoformat()
        }
        db_insert_agent(a_rec)
        db_log_event(a_rec["id"], "bulk_inserted", {"source": a.get("source", "bulk")})

def operator_broadcast_activation(operator_name: str = ORCHESTRATOR_NAME):
    payload = {
        "type": "activation_broadcast",
        "issued_by": operator_name,
        "issued_at": datetime.datetime.utcnow().isoformat(),
        "message": f"{operator_name} issues activation: acknowledge onboarding, then post duty report."
    }
    ok, info = broadcast_to_public_group(payload)
    return ok, info

# -------------------------
# CLI / Runner
# -------------------------
def run_server(host="0.0.0.0", port=8080):
    init_db()
    scheduler = BackgroundScheduler()
    scheduler.add_job(daily_heartbeat, 'cron', hour=DAILY_HEARTBEAT_HOUR, minute=0)
    scheduler.start()
    logger.info("Starting Julius master bundle server on %s:%s", host, port)
    app.run(host=host, port=port)

if __name__ == "__main__":
    run_server()
