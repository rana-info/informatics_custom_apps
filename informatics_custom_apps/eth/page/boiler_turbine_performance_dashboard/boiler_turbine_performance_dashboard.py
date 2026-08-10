import frappe

# Master list of known DMR parameters. Used as the base row-set for the
# "Key Operational Parameters" table so a row still shows (with Total
# pulled from the parent doc) even when the child table has no matching
# row yet. Any fieldname found in the child table but missing here is
# appended automatically at render time.
#
# NOTE: this is a partial list - extend with the remaining parameters
# from your field_tag_map before relying on this in production.
FIELD_TAG_MAP = {
    "float_zcpn": {"tag": "FT302", "label": "Steam Produced", "agg": "sum"},
    "float_pvrh": {"tag": "EKW2000", "label": "Power Generation", "agg": "sum"},
    "float_reke": {"tag": "TE414", "label": "ESP Outlet Temp", "agg": "avg"},
    "deaerator": {"tag": "FT102", "label": "Deartor", "agg": "sum"},
    "main_steam_pressure": {"tag": "PT302", "label": "Main Steam Pressure", "agg": "avg"},
    "main_steam_temprature": {"tag": "TT303", "label": "Main Steam Temprature", "agg": "avg"},
    "oxygen__at_eco_ol": {"tag": "AT401", "label": "Oxygen % At Eco O/L", "agg": "avg"},
    "boiler_feed_water_flow": {"tag": "FT301", "label": "Boiler Feed Water Flow", "agg": "sum"},
    "dm_flow_to_dearator": {"tag": "FT101", "label": "DM Flow To Dearator", "agg": "sum"},
    "turbine_steam": {"tag": "FT2001", "label": "Turbine Steam", "agg": "sum"}
}


# Fixed item codes for the single-item fuel categories.
FUEL_ITEM_CODES = {
    "Paddy": "106441",
    "Husk": "106436",
    "Mustard": "106440"
}

# Coal isn't a single item code - there can be several coal items in the
# system. Resolved dynamically at render time via item_group + name match,
# and all matching item codes are aggregated into ONE "Coal" row.
COAL_ITEM_GROUP = "Power & Fuel"
COAL_NAME_MATCH = "%coal%"


# Maps generic parameter name -> actual Power Plant Log Book fieldname,
# per section. "Power Plant Log Norms" stores norms against these exact
# fieldnames (ph, ph1, ph2, conductivity, conductivity1, ...).
SECTION_FIELD_MAP = {
    "Feed Water": {
        "ph": "ph",
        "conductivity": "conductivity",
        "silica": "silica"
    },
    "Boiler Water": {
        "ph": "ph1",
        "conductivity": "conductivity1",
        "silica": "silica1"
    },
    "Steam": {
        "ph": "ph2",
        "conductivity": "conductivity2",
        "silica": "silica2"
    }
}


@frappe.whitelist()
def get_dashboard(date):

    norms = get_norms()

    log_rows = frappe.get_all(
        "Power Plant Log Book",
        filters={
            "log_date": date,

        },
        or_filters=[
        ["ph", "!=", 0],
        ["ph1", "!=", 0],
        ["ph2", "!=", 0],
        ["conductivity", "!=", 0],
        ["conductivity1", "!=", 0],
        ["conductivity2", "!=", 0],
        ["silica", "!=", 0],
        ["silica1", "!=", 0],
        ["silica2", "!=", 0],
    ],
        fields=[
            "name",
            "plant"
        ]
    )

    log_map = {row.plant: row.name for row in log_rows}

    dmr_parent_rows = frappe.get_all(
        "DMR Boiler And Turbine Parameters",
        filters={
            "date": date
        },
        or_filters=[
        ["float_zcpn", "!=", 0],
        ["float_pvrh", "!=", 0],
        ["float_reke", "!=", 0],
        ["deaerator", "!=", 0],
        ["main_steam_pressure", "!=", 0],
        ["main_steam_temprature", "!=", 0],
        ["oxygen__at_eco_ol", "!=", 0],
        ["boiler_feed_water_flow", "!=", 0],
        ["dm_flow_to_dearator", "!=", 0],
        ["turbine_steam", "!=", 0],
        ],
        fields=[
            "plant"
        ]
    )

    dmr_plant_set = {row.plant for row in dmr_parent_rows}

    all_plants = sorted(set(log_map.keys()) | dmr_plant_set)

    plants = []

    for plant_name in all_plants:

        feed_water = {
            "ph": [],
            "conductivity": [],
            "silica": []
        }

        boiler_water = {
            "ph": [],
            "conductivity": [],
            "silica": []
        }

        steam = {
            "ph": [],
            "conductivity": [],
            "silica": []
        }

        if plant_name in log_map:

            doc = frappe.get_doc(
                "Power Plant Log Book",
                log_map[plant_name]
            )

            for row in doc.logs:

                add_value(feed_water["ph"], row.ph)
                add_value(feed_water["conductivity"], row.conductivity)
                add_value(feed_water["silica"], row.silica)

                add_value(boiler_water["ph"], row.ph1)
                add_value(boiler_water["conductivity"], row.conductivity1)
                add_value(boiler_water["silica"], row.silica1)

                add_value(steam["ph"], row.ph2)
                add_value(steam["conductivity"], row.conductivity2)
                add_value(steam["silica"], row.silica2)

        plants.append({

            "plant": plant_name,

            "feed_water": calculate_section(feed_water, norms, SECTION_FIELD_MAP["Feed Water"]),

            "boiler_water": calculate_section(boiler_water, norms, SECTION_FIELD_MAP["Boiler Water"]),

            "steam": calculate_section(steam, norms, SECTION_FIELD_MAP["Steam"]),

            "dmr": get_dmr_data(plant_name, date),

            "fuel": get_fuel_data(plant_name, date)

        })

    return {

        "date": date,

        "plants": plants

    }


