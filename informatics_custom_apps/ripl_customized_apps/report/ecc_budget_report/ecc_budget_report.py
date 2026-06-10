import frappe
from frappe.utils import today

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {"label": "Budget ID", "fieldname": "budget_id", "fieldtype": "Link", "options": "Budget", "width": 180},
        {"label": "Budget Account", "fieldname": "budget_account", "fieldtype": "Link", "options": "Account", "width": 260},
        {"label": "Fiscal Year", "fieldname": "fiscal_year", "fieldtype": "Link", "options": "Fiscal Year", "width": 120},
        {"label": "Cost Center", "fieldname": "cost_center", "fieldtype": "Link", "options": "Cost Center", "width": 220},
        {"label": "Plant", "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 180},
        {"label": "Segment", "fieldname": "segment", "fieldtype": "Link", "options": "Segment", "width": 180},
        {"label": "Budget Amount", "fieldname": "budget_amount", "fieldtype": "Currency", "width": 180},
        {"label": "Actual Expense Amount", "fieldname": "actual_expense_amount", "fieldtype": "Currency", "width": 200},
        {"label": "Variance", "fieldname": "variance", "fieldtype": "Currency", "width": 220},
    ]

def get_data(filters):
    filters = frappe._dict(filters or {})


    exclude_small = int(filters.get("exclude_small_budget") or 0)

    # Date Logic
    if not filters.get("fiscal_year"):
        active_fy = frappe.db.sql(
            "SELECT name, year_start_date FROM `tabFiscal Year` WHERE CURDATE() BETWEEN year_start_date AND year_end_date LIMIT 1",
            as_dict=True
        )
        if active_fy:
            filters["fiscal_year"] = active_fy[0].name
            filters.setdefault("from_date", active_fy[0].year_start_date)
            filters.setdefault("to_date", today())
    elif not filters.get("from_date") or not filters.get("to_date"):
        fy = frappe.get_doc("Fiscal Year", filters.get("fiscal_year"))
        filters.setdefault("from_date", fy.year_start_date)
        filters.setdefault("to_date", today())

    # Build Conditions
    conditions = ["b.docstatus = 1"]
    query_filters = frappe._dict({
        "from_date": filters.get("from_date"),
        "to_date": filters.get("to_date"),
        "fiscal_year": filters.get("fiscal_year"),
    })

    if filters.get("company"):
        conditions.append("b.company IN %(company)s")
        query_filters["company"] = filters.get("company")

    if filters.get("branch"):
        conditions.append("b.branch IN %(branch)s")
        query_filters["branch"] = filters.get("branch")

    if filters.get("segment"):
        conditions.append("b.segment IN %(segment)s")
        query_filters["segment"] = filters.get("segment")

    if filters.get("fiscal_year"):
        conditions.append("b.fiscal_year = %(fiscal_year)s")


    if exclude_small == 1:
        conditions.append("ABS(ba.budget_amount) >= 2")

    conditions_sql = " AND ".join(conditions)

    query = f"""
        SELECT b.name AS budget_id, ba.account AS budget_account, b.fiscal_year, 
               b.cost_center, b.branch, b.segment, ba.budget_amount, 
               IFNULL(gl.actual_expense_amount, 0) AS actual_expense_amount,
               (ba.budget_amount - IFNULL(gl.actual_expense_amount, 0)) AS variance
        FROM `tabBudget` b
        INNER JOIN `tabBudget Account` ba ON ba.parent = b.name
        LEFT JOIN (
            SELECT gle.company, gle.account, gle.cost_center, 
                   IFNULL(gle.branch, '') AS branch, 
                   IFNULL(gle.segment, '') AS segment, 
                   SUM(gle.debit - gle.credit) AS actual_expense_amount
            FROM `tabGL Entry` gle
            WHERE gle.docstatus = 1 
              AND gle.is_cancelled = 0 
              AND gle.posting_date BETWEEN %(from_date)s AND %(to_date)s
            GROUP BY gle.company, gle.account, gle.cost_center, 
                     IFNULL(gle.branch, ''), IFNULL(gle.segment, '')
        ) gl ON gl.company = b.company 
             AND gl.account = ba.account 
             AND gl.cost_center = b.cost_center 
             AND gl.branch = IFNULL(b.branch, '') 
             AND gl.segment = IFNULL(b.segment, '')
        WHERE {conditions_sql}
        ORDER BY b.branch, b.segment, b.cost_center, ba.account
    """

    return frappe.db.sql(query, query_filters, as_dict=1)