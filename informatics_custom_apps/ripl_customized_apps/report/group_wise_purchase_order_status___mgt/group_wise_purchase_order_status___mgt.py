# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	total_row = {
            "item_code": "TOTAL",
            "ordered_qty": sum(d.get("ordered_qty", 0) or 0 for d in data),
            "received_qty": sum(d.get("received_qty", 0) or 0 for d in data),
            "pending_qty": sum(d.get("pending_qty", 0) or 0 for d in data),

            "ordered_value": sum(d.get("ordered_value", 0) or 0 for d in data),
            "received_value": sum(d.get("received_value", 0) or 0 for d in data),
            "pending_value": sum(d.get("pending_value", 0) or 0 for d in data),

            "po_value": sum(
                float(d.get("po_value") or 0)
                for d in data
                if d.get("po_value") not in ("", None)
            ),

            "is_total_row": 1
        }
	data = [total_row] + data

	return columns, data


def get_columns():
    return [
        
        {
            "label": "Item Code",
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 340,
            "align":"left"
        },
           
         {
            "label": "Supplier Name",
            "fieldname": "supplier_name",
            "fieldtype": "Data",
            "width": 200
        },
          {
            "label": "PO Date",
            "fieldname": "po_date",
            "fieldtype": "Date",
            "width": 120
        },
       
        {
            "label": "Ordered Qty",
            "fieldname": "ordered_qty",
            "fieldtype": "Float",
            "width": 160
        },
        {
            "label": "Received Qty",
            "fieldname": "received_qty",
            "fieldtype": "Float",
            "width": 160
        },
        
        
        {
            "label": "Pending Qty",
            "fieldname": "pending_qty",
            "fieldtype": "Float",
            "width": 160
        },
           
        {
            "label": "Ordered Value",
            "fieldname": "ordered_value",
            "fieldtype": "Currency",
            "width": 160
        },
        {
            "label": "Received Value",
            "fieldname": "received_value",
            "fieldtype": "Currency",
            "width": 160
        },
        {
            "label": "Pending Value",
            "fieldname": "pending_value",
            "fieldtype": "Currency",
            "width": 160
        },
         {
            "label": "Receipt Status",
            "fieldname": "receipt_status",
            "fieldtype": "Data",
            "width": 140
        },
        
          {
            "label": "Plant",
            "fieldname": "plant",
            "fieldtype": "Data",
            "width": 140
        }, 
          
         {
            "label": "UOM",
            "fieldname": "uom",
            "fieldtype": "Data",
            "width": 80
        },
           {
            "label": "Segment",
            "fieldname": "segment",
            "fieldtype": "Data",
            "width": 140
        },
     
        {
            "label": "Item Group",
            "fieldname": "item_group",
            "fieldtype": "Data",
            "width": 140
        },
        
        
        {
            "label": "Item Name",
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 180
        },
      
      
     
        {
            "label": "Purchase Receipts",
            "fieldname": "purchase_receipts",
            "fieldtype": "Data",
            "width": 220
        },
       
        {
            "label": "Warehouse",
            "fieldname": "warehouse",
            "fieldtype": "Link",
            "options": "Warehouse",
            "width": 160
        },
        
        {
            "label": "Company",
            "fieldname": "company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 140
        },
        {
            "label": "PO Status",
            "fieldname": "po_status",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": "Supplier ID",
            "fieldname": "supplier",
            "fieldtype": "Link",
            "options": "Supplier",
            "width": 140
        },
            {
            "label": "PO No",
            "fieldname": "po_no",
            "fieldtype": "Link",
            "options": "Purchase Order",
            "width": 200
        }
 
    ]