def get_norms():
    """
    Returns a FLAT dict keyed by the exact Power Plant Log Book fieldname
    (matches what's stored in Power Plant Log Norms.fieldname):
    {
        "ph":            {"unit": "", "min": 8.8, "max": 9.2},
        "conductivity":  {"unit": "µS/cm", "min": 0, "max": 5},
        "silica":        {...},
        "ph1":           {...},   # boiler water ph
        "conductivity1": {...},
        "silica1":       {...},
        "ph2":           {...},   # steam ph
        "conductivity2": {...},
        "silica2":       {...},
    }
    """

    rows = frappe.get_all(
        "Power Plant Log Norms",
        filters={
            "parent": "ETH Logbook Norms",
            "parenttype": "ETH Logbook Norms",
            "parentfield": "power_plant_log_norms",
            "enabled": 1
        },
        fields=[
            "fieldname",
            "unit",
            "min_value",
            "max_value"
        ]
    )

    norms = {}

    for row in rows:
        norms[row.fieldname] = {
            "unit": row.unit,
            "min": row.min_value,
            "max": row.max_value
        }

    return norms

def round_value(value):
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (ValueError, TypeError):
        return value


def format_time(value):
    if not value:
        return None

    try:
        # datetime.time object
        return value.strftime("%H:%M")
    except AttributeError:
        pass

    try:
        # string values
        parts = str(value).split(":")
        return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
    except Exception:
        return value

def get_dmr_data(plant, date):
    """
    Returns one row per known DMR parameter (from FIELD_TAG_MAP, plus any
    extra fieldname found in the child table that isn't in the map).

    For each parameter:
    - If a matching "DMR Parameters Range" child row exists, its
      max/min/avg/time values are used.
    - "total" is only populated for FIELD_TAG_MAP parameters marked
      "agg": "sum" - pulled straight off the parent doc at the same
      fieldname, regardless of whether a child row exists (this is what
      lets Total show up even when the child table hasn't been filled
      in). Parameters marked "agg": "avg" (temperature, pressure, %)
      always get total = None, since summing/totaling an average-type
      reading is meaningless even if the parent doc has a value there.
      Fieldnames not in FIELD_TAG_MAP at all (only seen in child data)
      default to getting a Total, since their agg type is unknown.

    If no parent record exists for this plant + date at all, returns [].
    """

    parents = frappe.get_all(
        "DMR Boiler And Turbine Parameters",
        filters={
            "plant": plant,
            "date": date
        },
        fields=["name"]
    )

    if not parents:
        return []

    dmr_rows = []

    for parent in parents:

        parent_doc = frappe.get_doc(
            "DMR Boiler And Turbine Parameters",
            parent.name
        )

        child_rows = frappe.get_all(
            "DMR Parameters Range",
            filters={
                "parent": parent.name,
                "parenttype": "DMR Boiler And Turbine Parameters"
            },
            fields=[
                "parameter_name",
                "field_name",
                "engg_units",
                "max_value",
                "max_value_time",
                "min_value",
                "min_value_time",
                "average_value"
            ],
            order_by="idx asc"
        )

        rows_by_field = {
            row.field_name: row
            for row in child_rows
            if row.field_name
        }

        # Master fieldname list = known map + anything extra in child data
        all_fieldnames = list(FIELD_TAG_MAP.keys())

        for fieldname in rows_by_field:
            if fieldname not in all_fieldnames:
                all_fieldnames.append(fieldname)

        for fieldname in all_fieldnames:

            child_row = rows_by_field.get(fieldname)
            map_entry = FIELD_TAG_MAP.get(fieldname, {})

            label = (
                (child_row.parameter_name if child_row else None)
                or map_entry.get("label")
                or fieldname
            )

            # Only "sum" type parameters get a Total - a Total for an
            # "avg" type (temperature, pressure, %) is meaningless, even
            # if the parent doc happens to have a value in that field.
            agg = map_entry.get("agg")

            if agg == "avg":
                total = None
            else:
                total = getattr(parent_doc, fieldname, None)

            dmr_rows.append({
            "parameter_name": label,
            "engg_units": child_row.engg_units if child_row else None,
            "max_value": round_value(child_row.max_value) if child_row else None,
            "max_value_time": format_time(child_row.max_value_time) if child_row else None,
            "min_value": round_value(child_row.min_value) if child_row else None,
            "min_value_time": format_time(child_row.min_value_time) if child_row else None,
            "average_value": round_value(child_row.average_value) if child_row else None,
            "total": round_value(total)
        })

    return dmr_rows

