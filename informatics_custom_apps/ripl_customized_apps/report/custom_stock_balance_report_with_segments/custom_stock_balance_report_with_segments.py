import frappe
from frappe import _
from frappe.utils import flt, getdate, cint


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
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 140},
        {"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 180},
        {"label": _("Plant"), "fieldname": "plant", "fieldtype": "Link", "options": "Branch", "width": 140},
        {"label": _("Segment"), "fieldname": "segment", "fieldtype": "Data", "width": 140},
        {"label": _("Opening Qty"), "fieldname": "opening_qty", "fieldtype": "Float", "width": 120},
        {"label": _("In Qty"), "fieldname": "in_qty", "fieldtype": "Float", "width": 120},
        {"label": _("Out Qty"), "fieldname": "out_qty", "fieldtype": "Float", "width": 120},
        {"label": _("Balance Qty"), "fieldname": "balance_qty", "fieldtype": "Float", "width": 120},
        {"label": _("Opening Value"), "fieldname": "opening_value", "fieldtype": "Currency", "width": 140},
        {"label": _("In Value"), "fieldname": "in_value", "fieldtype": "Currency", "width": 140},
        {"label": _("Out Value"), "fieldname": "out_value", "fieldtype": "Currency", "width": 140},
        {"label": _("Balance Value"), "fieldname": "balance_value", "fieldtype": "Currency", "width": 140},
        {"label": _("Valuation Rate"), "fieldname": "valuation_rate", "fieldtype": "Currency", "width": 130},
    ]


def get_data(filters):
    from_date = getdate(filters.get("from_date"))
    to_date = getdate(filters.get("to_date"))
    currency_precision = cint(frappe.db.get_default("currency_precision")) or 2
    qty_precision = cint(frappe.db.get_default("float_precision")) or 6

    # 1. Dynamic Query Filters
    conditions = "is_cancelled = 0 AND company = %(company)s AND posting_date <= %(to_date)s"
    if filters.get("item_code"):
        conditions += " AND item_code = %(item_code)s"
    if filters.get("warehouse"):
        conditions += " AND warehouse = %(warehouse)s"

    # 2. Sequential Ledger Query
    sles = frappe.db.sql(f"""
        SELECT
            company, item_code, warehouse, posting_date, actual_qty, stock_value_difference,
            voucher_type, voucher_no, voucher_detail_no, creation, name
        FROM `tabStock Ledger Entry`
        WHERE {conditions}
        ORDER BY item_code, warehouse, posting_datetime ASC, creation ASC, name ASC
    """, filters, as_dict=1)

    if not sles:
        return []

    # 3. Process Ledger Records
    summary = {}
    latest_vouchers = {}

    for sle in sles:
        key = (sle.company, sle.item_code, sle.warehouse)
        if key not in summary:
            summary[key] = {
                "opening_qty": 0.0, "in_qty": 0.0, "out_qty": 0.0, "balance_qty": 0.0,
                "opening_value": 0.0, "in_value": 0.0, "out_value": 0.0, "balance_value": 0.0,
            }

        p_date = getdate(sle.posting_date)
        qty = flt(sle.actual_qty)
        val_diff = flt(sle.stock_value_difference)

        # Period Totals
        if p_date < from_date:
            summary[key]["opening_qty"] += qty
            summary[key]["opening_value"] += val_diff
        elif from_date <= p_date <= to_date:
            if qty > 0:
                summary[key]["in_qty"] += qty
            elif qty < 0:
                summary[key]["out_qty"] += abs(qty)

            # NOTE: value can move even when qty is 0 (e.g. stock revaluation),
            # so this is intentionally not nested under the qty check.
            if val_diff > 0:
                summary[key]["in_value"] += val_diff
            elif val_diff < 0:
                summary[key]["out_value"] += abs(val_diff)

        # Balance Totals
        summary[key]["balance_qty"] += qty
        summary[key]["balance_value"] += val_diff

        # Track Newest Voucher for Plant/Segment
        latest_vouchers[key] = {
            "voucher_type": sle.voucher_type,
            "voucher_no": sle.voucher_no,
            "voucher_detail_no": sle.voucher_detail_no
        }

    # 4. Fetch Metadata without Table Errors
    metadata_map = get_latest_metadata(latest_vouchers)

    # 5. Format Response
    data = []
    for (comp, item, wh), row in summary.items():
        opening_qty = flt(row["opening_qty"], qty_precision)
        in_qty = flt(row["in_qty"], qty_precision)
        out_qty = flt(row["out_qty"], qty_precision)
        balance_qty = flt(row["balance_qty"], qty_precision)
        opening_value = flt(row["opening_value"], currency_precision)
        in_value = flt(row["in_value"], currency_precision)
        out_value = flt(row["out_value"], currency_precision)
        balance_value = flt(row["balance_value"], currency_precision)

        has_qty_activity = opening_qty or in_qty or out_qty or balance_qty
        has_value_activity = opening_value or in_value or out_value or balance_value
        if not (has_qty_activity or has_value_activity):
            continue

        # Match ERPNext's Stock Balance report: hide rows with zero closing
        # balance qty by default (even if there was value-only movement),
        # unless the user explicitly asks to include them.
        if not balance_qty and not filters.get("include_zero_stock_items"):
            continue

        val_rate = (balance_value / balance_qty) if balance_qty else 0.0
        meta = metadata_map.get((comp, item, wh), {"plant": "", "segment": ""})

        data.append({
            "company": comp,
            "item_code": item,
            "warehouse": wh,
            "plant": meta["plant"],
            "segment": meta["segment"],
            "opening_qty": opening_qty,
            "in_qty": in_qty,
            "out_qty": out_qty,
            "balance_qty": balance_qty,
            "opening_value": opening_value,
            "in_value": in_value,
            "out_value": out_value,
            "balance_value": balance_value,
            "valuation_rate": flt(val_rate, currency_precision),
        })

    data.sort(key=lambda x: (x["company"], x["item_code"], x["warehouse"]))
    return data


def get_latest_metadata(latest_vouchers):
    """
    Fetches Plant (Branch) and Segment from Child Tables & Parent Header Tables.
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
    for key, v in latest_vouchers.items():
        v_type = v["voucher_type"]
        if v_type in doctype_map:
            by_type.setdefault(v_type, []).append((key, v["voucher_detail_no"], v["voucher_no"]))

    result = {}

    for v_type, items in by_type.items():
        child_table, parent_table, branch_col, segment_col = doctype_map[v_type]

        detail_ids = [i[1] for i in items if i[1]]
        parent_ids = list(set([i[2] for i in items if i[2]]))

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

        # B. Fallback Child Lookup by Parent + Item Code (if detail_id missing)
        missing_items = [i for i in items if not i[1] or i[1] not in detail_map]
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
                for row in pi_data:
                    parent_item_map[(row["parent"], row["item_code"])] = row

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
        for key, detail_no, parent_no in items:
            comp, item_code, warehouse = key

            c_match = detail_map.get(detail_no) or parent_item_map.get((parent_no, item_code)) or {}
            p_match = parent_header_map.get(parent_no) or {}

            plant = c_match.get("branch") or p_match.get("branch") or ""
            segment = c_match.get("segment") or p_match.get("segment") or ""

            result[key] = {
                "plant": plant,
                "segment": segment
            }

    return result