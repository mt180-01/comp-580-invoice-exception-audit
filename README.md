# Invoice Exception Audit

Audit every invoice in the selected batch. Read all invoice pages starting with a
null cursor. Look up each referenced purchase order. Save one decision per
invoice and submit the total, approved, and review counts.

## Policy v1

Include every applicable reason in this order.

1. DUPLICATE_SUBMISSION applies when an earlier invoice in this batch has the
   same vendor ID and vendor invoice number. Compare submission sequence to
   establish which is earlier. Filenames, amounts, and PO references are
   irrelevant to duplicate identity.
2. MISSING_PURCHASE_ORDER applies when the lookup returns a null authorized
   amount. Skip the amount check for this invoice.
3. OVER_TOLERANCE applies when the invoice exceeds the PO amount by more than
   the supplied tolerance_cents (500 for the bundled example). Compare integer cents.

Use APPROVE and the full invoice amount when the reason list is empty.
Otherwise use REVIEW and zero approved cents.


## Tools

The audit-invoices task exposes list_invoices, get_purchase_orders, and
save_decisions. The hidden check_workspace reference tool enforces a fresh workspace. It submits total_count, approved_count, and review_count.

## Layout

nanoagent.yaml registers the task and tools. contract.py declares their
structured inputs and outputs. src/plugin serves the tools over MCP.
verifier validates the supplied dataset, fingerprints it for the reference, and independently evaluates the saved report. The fixed fixture is retained as a demo.

## Develop and run

Requires Python 3.12 or newer and uv. From this directory run:

    uv sync --locked --extra dev
    uv run --frozen pytest
    uv run --frozen ruff check .

Use task input {"batch_id":"batch-001","policy_version":"v1","dataset":null}. For the bundled example, a successful
submission reports five total, one approved, and four for review. Use a fresh
workspace for each run. The verifier rejects a staged report from an earlier run, even if its rows are correct. The tests include a scripted MCP session and check the
saved report without using a model.

## New input datasets

Version 0.2.0 accepts new records in the required dataset field. Set dataset to null
to use the original demo. For a new batch, supply a batch_id label, policy_version
v1, and dataset containing invoices, purchase_orders, and tolerance_cents.
tests/fixtures/unseen-input.json is a complete runnable input with new IDs and
a 37-cent tolerance.

Invoice IDs and submission sequences must be unique. Purchase order IDs must be
unique. All money and the tolerance must be nonnegative integer cents.
Use a missing PO reference to represent an invoice without an available order.
The policy still returns every applicable reason in its specified order.
Pagination adapts to the batch size and takes at most two reads.

The hidden reference pins a SHA256 fingerprint of the validated data and task
labels. The verifier recomputes each decision from that trusted task input and
checks that the pin still matches. Its expected answers are computed per run.

Supply the full JSON input to the task in RUSH Lab. Keep datasets small enough
to fit the platform's model context, output, and runtime limits. Each run requires
a fresh workspace.


## RUSH Lab publication

Upload this version's files to the plugin's existing GitHub repository, including the updated uv.lock. Version 0.2.0 must be submitted again on RUSH Lab after pushing.
Include the hidden .env and .gitignore files and uv.lock. Exclude .venv,
Python caches, test caches, run reports, and validation logs.

Submit the repository URL in the RUSH Lab course workspace marketplace.
After installation, run the task using the example input above in a fresh
workspace. Keep the exact input, test logs, and platform verdicts for the
milestone report. A scripted MCP test establishes the tool and verifier
workflow. A live model run on RUSH Lab remains part of final validation.
