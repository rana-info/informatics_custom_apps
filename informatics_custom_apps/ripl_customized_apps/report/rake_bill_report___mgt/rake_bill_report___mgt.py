import frappe


def execute(filters=None):
    filters = filters or {}

    columns = get_columns(filters)
    data = get_data(filters)

    return columns, data


def get_columns(filters=None):

    return [
        {
            "label": "Rake Bill No",
            "fieldname": "name",
            "fieldtype": "Link",
            "options": "Rake Bill",
            "width": 120
        },
        {
            "label": "Item Name",
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": "PO Qty (MT)",
            "fieldname": "po_qty",
            "fieldtype": "Int",
            "width": 120
        },
        {
            "label": "Billed Qty (MT)",
            "fieldname": "billed_qty",
            "fieldtype": "Int",
            "width": 130
        },
        {
            "label": "Tolerance Qty (MT)",
            "fieldname": "tolerance_qty",
            "fieldtype": "Int",
            "width": 160
        },
        {
            "label": "Gate Entry Received Qty (MT)",
            "fieldname": "gate_entry_received_qty",
            "fieldtype": "Int",
            "width": 220
        },
        {
            "label": "Billed To After Tolerance (MT)",
            "fieldname": "billed_to_after_tolerance",
            "fieldtype": "Int",
            "width": 220
        },
        {
            "label": "Factory Received Qty (MT)",
            "fieldname": "factory_received_qty",
            "fieldtype": "Int",
            "width": 200
        },
        {
            "label": "Short Billed Qty (MT)",
            "fieldname": "short_billed_qty",
            "fieldtype": "Int",
            "width": 180
        },
        {
            "label": "Debit Note Qty (MT)",
            "fieldname": "debit_note_qty",
            "fieldtype": "Int",
            "width": 180
        },

        {
            "label": "Supplier Invoice No",
            "fieldname": "supplier_invoice_no",
            "fieldtype": "Data",
            "width": 160
        },
        {
            "label": "Supplier Invoice Date",
            "fieldname": "supplier_invoice_date",
            "fieldtype": "Date",
            "width": 160
        },
        {
            "label": "Purchase Invoice Date",
            "fieldname": "purchase_invoice_date",
            "fieldtype": "Date",
            "width": 170
        },
        {
            "label": "Purchase Order",
            "fieldname": "purchase_order",
            "fieldtype": "Link",
            "options": "Purchase Order",
            "width": 160
        },
        {
            "label": "Incoterm",
            "fieldname": "incoterm",
            "fieldtype": "Data",
            "width": 120
        },
          {
            "label": "Company",
            "fieldname": "company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 150
        },
        {
            "label": "Plant",
            "fieldname": "branch",
            "fieldtype": "Link",
            "options": "Branch",
            "width": 150
        },
        {
            "label": "Segment",
            "fieldname": "segment",
            "fieldtype": "Data",
            "width": 150
        },

    ]

