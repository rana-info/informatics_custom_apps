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


# Master list of fuel item codes used in the "Boiler Fuel Parameters"
# section. code -> fallback label (real label is fetched from Item master
# at render time; this is just a fallback if the Item doesn't exist).
FUEL_ITEMS = ["106441", "106436", "115566", "106440"]


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
    - "total" is always pulled straight off the parent doc at the same
      fieldname, regardless of whether a child row exists - this is what
      lets Total show up even when the child table hasn't been filled in.

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


def get_fuel_data(plant, date):
    """
    Builds the "Boiler Fuel Parameters" + "Fuel Cost" section for a plant
    on a given date:

    - consumption: sum of qty (kg -> quintal) from submitted Material
      Issue Stock Entries, per fuel item code, filtered by branch + date.
    - pct_total_fuel: this item's share of total fuel consumed that day.
    - pct_moisture / pct_dust: average of matching Quality Inspection
      readings (specification "Moisture" / "Foreign Particle") for that
      item, branch, and report_date. Only QC docs with an actual
      non-blank reading are counted - a QC doc missing that reading is
      excluded from both the sum and the denominator. If NO QC doc has
      a reading for that parameter at all, returns None (shown as "-"
      on the dashboard, not "0%").
    - last_price: rate from a submitted Purchase Order dated EXACTLY on
      the selected date for that item + branch. If no PO was raised for
      that plant/item on that exact date, this is None ("-" on the
      dashboard) - no fallback to an earlier or later date's price.
    - cost: consumption_qtl * last_price, assuming rate is per quintal.

    Fuel Cost:
    - rupees_per_day: sum of cost across all fuel items.
    - per_ton_steam: rupees_per_day / Total Steam Produced (from DMR
      "float_zcpn" Total on the same plant + date).
    """

    item_names = get_item_names(FUEL_ITEMS)

    consumption_kg = {code: 0.0 for code in FUEL_ITEMS}

    stock_entries = frappe.get_all(
        "Stock Entry",
        filters={
            "branch": plant,
            "posting_date": date,
            "stock_entry_type": "Material Issue",
            "docstatus": 1
        },
        fields=["name"]
    )

    for se in stock_entries:

        items = frappe.get_all(
            "Stock Entry Detail",
            filters={
                "parent": se.name,
                "parenttype": "Stock Entry",
                "item_code": ["in", FUEL_ITEMS]
            },
            fields=["item_code", "qty"]
        )

        for it in items:
            consumption_kg[it.item_code] = consumption_kg.get(it.item_code, 0) + (it.qty or 0)

    consumption_qtl = {
        code: round(qty / 100, 2)
        for code, qty in consumption_kg.items()
    }

    total_qtl = sum(consumption_qtl.values())

    fuel_rows = []
    rupees_per_day = 0

    for code in FUEL_ITEMS:

        qty_qtl = consumption_qtl.get(code, 0)

        pct_total_fuel = round((qty_qtl / total_qtl) * 100, 2) if total_qtl else 0

        moisture, dust = get_quality_averages(code, plant, date)

        last_price = get_last_price(code, plant, date)

        cost = round(qty_qtl * last_price, 2) if last_price is not None else None

        if cost is not None:
            rupees_per_day += cost

        fuel_rows.append({
            "item_code": code,
            "item_name": item_names.get(code, code),
            "consumption_qtl": qty_qtl,
            "pct_total_fuel": pct_total_fuel,
            "pct_moisture": moisture,
            "pct_dust": dust,
            "last_price": last_price,
            "cost": cost
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
        "rupees_per_day": rupees_per_day,
        "per_ton_steam": per_ton_steam
    }


def get_item_names(item_codes):

    rows = frappe.get_all(
        "Item",
        filters={
            "name": ["in", item_codes]
        },
        fields=["name", "item_name"]
    )

    return {row.name: row.item_name for row in rows}


def get_quality_averages(item_code, plant, date):
    """
    Returns (avg_moisture, avg_dust) across all submitted Quality
    Inspections for this item + branch + report_date.

    Averaging rule: only QC docs that actually have a non-blank
    Moisture / Foreign Particle reading are counted. A QC doc with no
    matching reading row, or a blank reading_1, is EXCLUDED from both
    the sum and the denominator for that parameter (so if 5 of 7 QC
    docs have a moisture reading, the average is over those 5, not 7).

    Uses a single SQL join instead of one query per QC doc.
    """

    rows = frappe.db.sql(
        """
        select qir.specification as specification, qir.reading_1 as reading_1
        from `tabQuality Inspection Reading` qir
        inner join `tabQuality Inspection` qi on qi.name = qir.parent
        where qi.item_code = %(item_code)s
          and qi.custom_branch = %(plant)s
          and qi.report_date = %(date)s
          and qi.docstatus = 1
        """,
        {"item_code": item_code, "plant": plant, "date": date},
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


def get_last_price(item_code, plant, date):
    """
    Rate from a submitted Purchase Order dated EXACTLY on the selected
    date (transaction_date = date) with a line for this item_code and
    branch. If no PO was raised for that plant/item on that exact date,
    returns None (shown as "-" on the dashboard) - no fallback to an
    earlier date's price.
    """

    rows = frappe.db.sql(
        """
        select poi.rate as rate, poi.uom as uom
        from `tabPurchase Order Item` poi
        inner join `tabPurchase Order` po on po.name = poi.parent
        where poi.item_code = %(item_code)s
          and po.branch = %(plant)s
          and po.docstatus = 1
          and po.transaction_date = %(date)s
        order by po.creation desc
        limit 1
        """,
        {"item_code": item_code, "plant": plant, "date": date},
        as_dict=True
    )

    if not rows:
        return None

    return convert_rate_to_quintal(rows[0].rate, rows[0].uom)


def convert_rate_to_quintal(rate, uom):
    """
    Normalizes a per-UOM rate to a per-quintal rate.

    Recognized UOMs: Kg / Quintal / Ton variants. Anything else
    (including blank/missing UOM) is treated as Kg, since that's the
    dominant UOM (~90% of cases) for these fuel items - defaulting to
    "unconverted raw rate" was silently wrong far more often than
    defaulting to Kg would be.
    """

    if rate is None:
        return None

    uom_clean = (uom or "").strip().lower()

    if uom_clean in ["quintal", "qtl", "quintals"]:
        return round(rate, 2)

    if uom_clean in ["ton", "tonne", "mt", "tonnes"]:
        return round(rate / 10, 2)

    # Kg, or unrecognized/blank UOM - assume Kg.
    return round(rate * 100, 2)


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