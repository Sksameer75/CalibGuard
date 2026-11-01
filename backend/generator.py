"""Deterministic master-data generator for CalibGuard.

Usage:
    python -m backend.generator --scale starter --seed 20261022
    python -m backend.generator --scale full --seed 20261022

Generates master, calibration, operational and production-use records.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from .production import generate_production_uses

START = datetime(2025, 10, 30, 0, 0, 0)
TYPES = [
    ("Pressure Gauge", "bar", "0.2000", 90),
    ("Temperature Sensor", "C", "0.5000", 180),
    ("Flow Meter", "L/min", "1.0000", 90),
    ("Weighing Scale", "kg", "0.0100", 180),
    ("Humidity Sensor", "%RH", "2.0000", 90),
    ("Voltage Meter", "V", "0.0500", 180),
    ("Torque Wrench", "Nm", "0.5000", 90),
    ("Level Transmitter", "m", "0.0200", 180),
]
AREAS = ["Assembly", "Quality Lab", "Packaging", "Utilities", "Production Line A", "Production Line B"]


def timestamp(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def generate_master_data(asset_count: int, seed: int) -> dict[str, list[dict]]:
    rng = random.Random(seed)
    types = [
        dict(instrument_type_id=f"TYPE-{i:04d}", type_name=name,
             measurement_unit=unit, tolerance=tolerance,
             default_interval_days=interval)
        for i, (name, unit, tolerance, interval) in enumerate(TYPES, 1)
    ]
    suppliers = [
        dict(supplier_id=f"SUP-{i:04d}", supplier_name=f"Synthetic Supplier {i:02d}",
             supplier_kind=("MANUFACTURER", "CALIBRATION_LAB", "BOTH")[(i - 1) % 3],
             accreditation_reference=f"SYNTH-ACC-{i:04d}" if i % 3 != 1 else "")
        for i in range(1, 17)
    ]
    assets, plans = [], []
    for i in range(1, asset_count + 1):
        asset_id = f"AST-{i:06d}"
        typ = rng.choice(types)
        commissioned = START - timedelta(days=rng.randint(30, 1000))
        interval = int(typ["default_interval_days"])
        if rng.random() < 0.12:
            interval = max(30, interval // 2)
        assets.append(dict(
            asset_id=asset_id, instrument_type_id=typ["instrument_type_id"],
            supplier_id=rng.choice(suppliers)["supplier_id"],
            serial_number=f"CG-SYN-{i:07d}", asset_name=f"{typ['type_name']} {i:04d}",
            plant_area=rng.choice(AREAS), commissioned_at=timestamp(commissioned),
            retired_at="", lifecycle_state="ACTIVE"))
        plans.append(dict(
            plan_id=f"PLAN-{i:06d}", asset_id=asset_id,
            interval_days=interval, effective_from=timestamp(commissioned),
            effective_to="", policy_requires_block=1,
            requires_certificate=1, state="ACTIVE"))
    return {"instrument_types": types, "suppliers": suppliers,
            "assets": assets, "calibration_plans": plans}



def generate_calibration_data(master: dict[str, list[dict]], event_count: int, seed: int) -> dict[str, list[dict]]:
    """Create chronologically ordered calibrations with calculated outcomes.

    Every asset receives at least two events in full mode (5000 / 2000).
    Dates span 2025-10-30 through 2026-10-29, a fixed one-year window.
    Missing certificates are normal exception coverage; labelled anomalies follow later.
    """
    rng = random.Random(seed + 17)
    assets = master["assets"]
    if event_count < len(assets):
        raise ValueError("event_count must be >= number of assets")
    types = {t["instrument_type_id"]: t for t in master["instrument_types"]}
    plans = {p["asset_id"]: p for p in master["calibration_plans"]}
    counts = [event_count // len(assets)] * len(assets)
    for i in range(event_count % len(assets)):
        counts[i] += 1
    events, certificates = [], []
    for index, asset in enumerate(assets):
        plan = plans[asset["asset_id"]]
        typ = types[asset["instrument_type_id"]]
        tolerance = Decimal(typ["tolerance"])
        n = counts[index]
        # Spread events throughout the year, with reproducible bounded jitter.
        for seq in range(1, n + 1):
            day = min(364, max(0, round((seq - 0.5) * 365 / n) + rng.randint(-12, 12)))
            performed = START + timedelta(days=day, hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
            reference = Decimal('100.0000')
            # A measurement is generated; the result is *derived* from its error.
            multiplier = Decimal(rng.randint(-140, 140)) / Decimal(100)
            measured = (reference + tolerance * multiplier).quantize(Decimal('0.0001'))
            error = abs(measured - reference)
            result = 'PASS' if error <= tolerance else 'FAIL'
            due = performed + timedelta(days=int(plan['interval_days'])) if result == 'PASS' else None
            calibration_id = f"CAL-{asset['asset_id']}-2026-{seq:06d}"
            event = dict(calibration_id=calibration_id, asset_id=asset['asset_id'],
                         plan_id=plan['plan_id'], supplier_id=asset['supplier_id'],
                         performed_at=timestamp(performed), reference_value=f"{reference:.4f}",
                         measured_value=f"{measured:.4f}", absolute_error=f"{error:.4f}",
                         tolerance_at_test=f"{tolerance:.4f}", result=result,
                         calculated_due_at=timestamp(due) if due else '',
                         recorded_due_at=timestamp(due) if due else '',
                         recorded_at=timestamp(performed + timedelta(minutes=15)))
            events.append(event)
            # Certificates are issued only for passing calibrations, with some gaps.
            if result == 'PASS' and rng.random() >= 0.035:
                certificates.append(dict(
                    certificate_id=f"CERT-{calibration_id}", calibration_id=calibration_id,
                    asset_id=asset['asset_id'],
                    issued_at=timestamp(performed + timedelta(minutes=10)),
                    valid_until=timestamp(due), certificate_status='ISSUED',
                    document_reference=f"synthetic://certificates/{calibration_id}.pdf"))
    events.sort(key=lambda e: (e['performed_at'], e['calibration_id']))
    return {'calibration_events': events, 'certificates': certificates}



def generate_operations(master: dict[str, list[dict]], calibration: dict[str, list[dict]], seed: int) -> dict[str, list[dict]]:
    """Generate linked operational records; preserve failure history and exception events."""
    rng = random.Random(seed + 31)
    events = calibration['calibration_events']
    plans = {p['asset_id']: p for p in master['calibration_plans']}
    work_orders, bridges, assessments, extensions, alerts, audits, lifecycle = ([] for _ in range(7))
    wo_seq = assessment_seq = extension_seq = alert_seq = audit_seq = life_seq = 0

    def audit(entity: str, identifier: str, action: str, when: str, detail: dict) -> None:
        nonlocal audit_seq
        audit_seq += 1
        audits.append(dict(audit_id=f'AUD-{audit_seq:08d}', entity_name=entity,
                           entity_id=identifier, action=action, actor_reference='synthetic-generator',
                           occurred_at=when, details=json.dumps(detail, sort_keys=True, separators=(',', ':'))))

    def transition(entity: str, identifier: str, old: str, new: str, when: str, reason: str) -> None:
        nonlocal life_seq
        life_seq += 1
        lifecycle.append(dict(lifecycle_event_id=f'LIFE-{life_seq:08d}', entity_name=entity,
                              entity_id=identifier, from_state=old, to_state=new,
                              occurred_at=when, actor_reference='synthetic-generator', reason=reason))
        audit(entity, identifier, 'STATE_TRANSITION', when, {'from': old, 'to': new, 'reason': reason})

    for event in events:
        asset_id = event['asset_id']
        performed = datetime.strptime(event['performed_at'], '%Y-%m-%d %H:%M:%S')
        is_fail = event['result'] == 'FAIL'
        wo_seq += 1
        wo_id = f'WO-2026-{wo_seq:06d}'
        opened = performed - timedelta(hours=4)
        started = performed - timedelta(minutes=45)
        finished = performed + timedelta(minutes=45 if not is_fail else 120)
        work_orders.append(dict(work_order_id=wo_id, calibration_id=event['calibration_id'],
                                work_type='CORRECTIVE_ACTION' if is_fail else 'SCHEDULED_CALIBRATION',
                                status='COMPLETED', opened_at=timestamp(opened), started_at=timestamp(started),
                                completed_at=timestamp(finished),
                                downtime_minutes=int((finished - started).total_seconds() // 60)))
        bridges.append(dict(work_order_id=wo_id, asset_id=asset_id))
        transition('WORK_ORDER', wo_id, '', 'OPEN', timestamp(opened), 'scheduled')
        transition('WORK_ORDER', wo_id, 'OPEN', 'IN_PROGRESS', timestamp(started), 'work started')
        transition('WORK_ORDER', wo_id, 'IN_PROGRESS', 'COMPLETED', timestamp(finished), 'work completed')
        if is_fail:
            assessment_seq += 1
            aid = f'IMP-{assessment_seq:06d}'
            assessments.append(dict(assessment_id=aid, calibration_id=event['calibration_id'],
                                    status='OPEN', created_at=timestamp(performed + timedelta(minutes=5)),
                                    closed_at='', notes='Synthetic impact review of prior production batches'))
            transition('IMPACT_ASSESSMENT', aid, '', 'OPEN', timestamp(performed + timedelta(minutes=5)), 'failed calibration')
            alert_seq += 1
            alerts.append(dict(alert_id=f'ALT-{alert_seq:07d}', asset_id=asset_id,
                               calibration_id=event['calibration_id'], use_id='',
                               issue_type='CALIBRATION_FAILED', severity='CRITICAL',
                               alert_state='OPEN', created_at=timestamp(performed + timedelta(minutes=5))))

    # Build extensions around genuine overdue PASS intervals. The certificate
    # remains valid during the approved exception, but the calibration due date
    # is NOT altered. This distinguishes certificate validity from due policy.
    from collections import defaultdict
    by_asset = defaultdict(list)
    for event in events:
        by_asset[event['asset_id']].append(event)
    cert_by_cal = {c['calibration_id']: c for c in calibration['certificates']}
    window_end = START + timedelta(days=365)
    for index, asset in enumerate(master['assets']):
        if index % 17 != 0:
            continue
        asset_id = asset['asset_id']
        history = sorted(by_asset[asset_id], key=lambda e: (e['performed_at'], e['calibration_id']))
        chosen = None
        for position, event in enumerate(history):
            if event['result'] != 'PASS' or event['calibration_id'] not in cert_by_cal:
                continue
            due = datetime.strptime(event['calculated_due_at'], '%Y-%m-%d %H:%M:%S')
            next_cal = (datetime.strptime(history[position + 1]['performed_at'], '%Y-%m-%d %H:%M:%S')
                        if position + 1 < len(history) else window_end)
            # Require a real overdue gap within the fixed simulation year.
            if due + timedelta(days=4) < min(next_cal, window_end):
                chosen = (event, due)
                break
        if chosen is None:
            continue
        event, due = chosen
        base = due + timedelta(hours=1)
        until = min(due + timedelta(days=3), window_end - timedelta(minutes=1))
        # Explicit policy assumption for synthetic data: document validity and
        # calibration due date are independent; the certificate is still issued
        # for this PASS and valid through the approved exception window.
        cert_by_cal[event['calibration_id']]['valid_until'] = timestamp(until)
        extension_seq += 1
        eid = f'EXT-{extension_seq:06d}'
        extensions.append(dict(extension_id=eid, asset_id=asset_id,
                               approved_from=timestamp(base), approved_until=timestamp(until),
                               approval_state='APPROVED', approver_reference='quality-engineer-synthetic',
                               reason='Controlled overdue continuity exception; certificate valid'))
        transition('EMERGENCY_EXTENSION', eid, '', 'REQUESTED', timestamp(base - timedelta(days=2)), 'requested')
        transition('EMERGENCY_EXTENSION', eid, 'REQUESTED', 'APPROVED', timestamp(base - timedelta(days=1)), 'quality approval')
    return dict(work_orders=work_orders, work_order_assets=bridges,
                impact_assessments=assessments, emergency_extensions=extensions,
                alerts=alerts, audit_records=audits, lifecycle_events=lifecycle)


def generate_dataset(asset_count: int, event_count: int, seed: int, use_count: int = 0) -> dict[str, list[dict]]:
    master = generate_master_data(asset_count, seed)
    calibration = generate_calibration_data(master, event_count, seed)
    master.update(calibration)
    master.update(generate_operations(master, calibration, seed))
    if use_count:
        uses, use_alerts = generate_production_uses(master, use_count, seed)
        master["production_uses"] = uses
        master["alerts"].extend(use_alerts)
    return master


def export_data(tables: dict[str, list[dict]], output: Path, seed: int, scale: str) -> None:
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"seed": seed, "scale": scale, "generator_stage": "production_use_authorization_corrected",
                "synthetic": True, "files": {}}
    for name, rows in tables.items():
        file = output / f"{name}.csv"
        with file.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        manifest["files"][file.name] = {
            "rows": len(rows), "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate CalibGuard calibration dataset")
    parser.add_argument("--scale", choices=["starter", "full"], default="starter")
    parser.add_argument("--seed", type=int, default=20261022)
    parser.add_argument("--output", type=Path, default=Path("data/generated"))
    args = parser.parse_args()
    count = 40 if args.scale == "starter" else 2000
    events = 100 if args.scale == "starter" else 5000
    use_count = 1000 if args.scale == "starter" else 100000
    export_data(generate_dataset(count, events, args.seed, use_count), args.output, args.seed, args.scale)


if __name__ == "__main__":
    main()
