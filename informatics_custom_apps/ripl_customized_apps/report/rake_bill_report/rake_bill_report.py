# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():

    meta = frappe.get_meta("Rake Bill")
    columns = []

    exclude_fields = [
        "_user_tags",
        "_comments",
        "_assign",
        "_liked_by",
        "amended_from"
    ]

    for field in meta.fields:

        if field.fieldtype in [
            "Section Break",
            "Column Break",
            "Tab Break",
            "Button",
            "HTML",
            "Table",
            "Fold",
            "Heading"
        ]:
            continue

        if field.fieldname in exclude_fields:
            continue

        columns.append({
            "label": field.label or field.fieldname,
            "fieldname": field.fieldname,
            "fieldtype": field.fieldtype or "Data",
            "options": field.options,
            "width": 180
        })

    return columns



def get_data(filters):

    conditions = ""
    values = {}

    if filters.get("from_date") and filters.get("to_date"):
        conditions += """
            AND posting_date BETWEEN %(from_date)s AND %(to_date)s
        """

        values["from_date"] = filters.get("from_date")
        values["to_date"] = filters.get("to_date")

    query = f"""
        SELECT
            *
        FROM
            `tabRake Bill`
        WHERE
            docstatus < 2
            {conditions}
        ORDER BY
            creation DESC
    """

    return frappe.db.sql(query, values, as_dict=True)