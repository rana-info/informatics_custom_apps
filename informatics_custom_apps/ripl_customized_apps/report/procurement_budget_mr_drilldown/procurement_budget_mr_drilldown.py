import frappe


def execute(filters=None):

    filters = filters or {}

    columns = [
        {
            "label": "Material Request",
            "fieldname": "material_request",
            "fieldtype": "Link",
            "options": "Material Request",
            "width": 340,

        },
        {
            "label": "MR Date",
            "fieldname": "transaction_date",
            "fieldtype": "Date",            
            "width": 340,

        },
        {
            "label": "MR Amount",
            "fieldname": "mr_amount",
            "fieldtype": "Currency",
            "width": 340,

        },
    ]

    if not filters.get("gl_account"):
        return columns, []

    conditions = [
        "mr.docstatus = 1",
        "mr.material_request_type = 'Purchase'"
    ]

    if filters.get("gl_account"):
        conditions.append("mri.expense_account = %(gl_account)s")

    if filters.get("cost_center"):
        conditions.append("mri.cost_center = %(cost_center)s")

    if filters.get("plant"):
        conditions.append("IFNULL(mri.branch,'') = %(plant)s")

    if filters.get("segment"):
        conditions.append("IFNULL(mri.segment,'') = %(segment)s")

    where_clause = " AND ".join(conditions)

    data = frappe.db.sql(f"""
        SELECT
            mr.name AS material_request,
            mr.transaction_date,

            SUM(mri.amount) AS mr_amount

        FROM `tabMaterial Request` mr
        INNER JOIN `tabMaterial Request Item` mri
            ON mri.parent = mr.name

        WHERE {where_clause}

        GROUP BY
            mr.name,
            mr.transaction_date

        ORDER BY
            mr.transaction_date DESC,
            mr.name DESC
    """, filters, as_dict=True)

    return columns, data