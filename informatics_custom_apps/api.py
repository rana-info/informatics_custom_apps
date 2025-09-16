import frappe
from frappe import _

@frappe.whitelist()
def reopen_loan(loan_name, reason):
    loan = frappe.get_doc("Loan", loan_name)
    
    # Update status
    loan.db_set("status", "Disbursed")

    # Add comment with user input
    loan.add_comment(
        "Comment", 
        _("{0} reopened this loan, Reason: {1}").format(frappe.session.user, reason)
    )

    frappe.db.commit()
    return {"status": "success"}

@frappe.whitelist()
def make_purchase_receipt_paddy(master,Items):
	try:
		purchase_receipt = frappe.new_doc("Purchase Receipt")
		purchase_receipt.set_posting_time = 1
		purchase_receipt.posting_date = master.get("posting_date")
		purchase_receipt.company = master.get("company")
		purchase_receipt.supplier = master.get("supplier")
		purchase_receipt.branch = master.get("plant")
		purchase_receipt.bill_no = master.get("bill_no")
		purchase_receipt.bill_date = master.get("bill_date")
		purchase_receipt.supplier_warehouse = master.get("warehouse")
		purchase_receipt.custom_transport = master.get("custom_transport")
		purchase_receipt.custom_loading_unloading = master.get("custom_loading_unloading")
		# purchase_receipt.db_set("custom_overall_qc_status","Completed")
		purchase_receipt.cost_center = master.get("cost_center")
		purchase_receipt.custom_commission = master.get("custom_commission")
		for item in Items:
			purchase_receipt.append("items",{
				"item_code":item.get("name"),
				"warehouse":master.get("warehouse"),
				"uom": frappe.get_value("Item", {"item_code": item.get("name")}, "stock_uom"),
				"qty":item.get('qty'),
				"custom_cane_type":item.get("cane_type"),
				"rate":item.get('rate') 
			})

		purchase_receipt.tax_category = "In-State"
		tax_charge = frappe.get_value("Branch", {"name": master.get("plant")}, "custom_cane_purchase_tax")
		purchase_receipt.taxes_and_charges = tax_charge
		taxes = get_taxes_and_charges("Purchase Taxes and Charges Template",purchase_receipt.taxes_and_charges)
		tax_sum = 0
		for tax in taxes:
			tax.cost_center = master.get("cost_center")
			if tax.custom_formula == "custom_insurance_expenses":
				tax.tax_amount = purchase_receipt.custom_insurance_expenses or 0
				tax_sum += float(tax.get("tax_amount") or 0)

			elif tax.custom_formula == "custom_transport":
				tax.tax_amount = purchase_receipt.custom_transport or 0
				tax_sum += float(tax.get("tax_amount") or 0)

			elif tax.custom_formula == "custom_loading_unloading":
				tax.tax_amount =purchase_receipt.custom_loading_unloading
				tax_sum += float(tax.get("tax_amount") or 0)

			elif tax.custom_formula == "custom_packing_handling":
				tax.tax_amount = purchase_receipt.custom_packing_handling or 0
				tax_sum += float(tax.get("tax_amount") or 0)

			elif tax.custom_formula == "custom_short_excess":
				tax.tax_amount = purchase_receipt.custom_short_excess or 0
				tax_sum += float(tax.get("tax_amount") or 0)

			elif tax.custom_formula == "custom_freight_on_bill":
				tax.tax_amount =  purchase_receipt.custom_freight_on_bill or 0
				tax_sum += float(tax.get("tax_amount") or 0)

			elif tax.custom_formula == "custom_tcs":
				tax.tax_amount = purchase_receipt.custom_tcs or 0
				tax_sum += float(tax.get("tax_amount") or 0)

			elif tax.custom_formula == "custom_commission":
				tax.tax_amount = purchase_receipt.custom_commission or 0
				tax_sum += float(tax.get("tax_amount") or 0)

			purchase_receipt.append("taxes", tax)
		
		purchase_receipt.save(ignore_permissions=True)
		if purchase_receipt.custom_overall_qc_status  is None:
			purchase_receipt.db_set("custom_overall_qc_status","Completed")

		# frappe.db.set_value("Purchase Receipt", purchase_receipt.name, "taxes_and_charges_added", tax_sum)
		# grand_total = purchase_receipt.total + tax_sum
		# frappe.db.set_value("Purchase Receipt",purchase_receipt.name,"grand_total",grand_total)
		# frappe.db.commit()
		
		
		return {"status": "success", "message": "Purchase Receipt Created", "purchase_receipt": purchase_receipt.name}

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Purchase Receipt Creation Error")
		frappe.local.response["Purchase_Receipt"] = "Not Created Purchase Receipt"
		return {"status": "error", "message": str(e)}

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
	
	print("-------------->",len(taxes_and_charges))
	return taxes_and_charges
