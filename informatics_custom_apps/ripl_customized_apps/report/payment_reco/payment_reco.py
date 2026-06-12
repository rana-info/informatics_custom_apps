# Copyright (c) 2024, Your Company and contributors
# For license information, please see license.txt
#
# Payment Reconciliation Report — ERPNext v15 (Hyper-Optimized & Swapped)

import frappe
from frappe import _, qb
from frappe.query_builder import Criterion
from frappe.query_builder.functions import Sum, Max
from frappe.utils import flt, getdate
import erpnext

# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def execute(filters=None):
    filters = frappe._dict(filters or {})
    validate_filters(filters)
    
    # Cache schema checks
    filters.has_ple_branch = frappe.db.has_column("Payment Ledger Entry", "branch")
    filters.has_ple_cc     = frappe.db.has_column("Payment Ledger Entry", "cost_center")
    filters.has_ple_segment = frappe.db.has_column("Payment Ledger Entry", "segment")

    columns = get_columns(filters)
    data    = get_data(filters)
    chart   = get_chart(data)
    summary = get_report_summary(data)
    return columns, data, None, chart, summary

# ─────────────────────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_filters(filters):
    if not filters.company:
        frappe.throw(_("Please select a Company"))
    if not filters.party_type:
        frappe.throw(_("Please select a Party Type"))

# ─────────────────────────────────────────────────────────────────────────────
# Columns
# ─────────────────────────────────────────────────────────────────────────────

