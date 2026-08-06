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

            "dmr": get_dmr_data(plant_name, date)

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