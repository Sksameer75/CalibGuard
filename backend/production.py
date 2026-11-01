"""Historical, deterministic production-use policy engine."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta
import random

FMT = '%Y-%m-%d %H:%M:%S'
START = datetime(2025, 10, 30)

def dt(value):
    return datetime.strptime(value, FMT)

def evaluate_use(asset, used_at, events, certificates, extensions, plan):
    """Evaluate only evidence effective at the usage timestamp.

    An approved extension may override an expired due date, never a failed
    calibration, missing certificate, or absent passing calibration.
    """
    if used_at < dt(asset['commissioned_at']) or (asset['retired_at'] and used_at >= dt(asset['retired_at'])):
        return 'BLOCK', 'ASSET_NOT_IN_SERVICE'
    past = [e for e in events if dt(e['performed_at']) <= used_at]
    if not past:
        return 'BLOCK', 'NO_CALIBRATION'
    latest = max(past, key=lambda e: (e['performed_at'], e['calibration_id']))
    if latest['result'] != 'PASS':
        return 'BLOCK', 'FAILED_CALIBRATION'
    if dt(plan['effective_from']) > used_at or (plan['effective_to'] and used_at > dt(plan['effective_to'])):
        return 'BLOCK', 'PLAN_NOT_EFFECTIVE'
    if int(plan['requires_certificate']):
        cert = certificates.get(latest['calibration_id'])
        if not cert or cert['certificate_status'] != 'ISSUED' or dt(cert['issued_at']) > used_at or dt(cert['valid_until']) < used_at or cert['asset_id'] != asset['asset_id']:
            return 'BLOCK', 'CERTIFICATE_INVALID'
    due = dt(latest['calculated_due_at'])
    if used_at <= due:
        return 'ALLOW', 'VALID_CALIBRATION'
    if not int(plan['policy_requires_block']):
        return 'ALLOW', 'OVERDUE_NONBLOCKING_POLICY'
    approved = any(x['approval_state'] == 'APPROVED' and dt(x['approved_from']) <= used_at <= dt(x['approved_until']) and dt(x['approved_from']) - timedelta(days=1) <= used_at for x in extensions)
    if approved:
        return 'CONDITIONAL_ALLOW', 'APPROVED_EXTENSION'
    return 'BLOCK', 'OVERDUE_NO_EXCEPTION'

def generate_production_uses(tables, count, seed):
    rng = random.Random(seed + 53)
    assets = tables['assets']
    if not assets or count < 0:
        raise ValueError('invalid assets or count')
    by_asset = defaultdict(list)
    for e in tables['calibration_events']:
        by_asset[e['asset_id']].append(e)
    for events in by_asset.values():
        events.sort(key=lambda x: (x['performed_at'], x['calibration_id']))
    certs = {c['calibration_id']: c for c in tables['certificates']}
    extensions = defaultdict(list)
    for x in tables['emergency_extensions']:
        extensions[x['asset_id']].append(x)
    plans = {p['asset_id']: p for p in tables['calibration_plans']}
    rows, alerts = [], []
    # Unique per-asset timestamps, including second-level variation.
    seen = set()
    targeted = []
    for ext in tables['emergency_extensions']:
        if ext['approval_state'] == 'APPROVED':
            target = dt(ext['approved_from']) + timedelta(hours=12)
            if target < dt(ext['approved_until']) and START <= target < START + timedelta(days=365):
                targeted.append((ext['asset_id'], target))
    asset_by_id = {a['asset_id']: a for a in assets}
    for i in range(count):
        if i < len(targeted):
            aid, used = targeted[i]
            asset = asset_by_id[aid]
            offset = int((used - START).total_seconds())
            if (aid, offset) in seen:
                raise AssertionError('duplicate targeted timestamp')
            seen.add((aid, offset))
        else:
            asset = assets[rng.randrange(len(assets))]
        aid = asset['asset_id']
        if i >= len(targeted):
            while True:
                offset = rng.randrange(365 * 24 * 3600)
                key = (aid, offset)
                if key not in seen:
                    seen.add(key)
                    break
            used = START + timedelta(seconds=offset)
        decision, reason = evaluate_use(asset, used, by_asset[aid], certs, extensions[aid], plans[aid])
        # Rare operational noncompliance: execution occurs despite a BLOCK decision.
        executed = decision != 'BLOCK' or rng.random() < 0.025
        use_id = f"USE-{aid}-{used:%Y%m%d%H%M%S}"
        row = dict(use_id=use_id, asset_id=aid, used_at=used.strftime(FMT),
                   batch_reference=f'BATCH-{i+1:07d}', decision=decision,
                   was_executed=int(executed), evaluated_at=(used + timedelta(seconds=1)).strftime(FMT))
        rows.append(row)
        if decision == 'BLOCK':
            alerts.append(dict(alert_id=f'ALT-USE-{len(alerts)+1:07d}', asset_id=aid,
                               calibration_id='', use_id=use_id, issue_type=reason,
                               severity='CRITICAL' if executed else 'WARNING',
                               alert_state='OPEN', created_at=row['evaluated_at']))
    rows.sort(key=lambda x: (x['used_at'], x['use_id']))
    return rows, alerts
