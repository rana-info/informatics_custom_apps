import frappe
from frappe.utils import flt, getdate, nowdate


@frappe.whitelist()
def get_page_data(filters=None):
    filters = frappe._dict(frappe.parse_json(filters) or {})
    as_on = filters.get("date") or nowdate()
    filters["date"] = as_on

    quarters_meta = frappe.db.sql("""
        SELECT quarter, start_date, end_date
        FROM `tabEthanol Supply Quarter`
        WHERE start_date <= %(as_on)s
        ORDER BY start_date ASC
    """, {"as_on": as_on}, as_dict=True)

    active_quarters = []
    for q in quarters_meta:
        if getdate(q.start_date) <= getdate(as_on):
            active_quarters.append({
                "quarter":       q.quarter,
                "start_date":    str(q.start_date),
                "end_date":      str(q.end_date),
                "effective_end": str(min(getdate(q.end_date), getdate(as_on))),
            })

    if not active_quarters:
        import datetime
        d = getdate(as_on)
        qs_m = ((d.month - 1) // 3) * 3 + 1
        qs = datetime.date(d.year, qs_m, 1)
        active_quarters = [{
            "quarter":       f"Q{(qs_m-1)//3+1} {d.year}",
            "start_date":    str(qs),
            "end_date":      str(as_on),
            "effective_end": str(as_on),
        }]

    conditions = " AND di.po_date <= %(date)s"
    if filters.get("company"):
        conditions += " AND di.company = %(company)s"
    if filters.get("plant"):
        conditions += " AND di.branch = %(plant)s"
    if filters.get("customer"):
        conditions += " AND di.customer_name = %(customer)s"
    if filters.get("po_no"):
        conditions += " AND di.po_no LIKE %(po_no)s"
        filters["po_no"] = f"%{filters['po_no']}%"
    if filters.get("item_code"):
        conditions += " AND dii.item_code = %(item_code)s"

    q_sums_sql = ""
    for q in active_quarters:
        safe = _q_fieldname(q["quarter"])
        q_sums_sql += (
            f", SUM(CASE WHEN dn.is_return = 0 "
            f"AND dn.posting_date BETWEEN %(q_start_{safe})s AND %(q_eff_{safe})s "
            f"THEN dni.qty ELSE 0 END) AS `q_supplied_{safe}`"
        )
        filters[f"q_start_{safe}"] = q["start_date"]
        filters[f"q_eff_{safe}"]   = q["effective_end"]

    base_rows = frappe.db.sql(f"""
        SELECT
            di.company,
            di.branch                                                   AS plant,
            di.customer_name,
            di.po_no,
            di.po_date,
            di.name                                                     AS dispatch_order,
            dii.name                                                    AS doi_name,
            dii.item_code,
            it.item_name,
            dii.qty                                                     AS order_qty,
            dii.uom,
            IFNULL(SUM(CASE WHEN dn.is_return = 0
                     AND dn.posting_date <= %(date)s THEN dni.qty ELSE 0 END), 0)
                                                                        AS supplied_qty
            {q_sums_sql}
        FROM `tabDispatch Order` di
        INNER JOIN `tabDispatch Order Item` dii ON dii.parent = di.name
        LEFT JOIN `tabItem` it ON it.name = dii.item_code
        LEFT JOIN `tabDelivery Note Item` dni
            ON dni.custom_dispatch_order = di.name
            AND dni.item_code = dii.item_code
        LEFT JOIN `tabDelivery Note` dn
            ON dn.name = dni.parent AND dn.docstatus = 1
        WHERE di.docstatus = 1 {conditions}
        GROUP BY dii.name
        ORDER BY it.item_name ASC, di.customer_name ASC, di.po_date DESC
    """, {**filters, "date": as_on}, as_dict=True)

    rows = []
    for r in base_rows:
        order_qty = flt(r.order_qty)
        supplied  = flt(r.supplied_qty)
        row_out = {
            "company":        r.company or "",
            "plant":          r.plant or "",
            "customer_name":  r.customer_name or "",
            "po_no":          r.po_no or "",
            "po_date":        str(r.po_date) if r.po_date else "",
            "dispatch_order": r.dispatch_order,
            "item_code":      r.item_code,
            "item_name":      r.item_name or r.item_code,
            "order_qty":      order_qty,
            "supplied_qty":   supplied,
            "pending_qty":    order_qty - supplied,
            "uom":            r.uom or "",
        }
        for q in active_quarters:
            safe = _q_fieldname(q["quarter"])
            row_out[f"q_supplied_{safe}"] = flt(r.get(f"q_supplied_{safe}") or 0)
        rows.append(row_out)

    quarters_out = []
    for q in active_quarters:
        safe = _q_fieldname(q["quarter"])
        total_supplied = sum(r.get(f"q_supplied_{safe}", 0) for r in rows)
        quarters_out.append({**q, "fieldname": f"q_supplied_{safe}", "total_supplied": total_supplied})

    items_map = {}
    for r in rows:
        ic = r["item_code"]
        if ic not in items_map:
            items_map[ic] = {"item_code": ic, "item_name": r["item_name"], "uom": r["uom"],
                             "order_qty": 0.0, "supplied_qty": 0.0, "pending_qty": 0.0}
        items_map[ic]["order_qty"]    += r["order_qty"]
        items_map[ic]["supplied_qty"] += r["supplied_qty"]
        items_map[ic]["pending_qty"]  += r["pending_qty"]

    item_codes = list(items_map.keys())
    today_summary = get_item_wise_stock_dispatch(filters, item_codes=item_codes)

    return {
        "as_on":         as_on,
        "quarters":      quarters_out,
        "items":         list(items_map.values()),
        "rows":          rows,
        "today_summary": today_summary,
    }


def _q_fieldname(quarter_label):
    return "".join(ch if ch.isalnum() else "_" for ch in str(quarter_label))


def get_item_wise_stock_dispatch(filters=None, item_codes=None):
    filters = filters or frappe._dict()
    as_on = filters.get("date") or nowdate()

    if item_codes is not None:
        if not item_codes:
            return []
        item_condition = "name IN %(item_codes)s AND disabled = 0"
        item_values = {"item_codes": item_codes}
    else:
        item_condition = "disabled = 0"
        item_values = {}
        if filters.get("item_code"):
            item_condition += " AND name = %(item_code)s"
            item_values["item_code"] = filters.item_code

    items = frappe.db.sql(f"""
        SELECT name AS item_code, item_name, stock_uom AS uom
        FROM `tabItem` WHERE {item_condition} ORDER BY item_name ASC
    """, item_values, as_dict=True)

    if not items:
        return []

    codes  = [i.item_code for i in items]
    values = {"item_codes": codes, "as_on": as_on}

    stock_join = stock_company_clause = stock_plant_clause = ""
    dispatch_join = dispatch_company_clause = dispatch_plant_clause = ""
    warehouse_clause = dispatch_warehouse_clause = ""

    if filters.get("warehouse"):
        warehouse_clause          = " AND b.warehouse = %(warehouse)s"
        dispatch_warehouse_clause = " AND dni.warehouse = %(warehouse)s"
        values["warehouse"] = filters.warehouse

    if filters.get("company") or filters.get("plant"):
        stock_join = "INNER JOIN `tabWarehouse` wh ON wh.name = b.warehouse"
        if filters.get("company"):
            stock_company_clause = " AND wh.company = %(company)s"
            values["company"] = filters.company
        if filters.get("plant"):
            stock_plant_clause = " AND wh.custom_branch = %(plant)s"
            values["plant"] = filters.plant
        dispatch_join = "LEFT JOIN `tabDispatch Order` do ON do.name = dni.custom_dispatch_order"
        if filters.get("company"):
            dispatch_company_clause = " AND do.company = %(company)s"
        if filters.get("plant"):
            dispatch_plant_clause = " AND do.branch = %(plant)s"

    combined = frappe.db.sql(f"""
        SELECT i.name AS item_code,
               IFNULL(b.stock_qty, 0)    AS stock_qty,
               IFNULL(d.dispatch_qty, 0) AS dispatch_qty
        FROM (SELECT name FROM `tabItem` WHERE name IN %(item_codes)s) i
        LEFT JOIN (
            SELECT b.item_code, SUM(b.actual_qty) AS stock_qty
            FROM `tabBin` b {stock_join}
            WHERE b.item_code IN %(item_codes)s
              {warehouse_clause} {stock_company_clause} {stock_plant_clause}
            GROUP BY b.item_code
        ) b ON b.item_code = i.name
        LEFT JOIN (
            SELECT dni.item_code,
                   SUM(CASE WHEN dn.is_return = 1 THEN 0 ELSE dni.qty END) AS dispatch_qty
            FROM `tabDelivery Note Item` dni
            INNER JOIN `tabDelivery Note` dn ON dn.name = dni.parent
            {dispatch_join}
            WHERE dni.item_code IN %(item_codes)s
              AND dn.posting_date = %(as_on)s AND dn.docstatus = 1
              {dispatch_warehouse_clause} {dispatch_company_clause} {dispatch_plant_clause}
            GROUP BY dni.item_code
        ) d ON d.item_code = i.name
    """, values, as_dict=True)

    combo_map = {r.item_code: r for r in combined}
    data = []
    totals = frappe._dict(item_code="TOTAL", item_name="", uom="",
                          stock_qty=0.0, dispatch_qty=0.0, balance_qty=0.0, as_on=as_on)

    for item in items:
        c = combo_map.get(item.item_code, frappe._dict(stock_qty=0, dispatch_qty=0))
        sq = flt(c.stock_qty)
        dq = flt(c.dispatch_qty)
        bq = sq - dq
        data.append({"item_code": item.item_code, "item_name": item.item_name,
                     "uom": item.uom, "stock_qty": sq, "dispatch_qty": dq,
                     "balance_qty": bq, "as_on": as_on})
        totals.stock_qty    += sq
        totals.dispatch_qty += dq
        totals.balance_qty  += bq

    data.append(dict(totals))
    return data