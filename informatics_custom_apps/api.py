import frappe
from frappe import _


@frappe.whitelist()
def reopen_loan(loan_name, reason):
    loan = frappe.get_doc("Loan", loan_name)
    ld= frappe.db.exists("Loan Disbursement", {"against_loan": loan_name, "docstatus": 1})
    # Update status
    if ld:
        loan.db_set("status", "Disbursed")
    else:
        loan.db_set("status", "Sanctioned")

    # Add comment with user input
    loan.add_comment(
        "Comment",
        _("{0} reopened this loan, Reason: {1}").format(frappe.session.user, reason)
    )

    frappe.db.commit()
    return {"status": "success"}


@frappe.whitelist()
def make_purchase_receipt_paddy(master, Items):
    try:
        purchase_receipt = frappe.new_doc("Purchase Receipt")
        purchase_receipt.set_posting_time = 1
        purchase_receipt.posting_date = master.get("posting_date")
        purchase_receipt.company = master.get("company")
        purchase_receipt.vehicle_no = master.get("vehicle_no")
        purchase_receipt.supplier = master.get("supplier")
        purchase_receipt.branch = master.get("plant")
        purchase_receipt.bill_no = master.get("bill_no")
        purchase_receipt.bill_date = master.get("bill_date")
        purchase_receipt.supplier_warehouse = master.get("warehouse")
        purchase_receipt.custom_transport = master.get("custom_transport")
        purchase_receipt.custom_loading_unloading = master.get("custom_loading_unloading")
        purchase_receipt.cost_center = master.get("cost_center")
        purchase_receipt.custom_commission = master.get("custom_commission")

        for item in Items:
            # Fetch purchase_order_item automatically
            purchase_order_item = frappe.db.get_value(
                "Purchase Order Item",
                {
                    "parent": item.get("purchase_order"),
                    "item_code": item.get("name")
                },
                "name"
            )

            purchase_receipt.append("items", {
                "item_code": item.get("name"),
                "purchase_order": item.get("purchase_order"),
                "purchase_order_item": purchase_order_item,
                "warehouse": master.get("warehouse"),
                "uom": frappe.get_value("Item", {"item_code": item.get("name")}, "stock_uom"),
                "qty": item.get("qty"),
                "custom_cane_type": item.get("cane_type"),
                "rate": item.get("rate")
            })

        purchase_receipt.tax_category = "In-State"
        tax_charge = frappe.get_value(
            "Branch",
            {"name": master.get("plant")},
            "custom_cane_purchase_tax"
        )
        purchase_receipt.taxes_and_charges = tax_charge

        taxes = get_taxes_and_charges(
            "Purchase Taxes and Charges Template",
            purchase_receipt.taxes_and_charges
        )

        tax_sum = 0
        if taxes:
            for tax in taxes:
                tax.cost_center = master.get("cost_center")

                if tax.custom_formula == "custom_insurance_expenses":
                    tax.tax_amount = purchase_receipt.custom_insurance_expenses or 0
                elif tax.custom_formula == "custom_transport":
                    tax.tax_amount = purchase_receipt.custom_transport or 0
                elif tax.custom_formula == "custom_loading_unloading":
                    tax.tax_amount = purchase_receipt.custom_loading_unloading or 0
                elif tax.custom_formula == "custom_packing_handling":
                    tax.tax_amount = purchase_receipt.custom_packing_handling or 0
                elif tax.custom_formula == "custom_short_excess":
                    tax.tax_amount = purchase_receipt.custom_short_excess or 0
                elif tax.custom_formula == "custom_freight_on_bill":
                    tax.tax_amount = purchase_receipt.custom_freight_on_bill or 0
                elif tax.custom_formula == "custom_tcs":
                    tax.tax_amount = purchase_receipt.custom_tcs or 0
                elif tax.custom_formula == "custom_commission":
                    tax.tax_amount = purchase_receipt.custom_commission or 0
                else:
                    tax.tax_amount = 0

                tax_sum += float(tax.get("tax_amount") or 0)
                purchase_receipt.append("taxes", tax)

            purchase_receipt.save(ignore_permissions=True)

            if purchase_receipt.custom_overall_qc_status is None:
                purchase_receipt.db_set("custom_overall_qc_status", "Completed")

            return {
                "status": "success",
                "message": "Purchase Receipt Created",
                "purchase_receipt": purchase_receipt.name
            }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Purchase Receipt Creation Error")
        frappe.local.response["Purchase_Receipt"] = "Not Created Purchase Receipt"
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def get_taxes_and_charges(master_doctype, master_name):
    if not master_name:
        return

    from frappe.model import child_table_fields, default_fields

    tax_master = frappe.get_doc(master_doctype, master_name)
    taxes_and_charges = []

    for _i, tax in enumerate(tax_master.get("taxes")):
        tax = tax.as_dict()

        for fieldname in default_fields + child_table_fields:
            if fieldname in tax:
                del tax[fieldname]

        taxes_and_charges.append(tax)

    print("-------------->", len(taxes_and_charges))
    return taxes_and_charges

@frappe.whitelist()
def update_attendance_for_half_day(doc, event):
    print("------> Running update_attendance_for_half_day")

    if not doc.half_day or doc.status != "Approved":
        print("------> Exit The  update_attendance_for_half_day Function")
        return

    # Find related attendance record
    attendance = frappe.db.get_value(
        "Attendance",
        {"employee": doc.employee, "attendance_date": doc.from_date},
        "name"
    )

    if attendance:
        att_doc = frappe.get_doc("Attendance", attendance)
        print("---------->Attendance",attendance)
        if att_doc.docstatus == 1 and att_doc.status == "Half Day" and att_doc.leave_application and att_doc.half_day_status=="Present" and not att_doc.working_hours:
            att_doc.db_set("half_day_status", "Absent")
            print("-------> Updated attendance half_day_status")
        else:
            print("------> Exit The  update_attendance_for_half_day Function")

@frappe.whitelist()
def add_asset_date(docname, required_date):
    asset = frappe.get_doc("Asset", docname)
    if not asset.available_for_use_date and not asset.purchase_date:
        asset.db_set("available_for_use_date", required_date)
        asset.db_set("purchase_date", required_date)
        
        
from erpnext.buying.doctype.purchase_order.purchase_order import (
    make_purchase_receipt as original_make_purchase_receipt
)


@frappe.whitelist()
def make_purchase_receipt(source_name, target_doc=None):

    po = frappe.get_doc("Purchase Order", source_name)

    blocked_items = []

    for row in po.items:

        item_group = frappe.db.get_value(
            "Item",
            row.item_code,
            "item_group"
        )

        is_weighment_required = frappe.db.get_value(
            "Item Group",
            item_group,
            "custom_is_weighment_required"
        )

        if is_weighment_required == "Yes":

            blocked_items.append(
                f"{row.item_code} - {row.item_name}"
            )

    if blocked_items:

        frappe.throw(_(
            "Purchase Receipt cannot be created because "
            "Weighment is required for the following item(s):"
            "<br><br><br><b>{0}</b>"
        ).format("<br>".join(blocked_items)))

    return original_make_purchase_receipt(
        source_name,
        target_doc
    )