import frappe


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(frappe._("From Date and To Date are mandatory"))
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": "Company", "fieldname": "company", "fieldtype": "Data", "options": "Company", "width": 140},
		{"label": "Item", "fieldname": "item_code", "fieldtype": "Data", "options": "Item", "width": 150},
		{"label": "Item Description", "fieldname": "item_description", "fieldtype": "Data", "width": 250},
		{"label": "Warehouse", "fieldname": "warehouse", "fieldtype": "Data", "options": "Warehouse", "width": 180},
		{"label": "Plant", "fieldname": "plant", "fieldtype": "Data", "options": "Branch", "width": 140},
		{"label": "Segment", "fieldname": "segment", "fieldtype": "Data", "width": 140},
		{"label": "Opening Qty", "fieldname": "opening_qty", "fieldtype": "Float", "width": 120},
		{"label": "In Qty", "fieldname": "in_qty", "fieldtype": "Float", "width": 120},
		{"label": "Out Qty", "fieldname": "out_qty", "fieldtype": "Float", "width": 120},
		{"label": "Balance Qty", "fieldname": "balance_qty", "fieldtype": "Float", "width": 120},
		{"label": "Opening Value", "fieldname": "opening_value", "fieldtype": "Currency", "width": 140},
		{"label": "In Value", "fieldname": "in_value", "fieldtype": "Currency", "width": 140},
		{"label": "Out Value", "fieldname": "out_value", "fieldtype": "Currency", "width": 140},
		{"label": "Balance Value", "fieldname": "balance_value", "fieldtype": "Currency", "width": 140},
		{"label": "Valuation Rate", "fieldname": "valuation_rate", "fieldtype": "Currency", "width": 130},
	]


