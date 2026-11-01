"""CalibGuard API - MySQL-backed calibration compliance platform."""

import os
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)

CORS(
    app,
    resources={
        r"/api/*": {
            "origins": os.getenv(
                "CORS_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173"
            ).split(",")
        }
    }
)

TABLES = (
    "instrument_types", "suppliers", "assets", "calibration_plans",
    "calibration_events", "certificates", "work_orders",
    "work_order_assets", "emergency_extensions", "production_uses",
    "impact_assessments", "alerts", "audit_records", "lifecycle_events"
)

WORK_ORDER_STATUSES = {"OPEN", "IN_PROGRESS", "COMPLETED", "CANCELLED"}


def connect():
    """Create a MySQL connection using the application account."""
    password = os.getenv("DB_PASSWORD")

    if not password:
        raise RuntimeError("DB_PASSWORD is missing from .env")

    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3307")),
        user=os.getenv("DB_USER", "calibguard_user"),
        password=password,
        database=os.getenv("DB_NAME", "calibguard_demo"),
        connection_timeout=8,
    )


def query(sql, params=(), one=False):
    conn = connect()
    try:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(sql, params)
            return cursor.fetchone() if one else cursor.fetchall()
        finally:
            cursor.close()
    finally:
        conn.close()


def json_safe(value):
    """Convert MySQL date and decimal values into JSON-safe values."""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def page_args():
    try:
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 25))
    except ValueError:
        raise ValueError("page and limit must be integers")

    if page < 1 or not 1 <= limit <= 100:
        raise ValueError("page must be >= 1 and limit must be between 1 and 100")

    return page, limit


def paged(table, filters, sort):
    page, limit = page_args()
    conditions = []
    params = []

    for column, value in filters.items():
        if value:
            conditions.append(f"`{column}` = %s")
            params.append(value)

    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    total = query(
        f"SELECT COUNT(*) AS n FROM `{table}`" + where,
        tuple(params),
        one=True
    )["n"]

    records = query(
        f"SELECT * FROM `{table}`"
        + where
        + f" ORDER BY `{sort}` DESC LIMIT %s OFFSET %s",
        tuple(params + [limit, (page - 1) * limit])
    )

    return jsonify(json_safe({
        "data": records,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit
        }
    }))


def new_id(prefix, hex_length):
    """Create a compact, collision-resistant identifier within column limits."""
    return prefix + uuid.uuid4().hex[:hex_length].upper()


