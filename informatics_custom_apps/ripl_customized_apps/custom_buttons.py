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
    

@frappe.whitelist()
def update_itc_claim_period(purchase_invoice, itc_claim_period):

    doc = frappe.get_doc("Purchase Invoice", purchase_invoice)

    doc.db_set(
        "itc_claim_period",
        itc_claim_period,
        update_modified=False
    )

    frappe.db.commit()

    return {
        "itc_claim_period": itc_claim_period
    }
    


@frappe.whitelist()
def update_transporter(sales_invoice, transporter):

    doc = frappe.get_doc("Sales Invoice", sales_invoice)

    if doc.docstatus == 2:
        frappe.throw("Cancelled Sales Invoice cannot be updated.")

    transporter_name = frappe.db.get_value(
        "Supplier",
        transporter,
        "supplier_name"
    )

    doc.db_set(
        "transporter",
        transporter,
        update_modified=False
    )

    doc.db_set(
        "transporter_name",
        transporter_name,
        update_modified=False
    )

    frappe.db.commit()

    return "Success"