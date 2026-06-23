import calendar

import frappe
from frappe.utils import cint, flt, getdate, nowdate


@frappe.whitelist()
def get_page_data(filters=None):
	"""
	Single entry point for the Dispatch Order Balance page.

	Returns:
	{
		"as_on": "...",
		"item_tables":   { "quarter_columns":[...], "month_columns":[...], "items":[...] },
		"today_summary": [ ...Stock / Dispatch / Balance... ]
	}

	KEY CHANGE: Only the quarter that CONTAINS the as_on date is shown.
	Month columns are restricted to months up to (and including) as_on within that quarter.

	Rows (and the items that contain them) with a fully-supplied (pending_qty == 0)
	balance are dropped from the item-wise tables — only outstanding/pending
	balances are surfaced — UNLESS the "Show Zero Pending" filter is checked,
	in which case all rows (including fully-supplied ones) are shown.
	"""
	filters = frappe._dict(frappe.parse_json(filters) or {})
	as_on = filters.get("date") or nowdate()
	filters["date"] = as_on

	item_block = get_item_wise_balance(filters)
	item_codes = [i["item_code"] for i in item_block.get("items", [])]

	return {
		"as_on": as_on,
		"item_tables": item_block,
		"today_summary": get_item_wise_stock_dispatch(filters, item_codes=item_codes),
	}


# ──────────────────────────────────────────────────────────────────────────
# Quarter helpers
# ──────────────────────────────────────────────────────────────────────────

def get_current_quarter(as_on):
	"""
	Return the SINGLE quarter row from tabEthanol Supply Quarter whose
	date range CONTAINS as_on. Returns None if not found.
	"""
	rows = frappe.db.sql("""
		SELECT quarter, start_date, end_date
		FROM `tabEthanol Supply Quarter`
		WHERE start_date <= %(as_on)s AND end_date >= %(as_on)s
		ORDER BY start_date ASC
		LIMIT 1
	""", {"as_on": as_on}, as_dict=True)
	return rows[0] if rows else None


def get_month_range(start_date, end_date):
	start = getdate(start_date)
	end = getdate(end_date)
	months, y, m = [], start.year, start.month
	while (y, m) <= (end.year, end.month):
		months.append((y, m))
		m += 1
		if m > 12:
			m = 1
			y += 1
	return months


def quarter_fieldname(quarter_label):
	return "qsum_" + "".join(ch if ch.isalnum() else "_" for ch in str(quarter_label))


# ──────────────────────────────────────────────────────────────────────────
# PART 1 — Item-wise, OMC-wise balance tables
# ──────────────────────────────────────────────────────────────────────────

