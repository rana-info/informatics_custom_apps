import json

import frappe

# (s_no, description, unit)
LAB_PARAMETERS = [
	(1, "PH", ""),
	(2, "Temperature", "Celcius"),
	(3, "TDS", "mg/l"),
	(4, "TCOD", "mg/l"),
	(5, "SCOD", "mg/l"),
	(6, "BOD", "mg/l"),
	(7, "DO", "mg/l"),
	(8, "MLSS", "mg/l"),
	(9, "SVI", "mg/l"),
	(10, "VSS", "mg/l"),
	(11, "VFA", "mg/l"),
	(12, "NH4 - N", "mg/l"),
	(13, "FOG", "mg/l"),
	(14, "SO4", "mg/l"),
	(15, "TSS", "mg/l"),
	(16, "Alkalinity", "mg/l"),
	(17, "Chlorides", "mg/l"),
	(18, "Total Hardness", "mg/l"),
	(19, "Calcium", "mg/l"),
	(20, "P - Alkalinity", ""),
	(21, "Silica SiO2", "mg/l"),
	(22, "PO4 -P", "mg/l"),
	(23, "TBC", ""),
	(24, "SRB", ""),
	(25, "FRC", "mg/l"),
	(26, "Delta - T", "deg C"),
	(27, "CT - Evaporation", "m3/day"),
	(28, "COC", ""),
	(29, "SDI", "mg/l"),
	(30, "Turbudity", "NTU"),
]

LOCATION_FIELDS = [
	"cpu_feed",
	"eqt_tank",
	"ct_tank",
	"reactor_inlet",
	"reactor_outlet",
	"aeration_tank",
	"sec_clarifier_outlet",
	"hrscc_outlet",
	"mgf_outlet",
	"acf_outlet",
	"uv_outlet",
]


@frappe.whitelist()
def ping():
	"""Trivial connectivity test - if this doesn't return {"ok": True} in the
	browser console, the method path in the JS file is wrong or the app
	hasn't picked up this file yet (run bench build + bench clear-cache)."""
	return {"ok": True, "user": frappe.session.user}


@frappe.whitelist()
def list_existing_logs():
	"""Return existing logs for the ID dropdown: [{name, log_date}, ...]"""
	return frappe.get_all(
		"CPU Plant Lab Log",
		fields=["name", "log_date"],
		order_by="log_date desc",
		limit_page_length=0,
	)


def _blank_grid():
	grid = []
	for s_no, description, unit in LAB_PARAMETERS:
		row = {"s_no": s_no, "parameter": description, "unit": unit}
		for field in LOCATION_FIELDS:
			row[field] = None
		grid.append(row)
	return grid


def _grid_from_doc(doc):
	rows_by_sno = {row.s_no: row.as_dict() for row in doc.parameters}
	grid = []
	for s_no, description, unit in LAB_PARAMETERS:
		existing_row = rows_by_sno.get(s_no)
		row = {"s_no": s_no, "parameter": description, "unit": unit}
		for field in LOCATION_FIELDS:
			row[field] = existing_row.get(field) if existing_row else None
		grid.append(row)
	return grid


@frappe.whitelist()
def get_lab_log(log_date):
	if not frappe.db.exists("DocType", "CPU Plant Lab Log"):
		frappe.throw("DocType 'CPU Plant Lab Log' does not exist. Run bench migrate.")

	existing = frappe.db.exists("CPU Plant Lab Log", {"log_date": log_date})

	if existing:
		doc = frappe.get_doc("CPU Plant Lab Log", existing)
		return {"name": doc.name, "log_date": str(log_date), "rows": _grid_from_doc(doc)}

	return {"name": None, "log_date": str(log_date), "rows": _blank_grid()}


@frappe.whitelist()
def get_lab_log_by_name(docname):
	doc = frappe.get_doc("CPU Plant Lab Log", docname)
	return {"name": doc.name, "log_date": str(doc.log_date), "rows": _grid_from_doc(doc)}


@frappe.whitelist()
def save_lab_log(log_date, rows, docname=None):
	if isinstance(rows, str):
		rows = json.loads(rows)

	if not rows:
		frappe.throw("No rows to save.")

	if docname:
		doc = frappe.get_doc("CPU Plant Lab Log", docname)
		doc.log_date = log_date
	else:
		existing = frappe.db.exists("CPU Plant Lab Log", {"log_date": log_date})
		if existing:
			doc = frappe.get_doc("CPU Plant Lab Log", existing)
		else:
			doc = frappe.new_doc("CPU Plant Lab Log")
			doc.log_date = log_date

	doc.set("parameters", [])
	for row in rows:
		child = {
			"s_no": row.get("s_no"),
			"parameter": row.get("parameter"),
			"unit": row.get("unit"),
		}
		for field in LOCATION_FIELDS:
			value = row.get(field)
			try:
				child[field] = float(value) if value not in ("", None) else None
			except (TypeError, ValueError):
				child[field] = None
		doc.append("parameters", child)

	doc.save()
	frappe.db.commit()

	return {"name": doc.name, "log_date": str(doc.log_date)}