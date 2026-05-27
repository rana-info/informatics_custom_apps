# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt
# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters or {})
    return columns, data


# =========================================================
# COLUMNS
# =========================================================

def get_columns():
    return [

        {
            "label": _("Posting Date"),
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 110
        },

        {
            "label": _("Company"),
            "fieldname": "company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 180
        },

        {
            "label": _("Account"),
            "fieldname": "account",
            "fieldtype": "Link",
            "options": "Account",
            "width": 240
        },

        {
            "label": _("Voucher Type"),
            "fieldname": "voucher_type",
            "fieldtype": "Data",
            "width": 140
        },

        {
            "label": _("Voucher Subtype"),
            "fieldname": "voucher_subtype",
            "fieldtype": "Data",
            "width": 170
        },

        {
            "label": _("Voucher No"),
            "fieldname": "voucher_no",
            "fieldtype": "Dynamic Link",
            "options": "voucher_type",
            "width": 180
        },

        {
            "label": _("Party"),
            "fieldname": "party",
            "fieldtype": "Data",
            "width": 150
        },

        {
            "label": _("Plant"),
            "fieldname": "plant",
            "fieldtype": "Link",
            "options": "Branch",
            "width": 130
        },

        {
            "label": _("Cost Center"),
            "fieldname": "cost_center",
            "fieldtype": "Link",
            "options": "Cost Center",
            "width": 180
        },

        {
            "label": _("Segment"),
            "fieldname": "segment",
            "fieldtype": "Link",
            "options": "Segment",
            "width": 130
        },

        {
            "label": _("Debit"),
            "fieldname": "debit",
            "fieldtype": "Currency",
            "width": 120
        },

        {
            "label": _("Credit"),
            "fieldname": "credit",
            "fieldtype": "Currency",
            "width": 120
        },

        {
            "label": _("Item Code"),
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 150
        },

        {
            "label": _("Item Name"),
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 220
        },

        {
            "label": _("Qty"),
            "fieldname": "qty",
            "fieldtype": "Float",
            "width": 100
        },

        {
            "label": _("Rate"),
            "fieldname": "rate",
            "fieldtype": "Currency",
            "width": 120
        },

        {
            "label": _("Item Value"),
            "fieldname": "item_value",
            "fieldtype": "Currency",
            "width": 140
        }

    ]


# =========================================================
# MAIN DATA
# =========================================================

