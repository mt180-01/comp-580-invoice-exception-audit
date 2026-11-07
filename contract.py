from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    CHECK = "check_workspace"
    LIST = "list_invoices"
    LOOKUP = "get_purchase_orders"
    SAVE = "save_decisions"


class Task(Enum):
    AUDIT = "audit-invoices"


class DecisionKind(Enum):
    APPROVE = "APPROVE"
    REVIEW = "REVIEW"


class Reason(Enum):
    DUPLICATE = "DUPLICATE_SUBMISSION"
    MISSING = "MISSING_PURCHASE_ORDER"
    OVER = "OVER_TOLERANCE"


@dataclass
class Invoice(Output):
    invoice_id: Annotated[str, "Unique submission ID"]
    vendor_id: Annotated[str, "Vendor ID"]
    vendor_invoice_number: Annotated[str, "Invoice number assigned by the vendor"]
    purchase_order_id: Annotated[str, "Referenced purchase order"]
    filename: Annotated[str, "Submission filename"]
    submission_sequence: Annotated[int, "Earlier submissions have lower sequence numbers"]
    amount_cents: Annotated[int, "Invoice amount in cents"]


@dataclass
class PurchaseOrder(Output):
    purchase_order_id: Annotated[str, "Requested purchase order ID"]
    authorized_amount_cents: Annotated[int | None, "Authorized amount in cents, null if missing"]


@dataclass
class BatchData(Output):
    invoices: Annotated[list[Invoice], "New invoice submissions to audit"]
    purchase_orders: Annotated[list[PurchaseOrder], "Known POs with nonnegative integer authorized amounts"]
    tolerance_cents: Annotated[int, "Nonnegative overage allowed by policy v1, in integer cents"]


@dataclass
class AuditInput(Output):
    batch_id: Annotated[str, "Batch label; batch-001 loads the bundled example when dataset is null"]
    policy_version: Annotated[str, "Supported policy version, v1"]
    dataset: Annotated[BatchData | None, "Supply new invoice and PO records, or null for the bundled example"]


@dataclass
class PageInput(Output):
    task: Annotated[AuditInput, "Copy the complete audit input including its dataset"]
    cursor: Annotated[int | None, "Null for the first page, then use next_cursor"]


@dataclass
class PageOutput(Output):
    invoices: Annotated[list[Invoice], "Invoice records in this page"]
    next_cursor: Annotated[int | None, "Null when no pages remain"]


@dataclass
class LookupInput(Output):
    task: Annotated[AuditInput, "Copy the audit input"]
    purchase_order_ids: Annotated[list[str], "Distinct purchase order IDs referenced in the batch"]


@dataclass
class LookupOutput(Output):
    orders: Annotated[list[PurchaseOrder], "One result per requested purchase order"]


@dataclass
class Decision(Output):
    invoice_id: Annotated[str, "Invoice submission ID"]
    decision: Annotated[DecisionKind, "Approve or send for review"]
    approved_amount_cents: Annotated[int, "Full invoice amount if approved, otherwise zero"]
    reason_codes: Annotated[list[Reason], "Every applicable reason in policy order"]


@dataclass
class SaveInput(Output):
    task: Annotated[AuditInput, "Copy the audit input"]
    decisions: Annotated[list[Decision], "Decisions to save, one per distinct invoice ID"]


@dataclass
class SaveOutput(Output):
    invoice_ids: Annotated[list[str], "IDs saved by this call"]


@dataclass
class AuditOutput(Output):
    total_count: Annotated[int, "Number of audited invoices"]
    approved_count: Annotated[int, "Number of approvals"]
    review_count: Annotated[int, "Number of invoices sent for review"]


@dataclass
class WorkspaceOutput(Output):
    clean: Annotated[bool, "True only when the task workspace has no previous saved result"]
    dataset_digest: Annotated[str, "SHA256 fingerprint of the validated task and source dataset"]


TOOLS = {
    Tool.CHECK: (AuditInput, WorkspaceOutput),
    Tool.LIST: (PageInput, PageOutput),
    Tool.LOOKUP: (LookupInput, LookupOutput),
    Tool.SAVE: (SaveInput, SaveOutput),
}
TASKS = {Task.AUDIT: (AuditInput, AuditOutput)}
