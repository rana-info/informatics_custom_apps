import frappe
from frappe import _
from frappe.utils import flt, getdate, cint
from frappe.utils.nestedset import get_descendants_of


def execute(filters=None):
    filters = filters or {}
    validate_filters(filters)

    columns = get_columns()
    data = get_data(filters)
    return columns, data


def validate_filters(filters):
    if not filters.get("company"):
        frappe.throw(_("Company is mandatory"))
    if not filters.get("from_date"):
        frappe.throw(_("From Date is mandatory"))
    if not filters.get("to_date"):
        frappe.throw(_("To Date is mandatory"))
    if getdate(filters.get("from_date")) > getdate(filters.get("to_date")):
        frappe.throw(_("From Date cannot be after To Date"))


def get_columns():
    return [
        {"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
        {"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
        {"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 150},
        {"label": _("Voucher Type"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 140},
        {"label": _("Voucher No"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 160},
        {"label": _("Plant"), "fieldname": "plant", "fieldtype": "Link", "options": "Branch", "width": 120},
        {"label": _("Segment"), "fieldname": "segment", "fieldtype": "Data", "width": 120},
        {"label": _("In Qty"), "fieldname": "in_qty", "fieldtype": "Float", "width": 90},
        {"label": _("Out Qty"), "fieldname": "out_qty", "fieldtype": "Float", "width": 90},
        {"label": _("Balance Qty"), "fieldname": "balance_qty", "fieldtype": "Float", "width": 100},
        {"label": _("In Value"), "fieldname": "in_value", "fieldtype": "Currency", "width": 120},
        {"label": _("Out Value"), "fieldname": "out_value", "fieldtype": "Currency", "width": 120},
        {"label": _("Balance Value"), "fieldname": "balance_value", "fieldtype": "Currency", "width": 130},
        {"label": _("Valuation Rate"), "fieldname": "valuation_rate", "fieldtype": "Currency", "width": 110},
    ]


def get_warehouse_list(warehouse):
    """Expand a group warehouse into itself + all descendant warehouses.
    Leaf warehouses are returned as a single-item list."""
    if frappe.db.get_value("Warehouse", warehouse, "is_group"):
        return get_descendants_of("Warehouse", warehouse) + [warehouse]
    return [warehouse]


def get_data(filters):
    from_date = getdate(filters.get("from_date"))
    to_date = getdate(filters.get("to_date"))
    currency_precision = cint(frappe.db.get_default("currency_precision")) or 2
    qty_precision = cint(frappe.db.get_default("float_precision")) or 6
    show_opening_row = not filters.get("hide_opening_row")

    # 1. Dynamic Query Filters. We deliberately do NOT restrict posting_date
    #    at the SQL level beyond to_date - we need every entry before
    #    from_date too, in order to compute correct opening/running balances.
    conditions = "is_cancelled = 0 AND company = %(company)s AND posting_date <= %(to_date)s"
    if filters.get("item_code"):
        conditions += " AND item_code = %(item_code)s"
    if filters.get("warehouse"):
        filters["warehouses"] = tuple(get_warehouse_list(filters.get("warehouse")))
        conditions += " AND warehouse in %(warehouses)s"

    # 2. Sequential Ledger Query - authoritative chronological order used to
    #    build running balances, same ordering Frappe itself relies on.
    sles = frappe.db.sql(f"""
        SELECT
            company, item_code, warehouse, posting_date, posting_datetime, actual_qty,
            stock_value_difference, voucher_type, voucher_no, voucher_detail_no,
            creation, name
        FROM `tabStock Ledger Entry`
        WHERE {conditions}
        ORDER BY item_code, warehouse, posting_datetime ASC, creation ASC, name ASC
    """, filters, as_dict=1)

    if not sles:
        return []

    # 3. Walk the ledger per item+warehouse, carrying a running balance.
    #    Rows before from_date are collapsed into a single Opening row;
    #    rows within the period are emitted one per voucher (this is the
    #    detailed, voucher-by-voucher ledger, not a summary).
    running = {}            # key -> running {"qty", "value"} as we walk chronologically
    opening = {}             # key -> balance frozen at the from_date boundary
    voucher_lookup = {}      # (key, sle_name) -> voucher info, for per-row metadata

    rows_in_period = []

    for sle in sles:
        key = (sle.company, sle.item_code, sle.warehouse)
        bal = running.setdefault(key, {"qty": 0.0, "value": 0.0})

        qty = flt(sle.actual_qty)
        val_diff = flt(sle.stock_value_difference)

        bal["qty"] += qty
        bal["value"] += val_diff

        p_date = getdate(sle.posting_date)

        if p_date < from_date:
            # Keep advancing; last write before from_date is the opening balance.
            opening[key] = {"qty": bal["qty"], "value": bal["value"]}
            continue

        if p_date > to_date:
            continue

        rows_in_period.append({
            "key": key,
            "posting_date": sle.posting_date,
            "voucher_type": sle.voucher_type,
            "voucher_no": sle.voucher_no,
            "voucher_detail_no": sle.voucher_detail_no,
            "sle_name": sle.name,
            "qty": qty,
            "val_diff": val_diff,
            "balance_qty": bal["qty"],
            "balance_value": bal["value"],
        })
        voucher_lookup[(key, sle.name)] = {
            "voucher_type": sle.voucher_type,
            "voucher_no": sle.voucher_no,
            "voucher_detail_no": sle.voucher_detail_no,
        }

    if not rows_in_period:
        return []

    # 4. Fetch Plant/Segment metadata per voucher - every row needs its own,
    #    since this is a detailed ledger, not a "latest voucher" summary.
    metadata_map = get_metadata(voucher_lookup)

    # 5. Format rows, grouped by item+warehouse, each preceded by an Opening
    #    balance row (skippable via the "Hide Opening Row" filter).
    data = []
    seen_opening_for = set()

    for row in rows_in_period:
        key = row["key"]
        comp, item, wh = key

        if show_opening_row and key not in seen_opening_for:
            seen_opening_for.add(key)
            op = opening.get(key, {"qty": 0.0, "value": 0.0})
            op_qty = flt(op["qty"], qty_precision)
            op_val = flt(op["value"], currency_precision)
            data.append({
                "posting_date": from_date,
                "item_code": item,
                "warehouse": wh,
                "voucher_type": "",
                "voucher_no": _("Opening"),
                "plant": "",
                "segment": "",
                "in_qty": None,
                "out_qty": None,
                "balance_qty": op_qty,
                "in_value": None,
                "out_value": None,
                "balance_value": op_val,
                "valuation_rate": flt(op_val / op_qty, currency_precision) if op_qty else 0.0,
            })

        qty = row["qty"]
        val_diff = row["val_diff"]
        balance_qty = flt(row["balance_qty"], qty_precision)
        balance_value = flt(row["balance_value"], currency_precision)
        meta = metadata_map.get((key, row["sle_name"]), {"plant": "", "segment": ""})

        data.append({
            "posting_date": row["posting_date"],
            "item_code": item,
            "warehouse": wh,
            "voucher_type": row["voucher_type"],
            "voucher_no": row["voucher_no"],
            "plant": meta["plant"],
            "segment": meta["segment"],
            "in_qty": flt(qty, qty_precision) if qty > 0 else None,
            "out_qty": flt(abs(qty), qty_precision) if qty < 0 else None,
            "balance_qty": balance_qty,
            "in_value": flt(val_diff, currency_precision) if val_diff > 0 else None,
            "out_value": flt(abs(val_diff), currency_precision) if val_diff < 0 else None,
            "balance_value": balance_value,
            "valuation_rate": flt(balance_value / balance_qty, currency_precision) if balance_qty else 0.0,
        })

    return data


def get_metadata(voucher_lookup):
    """
    Fetches Plant (Branch) and Segment from Child Tables & Parent Header Tables,
    per individual voucher (keyed by (item/warehouse key, sle name)).
    Handles empty/NULL voucher_detail_no gracefully without database schema errors.
    """
    doctype_map = {
        'Stock Entry': ('tabStock Entry Detail', 'tabStock Entry', 'branch', 'segment'),
        'Purchase Receipt': ('tabPurchase Receipt Item', 'tabPurchase Receipt', 'branch', 'segment'),
        'Delivery Note': ('tabDelivery Note Item', 'tabDelivery Note', 'branch', 'segment'),
        'Sales Invoice': ('tabSales Invoice Item', 'tabSales Invoice', 'branch', 'segment'),
        'Purchase Invoice': ('tabPurchase Invoice Item', 'tabPurchase Invoice', 'branch', 'segment'),
        'POS Invoice': ('tabPOS Invoice Item', 'tabPOS Invoice', 'branch', 'segment'),
        'Subcontracting Receipt': ('tabSubcontracting Receipt Item', 'tabSubcontracting Receipt', 'branch', 'segment'),
        'Stock Reconciliation': ('tabStock Reconciliation Item', 'tabStock Reconciliation', 'branch', 'segment'),
    }

    by_type = {}
    for (key, sle_name), v in voucher_lookup.items():
        v_type = v["voucher_type"]
        if v_type in doctype_map:
            by_type.setdefault(v_type, []).append((key, sle_name, v["voucher_detail_no"], v["voucher_no"]))

    result = {}

    for v_type, items in by_type.items():
        child_table, parent_table, branch_col, segment_col = doctype_map[v_type]

        detail_ids = list(set([i[2] for i in items if i[2]]))
        parent_ids = list(set([i[3] for i in items if i[3]]))

        # A. Child Lookup by Detail Name
        detail_map = {}
        if detail_ids:
            d_data = frappe.db.sql(f"""
                SELECT name,
                       IFNULL(NULLIF(`{branch_col}`, ''), '') as branch,
                       IFNULL(NULLIF(`{segment_col}`, ''), '') as segment
                FROM `{child_table}`
                WHERE name IN %s
            """, (tuple(detail_ids),), as_dict=1)
            detail_map = {d["name"]: d for d in d_data}

        # B. Fallback Child Lookup by Parent + Item Code
        missing_items = [i for i in items if not i[2] or i[2] not in detail_map]
        parent_item_map = {}
        if missing_items:
            item_codes = list(set([i[0][1] for i in missing_items]))
            if parent_ids and item_codes:
                pi_data = frappe.db.sql(f"""
                    SELECT parent, item_code,
                           IFNULL(NULLIF(`{branch_col}`, ''), '') as branch,
                           IFNULL(NULLIF(`{segment_col}`, ''), '') as segment
                    FROM `{child_table}`
                    WHERE parent IN %s AND item_code IN %s
                """, (tuple(parent_ids), tuple(item_codes)), as_dict=1)
                for prow in pi_data:
                    parent_item_map[(prow["parent"], prow["item_code"])] = prow

        # C. Fallback Parent Header Lookup
        parent_header_map = {}
        if parent_ids:
            ph_data = frappe.db.sql(f"""
                SELECT name,
                       IFNULL(NULLIF(`{branch_col}`, ''), '') as branch,
                       IFNULL(NULLIF(`{segment_col}`, ''), '') as segment
                FROM `{parent_table}`
                WHERE name IN %s
            """, (tuple(parent_ids),), as_dict=1)
            parent_header_map = {d["name"]: d for d in ph_data}

        # Fallback Resolution Hierarchy: Child Detail -> Child Parent+Item -> Parent Header
        for key, sle_name, detail_no, parent_no in items:
            comp, item_code, warehouse = key

            c_match = detail_map.get(detail_no) or parent_item_map.get((parent_no, item_code)) or {}
            p_match = parent_header_map.get(parent_no) or {}

            plant = c_match.get("branch") or p_match.get("branch") or ""
            segment = c_match.get("segment") or p_match.get("segment") or ""

            result[(key, sle_name)] = {
                "plant": plant,
                "segment": segment
            }

    return result