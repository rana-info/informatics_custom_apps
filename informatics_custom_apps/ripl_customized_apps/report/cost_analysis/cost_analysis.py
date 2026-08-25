import frappe
from frappe import _
from frappe.utils import getdate, flt, add_days
from dateutil.relativedelta import relativedelta
from calendar import monthrange
from erpnext.stock.get_item_details import get_conversion_factor


def execute(filters=None):
    if not filters:
        filters = {}
    months = get_months_in_range(filters.get("from_date"), filters.get("to_date"))
    columns = get_columns(filters, months)
    data, target_production = get_data(filters, months)
    message = None
    if not filters.get("show_quantitative_data", 0):
        message = f"<b style='color:#0369a1;'>{_('Target Production Qty (BL)')}: {frappe.utils.fmt_money(target_production, currency='')}</b>"
    return columns, data, message


def get_months_in_range(from_date, to_date):
    if not from_date or not to_date:
        return []

    start = getdate(from_date).replace(day=1)
    end = getdate(to_date).replace(day=1)

    months = []
    curr = start
    while curr <= end:
        months.append({
            "key": curr.strftime("%Y-%m"),
            "label": curr.strftime("%b %Y")
        })
        curr += relativedelta(months=1)

    return months


def zero_month_dict(months):
    return {m["key"]: 0.0 for m in months}


def get_columns(filters, months):
    show_quant = filters.get("show_quantitative_data", 0)

    if show_quant:
        columns = [
            {"fieldname": "expense_category", "label": _("Description"), "fieldtype": "Data", "width": 300},
            {"fieldname": "gl_code", "label": _("Item Code / QTY"), "fieldtype": "Data", "width": 100, "align": "center"},
            {"fieldname": "uom", "label": _("UOM"), "fieldtype": "Data", "width": 80, "align": "center"}
        ]
        for m in months:
            columns.append({
                "fieldname": f"actual_{m['key']}",
                "label": _(m['label']),
                "fieldtype": "Float",
                "precision": 2,
                "width": 120
            })
        columns.append({
            "fieldname": "total_actual",
            "label": _("Total"),
            "fieldtype": "Float",
            "precision": 2,
            "width": 130
        })
        return columns

    columns = [
        {"fieldname": "expense_category", "label": _("Expense Category / Description"), "fieldtype": "Data", "width": 320},
        {"fieldname": "gl_code", "label": _("GL Code"), "fieldtype": "Data", "width": 100, "align": "center"},
        {"fieldname": "budget_amount", "label": _("Budget Amount"), "fieldtype": "Currency", "width": 130},
        {"fieldname": "budget_per_bl", "label": _("Budget Per BL"), "fieldtype": "Float", "precision": 2, "width": 120}
    ]

    for m in months:
        columns.extend([
            {"fieldname": f"actual_{m['key']}", "label": _(f"{m['label']} (Act)"), "fieldtype": "Currency", "width": 125},
            {"fieldname": f"per_bl_{m['key']}", "label": _(f"Per BL ({m['label']})"), "fieldtype": "Float", "precision": 2, "width": 115}
        ])

    columns.extend([
        {"fieldname": "total_actual", "label": _("YTD Actual"), "fieldtype": "Currency", "width": 140},
        {"fieldname": "total_per_bl", "label": _("YTD Per BL"), "fieldtype": "Float", "precision": 2, "width": 120}
    ])

    return columns


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
            "components": [],
            "row_style": row.row_style or "Total",
            "reverse_color": bool(row.reverse_variance_color),
            "is_cop_base": bool(row.is_cop_base)
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
    sequence = []
    seen = set()

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


CONSUMPTION_ITEMS = [
    ("106444", "Maize", "maize_opening_balance", "maize_closing_balance"),
    ("100474", "DFG", "dfg_opening_balance", "dfg_closing_balance"),
    ("106448", "Rice", "fci_opening_balance", "fci_closing_balance"),
]

CONSUMPTION_UOM = "Quintal"


def get_stock_uom(item_code):
    return frappe.get_cached_value("Item", item_code, "stock_uom") or ""


def get_stock_to_target_factor(item_code, target_uom):
    stock_uom = get_stock_uom(item_code)
    if not stock_uom or target_uom == stock_uom:
        return 1
    factor = (get_conversion_factor(item_code, target_uom) or {}).get("conversion_factor") or 1
    return 1 / factor if factor else 1


