import csv
from collections import Counter, defaultdict
from datetime import datetime
from backend.production import evaluate_use

FMT = "%Y-%m-%d %H:%M:%S"


def read(name):
    with open(
        f"data/generated/{name}.csv",
        newline="",
        encoding="utf-8"
    ) as file:
        return list(csv.DictReader(file))


assets = {r["asset_id"]: r for r in read("assets")}
plans = {r["asset_id"]: r for r in read("calibration_plans")}
certs = {r["calibration_id"]: r for r in read("certificates")}

events = defaultdict(list)

for row in read("calibration_events"):
    events[row["asset_id"]].append(row)

extensions = defaultdict(list)

for row in read("emergency_extensions"):
    extensions[row["asset_id"]].append(row)

reasons = Counter()
overlaps = 0

for use in read("production_uses"):
    asset_id = use["asset_id"]

    applicable = [
        extension
        for extension in extensions[asset_id]
        if extension["approval_state"] == "APPROVED"
        and extension["approved_from"] <= use["used_at"]
        <= extension["approved_until"]
    ]

    if not applicable:
        continue

    overlaps += 1

    decision, reason = evaluate_use(
        assets[asset_id],
        datetime.strptime(use["used_at"], FMT),
        events[asset_id],
        certs,
        extensions[asset_id],
        plans[asset_id]
    )

    reasons[(decision, reason)] += 1

print("\nTotal approved extension overlaps:", overlaps)

print("\nDecision breakdown:")

for (decision, reason), count in sorted(reasons.items()):
    print(f"{decision:20} {reason:30} {count}")