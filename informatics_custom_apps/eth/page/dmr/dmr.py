import frappe
from frappe.utils import getdate, add_days, formatdate
from collections import defaultdict
from erpnext.stock.get_item_details import get_conversion_factor

# =============================================================================
# REPORT DAY WINDOW
# =============================================================================
# The plant's operational "day" does not run midnight-to-midnight — it runs
# DAY_START_TIME to DAY_START_TIME the next calendar day (e.g. 6:00 AM to
# 6:00 AM). A Stock Entry / Stock Ledger Entry posted at 2:00 AM on the 17th
# belongs to the "16th" report day, not the 17th.
#
# This ONLY applies to data sources with a real posting timestamp (Stock
# Entry, Stock Ledger Entry). Per-day master doctypes (DMR Technical Lab
# Parameters, DMR Boiler And Turbine Parameters) already store one row per
# plant per REPORT day against a plain Date field — the shift is baked into
# how that field gets filled in at data-entry time, so their date-range
# filters are left as plain date `between` and need no further adjustment.
DAY_START_TIME = "06:00:00"


def get_report_datetime_range(from_date, to_date, day_start_time=DAY_START_TIME):
    """
    Convert report from_date/to_date (both report-day dates) into the actual
    [from_datetime, to_datetime) window to filter real posting timestamps
    against.

    e.g. from_date=16-Jul, to_date=16-Jul, day_start_time=06:00:00 ->
         ("2026-07-16 06:00:00", "2026-07-17 06:00:00")
    to_datetime is exclusive — a doc posted exactly at the next day's
    06:00:00 belongs to the next report day, not this one.
    """
    from_dt = f"{getdate(from_date)} {day_start_time}"
    to_dt = f"{add_days(getdate(to_date), 1)} {day_start_time}"
    return from_dt, to_dt


# =============================================================================
# DATA SOURCE MAP (quick reference — see per-section comments below for detail)
# =============================================================================
#   A  Production of FG              -> Stock Entry (Material Receipt)
#   B  Consumption of Raw Material   -> Stock Entry (Material Issue), netted
#                                        against WIP opening/closing balances
#                                        from DMR Technical Lab Parameters
#                                        (see get_wip_opening_closing below)
#   C  Recovery of FG                -> calculated from A / B
#   D  Fermentation Parameters       -> DMR Technical Lab Parameters
#   E  Production of By Products     -> Stock Entry (Material Receipt)
#   F  Recovery of By Products       -> calculated, mixed formula per item
#                                        (Maize rows use A / E, DFG/FCI/Crude
#                                        Oil rows use E / B -- see that section)
#   G  Boiler Performance            -> DMR Boiler And Turbine Parameters
#   H  Fuel used for Boiler          -> Stock Entry (Material Issue)
#   I  Steam Raising Ratio           -> Steam Raising Ratio (fixed master,
#                                        not date-dependent) + H for weighting;
#                                        I.11-I.18 also carry a reverse-
#                                        calculated ideal vs actual stock
#                                        comparison in a single row (value is
#                                        {ideal, actual}, not a plain number)
#   J  Section wise Steam Consumed   -> DMR Boiler And Turbine Parameters
#                                        (DMR Process Data doctype was
#                                        deleted; these fields were merged
#                                        onto this doctype — see note by
#                                        PROCESS_DATA_SUM_FIELDS below)
#   K  Steam Consumed per BL         -> calculated from J / (A total BL)
#   L  Technical Parameters (Boiler) -> DMR Boiler And Turbine Parameters
#   M  Power Performance             -> DMR Boiler And Turbine Parameters
#   N  Stock                         -> Stock Ledger Entry
# =============================================================================

# NOTE: "Plant" is not a real fieldname on Stock Entry — the underlying
# field is "branch" (Branch doctype). It is only labeled/translated as
# "Plant" in the UI, so the DB-side filter must use the actual fieldname.
PLANT_FIELD = "branch"
SEGMENT_FIELD = "segment"

# Item tuples: (item_code, label, sr_no, display_uom). display_uom is the
# UOM each row is shown in on the report — NOT necessarily the item's stock
# UOM. Raw quantities come back from Stock Entry/Stock Ledger Entry in stock
# UOM (see get_stock_to_target_factor / convert_qty_dict below), so this
# value drives the conversion applied right after each DB fetch.
PRODUCTION_ITEMS = [
    ("100114", "Production of Ethanol from Maize", "A.1", "BL"),
    ("100112", "Production of Ethanol from DFG", "A.2", "BL"),
    ("100113", "Production of Ethanol from FCI Rice", "A.3", "BL"),
    ("100122", "Production of ENA from Maize", "A.4", "BL"),
    ("100120", "Production of ENA from DFG", "A.5", "BL"),
    ("100130", "Production of RS from Maize", "A.6", "BL"),
    ("100128", "Production of RS from DFG", "A.7", "BL"),
]

RM_ITEMS = [
    ("106444", "Maize Consumed ( Net of WIP)", "B.1", "Qtl"),
    ("100474", "DFG Consumed ( Net of WIP)", "B.2", "Qtl"),
    ("106448", "FCI Surplus Rice Consumed ( Net of WIP)", "B.3", "Qtl"),
]

