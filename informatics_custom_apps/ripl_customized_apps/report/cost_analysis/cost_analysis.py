import frappe
from frappe import _
from frappe.utils import getdate, flt, add_days
from dateutil.relativedelta import relativedelta
from calendar import monthrange
from dataclasses import dataclass
from erpnext.stock.get_item_details import get_conversion_factor

def execute(filters=None):
    filters = filters or {}
    months = get_months_in_range(filters.get("from_date"), filters.get("to_date"))
    columns = get_columns(filters, months)
    data, target_production = get_data(filters, months)

    if not filters.get("show_quantitative_data", 0):
        data.insert(0, {
            "expense_category": f"{_('Target Production Qty (BL)')}: {frappe.utils.fmt_money(target_production, currency='')}",
            "is_target_row": 1,
        })

    return columns, data, None


def get_data(filters, months):
    company_val = filters.get("company")
    if not company_val:
        frappe.throw(_("Company is mandatory"))

    ctx = build_context(filters, months)

    if filters.get("show_quantitative_data", 0):
        return get_quant_data(filters, months, ctx), 0.0

    budget_by_account, target_production = get_budget_summary(
        ctx.company, ctx.branch, filters.get("from_date"), filters.get("to_date")
    )
    data = get_cost_data(
        filters, months, FIXED_CODES, ctx.monthly_prod_map, ctx.total_ytd_production,
        ctx.sales_qty_map, ctx.sales_val_map,
        filters.get("show_summary", 0), filters.get("hide_zero_amounts", 0),
        ctx.company, ctx.branch, ctx.segment, budget_by_account, target_production,
    )
    return data, target_production



def get_months_in_range(from_date, to_date):
    if not from_date or not to_date:
        return []

    start = getdate(from_date).replace(day=1)
    end = getdate(to_date).replace(day=1)

    months = []
    curr = start
    while curr <= end:
        months.append({"key": curr.strftime("%Y-%m"), "label": curr.strftime("%b %Y")})
        curr += relativedelta(months=1)
    return months


def zero_month_dict(months):
    return {m["key"]: 0.0 for m in months}


def fmt_num(value):
    """Format a number for the quant table's Data-type month/total columns."""
    return frappe.utils.fmt_money(flt(value), precision=2, currency="")


def is_by_product_section(section_name):
    name_l = (section_name or "").lower()
    return "by product" in name_l or "by-product" in name_l


def get_variance_color(actual, budget, reverse=False):
    if not budget:
        return ""
    pct = (abs(actual) / abs(budget)) * 100
    if pct > 110:
        return "green" if reverse else "red"
    if pct < 90:
        return "red" if reverse else "green"
    return ""


def get_stock_uom(item_code):
    return frappe.get_cached_value("Item", item_code, "stock_uom") or ""


def get_stock_to_target_factor(item_code, target_uom):
    stock_uom = get_stock_uom(item_code)
    if not stock_uom or target_uom == stock_uom:
        return 1
    factor = (get_conversion_factor(item_code, target_uom) or {}).get("conversion_factor") or 1
    return 1 / factor if factor else 1


def get_columns(filters, months):
    if filters.get("show_quantitative_data", 0):
        columns = [
            {"fieldname": "expense_category", "label": _("Description"), "fieldtype": "Data", "width": 300},
            {"fieldname": "gl_code", "label": _("Item Code / QTY"), "fieldtype": "Data", "width": 100, "align": "center"},
            {"fieldname": "uom", "label": _("UOM"), "fieldtype": "Data", "width": 80, "align": "center"},
        ]
        for m in months:
            columns.append({"fieldname": f"actual_{m['key']}", "label": _(m['label']),
                             "fieldtype": "Data", "width": 120, "align": "right"})
        columns.append({"fieldname": "total_actual", "label": _("Total"),
                         "fieldtype": "Data", "width": 130, "align": "right"})
        return columns

    columns = [
        {"fieldname": "expense_category", "label": _("Expense Category / Description"), "fieldtype": "Data", "width": 320},
        {"fieldname": "gl_code", "label": _("GL Code"), "fieldtype": "Data", "width": 100, "align": "center"},
        {"fieldname": "budget_amount", "label": _("Budget Amount (Rs.)"), "fieldtype": "Currency", "width": 150},
        {"fieldname": "budget_per_bl", "label": _("Budget Per BL (Rs/BL)"), "fieldtype": "Float", "precision": 2, "width": 140},
    ]
    for m in months:
        columns.extend([
            {"fieldname": f"actual_{m['key']}", "label": _(f"{m['label']} (Act)"), "fieldtype": "Currency", "width": 125},
            {"fieldname": f"per_bl_{m['key']}", "label": _(f"Per BL ({m['label']})"), "fieldtype": "Float", "precision": 2, "width": 115},
        ])
    columns.extend([
        {"fieldname": "total_actual", "label": _("YTD Actual"), "fieldtype": "Currency", "width": 140},
        {"fieldname": "total_per_bl", "label": _("YTD Per BL"), "fieldtype": "Float", "precision": 2, "width": 120},
    ])
    return columns



CONSUMPTION_ITEMS = [
    ("106444", "Maize", "maize_opening_balance", "maize_closing_balance"),
    ("106446", "DFG", "dfg_opening_balance", "dfg_closing_balance"),
    ("106448", "Rice", "fci_opening_balance", "fci_closing_balance"),
]
CONSUMPTION_UOM = "Quintal"
CONSUMPTION_ITEM_CODES = {label: item_code for item_code, label, _o, _c in CONSUMPTION_ITEMS}

DWGS_ITEMS = [
    ("100151", "DWGS from Maize"),
    ("100149", "DWGS from DFG"),
    ("100150", "DWGS from FCI"),
    ("100152", "DWGS from ???"),
]
DDGS_ITEMS = [
    ("100147", "DDGS from Maize"),
    ("100145", "DDGS from DFG"),
    ("100146", "DDGS from FCI"),
    ("100148", "DDGS from ???"),
    ("129749", "DDGS from ???"),
]

CRUDE_OIL_ITEM = "129946"
DDGS_TO_DWGS_FACTOR = 3.6
DWGS_STD_MAIZE_PCT = 0.0275
DWGS_STD_RICE_PCT = 0.016
CRUDE_OIL_STD_PRODUCTION = 0.6

ITEM_SALES_GL_ACCOUNTS = {
    "100114": "30124", "100112": "30125", "100113": "30126", "100122": "30129", "100120": "30128",
}

