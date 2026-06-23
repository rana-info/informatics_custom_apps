import frappe
from frappe.utils import getdate
import calendar


def execute(filters=None):
    filters = filters or {}
    quarters = get_quarters(filters)
    columns = get_columns(quarters)
    data = get_data(filters, quarters)
    return columns, data


def get_quarters(filters):
    conditions = ""
    if filters.get("quarter"):
        conditions = "WHERE quarter = %(quarter)s"
    return frappe.db.sql(f"""
        SELECT quarter, start_date, end_date
        FROM `tabEthanol Supply Quarter`
        {conditions}
        ORDER BY start_date ASC
    """, filters, as_dict=True)


def get_month_range(start_date, end_date):
    start = getdate(start_date)
    end   = getdate(end_date)
    months, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def get_all_month_columns(quarters):
    cols = []
    for q in quarters:
        for (y, m) in get_month_range(q.start_date, q.end_date):
            cols.append((q.quarter, y, m, q.start_date, q.end_date))
    return cols


def quarter_fieldname(quarter_label):
    return "qsum_" + "".join(ch if ch.isalnum() else "_" for ch in str(quarter_label))


def get_columns(quarters):
    columns = [
        {"label": "OMC",            "fieldname": "customer_name",   "fieldtype": "Data",  "width": 380},
    ]

    # quarter sum columns start right after OMC (2nd column onward)
    for q in quarters:
        columns.append({
            "label":     q.quarter,
            "fieldname": quarter_fieldname(q.quarter),
            "fieldtype": "Data",
            "width": 90,
        })

    # individual month columns follow, label no longer prefixed with the quarter
    for q in quarters:
        for (y, m) in get_month_range(q.start_date, q.end_date):
            columns.append({
                "label":     f"{calendar.month_abbr[m]} {y}",
                "fieldname": f"month_{y}_{m:02d}",
                "fieldtype": "Data", 
                "width": 90,
            })

    columns += [
                {"label": "Balance Qty",    "fieldname": "balance_qty",     "fieldtype": "Float", "width": 120},
        		{"label": "P.O. No",        "fieldname": "po_no",           "fieldtype": "Data",  "width": 120, "align": "left"},
        		{"label": "P.O. Date",      "fieldname": "po_date",         "fieldtype": "Date",  "width": 110},
        		{"label": "Dispatch Order", "fieldname": "dispatch_order",  "fieldtype": "Link", "options": "Dispatch Order", "width": 200},
				{"label": "Item Code & Name", "fieldname": "item_display",  "fieldtype": "Data",  "width": 220},
				{"label": "UOM",            "fieldname": "uom",             "fieldtype": "Data",  "width": 60},
				{"label": "Order Qty",      "fieldname": "quarter_qty",     "fieldtype": "Float", "width": 100},
				{"label": "Supplied Qty",   "fieldname": "supplied_qty",    "fieldtype": "Float", "width": 115},
				{"label": "Fulfillment %",  "fieldname": "fulfillment_pct", "fieldtype": "Float", "width": 105},
    ]
    return columns


