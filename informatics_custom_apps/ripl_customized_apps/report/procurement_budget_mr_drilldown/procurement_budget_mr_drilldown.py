# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):

    filters = filters or {}

    columns = [
        {
            "label": "Material Request",
            "fieldname": "material_request",
            "fieldtype": "Link",
            "options": "Material Request",
            "width": 200,
        },
        {
            "label": "MR Date",
            "fieldname": "transaction_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": "Requested Items",
            "fieldname": "items",
            "fieldtype": "Data",
            "width": 400,
        },
        {
            "label": "Requested Value",
            "fieldname": "mr_amount",
            "fieldtype": "Currency",
            "width": 140,
        },
        {
            "label": "Ordered Value",
            "fieldname": "po_amount",
            "fieldtype": "Currency",
            "width": 140,
        },
        {
            "label": "Pending Value",
            "fieldname": "remaining_amount",
            "fieldtype": "Currency",
            "width": 140,
        },
    ]

    # Don't load entire database if report is opened directly
    if not filters.get("gl_account"):
        return columns, []

    conditions = []

    if filters.get("gl_account"):
        conditions.append("mri.expense_account = %(gl_account)s")

    if filters.get("cost_center"):
        conditions.append("mri.cost_center = %(cost_center)s")

    if filters.get("plant"):
        conditions.append("IFNULL(mri.branch,'') = %(plant)s")

    if filters.get("segment"):
        conditions.append("IFNULL(mri.segment,'') = %(segment)s")

    where_clause = ""
    if conditions:
        where_clause = " AND " + " AND ".join(conditions)

    data = frappe.db.sql(
        f"""
        SELECT
            mr.name AS material_request,
            mr.transaction_date,

            GROUP_CONCAT(
                DISTINCT mri.item_code
                ORDER BY mri.item_code
                SEPARATOR ', '
            ) AS items,

            SUM(mri.amount) AS mr_amount,

            COALESCE(
                SUM(po_map.po_amount),
                0
            ) AS po_amount,

            SUM(mri.amount)
            -
            COALESCE(
                SUM(po_map.po_amount),
                0
            ) AS remaining_amount

        FROM `tabMaterial Request Item` mri

        INNER JOIN `tabMaterial Request` mr
            ON mr.name = mri.parent

        LEFT JOIN
        (
            SELECT
                poi.material_request_item,
                SUM(poi.amount) AS po_amount
            FROM `tabPurchase Order Item` poi
            INNER JOIN `tabPurchase Order` po
                ON po.name = poi.parent
            WHERE po.docstatus = 1
                AND poi.material_request_item IS NOT NULL
            GROUP BY poi.material_request_item
        ) po_map
            ON po_map.material_request_item = mri.name

        WHERE mr.docstatus = 1
            AND mr.material_request_type = 'Purchase'
            {where_clause}

        GROUP BY
            mr.name,
            mr.transaction_date

        ORDER BY
            mr.transaction_date DESC,
            mr.name DESC
        """,
        filters,
        as_dict=True,
    )

    return columns, data