import frappe
from frappe.utils import today, add_days


def auto_close_po_specific_items():

	current_date = today()

	po_items = frappe.db.sql("""
		SELECT
			poi.parent AS po,
			poi.item_code,
			poi.schedule_date,

			IFNULL(i.custom_buffer_days, 0) AS buffer_days,
			IFNULL(i.custom_auto_close_po, 0) AS auto_close_po,

			CASE
				WHEN IFNULL(poi.conversion_factor, 0) > 0
				THEN poi.rate / poi.conversion_factor
				ELSE poi.rate
			END AS po_stock_uom_rate,

			(
				SELECT
					CASE
						WHEN IFNULL(pri.conversion_factor, 0) > 0
						THEN pri.rate / pri.conversion_factor
						ELSE pri.rate
					END
				FROM `tabPurchase Receipt Item` pri

				INNER JOIN `tabPurchase Receipt` pr
					ON pr.name = pri.parent

				WHERE
					pri.item_code = poi.item_code
					AND pr.docstatus = 1

				ORDER BY pr.posting_date DESC, pr.creation DESC
				LIMIT 1
			) AS latest_stock_uom_rate

		FROM `tabPurchase Order Item` poi

		INNER JOIN `tabPurchase Order` po
			ON po.name = poi.parent

		INNER JOIN `tabItem` i
			ON i.item_code = poi.item_code

		WHERE
			po.docstatus = 1

			AND po.status NOT IN (
				'Closed',
				'Completed',
				'Cancelled'
			)

			-- Only items enabled for auto close
			AND IFNULL(i.custom_auto_close_po, 0) = 1
	""", as_dict=1)

	if not po_items:
		return

	to_close = []

	for d in po_items:

		buffer_days = d.buffer_days or 0

		before_days = add_days(current_date, -buffer_days)

		if not d.schedule_date or d.schedule_date > before_days:
			continue

		latest_price = d.latest_stock_uom_rate or 0
		po_rate = d.po_stock_uom_rate or 0

		if latest_price and po_rate > latest_price:
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
			title="PO Auto Close - Dynamic Buffer Days"
		)