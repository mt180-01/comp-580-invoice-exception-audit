from slimconfig import build_output, plain_output

from contract import LookupOutput, PageOutput, SaveOutput, Tool, WorkspaceOutput
from verifier.data import task_digest
from verifier.report import REPORT

from .audit import AuditTools


def list_invoices(request, workspace):
    tools = AuditTools(plain_output(request.task), workspace)
    return build_output(tools.list_invoices({"cursor": request.cursor}), PageOutput)


def get_purchase_orders(request, workspace):
    tools = AuditTools(plain_output(request.task), workspace)
    orders = [
        {"purchase_order_id": order_id, **tools.get_purchase_order({"purchase_order_id": order_id})}
        for order_id in request.purchase_order_ids
    ]
    return build_output({"orders": orders}, LookupOutput)


def save_decisions(request, workspace):
    tools = AuditTools(plain_output(request.task), workspace)
    tools.save_decisions([plain_output(row) for row in request.decisions])
    return SaveOutput(invoice_ids=[row.invoice_id for row in request.decisions])


def check_workspace(value, workspace):
    return WorkspaceOutput(clean=not (workspace / REPORT).exists(), dataset_digest=task_digest(plain_output(value)))


IMPLEMENTATIONS = {
    Tool.CHECK: check_workspace,
    Tool.LIST: list_invoices,
    Tool.LOOKUP: get_purchase_orders,
    Tool.SAVE: save_decisions,
}
