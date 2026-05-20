# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {
            "label": "Procurement Budget",
            "fieldname": "procurement_budget",
            "fieldtype": "Link",
            "options": "Procurement Budget",
            "width": 200,
        },
        {
            "label": "GL Account",
            "fieldname": "gl_account",
            "fieldtype": "Link",
            "options": "Account",
            "width": 300,
        },
        {
            "label": "Cost Center",
            "fieldname": "cost_center",
            "fieldtype": "Link",
            "options": "Cost Center",
            "width": 280,
        },
        {
            "label": "Plant",
            "fieldname": "plant",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": "Segment",
            "fieldname": "segment",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": "Budget Amount",
            "fieldname": "budget_amount",
            "fieldtype": "Currency",
            "width": 140,
        },
        {
            "label": "MR Amount",
            "fieldname": "mr_amount",
            "fieldtype": "Currency",
            "width": 140,
        },
        {
            "label": "PO Amount",
            "fieldname": "po_amount",
            "fieldtype": "Currency",
            "width": 140,
        },
        {
            "label": "Total Consumed",
            "fieldname": "total_consumed",
            "fieldtype": "Currency",
            "width": 150,
        },
        {
            "label": "Balance Budget",
            "fieldname": "balance_budget",
            "fieldtype": "Currency",
            "width": 150,
        },
        {
            "label": "Utilization %",
            "fieldname": "utilization",
            "fieldtype": "Percent",
            "width": 120,
        },
    ]


def get_data(filters):

	conditions = ""

	if filters.get("company"):
		conditions += " AND pb.company = %(company)s "

	if filters.get("fiscal_year"):
		conditions += " AND pb.fiscal_year = %(fiscal_year)s "

	if filters.get("gl_accounts"):
		conditions += " AND pb.gl IN %(gl_accounts)s "
		
	budget_rows = frappe.db.sql(
		f"""
		SELECT
			pb.name AS procurement_budget,
			pb.company,
			pb.fiscal_year,
			pb.gl AS gl_account,
			pbd.cost_center,
			pb.plant,
			pb.segment,
			pbd.budget_amount
		FROM `tabProcurement Budget` pb
		INNER JOIN `tabProcurement Cost Center` pbd
			ON pbd.parent = pb.name
		WHERE pb.docstatus = 1
		{conditions}
		ORDER BY pb.gl, pbd.cost_center
		""",
		filters,
		as_dict=1,
	)

	data = []

	for row in budget_rows:

		mr_amount = get_mr_consumption(row)

		po_amount = get_po_consumption(row)

		total_consumed = mr_amount + po_amount

		balance_budget = row.budget_amount - total_consumed

		utilization = 0

		if row.budget_amount:
			utilization = (
				total_consumed / row.budget_amount
			) * 100

		data.append(
			{
				"procurement_budget": row.procurement_budget,
				"gl_account": row.gl_account,
				"cost_center": row.cost_center,
				"plant": row.plant,
				"segment": row.segment,
				"budget_amount": row.budget_amount,
				"mr_amount": mr_amount,
				"po_amount": po_amount,
				"total_consumed": total_consumed,
				"balance_budget": balance_budget,
				"utilization": utilization,
			}
		)

	return data


def get_mr_consumption(row):

    result = frappe.db.sql(
        """
        SELECT
            COALESCE(SUM(mri.amount),0)
        FROM `tabMaterial Request Item` mri
        INNER JOIN `tabMaterial Request` mr
            ON mr.name = mri.parent
        WHERE mr.docstatus = 1
            AND mr.material_request_type = 'Purchase'
            AND mr.company = %(company)s
            AND mri.expense_account = %(gl_account)s
            AND mri.cost_center = %(cost_center)s
            AND IFNULL(mri.branch,'') = IFNULL(%(plant)s,'')
            AND IFNULL(mri.segment,'') = IFNULL(%(segment)s,'')
        """,
        row,
    )

    return result[0][0] or 0


def get_po_consumption(row):

    result = frappe.db.sql(
        """
        SELECT
            COALESCE(SUM(poi.amount),0)
        FROM `tabPurchase Order Item` poi
        INNER JOIN `tabPurchase Order` po
            ON po.name = poi.parent
        WHERE po.docstatus = 1
            AND po.company = %(company)s
            AND poi.expense_account = %(gl_account)s
            AND poi.cost_center = %(cost_center)s
            AND IFNULL(poi.branch,'') = IFNULL(%(plant)s,'')
            AND IFNULL(poi.segment,'') = IFNULL(%(segment)s,'')
        """,
        row,
    )

    return result[0][0] or 0
