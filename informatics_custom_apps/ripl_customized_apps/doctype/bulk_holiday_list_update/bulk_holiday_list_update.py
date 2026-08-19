# Copyright (c) 2026, Yash and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BulkHolidayListUpdate(Document):
    
	def before_save(self):
		self.update_holiday_list()

	@frappe.whitelist()
	def get_employee_data(self):
		return frappe.get_all(
			"Employee",
			filters={
				"holiday_list": self.old_holiday_list,
				"status": "Active"
			},
			fields=[
				"name as employee",
				"employee_name",
				"holiday_list"
			]
		)
	
	def update_holiday_list(self):
		if not self.selected_employees:
			frappe.throw("Please select at least one employee to update the holiday list.")
		selected = frappe.parse_json(self.selected_employees)
		if not selected:
			frappe.throw("Please select at least one employee to update the holiday list.")

		for e in selected:
			emp_doc = frappe.get_doc("Employee", e)
			emp_doc.db_set("holiday_list", self.new_holiday_list)