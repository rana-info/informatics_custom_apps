import frappe


@frappe.whitelist()
def get_dashboard(date=None, segment=None):

    if not date:
        date = frappe.utils.today()

    filters = {"log_date": date}

    # optional segment filter ("" / None = all segments)
    if segment:
        filters["segment"] = segment

    logbooks = frappe.get_all(
        "Power Plant Log Book",
        filters=filters,
        fields=["name", "plant", "segment", "log_date"],
        order_by="plant, segment"
    )

    norms = get_norms()

    plants = []

    for log in logbooks:

        violation_count = 0

        doc = frappe.get_doc("Power Plant Log Book", log.name)

        for row in doc.logs:

            for fieldname, norm in norms.items():

                value = row.get(fieldname)

                if value in (None, "", 0):
                    continue

                status = get_status(
                    value,
                    norm["min"],
                    norm["max"]
                )

                if status in ("Low", "High"):
                    violation_count += 1

        plants.append({
            "name": log.name,
            "plant": log.plant,
            "segment": log.segment or "",
            "last_updated": log.log_date,
            "violations": violation_count
        })

    return {
        "plants": plants
    }


def get_norms():

    doc = frappe.get_single("ETH Logbook Norms")

    norms = {}

    for row in doc.power_plant_log_norms:

        if not row.fieldname:
            continue

        norms[row.fieldname] = {
            "section": row.section,
            "min": row.min_value,
            "max": row.max_value,
            "unit": row.unit or ""
        }

    return norms


@frappe.whitelist()
def get_parameters():

    doc = frappe.get_single("ETH Logbook Norms")

    parameters = []

    for row in doc.power_plant_log_norms:

        if not row.fieldname:
            continue

        parameters.append({
            "fieldname": row.fieldname,
            "label": frappe.get_meta("Power Plant Log Book Item").get_field(row.fieldname).label,
            "section": row.section or ""
        })

    return parameters


def get_field_labels():

    meta = frappe.get_meta("Power Plant Log Book Item")

    labels = {}

    for df in meta.fields:

        labels[df.fieldname] = df.label

    return labels


def get_status(value, min_value=None, max_value=None):

    if value in (None, "", 0, 0.0):
        return None

    # Treat blank norms (stored as 0) as not configured
    has_min = min_value not in (None, "", 0, 0.0)
    has_max = max_value not in (None, "", 0, 0.0)

    if has_min and value < min_value:
        return "Low"

    if has_max and value > max_value:
        return "High"

    # If no norm exists at all, don't assign any status
    if not has_min and not has_max:
        return None

    return "Normal"


@frappe.whitelist()
def get_plant_logbook(plant, date, segment=None):

    norms = get_norms()
    labels = get_field_labels()

    log_filters = {
        "plant": plant,
        "log_date": date
    }

    # segment is part of the log's identity now (company+plant+segment+date)
    if segment:
        log_filters["segment"] = segment

    log = frappe.get_value("Power Plant Log Book", log_filters, "name")

    if not log:
        return []

    rows = frappe.get_all(
        "Power Plant Log Book Item",
        filters={"parent": log},
        fields=["*"],
        order_by="idx"
    )

    meta = frappe.get_meta("Power Plant Log Book Item")

    skip_fields = (
        "name",
        "owner",
        "creation",
        "modified",
        "modified_by",
        "parent",
        "parentfield",
        "parenttype",
        "doctype",
        "idx",
        "time_slot"
    )

    parameters = {}

    for row in rows:

        time_slot = row.time_slot

        for df in meta.fields:

            if df.fieldtype not in ("Float", "Int", "Currency", "Small Text"):
                continue

            fieldname = df.fieldname

            if fieldname in skip_fields:
                continue

            if fieldname not in parameters:

                norm = norms.get(fieldname, {})

                parameters[fieldname] = {
                    "fieldname": fieldname,
                    "label": labels.get(fieldname, fieldname),
                    "section": norm.get("section"),
                    "unit": norm.get("unit", ""),
                    "min": norm.get("min"),
                    "max": norm.get("max"),
                    "values": {}
                }

            value = row.get(fieldname)

            if value in (None, 0, 0.0):
                value = ""

            status = ""

            norm = norms.get(fieldname)

            if norm and value != "":
                status = get_status(
                    value,
                    norm.get("min"),
                    norm.get("max")
                ) or ""

            parameters[fieldname]["values"][time_slot] = {
                "value": value,
                "status": status
            }

    return list(parameters.values())


@frappe.whitelist()
def get_parameter_trend(plant, parameter, from_date, to_date, segment=None):

    norms = get_norms()

    log_filters = {
        "plant": plant,
        "log_date": ["between", [from_date, to_date]]
    }

    if segment:
        log_filters["segment"] = segment

    logs = frappe.get_all(
        "Power Plant Log Book",
        filters=log_filters,
        fields=["name", "log_date"],
        order_by="log_date"
    )

    result = []

    for log in logs:

        doc = frappe.get_doc("Power Plant Log Book", log.name)

        for row in doc.logs:

            value = row.get(parameter)

            if value in (None, "", 0):
                continue

            result.append({
                "date": str(log.log_date),
                "time_slot": row.time_slot,
                "value": value
            })

    norm = norms.get(parameter)

    return {
        "data": result,
        "norm": norm
    }