# (item_code, display name) - used for both the Production and Sales Qty/Amount/Price tables.
FIXED_PROD_ITEMS = [
    ("100114", "Production of Ethanol from Maize"),
    ("100112", "Production of Ethanol from DFG"),
    ("100113", "Production of Ethanol from FCI Rice"),
    ("100122", "Production of ENA from Maize"),
    ("100120", "Production of ENA from DFG"),
    ("100130", "Production of RS from Maize"),
    ("100128", "Production of RS from DFG"),
]
FIXED_SALES_ITEMS = [
    ("100114", "Ethanol from Maize"),
    ("100112", "Ethanol from DFG"),
    ("100113", "Ethanol from FCI"),
    ("100122", "ENA from Maize"),
    ("100120", "ENA from DFG"),
    ("100130", "RS from Maize"),
    ("100128", "RS from DFG"),
]
FIXED_CODES = tuple(code for code, _name in FIXED_PROD_ITEMS)




@dataclass
class ReportContext:
    company: str
    branch: str
    segment: str
    item_month_prod: dict   
    monthly_prod_map: dict   
    total_ytd_production: float
    sales_qty_map: dict       
    sales_val_map: dict     


def build_context(filters, months):
    company_val = filters.get("company")
    branch_val = filters.get("branch")
    segment_val = filters.get("segment")

    item_month_prod = get_production_qty_by_month(company_val, branch_val, segment_val, FIXED_CODES, filters)

    monthly_prod_map = zero_month_dict(months)
    for month_map in item_month_prod.values():
        for m_key, qty in month_map.items():
            if m_key in monthly_prod_map:
                monthly_prod_map[m_key] += qty
    total_ytd_production = sum(monthly_prod_map.values())

    sales_qty_map, sales_val_map = get_sales_qty_val_by_month(
        company_val, branch_val, segment_val, FIXED_CODES, filters
    )

    return ReportContext(
        company=company_val, branch=branch_val, segment=segment_val,
        item_month_prod=item_month_prod, monthly_prod_map=monthly_prod_map,
        total_ytd_production=total_ytd_production,
        sales_qty_map=sales_qty_map, sales_val_map=sales_val_map,
    )


def get_production_qty_by_month(company_val, branch_val, segment_val, item_codes, filters):
    """Qty received (Material Receipt stock entries) per item per month."""
    if not item_codes:
        return {}

    conditions = [
        "se.docstatus = 1", "se.purpose = 'Material Receipt'",
        "se.posting_date >= %(from_date)s", "se.posting_date <= %(to_date)s",
        "sed.item_code IN %(items)s", "se.company = %(company)s",
    ]
    values = {
        "from_date": filters.get("from_date"), "to_date": filters.get("to_date"),
        "items": tuple(item_codes), "company": company_val,
    }
    if branch_val:
        conditions.append("(se.branch = %(branch)s OR se.to_warehouse LIKE %(branch_pat)s)")
        values["branch"] = branch_val
        values["branch_pat"] = f"%{branch_val}%"
    if segment_val:
        conditions.append("se.segment = %(segment)s")
        values["segment"] = segment_val

    rows = frappe.db.sql(f"""
        SELECT sed.item_code, DATE_FORMAT(se.posting_date, '%%Y-%%m') AS month_key,
               SUM(sed.qty * sed.conversion_factor) AS qty
        FROM `tabStock Entry Detail` sed
        INNER JOIN `tabStock Entry` se ON se.name = sed.parent
        WHERE {" AND ".join(conditions)}
        GROUP BY sed.item_code, DATE_FORMAT(se.posting_date, '%%Y-%%m')
    """, values, as_dict=True)

    result = {}
    for r in rows:
        result.setdefault(r.item_code, {})[r.month_key] = flt(r.qty)
    return result


def get_sales_qty_val_by_month(company_val, branch_val, segment_val, item_codes, filters):
    """Qty + value delivered (Delivery Note) per item per month."""
    if not item_codes:
        return {}, {}

    conditions = [
        "dn.docstatus = 1", "dn.posting_date >= %(from_date)s", "dn.posting_date <= %(to_date)s",
        "dni.item_code IN %(items)s", "dn.company = %(company)s",
    ]
    values = {
        "from_date": filters.get("from_date"), "to_date": filters.get("to_date"),
        "items": tuple(item_codes), "company": company_val,
    }
    if branch_val:
        conditions.append("dn.branch = %(branch)s")
        values["branch"] = branch_val
    if segment_val:
        conditions.append("dn.segment = %(segment)s")
        values["segment"] = segment_val

    rows = frappe.db.sql(f"""
        SELECT dni.item_code, DATE_FORMAT(dn.posting_date, '%%Y-%%m') AS month_key,
               SUM(dni.stock_qty) AS qty, SUM(dni.base_amount) AS val
        FROM `tabDelivery Note Item` dni
        INNER JOIN `tabDelivery Note` dn ON dn.name = dni.parent
        WHERE {" AND ".join(conditions)}
        GROUP BY dni.item_code, DATE_FORMAT(dn.posting_date, '%%Y-%%m')
    """, values, as_dict=True)

    qty_map, val_map = {}, {}
    for r in rows:
        qty_map.setdefault(r.item_code, {})[r.month_key] = flt(r.qty)
        val_map.setdefault(r.item_code, {})[r.month_key] = flt(r.val)
    return qty_map, val_map


def get_sales_gl_amount_by_month(company_val, branch_val, segment_val, item_to_account, filters):
    """Sales value per item per month, taken from GL Entry against each item's sales account."""
    account_numbers = tuple(item_to_account.values())
    if not account_numbers:
        return {}

    accounts = frappe.db.sql("""
        SELECT name, account_number FROM `tabAccount`
        WHERE company = %(company)s AND is_group = 0 AND account_number IN %(codes)s
    """, {"company": company_val, "codes": account_numbers}, as_dict=True)

    account_to_names = {}
    for acc in accounts:
        account_to_names.setdefault(acc.account_number, []).append(acc.name)

    all_acc_names = [name for names in account_to_names.values() for name in names]
    if not all_acc_names:
        return {}

    conditions = [
        "docstatus = 1", "is_cancelled = 0", "company = %(company)s",
        "posting_date >= %(from_date)s", "posting_date <= %(to_date)s", "account IN %(accounts)s",
    ]
    values = {
        "company": company_val, "from_date": filters.get("from_date"), "to_date": filters.get("to_date"),
        "accounts": tuple(all_acc_names),
    }
    if branch_val:
        conditions.append("(section = %(branch)s OR branch = %(branch)s)")
        values["branch"] = branch_val
    if segment_val:
        conditions.append("segment = %(segment)s")
        values["segment"] = segment_val

    gl_entries = frappe.db.sql(f"""
        SELECT account, DATE_FORMAT(posting_date, '%%Y-%%m') AS month_key, SUM(credit - debit) AS amount
        FROM `tabGL Entry`
        WHERE {" AND ".join(conditions)}
        GROUP BY account, DATE_FORMAT(posting_date, '%%Y-%%m')
    """, values, as_dict=True)

    name_to_account_number = {name: num for num, names in account_to_names.items() for name in names}
    account_month_amount = {}
    for row in gl_entries:
        account_number = name_to_account_number.get(row.account)
        if not account_number:
            continue
        bucket = account_month_amount.setdefault(account_number, {})
        bucket[row.month_key] = bucket.get(row.month_key, 0.0) + flt(row.amount)

    return {item_code: account_month_amount.get(acc_num, {}) for item_code, acc_num in item_to_account.items()}




