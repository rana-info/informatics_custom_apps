# Copyright (c) 2026, Your Company and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):

    filters = filters or {}

    report_type = filters.get("report_type")

    if report_type == "Asset Repair Wise":
        columns = get_detail_columns()
        data = get_detail_data(filters)

    elif report_type == "Item Wise":
        columns = get_item_columns()
        data = get_item_data(filters)

    else:
        columns = get_summary_columns()
        data = get_summary_data(filters)

    return columns, data



def get_conditions(filters):

    conditions = []
    query_filters = {
        "from_date": filters.get("from_date"),
        "to_date": filters.get("to_date")
    }

    # Company MultiSelect
    if filters.get("company"):
        companies = filters.get("company")

        if isinstance(companies, str):
            companies = frappe.parse_json(companies)

        conditions.append("ar.company IN %(company)s")
        query_filters["company"] = tuple(companies)

    # Branch MultiSelect
    if filters.get("branch"):
        branches = filters.get("branch")

        if isinstance(branches, str):
            branches = frappe.parse_json(branches)

        conditions.append("ar.branch IN %(branch)s")
        query_filters["branch"] = tuple(branches)

    conditions = " AND ".join(conditions)

    if conditions:
        conditions = " AND " + conditions

    return conditions, query_filters


def get_summary_columns():

    return [

        {
            "label": "Asset",
            "fieldname": "Asset",
            "fieldtype": "Link",
            "options": "Asset",
            "width": 150
        },

        {
            "label": "Asset Name",
            "fieldname": "Asset Name",
            "fieldtype": "Data",
            "width": 220
        },

        {
            "label": "Company",
            "fieldname": "Company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 150
        },

        {
            "label": "Branch",
            "fieldname": "Branch",
            "fieldtype": "Link",
            "options": "Branch",
            "width": 140
        },

        {
            "label": "Cost Center",
            "fieldname": "Cost Center",
            "fieldtype": "Link",
            "options": "Cost Center",
            "width": 160
        },

        {
            "label": "Segment",
            "fieldname": "Segment",
            "fieldtype": "Data",
            "width": 140
        },

        {
            "label": "Asset Status",
            "fieldname": "Asset Status",
            "fieldtype": "Data",
            "width": 140
        },

        {
            "label": "Asset Category",
            "fieldname": "Asset Category",
            "fieldtype": "Link",
            "options": "Asset Category",
            "width": 160
        },

        {
            "label": "Total Repairs",
            "fieldname": "Total Repairs",
            "fieldtype": "Int",
            "width": 120
        },

        {
            "label": "Capitalized Repairs",
            "fieldname": "Capitalized Repairs",
            "fieldtype": "Int",
            "width": 150
        },

        {
            "label": "Stock Cost",
            "fieldname": "Stock Cost",
            "fieldtype": "Currency",
            "width": 140
        },

        {
            "label": "Purchase Cost",
            "fieldname": "Purchase Cost",
            "fieldtype": "Currency",
            "width": 150
        },

        {
            "label": "Capitalized Repair Cost",
            "fieldname": "Capitalized Repair Cost",
            "fieldtype": "Currency",
            "width": 200
        },

        {
            "label": "Total Repair Cost",
            "fieldname": "Total Repair Cost",
            "fieldtype": "Currency",
            "width": 180
        },

    ]


