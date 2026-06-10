# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
    columns = get_columns()
    data    = get_data(filters or {})
    return columns, data


def get_columns():
    return [
        {"label": "Procurement Budget", "fieldname": "procurement_budget",
         "fieldtype": "Link", "options": "Procurement Budget", "width": 200},
        {"label": "GL Account",         "fieldname": "gl_account",
         "fieldtype": "Link", "options": "Account",            "width": 300},
        {"label": "Cost Center",        "fieldname": "cost_center",
         "fieldtype": "Link", "options": "Cost Center",        "width": 280},
        {"label": "Plant",              "fieldname": "plant",
         "fieldtype": "Data",                                  "width": 120},
        {"label": "Segment",            "fieldname": "segment",
         "fieldtype": "Data",                                  "width": 120},
        {"label": "Budget Amount",      "fieldname": "budget_amount",
         "fieldtype": "Currency",                              "width": 140},
        {"label": "Total MR Amount",    "fieldname": "total_mr_amount",
         "fieldtype": "Currency",                              "width": 150},
        {"label": "MR Pending",         "fieldname": "mr_amount",
         "fieldtype": "Currency",                              "width": 140},
        {"label": "PO Amount",          "fieldname": "po_amount",
         "fieldtype": "Currency",                              "width": 140},
        {"label": "Invoice Amount (RC)","fieldname": "invoice_amount",
         "fieldtype": "Currency",                              "width": 160},
        {"label": "Total Consumed",     "fieldname": "total_consumed",
         "fieldtype": "Currency",                              "width": 150},
        {"label": "Balance Budget",     "fieldname": "balance_budget",
         "fieldtype": "Currency",                              "width": 150},
        {"label": "Utilization %",      "fieldname": "utilization",
         "fieldtype": "Percent",                               "width": 120},
    ]


# ---------------------------------------------------------------------------
# Recommended indexes (run once in the MariaDB console / via a patch):
#
#   ALTER TABLE `tabProcurement Budget`
#       ADD INDEX idx_pb_lookup (docstatus, company, fiscal_year, gl, plant, segment);
#
#   ALTER TABLE `tabProcurement Cost Center`
#       ADD INDEX idx_pcc_parent (parent, cost_center, budget_amount);
#
#   ALTER TABLE `tabMaterial Request Item`
#       ADD INDEX idx_mri_lookup (parent, expense_account, cost_center, branch, segment);
#
#   ALTER TABLE `tabMaterial Request`
#       ADD INDEX idx_mr_lookup (docstatus, material_request_type);
#
#   ALTER TABLE `tabPurchase Order Item`
#       ADD INDEX idx_poi_lookup (parent, expense_account, cost_center, branch, segment);
#   ALTER TABLE `tabPurchase Order Item`
#       ADD INDEX idx_poi_mr (material_request_item, amount);
#
#   ALTER TABLE `tabPurchase Order`
#       ADD INDEX idx_po_lookup (docstatus);
#
#   ALTER TABLE `tabPurchase Invoice Item`
#       ADD INDEX idx_pii_lookup (parent, custom_contract, expense_account, cost_center, amount);
#
#   ALTER TABLE `tabPurchase Invoice`
#       ADD INDEX idx_pi_lookup (docstatus);
#
#   ALTER TABLE `tabContract`
#       ADD INDEX idx_contract_lookup (name, docstatus, branch, segment);
# ---------------------------------------------------------------------------


