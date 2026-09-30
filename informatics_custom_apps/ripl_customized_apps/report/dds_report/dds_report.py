import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, today

STATES = {
    "punjab": "Punjab",
    "haryana": "Haryana",
    "up": "UP",
    "other_state": "Other State",
}


def execute(filters=None):
    filters = frappe._dict(filters or {})
    from_date = filters.get("from_date") or add_days(today(), -30)
    to_date = filters.get("to_date") or today()

    conditions = ["p.docstatus < 2", "p.date BETWEEN %(from_date)s AND %(to_date)s"]
    values = {"from_date": from_date, "to_date": to_date}
    if filters.get("state"):
        conditions.append("d.parentfield = %(state)s")
        values["state"] = filters.state

    data = frappe.db.sql(
        f"""
        SELECT p.date, d.parentfield AS state, d.plant, d.rate
        FROM `tabDDS Details` d
        INNER JOIN `tabDDS Benchmarking` p
            ON p.name = d.parent AND d.parenttype = 'DDS Benchmarking'
        WHERE {" AND ".join(conditions)}
        """,
        values,
        as_dict=True,
    )

    dates = sorted({getdate(r.date) for r in data})

    columns = [
        {"label": _("State"), "fieldname": "state", "fieldtype": "Data", "width": 110},
        {"label": _("Plant"), "fieldname": "plant", "fieldtype": "Data", "width": 100},
    ]
    for d in dates:
        columns.append(
            {
                "label": d.strftime("%d-%m-%Y"),
                "fieldname": date_key(d),
                "fieldtype": "Float",
                "width": 120,
            }
        )

    grid = {}
    for r in data:
        cell = grid.setdefault((r.state, r.plant or ""), {})
        cell.setdefault(date_key(getdate(r.date)), []).append(flt(r.rate))

    state_order = list(STATES)
    rows = []
    for (state, plant) in sorted(
        grid, key=lambda k: (state_order.index(k[0]) if k[0] in state_order else 99, k[1])
    ):
        row = {"state": STATES.get(state, state), "plant": plant}
        for key, rates in grid[(state, plant)].items():
            row[key] = sum(rates) / len(rates)
        rows.append(row)

    return columns, rows, None, get_chart(rows, dates)


def date_key(d):
    return "d_" + d.strftime("%Y%m%d")


def get_chart(rows, dates):
    if not rows or not dates:
        return None
    return {
        "data": {
            "labels": [d.strftime("%d-%m-%Y") for d in dates],
            "datasets": [
                {
                    "name": f"{r['state']} - {r['plant']}",
                    "values": [r.get(date_key(d)) for d in dates],
                }
                for r in rows
            ],
        },
        "type": "line",
    }