def format_indian_currency(value):
    if value is None:
        return None

    value = round(float(value), 2)
    integer_part, decimal_part = f"{value:.2f}".split(".")

    if len(integer_part) > 3:
        last_three = integer_part[-3:]
        remaining = integer_part[:-3]

        groups = []
        while remaining:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]

        integer_part = ",".join(groups) + "," + last_three

    return f"{integer_part}.{decimal_part}"


def resolve_coal_item_codes():
    """
    Coal isn't one fixed item code - there can be several coal items in
    the system. Resolves ALL item codes in the "Power & Fuel" item group
    whose item_name contains "coal" (case-insensitive), so they can be
    aggregated into a single "Coal" row instead of listed individually.
    """

    rows = frappe.get_all(
        "Item",
        filters={
            "item_group": COAL_ITEM_GROUP,
            "item_name": ["like", COAL_NAME_MATCH]
        },
        fields=["name"]
    )

    return [row.name for row in rows]


def build_fuel_categories():
    """
    Returns the list of fuel rows to show, each as:
    {"label": "Paddy", "item_codes": ["106441"]}

    Paddy / Husk / Mustard are single fixed item codes with their real
    name pulled from Item master. Coal is resolved dynamically and can
    map to multiple item codes, all aggregated under one "Coal" row.
    """

    fixed_codes = list(FUEL_ITEM_CODES.values())
    item_names = get_item_names(fixed_codes)

    categories = []

    for label, code in FUEL_ITEM_CODES.items():
        categories.append({
            "label": item_names.get(code, label),
            "item_codes": [code]
        })

    categories.append({
        "label": "Coal",
        "item_codes": resolve_coal_item_codes()
    })

    return categories


