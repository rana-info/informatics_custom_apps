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
        # {"label": "Voucher Type", "fieldname": "voucher_type", "fieldtype": "Data"},
        {"label": "Voucher Type", "fieldtype": "Data", "fieldname": "voucher_type"},
        {"label": "Voucher", "fieldtype": "Dynamic Link", "fieldname": "voucher_no", "options": "voucher_type"},
        {"label": "GL Entry", "fieldname": "gl_entry", "fieldtype": "Link", "options": "GL Entry"},
        {"label": "Account", "fieldname": "account", "fieldtype": "Link", "options": "Account"},
        {"label": "Cost Center", "fieldname": "cost_center", "fieldtype": "Data"},
        {"label": "Party Type", "fieldname": "party_type", "fieldtype": "Data"},
        {"label": "Party", "fieldname": "party", "fieldtype": "Dynamic Link", "options": "party_type"},
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
            "account", "debit","cost_center","credit", "party_type", "party"
        ],
        order_by="posting_date asc"
    )

    output = []
    voucher_items_map = {}

    # Step 1: Fetch items per voucher
    for entry in entries:
        key = (entry.voucher_type, entry.voucher_no)
        if key not in voucher_items_map:
            try:
                doc = frappe.get_doc(entry.voucher_type, entry.voucher_no)
                if doc.docstatus == 1 and hasattr(doc, "items"):
                    voucher_items_map[key] = doc.items
                else:
                    voucher_items_map[key] = []
            except Exception:
                frappe.log_error(title="GL Report Error", message=frappe.get_traceback())
                voucher_items_map[key] = []

    # Step 2: Add GL Entries
    for entry in entries:
        output.append({
            "posting_date": entry.posting_date,
            "voucher_type": entry.voucher_type,
            "voucher_no": entry.voucher_no,
            "account": entry.account,
            "debit": entry.debit,
            "credit": entry.credit,
            "cost_center":entry.cost_center,
            "gl_entry": entry.name,
            "party_type": entry.party_type,
            "party": entry.party,
            "item_code": "",
            "item_name": "",
            "qty": 0,
            "rate": 0,
            "amount": 0
        })

    # Step 3: Add item rows (separately)
    for key, items in voucher_items_map.items():
        voucher_type, voucher_no = key
        for item in items:
            rate = "base_rate"
            if voucher_type=="Stock Entry":
                rate = "basic_rate"    
            output.append({
                "posting_date": "",  # or could use voucher date if needed
                "voucher_type": voucher_type,
                "voucher_no": voucher_no,
                "account": "",
                "debit": 0,
                "credit": 0,
                "gl_entry": "",
                "party_type": "",
                "party": "",
                "item_code": item.get("item_code"),
                "item_name": item.get("item_name"),
                "qty": item.get("qty"),
                "rate": item.get(rate),
                "amount": item.get("amount")
            })
    return output

# def get_data(filters):
#     entries = frappe.get_all(
#         "GL Entry",
#         filters={
#             "docstatus": 1,
#             "company": filters.get("company"),
#             "posting_date": ["between", [filters.get("from_date"), filters.get("to_date")]],
#             "account": filters.get("account") if filters.get("account") else ["!=", ""]
#         },
#         fields=["name", "posting_date", "voucher_type", "voucher_no", "account", "debit", "credit", "party_type", "party"],
#         order_by="posting_date asc"
#     )

#     output = []

#     for entry in entries:
#         base_row = {
#             "posting_date": entry.posting_date,
#             "voucher_type": entry.voucher_type,
#             "voucher_no": entry.voucher_no,
#             "account": entry.account,
#             "debit": entry.debit,
#             "credit": entry.credit,
#             "gl_entry": entry.name,
#             "party_type": entry.party_type,
#             "party": entry.party
#         }

#         try:
#             doc = frappe.get_doc(entry.voucher_type, entry.voucher_no)
#             if doc.docstatus != 1:
#                 continue

#             if hasattr(doc, "items"):
#                 for item in doc.items:
#                     row = base_row.copy()
#                     row.update({
#                         "item_code": item.get("item_code"),
#                         "item_name": item.get("item_name"),
#                         "qty": item.get("qty"),
#                         "rate": item.get("rate"),
#                         "amount": item.get("amount")
#                     })
#                     output.append(row)
#             else:
#                 output.append(base_row)

#         except Exception as e:
#             frappe.log_error(title="GL Report Error", message=frappe.get_traceback())
#             output.append(base_row)

#     return output
