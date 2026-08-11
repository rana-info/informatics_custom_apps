import frappe

# Display order of the doctype columns in the violations matrix.
SOURCE_LABELS = ["Power Plant", "RO Plant", "DM Plant", "CPU Plant"]

# Location columns present on CPU Plant Lab Log Detail / CPU Plant Lab
# Norms - used when parsing every location's norm out of the norms
# table. CPU_CHECK_MAP (below) then decides which of these are actually
# checked for violations.
CPU_LOCATION_FIELDS = [
    "eqt_tank",
    "ct_tank",
    "reactor_inlet",
    "reactor_outlet",
    "aeration_tank",
    "sec_clarifier_outlet",
    "hrscc_outlet",
    "mgf_outlet",
    "acf_outlet",
    "uv_outlet"
]

# Cache of (doctype, fieldname) -> label, since frappe.get_meta() calls
# add up across hundreds of field lookups per request otherwise.
_LABEL_CACHE = {}

# Only these specific parameters are checked for violations - everything
# else defined in the norms tables is ignored on this screen even if a
# norm exists for it.
POWER_PLANT_CHECK_FIELDS = {
    "ph", "conductivity", "silica",           # Feed Water
    "ph1", "conductivity1", "silica1",        # Boiler Water
    "ph2", "conductivity2", "silica2"         # Steam
}

RO_PLANT_CHECK_FIELDS = {
    "ph2", "conductivity2", "silica_as_sio22"  # RO Outlet Parameters
}

DM_PLANT_CHECK_FIELDS = {
    "mb_after_dosing_ph",
    "mb_outlet_conductivity",
    "mb_outlet_silica"
}

# location -> set of parameter names (matched lowercase/trimmed against
# CPU Plant Lab Log Detail.parameter) that are checked at that location.
# Any location/parameter combo not listed here is skipped entirely.
CPU_CHECK_MAP = {
    "eqt_tank": {"ph", "vfa", "cod"},
    "uv_outlet": {"ph", "cod", "total hardness", "tds"}
}


@frappe.whitelist()
def get_violations(date):
    """
    Returns a plant x doctype violation-count matrix for the given date,
    plus per-parameter drilldown detail (every individual out-of-range
    reading, not a daily average - a parameter breached in 3 different
    shifts counts as 3).

    {
        "date": date,
        "sources": ["Power Plant", "RO Plant", "DM Plant", "CPU Plant"],
        "plants": [
            {
                "plant": "RSL Louhka",
                "total": 7,
                "sources": {
                    "Power Plant": {"count": 3, "parameters": [
                        {"label": "Boiler Water - PH", "section": "Boiler Water",
                         "unit": "", "min": 9.5, "max": 10.2, "values": [10.8, 10.9, 11.1]},
                        ...
                    ]},
                    "RO Plant": {"count": 0, "parameters": []},
                    ...
                }
            },
            ...
        ]
    }
    """

    power = compute_power_plant_violations(date)
    ro = compute_ro_plant_violations(date)
    dm = compute_dm_plant_violations(date)
    cpu = compute_cpu_plant_violations(date)

    results_by_source = {
        "Power Plant": power,
        "RO Plant": ro,
        "DM Plant": dm,
        "CPU Plant": cpu
    }

    all_plants = sorted(
        set(power.keys()) | set(ro.keys()) | set(dm.keys()) | set(cpu.keys())
    )

    plants = []

    for plant_name in all_plants:

        sources = {}

        for label in SOURCE_LABELS:

            # None = no doc submitted for this plant/source/date at all
            # (shown as "No Data"). A present-but-empty result means a
            # doc WAS submitted and nothing violated (shown as "-").
            sources[label] = results_by_source[label].get(plant_name)

        total = sum(
            (s["count"] if s else 0)
            for s in sources.values()
        )

        plants.append({
            "plant": plant_name,
            "total": total,
            "sources": sources
        })

    # Highest total violations first, so the MD sees the worst plant up top
    plants.sort(key=lambda p: p["total"], reverse=True)

    return {
        "date": date,
        "sources": SOURCE_LABELS,
        "plants": plants
    }


def safe_float(value):

    if value in [None, ""]:
        return None

    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def prettify_fieldname(fieldname):

    return (fieldname or "").replace("_", " ").strip().title()


def get_field_label(doctype, fieldname):
    """
    Pulls the real field label from the doctype's own metadata (e.g.
    Power Plant Log Book Item's "ph1" field is labeled "PH" in the
    doctype itself, same as "ph" / "ph2" / etc - so this naturally
    collapses suffixed fieldnames like ph1/ph2/conductivity1 down to
    their real, presentable label instead of showing the raw fieldname).

    Falls back to a prettified version of the fieldname if the field
    isn't found or has no label set.
    """

    cache_key = (doctype, fieldname)

    if cache_key in _LABEL_CACHE:
        return _LABEL_CACHE[cache_key]

    label = prettify_fieldname(fieldname)

    try:
        meta = frappe.get_meta(doctype)
        field = meta.get_field(fieldname)
        if field and field.label:
            label = field.label
    except Exception:
        pass

    _LABEL_CACHE[cache_key] = label

    return label