def get_data(filters, quarters):
    conditions = ""
    if filters.get("customer"):
        conditions += " AND di.customer_name = %(customer)s"
    if filters.get("from_date"):
        conditions += " AND di.po_date >= %(from_date)s"
    if filters.get("to_date"):
        conditions += " AND di.po_date <= %(to_date)s"
    if filters.get("po_no"):
        conditions += " AND di.po_no = %(po_no)s"
    if filters.get("quarter"):
        conditions += " AND esq.quarter = %(quarter)s"
    if filters.get("item_code"):
        conditions += " AND dii.item_code = %(item_code)s"

    base_rows = frappe.db.sql(f"""
        SELECT
            di.customer_name,
            di.po_no,
            di.po_date,
            di.name        AS dispatch_order,
            dii.name       AS dii_name,
            dii.item_code,
            it.item_name,
            CONCAT(dii.item_code, ' - ', IFNULL(it.item_name, '')) AS item_display,
            dii.qty        AS quarter_qty,
            dii.uom,
            IFNULL(SUM(CASE WHEN dn.is_return = 1 THEN 0 ELSE dni.qty END), 0) AS supplied_qty,
            GREATEST(
                dii.qty - IFNULL(SUM(CASE WHEN dn.is_return = 1 THEN 0 ELSE dni.qty END), 0),
                0
            ) AS balance_qty
        FROM `tabDispatch Order` di
        INNER JOIN `tabDispatch Order Item` dii ON di.name = dii.parent
        LEFT JOIN `tabItem` it
            ON it.name = dii.item_code
        LEFT JOIN `tabEthanol Supply Quarter` esq
            ON di.po_date BETWEEN esq.start_date AND esq.end_date
        LEFT JOIN `tabDelivery Note Item` dni
            ON dni.custom_dispatch_order = di.name AND dni.item_code = dii.item_code
        LEFT JOIN `tabDelivery Note` dn
            ON dn.name = dni.parent AND dn.docstatus = 1
        WHERE di.docstatus = 1 {conditions}
        GROUP BY dii.name
        ORDER BY di.customer_name, di.po_date DESC
    """, filters, as_dict=True)

    if not base_rows:
        return []

    all_month_cols = get_all_month_columns(quarters)

    # which month fieldnames belong to each quarter, for the quarter-sum columns
    quarter_months = {}
    for (q_label, y, m, *_rest) in all_month_cols:
        quarter_months.setdefault(q_label, []).append(f"month_{y}_{m:02d}")

    dispatch_orders = list(set(r.dispatch_order for r in base_rows))
    dn_monthly = frappe.db.sql("""
        SELECT
            dni.custom_dispatch_order,
            dni.item_code,
            YEAR(dn.posting_date)  AS yr,
            MONTH(dn.posting_date) AS mo,
            SUM(CASE WHEN dn.is_return = 1 THEN 0 ELSE dni.qty END) AS qty
        FROM `tabDelivery Note Item` dni
        INNER JOIN `tabDelivery Note` dn ON dn.name = dni.parent AND dn.docstatus = 1
        WHERE dni.custom_dispatch_order IN %(dispatch_orders)s
        GROUP BY dni.custom_dispatch_order, dni.item_code, yr, mo
    """, {"dispatch_orders": dispatch_orders}, as_dict=True)

    monthly_index = {}
    for r in dn_monthly:
        monthly_index[(r.custom_dispatch_order, r.item_code, r.yr, r.mo)] = r.qty

    result = []
    totals = {
        "customer_name": "TOTAL", "po_no": "", "po_date": "",
        "dispatch_order": "", "item_display": "", "uom": "", "dii_name": "",
        "quarter_qty": 0, "supplied_qty": 0, "balance_qty": 0,
        "bold": 1,
    }
    month_totals = {}

    for row in base_rows:
        # rows with no po_date are kept (item line still shows) but never
        # blanked out by the month cutoff below
        if row.po_date:
            po_date = getdate(row.po_date)
            po_ym   = (po_date.year, po_date.month)
        else:
            po_ym = (0, 0)

        # fulfillment %
        row["fulfillment_pct"] = (
            round((row.supplied_qty / row.quarter_qty) * 100, 2)
            if row.quarter_qty else 0.0
        )

        for (q_label, y, m, *_) in all_month_cols:
            fn = f"month_{y}_{m:02d}"
            if (y, m) < po_ym:
                # ── Fix 1: blank string → renders as empty cell, not 0 ──
                row[fn] = ""
            else:
                qty = monthly_index.get(
                    (row.dispatch_order, row.item_code, y, m), 0
                )
                # store as formatted string so Float fieldtype won't zero-pad blanks
                row[fn] = f"{qty:.3f}" if qty else "0.000"
                month_totals[fn] = month_totals.get(fn, 0) + qty

        # quarter-sum columns: sum the months inside each quarter that are
        # actually "active" for this row (on/after the PO date); a quarter
        # blanks out only if none of its months were active for this row
        for q_label, fns in quarter_months.items():
            active_vals = [row[fn] for fn in fns if row[fn] != ""]
            qfn = quarter_fieldname(q_label)
            if active_vals:
                qty_sum = sum(float(v) for v in active_vals)
                row[qfn] = f"{qty_sum:.3f}" if qty_sum else "0.000"
            else:
                row[qfn] = ""

        totals["quarter_qty"]  += row.quarter_qty  or 0
        totals["supplied_qty"] += row.supplied_qty or 0
        totals["balance_qty"]  += row.balance_qty  or 0
        result.append(row)

    # totals row fulfillment
    totals["fulfillment_pct"] = (
        round(totals["supplied_qty"] / totals["quarter_qty"] * 100, 2)
        if totals["quarter_qty"] else 0.0
    )
    for (q_label, y, m, *_) in all_month_cols:
        fn = f"month_{y}_{m:02d}"
        v  = month_totals.get(fn, 0)
        totals[fn] = f"{v:.3f}" if v else "0.000"

    # totals row quarter sums, rolled up from the month totals
    for q_label, fns in quarter_months.items():
        v = sum(month_totals.get(fn, 0) for fn in fns)
        totals[quarter_fieldname(q_label)] = f"{v:.3f}" if v else "0.000"

    result.append(totals)
    return result


@frappe.whitelist()
def get_ethanol_quarters():
    return frappe.db.sql("""
        SELECT quarter, start_date, end_date
        FROM `tabEthanol Supply Quarter`
        ORDER BY start_date ASC
    """, as_dict=True)