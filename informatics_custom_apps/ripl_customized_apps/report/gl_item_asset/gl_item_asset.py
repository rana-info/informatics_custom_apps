# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 110},
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
        {"label": _("Account"), "fieldname": "account", "fieldtype": "Link", "options": "Account", "width": 160},
        {"label": _("Voucher Type"), "fieldname": "voucher_type", "fieldtype": "Link", "options": "DocType", "width": 140},
        {"label": _("Voucher No"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 160},
        {"label": _("Party"), "fieldname": "party", "fieldtype": "Data", "width": 140},
        {"label": _("Plant"), "fieldname": "plant", "fieldtype": "Link", "options": "Branch", "width": 120},
        {"label": _("Cost Center"), "fieldname": "cost_center", "fieldtype": "Link", "options": "Cost Center", "width": 140},
        {"label": _("Segment"), "fieldname": "segment", "fieldtype": "Link", "options": "Segment", "width": 120},
        {"label": _("Debit"), "fieldname": "debit", "fieldtype": "Currency", "width": 110},
        {"label": _("Credit"), "fieldname": "credit", "fieldtype": "Currency", "width": 110},

        {"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Data", "width": 130},
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
        {"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 90},
        {"label": _("Rate"), "fieldname": "rate", "fieldtype": "Currency", "width": 110},
        {"label": _("Item Value"), "fieldname": "item_value", "fieldtype": "Currency", "width": 140},

        # ✅ ASSET FIELDS
        {"label": _("Asset Repair"), "fieldname": "asset_repair", "fieldtype": "Link", "options": "Asset Repair", "width": 160},
        {"label": _("Asset Capitalization"), "fieldname": "asset_capitalization", "fieldtype": "Link", "options": "Asset Capitalization", "width": 180},
        {"label": _("Asset"), "fieldname": "asset", "fieldtype": "Link", "options": "Asset", "width": 150},
        {"label": _("Asset Name"), "fieldname": "asset_name", "fieldtype": "Data", "width": 180},
    ]


def get_data(filters):
    conditions = ["gl.is_cancelled = 0"]
    values = {}

    # ✅ COMPANY
    if filters.get("company"):
        conditions.append("gl.company IN %(company)s")
        values["company"] = tuple(filters.get("company"))
    else:
        frappe.throw(_("Company filter is required"))

    # ✅ DATE FILTERS
    if filters.get("from_date"):
        conditions.append("gl.posting_date >= %(from_date)s")
        values["from_date"] = filters.get("from_date")

    if filters.get("to_date"):
        conditions.append("gl.posting_date <= %(to_date)s")
        values["to_date"] = filters.get("to_date")

    # ✅ OTHER FILTERS
    if filters.get("account"):
        conditions.append("gl.account IN %(account)s")
        values["account"] = tuple(filters.get("account"))

    if filters.get("plant"):
        conditions.append("gl.branch IN %(plant)s")
        values["plant"] = tuple(filters.get("plant"))

    if filters.get("segment"):
        conditions.append("gl.segment IN %(segment)s")
        values["segment"] = tuple(filters.get("segment"))

    if filters.get("cost_center"):
        conditions.append("gl.cost_center IN %(cost_center)s")
        values["cost_center"] = tuple(filters.get("cost_center"))

    where_clause = " AND ".join(conditions)

    # ✅ GL ENTRIES
    gl_entries = frappe.db.sql(f"""
        SELECT
            gl.posting_date,
            gl.company,
            gl.account,
            gl.voucher_type,
            gl.voucher_no,
            gl.party,
            gl.branch as plant,
            gl.cost_center,
            gl.segment,
            gl.debit,
            gl.credit
        FROM `tabGL Entry` gl
        WHERE {where_clause}
        ORDER BY gl.posting_date DESC
    """, values, as_dict=True)

    # ✅ GROUP VOUCHERS
    vouchers = {}

    for d in gl_entries:
        vouchers.setdefault(d.voucher_type, []).append(d.voucher_no)

    item_map = {}

    # ✅ FETCH ITEMS
    for v_type, v_nos in vouchers.items():

        if not v_nos:
            continue

        # SALES INVOICE
        if v_type == "Sales Invoice":

            items = frappe.db.sql("""
                SELECT
                    parent,
                    item_code,
                    item_name,
                    qty,
                    rate,
                    income_account as item_account,

                    NULL as asset_repair,
                    NULL as asset_capitalization,
                    NULL as asset,
                    NULL as asset_name

                FROM `tabSales Invoice Item`
                WHERE parent IN %s
            """, (tuple(v_nos),), as_dict=True)

        # PURCHASE / DELIVERY / RECEIPT
        elif v_type in ["Purchase Invoice", "Delivery Note", "Purchase Receipt"]:

            items = frappe.db.sql(f"""
                SELECT
                    parent,
                    item_code,
                    item_name,
                    qty,
                    rate,
                    expense_account as item_account,

                    NULL as asset_repair,
                    NULL as asset_capitalization,
                    NULL as asset,
                    NULL as asset_name

                FROM `tab{v_type} Item`
                WHERE parent IN %s
            """, (tuple(v_nos),), as_dict=True)

        # STOCK ENTRY
        elif v_type == "Stock Entry":

            items = frappe.db.sql("""
                SELECT
                    ste.parent,
                    ste.item_code,
                    ste.item_name,
                    ste.qty,
                    ste.basic_rate as rate,
                    ste.expense_account as item_account,

                    ste.custom_asset_repair as asset_repair,
                    ste.custom_asset_capitalization as asset_capitalization,

                    ast.name as asset,
                    ast.asset_name as asset_name

                FROM `tabStock Entry Detail` ste

                LEFT JOIN `tabAsset Repair` ar
                    ON ar.name = ste.custom_asset_repair

                LEFT JOIN `tabAsset Capitalization` ac
                    ON ac.name = ste.custom_asset_capitalization

                LEFT JOIN `tabAsset` ast
                    ON ast.name = COALESCE(ar.asset, ac.target_asset)

                WHERE ste.parent IN %s
            """, (tuple(v_nos),), as_dict=True)

        else:
            continue

        for item in items:
            item_map.setdefault(item.parent, []).append(item)

    # ✅ FINAL DATA
    data = []

    for gl in gl_entries:

        items = item_map.get(gl.voucher_no, [])

        matched_items = [
            i for i in items
            if i.get("item_account") == gl.account
        ]

        if matched_items:

            for idx, item in enumerate(matched_items):

                item_value = (item.qty or 0) * (item.rate or 0)

                row = gl.copy()

                row.update({
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "qty": item.qty,
                    "rate": item.rate,
                    "item_value": item_value,

                    # ✅ ASSET FIELDS
                    "asset_repair": item.asset_repair,
                    "asset_capitalization": item.asset_capitalization,
                    "asset": item.asset,
                    "asset_name": item.asset_name,
                })

                # ✅ PREVENT GL DUPLICATION
                if idx > 0:
                    row["debit"] = 0
                    row["credit"] = 0

                data.append(row)

        else:

            gl.update({
                "item_code": "",
                "item_name": "",
                "qty": 0,
                "rate": 0,
                "item_value": 0,

                "asset_repair": "",
                "asset_capitalization": "",
                "asset": "",
                "asset_name": "",
            })

            data.append(gl)

    return data