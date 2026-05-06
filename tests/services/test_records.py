from datetime import date
from types import SimpleNamespace


def site_history_row(**overrides):
    row = {
        "site_id": 71,
        "cert_id": 100,
        "result": "Pass",
        "resolution_date": None,
        "reg_title": "USDA Organic",
        "reg_description": "Organic certification",
        "certifier_org_name": "Org A",
        "inspection_date": date(2026, 4, 1),
        "finding_id": 1,
        "finding": "Missing document",
        "rule_index": "7 CFR 205.201",
        "rule_title": "Organic plan",
        "rule_description": "Producer must maintain an organic system plan.",
    }
    row.update(overrides)
    return row


def finding_row(**overrides):
    row = {
        "Finding": SimpleNamespace(
            id=1,
            finding="Missing document",
        ),
        "Certification": SimpleNamespace(
            id=100,
            site_id=71,
            resolution_date=date(2026, 4, 15),
        ),
        "Regulation": SimpleNamespace(
            title="USDA Organic",
        ),
        "Rule": SimpleNamespace(
            id=5,
            rule_index="7 CFR 205.201",
            title="Organic plan",
            description="Producer must maintain an organic system plan.",
        ),
    }
    row.update(overrides)
    return row
