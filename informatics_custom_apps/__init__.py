__version__ = "2.0.1"
import frappe
import erpnext.accounts.doctype.accounting_period.accounting_period as ap_module

from frappe import _
from erpnext.accounts.doctype.accounting_period.accounting_period import (
    ClosedAccountingPeriod,
)

def custom_validate_accounting_period_on_doc_save(doc, method=None):

    if doc.doctype == "Bank Clearance":
        return

    elif doc.doctype == "Asset":
        if doc.is_existing_asset:
            return
        date = doc.available_for_use_date

    elif doc.doctype == "Asset Repair":
        date = doc.completion_date

    elif doc.doctype == "Period Closing Voucher":
        date = doc.period_end_date

    else:
        date = doc.posting_date

    ap = frappe.qb.DocType("Accounting Period")
    cd = frappe.qb.DocType("Closed Document")

    conditions = [
        ap.name == cd.parent,
        ap.company == doc.company,
        cd.closed == 1,
        cd.document_type == doc.doctype,
        date >= ap.start_date,
        date <= ap.end_date,
    ]

    branch = getattr(doc, "branch", None)

    if branch:
        branch_condition = None

        if frappe.db.has_column("Accounting Period", "branch"):
            branch_condition = ap.branch == branch

        if frappe.db.has_column("Accounting Period", "custom_branch"):
            custom_branch_condition = ap.custom_branch == branch

            if branch_condition:
                branch_condition = branch_condition | custom_branch_condition
            else:
                branch_condition = custom_branch_condition

        if branch_condition:
            conditions.append(branch_condition)

    segment = getattr(doc, "segment", None)

    if (
        segment
        and frappe.db.has_column("Accounting Period", "segment")
    ):
        conditions.append(ap.segment == segment)

    q = frappe.qb.from_(ap).from_(cd).select(ap.name)

    for condition in conditions:
        q = q.where(condition)

    accounting_period = q.run(as_dict=True)

    if accounting_period:
        frappe.throw(
            _("You cannot create a {0} within the closed Accounting Period {1}").format(
                doc.doctype,
                frappe.bold(accounting_period[0]["name"]),
            ),
            ClosedAccountingPeriod,
        )


ap_module.validate_accounting_period_on_doc_save = (
    custom_validate_accounting_period_on_doc_save
)