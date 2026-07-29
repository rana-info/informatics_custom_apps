import frappe
from frappe.utils import getdate
from collections import defaultdict


def validate_procurement_budget(doc, method=None):
    if doc.doctype == "Material Request" and doc.material_request_type != "Purchase":
        return

    transaction_date = (
        doc.get("transaction_date") or doc.get("schedule_date") or doc.get("posting_date")
    )
    if not transaction_date:
        return

    fiscal_year_name = get_fiscal_year(transaction_date)
    if not fiscal_year_name:
        return

    fy = frappe.db.get_value(
        "Fiscal Year", fiscal_year_name, ["year_start_date", "year_end_date"], as_dict=True
    )

    procurement_budgets = frappe.get_all(
        "Procurement Budget",
        filters={"company": doc.company, "fiscal_year": fiscal_year_name, "docstatus": 1},
        fields=[
            "name", "gl", "plant", "segment",
            "action_if_annual_budget_exceeded_on_mr",
            "action_if_annual_budget_exceeded_on_po",
        ],
    )
    if not procurement_budgets:
        return

    budgets_by_name = {b.name: b for b in procurement_budgets}

    detail_rows = frappe.get_all(
        "Procurement Cost Center",
        filters={"parent": ["in", list(budgets_by_name.keys())]},
        fields=["parent", "cost_center", "budget_amount"],
    )

    budget_map = {}
    for row in detail_rows:
        b = budgets_by_name[row.parent]
        key = (b.gl, row.cost_center, b.plant, b.segment)
        budget_map[key] = {
            "budget_amount": row.budget_amount,
            "action_mr": b.action_if_annual_budget_exceeded_on_mr,
            "action_po": b.action_if_annual_budget_exceeded_on_po,
        }

    matched_items = []
    lookup_keys = set()
    for item in doc.items:
        expense_account = item.get("expense_account") or item.get("expense_head")
        plant = item.get("plant") or item.get("branch") or item.get("custom_branch")
        segment = item.get("segment") or item.get("custom_segment")
        key = (expense_account, item.cost_center, plant, segment)

        if key in budget_map:
            matched_items.append((item, expense_account, plant, segment, key))
            lookup_keys.add((item.cost_center, plant, segment, expense_account))

    if not matched_items:
        return

    consumed_map = get_consumed_budget_bulk(
        company=doc.company,
        from_date=fy.year_start_date,
        to_date=fy.year_end_date,
        keys=lookup_keys,
        current_doc=doc.name,
        current_doctype=doc.doctype,
    )

    for item, expense_account, plant, segment, key in matched_items:
        budget_data = budget_map[key]
        allowed_budget = budget_data["budget_amount"]

        consumed_amount = consumed_map.get(
            (item.cost_center, plant, segment, expense_account), 0
        )
        current_amount = item.amount or 0
        total_amount = consumed_amount + current_amount

        if total_amount > allowed_budget:
            action = get_budget_action(doc, budget_data)
            message = f"""
            Annual Procurement Budget Exceeded For Row #{item.idx}<br><br>
            GL Account: <b>{expense_account}</b><br>
            Cost Center: <b>{item.cost_center}</b><br>
            Plant: <b>{plant}</b><br>
            Segment: <b>{segment}</b><br><br>
            Allowed Budget: <b>{allowed_budget}</b><br>
            Consumed Budget: <b>{consumed_amount}</b><br>
            Current Amount: <b>{current_amount}</b><br>
            Total Amount: <b>{total_amount}</b>
            """
            if action == "Stop":
                frappe.throw(message)
            elif action == "Warn":
                frappe.msgprint(message, title="Budget Warning", indicator="orange")


def get_budget_action(doc, budget_data):
    if doc.doctype == "Material Request":
        if doc.material_request_type != "Purchase":
            return "Ignore"
        return budget_data.get("action_mr") or "Ignore"
    elif doc.doctype == "Purchase Order":
        return budget_data.get("action_po") or "Ignore"
    return "Ignore"


def get_fiscal_year(date):
    return frappe.db.get_value(
        "Fiscal Year",
        {"year_start_date": ("<=", getdate(date)), "year_end_date": (">=", getdate(date))},
        "name",
    )


def get_consumed_budget_bulk(company, from_date, to_date, keys, current_doc, current_doctype):
    """
    Returns {(cost_center, plant, segment, gl_account): consumed_amount}
    covering ALL requested keys in exactly 2 queries total (one per
    source doctype), regardless of how many items/keys there are.
    """
    if not keys:
        return {}

    cost_centers = list({k[0] for k in keys if k[0]})
    plants = list({k[1] for k in keys if k[1]})
    segments = list({k[2] for k in keys if k[2]})
    accounts = list({k[3] for k in keys if k[3]})

    consumed = defaultdict(float)
    doctypes = ["Material Request", "Purchase Order"]

    for doctype in doctypes:
        extra_condition = ""
        params = {
            "company": company,
            "from_date": from_date,
            "to_date": to_date,
            "cost_centers": cost_centers,
            "plants": plants,
            "segments": segments,
            "accounts": accounts,
        }

        if doctype == current_doctype:
            extra_condition += " AND parent.name != %(current_doc)s"
            params["current_doc"] = current_doc

        if doctype == "Material Request":
            extra_condition += " AND parent.material_request_type = 'Purchase'"

        query = f"""
            SELECT
                child.cost_center, child.branch, child.segment,
                child.expense_account, SUM(child.amount) AS total
            FROM `tab{doctype} Item` child
            INNER JOIN `tab{doctype}` parent ON parent.name = child.parent
            WHERE
                parent.docstatus = 1
                AND parent.company = %(company)s
                AND parent.transaction_date BETWEEN %(from_date)s AND %(to_date)s
                AND child.cost_center IN %(cost_centers)s
                AND child.branch IN %(plants)s
                AND child.segment IN %(segments)s
                AND child.expense_account IN %(accounts)s
                {extra_condition}
            GROUP BY child.cost_center, child.branch, child.segment, child.expense_account
        """
        for row in frappe.db.sql(query, params, as_dict=True):
            key = (row.cost_center, row.branch, row.segment, row.expense_account)
            consumed[key] += row.total or 0

    return dict(consumed)