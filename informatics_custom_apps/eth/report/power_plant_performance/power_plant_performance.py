# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
    filters = frappe._dict(filters or {})

    norms = get_norms()
    logs = get_logs(filters)

    columns = get_columns()
    data = prepare_data(logs, norms)

    return columns, data

def get_norms():
    norm_doc = frappe.get_single("ETH Logbook Norms")

    norms = {}

    for row in norm_doc.power_plant_log_norms:

        if hasattr(row, "enabled") and not row.enabled:
            continue

        if not row.fieldname:
            continue

        norms[row.fieldname] = {
            "section": row.section,
            "label": frappe.unscrub(row.fieldname).replace("_", " ").title(),
            "unit": row.unit,
            "min": row.min_value,
            "max": row.max_value,
        }

    return norms

def get_logs(filters):

    conditions = []

    if filters.company:
        conditions.append(["company", "=", filters.company])

    if filters.plant:
        conditions.append(["plant", "=", filters.plant])

    if filters.from_date:
        conditions.append(["log_date", ">=", filters.from_date])

    if filters.to_date:
        conditions.append(["log_date", "<=", filters.to_date])

    return frappe.get_all(
        "Power Plant Log Book",
        filters=conditions,
        fields=[
            "name",
            "company",
            "plant",
            "log_date"
        ]
    )

def prepare_data(logs, norms):

    data = []

    for log in logs:

        doc = frappe.get_doc("Power Plant Log Book", log.name)

        for entry in doc.logs:

            for fieldname, norm in norms.items():

                value = entry.get(fieldname)

                if value in (None, ""):
                    continue

                status = "Normal"

                if norm["min"] is not None and value < norm["min"]:
                    status = "Low"

                elif norm["max"] is not None and value > norm["max"]:
                    status = "High"

                data.append({
                    "date": doc.log_date,
                    "plant": doc.plant,
                    "time_slot": entry.time_slot,
                    "section": norm["section"],
                    "parameter": norm["label"],
                    "value": value,
                    "unit": norm["unit"],
                    "min": norm["min"],
                    "max": norm["max"],
                    "status": status
                })

    return data

def get_columns():

    return [
        {
            "label": _("Date"),
            "fieldname": "date",
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "label": _("Plant"),
            "fieldname": "plant",
            "fieldtype": "Link",
            "options": "Branch",
            "width": 180,
        },
        {
            "label": _("Time"),
            "fieldname": "time_slot",
            "fieldtype": "Data",
            "width": 90,
        },
        {
            "label": _("Section"),
            "fieldname": "section",
            "fieldtype": "Data",
            "width": 170,
        },
        {
            "label": _("Parameter"),
            "fieldname": "parameter",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": _("Value"),
            "fieldname": "value",
            "fieldtype": "Float",
            "width": 90,
        },
        {
            "label": _("Unit"),
            "fieldname": "unit",
            "fieldtype": "Data",
            "width": 80,
        },
        {
            "label": _("Min"),
            "fieldname": "min",
            "fieldtype": "Float",
            "width": 80,
        },
        {
            "label": _("Max"),
            "fieldname": "max",
            "fieldtype": "Float",
            "width": 80,
        },
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 90,
        },
    ]
	