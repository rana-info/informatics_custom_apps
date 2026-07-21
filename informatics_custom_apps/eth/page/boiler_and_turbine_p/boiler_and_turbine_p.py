import frappe
from frappe import _

# Range reference values per parameter, keyed by the field_name stored on each
# min_max_avg row (matches the field_tag_map keys in PLANT_CONFIG). This isn't
# part of the DMR Parameters Range child table schema, so it's kept here as a
# static lookup — add/edit entries as needed.
PARAMETER_RANGE = {
	"main_steam_pressure": "44 ± 10",
	"main_steam_temprature": "400 ± 10",
	"turbine_steam": "38",
	# "float_zcpn": "",
	# "float_pvrh": "",
	# "float_reke": "",
	# "deaerator": "",
	# "oxygen__at_eco_ol": "",
	# "boiler_feed_water_flow": "",
	# "dm_flow_to_dearator": "",
}


@frappe.whitelist()
def get_boiler_turbine_data(company, plant, date):
	"""Fetch the min_max_avg child rows for the DMR Boiler And Turbine
	Parameters record matching company + plant + date."""
	if not (company and plant and date):
		frappe.throw(_("Company, Plant and Date are all required."))

	parent = frappe.db.get_value(
		"DMR Boiler And Turbine Parameters",
		{"company": company, "plant": plant, "date": date},
		"name",
	)

	if not parent:
		return {"parent": None, "rows": []}

	if not frappe.has_permission("DMR Boiler And Turbine Parameters", "read", parent):
		frappe.throw(_("Not permitted to read this record."), frappe.PermissionError)

	doc = frappe.get_doc("DMR Boiler And Turbine Parameters", parent)

	rows = frappe.get_all(
		"DMR Parameters Range",
		filters={"parent": parent, "parenttype": "DMR Boiler And Turbine Parameters"},
		fields=[
			"parameter_name",
			"field_name",
			"engg_units",
			"max_value",
			"max_value_time",
			"min_value",
			"min_value_time",
			"average_value",
			"idx",
		],
		order_by="idx asc",
	)

	# "Total" only makes sense for cumulative (sum-type) parameters — e.g.
	# Boiler Feed Water Flow, Main Steam Flow, DM Flow To Dearator, Turbine
	# Power, Turbine Steam. For instantaneous (avg-type) parameters like
	# pressure/temperature there is no meaningful total, so it's left blank.
	from informatics_custom_apps.eth.doctype.dmr_boiler_and_turbine_parameters.dmr_boiler_and_turbine_parameters import (
		PLANT_CONFIG,
	)
	field_tag_map = PLANT_CONFIG.get(plant, {}).get("field_tag_map", {})

	for row in rows:
		row["range"] = PARAMETER_RANGE.get(row.get("field_name"), "")
		cfg = field_tag_map.get(row.get("field_name"))
		if cfg and cfg.get("agg", "sum") == "sum":
			row["total"] = doc.get(row.get("field_name"))
		else:
			row["total"] = None

	return {"parent": parent, "rows": rows}