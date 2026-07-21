import frappe


PLANTS = [
    "Buttar Biofuels",
    "RSL Belwara",
    "RSL Buttar",
    "RSL Louhka",
    "RSLD Karnal",
    "Superior Biofuels"
]


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
    }

    parameters = []

    for df in meta.fields:

        # Only actual numeric parameters
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


@frappe.whitelist()
def get_daily_data(plant, date):

    meta = frappe.get_meta("Water Balance Log Book")

    parameters = get_parameters()

    logs = frappe.get_all(
        "Water Balance Log Book",
        filters={
            "plant": plant,
            "date": date
        },
        fields=["name"] + [
            p["fieldname"] for p in parameters
        ],
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

        # Keep 0 values in daily data
        if value is None:
            value = 0

        result.append({
            "fieldname": parameter["fieldname"],
            "label": parameter["label"],
            "description": parameter["description"],
            "value": value
        })

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
            [
                p["fieldname"]
                for p in parameters
            ],
            as_dict=True
        )

        plant_data = []

        for parameter in parameters:

            value = full_doc.get(
                parameter["fieldname"]
            )

            # Keep 0 values in daily dashboard
            if value is None:
                value = 0

            plant_data.append({

                "fieldname":
                    parameter["fieldname"],

                "label":
                    parameter["label"],

                "description":
                    parameter["description"],

                "value":
                    value

            })


        result.append({

            "plant":
                log.plant,

            "date":
                str(log.date),

            "data":
                plant_data

        })


    return result