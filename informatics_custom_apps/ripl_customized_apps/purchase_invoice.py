import frappe

@frappe.whitelist()
def update_itc_claim_period(purchase_invoice, itc_claim_period):

    doc = frappe.get_doc("Purchase Invoice", purchase_invoice)

    doc.db_set(
        "itc_claim_period",
        itc_claim_period,
        update_modified=True
    )

    frappe.db.commit()

    return {
        "itc_claim_period": itc_claim_period
    }