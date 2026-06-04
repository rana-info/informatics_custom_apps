import frappe


def execute(filters=None):
	filters = filters or {}

	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns():
	return [
		{"label": "Item", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 350, "align": "left"},

		{"label": "Last PO", "fieldname": "last_po", "fieldtype": "Link", "options": "Purchase Order", "width": 200},
		{"label": "Last PO Date", "fieldname": "last_po_date", "fieldtype": "Date", "width": 120},
		{"label": "Last Rate", "fieldname": "last_rate", "fieldtype": "Currency", "width": 120},
		{"label": "Price Variation %", "fieldname": "price_variation_percent", "fieldtype": "Percent", "width": 150,"precision": 2},

		{"label": "Previous PO", "fieldname": "prev_po", "fieldtype": "Link", "options": "Purchase Order", "width": 200},
		{"label": "Previous PO Date", "fieldname": "prev_po_date", "fieldtype": "Date", "width": 140},
		{"label": "Previous Rate", "fieldname": "prev_rate", "fieldtype": "Currency", "width": 120},

		{"label": "2nd Previous PO", "fieldname": "prev2_po", "fieldtype": "Link", "options": "Purchase Order", "width": 200},
		{"label": "2nd Previous Date", "fieldname": "prev2_po_date", "fieldtype": "Date", "width": 150},
		{"label": "2nd Previous Rate", "fieldname": "prev2_rate", "fieldtype": "Currency", "width": 200},

		{"label": "Price Trend", "fieldname": "price_trend", "fieldtype": "Data", "width": 180},
		{"label": "Supplier Name", "fieldname": "supplier_name", "fieldtype": "Data", "width": 180},
		{"label": "Plant", "fieldname": "plant", "fieldtype": "Data", "width": 120},
		{"label": "Segment", "fieldname": "segment", "fieldtype": "Data", "width": 120},

		{"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 180},

		{"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},

	
		{"label": "Supplier", "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 150},

	]


def get_data(filters):

	conditions = []
	values = {}

	if filters.get("company"):
		companies = filters.get("company")
		if isinstance(companies, str):
			companies = [c.strip() for c in companies.split(",") if c.strip()]
		conditions.append("po.company IN %(company)s")
		values["company"] = tuple(companies)

	if filters.get("branch"):
		plants = filters.get("branch")
		if isinstance(plants, str):
			plants = [p.strip() for p in plants.split(",") if p.strip()]
		conditions.append("poi.branch IN %(plant)s")
		values["plant"] = tuple(plants)

	if filters.get("from_date"):
		conditions.append("po.transaction_date >= %(from_date)s")
		values["from_date"] = filters.get("from_date")

	if filters.get("to_date"):
		conditions.append("po.transaction_date <= %(to_date)s")
		values["to_date"] = filters.get("to_date")

	price_filter = filters.get("price_variation")

	where_clause = ""
	if conditions:
		where_clause = " AND " + " AND ".join(conditions)

	query = f"""
		SELECT
			t.item_code,
			i.item_name,

			MAX(CASE WHEN t.rn = 1 THEN t.company END) AS company,
			MAX(CASE WHEN t.rn = 1 THEN w.custom_branch END) AS plant,
			MAX(CASE WHEN t.rn = 1 THEN w.custom_segment END) AS segment,

			MAX(CASE WHEN t.rn = 1 THEN t.supplier END) AS supplier,
			MAX(CASE WHEN t.rn = 1 THEN t.supplier_name END) AS supplier_name,

			MAX(CASE WHEN t.rn = 1 THEN t.po_no END) AS last_po,
			MAX(CASE WHEN t.rn = 1 THEN t.transaction_date END) AS last_po_date,
			MAX(CASE WHEN t.rn = 1 THEN t.rate END) AS last_rate,

			MAX(CASE WHEN t.rn = 2 THEN t.po_no END) AS prev_po,
			MAX(CASE WHEN t.rn = 2 THEN t.transaction_date END) AS prev_po_date,
			MAX(CASE WHEN t.rn = 2 THEN t.rate END) AS prev_rate,

			MAX(CASE WHEN t.rn = 3 THEN t.po_no END) AS prev2_po,
			MAX(CASE WHEN t.rn = 3 THEN t.transaction_date END) AS prev2_po_date,
			MAX(CASE WHEN t.rn = 3 THEN t.rate END) AS prev2_rate,

			CASE
				WHEN MAX(CASE WHEN t.rn = 1 THEN t.rate END)
					 > MAX(CASE WHEN t.rn = 2 THEN t.rate END)
				THEN 'Price Increased'

				WHEN MAX(CASE WHEN t.rn = 1 THEN t.rate END)
					 < MAX(CASE WHEN t.rn = 2 THEN t.rate END)
				THEN 'Price Reduced'

				WHEN MAX(CASE WHEN t.rn = 1 THEN t.rate END)
					 = MAX(CASE WHEN t.rn = 2 THEN t.rate END)
				THEN 'No Price Change'

				ELSE 'Insufficient Data'
			END AS price_trend,

			CASE
				WHEN MAX(CASE WHEN t.rn = 2 THEN t.rate END) IS NULL THEN 0

				WHEN MAX(CASE WHEN t.rn = 1 THEN t.rate END)
					 > MAX(CASE WHEN t.rn = 2 THEN t.rate END)
				THEN
					(
						(MAX(CASE WHEN t.rn = 1 THEN t.rate END)
						- MAX(CASE WHEN t.rn = 2 THEN t.rate END))
						/ NULLIF(MAX(CASE WHEN t.rn = 2 THEN t.rate END), 0)
					) * 100

				ELSE 0
			END AS price_variation_percent

		FROM (
			SELECT
				poi.item_code,
				poi.warehouse,
				po.company,
				po.supplier,
				po.supplier_name,
				po.name AS po_no,
				po.transaction_date,
				poi.rate,
				po.creation,

				ROW_NUMBER() OVER (
					PARTITION BY poi.item_code
					ORDER BY po.transaction_date DESC, po.creation DESC
				) AS rn

			FROM `tabPurchase Order` po
			INNER JOIN `tabPurchase Order Item` poi
				ON poi.parent = po.name

			WHERE
				po.docstatus = 1
				{where_clause}
		) t

		INNER JOIN `tabItem` i ON i.name = t.item_code AND i.is_stock_item=1
		LEFT JOIN `tabWarehouse` w ON w.name = t.warehouse

		WHERE t.rn <= 3

		GROUP BY t.item_code, i.item_name
	"""

	data = frappe.db.sql(query, values, as_dict=True)

	if price_filter:
		def match(row):
			p = row.get("price_variation_percent") or 0

			if price_filter == "> 5%":
				return p > 5
			elif price_filter == "> 10%":
				return p > 10
			elif price_filter == "> 20%":
				return p > 20
			elif price_filter == "> 40%":
				return p > 40

			return True

		data = list(filter(match, data))

	return data