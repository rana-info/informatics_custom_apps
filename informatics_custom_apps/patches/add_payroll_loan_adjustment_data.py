import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fieldname = "Payroll Entry-loan_repayment_adjustment_data"
	if not frappe.db.exists("Custom Field", fieldname):
		create_custom_fields(
			{
				"Payroll Entry": [
					{
						"fieldname": "loan_repayment_adjustment_data",
						"fieldtype": "Long Text",
						"label": "Pending Loan Repayment Adjustments",
						"hidden": 1,
						"insert_after": "employees",
					}
				]
			}
		)