def get_summary_data(filters):

    conditions, query_filters = get_conditions(filters)

    query = """
       SELECT 
            ar.asset AS "Asset",
            ar.asset_name AS "Asset Name",
            ar.company AS "Company",
            ar.branch AS "Branch",
            ar.cost_center AS "Cost Center",
            ar.segment AS "Segment",

            a.status AS "Asset Status",
            a.asset_category AS "Asset Category",

            COUNT(ar.name) AS "Total Repairs",

            SUM(CASE 
                WHEN ar.capitalize_repair_cost = 1 THEN 1 
                ELSE 0 
            END) AS "Capitalized Repairs",

            ROUND(SUM(IFNULL(stock.total_stock, 0)), 2) AS "Stock Cost",

            ROUND(
                SUM(
                    CASE 
                        WHEN IFNULL(ar.capitalize_repair_cost, 0) = 1 
                            AND IFNULL(ar.custom_capitalized_repair_cost, 0) > 0
                        THEN 0
                        ELSE IFNULL(purchase.total_purchase, 0)
                    END
                ),
            2) AS "Purchase Cost",

            ROUND(SUM(IFNULL(ar.custom_capitalized_repair_cost, 0)), 2) AS "Capitalized Repair Cost",

            ROUND(
                SUM(
                    CASE 
                        WHEN IFNULL(ar.capitalize_repair_cost, 0) = 1 
                            AND IFNULL(ar.custom_capitalized_repair_cost, 0) > 0
                        THEN IFNULL(ar.custom_capitalized_repair_cost, 0)

                        ELSE 
                            IFNULL(stock.total_stock, 0) 
                            + IFNULL(purchase.total_purchase, 0)
                    END
                ),
            2) AS "Total Repair Cost"

        FROM `tabAsset Repair` ar

        LEFT JOIN `tabAsset` a
            ON a.name = ar.asset

        LEFT JOIN (
            SELECT 
                css.parent,
                SUM(css.total_value) AS total_stock
            FROM `tabAsset Repair Settlement` css
            INNER JOIN `tabStock Entry` se
                ON se.name = css.stock_entry
            WHERE se.posting_date BETWEEN %(from_date)s AND %(to_date)s
            GROUP BY css.parent
        ) stock
        ON stock.parent = ar.name

        LEFT JOIN (
            SELECT 
                pi.parent,
                SUM(pi.repair_cost) AS total_purchase
            FROM `tabAsset Repair Purchase Invoice` pi
            INNER JOIN `tabPurchase Invoice` p
                ON p.name = pi.purchase_invoice
            WHERE p.posting_date BETWEEN %(from_date)s AND %(to_date)s
            GROUP BY pi.parent
        ) purchase
        ON purchase.parent = ar.name

        WHERE 
            ar.docstatus IN (0,1)
            {conditions}

        GROUP BY 
            ar.asset,
            ar.asset_name,
            ar.company,
            ar.branch,
            ar.cost_center,
            ar.segment,
            a.status,
            a.asset_category

        ORDER BY 
            `Total Repair Cost` DESC
    """

    query = query.format(conditions=conditions)

    return frappe.db.sql(query, query_filters, as_dict=1)


# =========================================================
# DETAILED REPORT
# =========================================================

def get_detail_columns():

    return [

        {
            "label": "Repair ID",
            "fieldname": "Repair ID",
            "fieldtype": "Link",
            "options": "Asset Repair",
            "width": 160
        },

        {
            "label": "Asset",
            "fieldname": "Asset",
            "fieldtype": "Link",
            "options": "Asset",
            "width": 140
        },

        {
            "label": "Asset Name",
            "fieldname": "Asset Name",
            "fieldtype": "Data",
            "width": 220
        },

        {
            "label": "Repair Type",
            "fieldname": "Repair Type",
            "fieldtype": "Data",
            "width": 140
        },

        {
            "label": "Repair Status",
            "fieldname": "Repair Status",
            "fieldtype": "Data",
            "width": 140
        },

        {
            "label": "Failure Date",
            "fieldname": "Failure Date",
            "fieldtype": "Date",
            "width": 120
        },

        {
            "label": "Completion Date",
            "fieldname": "Completion Date",
            "fieldtype": "Date",
            "width": 140
        },

        {
            "label": "Downtime",
            "fieldname": "Downtime",
            "fieldtype": "Float",
            "width": 120
        },

        {
            "label": "Capitalized",
            "fieldname": "Capitalized",
            "fieldtype": "Data",
            "width": 120
        },

        {
            "label": "Stock Cost",
            "fieldname": "Stock Cost",
            "fieldtype": "Currency",
            "width": 140
        },

        {
            "label": "Purchase Cost",
            "fieldname": "Purchase Cost",
            "fieldtype": "Currency",
            "width": 150
        },

        {
            "label": "Capitalized Amount",
            "fieldname": "Capitalized Amount",
            "fieldtype": "Currency",
            "width": 170
        },

        {
            "label": "Total Repair Cost",
            "fieldname": "Total Repair Cost",
            "fieldtype": "Currency",
            "width": 180
        },

    ]


