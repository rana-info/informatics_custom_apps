# Copyright (c) 2026, Rana Informatics and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, add_days, cstr
from collections import defaultdict
from erpnext.stock.get_item_details import get_conversion_factor

# =============================================================================
# REPORT DAY WINDOW
# =============================================================================
# Same convention as dmr.py: Stock Entry has a real posting timestamp, so a
# fuel issue at 2:00 AM belongs to the PREVIOUS report day (shift boundary
# 06:00). "DMR Boiler And Turbine Parameters" is a per-day master (one row
# per plant per report day against a plain Date field) so it needs no
# shifting -- its date filter is a plain `between`.
# =============================================================================
DAY_START_TIME = "06:00:00"

# NOTE: "Plant" is labeled/translated as "Plant" in the UI but the real
# fieldname on Stock Entry is "branch" (Branch doctype) -- same as dmr.py.
PLANT_FIELD = "branch"


def get_report_datetime_range(from_date, to_date, day_start_time=DAY_START_TIME):
    from_dt = f"{getdate(from_date)} {day_start_time}"
    to_dt = f"{add_days(getdate(to_date), 1)} {day_start_time}"
    return from_dt, to_dt


# =============================================================================
# FUEL COLUMN -> ITEM CODE MAP
# =============================================================================
# Confirmed:
#   Coal      -> all 5 "Power & Fuel" coal-type items (Item List screenshot):
#                Indian Coal (136001), Coal (115566), Imported Indonesian
#                Coal (118488), Charcoal (101192), Steam Coal Powder (129549)
#   Paddy     -> 106441   (matches FUEL_ITEMS in dmr.py)
#   Mustard   -> 106440   (Mustard Husk, matches FUEL_ITEMS in dmr.py)
#   Bagasse   -> 100093   (matches FUEL_ITEMS in dmr.py)
#
# TODO / UNCONFIRMED (flagged, defaulting for now -- update when confirmed):
#   Husk      -> defaulted to Rice Husk only (106436). If "Husk" on the
#                Excel is meant to also include Mandi Husk (106442), add it
#                to the list below.
#   Trash     -> defaulted to Cane Trash only (101077).
#   Corn Cob  -> NO item code identified yet. Left as an empty list, which
#                means this column will always compute to 0 until an item
#                code is supplied.
# =============================================================================
FUEL_COLUMN_ITEM_MAP = {
    "coal":     ["136001", "115566", "118488", "101192", "129549"],
    "paddy":    ["106441"],
    "husk":     ["106436"],           # TODO confirm: Rice Husk only, or + Mandi Husk (106442)?
    "trash":    ["101077"],           # Cane Trash
    "mustard":  ["106440"],           # Mustard Husk
    "corn_cob": [],                    # TODO: item code not yet identified
    "bagasse":  ["100093"],
}

FUEL_COLUMNS_ORDER = ["coal", "paddy", "husk", "trash", "mustard", "corn_cob", "bagasse"]

FUEL_COLUMN_LABELS = {
    "coal": "Coal",
    "paddy": "Paddy",
    "husk": "Husk",
    "trash": "Trash",
    "mustard": "Mustard",
    "corn_cob": "Corn Cob",
    "bagasse": "Bagasse",
}

# Reverse lookup: item_code -> fuel_column, built once at import time.
_ITEM_TO_COLUMN = {}
for _col, _items in FUEL_COLUMN_ITEM_MAP.items():
    for _item in _items:
        _ITEM_TO_COLUMN[_item] = _col

ALL_FUEL_ITEM_CODES = list(_ITEM_TO_COLUMN.keys())

# =============================================================================
# ITEM -> STOCK-UOM-TO-MT CONVERSION FACTOR
# =============================================================================
# Applied on top of conversion_factor (which only converts the transaction
# UOM -> stock UOM). This second factor converts stock UOM -> MT so the
# report's fuel columns are always true metric tons.
#
# CONFIRMED:
#   Charcoal (101192) and Steam Coal Powder (129549) are stocked in KGS per
#   the Item List screenshot -> factor 0.001.
#
# ASSUMED (not yet confirmed against the Item master -- defaulted to 1,
# i.e. "already in MT". If any of these turn out to be stocked in KGS,
# Quintal, or another unit, update the factor below):
#   Indian Coal (136001), Coal (115566), Imported Indonesian Coal (118488),
#   Paddy (106441), Rice Husk (106436), Cane Trash (101077),
#   Mustard Husk (106440), Bagasse (100093)
# =============================================================================
ITEM_TO_MT_FACTOR = {
    "136001": 0.1,      # Indian Coal - Quintal
    "115566": 0.001,    # Coal - KGS
    "118488": 0.1,      # Imported Indonesian Coal - Quintal
    "101192": 0.001,    # Charcoal - KGS
    "129549": 0.001,    # Steam Coal Powder - KGS
    "106441": 0.001,    # Paddy - KGS
    "106436": 0.001,    # Rice Husk - KGS
    "101077": 0.1,      # Cane Trash - Quintal
    "106440": 0.001,    # Mustard Husk - KGS
    "100093": 0.001,    # Bagasse - KGS
}