def get_fuel_data(plant, date):
    """
    Builds the "Boiler Fuel Parameters" + "Fuel Cost" section for a plant
    on a given date. One row per fuel CATEGORY (Paddy/Husk/Mustard/Coal),
    where Coal can represent multiple underlying item codes aggregated
    together. All quantities are in TON (not quintal).

    - consumption_ton: sum of qty (kg -> ton, /1000) from submitted
      Material Issue Stock Entries, summed across every item code in the
      category, filtered by branch + date.
    - pct_total_fuel: this category's share of total fuel consumed that
      day (by ton).
    - pct_moisture / pct_dust: average of matching Quality Inspection
      readings (specification "Moisture" / "Foreign Particle") across
      every item code in the category, for that branch + report_date.
      Only QC docs with an actual non-blank reading are counted. If NO
      QC doc has a reading for that parameter at all, returns None
      (shown as "-", not "0%").
    - last_price: a consumption-weighted average price (per ton) across
      the category's item codes, using each item's own latest submitted
      PO (transaction_date <= date). Items with no consumption or no
      price that day are skipped; if none have a usable price, this is
      None ("-").

    Fuel Cost:
    - rupees_per_day: sum of cost across all fuel categories.
    - per_ton_steam: rupees_per_day / Total Steam Produced (from DMR
      "float_zcpn" Total on the same plant + date).
    """

    categories = build_fuel_categories()

    all_item_codes = [
        code
        for cat in categories
        for code in cat["item_codes"]
    ]

    consumption_kg_by_item = get_consumption_by_item(all_item_codes, plant, date)

    category_consumption = []
    total_ton_all = 0

    for cat in categories:

        cat_kg = sum(
            consumption_kg_by_item.get(code, 0)
            for code in cat["item_codes"]
        )

        cat_ton = round(cat_kg / 1000, 2)

        category_consumption.append({
            "label": cat["label"],
            "item_codes": cat["item_codes"],
            "consumption_ton": cat_ton
        })

        total_ton_all += cat_ton

    fuel_rows = []
    rupees_per_day = 0

    for cat in category_consumption:

        pct_total_fuel = (
            round((cat["consumption_ton"] / total_ton_all) * 100, 2)
            if total_ton_all
            else 0
        )

        moisture, dust = get_quality_averages(cat["item_codes"], plant, date)

        last_price, cost = get_category_price_and_cost(
            cat["item_codes"],
            consumption_kg_by_item,
            plant,
            date
        )

        if cost is not None:
            rupees_per_day += cost

        fuel_rows.append({
            "item_name": cat["label"],
            "consumption_ton": cat["consumption_ton"],
            "pct_total_fuel": pct_total_fuel,
            "pct_moisture": moisture,
            "pct_dust": dust,
            "last_price": last_price
        })

    rupees_per_day = round(rupees_per_day, 2)

    steam_total = get_steam_total(plant, date)

    per_ton_steam = (
        round(rupees_per_day / steam_total, 2)
        if steam_total
        else None
    )

    return {
        "fuel_rows": fuel_rows,
        "rupees_per_day": format_indian_currency(rupees_per_day),
        "per_ton_steam": format_indian_currency(per_ton_steam)
    }


def get_item_names(item_codes):

    if not item_codes:
        return {}

    rows = frappe.get_all(
        "Item",
        filters={
            "name": ["in", item_codes]
        },
        fields=["name", "item_name"]
    )

    return {row.name: row.item_name for row in rows}


def get_consumption_by_item(item_codes, plant, date):
    """
    Sum of qty (kg, raw system unit) per item_code, from submitted
    Material Issue Stock Entries for this branch + date. Single SQL
    join covering every item code at once.
    """

    if not item_codes:
        return {}

    rows = frappe.db.sql(
        """
        select sed.item_code as item_code, sum(sed.qty) as qty
        from `tabStock Entry Detail` sed
        inner join `tabStock Entry` se on se.name = sed.parent
        where se.branch = %(plant)s
          and se.posting_date = %(date)s
          and se.stock_entry_type = 'Material Issue'
          and se.docstatus = 1
          and sed.item_code in %(item_codes)s
        group by sed.item_code
        """,
        {
            "plant": plant,
            "date": date,
            "item_codes": tuple(item_codes)
        },
        as_dict=True
    )

    return {row.item_code: (row.qty or 0) for row in rows}


def get_quality_averages(item_codes, plant, date):
    """
    Returns (avg_moisture, avg_dust) across all submitted Quality
    Inspections for ANY of the given item codes + branch + report_date
    (lets a multi-code category like Coal pool readings across all its
    underlying items).

    Averaging rule: only QC docs that actually have a non-blank
    Moisture / Foreign Particle reading are counted. A QC doc with no
    matching reading row, or a blank reading_1, is EXCLUDED from both
    the sum and the denominator for that parameter.
    """

    if not item_codes:
        return None, None

    rows = frappe.db.sql(
        """
        select qir.specification as specification, qir.reading_1 as reading_1
        from `tabQuality Inspection Reading` qir
        inner join `tabQuality Inspection` qi on qi.name = qir.parent
        where qi.item_code in %(item_codes)s
          and qi.custom_branch = %(plant)s
          and qi.report_date = %(date)s
          and qi.docstatus = 1
        """,
        {
            "item_codes": tuple(item_codes),
            "plant": plant,
            "date": date
        },
        as_dict=True
    )

    moisture_values = []
    dust_values = []

    for r in rows:

        if r.reading_1 in [None, ""]:
            continue

        try:
            value = float(r.reading_1)
        except (ValueError, TypeError):
            continue

        spec = (r.specification or "").strip().lower()

        if spec == "moisture":
            moisture_values.append(value)
        elif spec == "foreign particle":
            dust_values.append(value)

    avg_moisture = round(sum(moisture_values) / len(moisture_values), 2) if moisture_values else None
    avg_dust = round(sum(dust_values) / len(dust_values), 2) if dust_values else None

    return avg_moisture, avg_dust


