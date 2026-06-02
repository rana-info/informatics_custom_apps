# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cint


def normalize_multiselect(value):
    if not value:
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return value



def make_in_clause(field, values, values_dict):
    if not values:
        return ""

    placeholders = []

    for i, v in enumerate(values):
        key = f"{field.replace('.', '_')}_{i}"
        placeholders.append(f"%({key})s")
        values_dict[key] = v

    return f"AND {field} IN ({', '.join(placeholders)})"



def execute(filters=None):

    filters = filters or {}

    if filters.get("report_view") == "Detail":
        return get_detail_columns(), get_detail_data(filters)

    return get_summary_columns(), get_summary_data(filters)



def get_summary_columns():
    return [
        {"label": "Plant", "fieldname": "branch", "fieldtype": "Data", "width": 180},
        {"label": "Segment", "fieldname": "segment", "fieldtype": "Data", "width": 150},
        {"label": "Avg Buyer Delay(MR→PO)", "fieldname": "buyer_delay", "fieldtype": "Float", "width": 200},
        {"label": "Avg Supplier Delay(PO→GRN)", "fieldname": "supplier_delay", "fieldtype": "Float", "width": 250},
        {"label": "Avg Procurement Days", "fieldname": "total_procurement_days", "fieldtype": "Float", "width": 180},
        {"label": "Avg Delivery Delay", "fieldname": "delivery_delay", "fieldtype": "Float", "width": 180},
        {"label": "Total MRs", "fieldname": "total_mrs", "fieldtype": "Int", "width": 120},
        {"label": "Total POs", "fieldname": "total_pos", "fieldtype": "Int", "width": 120},
    ]


def get_summary_data(filters):

	values = {}

	companies = normalize_multiselect(filters.get("company"))
	branches = normalize_multiselect(filters.get("branch"))

	company_condition = make_in_clause("mr.company", companies, values)
	branch_condition = make_in_clause("mr.branch", branches, values)
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")

	date_condition = ""

	if from_date and to_date:
		date_condition = " AND mr.transaction_date BETWEEN %(from_date)s AND %(to_date)s "
	elif from_date:
		date_condition = " AND mr.transaction_date >= %(from_date)s "
	elif to_date:
		date_condition = " AND mr.transaction_date <= %(to_date)s "

	values["from_date"] = from_date
	values["to_date"] = to_date

	query = f"""
		SELECT
			mr.branch AS branch,
			mri.segment AS segment,

			ROUND(AVG(DATEDIFF(po.transaction_date, mr.transaction_date)), 2) AS buyer_delay,
			ROUND(AVG(DATEDIFF(pr.posting_date, po.transaction_date)), 2) AS supplier_delay,
			ROUND(AVG(DATEDIFF(pr.posting_date, mr.transaction_date)), 2) AS total_procurement_days,
			ROUND(AVG(DATEDIFF(pr.posting_date, poi.schedule_date)), 2) AS delivery_delay,

			COUNT(DISTINCT mr.name) AS total_mrs,
			COUNT(DISTINCT po.name) AS total_pos,

			1 AS is_summary

		FROM `tabMaterial Request` mr

		LEFT JOIN `tabMaterial Request Item` mri
			ON mri.parent = mr.name

		LEFT JOIN `tabItem` i
			ON i.name = mri.item_code

		LEFT JOIN `tabPurchase Order Item` poi
			ON poi.material_request = mr.name
			AND poi.material_request_item = mri.name

		LEFT JOIN `tabPurchase Order` po
			ON po.name = poi.parent
			AND po.docstatus = 1

		LEFT JOIN `tabPurchase Receipt Item` pri
			ON pri.purchase_order_item = poi.name

		LEFT JOIN `tabPurchase Receipt` pr
			ON pr.name = pri.parent
			AND pr.docstatus = 1
			AND IFNULL(pr.is_return, 0) = 0

		WHERE
			mr.docstatus = 1
			AND mr.material_request_type = 'Purchase'
			AND LEFT(i.item_group, 6) NOT IN ('020201','020202','020203')
			{company_condition}
			{branch_condition}
			{date_condition}

		GROUP BY
			mr.branch,
			mri.segment

		ORDER BY
			AVG(DATEDIFF(pr.posting_date, mr.transaction_date)) DESC
	"""

	return frappe.db.sql(query, values, as_dict=True)