def get_data(filters):

    conditions = ""
    values = {}

    if filters.get("from_date") and filters.get("to_date"):
        conditions += """
            AND po.transaction_date BETWEEN %(from_date)s AND %(to_date)s
        """
        values["from_date"] = filters.get("from_date")
        values["to_date"] = filters.get("to_date")

    if filters.get("company"):
        companies = filters.get("company")
        conditions += " AND po.company IN %(company)s"
        values["company"] = tuple(companies)

    if filters.get("plant"):
        plants = filters.get("plant")
        conditions += " AND wh.custom_branch IN %(plant)s"
        values["plant"] = tuple(plants)

    if filters.get("item_group"):
        item_groups = filters.get("item_group")
        conditions += " AND i.item_group IN %(item_group)s"
        values["item_group"] = tuple(item_groups)

    query = f"""
        SELECT

            po.transaction_date AS po_date,
            po.name AS po_no,
            po.company AS company,
            po.status AS po_status,

            po.supplier AS supplier,
            po.supplier_name AS supplier_name,

            poi.item_code AS item_code,
            poi.item_name AS item_name,
            i.item_group AS item_group,
            poi.uom AS uom,

            poi.warehouse AS warehouse,
            wh.custom_branch AS plant,
            wh.custom_segment AS segment,

            poi.qty AS ordered_qty,

            IFNULL(
                SUM(
                    CASE
                        WHEN pr.is_return = 1 THEN 0
                        ELSE pri.qty
                    END
                ),
                0
            ) AS received_qty,

            GREATEST(
                poi.qty -
                IFNULL(
                    SUM(
                        CASE
                            WHEN pr.is_return = 1 THEN 0
                            ELSE pri.qty
                        END
                    ),
                    0
                ),
                0
            ) AS pending_qty,

            poi.amount AS ordered_value,

            (
                poi.amount *
                IFNULL(
                    SUM(
                        CASE
                            WHEN pr.is_return = 1 THEN 0
                            ELSE pri.qty
                        END
                    ),
                    0
                )
                / NULLIF(poi.qty, 0)
            ) AS received_value,

            (
                poi.amount *
                GREATEST(
                    poi.qty -
                    IFNULL(
                        SUM(
                            CASE
                                WHEN pr.is_return = 1 THEN 0
                                ELSE pri.qty
                            END
                        ),
                        0
                    ),
                    0
                )
                / NULLIF(poi.qty, 0)
            ) AS pending_value,

            GROUP_CONCAT(
                DISTINCT CASE
                    WHEN pr.is_return = 1 THEN NULL
                    ELSE pri.parent
                END
            ) AS purchase_receipts,

            CASE
                WHEN IFNULL(
                    SUM(
                        CASE
                            WHEN pr.is_return = 1 THEN 0
                            ELSE pri.qty
                        END
                    ),
                    0
                ) = 0
                    THEN 'Not Received'

                WHEN GREATEST(
                    poi.qty -
                    IFNULL(
                        SUM(
                            CASE
                                WHEN pr.is_return = 1 THEN 0
                                ELSE pri.qty
                            END
                        ),
                        0
                    ),
                    0
                ) > 0
                    THEN 'Partially Received'

                ELSE 'Fully Received'
            END AS receipt_status

        FROM `tabPurchase Order` po

        JOIN `tabPurchase Order Item` poi
            ON po.name = poi.parent

        LEFT JOIN `tabPurchase Receipt Item` pri
            ON pri.purchase_order_item = poi.name
            AND pri.docstatus = 1

        LEFT JOIN `tabPurchase Receipt` pr
            ON pr.name = pri.parent
            AND pr.docstatus = 1

        LEFT JOIN `tabWarehouse` wh
            ON poi.warehouse = wh.name

        LEFT JOIN `tabItem` i
            ON poi.item_code = i.name

        WHERE
            po.docstatus = 1
            AND po.status NOT IN (
                'Closed',
                'Completed'
            )

            AND poi.item_code NOT IN (
                '125428',
                '125426',
                '111513',
                '111512',
                '125427',
                '111511',
                '125556',
                '125557',
                '125558'
            )

            AND i.item_group NOT IN (
                '030302-Service Item',
                '030202-Other Products-Service',
                '030101-Other Products-Service',
                '03-Services',
                'Products & Services',
                '0301-Sugar-Service'
            )

            {conditions}

        GROUP BY
            po.name,
            poi.name

        ORDER BY
            po.transaction_date DESC,
            po.name DESC
    """

    data= frappe.db.sql(query, values, as_dict=True)
    return data