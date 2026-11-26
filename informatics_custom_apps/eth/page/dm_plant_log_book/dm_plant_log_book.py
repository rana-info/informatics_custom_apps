import json

import frappe

TIME_SLOTS = [
	(1, "6 AM - 10 AM"), (2, "10 AM - 2 PM"),
	(3, "2 PM - 6 PM"), (4, "6 PM - 10 PM"),
	(5, "10 PM - 2 AM"), (6, "2 AM - 6 AM"),
]

TEXT_FIELDS = [
	"started_time", "stopped_time", "discharging_time", "total_running_hours",
	"storage_tank_position", "remarks",
]

NUMERIC_FIELDS = [
	"dmf_inlet_turbidity", "dmf_outlet_turbidity", "dmf_inlet_pr", "dmf_outlet_pr",
	"sac_inlet_pr", "sac_outlet_pr", "sac_ph", "sac_th", "sac_fma",
	"wba_inlet_pr", "wba_outlet_pr", "wba_outlet_pr_2",
	"sba_inlet_pr", "sba_outlet_pr", "sba_outlet_ph", "sba_outlet_conductivity", "sba_outlet_silica",
	"mb_inlet_pr", "mb_outlet_pr", "mb_before_dosing_ph", "mb_after_dosing_ph",
	"mb_outlet_conductivity", "mb_outlet_silica",
]

DATA_FIELDS = TEXT_FIELDS + NUMERIC_FIELDS

# Branch (Plant) -> allowed Segments. Same map as Material Request / Power Plant Log / CPU Lab Log.
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
		"DM Plant Logbook",
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
			"time_slot": time_slot,
			**{field: rows_by_sno.get(s_no, {}).get(field) for field in DATA_FIELDS},
		}
		for s_no, time_slot in TIME_SLOTS
	]


def _find_existing(company, plant, segment, log_date, exclude_name=None):
	filters = {"company": company, "plant": plant, "segment": segment, "log_date": log_date}
	if exclude_name:
		filters["name"] = ["!=", exclude_name]
	return frappe.db.exists("DM Plant Logbook", filters)


@frappe.whitelist()
def get_dm_log(log_date, company, plant, segment):
	if not (log_date and company and plant and segment):
		frappe.throw("company, plant, segment and log_date are all required.")

	existing = _find_existing(company, plant, segment, log_date)
	doc = frappe.get_doc("DM Plant Logbook", existing) if existing else None

	return {
		"name": doc.name if doc else None,
		"log_date": str(log_date),
		"company": company,
		"plant": plant,
		"segment": segment,
		"rows": _grid(doc.rows if doc else None),
	}


@frappe.whitelist()
def get_dm_log_by_name(docname):
	doc = frappe.get_doc("DM Plant Logbook", docname)
	return {
		"name": doc.name,
		"log_date": str(doc.log_date),
		"company": doc.company,
		"plant": doc.plant,
		"segment": doc.segment,
		"rows": _grid(doc.rows),
	}


@frappe.whitelist()
def save_dm_log(log_date, company, plant, segment, rows, docname=None):
	if isinstance(rows, str):
		rows = json.loads(rows)
	if not rows:
		frappe.throw("No rows to save.")
	if not (log_date and company and plant and segment):
		frappe.throw("company, plant, segment and log_date are all required.")

	_validate_segment(plant, segment)

	if docname:
		doc = frappe.get_doc("DM Plant Logbook", docname)
		clash = _find_existing(company, plant, segment, log_date, exclude_name=doc.name)
		if clash:
			frappe.throw(
				f"Another log ({clash}) already exists for this company, plant, segment and date."
			)
	else:
		existing = _find_existing(company, plant, segment, log_date)
		doc = frappe.get_doc("DM Plant Logbook", existing) if existing else frappe.new_doc("DM Plant Logbook")

	doc.log_date, doc.company, doc.plant, doc.segment = log_date, company, plant, segment
	doc.set("rows", [])

	for row in rows:
		child = {"s_no": row.get("s_no"), "time_slot": row.get("time_slot")}
		for field in TEXT_FIELDS:
			value = row.get(field)
			child[field] = value if value not in ("", None) else None
		for field in NUMERIC_FIELDS:
			value = row.get(field)
			try:
				child[field] = float(value) if value not in ("", None) else None
			except (TypeError, ValueError):
				child[field] = None
		doc.append("rows", child)

	doc.save()
	return {
		"name": doc.name,
		"log_date": str(doc.log_date),
		"company": doc.company,
		"plant": doc.plant,
		"segment": doc.segment,
	}