import frappe
from frappe.utils import today

TARGET_ITEMS = ("106446", "106444")

def auto_close_po_specific_items():
	current_date = today()

	po_items = frappe.db.sql("""
		SELECT
			poi.parent AS po,
			poi.item_code,
			poi.qty,
			poi.received_qty
		FROM `tabPurchase Order Item` poi
		INNER JOIN `tabPurchase Order` po
			ON po.name = poi.parent
		WHERE poi.item_code IN %(items)s
		AND po.docstatus = 1
		AND po.status NOT IN ('Closed', 'Completed', 'Cancelled')
		AND IFNULL(poi.schedule_date, '') < %(today)s
	""", {
		"items": TARGET_ITEMS,
		"today": current_date
	}, as_dict=1)

	if not po_items:
		return

	po_map = {}

	for d in po_items:
		po_map.setdefault(d.po, []).append(d)

	to_close = list(po_map.keys())

	

	if to_close:
		frappe.db.sql("""
			UPDATE `tabPurchase Order`
			SET status = 'Closed'
			WHERE name IN %(pos)s
		""", {"pos": tuple(to_close)})

		frappe.log_error(
			message=f"Auto closed POs for overdue items: {', '.join(to_close)}",
			title="PO Auto Close (106446,106444 + Due Date)"
		)