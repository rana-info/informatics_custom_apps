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
            "label": "Material Request",
            "fieldname": "material_request",
            "fieldtype": "Link",
            "options": "Material Request",
            "width": 160,
        },
        {
            "label": "MR Date",
            "fieldname": "mr_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": "Item Code",
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 140,
        },
        {
            "label": "Item Name",
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "label": "Item Group",
            "fieldname": "item_group",
            "fieldtype": "Link",
            "options": "Item Group",
            "width": 150,
        },
        {
            "label": "UOM",
            "fieldname": "uom",
            "fieldtype": "Data",
            "width": 80,
        },
        {
            "label": "Plant",
            "fieldname": "branch",
            "fieldtype": "Link",
            "options": "Branch",
            "width": 140,
        },
  
        {
            "label": "Segment",
            "fieldname": "segment",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": "MR Qty",
            "fieldname": "mr_qty",
            "fieldtype": "Float",
            "width": 120,
        },
        {
            "label": "Purchase Order",
            "fieldname": "purchase_order",
            "fieldtype": "Link",
            "options": "Purchase Order",
            "width": 170,
        },
        {
            "label": "PO Date",
            "fieldname": "po_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": "Supplier Code",
            "fieldname": "supplier",
            "fieldtype": "Link",
            "options": "Supplier",
            "width": 150,
        },
        {
            "label": "Supplier Name",
            "fieldname": "supplier_name",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "label": "PO Qty",
            "fieldname": "po_qty",
            "fieldtype": "Float",
            "width": 120,
        },
        {
            "label": "Required Date",
            "fieldname": "required_date",
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "label": "Purchase Receipt",
            "fieldname": "purchase_receipt",
            "fieldtype": "Link",
            "options": "Purchase Receipt",
            "width": 170,
        },
        {
            "label": "Receipt Date",
            "fieldname": "receipt_date",
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "label": "Received Qty",
            "fieldname": "received_qty",
            "fieldtype": "Float",
            "width": 120,
        },
        {
            "label": "Buyer Delay (MR→PO Days)",
            "fieldname": "buyer_delay",
            "fieldtype": "Int",
            "width": 170,
        },
        {
            "label": "Supplier Delay (PO→GRN Days)",
            "fieldname": "supplier_delay",
            "fieldtype": "Int",
            "width": 190,
        },
        {
            "label": "Total Procurement Days",
            "fieldname": "total_procurement_days",
            "fieldtype": "Int",
            "width": 170,
        },
        {
            "label": "Delivery Delay vs Required Date",
            "fieldname": "delivery_delay",
            "fieldtype": "Int",
            "width": 210,
        },
        {
            "label": "PO / GRN Status",
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 180,
        },
    ]
def get_data(filters):

    conditions = ""
    values = {}

    if filters.get("company"):
        conditions += " AND mr.company = %(company)s "
        values["company"] = filters.get("company")

    if filters.get("branch"):

        branches = filters.get("branch")

        if isinstance(branches, str):
            branches = [b.strip() for b in branches.split(",") if b.strip()]

        if branches:

            branch_placeholders = ", ".join(
                [f"%(branch_{i})s" for i in range(len(branches))]
            )

            conditions += f" AND mr.branch IN ({branch_placeholders}) "

            for i, branch in enumerate(branches):
                values[f"branch_{i}"] = branch

    query = f"""
        SELECT
            mr.name AS material_request,
            mr.transaction_date AS mr_date,

            mri.item_code,
            mri.item_name,
            i.item_group,

            i.stock_uom AS uom,

            mr.branch,
            mri.segment,

            ROUND(mri.qty,2) AS mr_qty,

            po.name AS purchase_order,
            po.transaction_date AS po_date,

            po.supplier,
            po.supplier_name,

            ROUND(poi.qty,2) AS po_qty,
            poi.schedule_date AS required_date,

            pr.name AS purchase_receipt,
            pr.posting_date AS receipt_date,

            ROUND(IFNULL(SUM(pri.qty),0),2) AS received_qty,

            DATEDIFF(po.transaction_date, mr.transaction_date)
                AS buyer_delay,

            DATEDIFF(pr.posting_date, po.transaction_date)
                AS supplier_delay,

            DATEDIFF(pr.posting_date, mr.transaction_date)
                AS total_procurement_days,

            DATEDIFF(pr.posting_date, poi.schedule_date)
                AS delivery_delay,

            CASE
                WHEN po.docstatus = 0 THEN 'PO Draft'

                WHEN po.docstatus = 1
                AND IFNULL(SUM(pri.qty),0) = 0
                THEN 'PO Submitted - No GRN'

                WHEN po.docstatus = 1
                AND SUM(pri.qty) < poi.qty
                THEN 'Partial GRN'

                WHEN po.docstatus = 1
                AND SUM(pri.qty) >= poi.qty
                THEN 'Full GRN'

                ELSE 'Unknown'
            END AS status

        FROM `tabMaterial Request` mr

        INNER JOIN `tabMaterial Request Item` mri
            ON mri.parent = mr.name

        INNER JOIN `tabItem` i
            ON i.name = mri.item_code

        INNER JOIN `tabPurchase Order Item` poi
            ON poi.material_request = mr.name
            AND poi.material_request_item = mri.name

        INNER JOIN `tabPurchase Order` po
            ON po.name = poi.parent

        LEFT JOIN `tabPurchase Receipt Item` pri
            ON pri.purchase_order_item = poi.name

        LEFT JOIN `tabPurchase Receipt` pr
            ON pr.name = pri.parent
            AND pr.docstatus = 1
            AND IFNULL(pr.is_return,0) = 0

        WHERE mr.docstatus = 1
        AND mr.material_request_type = 'Purchase'
        AND LEFT(i.item_group,6) NOT IN ('020201','020202','020203')

        {conditions}

        GROUP BY
            mr.name,
            mri.name,
            poi.name

        ORDER BY mr.transaction_date DESC
    """

    return frappe.db.sql(query, values, as_dict=1)