def get_detail_data(filters):

    conditions, query_filters = get_conditions(filters)

    query = """
        SELECT 
            ar.name AS "Repair ID",
            ar.asset AS "Asset",
            ar.asset_name AS "Asset Name",
            ar.company AS "Company",
            ar.branch AS "Branch",
            ar.cost_center AS "Cost Center",
            ar.segment AS "Segment",                

            a.status AS "Asset Status",
            a.asset_category AS "Asset Category",

            ar.custom_repair_type AS "Repair Type",
            ar.repair_status AS "Repair Status",

            ar.failure_date AS "Failure Date",
            ar.completion_date AS "Completion Date",
            ar.downtime AS "Downtime",

            ar.description AS "Repair Description",
            ar.actions_performed AS "Actions Performed",

            CASE 
                WHEN IFNULL(ar.capitalize_repair_cost, 0) = 1 THEN 'Yes'
                ELSE 'No'
            END AS "Capitalized",

            ROUND(IFNULL(stock.total_stock, 0), 2) AS "Stock Cost",

            ROUND(
                CASE 
                    WHEN IFNULL(ar.capitalize_repair_cost, 0) = 1 
                        AND IFNULL(ar.custom_capitalized_repair_cost, 0) > 0
                    THEN 0
                    ELSE IFNULL(purchase.total_purchase, 0)
                END,
            2) AS "Purchase Cost",

            ROUND(IFNULL(ar.custom_capitalized_repair_cost, 0), 2) AS "Capitalized Amount",

            ROUND(
                CASE 
                    WHEN IFNULL(ar.capitalize_repair_cost, 0) = 1 
                        AND IFNULL(ar.custom_capitalized_repair_cost, 0) > 0
                    THEN IFNULL(ar.custom_capitalized_repair_cost, 0)

                    ELSE 
                        IFNULL(stock.total_stock, 0) 
                        + IFNULL(purchase.total_purchase, 0)
                END,
            2) AS "Total Repair Cost"

        FROM `tabAsset Repair` ar

        LEFT JOIN `tabAsset` a
            ON a.name = ar.asset

        LEFT JOIN (
            SELECT 
                css.parent,
                SUM(css.total_value) AS total_stock
            FROM `tabAsset Repair Settlement` css
            INNER JOIN `tabStock Entry` se
                ON se.name = css.stock_entry
            WHERE se.posting_date BETWEEN %(from_date)s AND %(to_date)s
            GROUP BY css.parent
        ) stock
        ON stock.parent = ar.name

        LEFT JOIN (
            SELECT 
                pi.parent,
                SUM(pi.repair_cost) AS total_purchase
            FROM `tabAsset Repair Purchase Invoice` pi
            INNER JOIN `tabPurchase Invoice` p
                ON p.name = pi.purchase_invoice
            WHERE p.posting_date BETWEEN %(from_date)s AND %(to_date)s
            GROUP BY pi.parent
        ) purchase
        ON purchase.parent = ar.name

        WHERE 
            ar.docstatus IN (0,1)
            {conditions}

        ORDER BY 
            ar.name DESC
    """

    query = query.format(conditions=conditions)

    return frappe.db.sql(query, query_filters, as_dict=1)



