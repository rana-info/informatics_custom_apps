import frappe


PARENT_DOCTYPE = "CPU Plant Lab Log"
CHILD_DOCTYPE = "CPU Plant Lab Log Detail"


LOCATIONS = [
    {
        "fieldname": "eqt_tank",
        "label": "EQT-Tank",
    },
    {
        "fieldname": "ct_tank",
        "label": "CT-Tank",
    },
    {
        "fieldname": "reactor_inlet",
        "label": "Reactor Inlet",
    },
    {
        "fieldname": "reactor_outlet",
        "label": "Reactor Outlet",
    },
    {
        "fieldname": "aeration_tank",
        "label": "Aeration Tank",
    },
    {
        "fieldname": "sec_clarifier_outlet",
        "label": "Sec. Clarifier Outlet",
    },
    {
        "fieldname": "hrscc_outlet",
        "label": "HRSCC Outlet",
    },
    {
        "fieldname": "mgf_outlet",
        "label": "MGF Outlet",
    },
    {
        "fieldname": "acf_outlet",
        "label": "ACF Outlet",
    },
    {
        "fieldname": "uv_outlet",
        "label": "UV Outlet",
    },
]


# =========================================================
# PARAMETERS
# =========================================================

@frappe.whitelist()
def get_parameters():

    meta = frappe.get_meta(CHILD_DOCTYPE)

    parameters = []

    for df in meta.fields:

        if df.fieldtype not in (
            "Float",
            "Int",
            "Currency"
        ):
            continue

        parameters.append({
            "fieldname": df.fieldname,
            "label": df.label or df.fieldname,
            "description": df.description or ""
        })

    return parameters


# =========================================================
# LOCATIONS
# =========================================================

@frappe.whitelist()
def get_locations():

    return LOCATIONS


# =========================================================
# GET PLANTS FOR SELECTED DATE
# =========================================================

@frappe.whitelist()
def get_plants_for_date(date):

    if not date:
        frappe.throw("Date is required.")

    return frappe.get_all(
        PARENT_DOCTYPE,
        filters={
            "log_date": date
        },
        fields=[
            "name",
            "company",
            "plant",
            "log_date"
        ],
        order_by="plant asc"
    )


# =========================================================
# GET CPU LOG
# =========================================================
@frappe.whitelist()
def get_cpu_log(plant, date):

    if not plant:
        frappe.throw("Plant is required.")

    if not date:
        frappe.throw("Date is required.")

    log_name = frappe.db.exists(
        PARENT_DOCTYPE,
        {
            "plant": plant,
            "log_date": date
        }
    )

    if not log_name:
        return {
            "name": None,
            "plant": plant,
            "date": date,
            "rows": [],
            "violations": [],
            "violation_count": 0
        }

    doc = frappe.get_doc(
        PARENT_DOCTYPE,
        log_name
    )

    # ---------------------------------------------------------
    # Get norms
    # ---------------------------------------------------------

    norms = get_norms()

    rows = []
    violations = []

    for row in doc.parameters:

        parameter = str(
            row.parameter or ""
        ).strip()

        parameter_key = parameter.lower()

        row_data = {
            "name": row.name,
            "s_no": row.s_no,
            "parameter": parameter,
            "unit": row.unit,
        }

        parameter_norms = norms.get(
            parameter_key,
            {}
        )

        # -----------------------------------------------------
        # Check every location
        # -----------------------------------------------------

        for location in LOCATIONS:

            fieldname = location["fieldname"]

            value = row.get(
                fieldname
            )

            row_data[fieldname] = value

            # No value
            if value is None or value == "":
                continue

            location_norm = parameter_norms.get(
                fieldname,
                {}
            )

            min_value = location_norm.get(
                "min"
            )

            max_value = location_norm.get(
                "max"
            )

            # No norm configured
            if min_value is None and max_value is None:
                continue

            is_violation = False

            if (
                min_value is not None
                and value < min_value
            ):
                is_violation = True

            if (
                max_value is not None
                and value > max_value
            ):
                is_violation = True

            if is_violation:

                violations.append({
                    "parameter": parameter,
                    "location": location["label"],
                    "location_fieldname": fieldname,
                    "value": value,
                    "min": min_value,
                    "max": max_value,
                    "unit": row.unit
                })

        rows.append(row_data)

    return {
        "name": doc.name,
        "company": doc.company,
        "plant": doc.plant,
        "date": str(doc.log_date),
        "rows": rows,
        "violations": violations,
        "violation_count": len(violations)
    }


