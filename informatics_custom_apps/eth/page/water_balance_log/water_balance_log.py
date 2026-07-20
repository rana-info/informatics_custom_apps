import frappe

@frappe.whitelist()
def get_parameters():

    meta = frappe.get_meta("Water Balance Log Book")

    skip_fields = {
        "name",
        "owner",
        "creation",
        "modified",
        "modified_by",
        "docstatus",
        "idx",
        "company",
        "plant",
        "date",
    }

    parameters = []

    for df in meta.fields:

        if df.fieldtype not in ("Float", "Int", "Currency"):
            continue

        if df.fieldname in skip_fields:
            continue

        parameters.append({
            "fieldname": df.fieldname,
            "label": df.label or df.fieldname,
            "description": df.description or ""
        })

    return parameters


@frappe.whitelist()
def get_parameter_trend(plant, parameter, from_date, to_date):

    meta = frappe.get_meta("Water Balance Log Book")

    field = meta.get_field(parameter)

    if not field:
        frappe.throw("Invalid parameter")

    if field.fieldtype not in ("Float", "Int", "Currency"):
        frappe.throw("Invalid parameter field")

    logs = frappe.get_all(
        "Water Balance Log Book",
        filters={
            "plant": plant,
            "date": ["between", [from_date, to_date]]
        },
        fields=[
            "name",
            "date",
            parameter
        ],
        order_by="date asc"
    )

    result = []

    for log in logs:

        value = log.get(parameter)

        if value in (None, ""):
            continue

        result.append({
            "date": str(log.date),
            "value": value
        })

    return {
        "data": result,
        "label": field.label or parameter
    }