def get_item_columns():

    return [

        {
            "label": "Repair ID",
            "fieldname": "Repair ID",
            "fieldtype": "Link",
            "options": "Asset Repair",
            "width": 160
        },

        {
            "label": "Asset",
            "fieldname": "Asset",
            "fieldtype": "Link",
            "options": "Asset",
            "width": 140
        },

        {
            "label": "Asset Name",
            "fieldname": "Asset Name",
            "fieldtype": "Data",
            "width": 220
        },

        {
            "label": "Company",
            "fieldname": "Company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 140
        },

        {
            "label": "Branch",
            "fieldname": "Branch",
            "fieldtype": "Link",
            "options": "Branch",
            "width": 140
        },

        {
            "label": "Cost Center",
            "fieldname": "Cost Center",
            "fieldtype": "Link",
            "options": "Cost Center",
            "width": 160
        },

        {
            "label": "Segment",
            "fieldname": "Segment",
            "fieldtype": "Data",
            "width": 140
        },

        {
            "label": "Repair Type",
            "fieldname": "Repair Type",
            "fieldtype": "Data",
            "width": 140
        },

        {
            "label": "Repair Status",
            "fieldname": "Repair Status",
            "fieldtype": "Data",
            "width": 140
        },

        {
            "label": "Failure Date",
            "fieldname": "Failure Date",
            "fieldtype": "Date",
            "width": 120
        },

        {
            "label": "Completion Date",
            "fieldname": "Completion Date",
            "fieldtype": "Date",
            "width": 140
        },

        {
            "label": "Downtime",
            "fieldname": "Downtime",
            "fieldtype": "Float",
            "width": 100
        },

        {
            "label": "Repair Description",
            "fieldname": "Repair Description",
            "fieldtype": "Small Text",
            "width": 250
        },

        {
            "label": "Actions Performed",
            "fieldname": "Actions Performed",
            "fieldtype": "Small Text",
            "width": 250
        },

        {
            "label": "Asset Status",
            "fieldname": "Asset Status",
            "fieldtype": "Data",
            "width": 130
        },

        {
            "label": "Asset Category",
            "fieldname": "Asset Category",
            "fieldtype": "Link",
            "options": "Asset Category",
            "width": 160
        },

        {
            "label": "Capitalized",
            "fieldname": "Capitalized",
            "fieldtype": "Data",
            "width": 110
        },

        {
            "label": "Source Type",
            "fieldname": "Source Type",
            "fieldtype": "Data",
            "width": 120
        },

        {
            "label": "Item Code",
            "fieldname": "Item Code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 140
        },

        {
            "label": "Item Name",
            "fieldname": "Item Name",
            "fieldtype": "Data",
            "width": 220
        },

        {
            "label": "UOM",
            "fieldname": "UOM",
            "fieldtype": "Link",
            "options": "UOM",
            "width": 100
        },

        {
            "label": "Qty",
            "fieldname": "Qty",
            "fieldtype": "Float",
            "width": 100
        },

        {
            "label": "Rate",
            "fieldname": "Rate",
            "fieldtype": "Currency",
            "width": 120
        },

        {
            "label": "Amount",
            "fieldname": "Amount",
            "fieldtype": "Currency",
            "width": 140
        },

        {
            "label": "Contract",
            "fieldname": "Contract",
            "fieldtype": "Data",
            "width": 160
        },

        {
            "label": "Purchase Invoice",
            "fieldname": "Purchase Invoice",
            "fieldtype": "Link",
            "options": "Purchase Invoice",
            "width": 170
        },

        {
            "label": "Supplier",
            "fieldname": "Supplier",
            "fieldtype": "Data",
            "width": 220
        },

        {
            "label": "Stock Entry",
            "fieldname": "Stock Entry",
            "fieldtype": "Link",
            "options": "Stock Entry",
            "width": 160
        },

        {
            "label": "Stock Entry Type",
            "fieldname": "Stock Entry Type",
            "fieldtype": "Data",
            "width": 160
        },

        {
            "label": "Stock Entry Date",
            "fieldname": "Stock Entry Date",
            "fieldtype": "Date",
            "width": 140
        },

        {
            "label": "Debit Account",
            "fieldname": "debit_account",
            "fieldtype": "Link",
            "options": "Account",
            "width": 220
        },

        {
            "label": "Debit Amount",
            "fieldname": "Debit Amount",
            "fieldtype": "Currency",
            "width": 140
        },

        {
            "label": "Credit Account",
            "fieldname": "credit_account",
            "fieldtype": "Link",
            "options": "Account",
            "width": 220
        },

        {
            "label": "Credit Amount",
            "fieldname": "Credit Amount",
            "fieldtype": "Currency",
            "width": 140
        },

    ]
    
    