# =========================================================
# GET CPU NORMS
# =========================================================

@frappe.whitelist()
def get_norms():

    doc = frappe.get_single(
        "ETH Logbook Norms"
    )

    norms = {}

    for row in doc.cpu_plant_logbook or []:

        if not row.description:
            continue

        parameter = str(
            row.description
        ).strip()

        # Remove " NORMS"
        if parameter.upper().endswith(" NORMS"):
            parameter = parameter[:-6].strip()

        parameter_key = parameter.lower()

        norms[parameter_key] = {}

        for location in LOCATIONS:

            fieldname = location["fieldname"]

            min_field = f"{fieldname}_min"
            max_field = f"{fieldname}_max"

            min_value = row.get(min_field)
            max_value = row.get(max_field)

            # =================================================
            # Treat 0 as "Norm Not Defined"
            # =================================================

            if min_value == 0:
                min_value = None

            if max_value == 0:
                max_value = None

            norms[parameter_key][fieldname] = {
                "min": min_value,
                "max": max_value
            }

    return norms
# =========================================================
# DASHBOARD
# =========================================================

@frappe.whitelist()
def get_daily_dashboard(date):

    if not date:
        frappe.throw("Date is required.")

    # Get all CPU logs for selected date
    logs = frappe.get_all(
        PARENT_DOCTYPE,
        filters={
            "log_date": date
        },
        fields=[
            "name",
            "company",
            "plant",
            "log_date",
            "modified"
        ],
        order_by="plant asc"
    )

    # Get norms
    norms = get_norms()

    plants = []

    for log in logs:

        doc = frappe.get_doc(
            PARENT_DOCTYPE,
            log.name
        )

        rows = []
        violation_count = 0

        for row in doc.parameters:

            row_data = {
                "name": row.name,
                "s_no": row.s_no,
                "parameter": row.parameter,
                "unit": row.unit,
                "violations": {}
            }

            # Normalize parameter name
            parameter_key = (
                str(row.parameter or "")
                .strip()
                .lower()
            )

            # Get norms for this parameter
            parameter_norm = norms.get(
                parameter_key,
                {}
            )

            for location in LOCATIONS:

                fieldname = location["fieldname"]

                value = row.get(
                    fieldname
                )

                # Store actual value
                row_data[fieldname] = value

                # No value
                if value is None or value == "":
                    continue

                # Get norm for this parameter + location
                location_norm = parameter_norm.get(
                    fieldname,
                    {}
                )

                min_value = location_norm.get(
                    "min"
                )

                max_value = location_norm.get(
                    "max"
                )

                # No norm configured
                if (
                    min_value is None
                    and max_value is None
                ):
                    continue

                violation = None

                # Check minimum
                if (
                    min_value is not None
                    and value < min_value
                ):

                    violation = {
                        "message": (
                            f"Below minimum norm "
                            f"({min_value})"
                        ),
                        "value": value,
                        "min": min_value,
                        "max": max_value
                    }

                # Check maximum
                elif (
                    max_value is not None
                    and value > max_value
                ):

                    violation = {
                        "message": (
                            f"Above maximum norm "
                            f"({max_value})"
                        ),
                        "value": value,
                        "min": min_value,
                        "max": max_value
                    }

                # Store violation
                if violation:

                    row_data[
                        "violations"
                    ][fieldname] = violation

                    violation_count += 1

            rows.append(
                row_data
            )

        plants.append({

            "name": doc.name,

            "company": doc.company,

            "plant": doc.plant,

            "log_date": str(
                doc.log_date
            ),

            "last_updated": str(
                doc.modified
            ),

            "violation_count":
                violation_count,

            "rows": rows

        })

    return {

        "date": date,

        "plants": plants,

        "norms": norms,

        "locations": LOCATIONS

    }