def get_month_boundaries(month_key, overall_from, overall_to):
    year, mon = map(int, month_key.split("-"))
    first_day = getdate(f"{year}-{mon:02d}-01")
    last_day = getdate(f"{year}-{mon:02d}-{monthrange(year, mon)[1]}")
    return max(first_day, getdate(overall_from)), min(last_day, getdate(overall_to))


def get_lab_parameter_data(companies, dates, plants=None):
    if not dates:
        return {}
    value_fields = sorted({field for _c, _l, opening, closing in CONSUMPTION_ITEMS for field in (opening, closing)})
    filters = {"company": ["in", companies], "date": ["in", list(dates)]}
    if plants:
        filters["plant"] = ["in", plants]

    rows = frappe.get_all("DMR Technical Lab Parameters", filters=filters, fields=["date"] + value_fields)

    lookup = {}
    for row in rows:
        for field in value_fields:
            key = (row["date"], field)
            lookup[key] = lookup.get(key, 0.0) + flt(row.get(field))
    return lookup


def get_issued_qty_for_range(companies, start_date, end_date, item_codes, plants=None, segments=None):
    if not item_codes:
        return {}

    from_dt = f"{start_date} 09:00:00"
    to_dt = f"{add_days(end_date, 1)} 09:00:00"
    conditions = [
        "se.docstatus = 1", "se.stock_entry_type = 'Material Issue'", "se.company in %(companies)s",
        "timestamp(se.posting_date, se.posting_time) >= %(from_dt)s",
        "timestamp(se.posting_date, se.posting_time) < %(to_dt)s", "sed.item_code in %(items)s",
    ]
    values = {"companies": companies, "from_dt": from_dt, "to_dt": to_dt, "items": item_codes}
    if plants:
        conditions.append("se.branch in %(plants)s")
        values["plants"] = plants
    if segments:
        conditions.append("sed.segment in %(segments)s")
        values["segments"] = segments

    rows = frappe.db.sql(f"""
        select sed.item_code, sum(sed.qty * sed.conversion_factor) as qty
        from `tabStock Entry` se
        inner join `tabStock Entry Detail` sed on se.name = sed.parent
        where {" and ".join(conditions)}
        group by sed.item_code
    """, values, as_dict=1)
    return {r.item_code: flt(r.qty) for r in rows}


def compute_consumption_data(company_val, branch_val, segment_val, months, filters):
    """
    Returns (issued_by_item, net_consumed_by_item, opening_by_item, closing_by_item).

    - issued_by_item:      material actually issued to production (Material Issue
                            stock entries). This is what's shown as "Raw Mat Consumed".
    - net_consumed_by_item: Opening WIP + Issued - Closing WIP. Used ONLY as the
                            Recovery % denominator, not for display.
    """
    companies = [company_val]
    plants = [branch_val] if branch_val else None
    segments = [segment_val] if segment_val else None

    overall_from = filters.get("from_date")
    overall_to = filters.get("to_date")
    month_bounds = {m["key"]: get_month_boundaries(m["key"], overall_from, overall_to) for m in months}

    needed_dates = set()
    for start, end in month_bounds.values():
        needed_dates.update([start, end])

    item_codes = [item_code for item_code, *_ in CONSUMPTION_ITEMS]
    lab_lookup = get_lab_parameter_data(companies, needed_dates, plants)
    issued_by_month = {
        m_key: get_issued_qty_for_range(companies, start, end, item_codes, plants, segments)
        for m_key, (start, end) in month_bounds.items()
    }

    issued_by_item, net_consumed_by_item, opening_by_item, closing_by_item = {}, {}, {}, {}

    for item_code, label, opening_field, closing_field in CONSUMPTION_ITEMS:
        factor = get_stock_to_target_factor(item_code, CONSUMPTION_UOM)
        issued_by_item[label] = {}
        net_consumed_by_item[label] = {}
        opening_by_item[label] = {}
        closing_by_item[label] = {}

        for m in months:
            m_key = m["key"]
            start, end = month_bounds[m_key]
            opening = lab_lookup.get((start, opening_field), 0.0) * factor
            closing = lab_lookup.get((end, closing_field), 0.0) * factor
            issued_qty = issued_by_month.get(m_key, {}).get(item_code, 0.0) * factor

            issued_by_item[label][m_key] = issued_qty
            net_consumed_by_item[label][m_key] = opening + issued_qty - closing
            opening_by_item[label][m_key] = opening
            closing_by_item[label][m_key] = closing

    return issued_by_item, net_consumed_by_item, opening_by_item, closing_by_item



def add_header_row(rows, title, header_label, months, unit_label):
    header = {"expense_category": title, "gl_code": header_label, "uom": "", "indent": 0, "is_quant_header": 1}
    for m in months:
        header[f"actual_{m['key']}"] = unit_label
    header["total_actual"] = unit_label
    rows.append(header)
    return header


def build_item_table(title, items, months, value_fn, header_label="Item Code",
                      unit_label="Qty", uom="", code_fn=None):
    """
    items:    list of (key, display_name)
    value_fn: (key, month_key) -> number
    uom:      a fixed string, or a callable key -> uom string (e.g. get_stock_uom)
    code_fn:  key -> gl_code shown in the "Item Code" column (defaults to the key itself)
    """
    rows = []
    add_header_row(rows, title, header_label, months, unit_label)

    totals = zero_month_dict(months)
    grand_total = 0.0

    for key, name in items:
        row = {
            "expense_category": name,
            "gl_code": code_fn(key) if code_fn else key,
            "uom": uom(key) if callable(uom) else uom,
            "indent": 1,
        }
        row_total = 0.0
        for m in months:
            m_key = m["key"]
            val = flt(value_fn(key, m_key))
            row[f"actual_{m_key}"] = fmt_num(val)
            row_total += val
            totals[m_key] += val
        row["total_actual"] = fmt_num(row_total)
        grand_total += row_total
        rows.append(row)

    tot_row = {"expense_category": "Total", "gl_code": "", "uom": uom if not callable(uom) else "",
               "indent": 0, "total_actual": fmt_num(grand_total), "is_quant_subtotal": 1}
    for m in months:
        tot_row[f"actual_{m['key']}"] = fmt_num(totals[m['key']])
    rows.append(tot_row)

    return rows, totals, grand_total


