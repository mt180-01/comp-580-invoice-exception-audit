import hashlib
import json

from .fixture import FIXTURE


def require_text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")


def require_cents(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")


def load_fixture(task):
    require_text(task["batch_id"], "batch_id")
    if task["policy_version"] != "v1":
        raise ValueError("Unsupported policy version")
    dataset = task.get("dataset")
    if dataset is None:
        if task["batch_id"] != FIXTURE["batch_id"]:
            raise ValueError("Unknown batch; supply dataset for a new batch")
        return FIXTURE
    invoices = dataset["invoices"]
    orders = dataset["purchase_orders"]
    require_cents(dataset["tolerance_cents"], "tolerance_cents")
    invoice_ids = set()
    sequences = set()
    for invoice in invoices:
        for key in ("invoice_id", "vendor_id", "vendor_invoice_number", "purchase_order_id", "filename"):
            require_text(invoice[key], key)
        require_cents(invoice["amount_cents"], "amount_cents")
        require_cents(invoice["submission_sequence"], "submission_sequence")
        if invoice["invoice_id"] in invoice_ids or invoice["submission_sequence"] in sequences:
            raise ValueError("Invoice IDs and submission sequences must be unique")
        invoice_ids.add(invoice["invoice_id"])
        sequences.add(invoice["submission_sequence"])
    order_map = {}
    for order in orders:
        order_id = order["purchase_order_id"]
        require_text(order_id, "purchase_order_id")
        require_cents(order["authorized_amount_cents"], "authorized_amount_cents")
        if order_id in order_map:
            raise ValueError("Purchase order IDs must be unique")
        order_map[order_id] = order["authorized_amount_cents"]
    return {
        "batch_id": task["batch_id"],
        "policy_version": task["policy_version"],
        "invoices": invoices,
        "purchase_orders": order_map,
        "tolerance_cents": dataset["tolerance_cents"],
    }


def task_digest(task):
    data = load_fixture(task)
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def page_size(invoices):
    return max(3, (len(invoices) + 1) // 2)
