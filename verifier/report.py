import json
from pathlib import Path

from .data import load_fixture

REPORT = "invoice-audit.json"


def read_report(path: Path) -> list:
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, list):
        raise TypeError("Report must be a JSON array")
    return report


def expected_rows(fixture: dict) -> dict:
    seen = set()
    expected = {}
    orders = fixture["purchase_orders"]
    for row in sorted(fixture["invoices"], key=lambda invoice: invoice["submission_sequence"]):
        reasons = []
        identity = row["vendor_id"], row["vendor_invoice_number"]
        if identity in seen:
            reasons.append("DUPLICATE_SUBMISSION")
        seen.add(identity)
        amount = row["amount_cents"]
        authorized = orders.get(row["purchase_order_id"])
        if authorized is None:
            reasons.append("MISSING_PURCHASE_ORDER")
        elif amount - authorized > fixture["tolerance_cents"]:
            reasons.append("OVER_TOLERANCE")
        invoice_id = row["invoice_id"]
        expected[invoice_id] = {
            "invoice_id": invoice_id,
            "decision": "REVIEW" if reasons else "APPROVE",
            "approved_amount_cents": 0 if reasons else amount,
            "reason_codes": reasons,
        }
    return expected


def verify(task: dict, workspace: Path, summary: dict) -> tuple[bool, str]:
    try:
        expected = expected_rows(load_fixture(task))
        report = read_report(workspace / REPORT)
    except FileNotFoundError:
        return False, "Missing saved report"
    except (TypeError, ValueError, OSError) as error:
        return False, f"Cannot verify report: {error}"

    seen = set()
    for row in report:
        if not isinstance(row, dict) or not isinstance(row.get("invoice_id"), str):
            return False, "Malformed report row"
        invoice_id = row["invoice_id"]
        if invoice_id in seen:
            return False, f"Repeated invoice ID: {invoice_id}"
        if invoice_id not in expected:
            return False, f"Unexpected invoice ID: {invoice_id}"
        seen.add(invoice_id)
        target = expected[invoice_id]
        if row.keys() != target.keys() or type(row["approved_amount_cents"]) is not int:
            return False, f"Malformed decision: {invoice_id}"
        for field, value in target.items():
            if row[field] != value:
                return False, f"{invoice_id}: incorrect {field}, expected {value!r}"

    missing = expected.keys() - seen
    if missing:
        return False, f"Missing invoice IDs: {', '.join(sorted(missing))}"

    approved = sum(row["decision"] == "APPROVE" for row in report)
    counts = {"total_count": len(report), "approved_count": approved, "review_count": len(report) - approved}
    if not isinstance(summary, dict) or any(type(value) is not int for value in summary.values()) or summary != counts:
        return False, f"Incorrect summary, expected {counts}"
    return True, "All invoice decisions and summary counts are correct"
