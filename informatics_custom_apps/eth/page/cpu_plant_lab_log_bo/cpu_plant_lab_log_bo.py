import json

import frappe

LAB_PARAMETERS = [
    (1, "PH", ""),
    (2, "Temperature", "Celcius"),
    (3, "TDS", "mg/l"),
    (4, "DO", "mg/l"),
    (5, "MLSS", "mg/l"),
    (6, "SVI", "mg/l"),
    (7, "VSS", "mg/l"),
    (8, "VFA", "mg/l"),
    (9, "NH4 - N", "mg/l"),
    (10, "FOG", "mg/l"),
    (11, "SO4", "mg/l"),
    (12, "TSS", "mg/l"),
    (13, "Alkalinity", "mg/l"),
    (14, "Chlorides", "mg/l"),
    (15, "Total Hardness", "mg/l"),
    (16, "Calcium", "mg/l"),
    (17, "P - Alkalinity", ""),
    (18, "Silica SiO2", "mg/l"),
    (19, "PO4 -P", "mg/l"),
    (20, "FRC", "mg/l"),
    (21, "Delta - T", "deg C"),
    (22, "CT - Evaporation", "m3/day"),
    (23, "COD", "mg/l"),
    (24, "SDI", "mg/l"),
    (25, "Turbudity", "NTU"),
]

LOCATION_FIELDS = [
	 "eqt_tank", "ct_tank", "reactor_inlet", "reactor_outlet", "aeration_tank",
	"sec_clarifier_outlet", "hrscc_outlet", "mgf_outlet", "acf_outlet", "uv_outlet",
]

# Branch (Plant) -> allowed Segments. Same map as Material Request / Power Plant Log.
BRANCH_SEGMENT_MAP = {
	"Buttar Biofuels": ["Distillery"],
	"RSL Buttar": ["Sugar", "Power", "Beet"],
	"Lakshmiji Sugar": ["Sugar"],
	"Rana Power": ["Power"],
	"RSL Belwara": ["Sugar", "Power", "Distillery"],
	"RSL Louhka": ["Distillery"],
	"RSL Shahbad": ["Sugar", "Power"],
	"RSLD Karnal": ["Distillery"],
	"RSLD Biofuels-Chhattisgarh": ["Distillery"],
	"Karimganj Biofuels": ["Distillery"],
	"Superior Biofuels": ["Distillery"],
	"ETH Louhka": ["Distillery"],
	"Superior Unn": ["Sugar", "Power"],
}
ALL_SEGMENTS = ["Beet", "Sugar", "Distillery", "Power"]


def _validate_segment(plant, segment):
	allowed = BRANCH_SEGMENT_MAP.get(plant, ALL_SEGMENTS)
	if segment not in allowed:
		frappe.throw(f"Segment {segment} is not allowed for plant {plant}.")


@frappe.whitelist()
def get_user_default_company_plant():
	employee = frappe.db.get_value(
		"Employee", {"user_id": frappe.session.user}, ["company", "branch"], as_dict=True
	)
	return {"company": employee.company if employee else None, "plant": employee.branch if employee else None}


@frappe.whitelist()
def list_existing_logs(company=None, plant=None, segment=None):
	filters = {
		k: v for k, v in {"company": company, "plant": plant, "segment": segment}.items() if v
	}
	return frappe.get_all(
		"CPU Plant Lab Log",
		filters=filters,
		fields=["name", "log_date", "company", "plant", "segment"],
		order_by="log_date desc",
		limit_page_length=0,
	)


def _grid(existing_rows=None):
	rows_by_sno = {row.s_no: row.as_dict() for row in existing_rows} if existing_rows else {}
	return [
		{
			"s_no": s_no,
			"parameter": description,
			"unit": unit,
			**{field: rows_by_sno.get(s_no, {}).get(field) for field in LOCATION_FIELDS},
		}
		for s_no, description, unit in LAB_PARAMETERS
	]


def _find_existing(company, plant, segment, log_date, exclude_name=None):
	filters = {"company": company, "plant": plant, "segment": segment, "log_date": log_date}
	if exclude_name:
		filters["name"] = ["!=", exclude_name]
	return frappe.db.exists("CPU Plant Lab Log", filters)


@frappe.whitelist()
def get_lab_log(log_date, company, plant, segment):
	if not (log_date and company and plant and segment):
		frappe.throw("company, plant, segment and log_date are all required.")

	existing = _find_existing(company, plant, segment, log_date)
	doc = frappe.get_doc("CPU Plant Lab Log", existing) if existing else None

	return {
		"name": doc.name if doc else None,
		"log_date": str(log_date),
		"company": company,
		"plant": plant,
		"segment": segment,
		"rows": _grid(doc.parameters if doc else None),
	}


@frappe.whitelist()
def get_lab_log_by_name(docname):
	doc = frappe.get_doc("CPU Plant Lab Log", docname)
	return {
		"name": doc.name,
		"log_date": str(doc.log_date),
		"company": doc.company,
		"plant": doc.plant,
		"segment": doc.segment,
		"rows": _grid(doc.parameters),
	}


@frappe.whitelist()
def save_lab_log(log_date, company, plant, segment, rows, docname=None):
	if isinstance(rows, str):
		rows = json.loads(rows)
	if not rows:
		frappe.throw("No rows to save.")
	if not (log_date and company and plant and segment):
		frappe.throw("company, plant, segment and log_date are all required.")

	_validate_segment(plant, segment)

	if docname:
		doc = frappe.get_doc("CPU Plant Lab Log", docname)
		clash = _find_existing(company, plant, segment, log_date, exclude_name=doc.name)
		if clash:
			frappe.throw(
				f"Another log ({clash}) already exists for this company, plant, segment and date."
			)
	else:
		existing = _find_existing(company, plant, segment, log_date)
		doc = frappe.get_doc("CPU Plant Lab Log", existing) if existing else frappe.new_doc("CPU Plant Lab Log")

	doc.log_date, doc.company, doc.plant, doc.segment = log_date, company, plant, segment
	doc.set("parameters", [])

	for row in rows:
		child = {"s_no": row.get("s_no"), "parameter": row.get("parameter"), "unit": row.get("unit")}
		for field in LOCATION_FIELDS:
			value = row.get(field)
			try:
				child[field] = float(value) if value not in ("", None) else None
			except (TypeError, ValueError):
				child[field] = None
		doc.append("parameters", child)

	doc.save()
	return {
		"name": doc.name,
		"log_date": str(doc.log_date),
		"company": doc.company,
		"plant": doc.plant,
		"segment": doc.segment,
	}