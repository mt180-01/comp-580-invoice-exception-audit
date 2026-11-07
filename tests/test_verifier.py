import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from plugin.audit import AuditTools
from verifier.report import verify

TASK = {"batch_id": "batch-001", "policy_version": "v1", "dataset": None}
SUMMARY = {"total_count": 5, "approved_count": 1, "review_count": 4}
GOLD = [
    ("I-01", "APPROVE", 10500, []),
    ("I-02", "REVIEW", 0, ["OVER_TOLERANCE"]),
    ("I-03", "REVIEW", 0, ["MISSING_PURCHASE_ORDER"]),
    ("I-04", "REVIEW", 0, ["DUPLICATE_SUBMISSION"]),
    ("I-05", "REVIEW", 0, ["DUPLICATE_SUBMISSION", "OVER_TOLERANCE"]),
]


class AuditTest(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(directory.cleanup)
        self.workspace = Path(directory.name)
        self.tools = AuditTools(TASK, self.workspace)
        self.rows = [
            {
                "invoice_id": invoice_id,
                "decision": decision,
                "approved_amount_cents": amount,
                "reason_codes": reasons.copy(),
            }
            for invoice_id, decision, amount, reasons in GOLD
        ]

    def save(self, rows):
        for row in rows:
            self.tools.save_decision(row)

    def assert_verdict(self, valid, message, summary=SUMMARY):
        actual, detail = verify(TASK, self.workspace, summary)
        self.assertEqual(actual, valid, detail)
        self.assertIn(message, detail)

    def test_scripted_end_to_end_and_retry(self):
        cursor = None
        position = 0
        while True:
            page = self.tools.list_invoices({"cursor": cursor})
            for invoice in page["invoices"]:
                row = self.rows[position]
                self.assertEqual(invoice["invoice_id"], row["invoice_id"])
                order = self.tools.get_purchase_order({"purchase_order_id": invoice["purchase_order_id"]})
                self.assertEqual(order["authorized_amount_cents"], None if position == 2 else 10000)
                self.assertEqual(self.tools.save_decision(row), {"invoice_id": row["invoice_id"]})
                position += 1
            cursor = page["next_cursor"]
            if cursor is None:
                break
        self.assertEqual(position, 5)
        self.save(self.rows[:1])
        self.assert_verdict(True, "All invoice decisions")

    def test_policy_errors(self):
        cases = [
            (0, "decision", "REVIEW"),
            (1, "reason_codes", []),
            (2, "reason_codes", ["OVER_TOLERANCE"]),
            (3, "reason_codes", []),
            (4, "reason_codes", ["DUPLICATE_SUBMISSION"]),
            (4, "reason_codes", ["OVER_TOLERANCE", "DUPLICATE_SUBMISSION"]),
            (0, "approved_amount_cents", 10000),
        ]
        for index, field, value in cases:
            with self.subTest(index=index, field=field, value=value):
                self.save(self.rows)
                self.save([dict(self.rows[index], **{field: value})])
                self.assert_verdict(False, f"{self.rows[index]['invoice_id']}: incorrect {field}")

    def test_missing_invoice_with_reconciled_summary(self):
        self.save(self.rows[:3] + self.rows[4:])
        self.assert_verdict(
            False, "Missing invoice IDs: I-04", {"total_count": 4, "approved_count": 1, "review_count": 3}
        )

    def test_missing_report(self):
        self.assert_verdict(False, "Missing saved report")

    def test_malformed_report(self):
        for content in ("{", "[null]", json.dumps([dict(self.rows[0], approved_amount_cents=True)])):
            with self.subTest(content=content):
                self.tools.report.write_text(content, encoding="utf-8")
                self.assert_verdict(False, "report" if content in ("{", "[null]") else "Malformed")

    def test_repeated_and_unexpected_ids(self):
        cases = [
            (self.rows[0], "Repeated invoice ID"),
            (dict(self.rows[0], invoice_id="I-99"), "Unexpected invoice ID"),
        ]
        for row, message in cases:
            with self.subTest(message=message):
                self.tools.report.write_text(json.dumps([*self.rows, row]), encoding="utf-8")
                self.assert_verdict(False, message)

    def test_incorrect_summary(self):
        self.save(self.rows)
        self.assert_verdict(False, "Incorrect summary", dict(SUMMARY, approved_count=2))
        self.assert_verdict(False, "Incorrect summary", dict(SUMMARY, approved_count=True))


def test_reused_workspace_is_rejected(tmp_path):
    from slimconfig import build_output

    from contract import AuditInput, AuditOutput
    from plugin.tools import check_workspace
    from verifier import verify_task

    task = build_output(TASK, AuditInput)
    assert check_workspace(task, tmp_path).clean
    tools = AuditTools(TASK, tmp_path)
    for invoice_id, decision, amount, reasons in GOLD:
        tools.save_decision(
            {
                "invoice_id": invoice_id,
                "decision": decision,
                "approved_amount_cents": amount,
                "reason_codes": reasons,
            }
        )
    reference = check_workspace(task, tmp_path)
    assert not reference.clean
    output = build_output(SUMMARY, AuditOutput)
    assert not verify_task("audit-invoices", task, output, reference, tmp_path)["valid"]
    assert not verify_task("audit-invoices", task, output, None, tmp_path)["valid"]


def test_tool_checks_reject_wrong_pages_and_unknown_ids(tmp_path):
    from slimconfig import build_output

    from contract import TOOLS, Tool
    from verifier import verify_input, verify_output

    given, made = TOOLS[Tool.LIST]
    request = build_output({"task": TASK, "cursor": None}, given)
    output = build_output(AuditTools(TASK, tmp_path).list_invoices({"cursor": None}), made)
    output.invoices[0].amount_cents += 1
    assert not verify_output(Tool.LIST.value, request, output, tmp_path)["valid"]
    invalid = build_output({"task": TASK, "cursor": 2}, given)
    assert not verify_input(Tool.LIST.value, invalid)["valid"]
