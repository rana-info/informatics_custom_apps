# Copyright (c) 2025, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
    {"label": "ID", "fieldname": "id", "fieldtype": "Data"},
    {"label": "Company", "fieldname": "company", "fieldtype": "Link","options": "Company"},
    {"label": "Posting Date", "fieldname": "pd", "fieldtype": "Date"},
    {"label": "Challan Type", "fieldname": "ct", "fieldtype": "Data"},
    {"label": "Segment", "fieldname": "segment", "fieldtype": "Data"},
    {"label": "Item Amount", "fieldname": "total", "fieldtype": "Data"},
    {"label": "Item Code", "fieldname": "item_code", "fieldtype": "Link","options": "Item"},
    {"label": "Item Name", "fieldname": "item_desc", "fieldtype": "Data"},
    {"label": "Item UOM", "fieldname": "uom", "fieldtype": "Data"},
    {"label": "Quantity Sent", "fieldname": "qty", "fieldtype": "Data"},
    {"label": "Quantity Received", "fieldname": "qtyr", "fieldtype": "Data"},
    {"label": "Balance Quantity", "fieldname": "bqty", "fieldtype": "Data"},
    {"label": "Cost Center", "fieldname": "cc", "fieldtype": "Link","options": "Cost Center"},
    {"label": "Expense Account", "fieldname": "expense_acc", "fieldtype": "Link", "options": "Account"},
    ]

def get_data(filters):
    output = []

    # Get parent Stock Entries
    s_entries = frappe.get_all(
        "Stock Entry",
        filters={
            "docstatus": 1,
            "branch": filters.get("plant"),
            "name": filters.get("se")
        },
        fields=[
            "name", "posting_date", "custom_challan_type", "company",
            "segment", "base_grand_total"
        ],
        order_by="posting_date asc"
    )
    
    # Loop through parent s_entries
    for parent in s_entries:
        # Get child table rows for this parent
        child_rows = frappe.get_all(
            "Stock Entry Detail",
            filters={"parent": parent.name},
            fields=[
                "item_code","uom","basic_amount","qty","item_name", "cost_center", "expense_account"
            ]
        )

        # Loop through child rows and append to output
        for child in child_rows:
            output.append({
                "id": parent.name,
                "company": parent.company,
                "pd": parent.posting_date,
                "ct": parent.custom_challan_type,
                "segment": parent.segment,
                "total": child.basic_amount,
                "item_code": child.item_code,
                "qty": child.qty,
                "item_desc":child.item_name,
                "uom":child.uom,
                "qtyr": "P",
                "bqty": "P", #child.qty - (child.received_qty or 0)
                "cc": child.cost_center,
                "expense_acc": child.expense_account
            })

    return output