def is_real_value(value):
    """
    True only for values that represent an actual entered reading.
    Excludes None AND 0 - if a user leaves a field blank, Frappe stores
    0 for Float fields, and that should never be treated as a real
    reading for violation-checking purposes (a blank field isn't "0",
    it's "not entered").
    """

    return value is not None and value != 0


def check_violation(value, min_val, max_val):
    """Returns True if value breaches either bound that's actually set."""

    if min_val is not None and value < min_val:
        return True

    if max_val is not None and value > max_val:
        return True

    return False


# ---------------------------------------------------------------------
# Power Plant (long-format norms: one row per parameter)
# ---------------------------------------------------------------------

def get_power_plant_norms():

    rows = frappe.get_all(
        "Power Plant Log Norms",
        filters={
            "parent": "ETH Logbook Norms",
            "parenttype": "ETH Logbook Norms",
            "parentfield": "power_plant_log_norms"
        },
        fields=["section", "fieldname", "unit", "min_value", "max_value"]
    )

    norms = {}

    for r in rows:
        if not r.fieldname:
            continue
        if r.fieldname not in POWER_PLANT_CHECK_FIELDS:
            continue
        norms[r.fieldname] = {
            "section": r.section,
            "unit": r.unit,
            "min": r.min_value,
            "max": r.max_value
        }

    return norms


def compute_power_plant_violations(date):

    norms = get_power_plant_norms()

    docs = frappe.get_all(
        "Power Plant Log Book",
        filters={"log_date": date},
        fields=["name", "plant"]
    )

    result = {}

    for doc in docs:

        d = frappe.get_doc("Power Plant Log Book", doc.name)
        plant_params = result.setdefault(doc.plant, {})

        for row in d.logs:

            for fieldname, norm in norms.items():

                value = safe_float(getattr(row, fieldname, None))

                if not is_real_value(value):
                    continue

                if check_violation(value, norm["min"], norm["max"]):

                    key = fieldname
                    field_label = get_field_label("Power Plant Log Book Item", fieldname)

                    entry = plant_params.setdefault(key, {
                        "label": f"{norm['section']} - {field_label}" if norm.get("section") else field_label,
                        "section": norm.get("section"),
                        "unit": norm.get("unit"),
                        "min": norm["min"],
                        "max": norm["max"],
                        "values": []
                    })

                    entry["values"].append(value)

    return finalize(result)


# ---------------------------------------------------------------------
# RO Plant (long-format norms, same shape as Power Plant)
# ---------------------------------------------------------------------

def get_ro_plant_norms():

    rows = frappe.get_all(
        "RO Plant Log Norms",
        filters={
            "parent": "ETH Logbook Norms",
            "parenttype": "ETH Logbook Norms",
            "parentfield": "ro_plant_log_norms"
        },
        fields=["section", "fieldname", "unit", "min_value", "max_value"]
    )

    norms = {}

    for r in rows:
        if not r.fieldname:
            continue
        if r.fieldname not in RO_PLANT_CHECK_FIELDS:
            continue
        norms[r.fieldname] = {
            "section": r.section,
            "unit": r.unit,
            "min": r.min_value,
            "max": r.max_value
        }

    return norms


def compute_ro_plant_violations(date):

    norms = get_ro_plant_norms()

    docs = frappe.get_all(
        "RO Plant Log Book",
        filters={"log_date": date},
        fields=["name", "plant"]
    )

    result = {}

    for doc in docs:

        d = frappe.get_doc("RO Plant Log Book", doc.name)
        plant_params = result.setdefault(doc.plant, {})

        for row in d.logs:

            for fieldname, norm in norms.items():

                value = safe_float(getattr(row, fieldname, None))

                if not is_real_value(value):
                    continue

                if check_violation(value, norm["min"], norm["max"]):

                    key = fieldname
                    field_label = get_field_label("RO Plant Log Book Item", fieldname)

                    entry = plant_params.setdefault(key, {
                        "label": f"{norm['section']} - {field_label}" if norm.get("section") else field_label,
                        "section": norm.get("section"),
                        "unit": norm.get("unit"),
                        "min": norm["min"],
                        "max": norm["max"],
                        "values": []
                    })

                    entry["values"].append(value)

    return finalize(result)


# ---------------------------------------------------------------------
# DM Plant (wide-format norms: ONE row, columns named <field>_min/_max)
# ---------------------------------------------------------------------

