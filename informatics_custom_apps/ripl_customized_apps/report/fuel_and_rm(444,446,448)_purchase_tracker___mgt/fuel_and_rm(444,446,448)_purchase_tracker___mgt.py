import frappe


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
     	{"fieldname": "doctype", "fieldtype": "Data", "hidden": 1},
		{"fieldname": "docname", "fieldtype": "Data", "hidden": 1},
		{"label": "Item", "fieldname": "name", "fieldtype": "Data", "width": 300},

		{"label": "Supplier Name", "fieldname": "supplier_name", "fieldtype": "Data", "width": 190},
		{"label": "PO Date", "fieldname": "po_date", "fieldtype": "Date", "width": 120},
		{"label": "Ordered Qty", "fieldname": "ordered_qty", "fieldtype": "Float", "width": 120},
		{"label": "Received Qty", "fieldname": "received_qty", "fieldtype": "Float", "width": 120},
		{"label": "Pending Qty", "fieldname": "pending_qty", "fieldtype": "Float", "width": 120},

		{"label": "Ordered Value", "fieldname": "ordered_value", "fieldtype": "Currency", "width": 140},
		{"label": "Received Value", "fieldname": "received_value", "fieldtype": "Currency", "width": 140},
		{"label": "Pending Value", "fieldname": "pending_value", "fieldtype": "Currency", "width": 140},

		{"label": "Receipt Status", "fieldname": "receipt_status", "fieldtype": "Data", "width": 140},
		{"label": "Plant", "fieldname": "plant", "fieldtype": "Data", "width": 140},

		{"label": "Dispatch Material To", "fieldname": "custom_despatch_material_to", "fieldtype": "Data", "width": 180},
		{"label": "Incoterm", "fieldname": "incoterm", "fieldtype": "Data", "width": 140},

		{"label": "UOM", "fieldname": "uom", "fieldtype": "Data", "width": 80},
		{"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 140},
		{"label": "Supplier ID", "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 140},
	]


def convert_to_mt(uom, qty):
	qty = qty or 0
	if uom == "KGS":
		return qty / 100
	return qty


def get_data(filters):

	conditions = ""
	values = {}

	if filters.get("from_date") and filters.get("to_date"):
		conditions += " AND po.transaction_date BETWEEN %(from_date)s AND %(to_date)s"
		values["from_date"] = filters.get("from_date")
		values["to_date"] = filters.get("to_date")

	if filters.get("company"):
		companies = filters.get("company")
		if isinstance(companies, str):
			companies = [c.strip() for c in companies.split(",") if c.strip()]
		conditions += " AND po.company IN %(company)s"
		values["company"] = tuple(companies)

	if filters.get("plant"):
		plants = filters.get("plant")
		if isinstance(plants, str):
			plants = [p.strip() for p in plants.split(",") if p.strip()]
		conditions += " AND wh.custom_branch IN %(plant)s"
		values["plant"] = tuple(plants)

	data = frappe.db.sql(f"""
		SELECT
			po.name AS po_no,
			po.transaction_date AS po_date,
			po.company,
			po.supplier,
			po.supplier_name,
			po.custom_despatch_material_to,
			po.incoterm,

			poi.name AS po_item,
			poi.item_code,
			poi.item_name,
			poi.qty AS ordered_qty,
			poi.uom,
			poi.segment,

			IFNULL(pri.received_qty, 0) AS received_qty,
			(poi.qty - IFNULL(pri.received_qty, 0)) AS pending_qty,

			po.grand_total AS po_value,
			wh.custom_branch AS plant,

			(poi.qty / SUM(poi.qty) OVER (PARTITION BY po.name)) * po.grand_total AS ordered_value,
			(IFNULL(pri.received_qty,0) / SUM(poi.qty) OVER (PARTITION BY po.name)) * po.grand_total AS received_value,
			((poi.qty - IFNULL(pri.received_qty,0)) / SUM(poi.qty) OVER (PARTITION BY po.name)) * po.grand_total AS pending_value,

			CASE
				WHEN IFNULL(pri.received_qty,0)=0 THEN 'Not Received'
				WHEN IFNULL(pri.received_qty,0)<poi.qty THEN 'Partially Received'
				ELSE 'Fully Received'
			END AS receipt_status

		FROM `tabPurchase Order` po
		INNER JOIN `tabPurchase Order Item` poi ON poi.parent = po.name

		LEFT JOIN (
			SELECT purchase_order_item, SUM(qty) AS received_qty
			FROM `tabPurchase Receipt Item`
			WHERE docstatus = 1
			GROUP BY purchase_order_item
		) pri ON pri.purchase_order_item = poi.name

		LEFT JOIN `tabWarehouse` wh ON wh.name = poi.warehouse

		WHERE
			po.docstatus = 1
			AND po.status NOT IN ('Closed','Completed')
			AND (
				poi.item_code IN ('106448','106446','106444')
				OR poi.item_group IN (
					'020301-Fuel-Trd',
					'020302-Fuel-Trd Non Weightment',
					'020104-Bagasse-Trd',
					'020104-Bagasse-Trd (Non Weighment)',
					'010108-Bagasse-Mfg (Non Weighment)',
					'010102-Bagasse-Mfg'
				)
			)
			{conditions}
	""".format(conditions=conditions), values, as_dict=True)

	item_rows = []
	for r in data:
		item_rows.append({
			"po_no": r.po_no,
			"plant": r.plant or "No Plant",

			"po_date": r.po_date,
			"supplier": r.supplier,
			"supplier_name": r.supplier_name,
			"custom_despatch_material_to": r.custom_despatch_material_to,
			"incoterm": r.incoterm,
			"company": r.company,

			"item_code": r.item_code,
			"item_name": r.item_name,

			"uom": "Quintal",

			"ordered_qty": convert_to_mt(r.uom, r.ordered_qty),
			"received_qty": convert_to_mt(r.uom, r.received_qty),
			"pending_qty": convert_to_mt(r.uom, r.pending_qty),

			"ordered_value": r.ordered_value,
			"received_value": r.received_value,
			"pending_value": r.pending_value,

			"po_value": r.po_value,
			"receipt_status": r.receipt_status,
		})

	po_summary = {}

	for r in item_rows:
		key = (r["plant"], r["po_no"])

		po_summary.setdefault(key, {
			"oq": 0, "rq": 0, "pq": 0,
			"ov": 0, "rv": 0, "pv": 0,
			"po_value": 0,
			"po_date": None,
			"supplier": None,
			"supplier_name": None,
			"incoterm": None,
			"custom_despatch_material_to": None,
			"company": None,
		})

		s = po_summary[key]

		s["oq"] += r["ordered_qty"]
		s["rq"] += r["received_qty"]
		s["pq"] += r["pending_qty"]

		s["ov"] += r["ordered_value"]
		s["rv"] += r["received_value"]
		s["pv"] += r["pending_value"]

		s["po_value"] = r["po_value"]

		s["po_date"] = r["po_date"]
		s["supplier"] = r["supplier"]
		s["supplier_name"] = r["supplier_name"]
		s["incoterm"] = r["incoterm"]
		s["custom_despatch_material_to"] = r["custom_despatch_material_to"]
		s["company"] = r["company"]

	plant_summary = {}

	for (plant, po), v in po_summary.items():

		plant_summary.setdefault(plant, {
			"oq": 0, "rq": 0, "pq": 0,
			"ov": 0, "rv": 0, "pv": 0,
			"po_value": 0
		})

		p = plant_summary[plant]

		p["oq"] += v["oq"]
		p["rq"] += v["rq"]
		p["pq"] += v["pq"]

		p["ov"] += v["ov"]
		p["rv"] += v["rv"]
		p["pv"] += v["pv"]

		p["po_value"] += v["po_value"]

	tree = []
	plant_added = set()
	po_added = set()

	for r in item_rows:
		plant = r["plant"]
		po = r["po_no"]

		if plant not in plant_added:
			s = plant_summary[plant]
			tree.append({
				 "name": plant,
				"doctype": "Branch",
				"docname": plant,
				"parent": "",
				"indent": 1,
				"po_value": s["po_value"],
				"ordered_qty": s["oq"],
				"received_qty": s["rq"],
				"pending_qty": s["pq"],
				"ordered_value": s["ov"],
				"received_value": s["rv"],
				"pending_value": s["pv"],
			})
			plant_added.add(plant)

		if (plant, po) not in po_added:
			s = po_summary[(plant, po)]
			tree.append({
				"name": po,
				"doctype": "Purchase Order",
				"docname": po,
				"parent": plant,
				"indent": 2,

				"po_value": s["po_value"],
				"po_date": s["po_date"],
				"supplier_name": s["supplier_name"],
				"supplier": s["supplier"],

				"ordered_qty": s["oq"],
				"received_qty": s["rq"],
				"pending_qty": s["pq"],

				"ordered_value": s["ov"],
				"received_value": s["rv"],
				"pending_value": s["pv"],

				"custom_despatch_material_to": s["custom_despatch_material_to"],
				"incoterm": s["incoterm"],
				"company": s["company"],
			})
			po_added.add((plant, po))

		tree.append({
			"name": f"{r['item_code']} - {r['item_name']}",
			"doctype": "Item",
			"docname": r["item_code"],
			"parent": po,
			"indent": 3,

			"plant": plant,

			"uom": "Quintal",
			"ordered_qty": r["ordered_qty"],
			"received_qty": r["received_qty"],
			"pending_qty": r["pending_qty"],

			"ordered_value": r["ordered_value"],
			"received_value": r["received_value"],
			"pending_value": r["pending_value"],

			"receipt_status": r["receipt_status"],
		})

	return tree