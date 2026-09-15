import frappe
from frappe import _
from frappe.utils import flt

from informatics_custom_apps.ripl_customized_apps.doctype.pnl_settings.pnl_settings import (
	PNLSettings,
)

PLANT_FIELD = "branch"


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
	amounts, plants = get_gl_amounts(filters, account_numbers)

	columns = get_columns(plants)
	data = get_data(settings, amounts, account_labels, plants, filters.get("view") or "Detailed")

	return columns, data


def validate_filters(filters):
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("From Date and To Date are required"))


def get_columns(plants):
	columns = [
		{"fieldname": "description", "label": _("Particulars"), "fieldtype": "Data", "width": 340},
		{"fieldname": "total", "label": _("Total"), "fieldtype": "Currency", "width": 140},
	]
	columns += [
		{"fieldname": plant_fieldname(p), "label": p, "fieldtype": "Currency", "width": 190}
		for p in plants
	]
	return columns


def plant_fieldname(plant):
	return f"plant_{frappe.scrub(plant)}"


def zero_row(plants):
	return {"total": 0, **{p: 0 for p in plants}}


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


def get_gl_amounts(filters, account_numbers):
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

	plant_filter = filters.get("branch")
	if plant_filter:
		if isinstance(plant_filter, str):
			plant_filter = frappe.parse_json(plant_filter)
		if plant_filter:
			conditions.append(f"ge.{PLANT_FIELD} IN %(plants)s")
			values["plants"] = plant_filter

	query = f"""
		SELECT
			acc.account_number AS account_number,
			ge.{PLANT_FIELD} AS plant,
			SUM(ge.credit - ge.debit) AS amount
		FROM `tabGL Entry` ge
		INNER JOIN `tabAccount` acc ON acc.name = ge.account
		WHERE {" AND ".join(conditions)}
		GROUP BY acc.account_number, ge.{PLANT_FIELD}
	"""

	amounts, plants = {}, set()
	for row in frappe.db.sql(query, values, as_dict=True):
		plant = row.plant or _("(No Plant)")
		plants.add(plant)
		amounts.setdefault(row.account_number, {})[plant] = flt(row.amount)

	return amounts, sorted(plants)


def build_section(section, section_accounts, amounts, account_labels, plants):
	section_total = zero_row(plants)
	leaf_rows = []

	for acc_row in section_accounts:
		sign = -1 if acc_row.sign == "Reverse" else 1
		acc_amounts = amounts.get(acc_row.account_number, {})
		label = account_labels.get(acc_row.account_number, acc_row.account_number)

		row = {"description": f"{acc_row.account_number} - {label}", "indent": 1}
		row_total = 0
		for plant in plants:
			val = flt(acc_amounts.get(plant, 0)) * sign
			row[plant_fieldname(plant)] = val
			section_total[plant] += val
			row_total += val
		row["total"] = row_total
		section_total["total"] += row_total
		leaf_rows.append(row)

	return leaf_rows, section_total


def get_data(settings, amounts, account_labels, plants, view):
	data = []
	summary_totals = {}
	summary_order = []

	for section in settings.sections:
		section_accounts = [a for a in settings.section_accounts if a.section == section.section_name]
		leaf_rows, section_total = build_section(section, section_accounts, amounts, account_labels, plants)

		if view == "Detailed":
			header = build_total_row(section.section_name, section_total, plants, indent=0, bold=True)
			data.append(header)
			data.extend(leaf_rows)
			if section.show_subtotal:
				data.append(
					build_total_row(
						section.subtotal_label or _("Sub Total"), section_total, plants, indent=1, bold=True
					)
				)
			data.append({"description": ""})

		key = (section.report_type, section.summary_group)
		if key not in summary_totals:
			summary_totals[key] = zero_row(plants)
			summary_order.append(key)
		accumulate(summary_totals[key], section_total, plants)

	if view == "Summary":
		data.extend(build_summary_view(summary_totals, summary_order, plants))

	return data


def sum_report_type(report_type, summary_totals, summary_order, plants):
	total = zero_row(plants)
	rows = []
	for key in summary_order:
		if key[0] != report_type:
			continue
		row = build_total_row(key[1], summary_totals[key], plants, indent=1)
		rows.append(row)
		accumulate(total, summary_totals[key], plants)
	return rows, total


def build_summary_view(summary_totals, summary_order, plants):
	income_rows, income_total = sum_report_type("Income", summary_totals, summary_order, plants)
	expense_rows, expense_total = sum_report_type("Expense", summary_totals, summary_order, plants)

	data = [build_total_row(_("INCOME"), income_total, plants, indent=0, bold=True)]
	data.extend(income_rows)
	data.append(build_total_row(_("Sub Total"), income_total, plants, indent=1, bold=True))
	data.append({"description": ""})

	data.append(build_total_row(_("EXPENSES"), expense_total, plants, indent=0, bold=True))
	data.extend(expense_rows)
	data.append(build_total_row(_("Sub Total"), expense_total, plants, indent=1, bold=True))
	data.append({"description": ""})

	pbei = subtract(income_total, expense_total, plants)
	data.append(build_total_row(_("Profit / (Loss) before Exceptional Items"), pbei, plants, bold=True))

	_unused_rows, exceptional_total = sum_report_type("Exceptional", summary_totals, summary_order, plants)
	if exceptional_total["total"] or any(exceptional_total[p] for p in plants):
		data.append(build_total_row(_("Exceptional Items"), exceptional_total, plants))

	pbt = add(pbei, exceptional_total, plants)
	data.append(build_total_row(_("Profit / (Loss) before Tax"), pbt, plants, bold=True))

	_unused_rows, tax_total = sum_report_type("Tax", summary_totals, summary_order, plants)
	data.append(build_total_row(_("Tax Expenses"), tax_total, plants))

	pat = subtract(pbt, tax_total, plants)
	data.append(build_total_row(_("Profit / (Loss) after Tax"), pat, plants, bold=True))

	return data


def build_total_row(description, totals, plants, indent=0, bold=False):
	row = {"description": description, "indent": indent, "total": totals.get("total", 0)}
	for plant in plants:
		row[plant_fieldname(plant)] = totals.get(plant, 0)
	if bold:
		row["is_bold"] = 1
	return row


def accumulate(target, source, plants):
	target["total"] += source.get("total", 0)
	for plant in plants:
		target[plant] += source.get(plant, 0)


def add(a, b, plants):
	return {"total": a["total"] + b["total"], **{p: a.get(p, 0) + b.get(p, 0) for p in plants}}


def subtract(a, b, plants):
	return {"total": a["total"] - b["total"], **{p: a.get(p, 0) - b.get(p, 0) for p in plants}}