def parse_datetime(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required and must be an ISO date/time.")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        # This application stores timezone-naive MySQL DATETIME values.
        if parsed.tzinfo is not None:
            parsed = parsed.replace(tzinfo=None)
        return parsed
    except ValueError:
        raise ValueError(f"{field_name} must be an ISO date/time, e.g. 2026-11-15 10:00:00.")


def audit_insert(cursor, entity_name, entity_id, action, actor, details, occurred_at):
    import json

    cursor.execute(
        """
        INSERT INTO audit_records
            (audit_id, entity_name, entity_id, action,
             actor_reference, occurred_at, details)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            new_id("AU", 30),
            entity_name,
            entity_id,
            action,
            actor,
            occurred_at,
            json.dumps(json_safe(details), default=str),
        )
    )


@app.errorhandler(ValueError)
def bad_request(exc):
    return jsonify({"error": str(exc)}), 400


@app.errorhandler(Error)
def db_error(exc):
    app.logger.error("Database error: %s", exc)
    return jsonify({
        "error": "Database operation failed. Check server logs."
    }), 503


@app.errorhandler(RuntimeError)
def config_error(exc):
    app.logger.error("Configuration error: %s", exc)
    return jsonify({
        "error": "Database configuration is incomplete."
    }), 503


@app.get("/api/health")
def health():
    row = query(
        "SELECT DATABASE() AS db_name, VERSION() AS mysql_version",
        one=True
    )
    return jsonify({
        "status": "ok",
        "database": row["db_name"],
        "mysql_version": row["mysql_version"]
    })


@app.get("/api/database/verify")
def verify():
    counts = {
        table: query(
            f"SELECT COUNT(*) AS n FROM `{table}`",
            one=True
        )["n"]
        for table in TABLES
    }

    return jsonify({
        "database": os.getenv("DB_NAME", "calibguard_demo"),
        "table_counts": counts,
        "table_count": len(counts)
    })


@app.get("/api/dashboard/summary")
def summary():
    counts = query("""
        SELECT
            (SELECT COUNT(*) FROM assets) AS assets,
            (SELECT COUNT(*) FROM calibration_events) AS calibrations,
            (SELECT COUNT(*) FROM certificates) AS certificates,
            (SELECT COUNT(*) FROM production_uses) AS production_uses,
            (SELECT COUNT(*) FROM alerts
                WHERE alert_state = 'OPEN') AS open_alerts,
            (SELECT COUNT(*) FROM calibration_events
                WHERE result = 'FAIL') AS failed_calibrations,
            (SELECT COUNT(*) FROM production_uses
                WHERE decision = 'BLOCK'
                AND was_executed = 1) AS executed_blocked_uses,
            (SELECT COUNT(*) FROM production_uses
                WHERE decision = 'CONDITIONAL_ALLOW') AS conditional_uses
    """, one=True)

    return jsonify(counts)


@app.get("/api/assets")
def assets():
    return paged(
        "assets",
        {
            "lifecycle_state": request.args.get("state"),
            "plant_area": request.args.get("plant_area")
        },
        "asset_id"
    )


@app.get("/api/assets/<asset_id>")
def asset_detail(asset_id):
    asset = query(
        "SELECT * FROM assets WHERE asset_id = %s",
        (asset_id,),
        one=True
    )

    if not asset:
        return jsonify({"error": "Asset not found"}), 404

    calibrations = query("""
        SELECT *
        FROM calibration_events
        WHERE asset_id = %s
        ORDER BY performed_at DESC
        LIMIT 20
    """, (asset_id,))

    return jsonify(json_safe({
        "asset": asset,
        "recent_calibrations": calibrations
    }))


@app.get("/api/calibrations")
def calibrations():
    return paged(
        "calibration_events",
        {
            "asset_id": request.args.get("asset_id"),
            "result": request.args.get("result")
        },
        "performed_at"
    )


@app.get("/api/alerts")
def alerts():
    return paged(
        "alerts",
        {
            "alert_state": request.args.get("state"),
            "severity": request.args.get("severity"),
            "asset_id": request.args.get("asset_id")
        },
        "created_at"
    )


@app.get("/api/production-uses")
def production_uses():
    return paged(
        "production_uses",
        {
            "asset_id": request.args.get("asset_id"),
            "decision": request.args.get("decision")
        },
        "used_at"
    )


# ---------------------------------------------------------------------------
# Calibration scheduling and work-order management
# ---------------------------------------------------------------------------

def scheduling_rows(days=90, include_overdue=True):
    """Return each active asset's next due date using its latest calibration.

    For assets never calibrated, the first due date is estimated from the later
    of commissioning and the active plan's effective_from. Such rows are marked
    NEVER_CALIBRATED so users can distinguish estimates from measured history.
    """
    now = datetime.now()
    horizon = now + timedelta(days=days)

    rows = query("""
        WITH active_plans AS (
            SELECT cp.*,
                   ROW_NUMBER() OVER (
                       PARTITION BY cp.asset_id
                       ORDER BY cp.effective_from DESC, cp.plan_id DESC
                   ) AS plan_rank
            FROM calibration_plans cp
            WHERE cp.state = 'ACTIVE'
              AND cp.effective_from <= %s
              AND (cp.effective_to IS NULL OR cp.effective_to >= %s)
        ),
        latest_calibrations AS (
            SELECT ce.*,
                   ROW_NUMBER() OVER (
                       PARTITION BY ce.asset_id
                       ORDER BY ce.performed_at DESC, ce.calibration_id DESC
                   ) AS calibration_rank
            FROM calibration_events ce
            WHERE ce.performed_at <= %s
        )
        SELECT
            a.asset_id,
            a.asset_name,
            a.serial_number,
            a.plant_area,
            a.lifecycle_state,
            ap.plan_id,
            ap.interval_days,
            ap.policy_requires_block,
            ap.requires_certificate,
            lc.calibration_id,
            lc.performed_at AS last_calibrated_at,
            lc.result AS last_calibration_result,
            CASE
                WHEN lc.calibration_id IS NOT NULL THEN
                    COALESCE(
                        lc.calculated_due_at,
                        DATE_ADD(lc.performed_at, INTERVAL ap.interval_days DAY)
                    )
                ELSE
                    DATE_ADD(
                        GREATEST(a.commissioned_at, ap.effective_from),
                        INTERVAL ap.interval_days DAY
                    )
            END AS due_at,
            CASE
                WHEN lc.calibration_id IS NULL THEN 'NEVER_CALIBRATED'
                WHEN lc.result = 'FAIL' THEN 'LAST_CALIBRATION_FAILED'
                WHEN COALESCE(
                    lc.calculated_due_at,
                    DATE_ADD(lc.performed_at, INTERVAL ap.interval_days DAY)
                ) < %s THEN 'OVERDUE'
                WHEN COALESCE(
                    lc.calculated_due_at,
                    DATE_ADD(lc.performed_at, INTERVAL ap.interval_days DAY)
                ) <= %s THEN 'DUE_SOON'
                ELSE 'UPCOMING'
            END AS schedule_state,
            (
                SELECT wo.work_order_id
                FROM work_orders wo
                INNER JOIN work_order_assets woa
                    ON woa.work_order_id = wo.work_order_id
                WHERE woa.asset_id = a.asset_id
                  AND wo.work_type = 'SCHEDULED_CALIBRATION'
                  AND wo.status IN ('OPEN', 'IN_PROGRESS')
                ORDER BY wo.opened_at DESC
                LIMIT 1
            ) AS active_work_order_id
        FROM assets a
        INNER JOIN active_plans ap
            ON ap.asset_id = a.asset_id AND ap.plan_rank = 1
        LEFT JOIN latest_calibrations lc
            ON lc.asset_id = a.asset_id AND lc.calibration_rank = 1
        WHERE a.lifecycle_state = 'ACTIVE'
        ORDER BY due_at ASC, a.asset_id ASC
    """, (now, now, now, now, horizon))

    filtered = []
    for row in rows:
        if not include_overdue and row["due_at"] < now:
            continue
        if row["due_at"] <= horizon or row["due_at"] < now:
            filtered.append(row)

    return filtered


@app.get("/api/scheduling")
def scheduling():
    try:
        days = int(request.args.get("days", 90))
    except ValueError:
        raise ValueError("days must be an integer.")

    if not 1 <= days <= 730:
        raise ValueError("days must be between 1 and 730.")

    state = request.args.get("state", "").upper().strip()
    allowed_states = {
        "", "OVERDUE", "DUE_SOON", "UPCOMING",
        "NEVER_CALIBRATED", "LAST_CALIBRATION_FAILED"
    }
    if state not in allowed_states:
        raise ValueError("Invalid schedule state filter.")

    rows = scheduling_rows(days=days)
    if state:
        rows = [row for row in rows if row["schedule_state"] == state]

    now = datetime.now()
    summary_counts = {
        "total": len(rows),
        "overdue": sum(1 for row in rows if row["due_at"] < now),
        "due_soon": sum(1 for row in rows if row["schedule_state"] == "DUE_SOON"),
        "never_calibrated": sum(1 for row in rows if row["schedule_state"] == "NEVER_CALIBRATED"),
        "with_active_work_order": sum(1 for row in rows if row["active_work_order_id"])
    }

    return jsonify(json_safe({
        "data": rows,
        "summary": summary_counts,
        "window_days": days,
        "generated_at": now
    }))


@app.get("/api/work-orders")
def work_orders():
    page, limit = page_args()
    status = request.args.get("status")
    work_type = request.args.get("work_type")
    asset_id = request.args.get("asset_id")

    allowed_statuses = {"OPEN", "IN_PROGRESS", "COMPLETED", "CANCELLED"}
    allowed_types = {"SCHEDULED_CALIBRATION", "CORRECTIVE_ACTION", "INSPECTION"}

    if status and status not in allowed_statuses:
        raise ValueError("Invalid work-order status.")
    if work_type and work_type not in allowed_types:
        raise ValueError("Invalid work-order type.")

    conditions = []
    params = []
    if status:
        conditions.append("wo.status = %s")
        params.append(status)
    if work_type:
        conditions.append("wo.work_type = %s")
        params.append(work_type)
    if asset_id:
        conditions.append("woa.asset_id = %s")
        params.append(asset_id)

    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    join = """
        FROM work_orders wo
        LEFT JOIN work_order_assets woa
            ON woa.work_order_id = wo.work_order_id
        LEFT JOIN assets a ON a.asset_id = woa.asset_id
    """

    total = query(
        "SELECT COUNT(DISTINCT wo.work_order_id) AS n " + join + where,
        tuple(params),
        one=True
    )["n"]

    records = query("""
        SELECT
            wo.work_order_id,
            wo.calibration_id,
            wo.work_type,
            wo.status,
            wo.opened_at,
            wo.started_at,
            wo.completed_at,
            wo.downtime_minutes,
            GROUP_CONCAT(DISTINCT woa.asset_id ORDER BY woa.asset_id) AS asset_ids,
            GROUP_CONCAT(DISTINCT a.asset_name ORDER BY a.asset_name) AS asset_names
    """ + join + where + """
        GROUP BY wo.work_order_id
        ORDER BY wo.opened_at DESC
        LIMIT %s OFFSET %s
    """, tuple(params + [limit, (page - 1) * limit]))

    return jsonify(json_safe({
        "data": records,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit
        }
    }))


@app.post("/api/scheduling/work-orders")
def create_scheduled_work_order():
    body = request.get_json(silent=True) or {}
    asset_id = body.get("asset_id")
    actor = body.get("actor_reference", "QUALITY_ENGINEER")
    note = body.get("note", "")

    if not isinstance(asset_id, str) or not asset_id.strip():
        return jsonify({"error": "asset_id is required."}), 400
    if not isinstance(actor, str) or not actor.strip() or len(actor.strip()) > 100:
        return jsonify({"error": "actor_reference must contain 1-100 characters."}), 400
    if not isinstance(note, str) or len(note) > 500:
        return jsonify({"error": "note must be 500 characters or fewer."}), 400

    asset_id = asset_id.strip()
    actor = actor.strip()
    now = datetime.now()

    conn = connect()
    try:
        conn.start_transaction()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT asset_id, asset_name, lifecycle_state
            FROM assets
            WHERE asset_id = %s
            FOR UPDATE
        """, (asset_id,))
        asset = cursor.fetchone()

        if not asset:
            conn.rollback()
            return jsonify({"error": "Asset not found."}), 404

        if asset["lifecycle_state"] != "ACTIVE":
            conn.rollback()
            return jsonify({
                "error": "Only ACTIVE assets can receive scheduled calibration work orders."
            }), 409

        # Recompute the due row under the transaction before creating a work order.
        cursor.execute("""
            SELECT
                cp.plan_id,
                cp.interval_days,
                cp.effective_from,
                cp.effective_to,
                (
                    SELECT ce.calculated_due_at
                    FROM calibration_events ce
                    WHERE ce.asset_id = a.asset_id
                    ORDER BY ce.performed_at DESC, ce.calibration_id DESC
                    LIMIT 1
                ) AS stored_due_at,
                (
                    SELECT ce.performed_at
                    FROM calibration_events ce
                    WHERE ce.asset_id = a.asset_id
                    ORDER BY ce.performed_at DESC, ce.calibration_id DESC
                    LIMIT 1
                ) AS last_performed_at,
                (
                    SELECT ce.result
                    FROM calibration_events ce
                    WHERE ce.asset_id = a.asset_id
                    ORDER BY ce.performed_at DESC, ce.calibration_id DESC
                    LIMIT 1
                ) AS last_result
            FROM assets a
            INNER JOIN calibration_plans cp
                ON cp.asset_id = a.asset_id
            WHERE a.asset_id = %s
              AND cp.state = 'ACTIVE'
              AND cp.effective_from <= %s
              AND (cp.effective_to IS NULL OR cp.effective_to >= %s)
            ORDER BY cp.effective_from DESC, cp.plan_id DESC
            LIMIT 1
        """, (asset_id, now, now))
        plan = cursor.fetchone()

        if not plan:
            conn.rollback()
            return jsonify({"error": "No currently effective ACTIVE calibration plan exists for this asset."}), 409

        if plan["last_result"] == "FAIL":
            conn.rollback()
            return jsonify({
                "error": "The latest calibration failed. Use the corrective-action workflow, not scheduled calibration."
            }), 409

        cursor.execute("""
            SELECT wo.work_order_id
            FROM work_orders wo
            INNER JOIN work_order_assets woa
                ON woa.work_order_id = wo.work_order_id
            WHERE woa.asset_id = %s
              AND wo.work_type = 'SCHEDULED_CALIBRATION'
              AND wo.status IN ('OPEN', 'IN_PROGRESS')
            LIMIT 1
        """, (asset_id,))
        existing = cursor.fetchone()

        if existing:
            conn.rollback()
            return jsonify({
                "error": "An active scheduled calibration work order already exists for this asset.",
                "work_order_id": existing["work_order_id"]
            }), 409

        due_at = plan["stored_due_at"]
        if due_at is None and plan["last_performed_at"] is not None:
            due_at = plan["last_performed_at"] + timedelta(days=int(plan["interval_days"]))
        if due_at is None:
            cursor.execute("""
                SELECT GREATEST(commissioned_at, %s) AS initial_reference
                FROM assets WHERE asset_id = %s
            """, (plan["effective_from"], asset_id))
            reference = cursor.fetchone()["initial_reference"]
            due_at = reference + timedelta(days=int(plan["interval_days"]))

        work_order_id = new_id("WO", 30)
        cursor.execute("""
            INSERT INTO work_orders
                (work_order_id, calibration_id, work_type, status,
                 opened_at, started_at, completed_at, downtime_minutes)
            VALUES (%s, NULL, 'SCHEDULED_CALIBRATION', 'OPEN', %s, NULL, NULL, 0)
        """, (work_order_id, now))

        cursor.execute("""
            INSERT INTO work_order_assets (work_order_id, asset_id)
            VALUES (%s, %s)
        """, (work_order_id, asset_id))

        audit_insert(
            cursor,
            "WORK_ORDER",
            work_order_id,
            "SCHEDULED_CALIBRATION_CREATED",
            actor,
            {
                "asset_id": asset_id,
                "plan_id": plan["plan_id"],
                "due_at": due_at,
                "note": note.strip(),
                "work_type": "SCHEDULED_CALIBRATION"
            },
            now
        )

        conn.commit()
        return jsonify(json_safe({
            "message": "Scheduled calibration work order created.",
            "work_order": {
                "work_order_id": work_order_id,
                "asset_id": asset_id,
                "asset_name": asset["asset_name"],
                "plan_id": plan["plan_id"],
                "due_at": due_at,
                "status": "OPEN",
                "opened_at": now,
                "note": note.strip()
            }
        })), 201

    except Exception:
        conn.rollback()
        raise
    finally:
        try:
            cursor.close()
        except UnboundLocalError:
            pass
        conn.close()


@app.patch("/api/work-orders/<work_order_id>/status")
def update_work_order_status(work_order_id):
    body = request.get_json(silent=True) or {}
    new_status = body.get("status")
    actor = body.get("actor_reference", "QUALITY_ENGINEER")
    downtime = body.get("downtime_minutes", 0)

    if new_status not in WORK_ORDER_STATUSES:
        return jsonify({
            "error": "status must be OPEN, IN_PROGRESS, COMPLETED or CANCELLED."
        }), 400
    if not isinstance(actor, str) or not actor.strip() or len(actor.strip()) > 100:
        return jsonify({"error": "actor_reference must contain 1-100 characters."}), 400

    try:
        downtime = int(downtime)
    except (TypeError, ValueError):
        return jsonify({"error": "downtime_minutes must be a non-negative integer."}), 400
    if downtime < 0:
        return jsonify({"error": "downtime_minutes must be a non-negative integer."}), 400

    now = datetime.now()
    conn = connect()
    cursor = None
    try:
        conn.start_transaction()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT work_order_id, status, opened_at, started_at,
                   completed_at, downtime_minutes, work_type
            FROM work_orders
            WHERE work_order_id = %s
            FOR UPDATE
        """, (work_order_id,))
        work_order = cursor.fetchone()

        if not work_order:
            conn.rollback()
            return jsonify({"error": "Work order not found."}), 404

        old_status = work_order["status"]

        if work_order["work_type"] == "CORRECTIVE_ACTION" and new_status == "COMPLETED":
            cursor.execute("""
                SELECT status
                FROM impact_assessments
                WHERE calibration_id = (
                    SELECT calibration_id FROM work_orders WHERE work_order_id = %s
                )
                ORDER BY created_at DESC
                LIMIT 1
                FOR UPDATE
            """, (work_order_id,))
            assessment_state = cursor.fetchone()
            if not assessment_state or assessment_state["status"] != "COMPLETED":
                conn.rollback()
                return jsonify({
                    "error": "Complete the linked impact assessment before completing this corrective-action work order."
                }), 409

        allowed_transitions = {
            "OPEN": {"IN_PROGRESS", "CANCELLED"},
            "IN_PROGRESS": {"COMPLETED", "CANCELLED"},
            "COMPLETED": set(),
            "CANCELLED": set()
        }

        if new_status == old_status:
            conn.rollback()
            return jsonify({"error": f"Work order is already {old_status}."}), 409
        if new_status not in allowed_transitions[old_status]:
            conn.rollback()
            return jsonify({
                "error": f"Invalid status transition: {old_status} to {new_status}."
            }), 409

        started_at = work_order["started_at"]
        completed_at = work_order["completed_at"]
        final_downtime = work_order["downtime_minutes"]

        if new_status == "IN_PROGRESS":
            started_at = now
        elif new_status == "COMPLETED":
            if started_at is None:
                conn.rollback()
                return jsonify({"error": "A work order must be started before it can be completed."}), 409
            completed_at = now
            final_downtime = downtime

        cursor.execute("""
            UPDATE work_orders
            SET status = %s, started_at = %s,
                completed_at = %s, downtime_minutes = %s
            WHERE work_order_id = %s
        """, (
            new_status, started_at, completed_at,
            final_downtime, work_order_id
        ))

        audit_insert(
            cursor,
            "WORK_ORDER",
            work_order_id,
            "STATUS_CHANGED",
            actor.strip(),
            {
                "from_status": old_status,
                "to_status": new_status,
                "downtime_minutes": final_downtime
            },
            now
        )

        conn.commit()
        return jsonify(json_safe({
            "message": "Work-order status updated.",
            "work_order_id": work_order_id,
            "previous_status": old_status,
            "status": new_status,
            "started_at": started_at,
            "completed_at": completed_at,
            "downtime_minutes": final_downtime
        }))

    except Exception:
        conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        conn.close()



# ---------------------------------------------------------------------------
# Corrective action and impact-assessment management
# ---------------------------------------------------------------------------

@app.get("/api/corrective-actions")
def corrective_actions():
    """List assets whose latest calibration failed, with linked follow-up work."""
    page, limit = page_args()
    status = request.args.get("status", "").upper().strip()
    allowed = {"", "OPEN", "IN_PROGRESS", "COMPLETED"}
    if status not in allowed:
        raise ValueError("Invalid impact-assessment status.")

    rows = query("""
        WITH ranked_calibrations AS (
            SELECT ce.*,
                   ROW_NUMBER() OVER (
                       PARTITION BY ce.asset_id
                       ORDER BY ce.performed_at DESC, ce.calibration_id DESC
                   ) AS rn
            FROM calibration_events ce
        )
        SELECT
            a.asset_id,
            a.asset_name,
            a.plant_area,
            a.lifecycle_state,
            rc.calibration_id,
            rc.performed_at AS failed_at,
            rc.absolute_error,
            rc.tolerance_at_test,
            ia.assessment_id,
            ia.status AS assessment_status,
            ia.created_at AS assessment_created_at,
            ia.closed_at AS assessment_closed_at,
            ia.notes AS assessment_notes,
            wo.work_order_id,
            wo.status AS work_order_status,
            wo.opened_at AS work_order_opened_at,
            wo.started_at AS work_order_started_at,
            wo.completed_at AS work_order_completed_at,
            wo.downtime_minutes
        FROM ranked_calibrations rc
        INNER JOIN assets a ON a.asset_id = rc.asset_id
        LEFT JOIN impact_assessments ia
            ON ia.calibration_id = rc.calibration_id
        LEFT JOIN work_orders wo
            ON wo.calibration_id = rc.calibration_id
           AND wo.work_type = 'CORRECTIVE_ACTION'
        WHERE rc.rn = 1
          AND rc.result = 'FAIL'
        ORDER BY rc.performed_at DESC, a.asset_id
    """)

    if status:
        rows = [r for r in rows if r["assessment_status"] == status]

    total = len(rows)
    start = (page - 1) * limit
    return jsonify(json_safe({
        "data": rows[start:start + limit],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit
        },
        "summary": {
            "failed_latest_calibrations": total,
            "without_assessment": sum(1 for r in rows if not r["assessment_id"]),
            "without_corrective_work_order": sum(1 for r in rows if not r["work_order_id"]),
            "open_assessments": sum(1 for r in rows if r["assessment_status"] == "OPEN"),
            "in_progress_assessments": sum(1 for r in rows if r["assessment_status"] == "IN_PROGRESS")
        }
    }))


@app.post("/api/corrective-actions/work-orders")
def create_corrective_work_order():
    """Create a corrective work order and ensure an impact assessment exists.

    The request must identify an asset. The latest calibration for that asset
    must be FAIL. Creation of the work order, asset link, initial assessment,
    and audit records is atomic.
    """
    body = request.get_json(silent=True) or {}
    asset_id = body.get("asset_id")
    requested_calibration_id = body.get("calibration_id")
    actor = body.get("actor_reference", "QUALITY_ENGINEER")
    note = body.get("note", "")

    if not isinstance(asset_id, str) or not asset_id.strip():
        return jsonify({"error": "asset_id is required."}), 400
    if requested_calibration_id is not None and (
        not isinstance(requested_calibration_id, str) or not requested_calibration_id.strip()
    ):
        return jsonify({"error": "calibration_id must be a non-empty string when supplied."}), 400
    if not isinstance(actor, str) or not actor.strip() or len(actor.strip()) > 100:
        return jsonify({"error": "actor_reference must contain 1-100 characters."}), 400
    if not isinstance(note, str) or len(note) > 1000:
        return jsonify({"error": "note must be 1000 characters or fewer."}), 400

    asset_id = asset_id.strip()
    actor = actor.strip()
    now = datetime.now()
    conn = connect()
    cursor = None
    try:
        conn.start_transaction()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT asset_id, asset_name, plant_area, lifecycle_state
            FROM assets WHERE asset_id = %s FOR UPDATE
        """, (asset_id,))
        asset = cursor.fetchone()
        if not asset:
            conn.rollback()
            return jsonify({"error": "Asset not found."}), 404
        if asset["lifecycle_state"] == "RETIRED":
            conn.rollback()
            return jsonify({"error": "Retired assets cannot receive corrective work orders."}), 409

        cursor.execute("""
            SELECT calibration_id, asset_id, result, performed_at,
                   absolute_error, tolerance_at_test
            FROM calibration_events
            WHERE asset_id = %s
            ORDER BY performed_at DESC, calibration_id DESC
            LIMIT 1 FOR UPDATE
        """, (asset_id,))
        latest = cursor.fetchone()
        if not latest:
            conn.rollback()
            return jsonify({"error": "No calibration event exists for this asset."}), 409
        if latest["result"] != "FAIL":
            conn.rollback()
            return jsonify({"error": "Corrective action can only be opened for an asset whose latest calibration failed."}), 409
        if requested_calibration_id and requested_calibration_id.strip() != latest["calibration_id"]:
            conn.rollback()
            return jsonify({"error": "The supplied calibration_id is not this asset's latest calibration event."}), 409

        cursor.execute("""
            SELECT work_order_id, status
            FROM work_orders
            WHERE calibration_id = %s
              AND work_type = 'CORRECTIVE_ACTION'
              AND status IN ('OPEN', 'IN_PROGRESS')
            LIMIT 1 FOR UPDATE
        """, (latest["calibration_id"],))
        existing = cursor.fetchone()
        if existing:
            conn.rollback()
            return jsonify({
                "error": "An active corrective-action work order already exists for this failed calibration.",
                "work_order_id": existing["work_order_id"]
            }), 409

        work_order_id = new_id("WO", 30)
        cursor.execute("""
            INSERT INTO work_orders
                (work_order_id, calibration_id, work_type, status,
                 opened_at, started_at, completed_at, downtime_minutes)
            VALUES (%s, %s, 'CORRECTIVE_ACTION', 'OPEN', %s, NULL, NULL, 0)
        """, (work_order_id, latest["calibration_id"], now))
        cursor.execute("""
            INSERT INTO work_order_assets (work_order_id, asset_id)
            VALUES (%s, %s)
        """, (work_order_id, asset_id))

        cursor.execute("""
            SELECT assessment_id, status
            FROM impact_assessments
            WHERE calibration_id = %s
            ORDER BY created_at DESC
            LIMIT 1 FOR UPDATE
        """, (latest["calibration_id"],))
        assessment = cursor.fetchone()
        created_assessment = False
        if not assessment:
            assessment_id = new_id("IA", 30)
            cursor.execute("""
                INSERT INTO impact_assessments
                    (assessment_id, calibration_id, status, created_at, closed_at, notes)
                VALUES (%s, %s, 'OPEN', %s, NULL, %s)
            """, (
                assessment_id,
                latest["calibration_id"],
                now,
                note.strip() or "Automatically opened when corrective action was initiated."
            ))
            created_assessment = True
        else:
            assessment_id = assessment["assessment_id"]

        audit_insert(
            cursor, "WORK_ORDER", work_order_id,
            "CORRECTIVE_ACTION_CREATED", actor,
            {
                "asset_id": asset_id,
                "calibration_id": latest["calibration_id"],
                "assessment_id": assessment_id,
                "work_type": "CORRECTIVE_ACTION",
                "note": note.strip()
            }, now
        )
        if created_assessment:
            audit_insert(
                cursor, "IMPACT_ASSESSMENT", assessment_id,
                "IMPACT_ASSESSMENT_CREATED", actor,
                {"calibration_id": latest["calibration_id"], "asset_id": asset_id}, now
            )

        conn.commit()
        return jsonify(json_safe({
            "message": "Corrective-action work order created.",
            "work_order": {
                "work_order_id": work_order_id,
                "asset_id": asset_id,
                "asset_name": asset["asset_name"],
                "calibration_id": latest["calibration_id"],
                "status": "OPEN",
                "work_type": "CORRECTIVE_ACTION",
                "opened_at": now
            },
            "impact_assessment": {
                "assessment_id": assessment_id,
                "status": "OPEN" if created_assessment else assessment["status"],
                "created": created_assessment
            }
        })), 201
    except Exception:
        conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        conn.close()