def get_month_boundaries(month_key, overall_from, overall_to):
    year, mon = map(int, month_key.split("-"))
    first_day = getdate(f"{year}-{mon:02d}-01")
    last_day = getdate(f"{year}-{mon:02d}-{monthrange(year, mon)[1]}")
    start = max(first_day, getdate(overall_from))
    end = min(last_day, getdate(overall_to))
    return start, end


def get_lab_parameter_data(companies, dates, plants=None):
    if not dates:
        return {}

    value_fields = sorted({field for _, _, opening, closing in CONSUMPTION_ITEMS for field in (opening, closing)})

    filters = {"company": ["in", companies], "date": ["in", list(dates)]}
    if plants:
        filters["plant"] = ["in", plants]

    rows = frappe.get_all(
        "DMR Technical Lab Parameters",
        filters=filters,
        fields=["date"] + value_fields
    )

    lookup = {}
    for row in rows:
        row_date = row["date"]
        for field in value_fields:
            key = (row_date, field)
            lookup[key] = lookup.get(key, 0.0) + flt(row.get(field))

    return lookup


def get_issued_qty_by_month(companies, overall_start, overall_end, item_codes, plants=None, segments=None):
    if not item_codes:
        return {}

    from_dt = f"{overall_start} 06:00:00"
    to_dt = f"{add_days(overall_end, 1)} 06:00:00"

    conditions = [
        "se.docstatus = 1",
        "se.stock_entry_type = 'Material Issue'",
        "se.company in %(companies)s",
        "timestamp(se.posting_date, se.posting_time) >= %(from_dt)s",
        "timestamp(se.posting_date, se.posting_time) < %(to_dt)s",
        "sed.item_code in %(items)s"
    ]
    values = {"companies": companies, "from_dt": from_dt, "to_dt": to_dt, "items": item_codes}

    if plants:
        conditions.append("se.branch in %(plants)s")
        values["plants"] = plants
    if segments:
        conditions.append("sed.segment in %(segments)s")
        values["segments"] = segments

    rows = frappe.db.sql(f"""
        select
            sed.item_code,
            date_format(date_sub(timestamp(se.posting_date, se.posting_time), interval 6 hour), '%%Y-%%m') as month_key,
            sum(sed.qty * sed.conversion_factor) as qty
        from `tabStock Entry` se
        inner join `tabStock Entry Detail` sed on se.name = sed.parent
        where {" and ".join(conditions)}
        group by sed.item_code, month_key
    """, values, as_dict=1)

    return {(r.item_code, r.month_key): flt(r.qty) for r in rows}


def compute_consumption_data(company_val, branch_val, segment_val, months, filters):
    companies = [company_val]
    plants = [branch_val] if branch_val else None
    segments = [segment_val] if segment_val else None

    overall_from = filters.get("from_date")
    overall_to = filters.get("to_date")

    month_bounds = {m["key"]: get_month_boundaries(m["key"], overall_from, overall_to) for m in months}

    needed_dates = set()
    for start, end in month_bounds.values():
        needed_dates.add(start)
        needed_dates.add(end)

    item_codes = [item_code for item_code, *_ in CONSUMPTION_ITEMS]

    lab_lookup = get_lab_parameter_data(companies, needed_dates, plants)

    overall_start = min(s for s, _ in month_bounds.values())
    overall_end = max(e for _, e in month_bounds.values())
    issued_lookup = get_issued_qty_by_month(companies, overall_start, overall_end, item_codes, plants, segments)

    consumed_by_item = {}
    opening_by_item = {}
    closing_by_item = {}

    for item_code, label, opening_field, closing_field in CONSUMPTION_ITEMS:
        factor = get_stock_to_target_factor(item_code, CONSUMPTION_UOM)
        consumed_by_item[label] = {}
        opening_by_item[label] = {}
        closing_by_item[label] = {}

        for m in months:
            m_key = m["key"]
            start, end = month_bounds[m_key]

            opening = lab_lookup.get((start, opening_field), 0.0) * factor
            closing = lab_lookup.get((end, closing_field), 0.0) * factor
            issued_qty = issued_lookup.get((item_code, m_key), 0.0) * factor

            net_consumed = opening + issued_qty - closing

            consumed_by_item[label][m_key] = net_consumed
            opening_by_item[label][m_key] = opening
            closing_by_item[label][m_key] = closing

    return consumed_by_item, opening_by_item, closing_by_item


