# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	filters = filters or {}

	columns = get_columns(filters)
	data = get_data(filters)

	buckets = [
		int(x.strip())
		for x in filters.get("age_buckets", "30,90,180,365").split(",")
		if x.strip()
	]

	total_row = {
    "item_code": "TOTAL",
    "received_qty": sum(d.get("received_qty", 0) or 0 for d in data),
    "purchase_value": sum(d.get("purchase_value", 0) or 0 for d in data),
    "purchase_price": sum(d.get("purchase_price", 0) or 0 for d in data),
    "is_total_row": 1
}
	start = 0

	for bucket in buckets:
		fieldname = f"value_{start}_{bucket}"
		total_row[fieldname] = sum(
			d.get(fieldname, 0) or 0 for d in data
		)
		start = bucket + 1

	total_row[f"value_above_{buckets[-1]}"] = sum(
		d.get(f"value_above_{buckets[-1]}", 0) or 0
		for d in data
	)

	data.insert(0, total_row)

	return columns, data

def get_columns(filters=None):

    columns = [
        {
            "label": "Item",
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 580,
        },
    ]

    buckets = [
        int(x.strip())
        for x in filters.get("age_buckets", "30,90,180,365").split(",")
        if x.strip()
    ]

    start = 0

    for bucket in buckets:
        columns.append({
            "label": f"{start}-{bucket} Days",
            "fieldname": f"value_{start}_{bucket}",
            "fieldtype": "Currency",
            "width": 150,
        })
        start = bucket + 1

    columns.extend([
        {
            "label": f">{buckets[-1]} Days",
            "fieldname": f"value_above_{buckets[-1]}",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": "Purchase Value",
            "fieldname": "purchase_value",
            "fieldtype": "Currency",
            "width": 150,
        },
        
        {
            "label": "Purchase Price",
            "fieldname": "purchase_price",
            "fieldtype": "Currency",
            "width": 150,
        },
        
         {
            "label": "Age (Days)",
            "fieldname": "age_days",
            "fieldtype": "Int",
            "width": 120,
        },
        
         {
            "label": "Received Qty",
            "fieldname": "received_qty",
            "fieldtype": "Float",
            "width": 130,
        },
        {
            "label": "Plant",
            "fieldname": "branch",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "label": "Purchase Receipt",
            "fieldname": "voucher_no",
            "fieldtype": "Link",
            "options": "Purchase Receipt",
            "width": 170,
        },
        {
            "label": "Date",
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "label": "Company",
            "fieldname": "company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 150,
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
            "fieldname": "stock_uom",
            "fieldtype": "Data",
            "width": 90,
        },
        {
            "label": "Warehouse",
            "fieldname": "warehouse",
            "fieldtype": "Link",
            "options": "Warehouse",
            "width": 180,
        },
        {
            "label": "Segment",
            "fieldname": "segment",
            "fieldtype": "Data",
            "width": 130,
        }
    ])

    return columns
def get_data(filters):
	conditions = ""
	values = {}

	if filters.get("company"):
		conditions += " AND sle.company IN %(company)s"
		values["company"] = filters.get("company")

	if filters.get("branch"):
		branches = tuple(filters.get("branch"))
		conditions += " AND w.custom_branch IN %(branches)s"
		values["branches"] = branches

	if filters.get("item_group"):
		conditions += " AND i.item_group IN %(item_group)s"
		values["item_group"] = filters.get("item_group")

	if filters.get("value_filter"):

		if filters.get("value_filter") == "> 50000":
			conditions += " AND pri.rate > 50000"

		elif filters.get("value_filter") == "> 100000":
			conditions += " AND pri.rate > 100000"


	data = frappe.db.sql(
		f"""
		SELECT
			sle.posting_date AS posting_date,
			sle.company AS company,
			sle.voucher_no AS voucher_no,
			sle.item_code AS item_code,
			i.item_name AS item_name,
			i.item_group AS item_group,
			i.stock_uom AS stock_uom,
			sle.warehouse AS warehouse,
			w.custom_branch AS branch,
			w.custom_segment AS segment,

			ROUND(sle.actual_qty, 2) AS received_qty,
			ROUND(pri.rate, 2) AS purchase_price,
			ROUND(sle.valuation_rate, 2) AS average_price,

			ROUND((sle.actual_qty * pri.rate), 2) AS purchase_value,
			ROUND((sle.actual_qty * sle.valuation_rate), 2) AS stock_value,

			DATEDIFF(CURDATE(), sle.posting_date) AS age_days

		FROM `tabStock Ledger Entry` sle

		LEFT JOIN `tabItem` i
			ON sle.item_code = i.name

		LEFT JOIN `tabWarehouse` w
			ON sle.warehouse = w.name

		LEFT JOIN `tabPurchase Receipt Item` pri
			ON pri.parent = sle.voucher_no
			AND pri.item_code = sle.item_code
			AND pri.warehouse = sle.warehouse

		WHERE
			sle.voucher_type = 'Purchase Receipt'
			AND sle.actual_qty > 0
			AND sle.docstatus = 1
			AND DATEDIFF(CURDATE(), sle.posting_date) > 30

			{conditions}

			AND NOT EXISTS (
				SELECT 1
				FROM `tabStock Ledger Entry` sle2
				WHERE sle2.item_code = sle.item_code
				AND sle2.warehouse = sle.warehouse
				AND sle2.actual_qty < 0
			)

		ORDER BY purchase_value DESC
		""",
		values,
		as_dict=True,
	)

	buckets = [
		int(x.strip())
		for x in filters.get("age_buckets", "30,90,180,365").split(",")
		if x.strip()
	]

	for row in data:

		age = row.get("age_days", 0) or 0
		value = row.get("stock_value", 0) or 0

		start = 0

		for bucket in buckets:

			fieldname = f"value_{start}_{bucket}"

			row[fieldname] = 0

			if start <= age <= bucket:
				row[fieldname] = value

			start = bucket + 1

		row[f"value_above_{buckets[-1]}"] = (
			value if age > buckets[-1] else 0
		)

	return data