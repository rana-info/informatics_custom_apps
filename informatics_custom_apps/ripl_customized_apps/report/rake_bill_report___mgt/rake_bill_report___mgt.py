import frappe


def execute(filters=None):
    filters = filters or {}

    if filters.get("show_detail"):
        columns = get_detail_columns()
    else:
        columns = get_summary_columns()

    data = get_data(filters)

    return columns, data

def get_summary_columns():
    return [
        {
            "label": "Item Name",
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": "PO Qty",
            "fieldname": "po_qty",
            "fieldtype": "Int",
            "width": 120
        },
        {
            "label": "Billed Qty",
            "fieldname": "billed_qty",
            "fieldtype": "Int",
            "width": 130
        },
        {
            "label": "Tolerance Qty",
            "fieldname": "tolerance_qty",
            "fieldtype": "Int",
            "width": 160
        },
        {
            "label": "Gate Entry Received Qty",
            "fieldname": "gate_entry_received_qty",
            "fieldtype": "Int",
            "width": 220
        },
        {
            "label": "Billed To After Tolerance",
            "fieldname": "billed_to_after_tolerance",
            "fieldtype": "Int",
            "width": 220
        },
        {
            "label": "Factory Received Qty",
            "fieldname": "factory_received_qty",
            "fieldtype": "Int",
            "width": 200
        },
        {
            "label": "Short Billed Qty",
            "fieldname": "short_billed_qty",
            "fieldtype": "Int",
            "width": 180
        },
        {
            "label": "Debit Note Qty",
            "fieldname": "debit_note_qty",
            "fieldtype": "Int",
            "width": 180
        },
        {
            "label": "Plant",
            "fieldname": "branch",
            "fieldtype": "Link",
            "options": "Branch",
            "width": 150
        },
        {
            "label": "Company",
            "fieldname": "company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 150
        },
        {
            "label": "Segment",
            "fieldname": "segment",
            "fieldtype": "Data",
            "width": 150
        }
    ]

