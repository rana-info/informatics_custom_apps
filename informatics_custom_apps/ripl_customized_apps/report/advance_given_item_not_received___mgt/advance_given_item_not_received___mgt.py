import frappe
import json
from frappe.utils import flt



def execute(filters=None):

    filters = filters or {}

    view_by = filters.get("view_by") or "Status Wise"

    if view_by == "PO Wise":
        return get_po_columns(), get_po_data(filters)

    return get_summary_columns(view_by), get_summary_data(filters, view_by)


def get_summary_columns(view_by):

    label_map = {
        "Status Wise": "Status",
        "Supplier Wise": "Supplier",
        "Plant Wise": "Plant"
    }

    return [
        {
            "label": label_map.get(view_by, "Group"),
            "fieldname": "group_by",
            "fieldtype": "Data",
            "width": 520
        },
        {
            "label": "PO Amount",
            "fieldname": "po_amount",
            "fieldtype": "Currency",
            "width": 180
        },
        {
            "label": "Total Advance Paid",
            "fieldname": "advance_paid",
            "fieldtype": "Currency",
            "width": 180
        },
        {
            "label": "Material Received",
            "fieldname": "received_amount",
            "fieldtype": "Currency",
            "width": 180
        },
        {
            "label": "Pending Material",
            "fieldname": "pending_amount",
            "fieldtype": "Currency",
            "width": 180
        },
        
         {
            "label": "Material Received %",
            "fieldname": "material_received_percent",
            "fieldtype": "Percent",
            "width": 180,
            "precision":2
        },
        {
            "label": "Advance Paid %",
            "fieldname": "advance_paid_percent",
            "fieldtype": "Percent",
            "width": 180,
            "precision":2

        }
    ]


def get_summary_data(filters, view_by):

	conditions = get_conditions(filters)

	if view_by == "Status Wise":

		group_field = """
		CASE
			WHEN po.per_received = 0
				THEN 'Advance Paid - Goods Not Received'
			WHEN po.per_received < 100
				THEN 'Partially Received'
			ELSE 'Fully Received'
		END
		"""

	elif view_by == "Supplier Wise":
		group_field = """
		CONCAT(po.supplier, ' - ', IFNULL(po.supplier_name, ''))
		"""

	elif view_by == "Plant Wise":
		group_field = "po.branch"

	else:
		group_field = """
		CASE
			WHEN po.per_received = 0
				THEN 'Advance Paid - Goods Not Received'
			WHEN po.per_received < 100
				THEN 'Partially Received'
			ELSE 'Fully Received'
		END
		"""

	data = frappe.db.sql(f"""
		SELECT

			{group_field} AS group_by,

			SUM(po.base_grand_total) AS po_amount,

			SUM(
				IFNULL((
					SELECT SUM(per.allocated_amount)
					FROM `tabPayment Entry Reference` per
					INNER JOIN `tabPayment Entry` pe
						ON pe.name = per.parent
					WHERE per.reference_doctype = 'Purchase Order'
						AND per.reference_name = po.name
						AND pe.docstatus = 1
						AND pe.payment_type = 'Pay'
				), 0)
			) AS advance_paid,

			SUM(
				IFNULL((
					SELECT SUM(pri.base_amount)
					FROM `tabPurchase Receipt Item` pri
					INNER JOIN `tabPurchase Receipt` pr
						ON pr.name = pri.parent
					WHERE pri.purchase_order = po.name
						AND pr.docstatus = 1
				), 0)
			) AS received_amount,

			SUM(
				po.base_grand_total -
				IFNULL((
					SELECT SUM(pri.base_amount)
					FROM `tabPurchase Receipt Item` pri
					INNER JOIN `tabPurchase Receipt` pr
						ON pr.name = pri.parent
					WHERE pri.purchase_order = po.name
						AND pr.docstatus = 1
				), 0)
			) AS pending_amount,
   
   
      (ROUND(
        SUM(
            IFNULL((
                SELECT SUM(pri.base_amount)
                FROM `tabPurchase Receipt Item` pri
                INNER JOIN `tabPurchase Receipt` pr
                    ON pr.name = pri.parent
                WHERE pri.purchase_order = po.name
                  AND pr.docstatus = 1
            ), 0)
        ) / NULLIF(SUM(po.base_grand_total), 0),
        4
    ) *100 ) AS material_received_percent,

    (ROUND(
        SUM(
            IFNULL((
                SELECT SUM(per.allocated_amount)
                FROM `tabPayment Entry Reference` per
                INNER JOIN `tabPayment Entry` pe
                    ON pe.name = per.parent
                WHERE per.reference_doctype = 'Purchase Order'
                  AND per.reference_name = po.name
                  AND pe.docstatus = 1
                  AND pe.payment_type = 'Pay'
            ), 0)
        ) / NULLIF(SUM(po.base_grand_total), 0),
        4
    ) * 100) AS advance_paid_percent


		FROM `tabPurchase Order` po

		WHERE
			po.docstatus = 1
			AND po.per_received < 100

			AND IFNULL((
				SELECT SUM(per.allocated_amount)
				FROM `tabPayment Entry Reference` per
				INNER JOIN `tabPayment Entry` pe
					ON pe.name = per.parent
				WHERE per.reference_doctype = 'Purchase Order'
					AND per.reference_name = po.name
					AND pe.docstatus = 1
					AND pe.payment_type = 'Pay'
			), 0) > 0

			{conditions}
	
		GROUP BY group_by
		ORDER BY pending_amount DESC	
  	""",filters, as_dict=True)

	
	total_row = {
		"group_by": "TOTAL",
		"po_amount": sum(flt(d.get("po_amount")) for d in data),
		"advance_paid": sum(flt(d.get("advance_paid")) for d in data),
		"received_amount": sum(flt(d.get("received_amount")) for d in data),
		"pending_amount": sum(flt(d.get("pending_amount")) for d in data),
		"is_total_row": 1
	}

	data = [total_row] + data

	return data


