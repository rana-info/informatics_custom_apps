# Copyright (c) 2025, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date"},
        {"label": "Voucher Type", "fieldtype": "Data", "fieldname": "voucher_type"},
        {"label": "Voucher Subtype", "fieldtype": "Data", "fieldname": "voucher_subtype"},
        {"label": "Voucher", "fieldtype": "Dynamic Link", "fieldname": "voucher_no", "options": "voucher_type"},
        {"label": "GL Entry", "fieldname": "gl_entry", "fieldtype": "Link", "options": "GL Entry"},
        {"label": "Account", "fieldname": "account", "fieldtype": "Link", "options": "Account"},
        {"label": "Cost Center", "fieldname": "cost_center", "fieldtype": "Data"},
        {"label": "Plant", "fieldname": "plant", "fieldtype": "Data"},
        {"label": "Segment", "fieldname": "segment", "fieldtype": "Data"},
        {"label": "Party Type", "fieldname": "party_type", "fieldtype": "Data"},
        {"label": "Party", "fieldname": "party", "fieldtype": "Dynamic Link", "options": "party_type"},
        {"label": "Party Name", "fieldname": "party_name", "fieldtype": "Data"},
        {"label": "Debit", "fieldname": "debit", "fieldtype": "Currency"},
        {"label": "Credit", "fieldname": "credit", "fieldtype": "Currency"},
        {"label": "Item Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item"},
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data"},
        {"label": "Qty", "fieldname": "qty", "fieldtype": "Float"},
        {"label": "Rate", "fieldname": "rate", "fieldtype": "Currency"},
        {"label": "Amount", "fieldname": "amount", "fieldtype": "Currency"},
    ]

def get_data(filters):
    entries = frappe.get_all(
        "GL Entry",
        filters={
            "docstatus": 1,
            "company": filters.get("company"),
            "posting_date": ["between", [filters.get("from_date"), filters.get("to_date")]],
            "account": filters.get("account") if filters.get("account") else ["!=", ""]
        },
        fields=[
            "name", "posting_date", "voucher_type", "voucher_no",
            "voucher_subtype", "account", "debit", "credit",
            "cost_center", "party_type", "party", "segment"
        ],
        order_by="posting_date asc"
    )

    output = []
    voucher_items_map = {}
    voucher_doc_map = {}
    voucher_subtype_map = {}

    # Step 1: Prepare maps
    for entry in entries:
        key = (entry.voucher_type, entry.voucher_no)

        # Save subtype from GL Entry
        if key not in voucher_subtype_map:
            voucher_subtype_map[key] = entry.voucher_subtype or ""

        # Save voucher doc and items
        if key not in voucher_doc_map:
            try:
                doc = frappe.get_doc(entry.voucher_type, entry.voucher_no)
                if doc.docstatus == 1:
                    voucher_doc_map[key] = doc
                    if hasattr(doc, "items"):
                        voucher_items_map[key] = doc.items
                    else:
                        voucher_items_map[key] = []
                else:
                    voucher_doc_map[key] = None
                    voucher_items_map[key] = []
            except Exception:
                frappe.log_error(title="GL Report Error", message=frappe.get_traceback())
                voucher_doc_map[key] = None
                voucher_items_map[key] = []

    # Step 2: Add GL Entry rows
    for entry in entries:
        key = (entry.voucher_type, entry.voucher_no)
        doc = voucher_doc_map.get(key)
        plant = doc.branch if (doc and hasattr(doc, "branch")) else ""

        output.append({
            "posting_date": entry.posting_date,
            "voucher_type": entry.voucher_type,
            "voucher_subtype": entry.voucher_subtype or "",
            "voucher_no": entry.voucher_no,
            "account": entry.account,
            "debit": entry.debit,
            "credit": entry.credit,
            "cost_center": entry.cost_center,
            "plant": plant,
            "segment": entry.segment,
            "gl_entry": entry.name,
            "party_type": entry.party_type,
            "party": entry.party,
            "party_name": get_party_name(entry.party_type, entry.party),
            "item_code": "",
            "item_name": "",
            "qty": 0,
            "rate": 0,
            "amount": 0
        })

    # Step 3: Add item rows
    for key, items in voucher_items_map.items():
        voucher_type, voucher_no = key
        doc = voucher_doc_map.get(key)

        posting_date = doc.posting_date if (doc and hasattr(doc, "posting_date")) else ""
        voucher_subtype = voucher_subtype_map.get(key, "")

        for item in items:
            rate_field = "base_rate"
            if voucher_type == "Stock Entry":
                rate_field = "basic_rate"

            output.append({
                "posting_date": posting_date,
                "voucher_type": voucher_type,
                "voucher_subtype": voucher_subtype,
                "voucher_no": voucher_no,
                "account": "",
                "debit": 0,
                "credit": 0,
                "cost_center": "",
                "plant": item.get("branch") or (doc.branch if (doc and hasattr(doc, "branch")) else ""),
                "segment": item.get("segment") or "",   # ✅ segment directly from item child row
                "gl_entry": "",
                "party_type": "",
                "party": "",
                "party_name": "",
                "item_code": item.get("item_code"),
                "item_name": item.get("item_name"),
                "qty": item.get("qty"),
                "rate": item.get(rate_field),
                "amount": item.get("amount")
            })

    

    return output

def get_party_name(party_type, party):
    """Fetch readable Party Name from linked doctype"""
    if not party_type or not party:
        return ""
    try:
        return frappe.db.get_value(party_type, party, party_type.lower() + "_name") or party
    except Exception:
        return party
