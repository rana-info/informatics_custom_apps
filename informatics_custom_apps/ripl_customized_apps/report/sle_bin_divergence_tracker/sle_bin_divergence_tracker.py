# Copyright (c) 2026
# For license information, please see license.txt

import frappe
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}

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
			"width": 400,
			"align":"left"
		},
		{
			"label": "Warehouse",
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 300,
		},
        {
			"label": "Bin Qty",
			"fieldname": "bin_qty",
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"label": "SLE Qty",
			"fieldname": "sle_qty",
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"label": "Qty Diff",
			"fieldname": "qty_diff",
			"fieldtype": "Float",
			"width": 120,
		},
  		{
			"label": "Bin Value",
			"fieldname": "bin_value_lakh",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": "SLE Value",
			"fieldname": "sle_value_lakh",
			"fieldtype": "Currency",
			"width": 110,
		},
		{
			"label": "Value Diff (₹L)",
			"fieldname": "value_diff_lakh",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": "Discrepancy Date",
			"fieldname": "discrepancy_date",
			"fieldtype": "Date",
			"width": 180,
		},
		{
			"label": "Voucher Type",
			"fieldname": "voucher_type",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": "Voucher",
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 220,
		},
	]


def get_data(filters):

	conditions = [
		"sle.is_cancelled=0",
		"wh.disabled=0"
	]

	if filters.get("company"):
		conditions.append(
			"wh.company=%(company)s"
		)

	if filters.get("plant"):
		conditions.append(
			"wh.custom_branch=%(plant)s"
		)

	where_clause = " AND ".join(conditions)

	rows = frappe.db.sql(
		f"""
		SELECT
			sle.item_code,
			i.item_name,
			i.item_group,

			sle.warehouse,
			wh.custom_branch AS plant,
			wh.company,

			SUM(sle.actual_qty) AS sle_qty,

			SUM(
				sle.stock_value_difference
			)/100000 AS sle_value_lakh,

			MAX(
				COALESCE(bin.actual_qty,0)
			) AS bin_qty,

			MAX(
				COALESCE(bin.stock_value,0)
			)/100000 AS bin_value_lakh,

			MAX(
				sle.posting_date
			) AS last_posting_date,

			COUNT(*) AS sle_entry_count,

			IF(
				MAX(bin.name) IS NULL,
				0,
				1
			) AS has_bin

		FROM `tabStock Ledger Entry` sle

		INNER JOIN `tabWarehouse` wh
			ON wh.name=sle.warehouse

		INNER JOIN `tabItem` i
			ON i.name=sle.item_code

		LEFT JOIN `tabBin` bin
			ON
				bin.item_code=sle.item_code
				AND bin.warehouse=sle.warehouse

		WHERE {where_clause}

		GROUP BY
			sle.item_code,
			sle.warehouse

		ORDER BY
			ABS(
				SUM(sle.stock_value_difference)
				-
				MAX(
					COALESCE(bin.stock_value,0)
				)
			)
			DESC
		""",
		filters,
		as_dict=True,
	)

	data = []

	for row in rows:

		row.qty_diff = round(
			flt(row.sle_qty)
			-
			flt(row.bin_qty),
			4
		)

		row.value_diff_lakh = round(
			flt(row.sle_value_lakh)
			-
			flt(row.bin_value_lakh),
			2
		)

		if (
			abs(row.qty_diff) < 0.01
			and
			abs(row.value_diff_lakh) < 0.01
		):
			continue

		trace = find_first_break(
			row.warehouse,
			row.item_code
		)

		row.discrepancy_date = (
			trace.get("date")
			if trace
			else None
		)

		row.voucher_type = (
			trace.get("voucher_type")
			if trace
			else None
		)

		row.voucher_no = (
			trace.get("voucher_no")
			if trace
			else None
		)

		data.append(row)

	return data


def find_first_break(warehouse, item_code):

    rows = frappe.db.sql(
        """
        SELECT
            posting_date,
            posting_time,
            creation,
            voucher_type,
            voucher_no,
            actual_qty,
            qty_after_transaction,
            stock_value_difference,
            stock_value

        FROM `tabStock Ledger Entry`

        WHERE
            warehouse = %s
            AND item_code = %s
            AND is_cancelled = 0

        ORDER BY
            posting_date,
            posting_time,
            creation
        """,
        (warehouse, item_code),
        as_dict=True,
    )

    if not rows:
        return None

    running_qty   = 0.0
    running_value = 0.0

    for r in rows:

        if r.voucher_type == "Stock Reconciliation":
            qty_diff   = flt(r.qty_after_transaction) - running_qty
            value_diff = flt(r.stock_value) - running_value
        else:
            qty_diff   = flt(r.actual_qty)
            value_diff = flt(r.stock_value_difference)

        running_qty   += qty_diff
        running_value += value_diff

        qty_mismatch   = abs(running_qty   - flt(r.qty_after_transaction)) > 0.01
        value_mismatch = abs(running_value - flt(r.stock_value))           > 0.5  # 50 paise tolerance

        if qty_mismatch or value_mismatch:
            return {
                "date":         r.posting_date,
                "voucher_type": r.voucher_type,
                "voucher_no":   r.voucher_no,
            }

    last = rows[-1]
    return {
        "date":         last.posting_date,
        "voucher_type": last.voucher_type,
        "voucher_no":   last.voucher_no,
    }