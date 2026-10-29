import frappe
from frappe import _
from frappe.utils import add_days, add_months, flt, getdate, formatdate

@frappe.whitelist()
def update_rejected_warehouse(purchase_receipt):

    pr = frappe.get_doc("Purchase Receipt", purchase_receipt)

    if not pr.branch:
        frappe.throw("Plant is not selected.")

    rejected_warehouse = frappe.db.get_value(
        "Branch",
        pr.branch,
        "custom_return_and_rejected_warehouse"
    )

    if not rejected_warehouse:
        frappe.throw(
            f"Rejected Warehouse is not set for Plant {pr.branch}"
        )

    for item in pr.items:
        item.rejected_warehouse = rejected_warehouse

    pr.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "warehouse": rejected_warehouse
    }
    

@frappe.whitelist()
def update_itc_claim_period(purchase_invoice, itc_claim_period):

    doc = frappe.get_doc("Purchase Invoice", purchase_invoice)

    doc.db_set(
        "itc_claim_period",
        itc_claim_period,
        update_modified=False
    )

    frappe.db.commit()

    return {
        "itc_claim_period": itc_claim_period
    }
    


@frappe.whitelist()
def update_transporter(sales_invoice, transporter):

    doc = frappe.get_doc("Sales Invoice", sales_invoice)

    if doc.docstatus == 2:
        frappe.throw("Cancelled Sales Invoice cannot be updated.")

    transporter_name = frappe.db.get_value(
        "Supplier",
        transporter,
        "supplier_name"
    )

    doc.db_set(
        "transporter",
        transporter,
        update_modified=False
    )

    doc.db_set(
        "transporter_name",
        transporter_name,
        update_modified=False
    )

    frappe.db.commit()

    return "Success"

# Customization for Loan Repayment Schedule

SCHEDULE = "Loan Repayment Schedule"
CHILD = "Repayment Schedule"   # verify child doctype name

def _window(payment_date):
    end = getdate(payment_date)
    return add_days(add_months(end, -1), 1), end

def _has_submitted_repayment(loan, payment_date):
    start, end = _window(payment_date)
    return frappe.db.exists("Loan Repayment", {
        "against_loan": loan, "docstatus": 1,
        "due_date": ["between", [start, end]],
    })

@frappe.whitelist()
def get_skippable_instalments(schedule):
    doc = frappe.get_doc(SCHEDULE, schedule)
    doc.check_permission("write")
    if doc.docstatus != 1 or doc.status != "Active":
        return []
    return [
        {"row_name": r.name, "payment_date": r.payment_date, "total_payment": r.total_payment}
        for r in doc.repayment_schedule
        if not r.get("custom_skipped") and flt(r.total_payment) > 0
        and not _has_submitted_repayment(doc.loan, r.payment_date)
    ]

@frappe.whitelist()
def skip_instalments(schedule, row_names):
    row_names = frappe.parse_json(row_names)
    doc = frappe.get_doc(SCHEDULE, schedule)
    doc.check_permission("write")
    if doc.docstatus != 1 or doc.status != "Active":
        frappe.throw(_("Schedule must be Active."))

    deferred = 0.0              # running total, used only for balance_loan_amount
    deferred_amounts = []       # one entry per skipped row, in schedule order
    skipped_dates = []

    for r in doc.repayment_schedule:
        if r.name in row_names:
            if r.get("custom_skipped") or _has_submitted_repayment(doc.loan, r.payment_date):
                frappe.throw(_("Row {0} cannot be skipped.").format(r.idx))
            _cancel_accruals(doc.loan, r.payment_date)

            amount = flt(r.principal_amount)
            deferred += amount
            deferred_amounts.append(amount)
            skipped_dates.append(formatdate(r.payment_date))

            frappe.db.set_value(CHILD, r.name, {
                "principal_amount": 0, "interest_amount": 0, "total_payment": 0,
                "custom_skipped": 1,
                "balance_loan_amount": flt(r.balance_loan_amount) + deferred,
            })
        elif deferred:
            # later rows: balance is higher because skipped principal is still owed
            frappe.db.set_value(CHILD, r.name, "balance_loan_amount",
                                flt(r.balance_loan_amount) + deferred)

    if not deferred_amounts:
        return

    last = doc.repayment_schedule[-1]
    next_idx = last.idx
    next_date = getdate(last.payment_date)
    remaining = deferred   # original last row's balance is now equal to total deferred

    # one new row per skipped instalment, each with that instalment's own amount
    for amount in deferred_amounts:
        next_idx += 1
        next_date = add_months(next_date, 1)
        remaining = flt(remaining - amount, 2)

        new = frappe.get_doc({
            "doctype": CHILD, "parent": doc.name, "parenttype": SCHEDULE,
            "parentfield": "repayment_schedule", "idx": next_idx,
            "payment_date": next_date,
            "principal_amount": amount, "interest_amount": 0,
            "total_payment": amount, "balance_loan_amount": max(remaining, 0),
        })
        new.set_new_name()
        new.db_insert()

    skipped = len(deferred_amounts)
    doc.db_set("repayment_periods", doc.repayment_periods + skipped)
    frappe.db.set_value("Loan", doc.loan, "repayment_periods",
                        frappe.db.get_value("Loan", doc.loan, "repayment_periods") + skipped)
    doc.add_comment("Info", _("Skipped instalment(s) for the following payment dates: {0}. These instalments have been deferred to the end of the schedule.").format(", ".join(skipped_dates)))

def _cancel_accruals(loan, payment_date):
    due_date = payment_date
    filters = {"loan": loan, "docstatus": 1, "due_date": due_date}
    # if your accrual has a link to the schedule, tighten the filter:
    # filters["repayment_schedule_name"] = schedule
    for a in frappe.get_all("Loan Interest Accrual", filters=filters,
                            fields=["name", "paid_interest_amount", "paid_principal_amount"]):
        if flt(a.get("paid_interest_amount")) or flt(a.get("paid_principal_amount")):
            frappe.throw(_("Accrual {0} is already partly paid.").format(a.name))
        frappe.get_doc("Loan Interest Accrual", a.name).cancel()