import frappe


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

    logs = frappe.get_all(
        "Power Plant Log Book",
        filters={
            "log_date": date
        },
        fields=[
            "name",
            "plant"
        ]
    )

    plants = []

    for log in logs:

        doc = frappe.get_doc(
            "Power Plant Log Book",
            log.name
        )

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

        # Skip plant if no required values found

        if not has_data(feed_water, boiler_water, steam):
            continue

        plants.append({

            "plant": log.plant,

            "feed_water": calculate_section(feed_water, norms, SECTION_FIELD_MAP["Feed Water"]),

            "boiler_water": calculate_section(boiler_water, norms, SECTION_FIELD_MAP["Boiler Water"]),

            "steam": calculate_section(steam, norms, SECTION_FIELD_MAP["Steam"]),

            "dmr": get_dmr_data(log.plant, date)

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


def get_dmr_data(plant, date):
    """
    Fetches all DMR Parameters Range child rows for the given plant + date,
    and attaches a "total" pulled off the parent doc at the same fieldname
    as the row's field_name (e.g. row.field_name = "float_zcpn" ->
    total = parent_doc.float_zcpn).
    """

    parents = frappe.get_all(
        "DMR Boiler And Turbine Parameters",
        filters={
            "plant": plant,
            "date": date
        },
        fields=["name"]
    )

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

        for row in child_rows:

            total = getattr(parent_doc, row.field_name, None) if row.field_name else None

            dmr_rows.append({
                "parameter_name": row.parameter_name,
                "engg_units": row.engg_units,
                "max_value": row.max_value,
                "max_value_time": row.max_value_time,
                "min_value": row.min_value,
                "min_value_time": row.min_value_time,
                "average_value": row.average_value,
                "total": total
            })

    return dmr_rows


def add_value(target, value):

    if value not in [None, "", 0]:

        target.append(float(value))


def has_data(*sections):

    for section in sections:

        for values in section.values():

            if values:
                return True

    return False


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