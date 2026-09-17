import frappe
from frappe import _
from frappe.utils import flt, cint
from collections import defaultdict

from informatics_custom_apps.ripl_customized_apps.doctype.pnl_settings.pnl_settings import (
	PNLSettings,
)

PLANT_FIELD = "branch"
SEGMENT_FIELD = "segment"

NO_PLANT = _("(No Plant)")
NO_SEGMENT = _("(No Segment)")

_scrub_cache = {}


def scrub(label):
	cached = _scrub_cache.get(label)
	if cached is None:
		cached = frappe.scrub(label)
		_scrub_cache[label] = cached
	return cached


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	settings = PNLSettings.get_active_settings()
	account_numbers = sorted(
		{row.account_number for row in settings.section_accounts if row.account_number}
	)
	if not account_numbers:
		frappe.throw(_("PNL Settings has no accounts configured"))

	account_labels = get_account_labels(account_numbers, filters.get("company"))
	plants = get_all_plants(filters)
	amounts, plant_segments = get_gl_amounts(filters, account_numbers, plants)

	columns = get_columns(plants, plant_segments)
	data = get_data(settings, amounts, account_labels, plants, plant_segments, filters.get("view") or "Detailed")

	if cint(filters.get("hide_zero")):
		columns, data = hide_zero_rows_and_columns(columns, data)

	return columns, data


def validate_filters(filters):
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("From Date and To Date are required"))


def cell_fieldname(plant, segment):
	return f"{scrub(plant)}__{scrub(segment)}"


def get_columns(plants, plant_segments):
	columns = [
		{"fieldname": "description", "label": _("Particulars"), "fieldtype": "Data", "width": 340},
	]
	for plant in plants:
		for segment in plant_segments.get(plant, []):
			columns.append(
				{
					"fieldname": cell_fieldname(plant, segment),
					"label": f"{plant} - {segment}",
					"fieldtype": "Currency",
					"width": 270,
				}
			)
	return columns


def data_fieldnames(plants, plant_segments):
	fieldnames = []
	for plant in plants:
		for segment in plant_segments.get(plant, []):
			fieldnames.append(cell_fieldname(plant, segment))
	return fieldnames


def zero_row(plants, plant_segments):
	row = {"total": 0}
	for fieldname in data_fieldnames(plants, plant_segments):
		row[fieldname] = 0
	return row


def accumulate(target, source, plants, plant_segments):
	target["total"] += source.get("total", 0)
	for fieldname in data_fieldnames(plants, plant_segments):
		target[fieldname] += source.get(fieldname, 0)


def add(a, b, plants, plant_segments):
	out = {"total": a["total"] + b["total"]}
	for fieldname in data_fieldnames(plants, plant_segments):
		out[fieldname] = a.get(fieldname, 0) + b.get(fieldname, 0)
	return out


def subtract(a, b, plants, plant_segments):
	out = {"total": a["total"] - b["total"]}
	for fieldname in data_fieldnames(plants, plant_segments):
		out[fieldname] = a.get(fieldname, 0) - b.get(fieldname, 0)
	return out


def get_all_plants(filters):
	plant_filter = filters.get("branch")
	if plant_filter and isinstance(plant_filter, str):
		plant_filter = frappe.parse_json(plant_filter)

	branches = frappe.get_all("Branch", pluck="name")
	if plant_filter:
		wanted = set(plant_filter)
		branches = [b for b in branches if b in wanted]

	return sorted(branches)


def get_account_labels(account_numbers, company=None):
	rows = frappe.get_all(
		"Account",
		filters={"account_number": ["in", account_numbers]},
		fields=["account_number", "account_name", "company"],
	)

	labels, fallback = {}, {}
	for row in rows:
		fallback.setdefault(row.account_number, row.account_name)
		if company and row.company == company:
			labels[row.account_number] = row.account_name

	for acc_no, name in fallback.items():
		labels.setdefault(acc_no, name)

	return labels


def get_gl_amounts(filters, account_numbers, plants):
	conditions = [
		"acc.account_number IN %(account_numbers)s",
		"ge.posting_date BETWEEN %(from_date)s AND %(to_date)s",
		"ge.is_cancelled = 0",
	]
	values = {
		"account_numbers": account_numbers,
		"from_date": filters.from_date,
		"to_date": filters.to_date,
	}

	if filters.get("company"):
		conditions.append("ge.company = %(company)s")
		values["company"] = filters.company

	if plants:
		conditions.append(f"ge.{PLANT_FIELD} IN %(plants)s")
		values["plants"] = plants

	query = f"""
		SELECT
			acc.account_number AS account_number,
			ge.{PLANT_FIELD} AS plant,
			ge.{SEGMENT_FIELD} AS segment,
			SUM(ge.debit - ge.credit) AS amount
		FROM `tabGL Entry` ge
		INNER JOIN `tabAccount` acc ON acc.name = ge.account
		WHERE {" AND ".join(conditions)}
		GROUP BY acc.account_number, ge.{PLANT_FIELD}, ge.{SEGMENT_FIELD}
	"""

	amounts = defaultdict(dict)
	plant_segments = defaultdict(dict)

	for row in frappe.db.sql(query, values, as_dict=True):
		plant = row.plant or NO_PLANT
		segment = row.segment or NO_SEGMENT
		amounts[row.account_number][(plant, segment)] = flt(row.amount)
		plant_segments[plant][segment] = True

	plant_segments = {plant: sorted(segs) for plant, segs in plant_segments.items()}
	return amounts, plant_segments


