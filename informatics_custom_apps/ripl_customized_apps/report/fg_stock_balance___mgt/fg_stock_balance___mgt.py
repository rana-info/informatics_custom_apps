# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
    return get_columns(), get_data(filters or {})


def get_columns():
    return [
        {
            "label": "Plant",
            "fieldname": "plant",
            "fieldtype": "Link",
            "options": "Branch",
            "width": 180,
        },
        {
            "label": "Item Group",
            "fieldname": "item_group",
            "fieldtype": "Link",
            "options": "Item Group",
            "width": 600,
            "align": "left",
        },
        {
            "label": "UOM",
            "fieldname": "stock_uom",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": "Qty",
            "fieldname": "qty",
            "fieldtype": "Float",
            "width": 150,
        },
        {
            "label": "Value",
            "fieldname": "value",
            "fieldtype": "Currency",
            "width": 150,
        },
        {
            "label": "Rate",
            "fieldname": "rate",
            "fieldtype": "Currency",
            "width": 120,
        },
    ]


def convert_qty(item_code, qty, stock_uom):
    """
    Convert quantity using Item UOM conversion.
    Pick highest available UOM.
    """

    stock_uom = (stock_uom or "").strip()

    conversions = frappe.get_all(
        "UOM Conversion Detail",
        filters={
            "parent": item_code
        },
        fields=[
            "uom",
            "conversion_factor"
        ],
        order_by="conversion_factor desc"
    )

    if not conversions:
        return round(qty, 2), stock_uom

    highest = None

    for row in conversions:

        factor = row.conversion_factor or 0

        if factor <= 0:
            continue

        converted_qty = qty / factor

        if converted_qty >= 1:
            highest = (
                round(converted_qty, 2),
                row.uom
            )
            break

    if highest:
        return highest

    return round(qty, 2), stock_uom


def get_data(filters):

    conditions = ["b.actual_qty > 0"]
    values = {}

    if filters.get("company"):

        company_list = filters["company"]

        if isinstance(company_list, str):
            company_list = [company_list]

        placeholders = ", ".join(
            [f"%(company_{i})s" for i in range(len(company_list))]
        )

        conditions.append(
            f"wh.company IN ({placeholders})"
        )

        for i, company in enumerate(company_list):
            values[f"company_{i}"] = company

    if filters.get("plant"):

        plant_list = filters["plant"]

        if isinstance(plant_list, str):
            plant_list = [plant_list]

        placeholders = ", ".join(
            [f"%(plant_{i})s" for i in range(len(plant_list))]
        )

        conditions.append(
            f"wh.custom_branch IN ({placeholders})"
        )

        for i, plant in enumerate(plant_list):
            values[f"plant_{i}"] = plant

    conditions.append("""
        i.item_group IN (
            '010101-Sugar-Mfg',
            '010102-Bagasse-Mfg',
            '010103-Cattle Feed-Mfg-Beet',
            '010105-Molasses-Mfg',

            '010201-Ethanol-Mfg',
            '010202-ENA-Mfg',
            '010203-Cattle Feed-Mfg',
            '010204-Country Liquor-Mfg',
            '010205-IMFL-Mfg',
            '010206-Rectified Spirit-Mfg',
            '010211-Corn Oil-Mfg',

            '010301-Power-Mfg',
            '010209-Other Products-Mfg'
        )
    """)

    where_clause = " AND ".join(conditions)

    rows = frappe.db.sql(
        f"""
        SELECT

            CASE
                WHEN IFNULL(
                    TRIM(wh.custom_branch),
                    ''
                ) = ''

                THEN 'Plant Missing'

                ELSE wh.custom_branch

            END AS plant,

            b.warehouse,

            i.name AS item_code,

            i.item_group,

            i.item_name,

            i.stock_uom,

            ROUND(
                b.actual_qty,
                2
            ) AS qty_raw,

            ROUND(
                b.stock_value,
                2
            ) AS value

        FROM `tabBin` b

        INNER JOIN `tabItem` i
            ON i.name = b.item_code

        INNER JOIN `tabWarehouse` wh
            ON wh.name = b.warehouse

        WHERE {where_clause}

        ORDER BY

            b.stock_value DESC,

            b.actual_qty DESC,

            wh.custom_branch,

            b.warehouse,

            b.item_code
        """,
        values,
        as_dict=True,
    )

    result = []

    for row in rows:

        qty_raw = row.qty_raw or 0

        value = row.value or 0

        qty_conv, uom_conv = convert_qty(
            row.item_code,
            qty_raw,
            row.stock_uom
        )

        rate = (
            round(value / qty_conv, 2)
            if qty_conv
            else 0
        )

        result.append({
            "plant": row.plant,

            "warehouse": row.warehouse,

            "item_group": row.item_group,

            "item_name": row.item_name,

            "stock_uom": uom_conv,

            "qty": qty_conv,

            "value": value,

            "rate": rate,
        })

    return result