def build_ratio_table(title, rows_def, months, unit_label="%", header_label=""):
    def ratio(n, d):
        return round(n / d, 2) if d else 0.0

    rows = []
    add_header_row(rows, title, header_label, months, unit_label)

    grand_num_by_month = zero_month_dict(months)
    grand_den_by_month = zero_month_dict(months)
    grand_num_total = grand_den_total = 0.0

    for label, num_fn, den_fn in rows_def:
        row = {"expense_category": label, "gl_code": "", "uom": unit_label, "indent": 1}
        num_total = den_total = 0.0
        for m in months:
            m_key = m["key"]
            n, d = flt(num_fn(m_key)), flt(den_fn(m_key))
            row[f"actual_{m_key}"] = fmt_num(ratio(n, d))
            num_total += n
            den_total += d
            grand_num_by_month[m_key] += n
            grand_den_by_month[m_key] += d
        row["total_actual"] = fmt_num(ratio(num_total, den_total))
        grand_num_total += num_total
        grand_den_total += den_total
        rows.append(row)

    tot_row = {"expense_category": "Total", "gl_code": "", "uom": unit_label, "indent": 0,
               "total_actual": fmt_num(ratio(grand_num_total, grand_den_total)), "is_quant_subtotal": 1}
    for m in months:
        tot_row[f"actual_{m['key']}"] = fmt_num(ratio(grand_num_by_month[m['key']], grand_den_by_month[m['key']]))
    rows.append(tot_row)

    return rows


def add_blank_header(rows, title, months):
    """A section title row with no data of its own (used inside the DWGS/DDGS block)."""
    header = {"expense_category": title, "gl_code": "", "uom": "", "indent": 0, "is_quant_header": 1}
    for m in months:
        header[f"actual_{m['key']}"] = ""
    header["total_actual"] = ""
    rows.append(header)


def add_sum_row(rows, label, gl_code, uom, months, value_fn, indent=1, is_subtotal=False):
    """A row whose YTD total is the sum of its monthly values. Returns the YTD total."""
    row = {"expense_category": label, "gl_code": gl_code, "uom": uom, "indent": indent}
    if is_subtotal:
        row["is_quant_subtotal"] = 1
    total = 0.0
    for m in months:
        v = flt(value_fn(m["key"]))
        row[f"actual_{m['key']}"] = fmt_num(v)
        total += v
    row["total_actual"] = fmt_num(total)
    rows.append(row)
    return total


def add_ratio_row(rows, label, uom, months, num_by_month, den_by_month, num_total, den_total,
                   indent=1, is_subtotal=False, multiplier=1):
    """A row that shows num/den per month, with the YTD total computed from the YTD sums.
    Pass multiplier=100 to express the ratio as a percentage."""
    def ratio(n, d):
        return round((n / d) * multiplier, 2) if d else 0.0
    row = {"expense_category": label, "gl_code": "", "uom": uom, "indent": indent}
    if is_subtotal:
        row["is_quant_subtotal"] = 1
    for m in months:
        m_key = m["key"]
        row[f"actual_{m_key}"] = fmt_num(ratio(num_by_month[m_key], den_by_month[m_key]))
    row["total_actual"] = fmt_num(ratio(num_total, den_total))
    rows.append(row)


def build_recovery_section(item_month_prod, net_consumed_by_item, months):
    """Recovery % denominator is the NET consumption (Opening + Issued - Closing),
    not the plain issued qty shown in the "Raw Mat Consumed" table."""
    recovery_defs = [
        ("Maize", ["100122", "100114"], "Maize"),
        ("DFG", ["100120", "100112"], "DFG"),
        ("Rice", ["100113"], "Rice"),
    ]

    def make_num_fn(codes):
        return lambda mk: sum(flt(item_month_prod.get(c, {}).get(mk, 0.0)) for c in codes)

    def make_den_fn(label):
        return lambda mk: flt(net_consumed_by_item.get(label, {}).get(mk, 0.0))

    rows_def = [(label, make_num_fn(codes), make_den_fn(consume_label))
                for label, codes, consume_label in recovery_defs]

    return build_ratio_table("Recovery", rows_def, months, unit_label="%")