# Boiler doctype fieldname -- confirmed from "DMR Boiler And Turbine
# Parameters" DocType JSON (auto-generated name, same as dmr.py's
# BOILER_SUM_FIELD_MAP).
STEAM_PRODUCED_FIELD = "float_zcpn"     # "Steam Produced"
# Avg Boiler Load per Hour = Total Steam Generated for that report day / 24
# hours -- calculated, not read from a stored field.


def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    columns = [
        {"label": "Date", "fieldname": "date", "fieldtype": "Data", "width": 100},
        {"label": "Boiler Section", "fieldname": "boiler_section", "fieldtype": "Data", "width": 160},
        {"label": "Total Steam Generated", "fieldname": "steam_generated", "fieldtype": "Float", "width": 180,
         "precision": 2},
        {"label": "Avg. Boiler Load per Hour", "fieldname": "avg_boiler_load", "fieldtype": "Float", "width": 200,
         "precision": 2},
    ]
    for col in FUEL_COLUMNS_ORDER:
        columns.append({
            "label": FUEL_COLUMN_LABELS[col], "fieldname": f"{col}_mt", "fieldtype": "Float",
            "width": 100, "precision": 2,
        })
    columns.append({"label": "Total Fuel", "fieldname": "total_fuel_mt", "fieldtype": "Float", "width": 110,
                     "precision": 2})
    for col in FUEL_COLUMNS_ORDER:
        columns.append({
            "label": f"{FUEL_COLUMN_LABELS[col]} %", "fieldname": f"{col}_pct", "fieldtype": "Percent",
            "width": 110, "precision": 1,
        })
    return columns


def get_data(filters):
    from_date = getdate(filters.get("from_date") or add_days(getdate(), -7))
    to_date = getdate(filters.get("to_date") or getdate())

    # Rows are the UNION of (plant, date) combos from both sources -- a row
    # shows up if EITHER a Steam Produced entry OR a Material Issue fuel
    # entry exists for that plant+date, not just when both do. Where one
    # side is missing, that side's figures just come back as 0.
    boiler_by_plant_date = get_boiler_data_by_plant_date(from_date, to_date)
    fuel_by_plant_date = get_fuel_qty_by_plant_date(from_date, to_date)

    if not boiler_by_plant_date and not fuel_by_plant_date:
        return []

    # Index fuel data by (date, normalized_plant_name) too, so a boiler
    # plant "RSL Belwara" still finds fuel booked against a slightly
    # differently-formatted branch value ("RSL Belwara ", "rsl belwara",
    # etc). Exact key is tried first; normalized is the fallback.
    fuel_by_normalized = {}
    for (dt, plant), fuel in fuel_by_plant_date.items():
        fuel_by_normalized.setdefault((dt, _normalize_plant(plant)), fuel)

    # Build the combined key set: every boiler key, plus every fuel key
    # that doesn't already match a boiler key under normalized comparison
    # (avoids a duplicate row for the same plant shown twice under two
    # slightly different text spellings).
    boiler_normalized_keys = {(dt, _normalize_plant(plant)) for (dt, plant) in boiler_by_plant_date}
    combined_keys = set(boiler_by_plant_date.keys())
    for (dt, plant) in fuel_by_plant_date.keys():
        if (dt, _normalize_plant(plant)) not in boiler_normalized_keys:
            combined_keys.add((dt, plant))

    rows = []
    for dt, plant in sorted(combined_keys, key=lambda k: (k[0], k[1])):
        boiler = boiler_by_plant_date.get((dt, plant))
        fuel = fuel_by_plant_date.get((dt, plant)) or fuel_by_normalized.get((dt, _normalize_plant(plant)), {})
        total_fuel = sum(fuel.get(col, 0) for col in FUEL_COLUMNS_ORDER)

        row = {
            "date": dt.strftime("%d/%m/%Y"),
            "boiler_section": plant,
            "steam_generated": (boiler or {}).get("steam_generated") or 0,
            "avg_boiler_load": (boiler or {}).get("avg_boiler_load") or 0,
            "total_fuel_mt": total_fuel,
        }
        for col in FUEL_COLUMNS_ORDER:
            qty = fuel.get(col, 0)
            row[f"{col}_mt"] = qty
            row[f"{col}_pct"] = (qty / total_fuel * 100) if total_fuel else 0

        rows.append(row)

    return rows


