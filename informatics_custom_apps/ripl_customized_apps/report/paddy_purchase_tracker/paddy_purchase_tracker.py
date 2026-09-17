import frappe
from frappe import _
from frappe.utils import flt

DEFAULT_ITEMS = ["106441"]

FALLBACK_QTL_FACTOR = {
    "Kg": 0.01, "Kilogram": 0.01, "Gram": 0.00001,
    "Ton": 10, "Tonne": 10, "Metric Ton": 10,
    "Quintal": 1, "Qtl": 1,
}


def execute(filters=None):
    filters = frappe._dict(filters or {})
    drill_type = filters.get("drill_type")

    if drill_type == "supplier":
        return get_supplier_drilldown_columns(), get_supplier_drilldown_data(filters)
    if drill_type == "po":
        return get_po_drilldown_columns(), get_po_drilldown_data(filters)
    if drill_type == "item":
        return get_item_drilldown_columns(), get_item_drilldown_data(filters)

    return get_summary_columns(), get_summary_data(filters)



def get_conditions(filters):
    conditions = ["po.docstatus = 1"]
    values = {}

    if filters.get("from_date") and filters.get("to_date"):
        conditions.append("po.transaction_date BETWEEN %(from_date)s AND %(to_date)s")
        values["from_date"] = filters.from_date
        values["to_date"] = filters.to_date

    if filters.get("warehouse"):
        conditions.append("poi.warehouse = %(warehouse)s")
        values["warehouse"] = filters.warehouse

    if filters.get("supplier"):
        conditions.append("po.supplier = %(supplier)s")
        values["supplier"] = filters.supplier

    if filters.get("purchase_order"):
        conditions.append("po.name = %(purchase_order)s")
        values["purchase_order"] = filters.purchase_order

    items = filters.get("item_code")
    if items:
        if isinstance(items, str):
            items = [i.strip() for i in items.split(",") if i.strip()]
        conditions.append("poi.item_code in %(items)s")
        values["items"] = tuple(items)
    else:
        conditions.append("poi.item_code in %(items)s")
        values["items"] = tuple(DEFAULT_ITEMS)

    return " AND ".join(conditions), values


def fetch_line_rows(filters):
    conditions, values = get_conditions(filters)

    rows = frappe.db.sql(
        f"""
        SELECT
            poi.warehouse,
            po.name AS purchase_order,
            po.transaction_date AS po_date,
            po.supplier,
            po.supplier_name,
            poi.item_code,
            poi.item_name,
            poi.stock_uom,
            poi.qty,
            poi.stock_qty,
            poi.received_qty,
            poi.conversion_factor,
            poi.rate,
            poi.amount
        FROM `tabPurchase Order Item` poi
        INNER JOIN `tabPurchase Order` po ON po.name = poi.parent
        WHERE {conditions}
        ORDER BY poi.warehouse, po.supplier_name, po.transaction_date, po.name
        """,
        values,
        as_dict=True,
    )

    factor_cache = {}
    result = []

    for r in rows:
        factor = get_qtl_factor(r.stock_uom, factor_cache)
        received_stock_qty = flt(r.received_qty) * flt(r.conversion_factor)

        if factor:
            ordered_qtl = flt(flt(r.stock_qty) * factor, 3)
            received_qtl = flt(received_stock_qty * factor, 3)
            pending_qtl = flt(ordered_qtl - received_qtl, 3)
            item_name = r.item_name or ""
        else:
            ordered_qtl = received_qtl = pending_qtl = 0.0
            item_name = f"{r.item_name or ''}  [UOM factor missing: {r.stock_uom}]"

        pct_received = flt((flt(r.received_qty) / r.qty) * 100, 1) if r.qty else 0

        result.append(
            {
                "warehouse": r.warehouse or "(No Warehouse)",
                "purchase_order": r.purchase_order,
                "po_date": r.po_date,
                "supplier": r.supplier or "(No Supplier)",
                "supplier_name": r.supplier_name or r.supplier or "(No Supplier)",
                "item_code": r.item_code,
                "item_name": item_name,
                "qty_ordered_qtl": ordered_qtl,
                "qty_received_qtl": received_qtl,
                "qty_pending_qtl": pending_qtl,
                "pct_received": pct_received,
                "rate": r.rate,
                "amount": flt(r.amount),
            }
        )

    return result