def build_dwgs_ddgs_section(months, item_month_prod, issued_by_item, filters,
                             company_val, branch_val, segment_val):
    byproduct_codes = [c for c, _n in DWGS_ITEMS] + [c for c, _n in DDGS_ITEMS] + [CRUDE_OIL_ITEM]
    byproduct_prod = get_production_qty_by_month(company_val, branch_val, segment_val, byproduct_codes, filters)

    def qty(code, mk):
        return flt(byproduct_prod.get(code, {}).get(mk, 0.0))

    m_keys = [m["key"] for m in months]

    # Each of the 3 DWGS items (and 3 DDGS items) can be stocked in a different UOM,
    # so convert every one to Quintal individually before summing them together.
    dwgs_factors = {c: get_stock_to_target_factor(c, CONSUMPTION_UOM) for c, _n in DWGS_ITEMS}
    ddgs_factors = {c: get_stock_to_target_factor(c, CONSUMPTION_UOM) for c, _n in DDGS_ITEMS}
    dwgs_qty = {mk: sum(qty(c, mk) * dwgs_factors[c] for c, _n in DWGS_ITEMS) for mk in m_keys}
    ddgs_qty = {mk: sum(qty(c, mk) * ddgs_factors[c] for c, _n in DDGS_ITEMS) for mk in m_keys}
    ddgs_equiv = {mk: ddgs_qty[mk] * DDGS_TO_DWGS_FACTOR for mk in m_keys}
    total_dwgs = {mk: dwgs_qty[mk] + ddgs_equiv[mk] for mk in m_keys}

    dwgs_codes = ", ".join(c for c, _n in DWGS_ITEMS)
    ddgs_codes = ", ".join(c for c, _n in DDGS_ITEMS)

    maize_qty = {mk: flt(item_month_prod.get("100114", {}).get(mk, 0.0)) for mk in m_keys}
    dfg_fci_qty = {mk: flt(item_month_prod.get("100112", {}).get(mk, 0.0))
                       + flt(item_month_prod.get("100113", {}).get(mk, 0.0)) for mk in m_keys}
    ethanol_qty = {mk: maize_qty[mk] + dfg_fci_qty[mk] for mk in m_keys}
    ethanol_ytd = sum(ethanol_qty.values())

    std_maize = {mk: maize_qty[mk] * DWGS_STD_MAIZE_PCT for mk in m_keys}
    std_rice = {mk: dfg_fci_qty[mk] * DWGS_STD_RICE_PCT for mk in m_keys}
    std_total = {mk: std_maize[mk] + std_rice[mk] for mk in m_keys}

    oil_qty = {mk: qty(CRUDE_OIL_ITEM, mk) for mk in m_keys}
    maize_consumed = {mk: flt(issued_by_item.get("Maize", {}).get(mk, 0.0)) for mk in m_keys}
    maize_consumed_ytd = sum(maize_consumed.values())

    rows = []

    add_blank_header(rows, "DWGS & DDGS Production", months)
    add_sum_row(rows, "DWGS produced", dwgs_codes, "Qtl", months, lambda mk: dwgs_qty[mk])
    add_sum_row(rows, "DDGS produced", ddgs_codes, "Qtl", months, lambda mk: ddgs_qty[mk])
    add_sum_row(rows, "DDGS Equivalent to DWGS", "", "Qtl", months, lambda mk: ddgs_equiv[mk])
    total_dwgs_ytd = add_sum_row(rows, "Total DWGS", "", "Qtl", months, lambda mk: total_dwgs[mk],
                                  indent=0, is_subtotal=True)
    # % of DWGS on Ethanol = Total DWGS (Quintal) / Ethanol production from Maize+DFG+FCI Rice (LTR),
    # expressed as a percentage.
    add_ratio_row(rows, "% of DWGS on Ethanol", "%", months, total_dwgs, ethanol_qty,
                  total_dwgs_ytd, ethanol_ytd, multiplier=100)

    add_blank_header(rows, "Standard Production of DWGS", months)
    std_maize_ytd = add_sum_row(rows, "On Maize @ 2.75%", "", "Qtl", months, lambda mk: std_maize[mk])
    std_rice_ytd = add_sum_row(rows, "On Rice @ 1.6%", "", "Qtl", months, lambda mk: std_rice[mk])
    std_total_ytd = add_sum_row(rows, "Total", "", "Qtl", months, lambda mk: std_total[mk],
                                 indent=0, is_subtotal=True)
    # Weighted Average = Ethanol production from Maize+DFG+FCI Rice (LTR) / (On Maize + On Rice).
    add_ratio_row(rows, "Weighted Average", "", months, ethanol_qty, std_total,
                  ethanol_ytd, std_total_ytd, indent=0, is_subtotal=True)

    add_blank_header(rows, "Crude Corn Oil", months)
    oil_prod_ytd = add_sum_row(rows, "Production of Crude Oil", CRUDE_OIL_ITEM, "Ltr", months, lambda mk: oil_qty[mk])
    add_ratio_row(rows, "% of Production on Maize Consumed", "%", months, oil_qty, maize_consumed,
                  oil_prod_ytd, maize_consumed_ytd)
    add_sum_row(rows, "Standard Production", "", "%", months, lambda mk: CRUDE_OIL_STD_PRODUCTION)
    # "Standard Production" is a fixed constant, not something that accumulates across
    # months - override the YTD total so it shows the constant itself, not a monthly sum.
    rows[-1]["total_actual"] = fmt_num(CRUDE_OIL_STD_PRODUCTION)

    return rows


def build_sales_price_table(items, months, qty_map, val_map,
                             month_qty_totals, month_val_totals, ytd_qty, ytd_val):
    """Per-litre selling price for each item, plus the weighted average across all of them."""
    def price(val, qty):
        return round(val / qty, 2) if qty else 0.0

    rows = []
    header = {"expense_category": "Sales Price", "gl_code": "Item Code", "uom": "", "indent": 0, "is_quant_header": 1}
    rows.append(header)

    for icode, iname in items:
        row = {"expense_category": iname, "gl_code": icode, "uom": get_stock_uom(icode), "indent": 1}
        item_ytd_qty = sum(qty_map.get(icode, {}).get(m["key"], 0.0) for m in months)
        item_ytd_val = sum(val_map.get(icode, {}).get(m["key"], 0.0) for m in months)
        for m in months:
            m_key = m["key"]
            m_qty = qty_map.get(icode, {}).get(m_key, 0.0)
            m_val = val_map.get(icode, {}).get(m_key, 0.0)
            row[f"actual_{m_key}"] = fmt_num(price(m_val, m_qty))
        row["total_actual"] = fmt_num(price(item_ytd_val, item_ytd_qty))
        rows.append(row)

    wgt_avg_row = {"expense_category": "WGT. AVG", "gl_code": "", "uom": "", "indent": 0,
                   "total_actual": fmt_num(price(ytd_val, ytd_qty)), "is_quant_subtotal": 1}
    for m in months:
        m_key = m["key"]
        wgt_avg_row[f"actual_{m_key}"] = fmt_num(price(month_val_totals[m_key], month_qty_totals[m_key]))
    rows.append(wgt_avg_row)

    for m in months:
        header[f"actual_{m['key']}"] = "Rs/LTR"
    header["total_actual"] = "Rs/LTR"

    return rows


