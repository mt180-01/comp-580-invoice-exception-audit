import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import sleep

from verifier.data import page_size
from verifier.report import REPORT, load_fixture, read_report

from .types import (
    Decision,
    Page,
    PageInput,
    PurchaseOrderInput,
    PurchaseOrderResult,
    SaveResult,
    TaskInput,
)


class AuditTools:
    def __init__(self, task: TaskInput, workspace: Path):
        self.fixture = load_fixture(task)
        self.report = workspace / REPORT

    def list_invoices(self, request: PageInput) -> Page:
        invoices = self.fixture["invoices"]
        cursor = request["cursor"]
        start = 0 if cursor is None else cursor
        size = page_size(invoices)
        if type(start) is not int or start not in (0, size) or (start != 0 and start >= len(invoices)):
            raise ValueError("Invalid invoice cursor")
        end = start + size
        return {
            "invoices": [row.copy() for row in invoices[start:end]],
            "next_cursor": end if end < len(invoices) else None,
        }

    def get_purchase_order(self, request: PurchaseOrderInput) -> PurchaseOrderResult:
        amount = self.fixture["purchase_orders"].get(request["purchase_order_id"])
        return {"authorized_amount_cents": amount}

    def save_decision(self, decision: Decision) -> SaveResult:
        self.save_decisions([decision])
        return {"invoice_id": decision["invoice_id"]}

    def save_decisions(self, decisions: list[Decision]) -> None:
        ids = [row["invoice_id"] for row in decisions]
        known = {row["invoice_id"] for row in self.fixture["invoices"]}
        if len(set(ids)) != len(ids) or not set(ids) <= known:
            raise ValueError("Expected distinct, known invoice IDs")
        try:
            rows = read_report(self.report)
        except FileNotFoundError:
            rows = []
        rows = [row for row in rows if row["invoice_id"] not in ids]
        rows.extend(decisions)
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.report.parent, delete=False) as temp:
            temporary_path = Path(temp.name)
            try:
                json.dump(rows, temp)
                temp.close()
                for attempt in range(5):
                    try:
                        os.replace(temporary_path, self.report)
                        break
                    except PermissionError:
                        if os.name != "nt" or attempt == 4:
                            raise
                        sleep(0.05 * (attempt + 1))
            finally:
                temporary_path.unlink(missing_ok=True)
