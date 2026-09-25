import frappe


PLANTS = [
    "Buttar Biofuels",
    "RSL Belwara",
    "RSL Buttar",
    "RSL Louhka",
    "RSLD Karnal",
    "Superior Biofuels",
    "Karimganj Biofuels"
]

HIDDEN_FIELDS = {
    "ethanol_production",
    "condensate_generation_ratio",
    "effluent_generation_ratio",
}

STATUS_SOURCE_MAP = {
    "total_condensate_genration": {
        "source": "condensate_generation_ratio",
        "norm": "condensate_generation_norm",
    },
    "total_effluent_genration": {
        "source": "effluent_generation_ratio",
        "norm": "effluent_generation_norm",
    },
    "effluent_treatment_cost": {
        "source": "effluent_treatment_cost",
        "norm": "effluent_treatment_cost_norm",
    },
    "dm_water_treatment_cost": {
        "source": "dm_water_treatment_cost",
        "norm": "dm_water_treatment_cost_norm",
    },
}


@frappe.whitelist()
def get_parameters():

    meta = frappe.get_meta("Water Balance Log Book")

    skip_fields = {
        "name",
        "owner",
        "creation",
        "modified",
        "modified_by",
        "docstatus",
        "idx",
        "company",
        "plant",
        "date",
    } | HIDDEN_FIELDS

    parameters = []

    for df in meta.fields:

        if df.fieldtype not in ("Float", "Int", "Currency"):
            continue

        if df.fieldname in skip_fields:
            continue

        parameters.append({
            "fieldname": df.fieldname,
            "label": df.label or df.fieldname,
            "description": df.description or ""
        })

    return parameters


def get_fetch_fields(parameters):
    fields = {p["fieldname"] for p in parameters}
    for mapping in STATUS_SOURCE_MAP.values():
        fields.add(mapping["source"])
    return list(fields)


def get_plant_norms(plant):
    """Returns the norm row (as a dict) configured for this plant, or {}."""
    settings = frappe.get_single("Water Balance Settings")
    for row in settings.norms:
        if row.plant == plant:
            return row.as_dict()
    return {}


def attach_exceeds(entry, source_row, plant_norms):
    mapping = STATUS_SOURCE_MAP.get(entry["fieldname"])

    if not mapping:
        entry["exceeds"] = None
        entry["norm"] = None
        return

    norm_value = plant_norms.get(mapping["norm"])

    if norm_value in (None, ""):
        entry["exceeds"] = None
        entry["norm"] = None
        return

    source_value = source_row.get(mapping["source"]) or 0

    entry["exceeds"] = source_value >= norm_value
    entry["norm"] = norm_value


@frappe.whitelist()
def get_daily_data(plant, date):

    parameters = get_parameters()
    plant_norms = get_plant_norms(plant)
    fetch_fields = get_fetch_fields(parameters)

    logs = frappe.get_all(
        "Water Balance Log Book",
        filters={
            "plant": plant,
            "date": date
        },
        fields=["name"] + fetch_fields,
        limit_page_length=1
    )

    if not logs:
        return {
            "exists": False,
            "data": []
        }

    log = logs[0]

    result = []

    for parameter in parameters:

        value = log.get(parameter["fieldname"])

        if value is None:
            value = 0

        entry = {
            "fieldname": parameter["fieldname"],
            "label": parameter["label"],
            "description": parameter["description"],
            "value": value
        }

        attach_exceeds(entry, log, plant_norms)

        result.append(entry)

    return {
        "exists": True,
        "data": result
    }


@frappe.whitelist()
def get_parameter_trend(
    plant,
    parameter,
    from_date,
    to_date
):

    meta = frappe.get_meta("Water Balance Log Book")

    field = meta.get_field(parameter)

    if not field:
        frappe.throw("Invalid parameter")

    if field.fieldtype not in (
        "Float",
        "Int",
        "Currency"
    ):
        frappe.throw("Invalid parameter field")

    logs = frappe.get_all(
        "Water Balance Log Book",
        filters={
            "plant": plant,
            "date": [
                "between",
                [from_date, to_date]
            ]
        },
        fields=[
            "name",
            "date",
            parameter
        ],
        order_by="date asc"
    )

    result = []

    for log in logs:

        value = log.get(parameter)

        if value in (None, ""):
            value = 0

        result.append({
            "date": str(log.date),
            "value": value
        })

    return {
        "data": result,
        "label": field.label or parameter
    }


@frappe.whitelist()
def get_daily_dashboard(date):

    parameters = get_parameters()
    fetch_fields = get_fetch_fields(parameters)

    logs = frappe.get_all(
        "Water Balance Log Book",
        filters={
            "date": date
        },
        fields=[
            "name",
            "plant",
            "date"
        ],
        order_by="plant asc"
    )

    result = []

    for log in logs:

        full_doc = frappe.db.get_value(
            "Water Balance Log Book",
            log.name,
            fetch_fields,
            as_dict=True
        )

        plant_norms = get_plant_norms(log.plant)

        plant_data = []

        for parameter in parameters:

            value = full_doc.get(
                parameter["fieldname"]
            )

            # Keep 0 values in daily dashboard
            if value is None:
                value = 0

            entry = {

                "fieldname":
                    parameter["fieldname"],

                "label":
                    parameter["label"],

                "description":
                    parameter["description"],

                "value":
                    value

            }

            attach_exceeds(entry, full_doc, plant_norms)

            plant_data.append(entry)


        result.append({

            "plant":
                log.plant,

            "date":
                str(log.date),

            "data":
                plant_data

        })


    return result