def get_data(filters):
    filters = filters or {}

    # ── 1. Build budget WHERE clause ────────────────────────────────────────
    pb_conditions  = ["pb.docstatus = 1"]
    pbd_conditions = []
    params         = {}

    if filters.get("company"):
        pb_conditions.append("pb.company = %(company)s")
        params["company"] = filters["company"]

    if filters.get("fiscal_year"):
        pb_conditions.append("pb.fiscal_year = %(fiscal_year)s")
        params["fiscal_year"] = filters["fiscal_year"]

        # Push the fiscal year date range into child-table scans so MariaDB
        # can use date indexes on the transaction tables.
        fy = frappe.db.get_value(
            "Fiscal Year", filters["fiscal_year"],
            ["year_start_date", "year_end_date"], as_dict=True
        )
        if fy:
            params["fy_start"] = fy.year_start_date
            params["fy_end"]   = fy.year_end_date

    if filters.get("gl_accounts"):
        gl_list = tuple(filters["gl_accounts"])
        pb_conditions.append("pb.gl IN %(gl_accounts)s")
        params["gl_accounts"] = gl_list

    if filters.get("plants"):
        plant_list = tuple(filters["plants"])
        pb_conditions.append("pb.plant IN %(plants)s")
        params["plants"] = plant_list

    if filters.get("segments"):
        seg_list = tuple(filters["segments"])
        pb_conditions.append("pb.segment IN %(segments)s")
        params["segments"] = seg_list

    if filters.get("hide_small_budget"):
        pbd_conditions.append("pbd.budget_amount > 1")

    pb_where  = " AND ".join(pb_conditions)
    pbd_where = (" AND " + " AND ".join(pbd_conditions)) if pbd_conditions else ""

    # ── 2. Optional fiscal-year date filter fragment ─────────────────────────
    # Reused in every child-table CTE so scans stay within the fiscal year.
    if params.get("fy_start"):
        mr_date_filter  = "AND mr.transaction_date  BETWEEN %(fy_start)s AND %(fy_end)s"
        po_date_filter  = "AND po.transaction_date  BETWEEN %(fy_start)s AND %(fy_end)s"
        pi_date_filter  = "AND pi.posting_date      BETWEEN %(fy_start)s AND %(fy_end)s"
    else:
        mr_date_filter = po_date_filter = pi_date_filter = ""

    # ── 3. Main query ────────────────────────────────────────────────────────
    #
    # Strategy:
    #   a) Aggregate MR / PO / RC amounts in CTEs first — one pass each,
    #      grouped exactly on (expense_account, cost_center, plant, segment).
    #   b) The MR CTE pre-computes the po_amount-per-MR-item in a sub-CTE
    #      so we avoid re-scanning PO items inside a correlated subquery.
    #   c) The RC CTE joins Contract *before* aggregating (not per-row) and
    #      uses COALESCE on keys at source so NULLs never reach the join.
    #   d) All LEFT JOINs use bare column equality — no functions on join keys
    #      — so composite indexes are fully utilised.
    #   e) COALESCE / IFNULL only appear in the SELECT list, never on join keys.
    #
    sql = f"""
        WITH

        /* ── PO amount raised against MR items (needed inside MR CTE) ── */
        mr_po_raised AS (
            SELECT
                poi.material_request_item,
                SUM(poi.amount) AS po_amount
            FROM `tabPurchase Order Item` poi
            INNER JOIN `tabPurchase Order` po
                ON po.name = poi.parent
               AND po.docstatus = 1
            WHERE poi.material_request_item IS NOT NULL
              AND poi.material_request_item != ''
            GROUP BY poi.material_request_item
        ),

        /* ── MR totals ── */
        mr_agg AS (
            SELECT
                mri.expense_account,
                mri.cost_center,
                COALESCE(mri.branch,  '') AS plant,
                COALESCE(mri.segment, '') AS segment,
                SUM(mri.amount)                                         AS total_mr_amount,
                SUM(GREATEST(mri.amount - COALESCE(r.po_amount, 0), 0)) AS mr_amount
            FROM `tabMaterial Request Item` mri
            INNER JOIN `tabMaterial Request` mr
                ON mr.name = mri.parent
               AND mr.docstatus = 1
               AND mr.material_request_type = 'Purchase'
               {mr_date_filter}
            LEFT JOIN mr_po_raised r
                ON r.material_request_item = mri.name
            GROUP BY
                mri.expense_account,
                mri.cost_center,
                COALESCE(mri.branch,  ''),
                COALESCE(mri.segment, '')
        ),

        /* ── Direct PO totals ── */
        po_agg AS (
            SELECT
                poi.expense_account,
                poi.cost_center,
                COALESCE(poi.branch,  '') AS plant,
                COALESCE(poi.segment, '') AS segment,
                SUM(poi.amount) AS po_amount
            FROM `tabPurchase Order Item` poi
            INNER JOIN `tabPurchase Order` po
                ON po.name = poi.parent
               AND po.docstatus = 1
               {po_date_filter}
            GROUP BY
                poi.expense_account,
                poi.cost_center,
                COALESCE(poi.branch,  ''),
                COALESCE(poi.segment, '')
        ),

        /* ── Rate Contract invoice totals ──
             Join Contract once at this level so the per-row join cost
             disappears from the outer query entirely.
        ── */
        rc_agg AS (
            SELECT
                pii.expense_account,
                pii.cost_center,
                COALESCE(rco.branch,  '') AS plant,
                COALESCE(rco.segment, '') AS segment,
                SUM(pii.amount) AS invoice_amount
            FROM `tabPurchase Invoice Item` pii
            INNER JOIN `tabPurchase Invoice` pi
                ON pi.name = pii.parent
               AND pi.docstatus = 1
               {pi_date_filter}
            INNER JOIN `tabContract` rco
                ON rco.name      = pii.custom_contract
               AND rco.docstatus = 1
            WHERE pii.custom_contract IS NOT NULL
              AND pii.custom_contract != ''
            GROUP BY
                pii.expense_account,
                pii.cost_center,
                COALESCE(rco.branch,  ''),
                COALESCE(rco.segment, '')
        )

        /* ── Final SELECT ── */
        SELECT
            pb.name  AS procurement_budget,
            pb.gl    AS gl_account,
            pbd.cost_center,
            pb.plant,
            pb.segment,
            pbd.budget_amount,

            COALESCE(mr.total_mr_amount, 0) AS total_mr_amount,
            COALESCE(mr.mr_amount,       0) AS mr_amount,
            COALESCE(po.po_amount,       0) AS po_amount,
            COALESCE(rc.invoice_amount,  0) AS invoice_amount,

            (
                COALESCE(mr.mr_amount,       0)
              + COALESCE(po.po_amount,       0)
              + COALESCE(rc.invoice_amount,  0)
            ) AS total_consumed,

            (
                pbd.budget_amount
              - COALESCE(mr.mr_amount,       0)
              - COALESCE(po.po_amount,       0)
              - COALESCE(rc.invoice_amount,  0)
            ) AS balance_budget,

            CASE
                WHEN pbd.budget_amount > 0 THEN
                    ROUND(
                        (
                            COALESCE(mr.mr_amount,       0)
                          + COALESCE(po.po_amount,       0)
                          + COALESCE(rc.invoice_amount,  0)
                        ) * 100.0 / pbd.budget_amount,
                        2
                    )
                ELSE 0
            END AS utilization

        FROM `tabProcurement Budget` pb

        INNER JOIN `tabProcurement Cost Center` pbd
            ON pbd.parent = pb.name
            {pbd_where}

        LEFT JOIN mr_agg mr
            ON mr.expense_account = pb.gl
           AND mr.cost_center     = pbd.cost_center
           AND mr.plant           = COALESCE(pb.plant,   '')
           AND mr.segment         = COALESCE(pb.segment, '')

        LEFT JOIN po_agg po
            ON po.expense_account = pb.gl
           AND po.cost_center     = pbd.cost_center
           AND po.plant           = COALESCE(pb.plant,   '')
           AND po.segment         = COALESCE(pb.segment, '')

        LEFT JOIN rc_agg rc
            ON rc.expense_account = pb.gl
           AND rc.cost_center     = pbd.cost_center
           AND rc.plant           = COALESCE(pb.plant,   '')
           AND rc.segment         = COALESCE(pb.segment, '')

        WHERE {pb_where}

        ORDER BY pb.gl, pbd.cost_center, pb.plant, pb.segment
    """

    return frappe.db.sql(sql, params, as_dict=True)


