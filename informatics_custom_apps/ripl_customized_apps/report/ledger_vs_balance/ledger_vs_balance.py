# Copyright (c) 2026, Rana Informatics and contributors
# License: MIT / proprietary — adjust as per your app's license header

"""
Ledger vs Balance
------------------
For every (Item, Warehouse) this report replays Stock Ledger Entries in the
exact order Frappe's stock ledger writer applies them (posting_datetime,
then creation) and independently recomputes the running qty/value using
actual_qty / stock_value_difference.

The first row where the recomputed running balance no longer matches the
*stored* qty_after_transaction / stock_value is flagged as the break point.
That row's item_code + warehouse + posting_date + posting_time is exactly
what Repost Item Valuation needs, so this report gives you a one-click
"Create Repost" action from the break row.

By default only the first break per item/warehouse is shown (that's the
useful signal — everything after it is noise until you repost). Turn on
"Show All Divergent Rows" to see every row that fails to reconcile after
the first break too (useful when auditing how bad the drift actually is).
"""

import frappe
from frappe import _
from frappe.utils import cint, flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	columns = get_columns()
	data = get_data(filters)

	return columns, data, None, None, None, len(data)


def validate_filters(filters):
	if not filters.get("company"):
		frappe.throw(_("Company is mandatory"))
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("From Date and To Date are mandatory"))
	if filters.get("from_date") > filters.get("to_date"):
		frappe.throw(_("From Date cannot be after To Date"))


def get_columns():
	return [
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 200,"align":"left"},
		{
			"label": _("Warehouse"),
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 180,
		},
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 120},
		{"label": _("Posting Time"), "fieldname": "posting_time", "fieldtype": "Data", "width": 100},
		{"label": _("Voucher Type"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 130},
		{
			"label": _("Voucher #"),
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 140,
		},
		{
			"label": _("Recorded Qty"),
			"fieldname": "recorded_qty",
			"fieldtype": "Float",
			"width": 110,
			"precision": 3,
		},
		{
			"label": _("Calculated Qty"),
			"fieldname": "calculated_qty",
			"fieldtype": "Float",
			"width": 110,
			"precision": 3,
		},
		{"label": _("Qty Diff"), "fieldname": "qty_diff", "fieldtype": "Float", "width": 100, "precision": 3},
		{
			"label": _("Recorded Value"),
			"fieldname": "recorded_value",
			"fieldtype": "Currency",
			"width": 120,
			"options": "Company:company:default_currency",
		},
		{
			"label": _("Calculated Value"),
			"fieldname": "calculated_value",
			"fieldtype": "Currency",
			"width": 120,
			"options": "Company:company:default_currency",
		},
		{
			"label": _("Value Diff"),
			"fieldname": "value_diff",
			"fieldtype": "Currency",
			"width": 110,
			"options": "Company:company:default_currency",
		},
		{"label": _("Break Type"), "fieldname": "break_type", "fieldtype": "Data", "width": 110},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 100},
	]