def get_detail_columns():
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
            "label": "PO Qty",
            "fieldname": "po_qty",
            "fieldtype": "Int",
            "width": 120
        },
        {
            "label": "Rate",
            "fieldname": "rate",
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "label": "Billed Qty",
            "fieldname": "billed_qty",
            "fieldtype": "Int",
            "width": 130
        },
        {
            "label": "Tolerance Qty",
            "fieldname": "tolerance_qty",
            "fieldtype": "Int",
            "width": 160
        },
        {
            "label": "Gate Entry Received Qty",
            "fieldname": "gate_entry_received_qty",
            "fieldtype": "Int",
            "width": 220
        },
        {
            "label": "Billed To After Tolerance",
            "fieldname": "billed_to_after_tolerance",
            "fieldtype": "Int",
            "width": 220
        },
        {
            "label": "Factory Received Qty",
            "fieldname": "factory_received_qty",
            "fieldtype": "Int",
            "width": 200
        },
        {
            "label": "Short Billed Qty",
            "fieldname": "short_billed_qty",
            "fieldtype": "Int",
            "width": 180
        },
        {
            "label": "Debit Note Qty",
            "fieldname": "debit_note_qty",
            "fieldtype": "Int",
            "width": 180
        },
        {
            "label": "Plant",
            "fieldname": "branch",
            "fieldtype": "Link",
            "options": "Branch",
            "width": 150
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
            "label": "Segment",
            "fieldname": "segment",
            "fieldtype": "Data",
            "width": 150
        }
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

              ROUND(SUM(
                    CASE
                        WHEN poi.uom = 'KGS' THEN IFNULL(rb.po_qty,0) / 1000
                        WHEN poi.uom = 'Quintal' THEN IFNULL(rb.po_qty,0) / 10
                        ELSE IFNULL(rb.po_qty,0)
                    END
                ),2) AS po_qty,

                ROUND(SUM(
                    CASE
                        WHEN poi.uom = 'KGS' THEN IFNULL(rb.billed_qty,0) / 1000
                        WHEN poi.uom = 'Quintal' THEN IFNULL(rb.billed_qty,0) / 10
                        ELSE IFNULL(rb.billed_qty,0)
                    END
                ),2) AS billed_qty,

                ROUND(SUM(
                    CASE
                        WHEN poi.uom = 'KGS' THEN IFNULL(rb.tolerance_qty,0) / 1000
                        WHEN poi.uom = 'Quintal' THEN IFNULL(rb.tolerance_qty,0) / 10
                        ELSE IFNULL(rb.tolerance_qty,0)
                    END
                ),2) AS tolerance_qty,

                ROUND(SUM(
                    CASE
                        WHEN poi.uom = 'KGS' THEN IFNULL(rb.gate_entry_received_qty,0) / 1000
                        WHEN poi.uom = 'Quintal' THEN IFNULL(rb.gate_entry_received_qty,0) / 10
                        ELSE IFNULL(rb.gate_entry_received_qty,0)
                    END
                ),2) AS gate_entry_received_qty,

                ROUND(SUM(
                    CASE
                        WHEN poi.uom = 'KGS' THEN IFNULL(rb.billed_to_after_tolerance,0) / 1000
                        WHEN poi.uom = 'Quintal' THEN IFNULL(rb.billed_to_after_tolerance,0) / 10
                        ELSE IFNULL(rb.billed_to_after_tolerance,0)
                    END
                ),2) AS billed_to_after_tolerance,

                ROUND(SUM(
                    CASE
                        WHEN poi.uom = 'KGS' THEN IFNULL(rb.factory_received_qty,0) / 1000
                        WHEN poi.uom = 'Quintal' THEN IFNULL(rb.factory_received_qty,0) / 10
                        ELSE IFNULL(rb.factory_received_qty,0)
                    END
                ),2) AS factory_received_qty,

                ROUND(SUM(
                    CASE
                        WHEN poi.uom = 'KGS' THEN IFNULL(rb.short_billed_qty,0) / 1000
                        WHEN poi.uom = 'Quintal' THEN IFNULL(rb.short_billed_qty,0) / 10
                        ELSE IFNULL(rb.short_billed_qty,0)
                    END
                ),2) AS short_billed_qty,

                ROUND(SUM(
                    CASE
                        WHEN poi.uom = 'KGS' THEN IFNULL(rb.debit_note_qty,0) / 1000
                        WHEN poi.uom = 'Quintal' THEN IFNULL(rb.debit_note_qty,0) / 10
                        ELSE IFNULL(rb.debit_note_qty,0)
                    END
                ),2) AS debit_note_qty,

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
            AND po.docstatus = 1
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
               CASE
                    WHEN poi.uom = 'KGS'
                        THEN ROUND(IFNULL(poi.rate,0) * 1000, 2)
                    WHEN poi.uom = 'Quintal'
                        THEN ROUND(IFNULL(poi.rate,0) * 10, 2)
                    ELSE
                        ROUND(IFNULL(poi.rate,0), 2)
                END AS rate,
                COALESCE(pi.company, po.company) AS company,
                COALESCE(pi.branch, po.branch) AS branch,
                COALESCE(pi.segment, po.segment) AS segment,

               CASE
                    WHEN poi.uom = 'KGS' THEN ROUND(IFNULL(rb.po_qty,0)/1000,2)
                    WHEN poi.uom = 'Quintal' THEN ROUND(IFNULL(rb.po_qty,0)/10,2)
                    ELSE ROUND(IFNULL(rb.po_qty,0),2)
                END AS po_qty,

                CASE
                    WHEN poi.uom = 'KGS' THEN ROUND(IFNULL(rb.billed_qty,0)/1000,2)
                    WHEN poi.uom = 'Quintal' THEN ROUND(IFNULL(rb.billed_qty,0)/10,2)
                    ELSE ROUND(IFNULL(rb.billed_qty,0),2)
                END AS billed_qty,

                CASE
                    WHEN poi.uom = 'KGS' THEN ROUND(IFNULL(rb.tolerance_qty,0)/1000,2)
                    WHEN poi.uom = 'Quintal' THEN ROUND(IFNULL(rb.tolerance_qty,0)/10,2)
                    ELSE ROUND(IFNULL(rb.tolerance_qty,0),2)
                END AS tolerance_qty,

                CASE
                    WHEN poi.uom = 'KGS' THEN ROUND(IFNULL(rb.gate_entry_received_qty,0)/1000,2)
                    WHEN poi.uom = 'Quintal' THEN ROUND(IFNULL(rb.gate_entry_received_qty,0)/10,2)
                    ELSE ROUND(IFNULL(rb.gate_entry_received_qty,0),2)
                END AS gate_entry_received_qty,

                CASE
                    WHEN poi.uom = 'KGS' THEN ROUND(IFNULL(rb.billed_to_after_tolerance,0)/1000,2)
                    WHEN poi.uom = 'Quintal' THEN ROUND(IFNULL(rb.billed_to_after_tolerance,0)/10,2)
                    ELSE ROUND(IFNULL(rb.billed_to_after_tolerance,0),2)
                END AS billed_to_after_tolerance,

                CASE
                    WHEN poi.uom = 'KGS' THEN ROUND(IFNULL(rb.factory_received_qty,0)/1000,2)
                    WHEN poi.uom = 'Quintal' THEN ROUND(IFNULL(rb.factory_received_qty,0)/10,2)
                    ELSE ROUND(IFNULL(rb.factory_received_qty,0),2)
                END AS factory_received_qty,

                CASE
                    WHEN poi.uom = 'KGS' THEN ROUND(IFNULL(rb.short_billed_qty,0)/1000,2)
                    WHEN poi.uom = 'Quintal' THEN ROUND(IFNULL(rb.short_billed_qty,0)/10,2)
                    ELSE ROUND(IFNULL(rb.short_billed_qty,0),2)
                END AS short_billed_qty,

                CASE
                    WHEN poi.uom = 'KGS' THEN ROUND(IFNULL(rb.debit_note_qty,0)/1000,2)
                    WHEN poi.uom = 'Quintal' THEN ROUND(IFNULL(rb.debit_note_qty,0)/10,2)
                    ELSE ROUND(IFNULL(rb.debit_note_qty,0),2)
                END AS debit_note_qty,
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
            AND po.docstatus = 1
            {conditions}

            ORDER BY rb.creation DESC
        """

    return frappe.db.sql(query, values, as_dict=True)