# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):

    filters = filters or {}

    columns = [
        {
            "label": "Purchase Order",
            "fieldname": "purchase_order",
            "fieldtype": "Link",
            "options": "Purchase Order",
            "width": 200,
        },
        {
            "label": "PO Date",
            "fieldname": "transaction_date",
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "label": "Ordered Items",
            "fieldname": "items",
            "fieldtype": "Data",
            "width": 450,
        },
        {
            "label": "PO Value",
            "fieldname": "amount",
            "fieldtype": "Currency",
            "width": 150,
        },
    ]

    # Don't load all records when report is opened directly
    if not filters.get("gl_account"):
        return columns, []

    conditions = []

    if filters.get("gl_account"):
        conditions.append("poi.expense_account = %(gl_account)s")

    if filters.get("cost_center"):
        conditions.append("poi.cost_center = %(cost_center)s")

    if filters.get("plant"):
        conditions.append("IFNULL(poi.branch,'') = %(plant)s")

    if filters.get("segment"):
        conditions.append("IFNULL(poi.segment,'') = %(segment)s")

    where_clause = ""
    if conditions:
        where_clause = " AND " + " AND ".join(conditions)

    data = frappe.db.sql(
        f"""
        SELECT
            po.name AS purchase_order,
            po.transaction_date,

            GROUP_CONCAT(
                DISTINCT poi.item_code
                ORDER BY poi.item_code
                SEPARATOR ', '
            ) AS items,

            SUM(poi.amount) AS amount

        FROM `tabPurchase Order Item` poi

        INNER JOIN `tabPurchase Order` po
            ON po.name = poi.parent

        WHERE po.docstatus = 1
            {where_clause}

        GROUP BY
            po.name,
            po.transaction_date

        ORDER BY
            po.transaction_date DESC,
            po.name DESC
        """,
        filters,
        as_dict=True,
    )

    return columns, data