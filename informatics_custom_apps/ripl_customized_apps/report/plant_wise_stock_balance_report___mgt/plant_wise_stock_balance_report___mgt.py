import frappe

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_data(filters):
    conditions = ["sle.docstatus = 1", "sle.is_cancelled = 0", "sle.posting_date <= %(to_date)s"]

    values = {
        "from_date": filters.get("from_date"),
        "to_date": filters.get("to_date")
    }

    if filters.get("company"):
        conditions.append("wh.company IN %(company)s")
        values["company"] = tuple(filters.get("company"))

    if filters.get("plant"):
        conditions.append("wh.custom_branch IN %(plant)s")
        values["plant"] = tuple(filters.get("plant"))

    where_clause = " AND ".join(conditions)

    return frappe.db.sql(f"""
        SELECT
            sle.item_code AS item_code,
            i.item_name AS item_name,
            i.item_group AS item_group,
            i.stock_uom AS uom,

            wh.company AS company,
            wh.custom_branch AS plant,
            
            ROUND(SUM(CASE
                WHEN sle.posting_date < %(from_date)s
                THEN sle.actual_qty ELSE 0 END), 2) AS opening_qty,

            ROUND(SUM(CASE
                WHEN sle.posting_date < %(from_date)s
                THEN sle.stock_value_difference ELSE 0 END), 2) AS opening_value,

            ROUND(SUM(CASE
                WHEN sle.posting_date BETWEEN %(from_date)s AND %(to_date)s
                     AND sle.actual_qty > 0
                THEN sle.actual_qty ELSE 0 END), 2) AS in_qty,

            ROUND(SUM(CASE
                WHEN sle.posting_date BETWEEN %(from_date)s AND %(to_date)s
                     AND sle.actual_qty > 0
                THEN sle.stock_value_difference ELSE 0 END), 2) AS in_value,

            ROUND(SUM(CASE
                WHEN sle.posting_date BETWEEN %(from_date)s AND %(to_date)s
                     AND sle.actual_qty < 0
                THEN ABS(sle.actual_qty) ELSE 0 END), 2) AS out_qty,

            ROUND(SUM(CASE
                WHEN sle.posting_date BETWEEN %(from_date)s AND %(to_date)s
                     AND sle.actual_qty < 0
                THEN ABS(sle.stock_value_difference) ELSE 0 END), 2) AS out_value,

            ROUND(SUM(sle.actual_qty), 2) AS balance_qty,
            ROUND(SUM(sle.stock_value_difference), 2) AS balance_value

        FROM `tabStock Ledger Entry` sle
        LEFT JOIN `tabWarehouse` wh ON wh.name = sle.warehouse
        LEFT JOIN `tabItem` i ON i.name = sle.item_code

        WHERE {where_clause}

        GROUP BY
            sle.item_code,
            i.item_name,
            i.item_group,
            i.stock_uom,
            wh.company,
            wh.custom_branch,
            wh.custom_segment

        ORDER BY
            wh.company,
            wh.custom_branch,
            sle.item_code
    """, values, as_dict=True)


def get_columns():
    return [
        {"label": "Item Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 360,"align":"left"},
        {"label": "Balance Qty", "fieldname": "balance_qty", "fieldtype": "Float", "width": 120},
        {"label": "Balance Value", "fieldname": "balance_value", "fieldtype": "Currency", "width": 120},
        {"label": "Out Qty", "fieldname": "out_qty", "fieldtype": "Float", "width": 100},
        {"label": "Out Value", "fieldname": "out_value", "fieldtype": "Currency", "width": 120},
        {"label": "In Qty", "fieldname": "in_qty", "fieldtype": "Float", "width": 100},
        {"label": "In Value", "fieldname": "in_value", "fieldtype": "Currency", "width": 120},
        {"label": "Opening Qty", "fieldname": "opening_qty", "fieldtype": "Float", "width": 120},
        {"label": "Opening Value", "fieldname": "opening_value", "fieldtype": "Currency", "width": 120},
 		{"label": "Plant", "fieldname": "plant", "fieldtype": "Data", "width": 150},
        {"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 200},
        {"label": "Item Group", "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 150},
        {"label": "UOM", "fieldname": "uom", "fieldtype": "Data", "width": 80}
    ]