# =============================================================================
# SECTION B — Work-in-Progress opening/closing balances
# =============================================================================
# Section B's rows are explicitly labeled "(Net of WIP)" — the plain Stock
# Entry (Material Issue) quantity is GROSS material fed into the process,
# not what was actually consumed during the report period. Confirmed
# formula:
#
#     net_consumed = gross_issued (Stock Entry) + opening_wip - closing_wip
#
# i.e. material that was already mid-process at the start of the period
# counts toward this period's consumption, and material still mid-process
# at the end of the period does NOT.
#
# Opening/closing balances are recorded per plant per day as point-in-time
# snapshots on "DMR Technical Lab Parameters" (maize/dfg/fci
# *_opening_balance / *_closing_balance fields) — confirmed from that
# DocType's JSON. Maps item_code -> (opening_field, closing_field, raw_uom).
#
# ASSUMPTION FLAGGED: raw_uom values ("KG" for maize/fci, "LTR" for dfg) are
# taken verbatim from that DocType JSON's field `description` text (e.g.
# "Item Code : 106444 \nUOM : KG"), not from an authoritative UOM field —
# please confirm these are the exact UOM doctype names in your system
# (case/spelling matters for get_conversion_factor to resolve a factor).
# Note the JSON's own "dfg_closing_balance" field description says
# "Item Code : 106444" (Maize's code) instead of 100474 (DFG) — almost
# certainly a copy-paste typo in that field's description, so this map
# uses 100474 (matching RM_ITEMS / dfg_opening_balance) instead of what the
# closing field's description literally says. Flag/confirm if that's wrong.
WIP_ITEM_FIELDS = {
    "106444": {"opening_field": "maize_opening_balance", "closing_field": "maize_closing_balance", "raw_uom": "KG"},
    "100474": {"opening_field": "dfg_opening_balance", "closing_field": "dfg_closing_balance", "raw_uom": "LTR"},
    "106448": {"opening_field": "fci_opening_balance", "closing_field": "fci_closing_balance", "raw_uom": "KG"},
}

BYPRODUCT_ITEMS = [
    ("100151", "DWGS from Maize", "E.1", "Qtl"),
    ("100149", "DWGS from DFG", "E.2", "Qtl"),
    ("100150", "DWGS from FCI", "E.3", "Qtl"),
    ("100147", "DDGS from Maize", "E.4", "Qtl"),
    ("100145", "DDGS from DFG", "E.5", "Qtl"),
    ("100146", "DDGS from FCI", "E.6", "Qtl"),
    ("129946", "Crude Corn Oil", "E.7", "Ltr"),
]

FUEL_ITEMS = [
    ("106441", "Paddy", "H.1", "MT"),
    ("106436", "Rice Husk", "H.2", "MT"),
    ("100093", "Bagasse", "H.3", "MT"),
    ("101077", "Cane Trash", "H.4", "MT"),
    ("106440", "Mustard Husk", "H.5", "MT"),
    ("106442", "Mandi Husk", "H.6", "MT"),
    ("106983", "Khudi", "H.7", "MT"),
    ("106443", "Wooden Chips", "H.8", "MT"),
]

STOCK_ITEMS = [r[0] for r in PRODUCTION_ITEMS] + [r[0] for r in BYPRODUCT_ITEMS]
# Section N displays all stock items in Ltrs regardless of what UOM they're
# produced/consumed in above (e.g. Crude Corn Oil is Ltr in E but its stock
# balance in N is also Ltrs, DWGS/DDGS are Qtl in E but shown as Ltrs in N).
STOCK_UOM = "Ltrs"

# Fieldnames for "DMR Technical Lab Parameters" — confirmed from DocType JSON.
# Maps our semantic key -> real fieldname (note the real fieldname has a
# double underscore: "average_starch__maize").
LAB_PARAM_FIELDS = {
    "alcohol_percentage": "alcohol_percentage",
    "fermenter_rs": "fermenter_rs",
    "fermenter_rst": "fermenter_rst",
    "average_starch_maize": "average_starch__maize",
    "average_starch_dfg": "average_starch_dfg",
    "average_starch_fci": "average_starch_fci",
}

# Confirmed from DocType JSON: "Wash Available(in Ltrs)", fieldname
# "wash_available", fieldtype Float, on "DMR Technical Lab Parameters".
WASH_AVAILABLE_FIELD = "wash_available"

# Fieldnames for "DMR Boiler And Turbine Parameters" — confirmed from DocType
# JSON. This doctype uses auto-generated names (float_xxxx / percent_xxxx),
# so an explicit label -> fieldname map is required (there's no pattern to
# derive it from). Maps our semantic key -> real fieldname.
BOILER_SUM_FIELD_MAP = {
    "steam_produced": "float_zcpn",
    "steam_purchased": "float_jgdk",
    "steam_consumed_through_prds": "float_smgv",
    "steam_used_through_turbine": "float_lcuw",
    "power_generation": "float_pvrh",
    "power_purchased": "float_iunw",
    "power_export": "float_vjzq",
    "power_sales": "float_dctr",
    "power_consumed": "float_evng",
}
BOILER_AVG_FIELD_MAP = {
    "bolier_load_per_hour": "float_hrth",
    "esp_outlet_temp": "float_reke",
    "unburnt_ash": "percent_bman",
}
# NOTE: the doctype also has a real, directly-stored "power_per_bl" field.
# We deliberately do NOT read it — M.6 is calculated dynamically instead
# (power_consumed / total production BL for the selected period) so it
# stays correct for whatever date range/plant filter is applied, rather
# than depending on what happens to be saved in each daily record.


PROCESS_DATA_FIELDS = [
    # Section J labels. These used to live on "DMR Process Data" (now
    # deleted) and were queried by plain fieldname == label, no mapping
    # needed. That doctype's fields have been merged onto
    # "DMR Boiler And Turbine Parameters".
    ("liquification", "Liquification"),
    ("distillation", "Distillation"),
    ("msdh", "MSDH"),
    ("evaporation", "Evaporation"),
    ("dryer", "Dryer"),
    ("deaerator", "Deaerator"),
    ("other", "Other"),
]
# ASSUMPTION FLAGGED: fieldnames above are carried over unchanged from the
# old "DMR Process Data" doctype. I don't have the new merged DocType JSON
# to confirm they landed with the same names on "DMR Boiler And Turbine
# Parameters" — please verify before relying on this.
#
# LIKELY COLLISION: "DMR Boiler And Turbine Parameters" already has a field
# named "deaerator" used for the boiler's own FT102 tag reading (Deaerator
# flow, wired up in the Excel-import PLANT_CONFIG in that doctype's
# controller). Section J.6 "Deaerator" here is a DIFFERENT quantity (steam
# consumed by the deaerator process). These cannot both be the same column
# — check the actual DocType JSON and rename this entry (e.g.
# "deaerator_steam_consumed") to whatever the real merged fieldname is.
PROCESS_DATA_SUM_FIELDS = [f for f, _ in PROCESS_DATA_FIELDS]


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


