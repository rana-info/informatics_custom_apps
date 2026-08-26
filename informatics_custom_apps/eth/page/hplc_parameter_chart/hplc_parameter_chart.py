# Copyright (c) 2026, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, formatdate


def get_context(context):
	# Desk Page — rendering happens entirely in hplc_parameter_chart.js
	context.no_cache = 1


@frappe.whitelist()
def get_chart_data(company=None, plant=None, from_date=None, to_date=None,
	parameter_group=None, parameters=None):
	"""Returns date-wise, per-parameter series ready for the custom SVG chart:
	{
	  "labels": ["01 Jul", "03 Jul", ...],
	  "series": {"Total Sugar (%)": [14.2, 14.6, ...], ...}
	}
	"""
	if not company:
		frappe.throw("Company is required")

	conditions = ["parent_doc.company = %(company)s"]
	values = {"company": company}

	if plant:
		conditions.append("parent_doc.plant = %(plant)s")
		values["plant"] = plant
	if from_date:
		conditions.append("parent_doc.sample_date >= %(from_date)s")
		values["from_date"] = from_date
	if to_date:
		conditions.append("parent_doc.sample_date <= %(to_date)s")
		values["to_date"] = to_date

	parameter_group = parameter_group or "Both"
	if parameter_group == "Sugar Parameters":
		conditions.append("child.parentfield = 'sugar_parameters'")
	elif parameter_group == "Organic and Alcohol Parameters":
		conditions.append("child.parentfield = 'organic_and_alcohol_parameters'")

	if parameters:
		parameter_list = frappe.parse_json(parameters) if isinstance(parameters, str) else parameters
		if parameter_list:
			conditions.append("child.parameter_name in %(parameter_list)s")
			values["parameter_list"] = tuple(parameter_list)

	condition_str = " and ".join(conditions)

	rows = frappe.db.sql(
		f"""
		select
			parent_doc.sample_date as sample_date,
			child.parameter_name as parameter_name,
			child.amount as amount
		from `tabHPLC Data` child
		inner join `tabHPLC` parent_doc on parent_doc.name = child.parent
		where {condition_str}
		order by parent_doc.sample_date asc, child.idx asc
		""",
		values,
		as_dict=True,
	)

	# preserve first-seen order for labels list (distinct dates, sorted)
	dates = sorted({row.sample_date for row in rows})
	date_index = {d: i for i, d in enumerate(dates)}

	series = {}
	param_order = []
	for row in rows:
		if row.parameter_name not in series:
			series[row.parameter_name] = [None] * len(dates)
			param_order.append(row.parameter_name)
		series[row.parameter_name][date_index[row.sample_date]] = flt(row.amount, 2)

	return {
		"labels": [formatdate(d, "dd MMM") for d in dates],
		"parameters": param_order,
		"series": series,
	}


@frappe.whitelist()
def get_parameter_list(txt=None, parameter_group=None, **kwargs):
	txt = txt or ""
	conditions = ["parameter_name like %(txt)s"]
	values = {"txt": f"%{txt}%"}

	if parameter_group == "Sugar Parameters":
		conditions.append("parentfield = 'sugar_parameters'")
	elif parameter_group == "Organic and Alcohol Parameters":
		conditions.append("parentfield = 'organic_and_alcohol_parameters'")

	condition_str = " and ".join(conditions)

	return frappe.db.sql(
		f"""
		select distinct parameter_name
		from `tabHPLC Data`
		where {condition_str}
		order by parameter_name
		limit 50
		""",
		values,
	)