def get_quant_data(filters, months, ctx):
    issued_by_item, net_consumed_by_item, opening_by_item, closing_by_item = compute_consumption_data(
        ctx.company, ctx.branch, ctx.segment, months, filters
    )

    data = []

    rows, *_ = build_item_table(
        "Production of Finished Goods", FIXED_PROD_ITEMS, months,
        value_fn=lambda code, mk: ctx.item_month_prod.get(code, {}).get(mk, 0.0),
        uom=get_stock_uom,
    )
    data.extend(rows)

    consumption_items = [(label, label) for label in ("Maize", "DFG", "Rice")]
    for title, source in (
        ("Raw Mat Consumed", issued_by_item),
        ("Opening WIP", opening_by_item),
        ("Closing WIP", closing_by_item),
    ):
        rows, *_ = build_item_table(
            title, consumption_items, months,
            value_fn=lambda label, mk, source=source: source.get(label, {}).get(mk, 0.0),
            header_label="ITEM CODE", uom=CONSUMPTION_UOM, code_fn=CONSUMPTION_ITEM_CODES.get,
        )
        data.extend(rows)

    data.extend(build_recovery_section(ctx.item_month_prod, net_consumed_by_item, months))
    data.extend(build_dwgs_ddgs_section(
        months, ctx.item_month_prod, issued_by_item, filters, ctx.company, ctx.branch, ctx.segment
    ))

    rows, sqty_totals, sqty_ytd = build_item_table(
        "Sales QTY", FIXED_SALES_ITEMS, months,
        value_fn=lambda code, mk: ctx.sales_qty_map.get(code, {}).get(mk, 0.0),
        uom=get_stock_uom,
    )
    data.extend(rows)

    sales_val_map = dict(ctx.sales_val_map)
    sales_val_map.update(get_sales_gl_amount_by_month(ctx.company, ctx.branch, ctx.segment, ITEM_SALES_GL_ACCOUNTS, filters))

    rows, sval_totals, sval_ytd = build_item_table(
        "Sales Amount", FIXED_SALES_ITEMS, months,
        value_fn=lambda code, mk: sales_val_map.get(code, {}).get(mk, 0.0),
        header_label="GL Code", unit_label="Amount in Rs.",
        code_fn=lambda code: ITEM_SALES_GL_ACCOUNTS.get(code, "--"),
    )
    data.extend(rows)

    data.extend(build_sales_price_table(
        FIXED_SALES_ITEMS, months, ctx.sales_qty_map, sales_val_map,
        sqty_totals, sval_totals, sqty_ytd, sval_ytd,
    ))

    return data


def get_grouping_doc():
    return frappe.get_single("Cost Analysis GL Grouping")


def get_section_definitions(grouping):
    """Returns (section_name -> [account_number, ...], [section_name in first-seen order])."""
    section_codes = {}
    section_seen_order = []

    for row in grouping.section_name:
        if row.section_name and row.section_name not in section_codes:
            section_codes[row.section_name] = []
            section_seen_order.append(row.section_name)

    for row in grouping.cost_analysis_gl:
        if not row.section_name or not row.account_number:
            continue
        section_codes.setdefault(row.section_name, [])
        if row.account_number not in section_codes[row.section_name]:
            section_codes[row.section_name].append(row.account_number)
        if row.section_name not in section_seen_order:
            section_seen_order.append(row.section_name)

    # drop sections with no GL codes at all - nothing to compute
    section_codes = {name: codes for name, codes in section_codes.items() if codes}
    section_seen_order = [name for name in section_seen_order if name in section_codes]
    return section_codes, section_seen_order


def get_total_row_definitions(grouping):
    """Returns row_label -> {components, row_style, reverse_color, is_cop_base}."""
    total_rows = {}
    total_row_seen_order = []

    for row in grouping.total_row:
        if not row.row_label:
            continue
        total_rows[row.row_label] = {
            "components": [], "row_style": row.row_style or "Total",
            "reverse_color": bool(row.reverse_variance_color), "is_cop_base": bool(row.is_cop_base),
        }
        total_row_seen_order.append(row.row_label)

    for row in grouping.total_row_components:
        if not row.row_label or row.row_label not in total_rows:
            continue
        if not row.component_name or not row.component_type:
            continue
        total_rows[row.row_label]["components"].append((row.component_type, row.component_name))

    return total_rows, total_row_seen_order


def get_row_sequence(grouping, section_codes, section_seen_order, total_rows, total_row_seen_order):
    """The single ordered list (Section / Total Row entries) that drives report + summary order."""
    sequence, seen = [], set()

    for row in grouping.row_sequence:
        if row.row_type == "Section" and row.row_name in section_codes and row.row_name not in seen:
            sequence.append(("Section", row.row_name))
            seen.add(row.row_name)
        elif row.row_type == "Total Row" and row.row_name in total_rows and row.row_name not in seen:
            sequence.append(("Total Row", row.row_name))
            seen.add(row.row_name)

    for name in section_seen_order:
        if name not in seen:
            sequence.append(("Section", name))
            seen.add(name)
    for label in total_row_seen_order:
        if label not in seen:
            sequence.append(("Total Row", label))
            seen.add(label)

    return sequence


def get_plants_for_company(company_val):
    if not company_val:
        return []
    return frappe.get_all("Branch", filters={"company": company_val}, pluck="name")


def get_target_plants(company_val, branch_val):
    return [branch_val] if branch_val else get_plants_for_company(company_val)


def get_budget_summary(company_val, branch_val, overall_from, overall_to):
    plants = get_target_plants(company_val, branch_val)
    if not plants or not overall_from or not overall_to:
        return {}, 0.0

    budget_docs = frappe.get_all(
        "Per BL Budget",
        filters={"plant": ["in", plants], "from": ["<=", overall_from], "to": [">=", overall_to]},
        fields=["name", "target_production"],
    )
    if not budget_docs:
        return {}, 0.0

    doc_names = [d.name for d in budget_docs]
    target_production = sum(flt(d.target_production) for d in budget_docs)

    budget_rows = frappe.get_all(
        "GL Budget", filters={"parent": ["in", doc_names], "parenttype": "Per BL Budget"},
        fields=["account_number", "budget_amount", "per_bl_budget"],
    )
    budget_by_account = {}
    for row in budget_rows:
        if not row.account_number:
            continue
        bucket = budget_by_account.setdefault(row.account_number, {"budget_amount": 0.0, "budget_per_bl": 0.0})
        bucket["budget_amount"] += flt(row.budget_amount)
        bucket["budget_per_bl"] += flt(row.per_bl_budget)

    return budget_by_account, target_production


def new_type_totals(months):
    return {"months": zero_month_dict(months), "total_actual": 0.0, "budget_amount": 0.0, "budget_per_bl": 0.0}


def build_summary_totals_row(label, totals_dict, months, monthly_prod_map, total_ytd_production,
                              flag_key, reverse_color=False):
    tot_act = totals_dict["total_actual"]
    budget_amount = totals_dict.get("budget_amount", 0.0)
    budget_per_bl = totals_dict.get("budget_per_bl", 0.0)
    total_per_bl = round(tot_act / total_ytd_production, 2) if total_ytd_production else 0.0

    row = {
        "expense_category": label, "gl_code": "", "indent": 0,
        "budget_amount": budget_amount, "budget_per_bl": budget_per_bl,
        "total_actual": tot_act, "total_per_bl": total_per_bl,
        "total_per_bl_color": get_variance_color(total_per_bl, budget_per_bl, reverse_color),
    }
    if flag_key:
        row[flag_key] = 1

    for m in months:
        m_key = m["key"]
        m_tot = totals_dict["months"][m_key]
        m_prod = monthly_prod_map.get(m_key, 0.0)
        m_per_bl = round(m_tot / m_prod, 2) if m_prod else 0.0
        row[f"actual_{m_key}"] = m_tot
        row[f"per_bl_{m_key}"] = m_per_bl
        row[f"per_bl_{m_key}_color"] = get_variance_color(m_per_bl, budget_per_bl, reverse_color)

    return row


