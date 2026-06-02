# Copyright (c) 2026
# For license information, please see license.txt

import frappe
from frappe.utils import cint, flt


def execute(filters=None):
    filters = filters or {}

    columns = get_columns()
    data = get_data(filters)

    return columns, data, None, None, None


def get_columns():
    return [
         {
			"fieldname": "tree_label",
			"label": "Cost Center / Asset / Repair",
			"fieldtype": "Data",
			"width": 300,
		},
        {
            "fieldname": "asset",
            "label": "Asset",
            "fieldtype": "Link",
            "options": "Asset",
            "width": 120,
        },
        {
            "fieldname": "asset_name",
            "label": "Asset Name",
            "fieldtype": "Data",
            "width": 320,
        },
         {
            "fieldname": "stock_cost",
            "label": "Stock Cost",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "fieldname": "purchase_cost",
            "label": "Purchase Cost",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "fieldname": "capitalized_amount",
            "label": "Capitalized Amount",
            "fieldtype": "Currency",
            "width": 140,
        },
        {
            "fieldname": "total_repair_cost",
            "label": "Total Repair Cost",
            "fieldtype": "Currency",
            "width": 140,
        },
        
        {
            "fieldname": "description",
            "label": "Error Description",
            "fieldtype": "Data",
            "width": 220,
        },
           {
            "fieldname": "actions_performed",
            "label": "Actions Performed",
            "fieldtype": "Data",
            "width": 200,
        },
        
        {
            "fieldname": "repair_type",
            "label": "Repair Type",
            "fieldtype": "Data",
            "width": 180,
        },
         {
            "fieldname": "repair_status",
            "label": "Repair Status",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "fieldname": "failure_date",
            "label": "Failure Date",
            "fieldtype": "Date",
            "width": 110,
        },
      
        {
            "fieldname": "completion_date",
            "label": "Completion Date",
            "fieldtype": "Date",
            "width": 140,
        },
        {
            "fieldname": "downtime",
            "label": "Downtime",
            "fieldtype": "data",
            "width": 100,
        },
         {
            "fieldname": "total_repairs",
            "label": "Total Repairs",
            "fieldtype": "Int",
            "width": 110,
        },
        {
            "fieldname": "capitalized_repairs",
            "label": "Capitalized Repairs",
            "fieldtype": "Int",
            "width": 140,
        },
        {
            "fieldname": "repair_id",
            "label": "Repair ID",
            "fieldtype": "Link",
            "options": "Asset Repair",
            "width": 260,
        },
    ]