def get_qtl_factor(uom, cache):
    if not uom:
        return None
    if uom in cache:
        return cache[uom]

    factor = frappe.db.get_value(
        "UOM Conversion Factor", {"from_uom": uom, "to_uom": "Quintal"}, "value"
    )
    if not factor:
        reverse = frappe.db.get_value(
            "UOM Conversion Factor", {"from_uom": "Quintal", "to_uom": uom}, "value"
        )
        if reverse:
            factor = 1.0 / flt(reverse)
    if not factor:
        factor = FALLBACK_QTL_FACTOR.get(uom)

    cache[uom] = flt(factor) if factor else None
    return cache[uom]



def get_summary_columns():
    return [
        {"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Data", "width": 460, "align": "left"},
        {"label": _("No. of Suppliers"), "fieldname": "supplier_count", "fieldtype": "Int", "width": 130, "align": "left"},
        {"label": _("No. of POs"), "fieldname": "po_count", "fieldtype": "Int", "width": 100, "align": "left"},
        {"label": _("Qty Ordered (Qtl)"), "fieldname": "qty_ordered_qtl", "fieldtype": "Float", "width": 140, "align": "left"},
        {"label": _("Qty Received (Qtl)"), "fieldname": "qty_received_qtl", "fieldtype": "Float", "width": 165, "align": "left"},
        {"label": _("Pending Qty (Qtl)"), "fieldname": "qty_pending_qtl", "fieldtype": "Float", "width": 140, "align": "left"},
        {"label": _("% Received"), "fieldname": "pct_received", "fieldtype": "Percent", "width": 120, "align": "left"},
    ]


def get_summary_data(filters):
    rows = fetch_line_rows(filters)

    groups = {}
    order = []
    for r in rows:
        wh = r["warehouse"]
        if wh not in groups:
            groups[wh] = {"suppliers": set(), "pos": set(), "ordered": 0.0, "received": 0.0}
            order.append(wh)
        g = groups[wh]
        g["suppliers"].add(r["supplier"])
        g["pos"].add(r["purchase_order"])
        g["ordered"] += r["qty_ordered_qtl"]
        g["received"] += r["qty_received_qtl"]

    out = []
    for wh in order:
        g = groups[wh]
        pending = flt(g["ordered"] - g["received"], 3)
        pct = flt((g["received"] / g["ordered"]) * 100, 1) if g["ordered"] else 0
        out.append(
            {
                "warehouse": wh,
                "row_type": "warehouse",
                "supplier_count": len(g["suppliers"]),
                "po_count": len(g["pos"]),
                "qty_ordered_qtl": flt(g["ordered"], 3),
                "qty_received_qtl": flt(g["received"], 3),
                "qty_pending_qtl": pending,
                "pct_received": pct,
            }
        )

    return sorted(out, key=lambda d: d["warehouse"])



def get_supplier_drilldown_columns():
    return [
        {"label": _("Supplier"), "fieldname": "supplier_name", "fieldtype": "Data", "width": 460, "align": "left"},
        {"label": _("No. of POs"), "fieldname": "po_count", "fieldtype": "Int", "width": 100, "align": "left"},
        {"label": _("Qty Ordered (Qtl)"), "fieldname": "qty_ordered_qtl", "fieldtype": "Float", "width": 180, "align": "left"},
        {"label": _("Qty Received (Qtl)"), "fieldname": "qty_received_qtl", "fieldtype": "Float", "width": 195, "align": "left"},
        {"label": _("Qty Pending(Qtl)"), "fieldname": "qty_pending_qtl", "fieldtype": "Float", "width": 190, "align": "left"},
        {"label": _("% Received"), "fieldname": "pct_received", "fieldtype": "Percent", "width": 120, "align": "left"},
    ]


