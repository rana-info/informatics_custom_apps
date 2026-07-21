from unittest import result
import pprint
import frappe

@frappe.whitelist()
def get_dashboard(date=None):

    if not date:
        date = frappe.utils.today()

    logbooks = frappe.get_all(
        "DM Plant Logbook",
        filters={"log_date": date},
        fields=["name", "plant", "log_date"],
        order_by="plant"
    )

    norms = get_norms()

    plants = []

    for log in logbooks:

        violation_count = 0

        doc = frappe.get_doc("DM Plant Logbook", log.name)

        for row in doc.rows:

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
            "last_updated": log.log_date,
            "violations": violation_count
        })

    return {
        "plants": plants
    }

def get_norms():

    doc = frappe.get_single("ETH Logbook Norms")

    norms = {}

    # Get metadata of the norms child table
    norms_meta = frappe.get_meta("DM Plant Log Norms")

    # Get actual fields from DM Plant Log Row
    log_meta = frappe.get_meta("DM Plant Log Row")

    # Get the single child row containing all norms
    if not doc.dm_plant_logbook:
        return norms

    norm_row = doc.dm_plant_logbook[0]

    for df in norms_meta.fields:

        fieldname = df.fieldname

        # Only process *_min fields
        if not fieldname.endswith("_min"):
            continue

        parameter = fieldname[:-4]

        max_fieldname = f"{parameter}_max"

        # Make sure corresponding max field exists
        if not norms_meta.get_field(max_fieldname):
            continue

        # Make sure parameter exists in DM Plant Log Row
        parameter_df = log_meta.get_field(parameter)

        if not parameter_df:
            continue

        min_value = norm_row.get(fieldname)
        max_value = norm_row.get(max_fieldname)

        norms[parameter] = {
            "min": min_value,
            "max": max_value,
            "label": parameter_df.label
        }

    return norms

@frappe.whitelist()
def get_parameters():

    meta = frappe.get_meta("DM Plant Log Row")
    norm_meta = frappe.get_meta("DM Plant Log Norms")

    parameters = []
    added = set()

    for df in norm_meta.fields:

        fieldname = df.fieldname

        if not fieldname.endswith("_min"):
            continue

        parameter = fieldname[:-4]  # Remove "_min"
        max_field = f"{parameter}_max"

        # Make sure corresponding max field exists
        if not norm_meta.get_field(max_field):
            continue

        # Make sure parameter exists in DM Plant Log Row
        parameter_df = meta.get_field(parameter)

        if not parameter_df:
            continue

        if parameter in added:
            continue

        added.add(parameter)

        parameters.append({
            "fieldname": parameter,
            "label": parameter_df.label,
            "min": None,
            "max": None
        })

    return parameters

# def calculate_plant_summary(norms, filters=None):

#     logbooks = get_logs(filters or {})

#     log_items = get_log_items([d.name for d in logbooks])

#     plant_summary = {}

#     for log in logbooks:

#         if log.plant not in plant_summary:
#             plant_summary[log.plant] = {
#                 "plant": log.plant,
#                 "normal": 0,
#                 "low": 0,
#                 "high": 0,
#                 "last_updated": log.log_date,
#             }

#         summary = plant_summary[log.plant]

#         # Keep latest log date
#         if log.log_date > summary["last_updated"]:
#             summary["last_updated"] = log.log_date

#         rows = log_items.get(log.name, [])

#         for row in rows:

#             for fieldname, norm in norms.items():

#                 value = row.get(fieldname)

#                 if value in (None, "", 0, 0.0):
#                     continue

#                 status = get_status(
#                     value,
#                     norm["min"],
#                     norm["max"]
#                 )

#                 if status == "Low":
#                     summary["low"] += 1

#                 elif status == "High":
#                     summary["high"] += 1

#                 else:
#                     summary["normal"] += 1

#     plants = []

#     for summary in plant_summary.values():

#         total = (
#             summary["normal"]
#             + summary["low"]
#             + summary["high"]
#         )

#         summary["total"] = total

#         summary["health"] = (
#             round((summary["normal"] / total) * 100, 2)
#             if total else 100
#         )

#         plants.append(summary)

#     plants.sort(key=lambda x: x["health"])

#     return plants

def get_field_labels():

    meta = frappe.get_meta("DM Plant Log Row")

    labels = {}

    for df in meta.fields:

        labels[df.fieldname] = df.label

    return labels

# def get_logs(filters):

#     conditions = {}

#     if filters.get("from_date"):
#         conditions["log_date"] = [">=", filters.from_date]

#     if filters.get("to_date"):

#         if "log_date" in conditions:
#             conditions["log_date"] = [
#                 "between",
#                 [filters.from_date, filters.to_date]
#             ]
#         else:
#             conditions["log_date"] = ["<=", filters.to_date]

#     if filters.get("plant"):
#         conditions["plant"] = filters.plant

#     return frappe.get_all(
#         "DM Plant Logbook",
#         filters=conditions,
#         fields=[
#             "name",
#             "plant",
#             "log_date"
#         ],
#         order_by="log_date asc"
#      )

# def get_log_items(parents):

#     if not parents: 
#         return {}

#     rows = frappe.get_all(
#         "Power Plant Log Book Item",
#         filters={
#             "parent": ["in", parents]
#         },
#         fields=["*"],
#         order_by="parent asc, idx asc"
#     )

#     grouped = {}

#     for row in rows:
#         grouped.setdefault(row.parent, []).append(row)

#     return grouped

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
def get_plant_logbook(plant, date):

    norms = get_norms()
    labels = get_field_labels()

    log = frappe.get_value(
        "DM Plant Logbook",
        {
            "plant": plant,
            "log_date": date
        },
        "name"
    )

    if not log:
        return []

    rows = frappe.get_all(
        "DM Plant Log Row",
        filters={"parent": log},
        fields=["*"],
        order_by="idx"
    )

    meta = frappe.get_meta("DM Plant Log Row")

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

            if df.fieldtype not in ("Float", "Int", "Currency"):
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
def get_parameter_trend(plant, parameter, from_date, to_date):

    norms = get_norms()

    logs = frappe.get_all(
        "DM Plant Logbook",
        filters={
            "plant": plant,
            "log_date": ["between", [from_date, to_date]]
        },
        fields=["name", "log_date"],
        order_by="log_date"
    )

    result = []

    for log in logs:

        doc = frappe.get_doc("DM Plant Logbook", log.name)

        for row in doc.rows:

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