def get_data(filters):

	conditions = ["ar.docstatus IN (0,1)"]
	values = {}

	if filters.get("company"):
		companies = filters.get("company")

		if isinstance(companies, str):
			companies = [d.strip() for d in companies.split(",") if d.strip()]

		conditions.append("ar.company IN %(company)s")
		values["company"] = tuple(companies)

	if filters.get("branch"):
		branches = filters.get("branch")

		if isinstance(branches, str):
			branches = [d.strip() for d in branches.split(",") if d.strip()]

		conditions.append("ar.branch IN %(branch)s")
		values["branch"] = tuple(branches)

	if filters.get("from_date"):
		conditions.append("ar.failure_date >= %(from_date)s")
		values["from_date"] = filters.get("from_date")

	if filters.get("to_date"):
		conditions.append("ar.failure_date <= %(to_date)s")
		values["to_date"] = filters.get("to_date")

	conditions = " AND ".join(conditions)

	repairs = frappe.db.sql(
		f"""
		SELECT
			ar.name AS repair_id,
			ar.asset,
			ar.asset_name,
			ar.company,
			ar.branch,
			ar.cost_center,
			ar.segment,
			ar.description,
			ar.actions_performed,

			ar.custom_repair_type AS repair_type,
			ar.repair_status,
			ar.failure_date,
			ar.completion_date,
			ar.downtime,

			IFNULL(ar.capitalize_repair_cost,0) AS capitalized_flag,
			IFNULL(ar.custom_capitalized_repair_cost,0) AS capitalized_amount,

			ROUND(
				IFNULL(SUM(DISTINCT css.total_value),0),
				2
			) AS stock_cost,

			ROUND(
				IFNULL(SUM(DISTINCT pi.repair_cost),0),
				2
			) AS purchase_cost

		FROM `tabAsset Repair` ar

		LEFT JOIN `tabAsset Repair Settlement` css
			ON css.parent = ar.name

		LEFT JOIN `tabAsset Repair Purchase Invoice` pi
			ON pi.parent = ar.name

		WHERE {conditions}

		GROUP BY ar.name

		ORDER BY
			ar.cost_center,
			ar.asset,
			ar.failure_date
		""",
		values,
		as_dict=True,
	)

	cost_center_map = {}

	for row in repairs:

		if row.capitalized_flag and row.capitalized_amount > 0:
			row.purchase_cost = 0
			row.total_repair_cost = row.capitalized_amount
		else:
			row.total_repair_cost = (
				flt(row.stock_cost) + flt(row.purchase_cost)
			)

		cost_center = row.cost_center or "Not Assigned"

		if cost_center not in cost_center_map:
			cost_center_map[cost_center] = {
				"total_repairs": 0,
				"capitalized_repairs": 0,
				"stock_cost": 0,
				"purchase_cost": 0,
				"capitalized_amount": 0,
				"total_repair_cost": 0,
				"assets": {}
			}

		cc = cost_center_map[cost_center]

		asset = row.asset

		if asset not in cc["assets"]:
			cc["assets"][asset] = {
				"asset_name": row.asset_name,
				"total_repairs": 0,
				"capitalized_repairs": 0,
				"stock_cost": 0,
				"purchase_cost": 0,
				"capitalized_amount": 0,
				"total_repair_cost": 0,
				"repairs": []
			}

		asset_row = cc["assets"][asset]

		asset_row["total_repairs"] += 1
		asset_row["capitalized_repairs"] += cint(row.capitalized_flag)
		asset_row["stock_cost"] += flt(row.stock_cost)
		asset_row["purchase_cost"] += flt(row.purchase_cost)
		asset_row["capitalized_amount"] += flt(row.capitalized_amount)
		asset_row["total_repair_cost"] += flt(row.total_repair_cost)
		asset_row["repairs"].append(row)

		cc["total_repairs"] += 1
		cc["capitalized_repairs"] += cint(row.capitalized_flag)
		cc["stock_cost"] += flt(row.stock_cost)
		cc["purchase_cost"] += flt(row.purchase_cost)
		cc["capitalized_amount"] += flt(row.capitalized_amount)
		cc["total_repair_cost"] += flt(row.total_repair_cost)

	data = []

	for cost_center, cc in cost_center_map.items():

		data.append({
			"tree_label": cost_center,
			"cost_center": cost_center,
			"total_repairs": cc["total_repairs"],
			"capitalized_repairs": cc["capitalized_repairs"],
			"stock_cost": cc["stock_cost"],
			"purchase_cost": cc["purchase_cost"],
			"capitalized_amount": cc["capitalized_amount"],
			"total_repair_cost": cc["total_repair_cost"],
			"indent": 0
		})

		for asset, asset_row in cc["assets"].items():

			data.append({
				"tree_label": asset,
				"cost_center": cost_center,
				"asset": asset,
				"asset_name": asset_row["asset_name"],
				"total_repairs": asset_row["total_repairs"],
				"capitalized_repairs": asset_row["capitalized_repairs"],
				"stock_cost": asset_row["stock_cost"],
				"purchase_cost": asset_row["purchase_cost"],
				"capitalized_amount": asset_row["capitalized_amount"],
				"total_repair_cost": asset_row["total_repair_cost"],
				"indent": 1
			})

			for repair in asset_row["repairs"]:

				data.append({
					"tree_label": repair.repair_id,
					"cost_center": cost_center,
					"repair_id": repair.repair_id,
					"repair_type": repair.repair_type,
					"description": repair.description,
					"actions_performed": repair.actions_performed,
					"repair_status": repair.repair_status,
					"failure_date": repair.failure_date,
					"completion_date": repair.completion_date,
					"downtime": repair.downtime,
					"stock_cost": repair.stock_cost,
					"purchase_cost": repair.purchase_cost,
					"capitalized_amount": repair.capitalized_amount,
					"total_repair_cost": repair.total_repair_cost,
					"indent": 2
				})

	return data