# =============================================================================
# UOM CONVERSION
# =============================================================================
# get_production_qty / get_issue_qty / get_stock_balance all return raw
# quantities in each item's STOCK UOM (that's what qty * conversion_factor
# on Stock Entry Detail / qty_after_transaction on Stock Ledger Entry give
# you). The report displays each row in a specific UOM (BL, Qtl, Ltr, MT...)
# which may differ from stock UOM, so every {item_code: qty} dict fetched
# from the DB needs converting before it's used.
# =============================================================================
def get_stock_to_target_factor(item_code, target_uom):
    """
    Factor to multiply a stock-UOM qty by to express it in target_uom.
    get_conversion_factor(item_code, uom) returns how many stock_uom units
    make up 1 target_uom, so converting stock_qty -> target_uom means
    dividing by that factor.
    """
    stock_uom = frappe.get_cached_value("Item", item_code, "stock_uom")
    if not stock_uom or stock_uom == target_uom:
        return 1
    factor = (get_conversion_factor(item_code, target_uom) or {}).get("conversion_factor") or 1
    return 1 / factor if factor else 1


def convert_qty_dict(qty_by_item, uom_map):
    """Apply get_stock_to_target_factor to every value in a {item_code: qty} dict."""
    return {
        code: qty * get_stock_to_target_factor(code, uom_map[code])
        for code, qty in qty_by_item.items()
        if code in uom_map
    }


def convert_between_uoms(item_code, qty, from_uom, target_uom):
    """
    Convert a raw quantity given in an arbitrary `from_uom` (NOT necessarily
    the item's stock UOM — e.g. a WIP balance field recorded directly in
    "KG" or "LTR") into `target_uom`, using the item's configured UOM
    Conversion Detail factors for both UOMs relative to its own stock UOM:

        qty_in_stock_uom = qty * conversion_factor(from_uom)
        qty_in_target    = qty_in_stock_uom / conversion_factor(target_uom)

    If either UOM has no conversion factor configured on the Item,
    get_conversion_factor falls back to a factor of 1 (silently a no-op for
    that side) rather than raising — so a misconfigured/missing UOM entry
    degrades to a wrong-but-not-crashing number. Verify results look sane,
    particularly for DFG (Ltr -> Qtl) where a real factor must exist.
    """
    if qty is None:
        return 0
    if from_uom == target_uom:
        return qty
    from_factor = (get_conversion_factor(item_code, from_uom) or {}).get("conversion_factor") or 1
    to_factor = (get_conversion_factor(item_code, target_uom) or {}).get("conversion_factor") or 1
    return qty * from_factor / to_factor


# =============================================================================
# SECTIONS A / E — Production of Finished Goods & By Products
# Source: Stock Entry (stock_entry_type = "Material Receipt") joined to
# Stock Entry Detail, summed over the report period for the given item
# codes. Filtered on the actual posting TIMESTAMP (date + time) against the
# shifted report-day window (DAY_START_TIME), not the bare posting_date.
# Returns raw quantities in each item's STOCK UOM — convert with
# convert_qty_dict before display.
# =============================================================================
def get_production_qty(companies, from_date, to_date, item_codes, plants=None, segments=None):
    if not item_codes:
        return {}
    from_dt, to_dt = get_report_datetime_range(from_date, to_date)
    extra_sql, extra_vals = build_plant_segment_conditions(plants, segments)
    values = {"companies": companies, "from_dt": from_dt, "to_dt": to_dt, "items": item_codes}
    values.update(extra_vals)
    rows = frappe.db.sql(f"""
        select sed.item_code, sum(sed.qty * sed.conversion_factor) as qty
        from `tabStock Entry` se
        inner join `tabStock Entry Detail` sed on se.name = sed.parent
        where se.docstatus = 1
            and se.stock_entry_type = 'Material Receipt'
            and se.company in %(companies)s
            and timestamp(se.posting_date, se.posting_time) >= %(from_dt)s
            and timestamp(se.posting_date, se.posting_time) < %(to_dt)s
            and sed.item_code in %(items)s
            {extra_sql}
        group by sed.item_code
    """, values, as_dict=1)
    return {r.item_code: r.qty or 0 for r in rows}


# =============================================================================
# SECTIONS B / H — Consumption of Raw Material & Fuel used for Boiler
# Source: Stock Entry (stock_entry_type = "Material Issue") joined to
# Stock Entry Detail, summed over the report period for the given item
# codes. Same shifted report-day timestamp window as get_production_qty.
# Returns raw quantities in each item's STOCK UOM — convert with
# convert_qty_dict before display. For Section B specifically, this is the
# GROSS issued quantity — see get_wip_opening_closing for the WIP
# opening/closing adjustment that turns it into the "Net of WIP" figure
# actually shown on the report.
# =============================================================================
def get_issue_qty(companies, from_date, to_date, item_codes, plants=None, segments=None):
    if not item_codes:
        return {}
    from_dt, to_dt = get_report_datetime_range(from_date, to_date)
    extra_sql, extra_vals = build_plant_segment_conditions(plants, segments)
    values = {"companies": companies, "from_dt": from_dt, "to_dt": to_dt, "items": item_codes}
    values.update(extra_vals)
    rows = frappe.db.sql(f"""
        select sed.item_code, sum(sed.qty * sed.conversion_factor) as qty
        from `tabStock Entry` se
        inner join `tabStock Entry Detail` sed on se.name = sed.parent
        where se.docstatus = 1
            and se.stock_entry_type = 'Material Issue'
            and se.company in %(companies)s
            and timestamp(se.posting_date, se.posting_time) >= %(from_dt)s
            and timestamp(se.posting_date, se.posting_time) < %(to_dt)s
            and sed.item_code in %(items)s
            {extra_sql}
        group by sed.item_code
    """, values, as_dict=1)
    return {r.item_code: r.qty or 0 for r in rows}


