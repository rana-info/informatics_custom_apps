import frappe


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	total_row = {
		"po_no": "TOTAL",
		"ordered_qty": sum(d.get("ordered_qty", 0) or 0 for d in data),
		"received_qty": sum(d.get("received_qty", 0) or 0 for d in data),
		"pending_qty": sum(d.get("pending_qty", 0) or 0 for d in data),
		"po_value": sum(d.get("po_value", 0) or 0 for d in data),
		"is_total_row": 1
	}

	data = [total_row] + data

	return columns, data


def get_columns():
	return [
		{"label": "PO No", "fieldname": "po_no", "fieldtype": "Link", "options": "Purchase Order", "width": 190},
		{"label": "Item Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 240},
		{"label": "Supplier Name", "fieldname": "supplier_name", "fieldtype": "Data", "width": 190},
		{"label": "PO Date", "fieldname": "po_date", "fieldtype": "Date", "width": 120},
		{"label": "Ordered Qty", "fieldname": "ordered_qty", "fieldtype": "Float", "width": 120},
		{"label": "Received Qty", "fieldname": "received_qty", "fieldtype": "Float", "width": 120},
		{"label": "Pending Qty", "fieldname": "pending_qty", "fieldtype": "Float", "width": 120},
		{"label": "PO Value", "fieldname": "po_value", "fieldtype": "Currency", "width": 140},
		{"label": "Receipt Status", "fieldname": "receipt_status", "fieldtype": "Data", "width": 140},
		{"label": "Plant", "fieldname": "plant", "fieldtype": "Data", "width": 140},
		{"label": "UOM", "fieldname": "uom", "fieldtype": "Data", "width": 80},
		{"label": "Segment", "fieldname": "segment", "fieldtype": "Data", "width": 140},
		{"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 140},
		{"label": "PO Status", "fieldname": "po_status", "fieldtype": "Data", "width": 120},
		{"label": "Supplier ID", "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 140},
		{"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": "Item Group", "fieldname": "item_group", "fieldtype": "Data", "width": 140},
		{"label": "Warehouse", "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 160},
		{"label": "Purchase Receipts", "fieldname": "purchase_receipts", "fieldtype": "Data", "width": 220},
	]



def get_data(filters):

	conditions = ""
	values = {}

	if filters.get("from_date") and filters.get("to_date"):
		conditions += " AND po.transaction_date BETWEEN %(from_date)s AND %(to_date)s"
		values["from_date"] = filters.get("from_date")
		values["to_date"] = filters.get("to_date")

	if filters.get("company"):
		companies = filters.get("company")
		if isinstance(companies, str):
			companies = [c.strip() for c in companies.split(",") if c.strip()]
		conditions += " AND po.company IN %(company)s"
		values["company"] = tuple(companies)

	if filters.get("plant"):
		plants = filters.get("plant")
		if isinstance(plants, str):
			plants = [p.strip() for p in plants.split(",") if p.strip()]
		conditions += " AND wh.custom_branch IN %(plant)s"
		values["plant"] = tuple(plants)

	data = frappe.db.sql(f"""
		SELECT
    po.transaction_date AS po_date,
    po.name AS po_no,
    po.company,
    po.status AS po_status,
    po.supplier,
    po.supplier_name,

    poi.item_code,
    poi.item_name,
    i.item_group,
    poi.uom,

    poi.warehouse,
    wh.custom_branch AS plant,
    wh.custom_segment AS segment,

    poi.qty AS ordered_qty,

    IFNULL(pri.received_qty, 0) AS received_qty,

    GREATEST(
        poi.qty - IFNULL(pri.received_qty, 0),
        0
    ) AS pending_qty,

    po.grand_total AS po_value,

    GROUP_CONCAT(DISTINCT pri_sub.parent) AS purchase_receipts,

    CASE
        WHEN IFNULL(pri.received_qty, 0) = 0 THEN 'Not Received'
        WHEN IFNULL(pri.received_qty, 0) < poi.qty THEN 'Partially Received'
        ELSE 'Fully Received'
    END AS receipt_status

FROM `tabPurchase Order` po

JOIN `tabPurchase Order Item` poi
    ON po.name = poi.parent

LEFT JOIN (
    SELECT
        purchase_order_item,
        SUM(qty) AS received_qty
    FROM `tabPurchase Receipt Item`
    WHERE docstatus = 1
    GROUP BY purchase_order_item
) pri
    ON pri.purchase_order_item = poi.name

LEFT JOIN `tabPurchase Receipt Item` pri_sub
    ON pri_sub.purchase_order_item = poi.name
    AND pri_sub.docstatus = 1

LEFT JOIN `tabWarehouse` wh
    ON poi.warehouse = wh.name

LEFT JOIN `tabItem` i
    ON poi.item_code = i.name

WHERE
    po.docstatus = 1
    AND po.status NOT IN ('Closed', 'Completed')

    AND (
        poi.item_code IN (
            '106448',
            '106446',
            '106444'
        )
        OR i.item_group IN (
            '020301-Fuel-Trd',
            '020302-Fuel-Trd Non Weightment',
            '020104-Bagasse-Trd',
            '020104-Bagasse-Trd (Non Weighment)',
            '010108-Bagasse-Mfg (Non Weighment)',
            '010102-Bagasse-Mfg'
        )
    )

    {conditions}

GROUP BY
    po.name,
    poi.name

ORDER BY
    po.transaction_date DESC,
    po.name DESC
	""", values, as_dict=True)

	previous_po = None

	for row in data:
		if row["po_no"] == previous_po:
			row["po_value"] = ""
		else:
			previous_po = row["po_no"]

	return data