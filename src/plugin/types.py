from typing import Literal, TypedDict

Reason = Literal["DUPLICATE_SUBMISSION", "MISSING_PURCHASE_ORDER", "OVER_TOLERANCE"]


class TaskInput(TypedDict):
    batch_id: str
    policy_version: str
    dataset: dict | None


class PageInput(TypedDict):
    cursor: int | None


class Invoice(TypedDict):
    invoice_id: str
    vendor_id: str
    vendor_invoice_number: str
    purchase_order_id: str
    filename: str
    submission_sequence: int
    amount_cents: int


class Page(TypedDict):
    invoices: list[Invoice]
    next_cursor: int | None


class PurchaseOrderInput(TypedDict):
    purchase_order_id: str


class PurchaseOrderResult(TypedDict):
    authorized_amount_cents: int | None


class Decision(TypedDict):
    invoice_id: str
    decision: Literal["APPROVE", "REVIEW"]
    approved_amount_cents: int
    reason_codes: list[Reason]


class SaveResult(TypedDict):
    invoice_id: str


class Summary(TypedDict):
    total_count: int
    approved_count: int
    review_count: int