def build_quant_section_from_data(title, items, data_by_item, months, uom=CONSUMPTION_UOM):
    rows = [{"expense_category": title, "gl_code": "QTY", "uom": "", "indent": 0, "is_quant_header": 1}]
    totals = zero_month_dict(months)
    grand_total = 0.0

    for label in items:
        row = {"expense_category": label, "gl_code": "", "uom": uom, "indent": 1}
        row_total = 0.0
        for m in months:
            m_key = m["key"]
            val = flt(data_by_item.get(label, {}).get(m_key, 0.0))
            row[f"actual_{m_key}"] = val
            row_total += val
            totals[m_key] += val
        row["total_actual"] = row_total
        grand_total += row_total
        rows.append(row)

    tot_row = {"expense_category": "Total", "gl_code": "", "uom": uom, "indent": 1, "total_actual": grand_total, "is_quant_subtotal": 1}
    for m in months:
        tot_row[f"actual_{m['key']}"] = totals[m['key']]
    rows.append(tot_row)

    return rows


def build_recovery_section(item_month_prod, consumed_by_item, months):
    rows = [{"expense_category": "Recovery", "gl_code": "QTY", "uom": "%", "indent": 0, "is_quant_header": 1}]

    def div(a, b):
        return round(a / b, 2) if b else 0.0

    recovery_defs = [
        ("Maize", ["100122", "100114"], "Maize"),
        ("DFG", ["100120", "100112"], "DFG"),
        ("Rice", ["100113"], "Rice"),
    ]

    totals_num = zero_month_dict(months)
    totals_den = zero_month_dict(months)
    grand_num = 0.0
    grand_den = 0.0

    for label, prod_codes, consume_label in recovery_defs:
        row = {"expense_category": label, "gl_code": "", "uom": "%", "indent": 1}
        row_num_total = 0.0
        row_den_total = 0.0
        for m in months:
            m_key = m["key"]
            num = sum(flt(item_month_prod.get(code, {}).get(m_key, 0.0)) for code in prod_codes)
            den = flt(consumed_by_item.get(consume_label, {}).get(m_key, 0.0))
            row[f"actual_{m_key}"] = div(num, den)
            row_num_total += num
            row_den_total += den
            totals_num[m_key] += num
            totals_den[m_key] += den
        row["total_actual"] = div(row_num_total, row_den_total)
        grand_num += row_num_total
        grand_den += row_den_total
        rows.append(row)

    tot_row = {"expense_category": "Total", "gl_code": "", "uom": "%", "indent": 1, "total_actual": div(grand_num, grand_den), "is_quant_subtotal": 1}
    for m in months:
        tot_row[f"actual_{m['key']}"] = div(totals_num[m['key']], totals_den[m['key']])
    rows.append(tot_row)

    return rows


def get_plants_for_company(company_val):
    if not company_val:
        return []
    return frappe.get_all("Branch", filters={"company": company_val}, pluck="name")


def get_target_plants(company_val, branch_val):
    if branch_val:
        return [branch_val]
    return get_plants_for_company(company_val)


def get_budget_summary(company_val, branch_val, overall_from, overall_to):
    plants = get_target_plants(company_val, branch_val)
    if not plants or not overall_from or not overall_to:
        return {}, 0.0

    budget_docs = frappe.get_all(
        "Per BL Budget",
        filters={
            "plant": ["in", plants],
            "from": ["<=", overall_from],
            "to": [">=", overall_to]
        },
        fields=["name", "target_production"]
    )

    if not budget_docs:
        return {}, 0.0

    doc_names = [d.name for d in budget_docs]
    target_production = sum(flt(d.target_production) for d in budget_docs)

    budget_rows = frappe.get_all(
        "GL Budget",
        filters={"parent": ["in", doc_names], "parenttype": "Per BL Budget"},
        fields=["account_number", "budget_amount", "per_bl_budget"]
    )

    budget_by_account = {}
    for row in budget_rows:
        if not row.account_number:
            continue
        bucket = budget_by_account.setdefault(row.account_number, {"budget_amount": 0.0, "budget_per_bl": 0.0})
        bucket["budget_amount"] += flt(row.budget_amount)
        bucket["budget_per_bl"] += flt(row.per_bl_budget)

    return budget_by_account, target_production


