# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "As On Date", "fieldname": "as_on_date", "fieldtype": "Date", "width": 120},

        {"label": "Plant", "fieldname": "plant", "fieldtype": "Data", "width": 120},
        {"label": "Warehouse", "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 180},
        {"label": "Account", "fieldname": "account", "fieldtype": "Link", "options": "Account", "width": 180},
        {"label": "Segment", "fieldname": "segment", "fieldtype": "Data", "width": 150},

        {"label": "Material Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": "Material Description", "fieldname": "item_name", "fieldtype": "Data", "width": 200},
        {"label": "UOM", "fieldname": "stock_uom", "fieldtype": "Data", "width": 80},

        {"label": "Quantity", "fieldname": "qty", "fieldtype": "Float", "width": 120},
        {"label": "Value", "fieldname": "value", "fieldtype": "Currency", "width": 120},
        {"label": "Rate", "fieldname": "rate", "fieldtype": "Currency", "width": 120},
    ]

def get_data(filters):

    company = filters.get("company")
    plant = filters.get("plant") or []
    segment = filters.get("segment") or []

    conditions = [
        "sle.docstatus = 1",
        "sle.is_cancelled = 0",
        "sle.posting_date <= %(to_date)s"
    ]

    # Company filter
    if company:
        conditions.append("wh.company = %(company)s")

    # Multi Plant filter
    if plant:
        conditions.append("wh.custom_branch IN %(plant)s")

    # Multi Segment filter
    if segment:
        conditions.append("wh.custom_segment IN %(segment)s")

    where_clause = " AND ".join(conditions)

    return frappe.db.sql(f"""
        SELECT
            %(to_date)s AS as_on_date,

            t.Plant AS plant,
            t.Warehouse AS warehouse,
            t.Account AS account,
            t.Segment AS segment,

            t.item_code,
            t.item_name,
            t.stock_uom,

            ROUND(SUM(t.qty), 2) AS qty,
            ROUND(SUM(t.value), 2) AS value,

            CASE 
                WHEN SUM(t.qty) != 0 
                THEN ROUND(SUM(t.value) / SUM(t.qty), 2)
                ELSE 0 
            END AS rate

        FROM (

            SELECT
                wh.custom_branch AS Plant,
                wh.name AS Warehouse,
                wh.account AS Account,
                wh.custom_segment AS Segment,

                sle.item_code,
                i.item_name,
                i.stock_uom,

                sle.actual_qty AS qty,
                sle.stock_value_difference AS value

            FROM `tabStock Ledger Entry` sle

            LEFT JOIN `tabItem` i 
                ON sle.item_code = i.name

            LEFT JOIN `tabWarehouse` wh 
                ON sle.warehouse = wh.name

            WHERE {where_clause}

        ) t

        GROUP BY 
            t.Plant,
            t.Warehouse,
            t.Account,
            t.Segment,
            t.item_code,
            t.item_name,
            t.stock_uom

        HAVING 
            ROUND(SUM(t.qty), 2) >= 0

        ORDER BY 
            SUM(t.value) DESC

    """, {
        "to_date": filters.get("to_date"),
        "company": company,
        "plant": tuple(plant) if plant else None,
        "segment": tuple(segment) if segment else None
    }, as_dict=1)