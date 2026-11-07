import json
import random
from copy import deepcopy

import pytest
from slimconfig import build_output, plain_output

from contract import AuditInput, AuditOutput, LookupInput, PageInput, SaveInput
from plugin.tools import check_workspace, get_purchase_orders, list_invoices, save_decisions
from verifier import verify_task
from verifier.report import REPORT


def generated_task(seed):
    rng = random.Random(seed)
    tolerance = rng.choice([0, 1, 37, 500, 10**12])
    orders = [
        {"purchase_order_id": f"P-{seed}-{i}", "authorized_amount_cents": rng.choice([0, 10000, 10**18])}
        for i in range(3)
    ]
    invoices = []
    for i in range(rng.randrange(1, 25)):
        order = rng.choice(orders)
        invoices.append(
            {
                "invoice_id": f"INV-{seed}-{i}",
                "vendor_id": f"V-{rng.randrange(3)}",
                "vendor_invoice_number": f"NUMBER-{rng.randrange(4)}",
                "purchase_order_id": order["purchase_order_id"] if rng.random() > 0.2 else "MISSING",
                "filename": f"file-{i}.pdf",
                "submission_sequence": 100 + i * 7,
                "amount_cents": max(0, order["authorized_amount_cents"] + tolerance + rng.choice([-1, 0, 1])),
            }
        )
    rng.shuffle(invoices)
    return {
        "batch_id": f"generated-{seed}",
        "policy_version": "v1",
        "dataset": {"invoices": invoices, "purchase_orders": orders, "tolerance_cents": tolerance},
    }


def independent_decisions(task):
    data = task["dataset"]
    orders = {row["purchase_order_id"]: row["authorized_amount_cents"] for row in data["purchase_orders"]}
    rows = []
    for invoice in data["invoices"]:
        same_identity = [
            row["submission_sequence"]
            for row in data["invoices"]
            if (row["vendor_id"], row["vendor_invoice_number"])
            == (invoice["vendor_id"], invoice["vendor_invoice_number"])
        ]
        missing = invoice["purchase_order_id"] not in orders
        violations = [
            ("DUPLICATE_SUBMISSION", invoice["submission_sequence"] != min(same_identity)),
            ("MISSING_PURCHASE_ORDER", missing),
            (
                "OVER_TOLERANCE",
                not missing
                and invoice["amount_cents"] > orders[invoice["purchase_order_id"]] + data["tolerance_cents"],
            ),
        ]
        reasons = [code for code, applies in violations if applies]
        rows.append(
            {
                "invoice_id": invoice["invoice_id"],
                "decision": "REVIEW" if reasons else "APPROVE",
                "approved_amount_cents": 0 if reasons else invoice["amount_cents"],
                "reason_codes": reasons,
            }
        )
    return rows


@pytest.mark.parametrize("seed", range(30))
def test_generated_unseen_batches_and_corrupted_reports(seed, tmp_path):
    raw = generated_task(seed)
    task = build_output(raw, AuditInput)
    reference = check_workspace(task, tmp_path)
    first = list_invoices(PageInput(task, None), tmp_path)
    invoices = list(first.invoices)
    if first.next_cursor is not None:
        second = list_invoices(PageInput(task, first.next_cursor), tmp_path)
        assert second.next_cursor is None
        invoices.extend(second.invoices)
    assert [plain_output(row) for row in invoices] == raw["dataset"]["invoices"]
    ids = sorted({row["purchase_order_id"] for row in raw["dataset"]["invoices"]})
    lookup = get_purchase_orders(LookupInput(task, ids), tmp_path)
    assert [row.purchase_order_id for row in lookup.orders] == ids
    correct = independent_decisions(raw)
    save_decisions(build_output({"task": raw, "decisions": correct}, SaveInput), tmp_path)
    approved = sum(row["decision"] == "APPROVE" for row in correct)
    summary = AuditOutput(len(correct), approved, len(correct) - approved)
    assert verify_task("audit-invoices", task, summary, reference, tmp_path)["valid"]

    mutations = [correct[:-1], [*correct, correct[0]]]
    for field, value in [
        ("decision", "REVIEW" if correct[0]["decision"] == "APPROVE" else "APPROVE"),
        ("approved_amount_cents", correct[0]["approved_amount_cents"] + 1),
        ("reason_codes", ["UNKNOWN_REASON"]),
        ("invoice_id", "UNKNOWN"),
    ]:
        altered = deepcopy(correct)
        altered[0][field] = value
        mutations.append(altered)
    for altered in mutations:
        (tmp_path / REPORT).write_text(json.dumps(altered), encoding="utf-8")
        assert not verify_task("audit-invoices", task, summary, reference, tmp_path)["valid"]


@pytest.mark.parametrize("bad_amount", [True, 12.5, "100", None])
def test_money_schema_rejects_nonintegers(bad_amount):
    raw = generated_task(3)
    raw["dataset"]["invoices"][0]["amount_cents"] = bad_amount
    with pytest.raises((TypeError, ValueError)):
        build_output(raw, AuditInput)