def get_data(filters, months):
    show_summary = filters.get("show_summary", 0)
    hide_zero = filters.get("hide_zero_amounts", 0)
    show_quant = filters.get("show_quantitative_data", 0)
    branch_val = filters.get("branch")
    segment_val = filters.get("segment")
    company_val = filters.get("company")

    if not company_val:
        frappe.throw(_("Company is mandatory"))

    FIXED_PROD_ITEMS_MAP = [
        {"name": "Production of Ethanol from Maize", "code": "100114"},
        {"name": "Production of Ethanol from DFG", "code": "100112"},
        {"name": "Production of Ethanol from FCI Rice", "code": "100113"},
        {"name": "Production of ENA from Maize", "code": "100122"},
        {"name": "Production of ENA from DFG", "code": "100120"},
        {"name": "Production of RS from Maize", "code": "100130"},
        {"name": "Production of RS from DFG", "code": "100128"}
    ]

    FIXED_SALES_ITEMS_MAP = [
        {"name": "Ethanol from Maize", "code": "100114"},
        {"name": "Ethanol from DFG", "code": "100112"},
        {"name": "Ethanol from FCI", "code": "100113"},
        {"name": "ENA from Maize", "code": "100122"},
        {"name": "ENA from DFG", "code": "100120"},
        {"name": "RS from Maize", "code": "100130"},
        {"name": "RS from DFG", "code": "100128"}
    ]

    FIXED_CODES = tuple(item["code"] for item in FIXED_PROD_ITEMS_MAP)

    stock_conditions = [
        "se.docstatus = 1",
        "se.purpose = 'Material Receipt'",
        "se.posting_date >= %(from_date)s",
        "se.posting_date <= %(to_date)s",
        "sed.item_code IN %(prod_items)s",
        "se.company = %(company)s"
    ]
    stock_args = {
        "from_date": filters.get("from_date"),
        "to_date": filters.get("to_date"),
        "prod_items": FIXED_CODES,
        "company": company_val
    }

    if branch_val:
        stock_conditions.append("(se.branch = %(branch)s OR se.to_warehouse LIKE %(branch_pat)s)")
        stock_args["branch"] = branch_val
        stock_args["branch_pat"] = f"%{branch_val}%"
    if segment_val:
        stock_conditions.append("se.segment = %(segment)s")
        stock_args["segment"] = segment_val

    prod_entries = frappe.db.sql(f"""
        SELECT
            sed.item_code,
            DATE_FORMAT(se.posting_date, '%%Y-%%m') AS month_key,
            SUM(sed.qty * sed.conversion_factor) AS prod_qty
        FROM `tabStock Entry Detail` sed
        INNER JOIN `tabStock Entry` se ON se.name = sed.parent
        WHERE {" AND ".join(stock_conditions)}
        GROUP BY sed.item_code, DATE_FORMAT(se.posting_date, '%%Y-%%m')
    """, stock_args, as_dict=True)

    item_month_prod = {}
    monthly_prod_map = zero_month_dict(months)

    for pe in prod_entries:
        item_month_prod.setdefault(pe.item_code, {})[pe.month_key] = pe.prod_qty
        monthly_prod_map[pe.month_key] = monthly_prod_map.get(pe.month_key, 0.0) + flt(pe.prod_qty)

    total_ytd_production = sum(monthly_prod_map.values())

    sales_conditions = [
        "si.docstatus = 1",
        "si.posting_date >= %(from_date)s",
        "si.posting_date <= %(to_date)s",
        "sii.item_code IN %(sales_items)s",
        "si.company = %(company)s"
    ]
    sales_args = {
        "from_date": filters.get("from_date"),
        "to_date": filters.get("to_date"),
        "sales_items": FIXED_CODES,
        "company": company_val
    }

    if branch_val:
        sales_conditions.append("si.branch = %(branch)s")
        sales_args["branch"] = branch_val
    if segment_val:
        sales_conditions.append("si.segment = %(segment)s")
        sales_args["segment"] = segment_val

    sales_entries = frappe.db.sql(f"""
        SELECT
            sii.item_code,
            DATE_FORMAT(si.posting_date, '%%Y-%%m') AS month_key,
            SUM(sii.stock_qty) AS sales_qty,
            SUM(sii.base_amount) AS sales_val
        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
        WHERE {" AND ".join(sales_conditions)}
        GROUP BY sii.item_code, DATE_FORMAT(si.posting_date, '%%Y-%%m')
    """, sales_args, as_dict=True)

    sales_qty_map = {}
    sales_val_map = {}
    for se in sales_entries:
        sales_qty_map.setdefault(se.item_code, {})[se.month_key] = flt(se.sales_qty)
        sales_val_map.setdefault(se.item_code, {})[se.month_key] = flt(se.sales_val)

    if show_quant:
        return get_quant_data(filters, months, FIXED_PROD_ITEMS_MAP, FIXED_SALES_ITEMS_MAP, item_month_prod, sales_qty_map, sales_val_map, company_val, branch_val, segment_val), 0.0

    overall_from = filters.get("from_date")
    overall_to = filters.get("to_date")
    budget_by_account, target_production = get_budget_summary(company_val, branch_val, overall_from, overall_to)
    data = get_cost_data(filters, months, FIXED_CODES, monthly_prod_map, total_ytd_production, sales_qty_map, sales_val_map, show_summary, hide_zero, company_val, branch_val, segment_val, budget_by_account, target_production)
    return data, target_production


