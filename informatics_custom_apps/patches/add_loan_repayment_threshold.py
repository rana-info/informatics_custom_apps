import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fieldname = "HR Settings-loan_repayment_threshold_percent"
	if not frappe.db.exists("Custom Field", fieldname):
		create_custom_fields(
			{
				"HR Settings": [
					{
						"fieldname": "loan_repayment_threshold_percent",
						"fieldtype": "Percent",
						"label": "Loan Repayment Net Salary Threshold (%)",
						"default": 10,
						"insert_after": "employee_settings",
					}
				]
			}
		)
	set_default_threshold()


def set_default_threshold():
	value = frappe.db.get_single_value("HR Settings", "loan_repayment_threshold_percent")
	if value in (None, 0, "0"):
		frappe.db.set_single_value("HR Settings", "loan_repayment_threshold_percent", 10)