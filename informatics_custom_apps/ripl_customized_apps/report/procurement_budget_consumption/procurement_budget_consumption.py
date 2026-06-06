import frappe


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters or {})
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
            "label": "Total MR Amount",
            "fieldname": "total_mr_amount",
            "fieldtype": "Currency",
            "width": 150,
        },
        {
            "label": "MR Pending",
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

    filters = filters or {}
    conditions = []

    if filters.get("company"):
        conditions.append("pb.company = %(company)s")

    if filters.get("fiscal_year"):
        conditions.append("pb.fiscal_year = %(fiscal_year)s")

    if filters.get("gl_accounts"):
        filters["gl_accounts"] = tuple(filters.get("gl_accounts"))
        conditions.append("pb.gl IN %(gl_accounts)s")

    if filters.get("plants"):
        filters["plants"] = tuple(filters.get("plants"))
        conditions.append("pb.plant IN %(plants)s")

    if filters.get("segments"):
        filters["segments"] = tuple(filters.get("segments"))
        conditions.append("pb.segment IN %(segments)s")

    if filters.get("hide_small_budget"):
        conditions.append("IFNULL(pbd.budget_amount, 0) > 1")

    where_clause = ""
    if conditions:
        where_clause = " AND " + " AND ".join(conditions)

    return frappe.db.sql(f"""
        SELECT
            pb.name AS procurement_budget,
            pb.gl AS gl_account,
            pbd.cost_center,
            pb.plant,
            pb.segment,
            pbd.budget_amount,
            COALESCE(mr.total_mr_amount, 0) AS total_mr_amount,
            COALESCE(mr.mr_amount, 0) AS mr_amount,
            COALESCE(po.po_amount, 0) AS po_amount,

            (
                COALESCE(mr.mr_amount, 0) + COALESCE(po.po_amount, 0)
            ) AS total_consumed,

            (
                pbd.budget_amount -
                (COALESCE(mr.mr_amount, 0) + COALESCE(po.po_amount, 0))
            ) AS balance_budget,

            CASE
                WHEN pbd.budget_amount > 0 THEN
                    ROUND(
                        (COALESCE(mr.mr_amount, 0) + COALESCE(po.po_amount, 0)) * 100
                        / pbd.budget_amount,
                        2
                    )
                ELSE 0
            END AS utilization

        FROM `tabProcurement Budget` pb

        INNER JOIN `tabProcurement Cost Center` pbd
            ON pbd.parent = pb.name
        LEFT JOIN (
            SELECT
                mri.expense_account,
                mri.cost_center,
                IFNULL(mri.branch,'') AS plant,
                IFNULL(mri.segment,'') AS segment,

                SUM(mri.amount) AS total_mr_amount,

                SUM(
                    GREATEST(
                        mri.amount - COALESCE(mr_po.po_amount, 0),
                        0
                    )
                ) AS mr_amount

            FROM `tabMaterial Request Item` mri
            INNER JOIN `tabMaterial Request` mr
                ON mr.name = mri.parent

            LEFT JOIN (
                SELECT
                    poi.material_request_item,
                    SUM(poi.amount) AS po_amount
                FROM `tabPurchase Order Item` poi
                INNER JOIN `tabPurchase Order` po
                    ON po.name = poi.parent
                WHERE po.docstatus = 1
                    AND poi.material_request_item IS NOT NULL
                GROUP BY poi.material_request_item
            ) mr_po
                ON mr_po.material_request_item = mri.name

            WHERE mr.docstatus = 1
                AND mr.material_request_type = 'Purchase'

            GROUP BY
                mri.expense_account,
                mri.cost_center,
                IFNULL(mri.branch,''),
                IFNULL(mri.segment,'')
        ) mr
            ON mr.expense_account = pb.gl
            AND mr.cost_center = pbd.cost_center
            AND mr.plant = IFNULL(pb.plant,'')
            AND mr.segment = IFNULL(pb.segment,'')

        LEFT JOIN (
            SELECT
                poi.expense_account,
                poi.cost_center,
                IFNULL(poi.branch,'') AS plant,
                IFNULL(poi.segment,'') AS segment,
                SUM(poi.amount) AS po_amount

            FROM `tabPurchase Order Item` poi
            INNER JOIN `tabPurchase Order` po
                ON po.name = poi.parent
            WHERE po.docstatus = 1

            GROUP BY
                poi.expense_account,
                poi.cost_center,
                IFNULL(poi.branch,''),
                IFNULL(poi.segment,'')
        ) po
            ON po.expense_account = pb.gl
            AND po.cost_center = pbd.cost_center
            AND po.plant = IFNULL(pb.plant,'')
            AND po.segment = IFNULL(pb.segment,'')

        LEFT JOIN (
            SELECT
                poi.expense_account,
                poi.cost_center,
                IFNULL(poi.branch,'') AS plant,
                IFNULL(poi.segment,'') AS segment,
                SUM(poi.amount) AS mr_to_po_amount

            FROM `tabPurchase Order Item` poi
            INNER JOIN `tabPurchase Order` po
                ON po.name = poi.parent
            WHERE po.docstatus = 1
                AND poi.material_request_item IS NOT NULL

            GROUP BY
                poi.expense_account,
                poi.cost_center,
                IFNULL(poi.branch,''),
                IFNULL(poi.segment,'')
        ) mrpo
            ON mrpo.expense_account = pb.gl
            AND mrpo.cost_center = pbd.cost_center
            AND mrpo.plant = IFNULL(pb.plant,'')
            AND mrpo.segment = IFNULL(pb.segment,'')

        WHERE pb.docstatus = 1
        {where_clause}

        ORDER BY pb.gl, pbd.cost_center, pb.plant, pb.segment
    """, filters, as_dict=1)