def get_category_price_and_cost(item_codes, consumption_kg_by_item, plant, date):
    """
    Consumption-weighted average price (per ton) across a category's
    item codes, plus the total cost for the category. Each item code's
    own latest submitted PO price (as of the selected date) is used,
    weighted by that item's own consumption that day. Items with zero
    consumption, or no usable PO price, are skipped entirely - they
    don't drag the average down or count as 0.

    If NONE of the category's item codes have both consumption and a
    price, returns (None, None) - shown as "-" on the dashboard.
    """

    total_cost = 0
    total_ton_with_price = 0

    for code in item_codes:

        kg = consumption_kg_by_item.get(code, 0)
        ton = kg / 1000

        if ton <= 0:
            continue

        price = get_last_price(code, plant, date)

        if price is None:
            continue

        total_cost += ton * price
        total_ton_with_price += ton

    if total_ton_with_price == 0:
        return None, None

    weighted_price = round(total_cost / total_ton_with_price, 2)

    return weighted_price, round(total_cost, 2)


def get_last_price(item_code, plant, date):
    """
    Rate from a submitted Purchase Order dated on or before the selected
    date (transaction_date <= date) with a line for this item_code and
    branch, most recent first. If no such PO exists, returns None
    (shown as "-" on the dashboard).
    """

    rows = frappe.db.sql(
        """
        select poi.rate as rate, poi.uom as uom
        from `tabPurchase Order Item` poi
        inner join `tabPurchase Order` po on po.name = poi.parent
        where poi.item_code = %(item_code)s
          and po.branch = %(plant)s
          and po.docstatus = 1
          and po.transaction_date <= %(date)s
        order by po.transaction_date desc, po.creation desc
        limit 1
        """,
        {"item_code": item_code, "plant": plant, "date": date},
        as_dict=True
    )

    if not rows:
        return None

    return convert_rate_to_ton(rows[0].rate, rows[0].uom)


def convert_rate_to_ton(rate, uom):
    """
    Normalizes a per-UOM rate to a per-TON rate.

    Recognized UOMs: Kg / Quintal / Ton variants. Anything else
    (including blank/missing UOM) is treated as Kg, since that's the
    dominant UOM for these fuel items - defaulting to "unconverted raw
    rate" was silently wrong far more often than defaulting to Kg would
    be.
    """

    if rate is None:
        return None

    uom_clean = (uom or "").strip().lower()

    if uom_clean in ["ton", "tonne", "mt", "tonnes"]:
        return round(rate, 2)

    if uom_clean in ["quintal", "qtl", "quintals"]:
        return round(rate * 10, 2)

    # Kg, or unrecognized/blank UOM - assume Kg.
    return round(rate * 1000, 2)


def get_steam_total(plant, date):
    """
    Pulls "Total Steam Produced" (fieldname float_zcpn) straight off the
    DMR parent doc for this plant + date, for use in the Per Ton Steam
    fuel-cost calculation.
    """

    parents = frappe.get_all(
        "DMR Boiler And Turbine Parameters",
        filters={
            "plant": plant,
            "date": date
        },
        fields=["name"]
    )

    if not parents:
        return None

    parent_doc = frappe.get_doc(
        "DMR Boiler And Turbine Parameters",
        parents[0].name
    )

    return getattr(parent_doc, "float_zcpn", None)


def add_value(target, value):

    if value not in [None, "", 0]:

        target.append(float(value))


def calculate_section(section, norms, field_map):

    result = {}

    for parameter, values in section.items():

        actual_fieldname = field_map.get(parameter, parameter)
        param_norm = norms.get(actual_fieldname, {})
        min_val = param_norm.get("min")
        max_val = param_norm.get("max")
        unit = param_norm.get("unit")

        if values:
            avg = round(sum(values) / len(values), 2)
            status = get_status(avg, min_val, max_val)

            result[parameter] = {
                "average": avg,
                "min": min(values),
                "max": max(values),
                "norm_min": min_val,
                "norm_max": max_val,
                "unit": unit,
                "status": status
            }

        else:
            result[parameter] = {
                "average": None,
                "min": None,
                "max": None,
                "norm_min": min_val,
                "norm_max": max_val,
                "unit": unit,
                "status": "No Data"
            }

    return result


def get_status(avg, min_val, max_val):

    if avg is None:
        return "No Data"

    if min_val is None and max_val is None:
        return "No Norm"

    if min_val is not None and avg < min_val:
        return "Low"

    if max_val is not None and avg > max_val:
        return "High"

    return "Normal"