# =============================================================================
# STEAM GENERATED / AVG BOILER LOAD per plant per report-day
# Source: "DMR Boiler And Turbine Parameters" -- one row per plant per
# report day against a plain Date field, so no timestamp shifting needed
# (same note as dmr.py). Only rows where Steam Produced has actually been
# entered (not null) are returned -- this is what drives which plant+date
# combinations appear on the report at all.
# =============================================================================
def get_boiler_data_by_plant_date(from_date, to_date):
    if not frappe.db.exists("DocType", "DMR Boiler And Turbine Parameters"):
        return {}

    meta = frappe.get_meta("DMR Boiler And Turbine Parameters")
    if not meta.has_field(STEAM_PRODUCED_FIELD):
        frappe.log_error(
            title="Boiler Section Fuel Consumption: missing field",
            message=f"Expected field not found on DMR Boiler And Turbine Parameters: '{STEAM_PRODUCED_FIELD}'",
        )
        return {}

    rows = frappe.db.sql(f"""
        select plant, date, `{STEAM_PRODUCED_FIELD}` as steam_generated
        from `tabDMR Boiler And Turbine Parameters`
        where date between %(from_date)s and %(to_date)s
            and `{STEAM_PRODUCED_FIELD}` is not null
            and plant is not null and plant != ''
    """, {"from_date": from_date, "to_date": to_date}, as_dict=1)

    result = {}
    for r in rows:
        steam = r.steam_generated or 0
        key = (getdate(r.date), r.plant)
        # If more than one record exists for the same plant+date, sum steam.
        if key in result:
            result[key]["steam_generated"] += steam
        else:
            result[key] = {"steam_generated": steam}

    for v in result.values():
        # Avg Boiler Load per Hour = Total Steam Generated / 24 hrs.
        v["avg_boiler_load"] = v["steam_generated"] / 24

    return result


# =============================================================================
# FUEL QUANTITY per plant per report-day
# Source: Stock Entry (Material Issue) + Stock Entry Detail, same source as
# dmr.py's get_issue_qty for Section H -- but calculated separately (two
# independent queries, no SQL join) per your instruction. No company/plant
# filter -- queried across everything in the date range, then matched to
# whatever plants have a Steam Produced entry.
#
# Quantities are pulled in each item's STOCK UOM (via conversion_factor),
# then converted stock UOM -> MT using ITEM_TO_MT_FACTOR above, so every
# fuel column is reported in true metric tons regardless of how each item
# is actually stocked (e.g. Charcoal/Steam Coal Powder are KGS, not MT).
# =============================================================================
def get_fuel_qty_by_plant_date(from_date, to_date):
    if not ALL_FUEL_ITEM_CODES:
        return {}

    from_dt, to_dt = get_report_datetime_range(from_date, to_date)

    # Query 1: Stock Entry headers only.
    headers = frappe.db.sql(f"""
        select name, {PLANT_FIELD} as plant, posting_date, posting_time
        from `tabStock Entry`
        where docstatus = 1
            and stock_entry_type = 'Material Issue'
            and timestamp(posting_date, posting_time) >= %(from_dt)s
            and timestamp(posting_date, posting_time) < %(to_dt)s
    """, {"from_dt": from_dt, "to_dt": to_dt}, as_dict=1)

    if not headers:
        return {}

    header_by_name = {h.name: h for h in headers}

    # Query 2: Stock Entry Detail rows for those parents, independently.
    details = frappe.db.sql("""
        select parent, item_code, qty, conversion_factor
        from `tabStock Entry Detail`
        where parent in %(parents)s
            and item_code in %(items)s
    """, {"parents": list(header_by_name.keys()), "items": ALL_FUEL_ITEM_CODES}, as_dict=1)

    result = defaultdict(lambda: defaultdict(float))
    for d in details:
        header = header_by_name.get(d.parent)
        if not header or not header.plant:
            continue
        col = _ITEM_TO_COLUMN.get(d.item_code)
        if not col:
            continue
        report_date = _report_date(header.posting_date, header.posting_time)
        # conversion_factor: transaction UOM -> stock UOM.
        # ITEM_TO_MT_FACTOR: stock UOM -> MT.
        qty = (d.qty or 0) * (d.conversion_factor or 1) * ITEM_TO_MT_FACTOR.get(d.item_code, 1)
        result[(report_date, header.plant)][col] += qty

    return result


def _normalize_plant(name):
    return (name or "").strip().lower()


def _report_date(posting_date, posting_time, day_start_time=DAY_START_TIME):
    """Mirror of dmr.py's report-day shift, applied per-row instead of as a
    SQL range (needed here since results are bucketed by day, not just
    filtered by a single range)."""
    posting_date = getdate(posting_date)
    if cstr(posting_time) < day_start_time:
        return add_days(posting_date, -1)
    return posting_date