def get_columns(filters):
    return [
        {"label": _("Section"),              "fieldname": "section",               "fieldtype": "Data",         "width": 110},
        {"label": _("Party"),                "fieldname": "party",                 "fieldtype": "Dynamic Link", "options": "party_type", "width": 150},
        {"label": _("Party Name"),           "fieldname": "party_name",            "fieldtype": "Data",         "width": 180},
        {"label": _("Voucher Type"),         "fieldname": "voucher_type",          "fieldtype": "Data",         "width": 150},
        {"label": _("Voucher / Invoice No"), "fieldname": "voucher_no",            "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 200},
        {"label": _("Date"),                 "fieldname": "posting_date",          "fieldtype": "Date",         "width": 110},
        {"label": _("Payment Amount"),       "fieldname": "invoice_amount",        "fieldtype": "Currency",     "options": "currency", "width": 150},
        {"label": _("Outstanding Amount"),   "fieldname": "outstanding_amount",    "fieldtype": "Currency",     "options": "currency", "width": 160},
        {"label": _("Invoice Amount"),       "fieldname": "payment_amount",        "fieldtype": "Currency",     "options": "currency", "width": 150},
        {"label": _("Currency"),             "fieldname": "currency",              "fieldtype": "Link",         "options": "Currency", "width": 80},
        {"label": _("Reconciliation Status"),"fieldname": "reconciliation_status", "fieldtype": "Data",         "width": 170},
        {"label": _("Branch"),               "fieldname": "branch",                "fieldtype": "Link",         "options": "Branch", "width": 120},
        {"label": _("Cost Center"),          "fieldname": "cost_center",           "fieldtype": "Link",         "options": "Cost Center", "width": 150},
        {"label": _("Segment"),              "fieldname": "segment",               "fieldtype": "Link",         "options": "Segment", "width": 130},
        {"label": _("Remarks"),              "fieldname": "remarks",               "fieldtype": "Small Text",   "width": 220},
        {"label": _("Party Type"),           "fieldname": "party_type",            "fieldtype": "Data",         "hidden": 1, "width": 0},
    ]

# ─────────────────────────────────────────────────────────────────────────────
# THE SPEED OF LIGHT ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def get_data(filters):
    ple = qb.DocType("Payment Ledger Entry")
    account_type = erpnext.get_party_account_type(filters.party_type)
    
    conditions = [
        ple.company == filters.company,
        ple.party_type == filters.party_type,
        ple.delinked == 0
    ]
    
    if filters.get("receivable_payable_account"):
        conditions.append(ple.account == filters.receivable_payable_account)
    else:
        conditions.append(ple.account_type == account_type)

    if filters.get("party"):
        conditions.append(ple.party == filters.party)
        
    if filters.get("cost_center") and filters.has_ple_cc:
        conditions.append(ple.cost_center == filters.cost_center)
        
    if filters.get("branch") and filters.has_ple_branch:
        conditions.append(ple.branch == filters.branch)
        
    orig_amount = qb.terms.Case().when(ple.voucher_no == ple.against_voucher_no, ple.amount_in_account_currency).else_(0)
    orig_date   = qb.terms.Case().when(ple.voucher_no == ple.against_voucher_no, ple.posting_date).else_(None)
    
    query = (
        qb.from_(ple)
        .select(
            ple.party,
            ple.against_voucher_type.as_("voucher_type"),
            ple.against_voucher_no.as_("voucher_no"),
            Sum(ple.amount_in_account_currency).as_("outstanding"),
            Sum(orig_amount).as_("invoice_amount"),
            Max(orig_date).as_("posting_date"),
            Max(ple.account_currency).as_("currency"),
        )
        .where(Criterion.all(conditions))
        .groupby(ple.party, ple.against_voucher_type, ple.against_voucher_no)
        .having(Sum(ple.amount_in_account_currency) != 0)
    )
    
    if filters.has_ple_cc:
        query = query.select(Max(ple.cost_center).as_("cost_center"))
    if filters.has_ple_branch:
        query = query.select(Max(ple.branch).as_("branch"))
    if filters.has_ple_segment:
        query = query.select(Max(ple.segment).as_("segment"))
        
    results = query.run(as_dict=True)
    
    # Fast Bulk Map Party Names to avoid 1-by-1 query latency
    party_names_map = {}
    if results:
        distinct_parties = list(set(r.party for r in results if r.party))
        name_field = "customer_name" if filters.party_type == "Customer" else "supplier_name" if filters.party_type == "Supplier" else "name"
        
        # Pull everything safely in a single batched query execution
        try:
            party_data = frappe.get_all(filters.party_type, filters={"name": ["in", distinct_parties]}, fields=["name", name_field])
            party_names_map = {d.name: d.get(name_field) for d in party_data}
        except Exception:
            # Fallback if customized party type doesn't fit standard pattern
            party_names_map = {}

    rows = []
    sign = 1 if account_type == "Receivable" else -1
    
    allowed_statuses = filters.get("reconciliation_status")
    if isinstance(allowed_statuses, str):
        try: allowed_statuses = frappe.parse_json(allowed_statuses)
        except: allowed_statuses = [allowed_statuses]
            
    for r in results:
        outstanding_val = flt(r.outstanding, 2)
        if outstanding_val == 0: continue
            
        inv_amt_val = flt(r.invoice_amount)
        is_invoice = (inv_amt_val * sign) > 0
        abs_outstanding = abs(outstanding_val)
        abs_inv_amt = abs(inv_amt_val)
        
        status = get_status(abs_outstanding, abs_inv_amt) if is_invoice else _("Unreconciled")
        if allowed_statuses and status not in allowed_statuses: continue

        # Swapped assignment per requirements
        rows.append(frappe._dict({
            "section": _("Invoice") if is_invoice else _("Payment"),
            "party_type": filters.party_type,
            "party": r.party,
            "party_name": party_names_map.get(r.party) or r.party,
            "voucher_type": r.voucher_type,
            "voucher_no": r.voucher_no,
            "posting_date": r.posting_date,
            "invoice_amount": 0.0 if is_invoice else abs_outstanding, 
            "outstanding_amount": abs_outstanding if is_invoice else 0.0,
            "payment_amount": abs_inv_amt if is_invoice else 0.0,    
            "currency": r.currency,
            "reconciliation_status": status,
            "branch": r.get("branch") or "",
            "cost_center": r.get("cost_center") or "",
            "segment": r.get("segment") or "",
            "remarks": "" 
        }))
        
    _fetch_bulk_remarks(rows)
    return rows

def _fetch_bulk_remarks(rows):
    if not rows: return
    vouchers_by_type = {}
    for r in rows: vouchers_by_type.setdefault(r.voucher_type, set()).add(r.voucher_no)
        
    remarks_map = {}
    for vtype, vnames in vouchers_by_type.items():
        vnames = list(vnames)
        field = "remarks" if frappe.db.has_column(vtype, "remarks") else "remark" if frappe.db.has_column(vtype, "remark") else None
        if not field: continue
        for i in range(0, len(vnames), 1000):
            data = frappe.get_all(vtype, filters={"name": ("in", vnames[i:i+1000])}, fields=["name", field])
            for d in data: remarks_map[f"{vtype}-{d.name}"] = d.get(field) or ""
                
    for r in rows: r.remarks = remarks_map.get(f"{r.voucher_type}-{r.voucher_no}", "")

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_status(outstanding, total):
    if not total: return _("Unknown")
    if flt(outstanding) == 0: return _("Fully Reconciled")
    if flt(outstanding) < flt(total): return _("Partially Reconciled")
    return _("Unreconciled")

def get_chart(data):
    inv_rows = [r for r in data if r.section == _("Invoice")]
    total_inv = sum(flt(r.payment_amount) for r in inv_rows)
    total_outstanding = sum(flt(r.outstanding_amount) for r in inv_rows)
    total_reconciled = max(total_inv - total_outstanding, 0)
    return {
        "data": {"labels": [_("Outstanding"), _("Reconciled")], "datasets": [{"name": _("Invoice Amount"), "values": [total_outstanding, total_reconciled]}]},
        "type": "donut", "height": 260, "colors": ["#e74c3c", "#2ecc71"],
    }

def get_report_summary(data):
    inv_rows = [r for r in data if r.section == _("Invoice")]
    pay_rows = [r for r in data if r.section == _("Payment")]
    total_outstanding = sum(flt(r.outstanding_amount) for r in inv_rows)
    total_payment = sum(flt(r.invoice_amount) for r in pay_rows)
    unreconciled_inv = sum(1 for r in inv_rows if r.reconciliation_status == _("Unreconciled"))
    partial_inv = sum(1 for r in inv_rows if r.reconciliation_status == _("Partially Reconciled"))
    return [
        {"value": total_outstanding, "label": _("Total Outstanding Amount"), "datatype": "Currency", "indicator": "Red" if total_outstanding else "Green"},
        {"value": total_payment, "label": _("Total Unreconciled Payment Amount"), "datatype": "Currency", "indicator": "Orange" if total_payment else "Green"},
        {"value": unreconciled_inv, "label": _("Unreconciled Invoices"), "datatype": "Int", "indicator": "Red" if unreconciled_inv else "Green"},
        {"value": partial_inv, "label": _("Partially Reconciled Invoices"), "datatype": "Int", "indicator": "Orange" if partial_inv else "Green"},
    ]