def get_data(filters):

    conditions = ""
    values = {}

    if filters.get("from_date") and filters.get("to_date"):
        conditions += """
          AND DATE(rb.creation) BETWEEN %(from_date)s AND %(to_date)s
        """
        values["from_date"] = filters.get("from_date")
        values["to_date"] = filters.get("to_date")

    if filters.get("company"):
        companies = filters.get("company")
        if isinstance(companies, str):
            companies = [d.strip() for d in companies.split(",") if d.strip()]

        conditions += " AND COALESCE(pi.company, po.company) IN %(company)s"
        values["company"] = tuple(companies)

    if filters.get("branch"):
        branches = filters.get("branch")
        if isinstance(branches, str):
            branches = [d.strip() for d in branches.split(",") if d.strip()]

        conditions += " AND COALESCE(pi.branch, po.branch) IN %(branch)s"
        values["branch"] = tuple(branches)

    if filters.get("segment"):
        segments = filters.get("segment")
        if isinstance(segments, str):
            segments = [d.strip() for d in segments.split(",") if d.strip()]

        conditions += " AND COALESCE(pi.segment, po.segment) IN %(segment)s"
        values["segment"] = tuple(segments)

    if filters.get("show_detail") != 1:

        query = f"""
            SELECT
                NULL AS name,
                poi.item_name,

                COALESCE(pi.company, po.company) AS company,
                COALESCE(pi.branch, po.branch) AS branch,
                COALESCE(pi.segment, po.segment) AS segment,

                ROUND(SUM(IFNULL(rb.po_qty,0))/1000) AS po_qty,
                ROUND(SUM(IFNULL(rb.billed_qty,0))/1000) AS billed_qty,
                ROUND(SUM(IFNULL(rb.tolerance_qty,0))/1000) AS tolerance_qty,
                ROUND(SUM(IFNULL(rb.gate_entry_received_qty,0))/1000) AS gate_entry_received_qty,
                ROUND(SUM(IFNULL(rb.billed_to_after_tolerance,0))/1000) AS billed_to_after_tolerance,
                ROUND(SUM(IFNULL(rb.factory_received_qty,0))/1000) AS factory_received_qty,
                ROUND(SUM(IFNULL(rb.short_billed_qty,0))/1000) AS short_billed_qty,
                ROUND(SUM(IFNULL(rb.debit_note_qty,0))/1000) AS debit_note_qty,

                NULL AS supplier_invoice_no,
                NULL AS supplier_invoice_date,
                NULL AS purchase_invoice_date,
                NULL AS purchase_order,
                NULL AS incoterm

            FROM `tabRake Bill` rb

            LEFT JOIN `tabPurchase Invoice` pi
                ON pi.name = rb.purchase_invoice

            LEFT JOIN `tabPurchase Order` po
                ON po.name = rb.purchase_order

            LEFT JOIN `tabPurchase Order Item` poi
                ON poi.parent = po.name

            WHERE rb.docstatus < 2
            {conditions}

            GROUP BY
                COALESCE(pi.company, po.company),
                COALESCE(pi.branch, po.branch),
                COALESCE(pi.segment, po.segment),
                poi.item_name

            ORDER BY branch
        """


    else:

        query = f"""
            SELECT
                rb.name,
                poi.item_name,

                COALESCE(pi.company, po.company) AS company,
                COALESCE(pi.branch, po.branch) AS branch,
                COALESCE(pi.segment, po.segment) AS segment,

                ROUND(IFNULL(rb.po_qty,0)/1000) AS po_qty,
                ROUND(IFNULL(rb.billed_qty,0)/1000) AS billed_qty,
                ROUND(IFNULL(rb.tolerance_qty,0)/1000) AS tolerance_qty,
                ROUND(IFNULL(rb.gate_entry_received_qty,0)/1000) AS gate_entry_received_qty,
                ROUND(IFNULL(rb.billed_to_after_tolerance,0)/1000) AS billed_to_after_tolerance,
                ROUND(IFNULL(rb.factory_received_qty,0)/1000) AS factory_received_qty,
                ROUND(IFNULL(rb.short_billed_qty,0)/1000) AS short_billed_qty,
                ROUND(IFNULL(rb.debit_note_qty,0)/1000) AS debit_note_qty,

                rb.supplier_invoice_no,
                rb.supplier_invoice_date,
                pi.posting_date AS purchase_invoice_date,
                rb.purchase_order,
                rb.incoterm

            FROM `tabRake Bill` rb

            LEFT JOIN `tabPurchase Invoice` pi
                ON pi.name = rb.purchase_invoice

            LEFT JOIN `tabPurchase Order` po
                ON po.name = rb.purchase_order

            LEFT JOIN `tabPurchase Order Item` poi
                ON poi.parent = po.name

            WHERE rb.docstatus < 2
            {conditions}

            ORDER BY rb.creation DESC
        """

    return frappe.db.sql(query, values, as_dict=True)