def get_data(filters):
	item_condition = get_item_condition(filters)
	if item_condition is None:
		return []

	query = f"""
		WITH filtered_sle AS (
			SELECT
				company,
				item_code,
				warehouse,
				posting_date,
				posting_datetime,
				creation,
				actual_qty,
				stock_value_difference,
				voucher_type,
				voucher_no,
				voucher_detail_no,
				name,
				ROW_NUMBER() OVER (
					PARTITION BY company, item_code, warehouse
					ORDER BY posting_datetime DESC, creation DESC, name DESC
				) AS rn
			FROM `tabStock Ledger Entry`
			WHERE is_cancelled = 0
			  AND posting_date <= %(to_date)s
			  {item_condition}
		),

		aggregated_totals AS (
			SELECT
				company,
				item_code,
				warehouse,

				SUM(
					CASE
						WHEN posting_date < %(from_date)s
						THEN actual_qty
						ELSE 0
					END
				) AS opening_qty,

				SUM(
					CASE
						WHEN posting_date BETWEEN %(from_date)s AND %(to_date)s
							 AND actual_qty > 0
						THEN actual_qty
						ELSE 0
					END
				) AS in_qty,

				SUM(
					CASE
						WHEN posting_date BETWEEN %(from_date)s AND %(to_date)s
							 AND actual_qty < 0
						THEN ABS(actual_qty)
						ELSE 0
					END
				) AS out_qty,

				SUM(actual_qty) AS balance_qty,

				SUM(
					CASE
						WHEN posting_date < %(from_date)s
						THEN stock_value_difference
						ELSE 0
					END
				) AS opening_value,

				SUM(
					CASE
						WHEN posting_date BETWEEN %(from_date)s AND %(to_date)s
							 AND stock_value_difference > 0
						THEN stock_value_difference
						ELSE 0
					END
				) AS in_value,

				SUM(
					CASE
						WHEN posting_date BETWEEN %(from_date)s AND %(to_date)s
							 AND stock_value_difference < 0
						THEN ABS(stock_value_difference)
						ELSE 0
					END
				) AS out_value,

				SUM(stock_value_difference) AS balance_value

			FROM filtered_sle
			GROUP BY company, item_code, warehouse
		),

		latest_row AS (
			SELECT *
			FROM filtered_sle
			WHERE rn = 1
		),

		latest_sle_metadata AS (
			SELECT
				sle.company,
				sle.item_code,
				sle.warehouse,

				CASE
					WHEN sle.voucher_type = 'Stock Entry'
						THEN NULLIF(sed.branch, '')
					WHEN sle.voucher_type = 'Purchase Receipt'
						THEN NULLIF(pri.branch, '')
					WHEN sle.voucher_type = 'Delivery Note'
						THEN NULLIF(dni.branch, '')
					WHEN sle.voucher_type = 'Sales Invoice'
						THEN NULLIF(sii.branch, '')
					WHEN sle.voucher_type = 'Purchase Invoice'
						THEN NULLIF(pii.branch, '')
					WHEN sle.voucher_type = 'POS Invoice'
						THEN NULLIF(posi.branch, '')
					WHEN sle.voucher_type = 'Subcontracting Receipt'
						THEN NULLIF(scri.branch, '')
					WHEN sle.voucher_type = 'Stock Reconciliation'
						THEN COALESCE(
							NULLIF(sri.branch, ''),
							NULLIF(sr.branch, '')
						)
					ELSE ''
				END AS plant,

				CASE
					WHEN sle.voucher_type = 'Stock Entry'
						THEN NULLIF(sed.segment, '')
					WHEN sle.voucher_type = 'Purchase Receipt'
						THEN NULLIF(pri.segment, '')
					WHEN sle.voucher_type = 'Delivery Note'
						THEN NULLIF(dni.segment, '')
					WHEN sle.voucher_type = 'Sales Invoice'
						THEN NULLIF(sii.segment, '')
					WHEN sle.voucher_type = 'Purchase Invoice'
						THEN NULLIF(pii.segment, '')
					WHEN sle.voucher_type = 'POS Invoice'
						THEN NULLIF(posi.segment, '')
					WHEN sle.voucher_type = 'Subcontracting Receipt'
						THEN NULLIF(scri.segment, '')
					WHEN sle.voucher_type = 'Stock Reconciliation'
						THEN COALESCE(
							NULLIF(sri.segment, ''),
							NULLIF(sr.segment, '')
						)
					ELSE ''
				END AS segment

			FROM latest_row sle

			LEFT JOIN `tabStock Entry Detail` sed
				ON sed.name = sle.voucher_detail_no
				AND sle.voucher_type = 'Stock Entry'

			LEFT JOIN `tabPurchase Receipt Item` pri
				ON pri.name = sle.voucher_detail_no
				AND sle.voucher_type = 'Purchase Receipt'

			LEFT JOIN `tabDelivery Note Item` dni
				ON dni.name = sle.voucher_detail_no
				AND sle.voucher_type = 'Delivery Note'

			LEFT JOIN `tabSales Invoice Item` sii
				ON sii.name = sle.voucher_detail_no
				AND sle.voucher_type = 'Sales Invoice'

			LEFT JOIN `tabPurchase Invoice Item` pii
				ON pii.name = sle.voucher_detail_no
				AND sle.voucher_type = 'Purchase Invoice'

			LEFT JOIN `tabPOS Invoice Item` posi
				ON posi.name = sle.voucher_detail_no
				AND sle.voucher_type = 'POS Invoice'

			LEFT JOIN `tabSubcontracting Receipt Item` scri
				ON scri.name = sle.voucher_detail_no
				AND sle.voucher_type = 'Subcontracting Receipt'

			LEFT JOIN `tabStock Reconciliation Item` sri
				ON sri.name = sle.voucher_detail_no
				AND sle.voucher_type = 'Stock Reconciliation'

			LEFT JOIN `tabStock Reconciliation` sr
				ON sr.name = sle.voucher_no
				AND sle.voucher_type = 'Stock Reconciliation'
		)

		SELECT
			t.company AS company,
			t.item_code AS item_code,
			IFNULL(item.description, '') AS item_description,
			t.warehouse AS warehouse,
			IFNULL(latest.plant, '') AS plant,
			IFNULL(latest.segment, '') AS segment,
			t.opening_qty AS opening_qty,
			t.in_qty AS in_qty,
			t.out_qty AS out_qty,
			t.balance_qty AS balance_qty,
			t.opening_value AS opening_value,
			t.in_value AS in_value,
			t.out_value AS out_value,
			t.balance_value AS balance_value,
			CASE
				WHEN t.balance_qty != 0
				THEN t.balance_value / t.balance_qty
				ELSE 0
			END AS valuation_rate

		FROM aggregated_totals t

		LEFT JOIN `tabItem` item
			ON item.name = t.item_code

		LEFT JOIN latest_sle_metadata latest
			ON latest.company = t.company
		   AND latest.item_code = t.item_code
		   AND latest.warehouse = t.warehouse

		WHERE NOT (
			t.opening_qty = 0
			AND t.in_qty = 0
			AND t.out_qty = 0
			AND t.balance_qty = 0
		)

		ORDER BY
			t.company,
			t.item_code,
			t.warehouse
	"""

	return frappe.db.sql(query, filters, as_dict=1)


def get_item_condition(filters):
	if filters.get("item"):
		return "AND item_code = %(item)s"

	if filters.get("item_group"):
		item_codes = frappe.db.sql_list(
			"SELECT name FROM `tabItem` WHERE item_group = %s", filters.get("item_group")
		)
		if not item_codes:
			return None
		filters["item_codes"] = tuple(item_codes) if len(item_codes) > 1 else (item_codes[0], item_codes[0])
		return "AND item_code IN %(item_codes)s"

	return ""