ROW_STYLE_FLAG = {"Total": "is_total_row", "Subtotal": "is_subtotal", "Grand Total": "is_grand_total"}


def build_section_rows(section_name, gl_codes, code_data_cache, code_to_title, budget_by_account,
                        months, monthly_prod_map, total_ytd_production, hide_zero, show_summary):
    reverse_color = is_by_product_section(section_name)
    cat_totals = new_type_totals(months)
    category_rows = []

    for code in gl_codes:
        code_budget = budget_by_account.get(code, {})
        row_budget_amount = code_budget.get("budget_amount", 0.0)
        row_budget_per_bl = code_budget.get("budget_per_bl", 0.0)

        row_data = {}
        row_tot_act = 0.0
        has_nonzero = False
        c_data = code_data_cache.get(code, {})

        for m in months:
            m_key = m["key"]
            m_act = c_data.get(m_key, 0.0)
            m_prod = monthly_prod_map.get(m_key, 0.0)
            m_per_bl = round(m_act / m_prod, 2) if m_prod else 0.0

            if flt(m_act, 2) != 0:
                has_nonzero = True

            row_data[f"actual_{m_key}"] = m_act
            row_data[f"per_bl_{m_key}"] = m_per_bl
            row_data[f"per_bl_{m_key}_color"] = get_variance_color(m_per_bl, row_budget_per_bl, reverse_color)

            row_tot_act += m_act
            cat_totals["months"][m_key] += m_act

        row_tot_per_bl = round(row_tot_act / total_ytd_production, 2) if total_ytd_production else 0.0
        cat_totals["total_actual"] += row_tot_act
        cat_totals["budget_amount"] += row_budget_amount
        cat_totals["budget_per_bl"] += row_budget_per_bl

        if hide_zero and not has_nonzero:
            continue

        detail_row = {
            "expense_category": code_to_title.get(code, code), "gl_code": code, "indent": 1,
            "budget_amount": row_budget_amount, "budget_per_bl": row_budget_per_bl,
            "total_actual": row_tot_act, "total_per_bl": row_tot_per_bl,
            "total_per_bl_color": get_variance_color(row_tot_per_bl, row_budget_per_bl, reverse_color),
        }
        detail_row.update(row_data)
        category_rows.append(detail_row)

    if hide_zero and not category_rows:
        return [], cat_totals

    display_rows = []
    if show_summary:
        display_rows.append(build_summary_totals_row(
            section_name, cat_totals, months, monthly_prod_map, total_ytd_production, None, reverse_color
        ))
    else:
        display_rows.append({"expense_category": section_name, "gl_code": "", "indent": 0, "is_header": 1})
        display_rows.extend(category_rows)
        display_rows.append(build_summary_totals_row(
            "Sub Total", cat_totals, months, monthly_prod_map, total_ytd_production, "is_subtotal", reverse_color
        ))

    return display_rows, cat_totals


def get_cost_data(filters, months, FIXED_CODES, monthly_prod_map, total_ytd_production,
                   sales_qty_map, sales_val_map, show_summary, hide_zero,
                   company_val, branch_val, segment_val, budget_by_account=None, target_production=0.0):
    budget_by_account = budget_by_account or {}
    data = []

    prod_qty_row = {
        "expense_category": "TOTAL PRODUCTION QTY (BL)", "gl_code": "", "indent": 0,
        "total_actual": total_ytd_production, "total_per_bl": 1.0 if total_ytd_production else 0.0,
        "is_total_row": 1,
    }
    for m in months:
        m_key = m["key"]
        p_qty = monthly_prod_map.get(m_key, 0.0)
        prod_qty_row[f"actual_{m_key}"] = p_qty
        prod_qty_row[f"per_bl_{m_key}"] = 1.0 if p_qty else 0.0
    data.append(prod_qty_row)
    data.append({"expense_category": "", "gl_code": "", "indent": 0, "is_blank_row": 1})

    grouping = get_grouping_doc()
    section_codes, section_seen_order = get_section_definitions(grouping)
    total_row_defs, total_row_seen_order = get_total_row_definitions(grouping)
    sequence = get_row_sequence(grouping, section_codes, section_seen_order, total_row_defs, total_row_seen_order)

    all_codes = set()
    for codes in section_codes.values():
        all_codes.update(codes)

    accounts = []
    if all_codes:
        accounts = frappe.db.sql("""
            SELECT name, account_number, account_name FROM `tabAccount`
            WHERE company = %(company)s AND is_group = 0 AND account_number IN %(codes)s
        """, {"company": company_val, "codes": tuple(all_codes)}, as_dict=True)

    code_to_names, code_to_title = {}, {}
    for acc in accounts:
        code_to_names.setdefault(acc.account_number, []).append(acc.name)
        code_to_title.setdefault(acc.account_number, acc.account_name)

    gl_conditions = [
        "docstatus = 1", "is_cancelled = 0", "company = %(company)s",
        "posting_date >= %(from_date)s", "posting_date <= %(to_date)s",
    ]
    gl_args = {"company": company_val, "from_date": filters.get("from_date"), "to_date": filters.get("to_date")}
    if branch_val:
        gl_conditions.append("(section = %(branch)s OR branch = %(branch)s)")
        gl_args["branch"] = branch_val
    if segment_val:
        gl_conditions.append("segment = %(segment)s")
        gl_args["segment"] = segment_val

    gl_entries = frappe.db.sql(f"""
        SELECT account, DATE_FORMAT(posting_date, '%%Y-%%m') AS month_key, SUM(debit - credit) AS actual_expense
        FROM `tabGL Entry`
        WHERE {" AND ".join(gl_conditions)}
        GROUP BY account, DATE_FORMAT(posting_date, '%%Y-%%m')
    """, gl_args, as_dict=True)

    gl_expense_map = {}
    for gle in gl_entries:
        gl_expense_map.setdefault(gle.account, {})[gle.month_key] = gle.actual_expense

    code_data_cache = {
        code: {m["key"]: sum(gl_expense_map.get(name, {}).get(m["key"], 0.0) for name in code_to_names.get(code, []))
               for m in months}
        for code in all_codes
    }

    computed_totals = {}
    cop_base_row = None

    for row_type, row_name in sequence:
        if row_type == "Section":
            display_rows, cat_totals = build_section_rows(
                row_name, section_codes.get(row_name, []), code_data_cache, code_to_title,
                budget_by_account, months, monthly_prod_map, total_ytd_production, hide_zero, show_summary,
            )
            data.extend(display_rows)
            computed_totals[row_name] = cat_totals

        elif row_type == "Total Row":
            total_def = total_row_defs[row_name]
            agg = new_type_totals(months)
            for _comp_type, comp_name in total_def["components"]:
                src = computed_totals.get(comp_name)
                if not src:
                    continue
                for m in months:
                    agg["months"][m["key"]] += src["months"][m["key"]]
                agg["total_actual"] += src["total_actual"]
                agg["budget_amount"] += src.get("budget_amount", 0.0)
                agg["budget_per_bl"] += src.get("budget_per_bl", 0.0)

            flag_key = ROW_STYLE_FLAG.get(total_def["row_style"], "is_total_row")
            total_row_out = build_summary_totals_row(
                row_name, agg, months, monthly_prod_map, total_ytd_production, flag_key, total_def["reverse_color"]
            )
            data.append(total_row_out)
            computed_totals[row_name] = agg
            if total_def["is_cop_base"]:
                cop_base_row = total_row_out

    if cop_base_row is None:
        for row_type, row_name in reversed(sequence):
            if row_type == "Total Row" and row_name in computed_totals:
                cop_base_row = build_summary_totals_row(
                    row_name, computed_totals[row_name], months, monthly_prod_map, total_ytd_production, "is_total_row"
                )
                break

    if cop_base_row is None:
        all_sections_agg = new_type_totals(months)
        has_any_section = False
        for row_type, row_name in sequence:
            if row_type == "Section" and row_name in computed_totals:
                has_any_section = True
                src = computed_totals[row_name]
                for m in months:
                    all_sections_agg["months"][m["key"]] += src["months"][m["key"]]
                all_sections_agg["total_actual"] += src["total_actual"]
                all_sections_agg["budget_amount"] += src.get("budget_amount", 0.0)
                all_sections_agg["budget_per_bl"] += src.get("budget_per_bl", 0.0)
        if has_any_section:
            cop_base_row = build_summary_totals_row(
                "TOTAL COST", all_sections_agg, months, monthly_prod_map, total_ytd_production, "is_total_row"
            )

    if cop_base_row is not None:
        data.extend(build_profitability_section(
            months, FIXED_CODES, monthly_prod_map, total_ytd_production, sales_qty_map, sales_val_map, cop_base_row
        ))

    return data


