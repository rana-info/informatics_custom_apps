import frappe
from frappe.utils import today, add_days
from erpnext.controllers.buying_controller import BuyingController


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

# Method for Missing Stock Ledger Entry Creation For Purchase Receipts
def create_missing_return_pr_sles():

    missing_prs = frappe.db.sql("""
        SELECT pr.name FROM `tabPurchase Receipt` pr LEFT JOIN `tabPurchase Receipt Item` pri ON pr.name = pri.parent
		LEFT JOIN `tabItem` im ON pri.item_code = im.name
		LEFT JOIN `tabStock Ledger Entry` sle ON sle.voucher_type = 'Purchase Receipt'
		AND sle.voucher_no = pr.name WHERE pr.is_return = 1 AND pr.docstatus = 1 AND sle.name IS NULL 
		AND im.is_stock_item = 1 AND pr.posting_date >= '2026-04-01';
    """, as_dict=True)

    for row in missing_prs:
        pr_name = row.name

        try:
            frappe.logger().info(
                f"Creating missing SLE for Purchase Receipt {pr_name}"
            )

            doc = frappe.get_doc("Purchase Receipt", pr_name)

            BuyingController.update_stock_ledger(
                doc,
                allow_negative_stock=False,
                via_landed_cost_voucher=False
            )

            frappe.db.commit()

        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Failed to create SLE for {pr_name}"
            )

#Method to cacnel GL Entries for return prs

def cancel_gl_entries_for_return_prs():
	query=frappe.db.sql("""SELECT  gl.name from `tabGL Entry` as gl left join `tabPurchase Receipt` as pr on gl.voucher_no = pr.name
	where gl.is_cancelled = 0 and gl.posting_date >= '2026-04-01' and pr.is_return = 1 ;""",as_dict=1)
	for row in query:
		try:
			frappe.db.set_value("GL Entry", row.name, "is_cancelled", 1)
			frappe.get_doc("GL Entry", row.name).add_comment(
                "Comment",
                "Cancelled GL Entry for return PR through scheduled job"
            )
		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				f"Failed to cancel GL Entry {row.name} for return PR"
			)