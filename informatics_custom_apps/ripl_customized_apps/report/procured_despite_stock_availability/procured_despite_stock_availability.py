# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    return [
        {
            "label": "Item Code",
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 150,
        },
        {
            "label": "Item Name",
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "label": "Ordering Company",
            "fieldname": "ordering_company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 180,
        },
        {
            "label": "Ordering Warehouse",
            "fieldname": "ordering_warehouse",
            "fieldtype": "Link",
            "options": "Warehouse",
            "width": 180,
        },
        {
            "label": "Ordered Qty",
            "fieldname": "ordered_qty",
            "fieldtype": "Float",
            "width": 120,
        },
        {
            "label": "Stock in Own WH",
            "fieldname": "stock_in_own_wh",
            "fieldtype": "Float",
            "width": 150,
        },
        {
            "label": "Max Stock in Other WH",
            "fieldname": "max_stock_in_other_wh",
            "fieldtype": "Float",
            "width": 150,
        },
        {
            "label": "Other Warehouses",
            "fieldname": "other_warehouses",
            "fieldtype": "Data",
            "width": 250,
        },
        {
            "label": "Other Companies",
            "fieldname": "other_companies",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "label": "Purchase Orders",
            "fieldname": "purchase_orders",
            "fieldtype": "Data",
            "width": 300,
        },
        {
            "label": "Material Requests",
            "fieldname": "material_requests",
            "fieldtype": "Data",
            "width": 250,
        },
        {
            "label": "Requested By",
            "fieldname": "requested_by",
            "fieldtype": "Data",
            "width": 250,
        },
    ]


def get_data(filters):

    conditions = ""

    if filters.get("company"):
        conditions += " AND po.company = %(company)s "

    query = f"""
        SELECT
            poi.item_code AS item_code,
            poi.item_name AS item_name,

            po.company AS ordering_company,
            poi.warehouse AS ordering_warehouse,

            SUM(poi.qty) AS ordered_qty,

            MAX(IFNULL(bin.actual_qty,0)) AS stock_in_own_wh,

            MAX(IFNULL(bin2.actual_qty,0)) AS max_stock_in_other_wh,

            GROUP_CONCAT(DISTINCT wh2.name)
                AS other_warehouses,

            GROUP_CONCAT(DISTINCT wh2.company)
                AS other_companies,

            GROUP_CONCAT(
                DISTINCT po.name
                ORDER BY po.transaction_date
            ) AS purchase_orders,

            GROUP_CONCAT(DISTINCT poi.material_request)
                AS material_requests,

            GROUP_CONCAT(
                DISTINCT CONCAT(
                    IFNULL(mr.employee,''),
                    ' - ',
                    IFNULL(mr.employee_name,'')
                )
            ) AS requested_by

        FROM `tabPurchase Order` po

        INNER JOIN `tabPurchase Order Item` poi
            ON poi.parent = po.name

        LEFT JOIN `tabMaterial Request` mr
            ON mr.name = poi.material_request

        LEFT JOIN `tabBin` bin
            ON bin.item_code = poi.item_code
            AND bin.warehouse = poi.warehouse

        LEFT JOIN `tabBin` bin2
            ON bin2.item_code = poi.item_code
            AND bin2.actual_qty > 0

        LEFT JOIN `tabWarehouse` wh2
            ON wh2.name = bin2.warehouse
            AND wh2.company != po.company

        WHERE
            po.docstatus = 1
            AND po.transaction_date BETWEEN %(from_date)s
            AND %(to_date)s

            {conditions}

        GROUP BY
            poi.item_code,
            po.company,
            poi.warehouse

        HAVING
            MAX(IFNULL(bin.actual_qty,0)) < SUM(poi.qty)
            AND MAX(IFNULL(bin2.actual_qty,0)) >= SUM(poi.qty)

        ORDER BY
            poi.item_code
    """

    return frappe.db.sql(query, filters, as_dict=1)