# =============================================================================
# SECTION N — Stock
# Source: Stock Ledger Entry — latest qty_after_transaction as of the END of
# the report day for to_date (i.e. up to but not including the next
# DAY_START_TIME), per item across all warehouses of the selected companies.
# Returns raw quantities in each item's STOCK UOM — convert with
# convert_qty_dict before display.
# =============================================================================
def get_stock_balance(companies, to_date, item_codes):
    if not item_codes:
        return {}
    _, to_dt = get_report_datetime_range(to_date, to_date)
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
                    and timestamp(posting_date, posting_time) < %(to_dt)s
                    and is_cancelled = 0
                group by item_code, warehouse
            ) x on x.item_code = s1.item_code
                and x.warehouse = s1.warehouse
                and concat(s1.posting_date,' ',s1.posting_time,' ',s1.creation) = x.last_entry
        ) sle on sle.item_code = i.item_code
        where i.item_code in %(items)s
        group by i.item_code
    """, {"companies": companies, "to_dt": to_dt, "items": item_codes}, as_dict=1)
    return {r.item_code: r.qty or 0 for r in rows}


# =============================================================================
# SECTION D — Fermentation Parameters
# Source: "DMR Technical Lab Parameters" doctype (Company + Plant + Date,
# one record per plant per REPORT day). These are lab readings / percentages,
# not cumulative quantities, so for a multi-day range we AVERAGE each field
# rather than summing it. Filtered on the plain Date field — see the REPORT
# DAY WINDOW note at the top of this file for why that's correct here.
# =============================================================================
def get_lab_parameters(companies, from_date, to_date, plants=None):
    if not frappe.db.exists("DocType", "DMR Technical Lab Parameters"):
        return {}
    filters = {
        "company": ["in", companies],
        "date": ["between", [from_date, to_date]],
    }
    if plants:
        filters["plant"] = ["in", plants]
    field_map = _existing_field_map("DMR Technical Lab Parameters", LAB_PARAM_FIELDS)
    select_fields = [f"avg(`{real}`) as {semantic}" for semantic, real in field_map.items()]
    if not select_fields:
        return {}
    rows = frappe.get_all("DMR Technical Lab Parameters", filters=filters, fields=select_fields)
    return rows[0] if rows else {}


# =============================================================================
# SECTION N.1 — Wash Available
# Source: "DMR Technical Lab Parameters" doctype (Company + Plant + Date),
# same doctype as Section D. Unlike Section D's %-based lab readings (which
# are averaged over a multi-day range), Wash Available is a WIP
# fermentation-broth quantity, not a percentage -- averaging or summing it
# across days wouldn't mean anything sensible. Instead this takes the
# LATEST report-day value on or before to_date (i.e. the fermentation WIP
# as it stood at the end of the selected period), same logic as reading a
# stock balance. Kept as its own query/function rather than folded into
# get_lab_parameters since it needs different aggregation semantics.
# =============================================================================
def get_wash_available(companies, to_date, plants=None):
    if not frappe.db.exists("DocType", "DMR Technical Lab Parameters"):
        return None
    if not frappe.get_meta("DMR Technical Lab Parameters").has_field(WASH_AVAILABLE_FIELD):
        frappe.log_error(
            title="DMR Report: missing fields on DMR Technical Lab Parameters",
            message=f"Fieldnames not found, check DocType JSON: ['{WASH_AVAILABLE_FIELD}']",
        )
        return None
    filters = {"company": ["in", companies], "date": ["<=", to_date]}
    if plants:
        filters["plant"] = ["in", plants]
    rows = frappe.get_all(
        "DMR Technical Lab Parameters", filters=filters,
        fields=[WASH_AVAILABLE_FIELD], order_by="date desc", limit=1,
    )
    return rows[0].get(WASH_AVAILABLE_FIELD) if rows else None


# =============================================================================
# SECTION B — WIP opening/closing balances (Maize / DFG / FCI)
# Source: "DMR Technical Lab Parameters" doctype (Company + Plant + Date),
# same doctype as Section D / N.1. These are point-in-time WIP snapshots,
# NOT summed/averaged over the date range like Section D or J/G above.
#
# Uses the EXACT from_date record for opening and the EXACT to_date record
# for closing — no falling back to the nearest earlier/later date. If no
# record exists for that specific date, the value is treated as 0 rather
# than pulling in a balance from some other day (which would misrepresent
# the WIP position on a day nobody actually logged one).
# If multiple plants match the filter, sums across all of them for that
# exact date.
# Returns already-converted-to-target-UOM values:
#   {item_code: {"opening": qty, "closing": qty}}
# See convert_between_uoms for the raw-UOM -> target-UOM conversion and its
# flagged assumptions.
# =============================================================================
def get_wip_opening_closing(companies, from_date, to_date, target_uom_map, plants=None):
    if not frappe.db.exists("DocType", "DMR Technical Lab Parameters"):
        return {}

    meta = frappe.get_meta("DMR Technical Lab Parameters")
    base_filters = {"company": ["in", companies]}
    if plants:
        base_filters["plant"] = ["in", plants]

    def sum_field_on_exact_date(fieldname, on_date):
        if not meta.has_field(fieldname):
            return 0
        f = dict(base_filters)
        f["date"] = on_date
        rows = frappe.get_all("DMR Technical Lab Parameters", filters=f,
                               fields=[f"sum(`{fieldname}`) as val"])
        return (rows[0].val if rows else 0) or 0

    missing_fields = [
        cfg[key] for cfg in WIP_ITEM_FIELDS.values() for key in ("opening_field", "closing_field")
        if not meta.has_field(cfg[key])
    ]
    if missing_fields:
        frappe.log_error(
            title="DMR Report: missing fields on DMR Technical Lab Parameters",
            message=f"Fieldnames not found, check DocType JSON: {missing_fields}",
        )

    result = {}
    for item_code, cfg in WIP_ITEM_FIELDS.items():
        target_uom = target_uom_map.get(item_code)
        if not target_uom:
            continue
        opening_raw = sum_field_on_exact_date(cfg["opening_field"], from_date)
        closing_raw = sum_field_on_exact_date(cfg["closing_field"], to_date)
        result[item_code] = {
            "opening": convert_between_uoms(item_code, opening_raw, cfg["raw_uom"], target_uom),
            "closing": convert_between_uoms(item_code, closing_raw, cfg["raw_uom"], target_uom),
        }
    return result


# =============================================================================
# SECTIONS G, J, L, M — Boiler Performance / Section-wise Steam Consumed /
# Technical Parameters / Power
# Source: "DMR Boiler And Turbine Parameters" doctype (Company + Plant +
# Date, one record per plant per REPORT day). Filtered on the plain Date
# field — see the REPORT DAY WINDOW note at the top of this file.
#   - Flow/production quantities (steam, power) are SUMMED over the period.
#   - Instrument readings (boiler load/hr, ESP temp, unburnt ash %) are
#     AVERAGED over the period since summing them would be meaningless.
#   - Section J (Section wise Steam Consumed) fields are SUMMED — merged in
#     here since the old "DMR Process Data" doctype was deleted and its
#     fields moved onto this doctype (see PROCESS_DATA_SUM_FIELDS note above
#     for a flagged fieldname collision that needs confirming).
# =============================================================================
def get_boiler_turbine_parameters(companies, from_date, to_date, plants=None):
    if not frappe.db.exists("DocType", "DMR Boiler And Turbine Parameters"):
        return {}
    filters = {
        "company": ["in", companies],
        "date": ["between", [from_date, to_date]],
    }
    if plants:
        filters["plant"] = ["in", plants]
    sum_map = _existing_field_map("DMR Boiler And Turbine Parameters", BOILER_SUM_FIELD_MAP)
    avg_map = _existing_field_map("DMR Boiler And Turbine Parameters", BOILER_AVG_FIELD_MAP)
    process_fields = _existing_fields("DMR Boiler And Turbine Parameters", PROCESS_DATA_SUM_FIELDS)
    select_fields = (
        [f"sum(`{real}`) as {semantic}" for semantic, real in sum_map.items()]
        + [f"avg(`{real}`) as {semantic}" for semantic, real in avg_map.items()]
        + [f"sum(`{f}`) as {f}" for f in process_fields]
    )
    if not select_fields:
        return {}
    rows = frappe.get_all("DMR Boiler And Turbine Parameters", filters=filters, fields=select_fields)
    return rows[0] if rows else {}


# =============================================================================
# SECTION I — Steam Raising Ratio
# Source: "Steam Raising Ratio" doctype — a FIXED master (parent = Company,
# child table "Steam Ratio Item" = Plant + Item + Ratio). It does NOT depend
# on the report's date range, only on Company (and Plant, if filtered).
# Returns {item_code: ratio}. If more than one plant's ratio matches an item
# (e.g. no plant filter applied, or multiple plants selected), the ratios
# are AVERAGED — flag if you'd rather pick a specific plant's ratio instead.
# =============================================================================
def get_steam_raising_ratios(companies, plants=None):
    if not frappe.db.exists("DocType", "Steam Raising Ratio"):
        return {}
    required_cols = [("Steam Raising Ratio", "company"), ("Steam Ratio Item", "plant"),
                      ("Steam Ratio Item", "item"), ("Steam Ratio Item", "ratio")]
    missing = [f"{dt}.{col}" for dt, col in required_cols if not frappe.db.has_column(dt, col)]
    if missing:
        frappe.log_error(
            title="DMR Report: missing fields on Steam Raising Ratio",
            message=f"Fieldnames not found, check DocType JSON: {missing}",
        )
        return {}
    conditions = "srr.company in %(companies)s"
    values = {"companies": companies}
    if plants:
        conditions += " and sri.plant in %(plants)s"
        values["plants"] = plants
    rows = frappe.db.sql(f"""
        select sri.item, sri.ratio
        from `tabSteam Raising Ratio` srr
        inner join `tabSteam Ratio Item` sri on sri.parent = srr.name
        where {conditions}
    """, values, as_dict=1)
    item_ratios = defaultdict(list)
    for r in rows:
        item_ratios[r.item].append(r.ratio or 0)
    return {item: sum(vals) / len(vals) for item, vals in item_ratios.items()}


def safe_div(n, d):
    # SQL SUM()/AVG() over zero matching rows returns NULL -> None in Python,
    # not 0 -- so a dict .get(field, 0) default won't catch it (the key
    # exists, just with value None). Guard against that here rather than at
    # every call site.
    n = n or 0
    d = d or 0
    return (n / d) if d else 0


def _existing_fields(doctype, fieldnames):
    """
    Filter fieldnames down to ones that actually exist on the doctype, so a
    wrong fieldname guess (renamed/typo'd field) degrades to returning None
    for that one value instead of throwing an OperationalError and taking
    down the whole report. Logs a warning once per doctype per request so
    the gap is visible in the Error Log without blocking the page.
    """
    meta = frappe.get_meta(doctype)
    valid = [f for f in fieldnames if meta.has_field(f)]
    missing = [f for f in fieldnames if f not in valid]
    if missing:
        frappe.log_error(
            title=f"DMR Report: missing fields on {doctype}",
            message=f"Fieldnames not found, check DocType JSON: {missing}",
        )
    return valid


def _existing_field_map(doctype, field_map):
    """
    Same purpose as _existing_fields, but for doctypes where the real
    fieldname differs from our semantic key (e.g. auto-generated
    "float_zcpn" on DMR Boiler And Turbine Parameters). field_map is
    {semantic_key: real_fieldname}; returns only the entries that exist.
    """
    meta = frappe.get_meta(doctype)
    valid = {k: v for k, v in field_map.items() if meta.has_field(v)}
    missing = {k: v for k, v in field_map.items() if k not in valid}
    if missing:
        frappe.log_error(
            title=f"DMR Report: missing fields on {doctype}",
            message=f"Fieldnames not found, check DocType JSON: {missing}",
        )
    return valid


# =============================================================================
# SECTION TOTALS
# =============================================================================
def _add_section_totals(rows):
    """
    Post-process pass: after each section's data rows, insert one "Total"
    row per uom group, but only for groups with 2+ rows (a lone item's
    "total" is just itself). Excluded from totals: uom "%" or "Ratio", any
    uom containing "/" (BL/Qtl, MT/Hr, KG/BL, ...) -- these are computed
    ratios/percentages, not additive quantities -- and any row explicitly
    flagged exclude_from_total (e.g. M.6 Power Per BL, itself a rate
    derived from M.5, not an independent MW figure to add to the rest of
    Section M).

    Group membership is structural (based on each row's uom/section, not
    whether its value happens to be None on a given day) so the set of
    Total rows stays identical across the meta call and every date column
    -- if it were data-dependent, a day with missing boiler data could
    silently drop a Total row that meta already declared, and the frontend
    (which renders columns strictly by meta's row list) would just show a
    blank instead of a real zero.
    """
    result = []
    i, n = 0, len(rows)
    while i < n:
        header_row = rows[i]
        result.append(header_row)
        if not header_row.get("header"):
            i += 1
            continue

        j = i + 1
        while j < n and not rows[j].get("header"):
            j += 1
        section_rows = rows[i + 1:j]
        result.extend(section_rows)

        numeric_groups = defaultdict(list)
        dict_groups = defaultdict(list)
        for r in section_rows:
            uom = r.get("uom")
            if r.get("exclude_from_total") or not uom or uom == "%" or uom == "Ratio" or "/" in uom:
                continue
            val = r.get("value")
            if isinstance(val, dict):
                dict_groups[uom].append(val)
            else:
                numeric_groups[uom].append(val or 0)

        for uom, vals in numeric_groups.items():
            if len(vals) < 2:
                continue
            result.append({"sr": f"{header_row['sr']}.Total", "label": "Total", "uom": uom,
                            "value": sum(vals), "total": True})

        for uom, vals in dict_groups.items():
            if len(vals) < 2:
                continue
            result.append({
                "sr": f"{header_row['sr']}.Total", "label": "Total", "uom": uom,
                "value": {
                    "ideal": sum(v.get("ideal") or 0 for v in vals),
                    "actual": sum(v.get("actual") or 0 for v in vals),
                },
                "total": True,
            })

        i = j
    return result


def build_section_rows(companies, from_date, to_date, plants=None, segments=None):
    prod_codes = [r[0] for r in PRODUCTION_ITEMS]
    rm_codes = [r[0] for r in RM_ITEMS]
    by_codes = [r[0] for r in BYPRODUCT_ITEMS]
    fuel_codes = [r[0] for r in FUEL_ITEMS]

    prod_uom = {code: uom for code, _, _, uom in PRODUCTION_ITEMS}
    rm_uom = {code: uom for code, _, _, uom in RM_ITEMS}
    by_uom = {code: uom for code, _, _, uom in BYPRODUCT_ITEMS}
    fuel_uom = {code: uom for code, _, _, uom in FUEL_ITEMS}

    # Raw fetch (stock UOM) then convert to each row's display UOM.
    prod = convert_qty_dict(get_production_qty(companies, from_date, to_date, prod_codes, plants, segments), prod_uom)
    rm_gross = convert_qty_dict(get_issue_qty(companies, from_date, to_date, rm_codes, plants, segments), rm_uom)
    by = convert_qty_dict(get_production_qty(companies, from_date, to_date, by_codes, plants, segments), by_uom)
    fuel = convert_qty_dict(get_issue_qty(companies, from_date, to_date, fuel_codes, plants, segments), fuel_uom)

    # Section B is "Net of WIP": net_consumed = gross_issued + opening - closing.
    # See get_wip_opening_closing for how opening/closing are resolved and
    # converted into each item's display UOM (rm_uom).
    wip = get_wip_opening_closing(companies, from_date, to_date, rm_uom, plants)
    rm = {
        code: rm_gross.get(code, 0) + wip.get(code, {}).get("opening", 0) - wip.get(code, {}).get("closing", 0)
        for code in rm_codes
    }

    maize_prod = prod.get("100114", 0) + prod.get("100122", 0) + prod.get("100130", 0)
    dfg_prod = prod.get("100112", 0) + prod.get("100120", 0) + prod.get("100128", 0)
    fci_prod = prod.get("100113", 0)
    total_production_bl = maize_prod + dfg_prod + fci_prod

    maize_rm = rm.get("106444", 0)
    dfg_rm = rm.get("100474", 0)
    fci_rm = rm.get("106448", 0)
    total_rm = maize_rm + dfg_rm + fci_rm

    dwgs_maize, dwgs_dfg, dwgs_fci = by.get("100151", 0), by.get("100149", 0), by.get("100150", 0)
    ddgs_maize, ddgs_dfg, ddgs_fci = by.get("100147", 0), by.get("100145", 0), by.get("100146", 0)
    crude_oil = by.get("129946", 0)

    rows = []

    # --- SECTION A: Production of Finished Goods -- Stock Entry (Material Receipt) ---
    rows.append({"sr": "A", "label": "Production of Finished Goods", "header": True})
    for code, label, sr, uom in PRODUCTION_ITEMS:
        rows.append({"sr": sr, "label": label, "uom": uom, "value": prod.get(code, 0), "item_code": code})

    # --- SECTION B: Consumption of Raw Material -- Stock Entry (Material Issue),
    # netted against WIP opening/closing balances (see rm computation above) ---
    rows.append({"sr": "B", "label": "Consumption of Raw Material", "header": True})
    for code, label, sr, uom in RM_ITEMS:
        rows.append({"sr": sr, "label": label, "uom": uom, "value": rm.get(code, 0), "item_code": code})

    # --- SECTION C: Recovery of Finished Goods -- calculated, A / B ---
    rows.append({"sr": "C", "label": "Recovery of Finished Goods", "header": True})
    rows.append({"sr": "C.1", "label": "Recovery from Maize", "uom": "BL/Qtl", "value": safe_div(maize_prod, maize_rm)})
    rows.append({"sr": "C.2", "label": "Recovery from DFG", "uom": "BL/Qtl", "value": safe_div(dfg_prod, dfg_rm)})
    rows.append({"sr": "C.3", "label": "Recovery from FCI Rice", "uom": "BL/Qtl", "value": safe_div(fci_prod, fci_rm)})

    # --- SECTION D: Fermentation Parameters -- DMR Technical Lab Parameters (averaged) ---
    rows.append({"sr": "D", "label": "Fermentation Parameters", "header": True})
    lab = get_lab_parameters(companies, from_date, to_date, plants)
    for sr, label, field in [
        ("D.1", "Alcohol Percentage", "alcohol_percentage"),
        ("D.2", "Fermenter -RS", "fermenter_rs"),
        ("D.3", "Fermenter -RST", "fermenter_rst"),
        ("D.4", "Average Starch - Maize", "average_starch_maize"),
        ("D.5", "Average Starch - DFG", "average_starch_dfg"),
        ("D.6", "Average Starch - FCI", "average_starch_fci"),
    ]:
        rows.append({"sr": sr, "label": label, "uom": "%", "value": lab.get(field)})

    # --- SECTION E: Production of By Products -- Stock Entry (Material Receipt) ---
    rows.append({"sr": "E", "label": "Production of by Products", "header": True})
    for code, label, sr, uom in BYPRODUCT_ITEMS:
        rows.append({"sr": sr, "label": label, "uom": uom, "value": by.get(code, 0), "item_code": code})

    # --- SECTION F: Recovery of By Products -- calculated, mixed formulas per item ---
    # This is NOT a uniform pattern across rows -- confirmed per-item:
    #   F.1 DWGS from Maize = (Ethanol+ENA+RS from Maize) / DWGS from Maize   (FG production / byproduct)
    #   F.2 DWGS from DFG   = DWGS from DFG produced / DFG Consumed (RM)      (byproduct / RM)
    #   F.3 DWGS from FCI   = DWGS from FCI produced / FCI net consumed (RM) (byproduct / RM)
    #   F.4 Average DWGS    = total DWGS produced / total RM consumed        (byproduct / RM)
    #   F.5-F.8 same pattern as F.1-F.4, for DDGS
    #   F.9 Crude Corn Oil  = Crude Corn Oil produced / Maize Consumed (RM) -- note: against
    #                          Maize RM specifically, not total RM
    # None of the above were specified as a "%", so these are left as plain
    # ratios (uom reflects the actual units involved -- BL/Qtl where FG
    # production is the numerator, Qtl/Qtl or Ltr/Qtl otherwise). Multiply
    # by 100 on the frontend if you want these displayed as percentages.
    rows.append({"sr": "F", "label": "Recovery of By Products", "header": True})
    rows.append({"sr": "F.1", "label": "DWGS from Maize", "uom": "BL/Qtl", "value": safe_div(maize_prod, dwgs_maize)})
    rows.append({"sr": "F.2", "label": "DWGS from DFG", "uom": "Qtl/Qtl", "value": safe_div(dwgs_dfg, dfg_rm)})
    rows.append({"sr": "F.3", "label": "DWGS from FCI", "uom": "Qtl/Qtl", "value": safe_div(dwgs_fci, fci_rm)})
    rows.append({"sr": "F.4", "label": "Average DWGS", "uom": "Qtl/Qtl", "value": safe_div(dwgs_maize + dwgs_dfg + dwgs_fci, total_rm)})
    rows.append({"sr": "F.5", "label": "DDGS from Maize", "uom": "BL/Qtl", "value": safe_div(maize_prod, ddgs_maize)})
    rows.append({"sr": "F.6", "label": "DDGS from DFG", "uom": "Qtl/Qtl", "value": safe_div(ddgs_dfg, dfg_rm)})
    rows.append({"sr": "F.7", "label": "DDGS from FCI", "uom": "Qtl/Qtl", "value": safe_div(ddgs_fci, fci_rm)})
    rows.append({"sr": "F.8", "label": "Average DDGS", "uom": "Qtl/Qtl", "value": safe_div(ddgs_maize + ddgs_dfg + ddgs_fci, total_rm)})
    rows.append({"sr": "F.9", "label": "Crude Corn Oil", "uom": "Ltr/Qtl", "value": safe_div(crude_oil, maize_rm)})

    # --- SECTION G: Boiler Performance -- DMR Boiler And Turbine Parameters (summed) ---
    rows.append({"sr": "G", "label": "Boiler Performance", "header": True})
    boiler = get_boiler_turbine_parameters(companies, from_date, to_date, plants)
    for sr, label, field in [
        ("G.1", "Steam produced", "steam_produced"),
        ("G.2", "Steam Purchased", "steam_purchased"),
        ("G.3", "Steam consumed Through PRDS", "steam_consumed_through_prds"),
        ("G.4", "Steam Used Through Turbine", "steam_used_through_turbine"),
    ]:
        rows.append({"sr": sr, "label": label, "uom": "MT", "value": boiler.get(field)})

    # --- SECTION H: Fuel used for Boiler -- Stock Entry (Material Issue) ---
    rows.append({"sr": "H", "label": "Fuel used for Boiler", "header": True})
    for code, label, sr, uom in FUEL_ITEMS:
        rows.append({"sr": sr, "label": label, "uom": uom, "value": fuel.get(code, 0), "item_code": code})

    # --- SECTION I: Steam Raising Ratio -- Steam Raising Ratio master (fixed, not date-dependent) ---
    # I.9 Weighted Average = sum(ratio_i * fuel_qty_i) / sum(fuel_qty_i), weighted by Section H quantities.
    rows.append({"sr": "I", "label": "Steam Raising Ratio", "header": True})
    ratios = get_steam_raising_ratios(companies, plants)
    weighted_num, weighted_den = 0, 0
    for i, (code, label, sr, uom) in enumerate(FUEL_ITEMS):
        ratio = ratios.get(code)
        rows.append({"sr": f"I.{i+1}", "label": label, "uom": "Ratio", "value": ratio, "item_code": code})
        qty = fuel.get(code, 0)
        if ratio is not None and qty:
            weighted_num += ratio * qty
            weighted_den += qty
    rows.append({
        "sr": "I.9", "label": "Weighted Average", "uom": "Ratio",
        "value": safe_div(weighted_num, weighted_den) if weighted_den else None,
    })

    # Reverse-calculate the "ideal" stock per fuel at the fixed standard
    # ratio, shown alongside the actual stock consumed (Section H) in the
    # SAME row for direct comparison (value is a dict: {ideal, actual}
    # instead of a plain number, since this row carries two figures).
    # Total Steam Produced (G.1) is a single boiler-wide figure -- it isn't
    # broken down per fuel -- so per your confirmation it's allocated across
    # fuels proportionally to each fuel's actual share of total fuel
    # consumed, by weight:
    #   allocated_steam_i = total_steam_produced * (actual_qty_i / total_fuel_qty)
    #   ideal_stock_i      = allocated_steam_i / standard_ratio_i
    total_fuel_qty = sum(fuel.get(code, 0) for code, _, _, _ in FUEL_ITEMS)
    total_steam_produced = boiler.get("steam_produced") or 0

    rows.append({"sr": "I", "label": "Standard vs Actual Stock Consumed (at standard ratio)", "header": True})
    for i, (code, label, sr, uom) in enumerate(FUEL_ITEMS):
        ratio = ratios.get(code)
        actual_qty = fuel.get(code, 0)
        allocated_steam = safe_div(total_steam_produced * actual_qty, total_fuel_qty)
        ideal_qty = safe_div(allocated_steam, ratio) if ratio else None
        rows.append({
            "sr": f"I.{11 + i}", "label": label, "uom": uom,
            "value": {"ideal": ideal_qty, "actual": actual_qty},
            "item_code": code,
        })

    # --- SECTIONS J & K: Section-wise Steam Consumed (+ per BL) ---
    # J now comes from the same "boiler" dict fetched above for Section G/L/M
    # -- "DMR Process Data" was deleted and its fields merged onto
    # "DMR Boiler And Turbine Parameters", so it's the same query/date-range,
    # no need to hit the DB again separately.
    process = boiler

    rows.append({"sr": "J", "label": "Section wise Steam Consumed", "header": True})
    for i, (field, label) in enumerate(PROCESS_DATA_FIELDS):
        rows.append({"sr": f"J.{i+1}", "label": label, "uom": "MT", "value": process.get(field)})

    rows.append({"sr": "K", "label": "Section wise Steam Consumed per BL", "header": True})
    for i, (field, label) in enumerate(PROCESS_DATA_FIELDS):
        mt_val = process.get(field)
        kg_per_bl = safe_div(mt_val * 1000, total_production_bl) if mt_val is not None else None
        rows.append({"sr": f"K.{i+1}", "label": label, "uom": "KG/BL", "value": kg_per_bl})

    # --- SECTION L: Technical Parameters Of Boiler & Turbine -- DMR Boiler And Turbine Parameters (averaged) ---
    rows.append({"sr": "L", "label": "Technical Parameters Of Boiler & Turbine", "header": True})
    for sr, label, uom, field in [
        ("L.1", "Bolier Load Per Hour", "MT/Hr", "bolier_load_per_hour"),
        ("L.2", "ESP Outlet Temp", "Degree", "esp_outlet_temp"),
        ("L.3", "Unburnt Ash %", "%", "unburnt_ash"),
    ]:
        rows.append({"sr": sr, "label": label, "uom": uom, "value": boiler.get(field)})

    # --- SECTION M: Power Performance -- DMR Boiler And Turbine Parameters (summed) ---
    # M.6 Power Per BL is CALCULATED (not read directly) as
    # sum(power_consumed) over the period / total finished-goods production (BL),
    # so it stays consistent with whatever plant/date filters are applied,
    # rather than trusting a possibly-stale stored value on each record.
    # It's excluded from the section Total since it's a rate derived from
    # M.5 (Power Consumed), not an independent MW figure to add.
    rows.append({"sr": "M", "label": "Power Performance", "header": True})
    for sr, label, field in [
        ("M.1", "Power Generation", "power_generation"),
        ("M.2", "Power Purchased", "power_purchased"),
        ("M.3", "Power Export", "power_export"),
        ("M.4", "Power Sales", "power_sales"),
        ("M.5", "Power Consumed", "power_consumed"),
    ]:
        rows.append({"sr": sr, "label": label, "uom": "MW", "value": boiler.get(field)})
    rows.append({
        "sr": "M.6", "label": "Power Per BL", "uom": "MW",
        "value": safe_div(boiler.get("power_consumed", 0), total_production_bl),
        "exclude_from_total": True,
    })

    # --- SECTION N: Stock -- Stock Ledger Entry (latest balance as of to_date) ---
    rows.append({"sr": "N", "label": "Stock", "header": True})
    stock = convert_qty_dict(
        get_stock_balance(companies, to_date, STOCK_ITEMS),
        {code: STOCK_UOM for code in STOCK_ITEMS},
    )
    wash_available = get_wash_available(companies, to_date, plants)
    rows.append({
        "sr": "N.1", "label": "Wash Available", "uom": "Ltrs", "value": wash_available,
        # WIP fermentation broth, not a finished-goods stock balance like
        # N.2-N.11 -- excluded so it doesn't get summed into the Section N
        # Total alongside Ethanol/ENA/RS/DDGS/DWGS/Crude Oil stock.
        "exclude_from_total": True,
    })
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

    return _add_section_totals(rows)


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
            "total": r.get("total", False),
        }
        for r in meta_rows
    ]

    columns = []
    for dt in date_list:
        rows = build_section_rows(companies, dt, dt, plants, segments)
        columns.append({"label": formatdate(dt, "dd/mm/yy"), "values": {r["sr"]: r.get("value") for r in rows}})

    todate_rows = build_section_rows(companies, fy_start, to_date, plants, segments)
    # Show the actual date range this "To Date" column covers (fiscal-year
    # start through the selected to_date) rather than a bare "To Date" label.
    todate_label = f"To Date ({formatdate(fy_start, 'dd/mm/yy')} - {formatdate(to_date, 'dd/mm/yy')})"
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