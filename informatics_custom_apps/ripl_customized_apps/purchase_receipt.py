import frappe

@frappe.whitelist()
def update_rejected_warehouse(purchase_receipt):

    pr = frappe.get_doc("Purchase Receipt", purchase_receipt)

    if not pr.branch:
        frappe.throw("Plant is not selected.")

    rejected_warehouse = frappe.db.get_value(
        "Branch",
        pr.branch,
        "custom_return_and_rejected_warehouse"
    )

    if not rejected_warehouse:
        frappe.throw(
            f"Rejected Warehouse is not set for Plant {pr.branch}"
        )

    for item in pr.items:
        item.rejected_warehouse = rejected_warehouse

    pr.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "warehouse": rejected_warehouse
    }