def get_quant_data(filters, months, FIXED_PROD_ITEMS_MAP, FIXED_SALES_ITEMS_MAP,
                    item_month_prod, sales_qty_map, sales_val_map,
                    company_val, branch_val, segment_val):
    data = []

    data.append({"expense_category": "Production of Finished Goods", "gl_code": "Item Code", "uom": "", "indent": 0, "is_quant_header": 1})
    quant_totals = zero_month_dict(months)
    quant_ytd_total = 0.0

    for item_info in FIXED_PROD_ITEMS_MAP:
        icode = item_info["code"]
        iname = item_info["name"]
        row = {"expense_category": iname, "gl_code": icode, "uom": get_stock_uom(icode), "indent": 1}
        row_ytd = 0.0
        for m in months:
            m_key = m["key"]
            qty = flt(item_month_prod.get(icode, {}).get(m_key, 0.0))
            row[f"actual_{m_key}"] = qty
            row_ytd += qty
            quant_totals[m_key] += qty
        row["total_actual"] = row_ytd
        quant_ytd_total += row_ytd
        data.append(row)

    tot_fg_row = {"expense_category": "Total", "gl_code": "", "uom": "", "indent": 1, "total_actual": quant_ytd_total, "is_quant_subtotal": 1}
    for m in months:
        tot_fg_row[f"actual_{m['key']}"] = quant_totals[m['key']]
    data.append(tot_fg_row)

    consumed_by_item, opening_by_item, closing_by_item = compute_consumption_data(
        company_val, branch_val, segment_val, months, filters
    )

    data.extend(build_quant_section_from_data("Raw Mat Consumed", ["Maize", "DFG", "Rice"], consumed_by_item, months))
    data.extend(build_quant_section_from_data("Opening WIP", ["Maize", "DFG", "Rice"], opening_by_item, months))
    data.extend(build_quant_section_from_data("Closing WIP", ["Maize", "DFG", "Rice"], closing_by_item, months))
    data.extend(build_recovery_section(item_month_prod, consumed_by_item, months))

    data.append({"expense_category": "Sales QTY", "gl_code": "Item Code", "uom": "", "indent": 0, "is_quant_header": 1})
    sqty_totals = zero_month_dict(months)
    sqty_ytd_total = 0.0

    for item_info in FIXED_SALES_ITEMS_MAP:
        icode = item_info["code"]
        iname = item_info["name"]
        row = {"expense_category": iname, "gl_code": icode, "uom": get_stock_uom(icode), "indent": 1}
        row_ytd = 0.0
        for m in months:
            m_key = m["key"]
            qty = sales_qty_map.get(icode, {}).get(m_key, 0.0)
            row[f"actual_{m_key}"] = qty
            row_ytd += qty
            sqty_totals[m_key] += qty
        row["total_actual"] = row_ytd
        sqty_ytd_total += row_ytd
        data.append(row)

    tot_sqty_row = {"expense_category": "Total", "gl_code": "", "uom": "", "indent": 1, "total_actual": sqty_ytd_total, "is_quant_subtotal": 1}
    for m in months:
        tot_sqty_row[f"actual_{m['key']}"] = sqty_totals[m['key']]
    data.append(tot_sqty_row)

    data.append({"expense_category": "Sales Value", "gl_code": "Item Code", "uom": "", "indent": 0, "is_quant_header": 1})
    sval_totals = zero_month_dict(months)
    sval_ytd_total = 0.0

    for item_info in FIXED_SALES_ITEMS_MAP:
        icode = item_info["code"]
        iname = item_info["name"]
        row = {"expense_category": iname, "gl_code": icode, "uom": "", "indent": 1}
        row_ytd = 0.0
        for m in months:
            m_key = m["key"]
            val = sales_val_map.get(icode, {}).get(m_key, 0.0)
            row[f"actual_{m_key}"] = val
            row_ytd += val
            sval_totals[m_key] += val
        row["total_actual"] = row_ytd
        sval_ytd_total += row_ytd
        data.append(row)

    tot_sval_row = {"expense_category": "Total", "gl_code": "", "uom": "", "indent": 1, "total_actual": sval_ytd_total, "is_quant_subtotal": 1}
    for m in months:
        tot_sval_row[f"actual_{m['key']}"] = sval_totals[m['key']]
    data.append(tot_sval_row)

    data.append({"expense_category": "Sales Price", "gl_code": "Item Code", "uom": "", "indent": 0, "is_quant_header": 1})
    for item_info in FIXED_SALES_ITEMS_MAP:
        icode = item_info["code"]
        iname = item_info["name"]
        row = {"expense_category": iname, "gl_code": icode, "uom": get_stock_uom(icode), "indent": 1}
        tot_item_qty = sum(sales_qty_map.get(icode, {}).get(m["key"], 0.0) for m in months)
        tot_item_val = sum(sales_val_map.get(icode, {}).get(m["key"], 0.0) for m in months)

        for m in months:
            m_key = m["key"]
            m_qty = sales_qty_map.get(icode, {}).get(m_key, 0.0)
            m_val = sales_val_map.get(icode, {}).get(m_key, 0.0)
            row[f"actual_{m_key}"] = round(m_val / m_qty, 2) if m_qty else 0.0

        row["total_actual"] = round(tot_item_val / tot_item_qty, 2) if tot_item_qty else 0.0
        data.append(row)

    wgt_avg_row = {
        "expense_category": "WGT. AVG", "gl_code": "", "uom": "", "indent": 1,
        "total_actual": round(sval_ytd_total / sqty_ytd_total, 2) if sqty_ytd_total else 0.0,
        "is_quant_subtotal": 1
    }
    for m in months:
        m_key = m["key"]
        m_tot_qty = sqty_totals[m_key]
        m_tot_val = sval_totals[m_key]
        wgt_avg_row[f"actual_{m_key}"] = round(m_tot_val / m_tot_qty, 2) if m_tot_qty else 0.0
    data.append(wgt_avg_row)

    return data


