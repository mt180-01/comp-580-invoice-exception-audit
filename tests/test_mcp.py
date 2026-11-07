import os
import sys

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from slimconfig import build_output
from test_verifier import GOLD, SUMMARY, TASK

from contract import TOOLS, AuditInput, AuditOutput, Tool, WorkspaceOutput
from verifier import verify_input, verify_output, verify_task
from verifier.data import task_digest


def test_mcp_task(tmp_path):
    async def run():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "plugin"],
            env={**os.environ, "NANOAGENT_WORKSPACE": str(tmp_path)},
        )
        async with stdio_client(params) as (read, write), ClientSession(read, write) as client:
            await client.initialize()
            listed = await client.list_tools()
            assert {tool.name for tool in listed.tools} == {tool.value for tool in Tool}

            async def call(tool, **arguments):
                input_type, output_type = TOOLS[tool]
                arguments["task"] = TASK
                value = build_output(arguments, input_type)
                assert verify_input(tool.value, value)["valid"]
                response = await client.call_tool(tool.value, arguments)
                assert not response.isError, response.content
                data = response.structuredContent
                output = build_output(data, output_type)
                assert verify_output(tool.value, value, output, tmp_path)["valid"]
                return data

            first = await call(Tool.LIST, cursor=None)
            second = await call(Tool.LIST, cursor=first["next_cursor"])
            invoices = first["invoices"] + second["invoices"]
            assert second["next_cursor"] is None
            assert [row["invoice_id"] for row in invoices] == [row[0] for row in GOLD]
            await call(Tool.LOOKUP, purchase_order_ids=["PO-100", "PO-404"])
            await call(
                Tool.SAVE,
                decisions=[
                    {
                        "invoice_id": invoice_id,
                        "decision": decision,
                        "approved_amount_cents": amount,
                        "reason_codes": reasons,
                    }
                    for invoice_id, decision, amount, reasons in GOLD
                ],
            )
            verdict = verify_task(
                "audit-invoices",
                build_output(TASK, AuditInput),
                build_output(SUMMARY, AuditOutput),
                WorkspaceOutput(True, task_digest(TASK)),
                tmp_path,
            )
            assert verdict["valid"], verdict

    anyio.run(run)
