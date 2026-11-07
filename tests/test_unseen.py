import json
from copy import deepcopy
from pathlib import Path

import pytest
from slimconfig import build_output, plain_output

from contract import AuditInput, AuditOutput, LookupInput, PageInput, SaveInput
from plugin.tools import check_workspace, get_purchase_orders, list_invoices, save_decisions
from verifier import verify_input, verify_output, verify_task
from verifier.data import load_fixture

EXAMPLE = Path(__file__).parent / "fixtures" / "unseen-input.json"
EXPECTED = [
    ("N1", "REVIEW", 0, ["DUPLICATE_SUBMISSION"]),
    ("N2", "REVIEW", 0, ["OVER_TOLERANCE"]),
    ("N3", "APPROVE", 10037, []),
    ("N4", "REVIEW", 0, ["OVER_TOLERANCE"]),
    ("N5", "REVIEW", 0, ["MISSING_PURCHASE_ORDER"]),
    ("N6", "REVIEW", 0, ["DUPLICATE_SUBMISSION", "MISSING_PURCHASE_ORDER"]),
    ("N7", "APPROVE", 0, []),
]


def example():
    return json.loads(EXAMPLE.read_text(encoding="utf-8-sig"))


def rows():
    return [{"invoice_id": i, "decision": d, "approved_amount_cents": a, "reason_codes": r} for i, d, a, r in EXPECTED]


def test_new_batch_uses_its_own_data(tmp_path):
    task = build_output(example(), AuditInput)
    reference = check_workspace(task, tmp_path)
    first = list_invoices(PageInput(task, None), tmp_path)
    second = list_invoices(PageInput(task, first.next_cursor), tmp_path)
    assert len(first.invoices) == 4
    assert second.next_cursor is None
    assert [row.invoice_id for row in first.invoices + second.invoices] == [row[0] for row in EXPECTED]
    request = LookupInput(task, ["ORDER-X", "ABSENT", "ORDER-ZERO"])
    output = get_purchase_orders(request, tmp_path)
    assert [row.authorized_amount_cents for row in output.orders] == [10000, None, 0]
    assert verify_output("get_purchase_orders", request, output, tmp_path)["valid"]
    save = build_output({"task": plain_output(task), "decisions": rows()}, SaveInput)
    save_decisions(save, tmp_path)
    summary = AuditOutput(7, 2, 5)
    assert verify_task("audit-invoices", task, summary, reference, tmp_path)["valid"]
    # The pin belongs to the original dataset even if an attacker changes a PO.
    changed = example()
    changed["dataset"]["purchase_orders"][0]["authorized_amount_cents"] = 999999
    assert not verify_task("audit-invoices", build_output(changed, AuditInput), summary, reference, tmp_path)["valid"]
    for row in rows():
        row["approved_amount_cents"] += 1
        save_decisions(build_output({"task": plain_output(task), "decisions": [row]}, SaveInput), tmp_path)
        assert not verify_task("audit-invoices", task, summary, reference, tmp_path)["valid"]


def test_empty_batch(tmp_path):
    value = example()
    value["dataset"]["invoices"] = []
    value["dataset"]["purchase_orders"] = []
    task = build_output(value, AuditInput)
    reference = check_workspace(task, tmp_path)
    assert list_invoices(PageInput(task, None), tmp_path).invoices == []
    request = build_output({"task": value, "decisions": []}, SaveInput)
    assert verify_input("save_decisions", request)["valid"]
    save_decisions(request, tmp_path)
    assert verify_task("audit-invoices", task, AuditOutput(0, 0, 0), reference, tmp_path)["valid"]


@pytest.mark.parametrize("change", ["sequence", "invoice_id", "order_id", "negative", "missing_amount", "policy"])
def test_invalid_new_data_is_rejected(change):
    value = deepcopy(example())
    data = value["dataset"]
    if change == "sequence":
        data["invoices"][1]["submission_sequence"] = data["invoices"][0]["submission_sequence"]
    elif change == "invoice_id":
        data["invoices"][1]["invoice_id"] = data["invoices"][0]["invoice_id"]
    elif change == "order_id":
        data["purchase_orders"].append(data["purchase_orders"][0])
    elif change == "negative":
        data["invoices"][0]["amount_cents"] = -1
    elif change == "missing_amount":
        data["purchase_orders"][0]["authorized_amount_cents"] = None
    else:
        value["policy_version"] = "v999"
    with pytest.raises(ValueError):
        load_fixture(value)