PER_BL_PROFIT_ROWS = {
    "Wgt Avg Selling Price (Per Litre)", "Wgt Avg COP (Per Litre)", "Net Profit / Loss (Per Litre)",
}


def build_profitability_section(months, FIXED_CODES, monthly_prod_map, total_ytd_production,
                                 sales_qty_map, sales_val_map, grand_total_row):
    monthly_snapshot = {}
    for m in months:
        m_key = m["key"]
        m_tot_qty = sum(sales_qty_map.get(c, {}).get(m_key, 0.0) for c in FIXED_CODES)
        m_tot_val = sum(sales_val_map.get(c, {}).get(m_key, 0.0) for c in FIXED_CODES)
        m_selling_price = round(m_tot_val / m_tot_qty, 2) if m_tot_qty else 0.0
        m_cop = grand_total_row.get(f"per_bl_{m_key}", 0.0)
        monthly_snapshot[m_key] = {
            "qty": m_tot_qty, "val": m_tot_val, "selling_price": m_selling_price, "cop": m_cop,
            "net_profit": round(m_selling_price - m_cop, 2), "prod": monthly_prod_map.get(m_key, 0.0),
        }

    tot_sales_qty = sum(v["qty"] for v in monthly_snapshot.values())
    tot_sales_val = sum(v["val"] for v in monthly_snapshot.values())
    wgt_selling_price = round(tot_sales_val / tot_sales_qty, 2) if tot_sales_qty else 0.0
    wgt_cop = grand_total_row["total_per_bl"]
    net_profit_per_litre = round(wgt_selling_price - wgt_cop, 2)

    prof_rows = [
        {"name": "Wgt Avg Selling Price (Per Litre)", "val": wgt_selling_price},
        {"name": "Wgt Avg COP (Per Litre)", "val": wgt_cop},
        {"name": "Net Profit / Loss (Per Litre)", "val": net_profit_per_litre},
        {"name": "Profit / Loss in Value (as Per Production)", "val": round(net_profit_per_litre * total_ytd_production, 2)},
        {"name": "Profit / Loss Value as Per Sales", "val": round(net_profit_per_litre * tot_sales_qty, 2)},
    ]

    data = [
        {"expense_category": "", "gl_code": "", "indent": 0},
        {"expense_category": "Profitability", "gl_code": "", "indent": 0, "is_header": 1},
    ]

    value_by_name = {
        "Wgt Avg Selling Price (Per Litre)": lambda snap: snap["selling_price"],
        "Wgt Avg COP (Per Litre)": lambda snap: snap["cop"],
        "Net Profit / Loss (Per Litre)": lambda snap: snap["net_profit"],
        "Profit / Loss in Value (as Per Production)": lambda snap: round(snap["net_profit"] * snap["prod"], 2),
        "Profit / Loss Value as Per Sales": lambda snap: round(snap["net_profit"] * snap["qty"], 2),
    }

    for pr in prof_rows:
        is_per_bl = pr["name"] in PER_BL_PROFIT_ROWS
        p_row = {
            "expense_category": pr["name"], "gl_code": "", "indent": 1,
            "total_actual": 0.0 if is_per_bl else pr["val"],
            "total_per_bl": pr["val"] if is_per_bl else 0.0,
            "is_subtotal": 1 if "Net Profit" in pr["name"] or "Sales" in pr["name"] else 0,
        }
        for m in months:
            m_key = m["key"]
            val = value_by_name[pr["name"]](monthly_snapshot[m_key])
            if is_per_bl:
                p_row[f"actual_{m_key}"] = 0.0
                p_row[f"per_bl_{m_key}"] = val
            else:
                p_row[f"actual_{m_key}"] = val
                p_row[f"per_bl_{m_key}"] = 0.0
        data.append(p_row)

    return data