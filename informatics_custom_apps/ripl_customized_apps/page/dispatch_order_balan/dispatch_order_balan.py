import datetime

import frappe
from frappe.utils import flt, getdate, nowdate

LITRE_UOMS = {"litre", "litres", "ltr", "ltrs", "liter", "liters", "l"}

ALLOCATION_ITEM_FIELD_MAP = {
    "Ethanol-SFG-Mfg": "ethanol_from_fci",
}
ALLOCATION_FEEDSTOCK_KEYWORDS = (
    ("dfg", "ethanol_from_dfg"),
    ("maize", "ethanol_from_maize"),
    ("fci", "ethanol_from_fci"),
)


@frappe.whitelist()
def get_page_data(filters=None):
    filters = frappe._dict(frappe.parse_json(filters) or {})
    as_on = str(getdate(filters.get("date") or nowdate()))

    quarters = _get_active_quarters(as_on)
    rows, items_map = _get_dispatch_rows(filters, as_on)
    allocations = _get_quarter_allocations(rows, items_map, quarters)

    return {
        "as_on": as_on,
        "quarters": quarters,
        "items": [i for i in items_map.values()],
        "rows": rows,
        "allocations": allocations,
        "today_summary": get_item_wise_stock_dispatch(filters, as_on, items_map),
    }


