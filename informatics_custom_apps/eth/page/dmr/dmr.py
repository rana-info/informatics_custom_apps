import frappe
from frappe.utils import getdate, add_days, formatdate

# NOTE: "Plant" is not a real fieldname on Stock Entry — the underlying
# field is "branch" (Branch doctype). It is only labeled/translated as
# "Plant" in the UI, so the DB-side filter must use the actual fieldname.
PLANT_FIELD = "branch"
SEGMENT_FIELD = "segment"

PRODUCTION_ITEMS = [
    ("100114", "Production of Ethanol from Maize", "A.1"),
    ("100112", "Production of Ethanol from DFG", "A.2"),
    ("100113", "Production of Ethanol from FCI Rice", "A.3"),
    ("100122", "Production of ENA from Maize", "A.4"),
    ("100120", "Production of ENA from DFG", "A.5"),
    ("100130", "Production of RS from Maize", "A.6"),
    ("100128", "Production of RS from DFG", "A.7"),
]

RM_ITEMS = [
    ("106444", "Maize Consumed ( Net of WIP)", "B.1"),
    ("100474", "DFG Consumed ( Net of WIP)", "B.2"),
    ("106448", "FCI Surplus Rice Consumed ( Net of WIP)", "B.3"),
]

BYPRODUCT_ITEMS = [
    ("100151", "DWGS from Maize", "E.1"),
    ("100149", "DWGS from DFG", "E.2"),
    ("100150", "DWGS from FCI", "E.3"),
    ("100147", "DDGS from Maize", "E.4"),
    ("100145", "DDGS from DFG", "E.5"),
    ("100146", "DDGS from FCI", "E.6"),
    ("129946", "Crude Corn Oil", "E.7"),
]

FUEL_ITEMS = [
    ("106441", "Paddy", "H.1"),
    ("106436", "Rice Husk", "H.2"),
    ("100093", "Bagasse", "H.3"),
    ("101077", "Cane Trash", "H.4"),
    ("106440", "Mustard Husk", "H.5"),
    ("106442", "Mandi Husk", "H.6"),
    ("106983", "Khudi", "H.7"),
    ("106443", "Wooden Chips", "H.8"),
]

STOCK_ITEMS = [r[0] for r in PRODUCTION_ITEMS] + [r[0] for r in BYPRODUCT_ITEMS]


def get_fiscal_year_start(date):
    fy = frappe.db.sql("""
        select year_start_date
        from `tabFiscal Year`
        where %(date)s between year_start_date and year_end_date
        limit 1
    """, {"date": date})
    return fy[0][0] if fy else date


def build_plant_segment_conditions(plants, segments):
    conditions = ""
    values = {}
    if plants:
        conditions += f" and se.{PLANT_FIELD} in %(plants)s"
        values["plants"] = plants
    if segments:
        conditions += f" and sed.{SEGMENT_FIELD} in %(segments)s"
        values["segments"] = segments
    return conditions, values


def get_production_qty(companies, from_date, to_date, item_codes, plants=None, segments=None):
    if not item_codes:
        return {}
    extra_sql, extra_vals = build_plant_segment_conditions(plants, segments)
    values = {"companies": companies, "from_date": from_date, "to_date": to_date, "items": item_codes}
    values.update(extra_vals)
    rows = frappe.db.sql(f"""
        select sed.item_code, sum(sed.qty * sed.conversion_factor) as qty
        from `tabStock Entry` se
        inner join `tabStock Entry Detail` sed on se.name = sed.parent
        where se.docstatus = 1
            and se.stock_entry_type = 'Material Receipt'
            and se.company in %(companies)s
            and se.posting_date between %(from_date)s and %(to_date)s
            and sed.item_code in %(items)s
            {extra_sql}
        group by sed.item_code
    """, values, as_dict=1)
    return {r.item_code: r.qty or 0 for r in rows}


def get_issue_qty(companies, from_date, to_date, item_codes, plants=None, segments=None):
    if not item_codes:
        return {}
    extra_sql, extra_vals = build_plant_segment_conditions(plants, segments)
    values = {"companies": companies, "from_date": from_date, "to_date": to_date, "items": item_codes}
    values.update(extra_vals)
    rows = frappe.db.sql(f"""
        select sed.item_code, sum(sed.qty * sed.conversion_factor) as qty
        from `tabStock Entry` se
        inner join `tabStock Entry Detail` sed on se.name = sed.parent
        where se.docstatus = 1
            and se.stock_entry_type = 'Material Issue'
            and se.company in %(companies)s
            and se.posting_date between %(from_date)s and %(to_date)s
            and sed.item_code in %(items)s
            {extra_sql}
        group by sed.item_code
    """, values, as_dict=1)
    return {r.item_code: r.qty or 0 for r in rows}