def get_detail_data(filters):

	values = {}

	companies = normalize_multiselect(filters.get("company"))
	branches = normalize_multiselect(filters.get("branch"))

	company_condition = make_in_clause("mr.company", companies, values)
	branch_condition = make_in_clause("mr.branch", branches, values)
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")

	date_condition = ""

	if from_date and to_date:
		date_condition = " AND mr.transaction_date BETWEEN %(from_date)s AND %(to_date)s "
	elif from_date:
		date_condition = " AND mr.transaction_date >= %(from_date)s "
	elif to_date:
		date_condition = " AND mr.transaction_date <= %(to_date)s "

	values["from_date"] = from_date
	values["to_date"] = to_date

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

			DATEDIFF(po.transaction_date, mr.transaction_date) AS buyer_delay,
			DATEDIFF(pr.posting_date, po.transaction_date) AS supplier_delay,
			DATEDIFF(pr.posting_date, mr.transaction_date) AS total_procurement_days,
			DATEDIFF(pr.posting_date, poi.schedule_date) AS delivery_delay,

			CASE
				WHEN po.docstatus = 0 THEN 'PO Draft'
				WHEN po.docstatus = 1 AND IFNULL(SUM(pri.qty),0) = 0 THEN 'PO Submitted - No GRN'
				WHEN po.docstatus = 1 AND SUM(pri.qty) < poi.qty THEN 'Partial GRN'
				WHEN po.docstatus = 1 AND SUM(pri.qty) >= poi.qty THEN 'Full GRN'
				ELSE 'Unknown'
			END AS status

		FROM `tabMaterial Request` mr

		LEFT JOIN `tabMaterial Request Item` mri
			ON mri.parent = mr.name

		LEFT JOIN `tabItem` i
			ON i.name = mri.item_code

		LEFT JOIN `tabPurchase Order Item` poi
			ON poi.material_request = mr.name
			AND poi.material_request_item = mri.name

		LEFT JOIN `tabPurchase Order` po
			ON po.name = poi.parent

		LEFT JOIN `tabPurchase Receipt Item` pri
			ON pri.purchase_order_item = poi.name

		LEFT JOIN `tabPurchase Receipt` pr
			ON pr.name = pri.parent
			AND pr.docstatus = 1
			AND IFNULL(pr.is_return,0) = 0

		WHERE
			mr.docstatus = 1
			AND mr.material_request_type = 'Purchase'
			AND LEFT(i.item_group,6) NOT IN ('020201','020202','020203')
			{company_condition}
			{branch_condition}
			{date_condition}

		GROUP BY
			mr.name,
			mri.name,
			poi.name

		ORDER BY mr.transaction_date DESC
	"""

	return frappe.db.sql(query, values, as_dict=1)


def get_detail_columns():
    return [
        {"label": "Material Request", "fieldname": "material_request", "fieldtype": "Link", "options": "Material Request", "width": 190},
		{"label": "Item Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 340,"align": "left"},
        {"label": "Plant", "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 140},
        {"label": "Segment", "fieldname": "segment", "fieldtype": "Data", "width": 120},
        {"label": "Buyer Delay(MR->PO days)", "fieldname": "buyer_delay", "fieldtype": "Int", "width": 190},
        {"label": "Supplier Delay(PO->GRN days)", "fieldname": "supplier_delay", "fieldtype": "Int", "width": 210},
        {"label": "Total Procurement Days", "fieldname": "total_procurement_days", "fieldtype": "Int", "width": 190},
        {"label": "Delivery Delay", "fieldname": "delivery_delay", "fieldtype": "Int", "width": 140},
        {"label": "MR Date", "fieldname": "mr_date", "fieldtype": "Date", "width": 110},
        {"label": "PO Date", "fieldname": "po_date", "fieldtype": "Date", "width": 110},
        {"label": "Required Date", "fieldname": "required_date", "fieldtype": "Date", "width": 120},
        {"label": "Receipt Date", "fieldname": "receipt_date", "fieldtype": "Date", "width": 120},
        {"label": "PO / GRN Status", "fieldname": "status", "fieldtype": "Data", "width": 180},
		{"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 200},
		{"label": "Item Group", "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 150},
		{"label": "UOM", "fieldname": "uom", "fieldtype": "Data", "width": 80},
		{"label": "MR Qty", "fieldname": "mr_qty", "fieldtype": "Float", "width": 120},
		{"label": "Purchase Order", "fieldname": "purchase_order", "fieldtype": "Link", "options": "Purchase Order", "width": 170},
		{"label": "Supplier Code", "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 150},
		{"label": "Supplier Name", "fieldname": "supplier_name", "fieldtype": "Data", "width": 200},
		{"label": "PO Qty", "fieldname": "po_qty", "fieldtype": "Float", "width": 120},
		{"label": "Purchase Receipt", "fieldname": "purchase_receipt", "fieldtype": "Link", "options": "Purchase Receipt", "width": 170},
		{"label": "Received Qty", "fieldname": "received_qty", "fieldtype": "Float", "width": 120},
         
    ]