def get_item_wise_balance(filters):
	as_on = filters.get("date") or nowdate()
	as_on_date = getdate(as_on)

	# Whether to keep fully-supplied (pending_qty == 0) rows in the result.
	show_zero_pending = cint(filters.get("show_zero_pending"))

	# ── Determine quarter & month columns ──────────────────────────────────
	current_quarter = get_current_quarter(as_on)

	if current_quarter:
		# Clip months at as_on date
		effective_end = min(getdate(current_quarter.end_date), as_on_date)
		all_month_cols = get_month_range(current_quarter.start_date, effective_end)
		quarter_label = current_quarter.quarter
		quarter_columns = [{
			"fieldname": quarter_fieldname(quarter_label),
			"label": quarter_label,
		}]
		quarter_months = {
			quarter_label: [f"month_{y}_{m:02d}" for (y, m) in all_month_cols]
		}
	else:
		# As-on date falls outside any configured quarter — show months of
		# the calendar quarter containing the date as a fallback.
		m = as_on_date.month
		quarter_start_month = ((m - 1) // 3) * 3 + 1
		all_month_cols = [(as_on_date.year, mo) for mo in range(quarter_start_month, m + 1)]
		quarter_columns = []
		quarter_months = {}

	month_columns = [
		{"fieldname": f"month_{y}_{m:02d}", "label": f"{calendar.month_abbr[m]} {y}"}
		for (y, m) in all_month_cols
	]

	# ── Build SQL conditions ───────────────────────────────────────────────
	conditions = " AND di.po_date <= %(date)s"
	if filters.get("company"):
		conditions += " AND di.company = %(company)s"
	if filters.get("plant"):
		conditions += " AND di.branch = %(plant)s"
	if filters.get("customer"):
		conditions += " AND di.customer_name = %(customer)s"
	if filters.get("po_no"):
		conditions += " AND di.po_no LIKE %(po_no)s"
		filters["po_no"] = f"%{filters['po_no']}%"
	if filters.get("item_code"):
		conditions += " AND dii.item_code = %(item_code)s"

	# ── Main base query: order + cumulative supplied up to as_on ──────────
	# We also pull monthly dispatch in the same query using conditional SUM
	# to avoid a second round-trip for each dispatch order.
	month_sums_sql = ", ".join(
		f"SUM(CASE WHEN dn.is_return = 0 AND YEAR(dn.posting_date) = {y} "
		f"AND MONTH(dn.posting_date) = {m} THEN dni.qty ELSE 0 END) AS `month_{y}_{m:02d}`"
		for (y, m) in all_month_cols
	) if all_month_cols else "NULL AS _dummy"

	base_rows = frappe.db.sql(f"""
		SELECT
			di.customer_name,
			di.po_no,
			di.po_date,
			di.name                                                    AS dispatch_order,
			dii.item_code,
			it.item_name,
			dii.qty                                                    AS order_qty,
			dii.uom,
			IFNULL(SUM(CASE WHEN dn.is_return = 0 THEN dni.qty ELSE 0 END), 0) AS supplied_qty,
			GREATEST(
				dii.qty - IFNULL(SUM(CASE WHEN dn.is_return = 0 THEN dni.qty ELSE 0 END), 0),
				0
			) AS pending_qty,
			{month_sums_sql}
		FROM `tabDispatch Order` di
		INNER JOIN `tabDispatch Order Item` dii
			ON dii.parent = di.name
		LEFT JOIN `tabItem` it
			ON it.name = dii.item_code
		LEFT JOIN `tabDelivery Note Item` dni
			ON dni.custom_dispatch_order = di.name
			AND dni.item_code = dii.item_code
		LEFT JOIN `tabDelivery Note` dn
			ON dn.name = dni.parent
			AND dn.docstatus = 1
			AND dn.posting_date <= %(date)s
		WHERE di.docstatus = 1 {conditions}
		GROUP BY dii.name
		ORDER BY it.item_name ASC, di.customer_name ASC, di.po_date DESC
	""", {**filters, "date": as_on}, as_dict=True)

	if not base_rows:
		return {"quarter_columns": quarter_columns, "month_columns": month_columns, "items": []}

	# ── Assemble item blocks ───────────────────────────────────────────────
	items = {}
	raw_totals = {}  # item_code → {fieldname: float}

	for row in base_rows:
		item_code = row.item_code

		if item_code not in items:
			items[item_code] = {
				"item_code": item_code,
				"item_name": row.item_name,
				"uom": row.uom,
				"rows": [],
				"total": {
					"customer_name": "TOTAL",
					"po_no": "", "po_date": "",
					"order_qty": 0, "supplied_qty": 0, "pending_qty": 0,
				},
			}
			raw_totals[item_code] = {c["fieldname"]: 0.0 for c in month_columns}
			raw_totals[item_code].update({c["fieldname"]: 0.0 for c in quarter_columns})

		if row.po_date:
			po_date = getdate(row.po_date)
			po_ym = (po_date.year, po_date.month)
		else:
			po_ym = (0, 0)

		# Format month cells (blank if before PO date)
		for (y, m) in all_month_cols:
			fn = f"month_{y}_{m:02d}"
			if (y, m) < po_ym:
				row[fn] = ""
			else:
				qty = flt(row.get(fn) or 0)
				row[fn] = f"{qty:.3f}" if qty else "0.000"
				raw_totals[item_code][fn] += qty

		# Quarter-sum cell
		for q_label, fns in quarter_months.items():
			active_vals = [row[fn] for fn in fns if row.get(fn) not in ("", None)]
			qfn = quarter_fieldname(q_label)
			if active_vals:
				qty_sum = sum(float(v) for v in active_vals)
				row[qfn] = f"{qty_sum:.3f}" if qty_sum else "0.000"
			else:
				row[qfn] = ""

		items[item_code]["rows"].append(row)
		items[item_code]["total"]["order_qty"] += flt(row.order_qty)
		items[item_code]["total"]["supplied_qty"] += flt(row.supplied_qty)
		items[item_code]["total"]["pending_qty"] += flt(row.pending_qty)

	# Roll up totals (computed across ALL rows, before the pending-qty filter
	# below is applied — these unfiltered totals are discarded in favour of
	# the recalculated, filtered totals further down).
	for item_code, block in items.items():
		for c in month_columns:
			fn = c["fieldname"]
			v = raw_totals[item_code][fn]
			block["total"][fn] = f"{v:.3f}" if v else "0.000"

		for q_label, fns in quarter_months.items():
			qfn = quarter_fieldname(q_label)
			v = sum(raw_totals[item_code].get(fn, 0.0) for fn in fns)
			block["total"][qfn] = f"{v:.3f}" if v else "0.000"

	# ── Optionally drop fully-supplied (pending_qty == 0) rows ─────────────
	# By default, only rows with an outstanding balance are shown, and items
	# left with no pending rows at all are dropped entirely. When the
	# "Show Zero Pending" filter is checked, every row (including fully
	# supplied ones) is kept instead. Either way, the "Total" row for each
	# remaining item is recalculated from just the rows actually being shown,
	# so the displayed total always matches what's on screen.
	final_items = []
	for item_code, block in items.items():
		if show_zero_pending:
			visible_rows = block["rows"]
		else:
			visible_rows = [r for r in block["rows"] if flt(r.get("pending_qty")) > 0]

		if not visible_rows:
			continue

		block["rows"] = visible_rows

		total = {
			"customer_name": "TOTAL",
			"po_no": "", "po_date": "",
			"order_qty": 0.0, "supplied_qty": 0.0, "pending_qty": 0.0,
		}
		col_sums = {c["fieldname"]: 0.0 for c in month_columns}
		for c in quarter_columns:
			col_sums[c["fieldname"]] = 0.0

		for r in visible_rows:
			total["order_qty"] += flt(r.get("order_qty"))
			total["supplied_qty"] += flt(r.get("supplied_qty"))
			total["pending_qty"] += flt(r.get("pending_qty"))
			for fn in col_sums:
				v = r.get(fn)
				if v not in ("", None):
					col_sums[fn] += flt(v)

		for fn, v in col_sums.items():
			total[fn] = f"{v:.3f}" if v else "0.000"

		block["total"] = total
		final_items.append(block)

	return {
		"quarter_columns": quarter_columns,
		"month_columns": month_columns,
		"items": final_items,
	}


# ──────────────────────────────────────────────────────────────────────────
# PART 2 — Today's Stock & Dispatch summary
# ──────────────────────────────────────────────────────────────────────────

def get_item_wise_stock_dispatch(filters=None, item_codes=None):
	filters = filters or frappe._dict()
	as_on = filters.get("date") or nowdate()

	if item_codes is not None:
		if not item_codes:
			return []
		item_values = {"item_codes": item_codes}
		item_condition = "name IN %(item_codes)s AND disabled = 0"
	else:
		item_values = {}
		item_condition = "disabled = 0"
		if filters.get("item_code"):
			item_condition += " AND name = %(item_code)s"
			item_values["item_code"] = filters.item_code

	items = frappe.db.sql(f"""
		SELECT name AS item_code, item_name, stock_uom AS uom
		FROM `tabItem`
		WHERE {item_condition}
		ORDER BY item_name ASC
	""", item_values, as_dict=True)

	if not items:
		return []

	codes = [i.item_code for i in items]

	# Stock + Dispatch in one combined query per item using subqueries
	values = {"item_codes": codes, "as_on": as_on}

	warehouse_clause = ""
	if filters.get("warehouse"):
		warehouse_clause = " AND b.warehouse = %(warehouse)s"
		values["warehouse"] = filters.warehouse

	dispatch_warehouse_clause = ""
	if filters.get("warehouse"):
		dispatch_warehouse_clause = " AND dni.warehouse = %(warehouse)s"

	# Stock (Bin) is scoped to Company / Plant via Warehouse. `Warehouse.company`
	# is a standard field; `Warehouse.plant` is assumed to mirror Dispatch
	# Order's `plant` field — adjust the fieldname below if your Warehouse
	# doctype names it differently (or links to Plant some other way).
	stock_join = ""
	stock_company_clause = ""
	stock_plant_clause = ""
	if filters.get("company") or filters.get("plant"):
		stock_join = "INNER JOIN `tabWarehouse` wh ON wh.name = b.warehouse"
		if filters.get("company"):
			stock_company_clause = " AND wh.company = %(company)s"
			values["company"] = filters.company
		if filters.get("plant"):
			stock_plant_clause = " AND wh.custom_branch = %(plant)s"
			values["plant"] = filters.plant

	# Dispatch (Delivery Note) is scoped to Company / Plant via the linked
	# Dispatch Order (the same custom_dispatch_order link used in Part 1),
	# since Company/Plant live on Dispatch Order itself.
	dispatch_join = ""
	dispatch_company_clause = ""
	dispatch_plant_clause = ""
	if filters.get("company") or filters.get("plant"):
		dispatch_join = "LEFT JOIN `tabDispatch Order` do ON do.name = dni.custom_dispatch_order"
		if filters.get("company"):
			dispatch_company_clause = " AND do.company = %(company)s"
		if filters.get("plant"):
			dispatch_plant_clause = " AND do.branch = %(plant)s"

	combined = frappe.db.sql(f"""
		SELECT
			i.name AS item_code,
			IFNULL(b.stock_qty, 0) AS stock_qty,
			IFNULL(d.dispatch_qty, 0) AS dispatch_qty
		FROM (SELECT name FROM `tabItem` WHERE name IN %(item_codes)s) i
		LEFT JOIN (
			SELECT b.item_code, SUM(b.actual_qty) AS stock_qty
			FROM `tabBin` b
			{stock_join}
			WHERE b.item_code IN %(item_codes)s {warehouse_clause} {stock_company_clause} {stock_plant_clause}
			GROUP BY b.item_code
		) b ON b.item_code = i.name
		LEFT JOIN (
			SELECT dni.item_code,
				SUM(CASE WHEN dn.is_return = 1 THEN 0 ELSE dni.qty END) AS dispatch_qty
			FROM `tabDelivery Note Item` dni
			INNER JOIN `tabDelivery Note` dn ON dn.name = dni.parent
			{dispatch_join}
			WHERE dni.item_code IN %(item_codes)s
				AND dn.posting_date = %(as_on)s
				AND dn.docstatus = 1
				{dispatch_warehouse_clause}
				{dispatch_company_clause}
				{dispatch_plant_clause}
			GROUP BY dni.item_code
		) d ON d.item_code = i.name
	""", values, as_dict=True)

	combo_map = {r.item_code: r for r in combined}
	item_name_map = {i.item_code: i.item_name for i in items}

	data = []
	totals = frappe._dict(
		item_code="TOTAL", item_name="", uom="",
		stock_qty=0.0, dispatch_qty=0.0, balance_qty=0.0, as_on=as_on,
	)

	for item in items:
		c = combo_map.get(item.item_code, frappe._dict(stock_qty=0, dispatch_qty=0))
		stock_qty = flt(c.stock_qty)
		dispatch_qty = flt(c.dispatch_qty)
		balance_qty = stock_qty - dispatch_qty

		data.append({
			"item_code": item.item_code,
			"item_name": item.item_name,
			"uom": item.uom,
			"stock_qty": stock_qty,
			"dispatch_qty": dispatch_qty,
			"balance_qty": balance_qty,
			"as_on": as_on,
		})
		totals.stock_qty += stock_qty
		totals.dispatch_qty += dispatch_qty
		totals.balance_qty += balance_qty

	data.append(dict(totals))
	return data