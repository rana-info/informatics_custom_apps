import frappe


def execute(filters=None):
    filters = filters or {}

    accounts = frappe.db.sql("""
        SELECT DISTINCT
            sa.account

        FROM `tabSalary Component Account` sa

        WHERE
            sa.parenttype = 'Salary Component'
            AND sa.company = %(company)s
            AND IFNULL(sa.account, '') != ''

        ORDER BY sa.account
    """, {
        "company": filters.company
    }, as_dict=True)

    account_list = [d.account for d in accounts]

    if not account_list:
        return [], []

    cost_centers = frappe.db.sql("""
        SELECT
            gle.cost_center,
            SUM(gle.debit) AS total_debit

        FROM `tabGL Entry` gle

        INNER JOIN `tabCost Center` cc
            ON cc.name = gle.cost_center

        WHERE
            gle.docstatus = 1
            AND gle.is_cancelled = 0

            AND gle.company = %(company)s
            AND gle.branch = %(branch)s

            AND gle.posting_date BETWEEN %(from_date)s
            AND %(to_date)s

            AND gle.account IN %(accounts)s

        GROUP BY gle.cost_center

        ORDER BY gle.cost_center
    """, {
        "company": filters.company,
        "branch": filters.branch,
        "from_date": filters.from_date,
        "to_date": filters.to_date,
        "accounts": tuple(account_list)
    }, as_dict=True)

    if not cost_centers:
        return [], []

    column_totals = {}

    columns = [
        {
            "label": "Account",
            "fieldname": "account",
            "fieldtype": "Link",
            "options": "Account",
            "width": 300
        }
    ]

    for cc in cost_centers:

        fieldname = frappe.scrub(cc.cost_center)

        columns.append({
            "label": cc.cost_center,
            "fieldname": fieldname,
            "fieldtype": "Currency",
            "width": 180
        })

        column_totals[fieldname] = 0

    data = []

    for account in account_list:

        row = {
            "account": account
        }

        row_total = 0

        for cc in cost_centers:

            fieldname = frappe.scrub(cc.cost_center)

            amount = frappe.db.sql("""
                SELECT
                    SUM(gle.debit)

                FROM `tabGL Entry` gle

                WHERE
                    gle.docstatus = 1
                    AND gle.is_cancelled = 0

                    AND gle.company = %(company)s
                    AND gle.branch = %(branch)s

                    AND gle.posting_date BETWEEN %(from_date)s
                    AND %(to_date)s

                    AND gle.account = %(account)s
                    AND gle.cost_center = %(cost_center)s

            """, {
                "company": filters.company,
                "branch": filters.branch,
                "from_date": filters.from_date,
                "to_date": filters.to_date,
                "account": account,
                "cost_center": cc.cost_center
            })[0][0] or 0

            row[fieldname] = amount

            row_total += amount

            column_totals[fieldname] += amount

        if row_total != 0:
            data.append(row)

    filtered_columns = [columns[0]]

    valid_fieldnames = set()

    for col in columns[1:]:

        if column_totals.get(col["fieldname"], 0) != 0:
            filtered_columns.append(col)
            valid_fieldnames.add(col["fieldname"])

    columns = filtered_columns

    cleaned_data = []

    for row in data:

        cleaned_row = {
            "account": row["account"]
        }

        for fieldname in valid_fieldnames:
            cleaned_row[fieldname] = row.get(fieldname, 0)

        cleaned_data.append(cleaned_row)

    data = cleaned_data

    return columns, data