def get_dm_plant_norms():
    """
    DM Plant Log Norms is a single-row child table where every parameter
    is its own pair of columns (e.g. dmf_inlet_turbidity_min /
    dmf_inlet_turbidity_max) rather than one row per parameter. Parsed
    generically by pairing up every "<x>_min" column with its "<x>_max"
    counterpart, so this doesn't need every fieldname hardcoded.

    Columns whose min/max are stored as text (Data fieldtype) that can't
    be parsed as a number are skipped, not errored on.
    """

    rows = frappe.get_all(
        "DM Plant Log Norms",
        filters={
            "parent": "ETH Logbook Norms",
            "parenttype": "ETH Logbook Norms",
            "parentfield": "dm_plant_logbook"
        },
        fields=["*"],
        limit_page_length=1
    )

    if not rows:
        return {}

    row = rows[0]
    norms = {}

    for key in row.keys():

        if not key.endswith("_min"):
            continue

        fieldname = key[:-4]

        if fieldname not in DM_PLANT_CHECK_FIELDS:
            continue

        max_key = fieldname + "_max"

        if max_key not in row:
            continue

        min_val = safe_float(row.get(key))
        max_val = safe_float(row.get(max_key))

        if min_val is None and max_val is None:
            continue

        norms[fieldname] = {"min": min_val, "max": max_val}

    return norms


def compute_dm_plant_violations(date):

    norms = get_dm_plant_norms()

    docs = frappe.get_all(
        "DM Plant Logbook",
        filters={"log_date": date},
        fields=["name", "plant"]
    )

    result = {}

    for doc in docs:

        d = frappe.get_doc("DM Plant Logbook", doc.name)
        plant_params = result.setdefault(doc.plant, {})

        for row in d.rows:

            for fieldname, norm in norms.items():

                value = safe_float(getattr(row, fieldname, None))

                if not is_real_value(value):
                    continue

                if check_violation(value, norm["min"], norm["max"]):

                    key = fieldname
                    field_label = get_field_label("DM Plant Log Row", fieldname)

                    entry = plant_params.setdefault(key, {
                        "label": field_label,
                        "section": None,
                        "unit": None,
                        "min": norm["min"],
                        "max": norm["max"],
                        "values": []
                    })

                    entry["values"].append(value)

    return finalize(result)


# ---------------------------------------------------------------------
# CPU Plant (matrix norms: rows = parameter description, columns =
# location, one reading per parameter per day - not shift-based)
# ---------------------------------------------------------------------

def get_cpu_plant_norms():
    """
    Returns { normalized_description: {"unit": ..., "locations": {
        "eqt_tank": {"min":..,"max":..}, ... } } }

    normalized_description = description.strip().lower(), so matching
    against logged parameter names is forgiving of case/whitespace.
    """

    rows = frappe.get_all(
        "CPU Plant Lab Norms",
        filters={
            "parent": "ETH Logbook Norms",
            "parenttype": "ETH Logbook Norms",
            "parentfield": "cpu_plant_logbook"
        },
        fields=["*"]
    )

    norms = {}

    for r in rows:

        key = (r.description or "").strip().lower()

        if not key:
            continue

        entry = norms.setdefault(key, {
            "description": r.description,
            "unit": r.unit,
            "locations": {}
        })

        for loc in CPU_LOCATION_FIELDS:

            min_val = safe_float(r.get(loc + "_min"))
            max_val = safe_float(r.get(loc + "_max"))

            if min_val is None and max_val is None:
                continue

            entry["locations"][loc] = {"min": min_val, "max": max_val}

    return norms


def compute_cpu_plant_violations(date):

    norms = get_cpu_plant_norms()

    docs = frappe.get_all(
        "CPU Plant Lab Log",
        filters={"log_date": date},
        fields=["name", "plant"]
    )

    result = {}

    for doc in docs:

        d = frappe.get_doc("CPU Plant Lab Log", doc.name)
        plant_params = result.setdefault(doc.plant, {})

        for row in d.parameters:

            key = (row.parameter or "").strip().lower()
            norm_entry = norms.get(key)

            if not norm_entry:
                continue

            for loc, allowed_params in CPU_CHECK_MAP.items():

                if key not in allowed_params:
                    continue

                loc_norm = norm_entry["locations"].get(loc)

                if not loc_norm:
                    continue

                value = safe_float(getattr(row, loc, None))

                if not is_real_value(value):
                    continue

                if check_violation(value, loc_norm["min"], loc_norm["max"]):

                    loc_label = get_field_label("CPU Plant Lab Log Detail", loc)
                    param_key = f"{row.parameter} ({loc_label})"

                    entry = plant_params.setdefault(param_key, {
                        "label": param_key,
                        "section": loc_label,
                        "unit": norm_entry.get("unit"),
                        "min": loc_norm["min"],
                        "max": loc_norm["max"],
                        "values": []
                    })

                    entry["values"].append(value)

    return finalize(result)


# ---------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------

def finalize(result):
    """
    Converts {plant: {fieldname: {..., "values":[...]}}} into
    {plant: {"count": N, "parameters": [ {...}, ... ]}}
    """

    final = {}

    for plant, params_dict in result.items():

        params_list = list(params_dict.values())
        count = sum(len(p["values"]) for p in params_list)

        final[plant] = {
            "count": count,
            "parameters": params_list
        }

    return final