def get_supplier_drilldown_data(filters):
    rows = fetch_line_rows(filters)

    groups = {}
    order = []
    for r in rows:
        sup = r["supplier"]
        if sup not in groups:
            groups[sup] = {"name": r["supplier_name"], "pos": set(), "ordered": 0.0, "received": 0.0}
            order.append(sup)
        g = groups[sup]
        g["pos"].add(r["purchase_order"])
        g["ordered"] += r["qty_ordered_qtl"]
        g["received"] += r["qty_received_qtl"]

    out = []
    for sup in order:
        g = groups[sup]
        pending = flt(g["ordered"] - g["received"], 3)
        pct = flt((g["received"] / g["ordered"]) * 100, 1) if g["ordered"] else 0
        out.append(
            {
                "supplier": sup,
                "supplier_name": g["name"],
                "row_type": "supplier",
                "po_count": len(g["pos"]),
                "qty_ordered_qtl": flt(g["ordered"], 3),
                "qty_received_qtl": flt(g["received"], 3),
                "qty_pending_qtl": pending,
                "pct_received": pct,
            }
        )

    return sorted(out, key=lambda d: d["supplier_name"])



def get_po_drilldown_columns():
    return [
        {"label": _("Purchase Order"), "fieldname": "purchase_order", "fieldtype": "Data", "width": 220, "align": "left"},
        {"label": _("PO Date"), "fieldname": "po_date", "fieldtype": "Date", "width": 120, "align": "left"},
        {"label": _("Qty Ordered (Qtl)"), "fieldname": "qty_ordered_qtl", "fieldtype": "Float", "width": 140, "align": "left"},
        {"label": _("Qty Received (Qtl)"), "fieldname": "qty_received_qtl", "fieldtype": "Float", "width": 155, "align": "left"},
        {"label": _("Pending Qty (Qtl)"), "fieldname": "qty_pending_qtl", "fieldtype": "Float", "width": 160, "align": "left"},
        {"label": _("% Received"), "fieldname": "pct_received", "fieldtype": "Percent", "width": 120, "align": "left"},
        {"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120, "align": "left"},
    ]


def get_po_drilldown_data(filters):
    rows = fetch_line_rows(filters)

    groups = {}
    order = []
    for r in rows:
        po = r["purchase_order"]
        if po not in groups:
            groups[po] = {"po_date": r["po_date"], "ordered": 0.0, "received": 0.0, "amount": 0.0}
            order.append(po)
        g = groups[po]
        g["ordered"] += r["qty_ordered_qtl"]
        g["received"] += r["qty_received_qtl"]
        g["amount"] += r["amount"] or 0

    out = []
    for po in order:
        g = groups[po]
        pending = flt(g["ordered"] - g["received"], 3)
        pct = flt((g["received"] / g["ordered"]) * 100, 1) if g["ordered"] else 0
        out.append(
            {
                "purchase_order": po,
                "row_type": "po",
                "po_date": g["po_date"],
                "qty_ordered_qtl": flt(g["ordered"], 3),
                "qty_received_qtl": flt(g["received"], 3),
                "qty_pending_qtl": pending,
                "pct_received": pct,
                "amount": flt(g["amount"], 2),
            }
        )

    return sorted(out, key=lambda d: d["po_date"] or "")



def get_item_drilldown_columns():
    return [
        {"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 180, "align": "left"},
        {"label": _("Qty Ordered (Qtl)"), "fieldname": "qty_ordered_qtl", "fieldtype": "Float", "width": 140, "align": "left"},
        {"label": _("Qty Received (Qtl)"), "fieldname": "qty_received_qtl", "fieldtype": "Float", "width": 155, "align": "left"},
        {"label": _("Pending Qty (Qtl)"), "fieldname": "qty_pending_qtl", "fieldtype": "Float", "width": 150, "align": "left"},
        {"label": _("% Received"), "fieldname": "pct_received", "fieldtype": "Percent", "width": 130, "align": "left"},
        {"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120, "align": "left"},
    ]


def get_item_drilldown_data(filters):
    rows = fetch_line_rows(filters)
    for r in rows:
        r["row_type"] = "item"
    return sorted(rows, key=lambda r: r["item_code"] or "")