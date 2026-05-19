import frappe
from frappe.utils import getdate

def validate_procurement_budget(doc, method=None):

    if doc.doctype == "Material Request":

        if doc.material_request_type != "Purchase":
            return

    transaction_date = (
        doc.get("transaction_date")
        or doc.get("schedule_date")
        or doc.get("posting_date")
    )

    if not transaction_date:
        return

    fiscal_year = get_fiscal_year(transaction_date)

    if not fiscal_year:
        return

    procurement_budgets = frappe.get_all(
        "Procurement Budget",
        filters={
            "company": doc.company,
            "fiscal_year": fiscal_year,
            "docstatus": 1
        },
        fields=[
            "name",
            "company",
            "gl",
            "fiscal_year",
            "action_if_annual_budget_exceeded_on_mr",
            "action_if_annual_budget_exceeded_on_po"
        ]
    )

    if not procurement_budgets:
        return

    budget_map = {}

    for budget in procurement_budgets:

        budget_doc = frappe.get_doc(
            "Procurement Budget",
            budget.name
        )

        for row in budget_doc.budget_details:

            key = (
                budget.gl,
                row.cost_center,
                row.plant,
                row.segment
            )

            budget_map[key] = {
                "budget_amount": row.budget_amount,
                "budget_doc": budget_doc
            }

    grouped_items = {}

    for item in doc.items:

        expense_account = (
            item.get("expense_account")
            or item.get("expense_head")
        )

        plant = (
            item.get("plant")
            or item.get("branch")
            or item.get("custom_branch")
        )

        segment = (
            item.get("segment")
            or item.get("custom_segment")
        )

        key = (
            expense_account,
            item.cost_center,
            plant,
            segment
        )

        if key not in grouped_items:

            grouped_items[key] = {
                "amount": 0,
                "rows": []
            }

        grouped_items[key]["amount"] += item.amount or 0
        grouped_items[key]["rows"].append(item.idx)


    for key, grouped_data in grouped_items.items():

        if key not in budget_map:
            continue

        expense_account, cost_center, plant, segment = key

        budget_data = budget_map[key]

        allowed_budget = budget_data["budget_amount"]

        procurement_budget_doc = budget_data["budget_doc"]

        consumed_amount = get_consumed_budget(
            company=doc.company,
            fiscal_year=fiscal_year,
            gl_account=expense_account,
            cost_center=cost_center,
            plant=plant,
            segment=segment,
            current_doc=doc.name,
            current_doctype=doc.doctype
        )

        current_amount = grouped_data["amount"]

        total_amount = consumed_amount + current_amount

        if total_amount > allowed_budget:

            rows = ", ".join(
                [str(d) for d in grouped_data["rows"]]
            )

            action = get_budget_action(
                doc,
                procurement_budget_doc
            )

            message = f"""
            Annual Procurement Budget Exceeded For Row(s): {rows}<br><br>

            GL Account: <b>{expense_account}</b><br>
            Cost Center: <b>{cost_center}</b><br>
            Plant: <b>{plant}</b><br>
            Segment: <b>{segment}</b><br><br>

            Allowed Budget: <b>{allowed_budget}</b><br>
            Consumed Budget: <b>{consumed_amount}</b><br>
            Current Document Amount: <b>{current_amount}</b><br>
            Total Amount: <b>{total_amount}</b>
            """

            if action == "Stop":

                frappe.throw(message)

            elif action == "Warn":

                frappe.msgprint(
                    message,
                    title="Budget Warning",
                    indicator="orange"
                )

            elif action == "Ignore":

                pass


def get_budget_action(doc, procurement_budget_doc):

    if doc.doctype == "Material Request":

        if doc.material_request_type != "Purchase":
            return "Ignore"

        return (
            procurement_budget_doc.get(
                "action_if_annual_budget_exceeded_on_mr"
            )
            or "Ignore"
        )

    elif doc.doctype == "Purchase Order":

        return (
            procurement_budget_doc.get(
                "action_if_annual_budget_exceeded_on_po"
            )
            or "Ignore"
        )

    return "Ignore"


def get_fiscal_year(date):

    fiscal_year = frappe.db.get_value(
        "Fiscal Year",
        {
            "year_start_date": ("<=", getdate(date)),
            "year_end_date": (">=", getdate(date))
        },
        "name"
    )

    return fiscal_year


def get_consumed_budget(
    company,
    fiscal_year,
    gl_account,
    cost_center,
    plant,
    segment,
    current_doc,
    current_doctype
):

    fy_doc = frappe.get_doc(
        "Fiscal Year",
        fiscal_year
    )

    total = 0

    doctypes = [
        "Material Request",
        "Purchase Order"
    ]

    for doctype in doctypes:

        extra_condition = ""

        if doctype == current_doctype:

            extra_condition += f"""
                AND parent.name != '{current_doc}'
            """

        # Only Purchase Material Requests
        if doctype == "Material Request":

            extra_condition += """
                AND parent.material_request_type = 'Purchase'
            """

        query = f"""
            SELECT
                SUM(child.amount)
            FROM
                `tab{doctype} Item` child
            INNER JOIN
                `tab{doctype}` parent
                ON parent.name = child.parent
            WHERE
                parent.docstatus = 1
                AND parent.company = %(company)s
                AND parent.transaction_date BETWEEN %(from_date)s AND %(to_date)s
                AND child.cost_center = %(cost_center)s
                AND child.branch = %(plant)s
                AND child.segment = %(segment)s
                AND child.expense_account = %(gl_account)s
                {extra_condition}
        """

        result = frappe.db.sql(
            query,
            {
                "company": company,
                "from_date": fy_doc.year_start_date,
                "to_date": fy_doc.year_end_date,
                "cost_center": cost_center,
                "plant": plant,
                "segment": segment,
                "gl_account": gl_account
            }
        )

        total += result[0][0] or 0

    return total