def get_stock_balance(companies, to_date, item_codes):
    if not item_codes:
        return {}
    rows = frappe.db.sql("""
        select i.item_code, round(coalesce(sum(sle.qty_after_transaction), 0), 3) as qty
        from `tabItem` i
        left join (
            select s1.item_code, s1.warehouse, s1.qty_after_transaction
            from `tabStock Ledger Entry` s1
            inner join (
                select item_code, warehouse,
                    max(concat(posting_date,' ',posting_time,' ',creation)) as last_entry
                from `tabStock Ledger Entry`
                where company in %(companies)s
                    and posting_date <= %(to_date)s
                    and is_cancelled = 0
                group by item_code, warehouse
            ) x on x.item_code = s1.item_code
                and x.warehouse = s1.warehouse
                and concat(s1.posting_date,' ',s1.posting_time,' ',s1.creation) = x.last_entry
        ) sle on sle.item_code = i.item_code
        where i.item_code in %(items)s
        group by i.item_code
    """, {"companies": companies, "to_date": to_date, "items": item_codes}, as_dict=1)
    return {r.item_code: r.qty or 0 for r in rows}


def safe_div(n, d):
    return (n / d) if d else 0


def build_section_rows(companies, from_date, to_date, plants=None, segments=None):
    prod_codes = [r[0] for r in PRODUCTION_ITEMS]
    rm_codes = [r[0] for r in RM_ITEMS]
    by_codes = [r[0] for r in BYPRODUCT_ITEMS]
    fuel_codes = [r[0] for r in FUEL_ITEMS]

    prod = get_production_qty(companies, from_date, to_date, prod_codes, plants, segments)
    rm = get_issue_qty(companies, from_date, to_date, rm_codes, plants, segments)
    by = get_production_qty(companies, from_date, to_date, by_codes, plants, segments)
    fuel = get_issue_qty(companies, from_date, to_date, fuel_codes, plants, segments)

    maize_prod = prod.get("100114", 0) + prod.get("100122", 0) + prod.get("100130", 0)
    dfg_prod = prod.get("100112", 0) + prod.get("100120", 0) + prod.get("100128", 0)
    fci_prod = prod.get("100113", 0)

    maize_rm = rm.get("106444", 0)
    dfg_rm = rm.get("100474", 0)
    fci_rm = rm.get("106448", 0)
    total_rm = maize_rm + dfg_rm + fci_rm

    dwgs_maize, dwgs_dfg, dwgs_fci = by.get("100151", 0), by.get("100149", 0), by.get("100150", 0)
    ddgs_maize, ddgs_dfg, ddgs_fci = by.get("100147", 0), by.get("100145", 0), by.get("100146", 0)
    crude_oil = by.get("129946", 0)

    rows = []
    rows.append({"sr": "A", "label": "Production of Finished Goods", "header": True})
    for code, label, sr in PRODUCTION_ITEMS:
        rows.append({"sr": sr, "label": label, "uom": "BL", "value": prod.get(code, 0), "item_code": code})

    rows.append({"sr": "B", "label": "Consumption of Raw Material", "header": True})
    for code, label, sr in RM_ITEMS:
        rows.append({"sr": sr, "label": label, "uom": "Qtl", "value": rm.get(code, 0), "item_code": code})

    rows.append({"sr": "C", "label": "Recovery of Finished Goods", "header": True})
    rows.append({"sr": "C.1", "label": "Recovery from Maize", "uom": "BL/Qtl", "value": safe_div(maize_prod, maize_rm)})
    rows.append({"sr": "C.2", "label": "Recovery from DFG", "uom": "BL/Qtl", "value": safe_div(dfg_prod, dfg_rm)})
    rows.append({"sr": "C.3", "label": "Recovery from FCI Rice", "uom": "BL/Qtl", "value": safe_div(fci_prod, fci_rm)})

    rows.append({"sr": "D", "label": "Fermentation Parameters", "header": True})
    for sr, label in [("D.1", "Alcohol Percentage"), ("D.2", "Fermenter -RS"), ("D.3", "Fermenter -RST"),
                       ("D.4", "Average Starch - Maize"), ("D.5", "Average Starch - DFG"), ("D.6", "Average Starch - FCI")]:
        rows.append({"sr": sr, "label": label, "uom": "%", "value": None})

    rows.append({"sr": "E", "label": "Production of by Products", "header": True})
    for code, label, sr in BYPRODUCT_ITEMS:
        uom = "Ltr" if code == "129946" else "Qtl"
        rows.append({"sr": sr, "label": label, "uom": uom, "value": by.get(code, 0), "item_code": code})

    rows.append({"sr": "F", "label": "Recovery of By Products", "header": True})
    rows.append({"sr": "F.1", "label": "DWGS from Maize", "uom": "%", "value": safe_div(dwgs_maize, maize_rm) * 100})
    rows.append({"sr": "F.2", "label": "DWGS from DFG", "uom": "%", "value": safe_div(dwgs_dfg, dfg_rm) * 100})
    rows.append({"sr": "F.3", "label": "DWGS from FCI", "uom": "%", "value": safe_div(dwgs_fci, fci_rm) * 100})
    rows.append({"sr": "F.4", "label": "Average DWGS", "uom": "%", "value": safe_div(dwgs_maize + dwgs_dfg + dwgs_fci, total_rm) * 100})
    rows.append({"sr": "F.5", "label": "DDGS from Maize", "uom": "%", "value": safe_div(ddgs_maize, maize_rm) * 100})
    rows.append({"sr": "F.6", "label": "DDGS from DFG", "uom": "%", "value": safe_div(ddgs_dfg, dfg_rm) * 100})
    rows.append({"sr": "F.7", "label": "DDGS from FCI", "uom": "%", "value": safe_div(ddgs_fci, fci_rm) * 100})
    rows.append({"sr": "F.8", "label": "Average DDGS", "uom": "%", "value": safe_div(ddgs_maize + ddgs_dfg + ddgs_fci, total_rm) * 100})
    rows.append({"sr": "F.9", "label": "Crude Corn Oil", "uom": "%", "value": safe_div(crude_oil, total_rm) * 100})

    rows.append({"sr": "G", "label": "Boiler Performance", "header": True})
    for sr, label in [("G.1", "Steam produced"), ("G.2", "Steam Purchased"),
                       ("G.3", "Steam consumed Through PRDS"), ("G.4", "Steam Used Through Turbine")]:
        rows.append({"sr": sr, "label": label, "uom": "MT", "value": None})

    rows.append({"sr": "H", "label": "Fuel used for Boiler", "header": True})
    for code, label, sr in FUEL_ITEMS:
        rows.append({"sr": sr, "label": label, "uom": "MT", "value": fuel.get(code, 0), "item_code": code})

    rows.append({"sr": "I", "label": "Steam Raising Ratio", "header": True})
    for i, (code, label, sr) in enumerate(FUEL_ITEMS):
        rows.append({"sr": f"I.{i+1}", "label": label, "uom": "Ratio", "value": None, "item_code": code})
    rows.append({"sr": "I.9", "label": "Weighted Average", "uom": "Ratio", "value": None})

    for section, section_label in [("J", "Section wise Steam Consumed"), ("K", "Section wise Steam Consumed per BL")]:
        rows.append({"sr": section, "label": section_label, "header": True})
        uom = "MT" if section == "J" else "KG/BL"
        for i, label in enumerate(["Liquification", "Distillation", "MSDH", "Evaporation", "Dryer", "Deaerator", "Other"]):
            rows.append({"sr": f"{section}.{i+1}", "label": label, "uom": uom, "value": None})

    rows.append({"sr": "L", "label": "Technical Parameters Of Boiler & Turbine", "header": True})
    for sr, label, uom in [("L.1", "Bolier Load Per Hour", "MT/Hr"), ("L.2", "ESP Outlet Temp", "Degree"), ("L.3", "Unburnt Ash %", "%")]:
        rows.append({"sr": sr, "label": label, "uom": uom, "value": None})

    rows.append({"sr": "M", "label": "Power Performance", "header": True})
    for sr, label in [("M.1", "Power Generation"), ("M.2", "Power Purchased"), ("M.3", "Power Export"),
                       ("M.4", "Power Sales"), ("M.5", "Power Consumed")]:
        rows.append({"sr": sr, "label": label, "uom": "MW", "value": None})
    rows.append({"sr": "M.6", "label": "Power Per BL", "uom": "MW", "value": None})

    rows.append({"sr": "N", "label": "Stock", "header": True})
    stock = get_stock_balance(companies, to_date, STOCK_ITEMS)
    rows.append({"sr": "N.1", "label": "Wash Available", "uom": "Ltrs", "value": None})
    rows.append({"sr": "N.2", "label": "Stock of Ethanol from Maize", "uom": "Ltrs", "value": stock.get("100114", 0), "item_code": "100114"})
    rows.append({"sr": "N.3", "label": "Stock of Ethanol from DFG", "uom": "Ltrs", "value": stock.get("100112", 0), "item_code": "100112"})
    rows.append({"sr": "N.4", "label": "Stock of Ethanol from FCI Rice", "uom": "Ltrs", "value": stock.get("100113", 0), "item_code": "100113"})
    rows.append({"sr": "N.5", "label": "Stock of ENA from Maize", "uom": "Ltrs", "value": stock.get("100122", 0), "item_code": "100122"})
    rows.append({"sr": "N.6", "label": "Stock of ENA from DFG", "uom": "Ltrs", "value": stock.get("100120", 0), "item_code": "100120"})
    rows.append({"sr": "N.7", "label": "Stock of RS from Maize", "uom": "Ltrs", "value": stock.get("100130", 0), "item_code": "100130"})
    rows.append({"sr": "N.8", "label": "Stock of RS from DFG", "uom": "Ltrs", "value": stock.get("100128", 0), "item_code": "100128"})
    rows.append({"sr": "N.9", "label": "Stock of DDGS", "uom": "Ltrs",
                 "value": stock.get("100147", 0) + stock.get("100145", 0) + stock.get("100146", 0)})
    rows.append({"sr": "N.10", "label": "Stock of DWGS", "uom": "Ltrs",
                 "value": stock.get("100151", 0) + stock.get("100149", 0) + stock.get("100150", 0)})
    rows.append({"sr": "N.11", "label": "Stock of Crude Oil", "uom": "Ltrs", "value": stock.get("129946", 0), "item_code": "129946"})

    return rows


