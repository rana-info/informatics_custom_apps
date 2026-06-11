import frappe
from frappe.utils import flt

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
			poi.item_group,

			poi.name AS po_item,
			poi.item_code,
			poi.item_name,
			poi.qty AS ordered_qty,
			poi.uom,
			poi.segment,

			IFNULL(pri.received_qty, 0) AS received_qty,
			(poi.qty - IFNULL(pri.received_qty, 0)) AS pending_qty,

			po.grand_total AS po_value,
			poi.branch AS plant,

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
			"item_group":r.item_group,

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

		key = (r["item_group"], r["plant"], r["po_no"])

		if key not in po_summary:
			po_summary[key] = {
				"oq": 0,
				"rq": 0,
				"pq": 0,
				"ov": 0,
				"rv": 0,
				"pv": 0,

				"po_date": r["po_date"],
				"supplier": r["supplier"],
				"supplier_name": r["supplier_name"],
				"incoterm": r["incoterm"],
				"custom_despatch_material_to": r["custom_despatch_material_to"],
				"company": r["company"],
			}

		s = po_summary[key]

		s["oq"] += r["ordered_qty"]
		s["rq"] += r["received_qty"]
		s["pq"] += r["pending_qty"]

		s["ov"] += r["ordered_value"]
		s["rv"] += r["received_value"]
		s["pv"] += r["pending_value"]


	# -----------------------------------
	# Plant Summary
	# -----------------------------------

	plant_summary = {}

	for (grp, plant, po), s in po_summary.items():

		key = (grp, plant)

		if key not in plant_summary:
			plant_summary[key] = {
				"oq": 0,
				"rq": 0,
				"pq": 0,
				"ov": 0,
				"rv": 0,
				"pv": 0,
			}

		plant_summary[key]["oq"] += s["oq"]
		plant_summary[key]["rq"] += s["rq"]
		plant_summary[key]["pq"] += s["pq"]

		plant_summary[key]["ov"] += s["ov"]
		plant_summary[key]["rv"] += s["rv"]
		plant_summary[key]["pv"] += s["pv"]


	# -----------------------------------
	# Group Summary
	# -----------------------------------

	group_summary = {}

	for (grp, plant), p in plant_summary.items():

		if grp not in group_summary:
			group_summary[grp] = {
				"oq": 0,
				"rq": 0,
				"pq": 0,
				"ov": 0,
				"rv": 0,
				"pv": 0,
			}

		group_summary[grp]["oq"] += p["oq"]
		group_summary[grp]["rq"] += p["rq"]
		group_summary[grp]["pq"] += p["pq"]

		group_summary[grp]["ov"] += p["ov"]
		group_summary[grp]["rv"] += p["rv"]
		group_summary[grp]["pv"] += p["pv"]


	tree = []

	# GROUP
	for grp, g in group_summary.items():

		group_id = f"GRP::{grp}"

		tree.append({
			"name": grp,
			"doctype": "Item Group",
			"docname": group_id,
			"parent": "",
			"indent": 0,

			"ordered_qty": g["oq"],
			"received_qty": g["rq"],
			"pending_qty": g["pq"],

			"ordered_value": g["ov"],
			"received_value": g["rv"],
			"pending_value": g["pv"],
		})

		# PLANT
		plants = [
			x for x in plant_summary
			if x[0] == grp
		]

		for (_, plant) in plants:

			p = plant_summary[(grp, plant)]

			plant_id = f"{grp}::{plant}"

			tree.append({
				"name": plant,
				"doctype": "Branch",
				"docname": plant_id,
				"parent": group_id,
				"indent": 1,

				"ordered_qty": p["oq"],
				"received_qty": p["rq"],
				"pending_qty": p["pq"],

				"ordered_value": p["ov"],
				"received_value": p["rv"],
				"pending_value": p["pv"],
			})

			# PO
			pos = [
				x for x in po_summary
				if x[0] == grp and x[1] == plant
			]

			for (_, _, po) in pos:

				s = po_summary[(grp, plant, po)]

				po_id = f"{grp}::{plant}::{po}"

				tree.append({
					"name": po,
					"doctype": "Purchase Order",
					"docname": po_id,
					"parent": plant_id,
					"indent": 2,

					"po_date": s["po_date"],
					"supplier": s["supplier"],
					"supplier_name": s["supplier_name"],
					"company": s["company"],

					"ordered_qty": s["oq"],
					"received_qty": s["rq"],
					"pending_qty": s["pq"],

					"ordered_value": s["ov"],
					"received_value": s["rv"],
					"pending_value": s["pv"],

					"custom_despatch_material_to": s["custom_despatch_material_to"],
					"incoterm": s["incoterm"],
				})

				# ITEMS
				for r in item_rows:

					if (
						r["item_group"] == grp
						and r["plant"] == plant
						and r["po_no"] == po
					):

						tree.append({
							"name": f'{r["item_code"]} - {r["item_name"]}',
							"doctype": "Item",
							"docname": f'{po_id}::{r["item_code"]}',
							"parent": po_id,
							"indent": 3,

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