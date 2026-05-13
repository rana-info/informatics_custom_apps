import frappe
from frappe.utils import today, add_days


TARGET_ITEMS = ("106446", "106444")


def auto_close_po_specific_items():

	current_date = today()

	before_30_days = add_days(current_date, -30)

	po_items = frappe.db.sql("""
		SELECT
			poi.parent AS po,
			poi.item_code,
			poi.rate,
			poi.schedule_date,

			(
				SELECT pri.rate
				FROM `tabPurchase Receipt Item` pri
				INNER JOIN `tabPurchase Receipt` pr
					ON pr.name = pri.parent
				WHERE
					pri.item_code = poi.item_code
					AND pr.docstatus = 1
				ORDER BY pr.posting_date DESC
				LIMIT 1
			) AS latest_price

		FROM `tabPurchase Order Item` poi

		INNER JOIN `tabPurchase Order` po
			ON po.name = poi.parent

		WHERE
			poi.item_code IN %(items)s

			AND po.docstatus = 1

			AND po.status NOT IN (
				'Closed',
				'Completed',
				'Cancelled'
			)

			-- Older than 30 days
			AND poi.schedule_date <= %(before_30_days)s

	""", {
		"items": TARGET_ITEMS,
		"before_30_days": before_30_days
	}, as_dict=1)

	if not po_items:
		return

	to_close = []

	for d in po_items:

		latest_price = d.latest_price or 0
		po_rate = d.rate or 0

		if po_rate > latest_price:
			to_close.append(d.po)

	to_close = list(set(to_close))

	if to_close:

		frappe.db.sql("""
			UPDATE `tabPurchase Order`
			SET status = 'Closed'
			WHERE name IN %(pos)s
		""", {
			"pos": tuple(to_close)
		})

		frappe.log_error(
			message=f"Auto closed POs: {', '.join(to_close)}",
			title="PO Auto Close - 30 Days + Higher Price"
		)