def get_data(filters):

    conditions = ["gl.is_cancelled = 0"]
    values = {}

    # =====================================================
    # COMPANY
    # =====================================================

    if not filters.get("company"):
        frappe.throw(_("Company is mandatory"))

    company = filters.get("company")

    if isinstance(company, list):
        conditions.append("gl.company IN %(company)s")
        values["company"] = tuple(company)
    else:
        conditions.append("gl.company = %(company)s")
        values["company"] = company

    # =====================================================
    # DATE FILTERS
    # =====================================================

    if filters.get("from_date"):
        conditions.append("gl.posting_date >= %(from_date)s")
        values["from_date"] = filters.get("from_date")

    if filters.get("to_date"):
        conditions.append("gl.posting_date <= %(to_date)s")
        values["to_date"] = filters.get("to_date")

    # =====================================================
    # ACCOUNT
    # =====================================================

    if filters.get("account"):

        account = filters.get("account")

        if isinstance(account, list):
            conditions.append("gl.account IN %(account)s")
            values["account"] = tuple(account)
        else:
            conditions.append("gl.account = %(account)s")
            values["account"] = account

    # =====================================================
    # PLANT
    # =====================================================

    if filters.get("plant"):

        plant = filters.get("plant")

        if isinstance(plant, list):
            conditions.append("gl.branch IN %(plant)s")
            values["plant"] = tuple(plant)
        else:
            conditions.append("gl.branch = %(plant)s")
            values["plant"] = plant

    # =====================================================
    # SEGMENT
    # =====================================================

    if filters.get("segment"):

        segment = filters.get("segment")

        if isinstance(segment, list):
            conditions.append("gl.segment IN %(segment)s")
            values["segment"] = tuple(segment)
        else:
            conditions.append("gl.segment = %(segment)s")
            values["segment"] = segment

    # =====================================================
    # COST CENTER
    # =====================================================

    if filters.get("cost_center"):

        cost_center = filters.get("cost_center")

        if isinstance(cost_center, list):
            conditions.append("gl.cost_center IN %(cost_center)s")
            values["cost_center"] = tuple(cost_center)
        else:
            conditions.append("gl.cost_center = %(cost_center)s")
            values["cost_center"] = cost_center

    where_clause = " AND ".join(conditions)

    # =====================================================
    # GL ENTRIES
    # =====================================================

    gl_entries = frappe.db.sql(f"""
        SELECT
            gl.name,
            gl.posting_date,
            gl.company,
            gl.account,
            gl.voucher_type,
            gl.voucher_no,
            gl.voucher_subtype,
            gl.party,
            gl.branch AS plant,
            gl.cost_center,
            gl.segment,
            gl.debit,
            gl.credit
        FROM `tabGL Entry` gl
        WHERE {where_clause}
        ORDER BY
            gl.posting_date DESC,
            gl.creation DESC
    """, values, as_dict=True)

    if not gl_entries:
        return []

    # =====================================================
    # GROUP VOUCHERS
    # =====================================================

    vouchers = {}

    for gl in gl_entries:

        if not gl.voucher_no:
            continue

        vouchers.setdefault(gl.voucher_type, set()).add(gl.voucher_no)

    # =====================================================
    # ITEM MAP
    # =====================================================

    item_map = {}

    # =====================================================
    # SALES INVOICE
    # =====================================================

    if vouchers.get("Sales Invoice"):

        si_items = frappe.db.sql("""
            SELECT
                parent,
                item_code,
                item_name,
                qty,
                rate,
                amount
            FROM `tabSales Invoice Item`
            WHERE parent IN %(vouchers)s
        """, {
            "vouchers": tuple(vouchers.get("Sales Invoice"))
        }, as_dict=True)

        for d in si_items:
            item_map.setdefault(d.parent, []).append(d)

    # =====================================================
    # PURCHASE INVOICE
    # =====================================================

    if vouchers.get("Purchase Invoice"):

        pi_items = frappe.db.sql("""
            SELECT
                parent,
                item_code,
                item_name,
                qty,
                rate,
                amount
            FROM `tabPurchase Invoice Item`
            WHERE parent IN %(vouchers)s
        """, {
            "vouchers": tuple(vouchers.get("Purchase Invoice"))
        }, as_dict=True)

        for d in pi_items:
            item_map.setdefault(d.parent, []).append(d)

    # =====================================================
    # PURCHASE RECEIPT
    # =====================================================

    if vouchers.get("Purchase Receipt"):

        pr_items = frappe.db.sql("""
            SELECT
                parent,
                item_code,
                item_name,
                qty,
                rate,
                amount
            FROM `tabPurchase Receipt Item`
            WHERE parent IN %(vouchers)s
        """, {
            "vouchers": tuple(vouchers.get("Purchase Receipt"))
        }, as_dict=True)

        for d in pr_items:
            item_map.setdefault(d.parent, []).append(d)

    # =====================================================
    # DELIVERY NOTE
    # =====================================================

    if vouchers.get("Delivery Note"):

        dn_items = frappe.db.sql("""
            SELECT
                parent,
                item_code,
                item_name,
                qty,
                rate,
                amount
            FROM `tabDelivery Note Item`
            WHERE parent IN %(vouchers)s
        """, {
            "vouchers": tuple(vouchers.get("Delivery Note"))
        }, as_dict=True)

        for d in dn_items:
            item_map.setdefault(d.parent, []).append(d)

    # =====================================================
    # STOCK ENTRY
    # =====================================================

    if vouchers.get("Stock Entry"):

        se_items = frappe.db.sql("""
            SELECT
                parent,
                item_code,
                item_name,
                qty,
                basic_rate AS rate,
                basic_amount AS amount
            FROM `tabStock Entry Detail`
            WHERE parent IN %(vouchers)s
        """, {
            "vouchers": tuple(vouchers.get("Stock Entry"))
        }, as_dict=True)

        for d in se_items:
            item_map.setdefault(d.parent, []).append(d)

    # =====================================================
    # MATERIAL REQUEST
    # =====================================================

    if vouchers.get("Material Request"):

        mr_items = frappe.db.sql("""
            SELECT
                parent,
                item_code,
                item_name,
                qty,
                rate,
                amount
            FROM `tabMaterial Request Item`
            WHERE parent IN %(vouchers)s
        """, {
            "vouchers": tuple(vouchers.get("Material Request"))
        }, as_dict=True)

        for d in mr_items:
            item_map.setdefault(d.parent, []).append(d)

    # =====================================================
    # FINAL DATA
    # =====================================================

    data = []

    shown_voucher_items = set()

    for gl in gl_entries:

        items = item_map.get(gl.voucher_no, [])

        # =================================================
        # SHOW ITEMS ONLY FIRST TIME PER VOUCHER
        # =================================================

        if items and gl.voucher_no not in shown_voucher_items:

            for idx, item in enumerate(items):

                row = gl.copy()

                row.update({
                    "item_code": item.get("item_code") or "",
                    "item_name": item.get("item_name") or "",
                    "qty": item.get("qty") or 0,
                    "rate": item.get("rate") or 0,
                    "item_value": item.get("amount") or 0
                })

                # =========================================
                # PREVENT GL TOTAL DUPLICATION
                # =========================================

                if idx > 0:
                    row["debit"] = 0
                    row["credit"] = 0

                data.append(row)

            shown_voucher_items.add(gl.voucher_no)

        else:

            row = gl.copy()

            row.update({
                "item_code": "",
                "item_name": "",
                "qty": 0,
                "rate": 0,
                "item_value": 0
            })

            data.append(row)

    return data
