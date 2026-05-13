__version__ = "1.0.2"
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
        else:
            date = doc.available_for_use_date

    elif doc.doctype == "Asset Repair":
        date = doc.completion_date

    elif doc.doctype == "Period Closing Voucher":
        date = doc.period_end_date

    else:
        date = doc.posting_date

    ap = frappe.qb.DocType("Accounting Period")
    cd = frappe.qb.DocType("Closed Document")

    q = (
        frappe.qb.from_(ap)
        .from_(cd)
        .select(ap.name)
        .where(
            (ap.name == cd.parent)
            & (ap.company == doc.company)
            & (ap.branch == doc.branch)
            & (ap.segment == doc.segment)
            & (cd.closed == 1)
            & (cd.document_type == doc.doctype)
            & (date >= ap.start_date)
            & (date <= ap.end_date)
        )
    )

    accounting_period = q.run(as_dict=1)

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