def build_section(section_accounts, amounts, account_labels, plants, plant_segments):
	section_total = zero_row(plants, plant_segments)
	leaf_rows = []

	for acc_row in section_accounts:
		acc_amounts = amounts.get(acc_row.account_number, {})
		label = account_labels.get(acc_row.account_number, acc_row.account_number)

		row = {"description": f"{acc_row.account_number} - {label}", "indent": 1}
		row_total = 0

		for plant in plants:
			for segment in plant_segments.get(plant, []):
				val = flt(acc_amounts.get((plant, segment), 0))
				row[cell_fieldname(plant, segment)] = val
				row_total += val

		row["total"] = row_total
		section_total["total"] += row_total
		for fieldname in data_fieldnames(plants, plant_segments):
			section_total[fieldname] += row.get(fieldname, 0)

		leaf_rows.append(row)

	return leaf_rows, section_total


def get_data(settings, amounts, account_labels, plants, plant_segments, view):
	data = []
	summary_totals = {}
	summary_order = []

	accounts_by_section = defaultdict(list)
	for acc_row in settings.section_accounts:
		accounts_by_section[acc_row.section].append(acc_row)

	for section in settings.sections:
		section_accounts = accounts_by_section.get(section.section_name, [])
		leaf_rows, section_total = build_section(
			section_accounts, amounts, account_labels, plants, plant_segments
		)

		if view == "Detailed":
			data.append(build_total_row(section.section_name, section_total, plants, plant_segments, indent=0, bold=True))
			data.extend(leaf_rows)
			if section.show_subtotal:
				data.append(
					build_total_row(
						section.subtotal_label or _("Sub Total"),
						section_total,
						plants,
						plant_segments,
						indent=1,
						bold=True,
					)
				)
			data.append(divider_row())

		key = (section.report_type, section.summary_group)
		if key not in summary_totals:
			summary_totals[key] = zero_row(plants, plant_segments)
			summary_order.append(key)
		accumulate(summary_totals[key], section_total, plants, plant_segments)

	if view == "Summary":
		data.extend(build_summary_view(summary_totals, summary_order, plants, plant_segments))

	return data


def negate(a, plants, plant_segments):
	out = {"total": -a["total"]}
	for fieldname in data_fieldnames(plants, plant_segments):
		out[fieldname] = -a.get(fieldname, 0)
	return out


def sum_report_type(report_type, summary_totals, summary_order, plants, plant_segments, multiplier=1):
	total = zero_row(plants, plant_segments)
	rows = []
	for key in summary_order:
		if key[0] != report_type:
			continue
		values = summary_totals[key]
		if multiplier == -1:
			values = negate(values, plants, plant_segments)
		rows.append(build_total_row(key[1], values, plants, plant_segments, indent=1))
		accumulate(total, values, plants, plant_segments)
	return rows, total


def build_summary_view(summary_totals, summary_order, plants, plant_segments):
	income_rows, income_total = sum_report_type(
		"Income", summary_totals, summary_order, plants, plant_segments, multiplier=-1
	)
	expense_rows, expense_total = sum_report_type("Expense", summary_totals, summary_order, plants, plant_segments)

	data = [build_total_row(_("INCOME"), income_total, plants, plant_segments, indent=0, bold=True)]
	data.extend(income_rows)
	data.append(build_total_row(_("Sub Total"), income_total, plants, plant_segments, indent=1, bold=True))
	data.append(divider_row())

	data.append(build_total_row(_("EXPENSES"), expense_total, plants, plant_segments, indent=0, bold=True))
	data.extend(expense_rows)
	data.append(build_total_row(_("Sub Total"), expense_total, plants, plant_segments, indent=1, bold=True))
	data.append(divider_row())

	pbei = subtract(income_total, expense_total, plants, plant_segments)
	data.append(build_total_row(_("Profit / (Loss) before Exceptional Items"), pbei, plants, plant_segments, bold=True))

	_unused, exceptional_total = sum_report_type("Exceptional", summary_totals, summary_order, plants, plant_segments)
	if exceptional_total["total"] or any(exceptional_total.get(f) for f in data_fieldnames(plants, plant_segments)):
		data.append(build_total_row(_("Exceptional Items"), exceptional_total, plants, plant_segments))

	pbt = add(pbei, exceptional_total, plants, plant_segments)
	data.append(build_total_row(_("Profit / (Loss) before Tax"), pbt, plants, plant_segments, bold=True))

	_unused, tax_total = sum_report_type("Tax", summary_totals, summary_order, plants, plant_segments)
	data.append(build_total_row(_("Tax Expenses"), tax_total, plants, plant_segments))

	pat = subtract(pbt, tax_total, plants, plant_segments)
	data.append(build_total_row(_("Profit / (Loss) after Tax"), pat, plants, plant_segments, bold=True))

	return data

def build_total_row(description, totals, plants, plant_segments, indent=0, bold=False):
	row = {"description": description, "indent": indent, "total": totals.get("total", 0)}
	for fieldname in data_fieldnames(plants, plant_segments):
		row[fieldname] = totals.get(fieldname, 0)
	if bold:
		row["is_bold"] = 1
	return row


def divider_row():
	return {"description": "", "is_divider": 1}


def hide_zero_rows_and_columns(columns, data):
	value_fieldnames = [c["fieldname"] for c in columns if c["fieldname"] != "description"]
	value_rows = [row for row in data if not row.get("is_divider")]

	zero_columns = {
		fieldname
		for fieldname in value_fieldnames
		if not any(flt(row.get(fieldname)) for row in value_rows)
	}

	kept_columns = [c for c in columns if c["fieldname"] not in zero_columns]
	kept_fieldnames = [c["fieldname"] for c in kept_columns if c["fieldname"] != "description"]

	kept_data = []
	for row in data:
		if row.get("is_divider"):
			kept_data.append(row)
			continue
		if any(flt(row.get(fieldname)) for fieldname in kept_fieldnames):
			kept_data.append(row)

	return kept_columns, kept_data