# ---------------------------------------------------------------------------
# Whitelisted method called by the JS rc-drilldown click handler
# ---------------------------------------------------------------------------
@frappe.whitelist()
def get_rc_invoice_drilldown(gl_account, cost_center, plant="", segment=""):
    """
    Returns Purchase Invoice Item rows that contributed to the RC invoice
    amount for a given (gl_account, cost_center, plant, segment) combination.
    Kept as a separate lightweight query so the main report stays fast.
    """
    return frappe.db.sql("""
        SELECT
            pi.name          AS invoice,
            pi.supplier,
            pii.custom_contract AS contract,
            pii.item_code,
            pii.item_name,
            pii.qty,
            pii.rate,
            pii.amount
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi
            ON pi.name = pii.parent
           AND pi.docstatus = 1
        INNER JOIN `tabContract` rco
            ON rco.name      = pii.custom_contract
           AND rco.docstatus = 1
        WHERE pii.custom_contract IS NOT NULL
          AND pii.custom_contract != ''
          AND pii.expense_account  = %(gl_account)s
          AND pii.cost_center      = %(cost_center)s
          AND COALESCE(rco.branch,  '') = %(plant)s
          AND COALESCE(rco.segment, '') = %(segment)s
        ORDER BY pi.name, pii.item_code
    """, {
        "gl_account":  gl_account,
        "cost_center": cost_center,
        "plant":       plant   or "",
        "segment":     segment or "",
    }, as_dict=True)