def get_po_columns():

    return [
        {
            "label": "Purchase Order",
            "fieldname": "purchase_order",
            "fieldtype": "Link",
            "options": "Purchase Order",
            "width": 200
        },
        {
            "label": "PO Date",
            "fieldname": "transaction_date",
            "fieldtype": "Date",
            "width": 110
        },
        {
            "label": "Supplier",
            "fieldname": "supplier",
            "fieldtype": "Data",
            "options": "Supplier",
            "width": 420
        },
        {
            "label": "PO Amount",
            "fieldname": "po_amount",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": "Advance Paid",
            "fieldname": "advance_paid",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": "Received Amount",
            "fieldname": "received_amount",
            "fieldtype": "Currency",
            "width": 170
        },
        {
            "label": "Pending Value",
            "fieldname": "pending_amount",
            "fieldtype": "Currency",
            "width": 150
        },
        {
			"label": "Receipt %",
			"fieldname": "receipt_percent",
			"fieldtype": "Percent",
			"width": 120
		},
      
		{
			"label": "Pending Days",
			"fieldname": "pending_days",
			"fieldtype": "Int",
			"width": 120
		},
       {
			"label": "Status",
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 160
		},
        {
            "label": "Company",
            "fieldname": "company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 180
        },
        {
            "label": "Plant",
            "fieldname": "plant",
            "fieldtype": "Data",
            "width": 150
        },
    ]


def get_po_data(filters):

    conditions = get_conditions(filters)

    data = frappe.db.sql(f"""
        SELECT

            po.name AS purchase_order,
            po.transaction_date,
            CONCAT(po.supplier, ' - ', IFNULL(po.supplier_name, '')) AS supplier,
            po.company,
            po.branch AS plant,

            po.base_grand_total AS po_amount,

            IFNULL((
                SELECT SUM(per.allocated_amount)
                FROM `tabPayment Entry Reference` per
                INNER JOIN `tabPayment Entry` pe
                    ON pe.name = per.parent
                WHERE per.reference_doctype = 'Purchase Order'
                  AND per.reference_name = po.name
                  AND pe.docstatus = 1
                  AND pe.payment_type = 'Pay'
            ), 0) AS advance_paid,

            IFNULL((
                SELECT SUM(pri.base_amount)
                FROM `tabPurchase Receipt Item` pri
                INNER JOIN `tabPurchase Receipt` pr
                    ON pr.name = pri.parent
                WHERE pri.purchase_order = po.name
                  AND pr.docstatus = 1
            ), 0) AS received_amount,

            (
                po.base_grand_total -
                IFNULL((
                    SELECT SUM(pri.base_amount)
                    FROM `tabPurchase Receipt Item` pri
                    INNER JOIN `tabPurchase Receipt` pr
                        ON pr.name = pri.parent
                    WHERE pri.purchase_order = po.name
                      AND pr.docstatus = 1
                ), 0)
            ) AS pending_amount,

            ROUND(
                (
                    IFNULL((
                        SELECT SUM(pri.base_amount)
                        FROM `tabPurchase Receipt Item` pri
                        INNER JOIN `tabPurchase Receipt` pr
                            ON pr.name = pri.parent
                        WHERE pri.purchase_order = po.name
                          AND pr.docstatus = 1
                    ), 0)
                    / NULLIF(po.base_grand_total, 0)
                ) * 100,
                2
            ) AS receipt_percent,
            po.status,

            DATEDIFF(CURDATE(), po.transaction_date) AS pending_days

        FROM `tabPurchase Order` po

        WHERE
            po.docstatus = 1
            AND po.per_received < 100

            AND IFNULL((
                SELECT SUM(per.allocated_amount)
                FROM `tabPayment Entry Reference` per
                INNER JOIN `tabPayment Entry` pe
                    ON pe.name = per.parent
                WHERE per.reference_doctype = 'Purchase Order'
                  AND per.reference_name = po.name
                  AND pe.docstatus = 1
                  AND pe.payment_type = 'Pay'
            ), 0) > 0

            {conditions}

        ORDER BY pending_amount DESC, po.transaction_date ASC
    """, filters, as_dict=True)
    
    total_row = {
        "purchase_order": "TOTAL",
        "po_amount": sum(flt(d.get("po_amount")) for d in data),
        "advance_paid": sum(flt(d.get("advance_paid")) for d in data),
        "received_amount": sum(flt(d.get("received_amount")) for d in data),
        "pending_amount": sum(flt(d.get("pending_amount")) for d in data),
        "is_total_row": 1
    }

    data = [total_row] + data

    return data

def get_conditions(filters):

    conditions = ""

    if filters.get("from_date"):
        conditions += " AND po.transaction_date >= %(from_date)s "

    if filters.get("to_date"):
        conditions += " AND po.transaction_date <= %(to_date)s "

    companies = filters.get("company") or []

    if isinstance(companies, str):
        try:
            companies = json.loads(companies)
        except Exception:
            companies = [companies]

    if companies:
        conditions += f"""
            AND po.company IN ({",".join(frappe.db.escape(c) for c in companies)})
        """

    plants = filters.get("plant") or []

    if isinstance(plants, str):
        try:
            plants = json.loads(plants)
        except Exception:
            plants = [plants]

    if plants:
        conditions += f"""
            AND po.branch IN ({",".join(frappe.db.escape(p) for p in plants)})
        """

    return conditions