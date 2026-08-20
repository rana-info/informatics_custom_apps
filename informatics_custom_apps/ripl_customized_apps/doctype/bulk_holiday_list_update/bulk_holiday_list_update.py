# Copyright (c) 2026, Yash and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class BulkHolidayListUpdate(Document):

	@frappe.whitelist()
	def get_employee_data(self):
		if not self.old_holiday_list:
			return []

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
			],
			order_by="name"
		)

	@frappe.whitelist()
	def update_holiday_list(self):
		if not self.old_holiday_list:
			frappe.throw(_("Please select Old Holiday List"))

		if not self.new_holiday_list:
			frappe.throw(_("Please select New Holiday List"))

		if self.old_holiday_list == self.new_holiday_list:
			frappe.throw(
				_("Old Holiday List and New Holiday List cannot be same")
			)

		if not self.selected_employees:
			frappe.throw(
				_("Please select at least one employee")
			)

		selected_employees = frappe.parse_json(
			self.selected_employees
		)

		if not selected_employees:
			frappe.throw(
				_("Please select at least one employee")
			)

		for employee in selected_employees:
			frappe.db.set_value(
				"Employee",
				employee,
				"holiday_list",
				self.new_holiday_list,
			)

		frappe.db.commit()

		# frappe.msgprint(
		# 	_("Holiday List updated successfully for {0} employee(s)")
		# 	.format(len(selected_employees))
		# )

		return {
			"updated_count": len(selected_employees)
		}