def _parse_list_arg(val):
    if isinstance(val, str):
        if val in ("", "null", "None", "undefined"):
            return None
        return frappe.parse_json(val)
    return val


@frappe.whitelist()
def get_report_data(companies, from_date, to_date, plants=None, segments=None):
    companies = _parse_list_arg(companies)
    plants = _parse_list_arg(plants) or None
    segments = _parse_list_arg(segments) or None

    from_date = getdate(from_date)
    to_date = getdate(to_date)

    date_list = []
    d = from_date
    while d <= to_date:
        date_list.append(d)
        d = add_days(d, 1)

    fy_start = get_fiscal_year_start(to_date)

    meta_rows = build_section_rows(companies, from_date, from_date, plants, segments)
    meta = [
        {
            "sr": r["sr"],
            "label": r["label"],
            "uom": r.get("uom"),
            "header": r.get("header", False),
            "item_code": r.get("item_code"),
        }
        for r in meta_rows
    ]

    columns = []
    for dt in date_list:
        rows = build_section_rows(companies, dt, dt, plants, segments)
        columns.append({"label": formatdate(dt, "d.MM"), "values": {r["sr"]: r.get("value") for r in rows}})

    todate_rows = build_section_rows(companies, fy_start, to_date, plants, segments)
    # Show the actual date range this "To Date" column covers (fiscal-year
    # start through the selected to_date) rather than a bare "To Date" label.
    todate_label = f"To Date ({formatdate(fy_start, 'd.MM.yy')} - {formatdate(to_date, 'd.MM.yy')})"
    columns.append({"label": todate_label, "values": {r["sr"]: r.get("value") for r in todate_rows}})

    return {"meta": meta, "columns": columns}