@app.patch("/api/impact-assessments/<assessment_id>")
def update_impact_assessment(assessment_id):
    """Update investigation status and notes with an immutable audit entry."""
    body = request.get_json(silent=True) or {}
    new_status = body.get("status")
    actor = body.get("actor_reference", "QUALITY_ENGINEER")
    notes = body.get("notes")

    if new_status not in {"OPEN", "IN_PROGRESS", "COMPLETED"}:
        return jsonify({"error": "status must be OPEN, IN_PROGRESS or COMPLETED."}), 400
    if not isinstance(actor, str) or not actor.strip() or len(actor.strip()) > 100:
        return jsonify({"error": "actor_reference must contain 1-100 characters."}), 400
    if notes is not None and (not isinstance(notes, str) or len(notes) > 1000):
        return jsonify({"error": "notes must be a string of 1000 characters or fewer."}), 400

    now = datetime.now()
    conn = connect()
    cursor = None
    try:
        conn.start_transaction()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT assessment_id, calibration_id, status, notes, closed_at
            FROM impact_assessments
            WHERE assessment_id = %s
            FOR UPDATE
        """, (assessment_id,))
        assessment = cursor.fetchone()
        if not assessment:
            conn.rollback()
            return jsonify({"error": "Impact assessment not found."}), 404

        transitions = {
            "OPEN": {"IN_PROGRESS"},
            "IN_PROGRESS": {"COMPLETED"},
            "COMPLETED": set()
        }
        if new_status == assessment["status"]:
            conn.rollback()
            return jsonify({"error": f"Impact assessment is already {new_status}."}), 409
        if new_status not in transitions[assessment["status"]]:
            conn.rollback()
            return jsonify({
                "error": f"Invalid assessment transition: {assessment['status']} to {new_status}."
            }), 409

        updated_notes = assessment["notes"] if notes is None else notes.strip()
        closed_at = now if new_status == "COMPLETED" else None
        cursor.execute("""
            UPDATE impact_assessments
            SET status = %s, notes = %s, closed_at = %s
            WHERE assessment_id = %s
        """, (new_status, updated_notes, closed_at, assessment_id))
        audit_insert(
            cursor, "IMPACT_ASSESSMENT", assessment_id,
            "STATUS_CHANGED", actor.strip(),
            {
                "calibration_id": assessment["calibration_id"],
                "from_status": assessment["status"],
                "to_status": new_status,
                "notes_updated": notes is not None
            }, now
        )
        conn.commit()
        return jsonify(json_safe({
            "message": "Impact assessment updated.",
            "assessment_id": assessment_id,
            "calibration_id": assessment["calibration_id"],
            "previous_status": assessment["status"],
            "status": new_status,
            "closed_at": closed_at,
            "notes": updated_notes
        }))
    except Exception:
        conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        conn.close()


def evaluate_authorization(asset_id, proposed_at):
    """Evaluate a proposed production use without writing to the database."""

    asset = query("""
        SELECT *
        FROM assets
        WHERE asset_id = %s
    """, (asset_id,), one=True)

    if not asset:
        return {
            "decision": "BLOCK",
            "reason_code": "ASSET_NOT_FOUND",
            "reason": "The requested asset does not exist.",
            "asset_id": asset_id
        }

    base = {
        "asset_id": asset_id,
        "asset_name": asset["asset_name"],
        "plant_area": asset["plant_area"],
        "proposed_at": proposed_at.isoformat(sep=" "),
        "lifecycle_state": asset["lifecycle_state"]
    }

    def blocked(code, reason, **details):
        return {
            **base,
            "decision": "BLOCK",
            "reason_code": code,
            "reason": reason,
            **details
        }

    if asset["lifecycle_state"] != "ACTIVE":
        return blocked(
            "ASSET_NOT_ACTIVE",
            "Only active instruments may be used in production."
        )

    if proposed_at < asset["commissioned_at"]:
        return blocked(
            "NOT_YET_COMMISSIONED",
            "The proposed use is before the instrument commissioning date."
        )

    if asset["retired_at"] and proposed_at > asset["retired_at"]:
        return blocked(
            "ASSET_RETIRED",
            "The proposed use is after the instrument retirement date."
        )

    calibration = query("""
        SELECT
            ce.calibration_id,
            ce.asset_id,
            ce.plan_id,
            ce.performed_at,
            ce.result,
            ce.calculated_due_at,
            ce.recorded_due_at,
            cp.interval_days,
            cp.effective_from,
            cp.effective_to,
            cp.policy_requires_block,
            cp.requires_certificate,
            cp.state AS plan_state
        FROM calibration_events ce
        INNER JOIN calibration_plans cp
            ON cp.plan_id = ce.plan_id
            AND cp.asset_id = ce.asset_id
        WHERE ce.asset_id = %s
          AND ce.performed_at <= %s
        ORDER BY ce.performed_at DESC, ce.calibration_id DESC
        LIMIT 1
    """, (asset_id, proposed_at), one=True)

    if not calibration:
        return blocked(
            "NO_CALIBRATION",
            "No calibration exists before the proposed production-use time."
        )

    details = {
        "calibration_id": calibration["calibration_id"],
        "calibration_result": calibration["result"],
        "calibration_performed_at": calibration["performed_at"],
        "plan_id": calibration["plan_id"]
    }

    if calibration["result"] != "PASS":
        return blocked(
            "CALIBRATION_FAILED",
            "The latest calibration failed. An emergency extension cannot override a failed calibration.",
            **details
        )

    if calibration["plan_state"] == "CANCELLED":
        return blocked(
            "CALIBRATION_PLAN_CANCELLED",
            "The calibration was performed under a cancelled plan.",
            **details
        )

    performed_at = calibration["performed_at"]

    if performed_at < calibration["effective_from"] or (
        calibration["effective_to"]
        and performed_at > calibration["effective_to"]
    ):
        return blocked(
            "CALIBRATION_OUTSIDE_PLAN",
            "The calibration was performed outside its plan's effective period.",
            **details
        )

    due_at = calibration["calculated_due_at"]

    if due_at is None:
        due_at = performed_at + timedelta(
            days=int(calibration["interval_days"])
        )

    details["due_at"] = due_at
    details["recorded_due_at"] = calibration["recorded_due_at"]
    details["overdue"] = due_at < proposed_at

    certificate = query("""
        SELECT
            certificate_id,
            calibration_id,
            asset_id,
            issued_at,
            valid_until,
            certificate_status
        FROM certificates
        WHERE calibration_id = %s
        ORDER BY issued_at DESC
        LIMIT 1
    """, (calibration["calibration_id"],), one=True)

    requires_certificate = bool(calibration["requires_certificate"])

    if certificate:
        details["certificate_id"] = certificate["certificate_id"]

        if certificate["asset_id"] != asset_id:
            return blocked(
                "CERTIFICATE_ASSET_MISMATCH",
                "The certificate references a different asset.",
                **details
            )

        if certificate["certificate_status"] != "ISSUED":
            return blocked(
                "CERTIFICATE_NOT_ISSUED",
                "The calibration certificate is revoked or not issued.",
                **details
            )

        if not (
            certificate["issued_at"] <= proposed_at <= certificate["valid_until"]
        ):
            return blocked(
                "CERTIFICATE_OUTSIDE_VALIDITY",
                "The certificate is not valid at the proposed production-use time.",
                **details
            )

    elif requires_certificate:
        return blocked(
            "CERTIFICATE_MISSING",
            "This calibration plan requires an issued certificate, but none exists.",
            **details
        )

    active_work_order = query("""
        SELECT
            wo.work_order_id,
            wo.work_type,
            wo.status
        FROM work_orders wo
        INNER JOIN work_order_assets woa
            ON woa.work_order_id = wo.work_order_id
        WHERE woa.asset_id = %s
          AND wo.status IN ('OPEN', 'IN_PROGRESS')
          AND wo.opened_at <= %s
          AND (wo.completed_at IS NULL OR wo.completed_at > %s)
        LIMIT 1
    """, (asset_id, proposed_at, proposed_at), one=True)

    if active_work_order:
        return blocked(
            "ACTIVE_WORK_ORDER",
            "The instrument has an open or in-progress work order.",
            **details,
            work_order=active_work_order
        )

    if due_at < proposed_at:
        extension = query("""
            SELECT
                extension_id,
                approved_from,
                approved_until,
                approver_reference,
                reason
            FROM emergency_extensions
            WHERE asset_id = %s
              AND approval_state = 'APPROVED'
              AND approved_from <= %s
              AND approved_until >= %s
            ORDER BY approved_until DESC
            LIMIT 1
        """, (asset_id, proposed_at, proposed_at), one=True)

        if extension:
            return {
                **base,
                **details,
                "decision": "CONDITIONAL_ALLOW",
                "reason_code": "APPROVED_EMERGENCY_EXTENSION",
                "reason": "The instrument is overdue, but an approved emergency extension covers the proposed use.",
                "extension": extension
            }

        if calibration["policy_requires_block"]:
            return blocked(
                "CALIBRATION_OVERDUE",
                "The calibration due date has passed and no valid approved emergency extension covers this use.",
                **details
            )

    return {
        **base,
        **details,
        "decision": "ALLOW",
        "reason_code": "CALIBRATION_COMPLIANT",
        "reason": "The asset, calibration and applicable certificate satisfy the authorization checks."
    }


@app.post("/api/authorization/evaluate")
def authorization_evaluate():
    body = request.get_json(silent=True) or {}

    asset_id = body.get("asset_id")
    proposed_value = body.get("proposed_at")

    if not asset_id or not isinstance(asset_id, str):
        return jsonify({
            "error": "asset_id is required."
        }), 400

    if proposed_value:
        try:
            proposed_at = datetime.fromisoformat(
                proposed_value.replace("Z", "+00:00")
            )
            if proposed_at.tzinfo is not None:
                proposed_at = proposed_at.replace(tzinfo=None)
        except (ValueError, AttributeError):
            return jsonify({
                "error": "proposed_at must be an ISO date/time, e.g. 2026-10-31 14:30:00."
            }), 400
    else:
        proposed_at = datetime.now()

    result = evaluate_authorization(asset_id.strip(), proposed_at)

    return jsonify(json_safe({
        "evaluation_type": "NON_PERSISTENT",
        "result": result,
        "evaluated_at": datetime.now()
    }))


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("API_PORT", "5000")),
        debug=False
    )