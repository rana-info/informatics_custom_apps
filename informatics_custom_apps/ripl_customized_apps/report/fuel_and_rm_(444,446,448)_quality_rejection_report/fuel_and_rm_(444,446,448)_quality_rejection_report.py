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
            "label": "Rej.Qty",
            "fieldname": "rejected_qty",
            "fieldtype": "Float",
            "width": 100
        },
        
        {
            "label": "Quality Inspection",
            "fieldname": "quality_inspection",
            "fieldtype": "Link",
            "options": "Quality Inspection",
            "width": 200
        },
        
        {
            "label": "Purchase Receipt",
            "fieldname": "purchase_receipt",
            "fieldtype": "Link",
            "options": "Purchase Receipt",
            "width": 200
        },
        
        {
            "label": "Item Name",
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 200
        },
          
        {
            "label": "Item Code",
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 120
        },
        
        {
            "label": "Posting Date",
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 110
        },
      
        {
            "label": "Supplier",
            "fieldname": "supplier",
            "fieldtype": "Link",
            "options": "Supplier",
            "width": 160
        },
        {
            "label": "Item Group",
            "fieldname": "item_group",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": "UOM",
            "fieldname": "uom",
            "fieldtype": "Data",
            "width": 80
        },
        {
            "label": "Warehouse",
            "fieldname": "warehouse",
            "fieldtype": "Link",
            "options": "Warehouse",
            "width": 180
        },
        {
            "label": "Plant",
            "fieldname": "plant",
            "fieldtype": "Data",
            "width": 140
        },
        {
            "label": "Segment",
            "fieldname": "segment",
            "fieldtype": "Data",
            "width": 140
        },

        {
            "label": "Inspection Status",
            "fieldname": "inspection_status",
            "fieldtype": "Data",
            "width": 140
        },
        {
            "label": "Company",
            "fieldname": "company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 150
        }
    ]


def get_data(filters):

    conditions = []
    values = {}

    if filters.get("from_date") and filters.get("to_date"):
        conditions.append(
            "pr.posting_date BETWEEN %(from_date)s AND %(to_date)s"
        )

        values["from_date"] = filters.get("from_date")
        values["to_date"] = filters.get("to_date")

    if filters.get("company"):
        conditions.append("pr.company IN %(company)s")
        values["company"] = tuple(filters.get("company"))

    if filters.get("plant"):
        conditions.append("wh.custom_branch IN %(plant)s")
        values["plant"] = tuple(filters.get("plant"))

    extra_conditions = ""

    if conditions:
        extra_conditions = " AND " + " AND ".join(conditions)

    query = f"""
        SELECT

            pr.posting_date AS posting_date,
            pr.name AS purchase_receipt,
            pr.supplier AS supplier,

            pri.item_code,
            pri.item_name AS item_name,
            pri.item_group AS item_group,

            pri.rejected_qty AS rejected_qty,
            pri.uom AS uom,
            pri.warehouse AS warehouse,

            pri.branch AS plant,
            pri.segment AS segment,

            qi.name AS quality_inspection,
            qi.status AS inspection_status,

            pr.company AS company

        FROM
            `tabPurchase Receipt Item` pri

        INNER JOIN
            `tabPurchase Receipt` pr
            ON pr.name = pri.parent

        LEFT JOIN
            `tabQuality Inspection` qi
            ON qi.reference_name = pr.name
            AND qi.item_code = pri.item_code

        WHERE
            pr.docstatus = 1
            AND pri.rejected_qty > 0

            AND (
                pri.item_code IN (
                    '106448',
                    '106446',
                    '106444'
                )

                OR pri.item_group IN (
                    '020301-Fuel-Trd',
                    '020302-Fuel-Trd Non Weightment'
                )
            )

            {extra_conditions}

        ORDER BY
            pr.posting_date DESC,
            pr.name DESC
    """

    return frappe.db.sql(query, values, as_dict=True)