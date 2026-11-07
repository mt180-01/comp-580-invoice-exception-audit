from dataclasses import asdict
from pathlib import Path

from contract import Task, Tool

from .data import page_size, task_digest
from .report import REPORT, load_fixture, read_report, verify


def result(valid, message):
    return {"valid": valid, "score": float(valid), "message": message, "details": {}}


def verify_input(tool, value):
    try:
        fixture = load_fixture(asdict(value if Tool(tool) == Tool.CHECK else value.task))
    except ValueError as error:
        return result(False, str(error))

    match Tool(tool):
        case Tool.CHECK:
            valid = True
        case Tool.LIST:
            size = page_size(fixture["invoices"])
            valid = value.cursor in (None, 0) or (value.cursor == size and size < len(fixture["invoices"]))
        case Tool.LOOKUP:
            ids = value.purchase_order_ids
            valid = len(set(ids)) == len(ids)
        case Tool.SAVE:
            ids = [row.invoice_id for row in value.decisions]
            known = {row["invoice_id"] for row in fixture["invoices"]}
            valid = len(set(ids)) == len(ids) and set(ids) <= known
    return result(valid, "Tool input accepted" if valid else "Invalid cursor or repeated, empty, or unknown IDs")


def decision_dict(row):
    return {
        "invoice_id": row.invoice_id,
        "decision": row.decision.value,
        "approved_amount_cents": row.approved_amount_cents,
        "reason_codes": [reason.value for reason in row.reason_codes],
    }


def verify_output(tool, input_value, output_value, workspace):
    if Tool(tool) == Tool.CHECK:
        clean = not (Path(workspace) / "invoice-audit.json").exists()
        return result(
            output_value.clean == clean and output_value.dataset_digest == task_digest(asdict(input_value)),
            "Workspace check verified",
        )
    match Tool(tool):
        case Tool.LIST:
            start = input_value.cursor or 0
            invoices = load_fixture(asdict(input_value.task))["invoices"]
            end = start + page_size(invoices)
            valid = [asdict(invoice) for invoice in output_value.invoices] == invoices[
                start:end
            ] and output_value.next_cursor == (end if end < len(invoices) else None)
        case Tool.LOOKUP:
            valid = [asdict(order) for order in output_value.orders] == [
                {
                    "purchase_order_id": order_id,
                    "authorized_amount_cents": load_fixture(asdict(input_value.task))["purchase_orders"].get(order_id),
                }
                for order_id in input_value.purchase_order_ids
            ]
        case Tool.SAVE:
            try:
                saved = read_report(Path(workspace) / REPORT)
            except (OSError, TypeError, ValueError):
                return result(False, "Could not read the saved report")
            submitted = [decision_dict(row) for row in input_value.decisions]
            valid = output_value.invoice_ids == [row["invoice_id"] for row in submitted] and all(
                row in saved for row in submitted
            )
    return result(valid, "Tool output verified" if valid else "Tool output does not match the fixture or saved rows")


def verify_task(task, arguments, output, reference, workspace):
    if reference is None or not reference.clean:
        return result(False, "A fresh workspace is required; an earlier result cannot pass this run")
    try:
        if reference.dataset_digest != task_digest(asdict(arguments)):
            return result(False, "Reference dataset fingerprint does not match the task input")
    except ValueError as error:
        return result(False, str(error))
    if Task(task) != Task.AUDIT:
        return result(False, "Unknown task")
    valid, message = verify(asdict(arguments), Path(workspace), asdict(output))
    return result(valid, message)