def get_item_data(filters):

    conditions, query_filters = get_conditions(filters)

    query = """
    SELECT 
        `Repair ID`,
        asset AS "Asset",
        asset_name AS "Asset Name",
        company AS "Company",
        branch AS "Branch",
        cost_center AS "Cost Center",
        segment AS "Segment",
        custom_repair_type AS "Repair Type",
        repair_status AS "Repair Status",

        failure_date AS "Failure Date",
        completion_date AS "Completion Date",
        downtime AS "Downtime",

        description AS "Repair Description",
        actions_performed AS "Actions Performed",

        asset_status AS "Asset Status",
        asset_category AS "Asset Category",

        CASE 
            WHEN IFNULL(capitalize_repair_cost, 0) = 1 THEN 'Yes'
            ELSE 'No'
        END AS "Capitalized",

        Type AS "Source Type",
        item_code AS "Item Code",
        item_name AS "Item Name",
        description_item AS "Description",
        uom AS "UOM",

        ROUND(qty, 2) AS "Qty",
        ROUND(rate, 2) AS "Rate",
        ROUND(Amount, 2) AS "Amount",

        custom_contract AS "Contract",

        purchase_invoice AS "Purchase Invoice",
        supplier AS "Supplier",

        stock_entry AS "Stock Entry",
        stock_entry_type AS "Stock Entry Type",
        posting_date AS "Stock Entry Date",

        debit_account,

        CASE 
            WHEN rn = 1 THEN ROUND(debit_amount, 2)
            ELSE NULL
        END AS "Debit Amount",

        credit_account,

        CASE 
            WHEN rn = 1 THEN ROUND(credit_amount, 2)
            ELSE NULL
        END AS "Credit Amount"

    FROM (

        SELECT 
            ar.name AS "Repair ID",
            ar.asset,
            ar.asset_name,
            ar.company,
            ar.branch,
            ar.cost_center,
            ar.segment,
            ar.custom_repair_type,
            ar.repair_status,

            ar.failure_date,
            ar.completion_date,
            ar.downtime,

            ar.description,
            ar.actions_performed,

            a.status AS asset_status,
            a.asset_category,

            ar.capitalize_repair_cost,

            'Stock' AS Type,

            css.item_code,
            css.item_name,
            i.description AS description_item,
            i.stock_uom AS uom,
            css.consumed_quantity AS qty,
            css.valuation_rate AS rate,
            css.total_value AS Amount,

            NULL AS custom_contract,
            NULL AS purchase_invoice,
            NULL AS supplier,

            css.stock_entry,
            se.purpose AS stock_entry_type,
            se.posting_date,

            gl_summary.debit_account,
            gl_summary.debit_amount,
            gl_summary.credit_account,
            gl_summary.credit_amount,

            ROW_NUMBER() OVER (
                PARTITION BY css.stock_entry
                ORDER BY css.item_code
            ) AS rn,

            1 AS sort_order

        FROM `tabAsset Repair` ar
        LEFT JOIN `tabAsset` a 
            ON a.name = ar.asset   

        LEFT JOIN `tabAsset Repair Settlement` css 
            ON css.parent = ar.name

        LEFT JOIN `tabStock Entry` se 
            ON se.name = css.stock_entry

        LEFT JOIN `tabItem` i 
            ON i.name = css.item_code

        LEFT JOIN (
            SELECT 
                voucher_no,
                MAX(CASE WHEN debit > 0 THEN account END) AS debit_account,
                SUM(debit) AS debit_amount,
                MAX(CASE WHEN credit > 0 THEN account END) AS credit_account,
                SUM(credit) AS credit_amount
            FROM `tabGL Entry`
            WHERE voucher_type = 'Stock Entry'
            GROUP BY voucher_no
        ) gl_summary 
            ON gl_summary.voucher_no = css.stock_entry

        WHERE 
            ar.docstatus IN (0,1)
            AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s
            {conditions}

        UNION ALL

        SELECT 
            ar.name,
            ar.asset,
            ar.asset_name,
            ar.company,
            ar.branch,
            ar.cost_center,
            ar.segment,
            ar.custom_repair_type,
            ar.repair_status,

            ar.failure_date,
            ar.completion_date,
            ar.downtime,

            ar.description,
            ar.actions_performed,

            a.status,
            a.asset_category,

            ar.capitalize_repair_cost,

            'Purchase',

            pii.item_code,
            pii.item_name,
            pii.description,
            pii.uom,
            pii.qty,
            pii.rate,
            pii.amount,

            pii.custom_contract,

            pi.purchase_invoice,
            CONCAT(p.supplier, ' - ', p.supplier_name),

            NULL,
            NULL,
            p.posting_date,

            NULL,
            NULL,
            NULL,
            NULL,

            1 AS rn,

            2 AS sort_order

        FROM `tabAsset Repair` ar

        LEFT JOIN `tabAsset` a 
            ON a.name = ar.asset   

        LEFT JOIN `tabAsset Repair Purchase Invoice` pi 
            ON pi.parent = ar.name

        LEFT JOIN `tabPurchase Invoice` p 
            ON p.name = pi.purchase_invoice

        LEFT JOIN `tabPurchase Invoice Item` pii 
            ON pii.parent = p.name

        WHERE 
            ar.docstatus IN (0,1)
            AND p.posting_date BETWEEN %(from_date)s AND %(to_date)s
            {conditions}

        UNION ALL

        SELECT 
            ar.name,
            ar.asset,
            ar.asset_name,
            ar.company,
            ar.branch,
            ar.cost_center,
            ar.segment,
            ar.custom_repair_type,
            ar.repair_status,

            ar.failure_date,
            ar.completion_date,
            ar.downtime,

            ar.description,
            ar.actions_performed,

            a.status,
            a.asset_category,

            ar.capitalize_repair_cost,

            '' AS Type,

            NULL AS item_code,
            NULL AS item_name,
            NULL AS description_item,
            NULL AS uom,
            NULL AS qty,
            NULL AS rate,
            NULL AS Amount,

            NULL AS custom_contract,
            NULL AS purchase_invoice,
            NULL AS supplier,

            NULL AS stock_entry,
            NULL AS stock_entry_type,
            NULL AS posting_date,

            NULL AS debit_account,
            NULL AS debit_amount,
            NULL AS credit_account,
            NULL AS credit_amount,

            1 AS rn,

            3 AS sort_order

        FROM `tabAsset Repair` ar

        LEFT JOIN `tabAsset` a 
            ON a.name = ar.asset   

        WHERE 
            ar.docstatus IN (0,1)
            {conditions}

            AND NOT EXISTS (
                SELECT 1 
                FROM `tabAsset Repair Settlement` css 
                WHERE css.parent = ar.name
            )

            AND NOT EXISTS (
                SELECT 1 
                FROM `tabAsset Repair Purchase Invoice` pi 
                WHERE pi.parent = ar.name
            )

    ) AS final_data

    ORDER BY 
        `Repair ID`,
        sort_order
    """

    query = query.format(conditions=conditions)

    return frappe.db.sql(query, query_filters, as_dict=1)