def get_data(filters):
	precision = cint(frappe.db.get_single_value("System Settings", "float_precision")) or 3
	qty_tolerance = flt(filters.get("qty_tolerance") or 0.001)
	value_tolerance = flt(filters.get("value_tolerance") or 1)
	show_all = cint(filters.get("show_all_divergent_rows"))

	entries = get_sl_entries(filters)

	# state per (item_code, warehouse): running qty/value + whether a break
	# has already been recorded for this key
	state = {}
	data = []

	for row in entries:
		key = (row.item_code, row.warehouse)
		s = state.get(key)
		if s is None:
			s = state[key] = {"qty": 0.0, "value": 0.0, "broken": False}

		if s["broken"] and not show_all:
			continue

		calculated_qty = flt(s["qty"] + row.actual_qty, precision)
		calculated_value = flt(s["value"] + row.stock_value_difference, precision)

		qty_diff = flt(calculated_qty - flt(row.qty_after_transaction), precision)
		value_diff = flt(calculated_value - flt(row.stock_value), precision)

		qty_mismatch = abs(qty_diff) > qty_tolerance
		value_mismatch = abs(value_diff) > value_tolerance

		if qty_mismatch or value_mismatch:
			break_type = []
			if qty_mismatch:
				break_type.append(_("Qty"))
			if value_mismatch:
				break_type.append(_("Value"))

			data.append(
				{
					"item_code": row.item_code,
					"item_name": row.item_name,
					"warehouse": row.warehouse,
					"posting_date": row.posting_date,
					"posting_time": row.posting_time,
					"voucher_type": row.voucher_type,
					"voucher_no": row.voucher_no,
					"recorded_qty": row.qty_after_transaction,
					"calculated_qty": calculated_qty,
					"qty_diff": qty_diff,
					"recorded_value": row.stock_value,
					"calculated_value": calculated_value,
					"value_diff": value_diff,
					"break_type": " + ".join(break_type),
					"company": row.company,
				}
			)

			s["broken"] = True
			# Re-anchor to the stored (recorded) values so that if the user
			# opted to show all divergent rows, we're reporting fresh drift
			# from this point rather than a cascading restatement of the
			# same original error.
			s["qty"] = flt(row.qty_after_transaction)
			s["value"] = flt(row.stock_value)
		else:
			s["qty"] = calculated_qty
			s["value"] = calculated_value

	# Sort so the earliest break per item/warehouse is easy to scan, item
	# grouped together.
	data.sort(key=lambda d: (d["item_code"], d["warehouse"], d["posting_date"], d["posting_time"]))

	return data


def get_sl_entries(filters):
	sle = frappe.qb.DocType("Stock Ledger Entry")
	item = frappe.qb.DocType("Item")

	query = (
		frappe.qb.from_(sle)
		.inner_join(item)
		.on(sle.item_code == item.name)
		.select(
			sle.item_code,
			item.item_name,
			sle.warehouse,
			sle.posting_date,
			sle.posting_time,
			sle.posting_datetime,
			sle.actual_qty,
			sle.qty_after_transaction,
			sle.stock_value_difference,
			sle.stock_value,
			sle.voucher_type,
			sle.voucher_no,
			sle.company,
			sle.creation,
		)
		.where((sle.docstatus < 2) & (sle.is_cancelled == 0) & (sle.company == filters.company))
		.orderby(sle.item_code)
		.orderby(sle.warehouse)
		.orderby(sle.posting_datetime)
		.orderby(sle.creation)
	)

	# We replay from the beginning of time for each item/warehouse so the
	# running total is accurate, then only report breaks that fall within
	# the requested date window.
	query = query.where(sle.posting_date <= filters.to_date)

	if filters.get("item_code"):
		items = filters.item_code
		items = items if isinstance(items, list) else [items]
		query = query.where(sle.item_code.isin(items))

	if filters.get("warehouse"):
		warehouses = filters.warehouse
		warehouses = warehouses if isinstance(warehouses, list) else [warehouses]
		query = query.where(sle.warehouse.isin(warehouses))

	if filters.get("item_group"):
		from frappe.utils.nestedset import get_descendants_of

		children = get_descendants_of("Item Group", filters.item_group, ignore_permissions=True)
		query = query.where(item.item_group.isin([*children, filters.item_group]))

	return query.run(as_dict=True)


@frappe.whitelist()
def create_repost_entry(item_code, warehouse, posting_date, posting_time, company):
	"""Create (as draft) a Repost Item Valuation doc pre-filled from a
	break row so the user can review and submit it from the UI."""

	frappe.has_permission("Repost Item Valuation", "create", throw=True)

	doc = frappe.new_doc("Repost Item Valuation")
	doc.based_on = "Item and Warehouse"
	doc.item_code = item_code
	doc.warehouse = warehouse
	doc.posting_date = posting_date
	doc.posting_time = posting_time
	doc.company = company
	doc.insert()

	return doc.name