def new_type_totals(months):
    return {
        "months": zero_month_dict(months),
        "total_actual": 0.0,
        "budget_amount": 0.0,
        "budget_per_bl": 0.0
    }


def build_summary_totals_row(label, totals_dict, months, monthly_prod_map, total_ytd_production, flag_key, reverse_color=False):
    tot_act = totals_dict["total_actual"]
    budget_amount = totals_dict.get("budget_amount", 0.0)
    budget_per_bl = totals_dict.get("budget_per_bl", 0.0)
    total_per_bl = round(tot_act / total_ytd_production, 2) if total_ytd_production else 0.0

    row = {
        "expense_category": label,
        "gl_code": "",
        "indent": 0,
        "budget_amount": budget_amount,
        "budget_per_bl": budget_per_bl,
        "total_actual": tot_act,
        "total_per_bl": total_per_bl,
        "total_per_bl_color": get_variance_color(total_per_bl, budget_per_bl, reverse_color)
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


ROW_STYLE_FLAG = {
    "Total": "is_total_row",
    "Subtotal": "is_subtotal",
    "Grand Total": "is_grand_total"
}


def build_section_rows(section_name, gl_codes, code_data_cache, code_to_title, budget_by_account,
                        months, monthly_prod_map, total_ytd_production, hide_zero, show_summary):
    """Returns (rows_to_display, cat_totals) for a single section."""
    reverse_color = is_by_product_section(section_name)
    cat_totals = new_type_totals(months)
    category_rows = []

    for code in gl_codes:
        code_budget = budget_by_account.get(code, {})
        row_budget_amount = code_budget.get("budget_amount", 0.0)
        row_budget_per_bl = code_budget.get("budget_per_bl", 0.0)

        row_data = {}
        row_tot_act = 0.0
        c_data = code_data_cache.get(code, {})

        for m in months:
            m_key = m["key"]
            m_act = c_data.get(m_key, 0.0)
            m_prod = monthly_prod_map.get(m_key, 0.0)
            m_per_bl = round(m_act / m_prod, 2) if m_prod else 0.0

            row_data[f"actual_{m_key}"] = m_act
            row_data[f"per_bl_{m_key}"] = m_per_bl
            row_data[f"per_bl_{m_key}_color"] = get_variance_color(m_per_bl, row_budget_per_bl, reverse_color)

            row_tot_act += m_act
            cat_totals["months"][m_key] += m_act

        row_tot_per_bl = round(row_tot_act / total_ytd_production, 2) if total_ytd_production else 0.0
        cat_totals["total_actual"] += row_tot_act
        cat_totals["budget_amount"] += row_budget_amount
        cat_totals["budget_per_bl"] += row_budget_per_bl

        if hide_zero and row_tot_act == 0:
            continue

        detail_row = {
            "expense_category": code_to_title.get(code, code),
            "gl_code": code,
            "indent": 1,
            "budget_amount": row_budget_amount,
            "budget_per_bl": row_budget_per_bl,
            "total_actual": row_tot_act,
            "total_per_bl": row_tot_per_bl,
            "total_per_bl_color": get_variance_color(row_tot_per_bl, row_budget_per_bl, reverse_color)
        }
        detail_row.update(row_data)
        category_rows.append(detail_row)

    if hide_zero and not category_rows and cat_totals["total_actual"] == 0:
        return [], cat_totals

    display_rows = []

    if show_summary:
        summary_row = build_summary_totals_row(section_name, cat_totals, months, monthly_prod_map,
                                                 total_ytd_production, None, reverse_color)
        display_rows.append(summary_row)
    else:
        display_rows.append({"expense_category": section_name, "gl_code": "", "indent": 0, "is_header": 1})
        display_rows.extend(category_rows)
        subtotal_row = build_summary_totals_row("Sub Total", cat_totals, months, monthly_prod_map,
                                                  total_ytd_production, "is_subtotal", reverse_color)
        display_rows.append(subtotal_row)

    return display_rows, cat_totals


def get_cost_data(filters, months, FIXED_CODES, monthly_prod_map, total_ytd_production,
                   sales_qty_map, sales_val_map, show_summary, hide_zero,
                   company_val, branch_val, segment_val, budget_by_account=None, target_production=0.0):
    budget_by_account = budget_by_account or {}
    data = []

    prod_qty_row = {
        "expense_category": "TOTAL PRODUCTION QTY (BL)",
        "gl_code": "",
        "indent": 0,
        "total_actual": total_ytd_production,
        "total_per_bl": 1.0 if total_ytd_production else 0.0,
        "is_total_row": 1
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
            SELECT name, account_number, account_name
            FROM `tabAccount`
            WHERE company = %(company)s
              AND is_group = 0
              AND account_number IN %(codes)s
        """, {
            "company": company_val,
            "codes": tuple(all_codes)
        }, as_dict=True)

    code_to_names = {}
    code_to_title = {}
    for acc in accounts:
        code_to_names.setdefault(acc.account_number, []).append(acc.name)
        code_to_title.setdefault(acc.account_number, acc.account_name)

    gl_conditions = [
        "docstatus = 1",
        "is_cancelled = 0",
        "company = %(company)s",
        "posting_date >= %(from_date)s",
        "posting_date <= %(to_date)s"
    ]
    gl_args = {
        "company": company_val,
        "from_date": filters.get("from_date"),
        "to_date": filters.get("to_date"),
    }

    if branch_val:
        gl_conditions.append("(section = %(branch)s OR branch = %(branch)s)")
        gl_args["branch"] = branch_val

    if segment_val:
        gl_conditions.append("segment = %(segment)s")
        gl_args["segment"] = segment_val

    gl_entries = frappe.db.sql(f"""
        SELECT
            account,
            DATE_FORMAT(posting_date, '%%Y-%%m') AS month_key,
            SUM(debit - credit) AS actual_expense
        FROM `tabGL Entry`
        WHERE {" AND ".join(gl_conditions)}
        GROUP BY account, DATE_FORMAT(posting_date, '%%Y-%%m')
    """, gl_args, as_dict=True)

    gl_expense_map = {}
    for gle in gl_entries:
        gl_expense_map.setdefault(gle.account, {})[gle.month_key] = gle.actual_expense

    code_data_cache = {}
    for code in all_codes:
        acc_names = code_to_names.get(code, [])
        code_data_cache[code] = {
            m["key"]: sum(gl_expense_map.get(acc_name, {}).get(m["key"], 0.0) for acc_name in acc_names)
            for m in months
        }

    computed_totals = {}
    cop_base_row = None
    cop_base_label = None

    for row_type, row_name in sequence:
        if row_type == "Section":
            display_rows, cat_totals = build_section_rows(
                row_name, section_codes.get(row_name, []), code_data_cache, code_to_title,
                budget_by_account, months, monthly_prod_map, total_ytd_production, hide_zero, show_summary
            )
            data.extend(display_rows)
            computed_totals[row_name] = cat_totals

        elif row_type == "Total Row":
            total_def = total_row_defs[row_name]
            agg = new_type_totals(months)

            for comp_type, comp_name in total_def["components"]:
                src = computed_totals.get(comp_name)
                if not src:
                    # component not yet computed (wrong order) or fully hidden by
                    # hide_zero - contributes nothing rather than erroring out
                    continue
                for m in months:
                    agg["months"][m["key"]] += src["months"][m["key"]]
                agg["total_actual"] += src["total_actual"]
                agg["budget_amount"] += src.get("budget_amount", 0.0)
                agg["budget_per_bl"] += src.get("budget_per_bl", 0.0)

            flag_key = ROW_STYLE_FLAG.get(total_def["row_style"], "is_total_row")
            total_row_out = build_summary_totals_row(
                row_name, agg, months, monthly_prod_map, total_ytd_production,
                flag_key, total_def["reverse_color"]
            )
            data.append(total_row_out)
            computed_totals[row_name] = agg

            if total_def["is_cop_base"]:
                cop_base_row = total_row_out
                cop_base_label = row_name

    if cop_base_row is None:
        for row_type, row_name in reversed(sequence):
            if row_type == "Total Row" and row_name in computed_totals:
                cop_base_row = build_summary_totals_row(
                    row_name, computed_totals[row_name], months, monthly_prod_map,
                    total_ytd_production, "is_total_row"
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
                "TOTAL COST", all_sections_agg, months, monthly_prod_map,
                total_ytd_production, "is_total_row"
            )

    if cop_base_row is not None:
        data.extend(build_profitability_section(months, FIXED_CODES, monthly_prod_map, total_ytd_production,
                                                 sales_qty_map, sales_val_map, cop_base_row))

    return data


PER_BL_PROFIT_ROWS = {
    "Wgt Avg Selling Price (Per Litre)",
    "Wgt Avg COP (Per Litre)",
    "Net Profit / Loss (Per Litre)"
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
        m_net_profit = round(m_selling_price - m_cop, 2)
        m_prod = monthly_prod_map.get(m_key, 0.0)

        monthly_snapshot[m_key] = {
            "qty": m_tot_qty,
            "val": m_tot_val,
            "selling_price": m_selling_price,
            "cop": m_cop,
            "net_profit": m_net_profit,
            "prod": m_prod,
        }

    tot_sales_qty = sum(v["qty"] for v in monthly_snapshot.values())
    tot_sales_val = sum(v["val"] for v in monthly_snapshot.values())

    wgt_selling_price = round(tot_sales_val / tot_sales_qty, 2) if tot_sales_qty else 0.0
    wgt_cop = grand_total_row["total_per_bl"]
    net_profit_per_litre = round(wgt_selling_price - wgt_cop, 2)

    profit_loss_production = round(net_profit_per_litre * total_ytd_production, 2)
    profit_loss_sales = round(net_profit_per_litre * tot_sales_qty, 2)

    data = [
        {"expense_category": "", "gl_code": "", "indent": 0},
        {"expense_category": "Profitability", "gl_code": "", "indent": 0, "is_header": 1},
    ]

    prof_rows = [
        {"name": "Wgt Avg Selling Price (Per Litre)", "val": wgt_selling_price},
        {"name": "Wgt Avg COP (Per Litre)", "val": wgt_cop},
        {"name": "Net Profit / Loss (Per Litre)", "val": net_profit_per_litre},
        {"name": "Profit / Loss in Value (as Per Production)", "val": profit_loss_production},
        {"name": "Profit / Loss Value as Per Sales", "val": profit_loss_sales}
    ]

    for pr in prof_rows:
        is_per_bl = pr["name"] in PER_BL_PROFIT_ROWS
        p_row = {
            "expense_category": pr["name"],
            "gl_code": "",
            "indent": 1,
            "total_actual": 0.0 if is_per_bl else pr["val"],
            "total_per_bl": pr["val"] if is_per_bl else 0.0,
            "is_subtotal": 1 if "Net Profit" in pr["name"] or "Sales" in pr["name"] else 0
        }
        for m in months:
            m_key = m["key"]
            snap = monthly_snapshot[m_key]

            if pr["name"] == "Wgt Avg Selling Price (Per Litre)":
                val = snap["selling_price"]
            elif pr["name"] == "Wgt Avg COP (Per Litre)":
                val = snap["cop"]
            elif pr["name"] == "Net Profit / Loss (Per Litre)":
                val = snap["net_profit"]
            elif pr["name"] == "Profit / Loss in Value (as Per Production)":
                val = round(snap["net_profit"] * snap["prod"], 2)
            else:
                val = round(snap["net_profit"] * snap["qty"], 2)

            if is_per_bl:
                p_row[f"actual_{m_key}"] = 0.0
                p_row[f"per_bl_{m_key}"] = val
            else:
                p_row[f"actual_{m_key}"] = val
                p_row[f"per_bl_{m_key}"] = 0.0

        data.append(p_row)

    return data