def _get_active_quarters(as_on):
    quarters_meta = frappe.db.sql(
        """
        SELECT quarter, start_date, end_date
        FROM `tabEthanol Supply Quarter`
        WHERE start_date <= %(as_on)s
        ORDER BY start_date ASC
        """,
        {"as_on": as_on},
        as_dict=True,
    )

    as_on_d = getdate(as_on)
    quarters = [
        {
            "quarter": q.quarter,
            "start_date": str(q.start_date),
            "end_date": str(q.end_date),
            "effective_end": str(min(getdate(q.end_date), as_on_d)),
        }
        for q in quarters_meta
    ]

    if not quarters:
        qs_m = ((as_on_d.month - 1) // 3) * 3 + 1
        qs = datetime.date(as_on_d.year, qs_m, 1)
        quarters = [
            {
                "quarter": f"Q{(qs_m - 1) // 3 + 1} {as_on_d.year}",
                "start_date": str(qs),
                "end_date": as_on,
                "effective_end": as_on,
            }
        ]
    return quarters


def _get_dispatch_rows(filters, as_on):
    """
    One row per (Dispatch Order, Item).

    Delivery Notes are pre-aggregated per (dispatch order, item) in a derived
    table and joined once. The old query joined every Delivery Note Item row
    onto every Dispatch Order Item row, which multiplied rows (and could
    double count supplied qty when a dispatch order had the same item twice).
    """
    params = {"date": as_on}
    where = ["di.docstatus = 1", "di.po_date <= %(date)s"]
    dn_item_cond = ""

    if filters.get("company"):
        where.append("di.company = %(company)s")
        params["company"] = filters.company
    if filters.get("plant"):
        where.append("di.branch = %(plant)s")
        params["plant"] = filters.plant
    if filters.get("customer"):
        where.append("di.customer_name = %(customer)s")
        params["customer"] = filters.customer
    if filters.get("po_no"):
        where.append("di.po_no LIKE %(po_no)s")
        params["po_no"] = f"%{filters.po_no}%"
    if filters.get("item_code"):
        where.append("dii.item_code = %(item_code)s")
        dn_item_cond = " AND dni.item_code = %(item_code)s"
        params["item_code"] = filters.item_code

    base_rows = frappe.db.sql(
        f"""
        SELECT
            di.company,
            di.branch        AS plant,
            di.customer_name,
            di.po_no,
            di.po_date,
            di.name          AS dispatch_order,
            dii.item_code,
            it.item_name,
            it.disabled      AS item_disabled,
            it.stock_uom     AS stock_uom,
            SUM(dii.qty)     AS order_qty,
            MAX(dii.uom)     AS uom,
            IFNULL(MAX(s.supplied_qty), 0) AS supplied_qty
        FROM `tabDispatch Order` di
        INNER JOIN `tabDispatch Order Item` dii ON dii.parent = di.name
        LEFT JOIN `tabItem` it ON it.name = dii.item_code
        LEFT JOIN (
            SELECT dni.custom_dispatch_order AS dispatch_order,
                   dni.item_code,
                   SUM(dni.qty) AS supplied_qty
            FROM `tabDelivery Note Item` dni
            INNER JOIN `tabDelivery Note` dn ON dn.name = dni.parent
            WHERE dn.docstatus = 1
              AND dn.is_return = 0
              AND dn.posting_date <= %(date)s
              AND IFNULL(dni.custom_dispatch_order, '') != ''
              {dn_item_cond}
            GROUP BY dni.custom_dispatch_order, dni.item_code
        ) s ON s.dispatch_order = di.name AND s.item_code = dii.item_code
        WHERE {" AND ".join(where)}
        GROUP BY di.name, dii.item_code
        ORDER BY it.item_name ASC, di.customer_name ASC, di.po_date DESC
        """,
        params,
        as_dict=True,
    )

    rows = []
    items_map = {}
    for r in base_rows:
        order_qty = flt(r.order_qty)
        supplied = flt(r.supplied_qty)
        pending = order_qty - supplied
        item_name = r.item_name or r.item_code

        rows.append(
            {
                "company": r.company or "",
                "plant": r.plant or "",
                "customer_name": r.customer_name or "",
                "po_no": r.po_no or "",
                "po_date": str(r.po_date) if r.po_date else "",
                "dispatch_order": r.dispatch_order,
                "item_code": r.item_code,
                "item_name": item_name,
                "order_qty": order_qty,
                "supplied_qty": supplied,
                "pending_qty": pending,
                "uom": r.uom or "",
            }
        )

        it = items_map.get(r.item_code)
        if not it:
            it = items_map[r.item_code] = {
                "item_code": r.item_code,
                "item_name": item_name,
                "uom": r.uom or "",
                "order_qty": 0.0,
                "supplied_qty": 0.0,
                "pending_qty": 0.0,
                "disabled": bool(r.item_disabled),
                "stock_uom": r.stock_uom or "",
            }
        it["order_qty"] += order_qty
        it["supplied_qty"] += supplied
        it["pending_qty"] += pending

    return rows, items_map


def get_item_wise_stock_dispatch(filters=None, as_on=None, items_map=None):
    """
    closing_qty  = stock as on `as_on` (Stock Ledger Entry up to that date)
    dispatch_qty = Delivery Note qty dispatched ON `as_on`
    stock_qty    = closing_qty + dispatch_qty  (stock before that day's dispatch)
    balance_qty  = closing_qty                 (stock after dispatch)

    Stock is read from Stock Ledger Entry instead of Bin. Bin only holds the
    current balance, so it never changed with the date filter.
    """
    filters = filters or frappe._dict()
    as_on = str(getdate(as_on or filters.get("date") or nowdate()))
    items_map = items_map or {}

    items = sorted(
        (i for i in items_map.values() if not i.get("disabled")),
        key=lambda i: (i["item_name"] or "").lower(),
    )
    if not items:
        return []

    item_codes = tuple(i["item_code"] for i in items)
    closing = _get_closing_stock(filters, as_on, item_codes)
    dispatched = _get_dispatch_on_date(filters, as_on, item_codes)

    data = []
    totals = {
        "item_code": "TOTAL",
        "item_name": "",
        "uom": "",
        "stock_qty": 0.0,
        "stock_kl": 0.0,
        "dispatch_qty": 0.0,
        "balance_qty": 0.0,
        "balance_kl": 0.0,
        "as_on": as_on,
    }

    for item in items:
        code = item["item_code"]
        bal = flt(closing.get(code))
        disp = flt(dispatched.get(code))
        stock = bal + disp

        is_litre = (item.get("stock_uom") or "").strip().lower() in LITRE_UOMS
        stock_kl = stock / 1000.0 if is_litre else None
        balance_kl = bal / 1000.0 if is_litre else None

        data.append(
            {
                "item_code": code,
                "item_name": item["item_name"],
                "uom": item.get("stock_uom") or item["uom"],
                "stock_qty": stock,
                "stock_kl": stock_kl,
                "dispatch_qty": disp,
                "balance_qty": bal,
                "balance_kl": balance_kl,
                "as_on": as_on,
            }
        )
        totals["stock_qty"] += stock
        totals["dispatch_qty"] += disp
        totals["balance_qty"] += bal
        if is_litre:
            totals["stock_kl"] += stock_kl
            totals["balance_kl"] += balance_kl

    data.append(totals)
    return data


def _get_closing_stock(filters, as_on, item_codes):
    params = {"as_on": as_on, "item_codes": item_codes}
    join = ""
    cond = ""

    if filters.get("warehouse"):
        cond += " AND sle.warehouse = %(warehouse)s"
        params["warehouse"] = filters.warehouse
    if filters.get("company"):
        # SLE carries company itself, no Warehouse join needed
        cond += " AND sle.company = %(company)s"
        params["company"] = filters.company
    if filters.get("plant"):
        join = "INNER JOIN `tabWarehouse` wh ON wh.name = sle.warehouse"
        cond += " AND wh.custom_branch = %(plant)s"
        params["plant"] = filters.plant

    res = frappe.db.sql(
        f"""
        SELECT sle.item_code, SUM(sle.actual_qty) AS qty
        FROM `tabStock Ledger Entry` sle
        {join}
        WHERE sle.item_code IN %(item_codes)s
          AND sle.is_cancelled = 0
          AND sle.posting_date <= %(as_on)s
          {cond}
        GROUP BY sle.item_code
        """,
        params,
        as_dict=True,
    )
    return {r.item_code: flt(r.qty) for r in res}


def _get_dispatch_on_date(filters, as_on, item_codes):
    params = {"as_on": as_on, "item_codes": item_codes}
    join = ""
    cond = ""

    if filters.get("warehouse"):
        cond += " AND dni.warehouse = %(warehouse)s"
        params["warehouse"] = filters.warehouse

    if filters.get("company") or filters.get("plant"):
        join = "INNER JOIN `tabDispatch Order` do ON do.name = dni.custom_dispatch_order"
        if filters.get("company"):
            cond += " AND do.company = %(company)s"
            params["company"] = filters.company
        if filters.get("plant"):
            cond += " AND do.branch = %(plant)s"
            params["plant"] = filters.plant

    res = frappe.db.sql(
        f"""
        SELECT dni.item_code, SUM(dni.qty) AS qty
        FROM `tabDelivery Note Item` dni
        INNER JOIN `tabDelivery Note` dn ON dn.name = dni.parent
        {join}
        WHERE dni.item_code IN %(item_codes)s
          AND dn.docstatus = 1
          AND dn.is_return = 0
          AND dn.posting_date = %(as_on)s
          {cond}
        GROUP BY dni.item_code
        """,
        params,
        as_dict=True,
    )
    return {r.item_code: flt(r.qty) for r in res}


def _allocation_field_for(item_code, item_name):
    field = ALLOCATION_ITEM_FIELD_MAP.get(item_code) or ALLOCATION_ITEM_FIELD_MAP.get(item_name)
    if field:
        return field
    text = f"{item_code} {item_name}".lower()
    for keyword, field in ALLOCATION_FEEDSTOCK_KEYWORDS:
        if keyword in text:
            return field
    return None


def _parse_supply_year(value):
    try:
        start, end = str(value).split("/")
        return getdate(start.strip()), getdate(end.strip())
    except Exception:
        return None, None


def _get_quarter_allocations(rows, items_map, quarters):
    plants = sorted({r["plant"] for r in rows if r["plant"]})
    item_fields = {}
    for code, it in items_map.items():
        field = _allocation_field_for(code, it["item_name"])
        if field:
            item_fields[code] = field
    if not plants or not item_fields:
        return {}

    recs = frappe.db.sql(
        """
        SELECT ea.ethanol_supply_year,
               aq.quarter,
               SUM(aq.ethanol_from_dfg)   AS ethanol_from_dfg,
               SUM(aq.ethanol_from_maize) AS ethanol_from_maize,
               SUM(aq.ethanol_from_fci)   AS ethanol_from_fci
        FROM `tabEthanol Allocation` ea
        INNER JOIN `tabEthanol Allocation Quarter` aq
            ON aq.parent = ea.name
            AND aq.parenttype = 'Ethanol Allocation'
            AND aq.parentfield = 'allocation'
        WHERE ea.docstatus < 2
          AND ea.plant IN %(plants)s
        GROUP BY ea.ethanol_supply_year, aq.quarter
        """,
        {"plants": tuple(plants)},
        as_dict=True,
    )

    allocations = {code: {} for code in item_fields}
    for rec in recs:
        start, end = _parse_supply_year(rec.ethanol_supply_year)
        if not start:
            continue
        label = (rec.quarter or "").strip().upper()
        for q in quarters:
            q_start = getdate(q["start_date"])
            if not (start <= q_start <= end):
                continue
            idx = ((q_start.year - start.year) * 12 + q_start.month - start.month) // 3 + 1
            if f"Q{idx}" != label:
                continue
            for code, field in item_fields.items():
                bucket = allocations[code]
                bucket[q["quarter"]] = bucket.get(q["quarter"], 0.0) + flt(rec.get(field))
    return allocations