# =========================================================
# TREND
# =========================================================
@frappe.whitelist()
def get_trend_filters():

    # ---------------------------------------------------------
    # Get all plants
    # ---------------------------------------------------------

    plants = frappe.get_all(
        PARENT_DOCTYPE,
        fields=[
            "plant"
        ],
        filters={
            "plant": [
                "is",
                "set"
            ]
        },
        distinct=True,
        order_by="plant asc"
    )

    plant_list = [
        x.plant
        for x in plants
        if x.plant
    ]

    # ---------------------------------------------------------
    # Get parameters from child table metadata
    # ---------------------------------------------------------

    meta = frappe.get_meta(
        CHILD_DOCTYPE
    )

    parameters = []

    # We don't want every Float/Int field.
    # Only parameter rows from existing CPU logs
    # are used here.

    parameter_rows = frappe.db.sql(
        f"""
        SELECT DISTINCT
            parameter
        FROM `tab{CHILD_DOCTYPE}`
        WHERE
            parameter IS NOT NULL
            AND parameter != ''
        ORDER BY parameter
        """,
        as_dict=True
    )

    parameters = [
        x.parameter
        for x in parameter_rows
        if x.parameter
    ]

    # ---------------------------------------------------------
    # Return locations
    # ---------------------------------------------------------

    return {

        "plants": plant_list,

        "parameters": parameters,

        "locations": LOCATIONS

    }
# =========================================================
# GET PARAMETER TREND
# =========================================================

@frappe.whitelist()
def get_parameter_trend(
    plant,
    parameter,
    location,
    from_date,
    to_date
):

    if not plant:
        frappe.throw("Plant is required.")

    if not parameter:
        frappe.throw("Parameter is required.")

    if not location:
        frappe.throw("Location is required.")

    if not from_date or not to_date:
        frappe.throw(
            "From Date and To Date are required."
        )

    if from_date > to_date:
        frappe.throw(
            "From Date cannot be greater than To Date."
        )

    # ---------------------------------------------------------
    # VALIDATE LOCATION
    # ---------------------------------------------------------

    valid_locations = [
        x["fieldname"]
        for x in LOCATIONS
    ]

    if location not in valid_locations:

        frappe.throw(
            "Invalid location."
        )

    # ---------------------------------------------------------
    # GET LOGS
    # ---------------------------------------------------------

    logs = frappe.get_all(
        PARENT_DOCTYPE,
        filters={
            "plant": plant,
            "log_date": [
                "between",
                [
                    from_date,
                    to_date
                ]
            ]
        },
        fields=[
            "name",
            "log_date"
        ],
        order_by="log_date asc"
    )

    data = []

    # ---------------------------------------------------------
    # GET VALUES
    # ---------------------------------------------------------

    for log in logs:

        doc = frappe.get_doc(
            PARENT_DOCTYPE,
            log.name
        )

        for row in doc.parameters:

            row_parameter = str(
                row.parameter or ""
            ).strip()

            if (
                row_parameter.lower()
                != str(parameter).strip().lower()
            ):
                continue

            value = row.get(
                location
            )

            # Treat 0 as not entered,
            # same as Section A
            if value in (
                None,
                "",
                0
            ):
                continue

            data.append({

                "date": str(
                    log.log_date
                ),

                "value": value

            })

            break

    # ---------------------------------------------------------
    # GET NORMS
    # ---------------------------------------------------------

    norms = get_norms()

    parameter_norm = norms.get(
        str(parameter).strip().lower(),
        {}
    )

    location_norm = parameter_norm.get(
        location,
        {}
    )

    min_norm = location_norm.get(
        "min"
    )

    max_norm = location_norm.get(
        "max"
    )

    # ---------------------------------------------------------
    # ADD STATUS TO EACH VALUE
    # ---------------------------------------------------------

    for record in data:

        value = record["value"]

        if (
            min_norm is not None
            and value < min_norm
        ):

            record["status"] = "low"

        elif (
            max_norm is not None
            and value > max_norm
        ):

            record["status"] = "high"

        else:

            record["status"] = "normal"

    # ---------------------------------------------------------
    # RETURN TREND DATA
    # ---------------------------------------------------------

    return {

        "plant": plant,

        "parameter": parameter,

        "location": location,

        "data": data,

        "min_norm": min_norm,

        "max_norm": max_norm

    }