# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)

    # Total Row
    total_row = {
        "item_name": "TOTAL",
        "received_qty": sum(d.get("received_qty", 0) or 0 for d in data),
        "purchase_value": sum(d.get("purchase_value", 0) or 0 for d in data),
        "value_31_60": sum(d.get("value_31_60", 0) or 0 for d in data),
        "value_61_90": sum(d.get("value_61_90", 0) or 0 for d in data),
        "value_90_plus": sum(d.get("value_90_plus", 0) or 0 for d in data),
    }

    # Insert total row at first
    data.insert(0, total_row)

    return columns, data


def get_columns():
    return [
        
        {
            "label": "Received Qty",
            "fieldname": "received_qty",
            "fieldtype": "Float",
            "width": 130,
        },
         
		{
        	"label": "Item Name",
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 220,
        },

   		{
            "label": "31-60 Days Value",
            "fieldname": "value_31_60",
            "fieldtype": "Currency",
            "width": 150,
        },
        {
            "label": "61-90 Days Value",
            "fieldname": "value_61_90",
            "fieldtype": "Currency",
            "width": 150,
        },
        {
            "label": "90+ Days Value",
            "fieldname": "value_90_plus",
            "fieldtype": "Currency",
            "width": 150,
        },
		{
            "label": "Purchase Value",
            "fieldname": "purchase_value",
            "fieldtype": "Currency",
            "width": 150,
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
            "label": "Purchase Receipt",
            "fieldname": "voucher_no",
            "fieldtype": "Link",
            "options": "Purchase Receipt",
            "width": 170,
        },
        {
            "label": "Item",
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
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
            "label": "Branch",
            "fieldname": "branch",
            "fieldtype": "Data",
            "width": 130,
        },
        {
            "label": "Segment",
            "fieldname": "segment",
            "fieldtype": "Data",
            "width": 130,
        },
        {
            "label": "Age (Days)",
            "fieldname": "age_days",
            "fieldtype": "Int",
            "width": 120,
        }
    ]


def get_data(filters):
	conditions = ""
	values = {}

	# Company Filter

	if filters.get("company"):
		conditions += " AND sle.company = %(company)s"
		values["company"] = filters.get("company")

	# Branch MultiSelect Filter

	if filters.get("branch"):
		branches = tuple(filters.get("branch"))

		conditions += " AND w.custom_branch IN %(branches)s"
		values["branches"] = branches
		
		

	# Item Group Filter

	if filters.get("item_group"):
		conditions += " AND i.item_group = %(item_group)s"
		values["item_group"] = filters.get("item_group")


	# Months Range Filter

	if filters.get("months_range"):

		if filters.get("months_range") == "1-3":
			conditions += """
				AND DATEDIFF(CURDATE(), sle.posting_date)
				BETWEEN 30 AND 90
			"""

		elif filters.get("months_range") == "3-6":
			conditions += """
				AND DATEDIFF(CURDATE(), sle.posting_date)
				BETWEEN 91 AND 180
			"""

		elif filters.get("months_range") == "6-9":
			conditions += """
				AND DATEDIFF(CURDATE(), sle.posting_date)
				BETWEEN 181 AND 270
			"""

		elif filters.get("months_range") == "9-12":
			conditions += """
				AND DATEDIFF(CURDATE(), sle.posting_date)
				BETWEEN 271 AND 365
			"""

		elif filters.get("months_range") == "12 Above":
			conditions += """
				AND DATEDIFF(CURDATE(), sle.posting_date) > 365
			"""

	return frappe.db.sql(
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

			DATEDIFF(CURDATE(), sle.posting_date) AS age_days,

			ROUND(
				CASE
					WHEN DATEDIFF(CURDATE(), sle.posting_date) <= 30
					THEN (sle.actual_qty * sle.valuation_rate)
					ELSE 0
				END,
			2) AS value_0_30,

			ROUND(
				CASE
					WHEN DATEDIFF(CURDATE(), sle.posting_date) BETWEEN 31 AND 60
					THEN (sle.actual_qty * sle.valuation_rate)
					ELSE 0
				END,
			2) AS value_31_60,

			ROUND(
				CASE
					WHEN DATEDIFF(CURDATE(), sle.posting_date) BETWEEN 61 AND 90
					THEN (sle.actual_qty * sle.valuation_rate)
					ELSE 0
				END,
			2) AS value_61_90,

			ROUND(
				CASE
					WHEN DATEDIFF(CURDATE(), sle.posting_date) > 90
					THEN (sle.actual_qty * sle.valuation_rate)
					ELSE 0
				END,
			2) AS value_90_plus

		FROM
			`tabStock Ledger Entry` sle

		LEFT JOIN
			`tabItem` i
			ON sle.item_code = i.name

		LEFT JOIN
			`tabWarehouse` w
			ON sle.warehouse = w.name

		LEFT JOIN
			`tabPurchase Receipt Item` pri
			ON pri.parent = sle.voucher_no
			AND pri.item_code = sle.item_code
			AND pri.warehouse = sle.warehouse

		WHERE
			sle.voucher_type = 'Purchase Receipt'
			AND sle.actual_qty > 0
			AND sle.docstatus = 1

			-- Only Age > 30 Days
			AND DATEDIFF(CURDATE(), sle.posting_date) > 30

			-- Only Purchase Price >= 1 Lakh
			AND pri.rate >= 100000

			{conditions}

			AND NOT EXISTS (
				SELECT 1
				FROM `tabStock Ledger Entry` sle2
				WHERE sle2.item_code = sle.item_code
				AND sle2.warehouse = sle.warehouse
				AND sle2.actual_qty < 0
			)
		""",
		values,
		as_dict=True,
	)