@frappe.whitelist()
def get_plant_options(companies=None):
    companies = _parse_list_arg(companies)

    # Prefer Branch's own "company" field as the source of truth for which
    # company a plant belongs to. Inferring it from Stock Entry usage (i.e.
    # "which companies have posted a Stock Entry against this branch") is
    # unreliable — a branch can appear on a mis-tagged or shared Stock Entry
    # under a company it doesn't actually belong to.
    if frappe.db.has_column("Branch", "company"):
        filters = {}
        if companies:
            filters["company"] = ["in", companies]
        return frappe.get_all("Branch", filters=filters, pluck="name", order_by="name")

    # Fallback for setups where Branch has no company field: fall back to
    # the old Stock-Entry-usage-based filter (best effort only).
    if not frappe.db.has_column("Stock Entry", PLANT_FIELD):
        return []
    condition = "and company in %(companies)s" if companies else ""
    plants = frappe.db.sql(f"""
        select distinct {PLANT_FIELD} as plant
        from `tabStock Entry`
        where {PLANT_FIELD} is not null and {PLANT_FIELD} != ''
        {condition}
        order by {PLANT_FIELD}
    """, {"companies": companies} if companies else {}, as_dict=1)
    return [p.plant for p in plants]


@frappe.whitelist()
def get_segment_options():
    return frappe.get_all("Segment", filters={"is_group": 0}, pluck="name", order_by="name")