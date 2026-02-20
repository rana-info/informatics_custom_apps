# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, flt, today
from frappe import _
from hrms.hr.doctype.leave_allocation.leave_allocation import create_additional_leave_ledger_entry
from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on

class BulkLeaveAdjustment(Document):

	def validate(self):
		valid_rows = []

		for row in self.employee:

			if not row.employee:
				continue

			emp_company, emp_plant = frappe.db.get_value(
				"Employee",
				row.employee,
				["company", "branch"]   
			)

			if emp_company == self.company and emp_plant == self.plant:
				valid_rows.append(row)
			else:
				frappe.msgprint(
					_("Row {0}: Employee {1} removed as it does not belong to selected Company/Plant").format(
						row.idx, row.employee
					),
					indicator="orange"
				)

		# replace child table with only valid rows
		self.set("employee", valid_rows)


	@frappe.whitelist()
	def before_submit(self):

		success = 0
		failed = 0

		for row in self.employee:

			try:
				action = row.action
				# -----------------------------
				# 1. BASIC VALIDATIONS
				# -----------------------------
				if not row.employee or not row.leave_type:
					raise Exception("Employee and Leave Type are mandatory")

				# if not row.leaves_count or flt(row.leaves_count) <= 0:
				# 	raise Exception("Leaves must be greater than 0")
				if not row.leaves_count:
					raise Exception("Leaves must be provided")

				if action == "Allocate" and flt(row.leaves_count) <= 0:
					raise Exception("Leaves must be greater than 0 for allocation")

				if action == "Expire" and flt(row.leaves_count) == 0:
					raise Exception("Leaves must be non-zero for expiry")


				posting_date = self.posting_date or today()

				# -----------------------------
				# 2. FETCH LEAVE ALLOCATION
				# -----------------------------
				allocation_name = frappe.db.get_value(
					"Leave Allocation",
					{
						"employee": row.employee,
						"leave_type": row.leave_type,
						"from_date": ["=", row.from_date],
						"to_date": ["=", row.to_date],
						"docstatus": 1
					},
					"name"
				)
				# print("------------------>allocation_name:",allocation_name)
				if not allocation_name:
					raise Exception("No submitted Leave Allocation found for selected period")

				la = frappe.get_doc("Leave Allocation", allocation_name)

				# -----------------------------
				# 3. PERFORM ACTION
				# -----------------------------
				if action == "Allocate":

					la.allocate_leaves_manually(
						new_leaves=flt(row.leaves_count),
						from_date=row.from_date
					)

					message = f"{row.leaves_count} leaves allocated"

				elif action == "Expire":

					# ----- VALIDATIONS -----
					available = flt(get_leave_balance_on(
									la.employee,
									la.leave_type,
									la.to_date
								))



					if flt(row.leaves_count) > available:
						raise Exception(
							f"Cannot expire {row.leaves_count} leaves. Only {available} leaves available"
						)

					# expiry date = last day before allocation start
					expiry_date = getdate(la.from_date)

					# ----- CALCULATE RESULT FIRST -----
					new_total = flt(la.total_leaves_allocated) - abs(flt(row.leaves_count))

					if new_total < 0:
						raise Exception("Resulting allocation cannot be negative")

					# ----- UPDATE ALLOCATION -----
					la.db_set("total_leaves_allocated", new_total, update_modified=False)

					# ----- CREATE LLE -----
					create_additional_leave_ledger_entry(
						la,
						-abs(flt(row.leaves_count)),
						expiry_date
					)

					# ----- FETCH CREATED LLE (SAFE USING transaction_name) -----
					ledger_name = frappe.db.get_value(
						"Leave Ledger Entry",
						{
							"employee": la.employee,
							"leave_type": la.leave_type,
							"transaction_type": "Leave Allocation",
							"transaction_name": la.name,
							"from_date": expiry_date,
							"leaves": -abs(flt(row.leaves_count))
						},
						"name",
						order_by="creation desc"
					)

					if ledger_name:
						frappe.db.set_value("Leave Ledger Entry", ledger_name, {
							"is_expired": 1,
							"from_date": expiry_date,
							"to_date": expiry_date
						})

						lle_doc = frappe.get_doc("Leave Ledger Entry", ledger_name)
						lle_doc.add_comment(
							"Info",
							_("{0} leaves expired via Bulk Adjustment on {1} by {2}").format(
								frappe.bold(row.leaves_count),
								frappe.bold(expiry_date),
								frappe.bold(frappe.session.user)
							)
						)

					# ----- COMMENT ON ALLOCATION -----
					la.add_comment(
						"Info",
						_("{0} leaves expired via Bulk Adjustment on {1} by {2}").format(
							frappe.bold(row.leaves_count),
							frappe.bold(expiry_date),
							frappe.bold(frappe.session.user)
						)
					)

					message = f"{row.leaves_count} leaves expired"


				else:
					raise Exception("Invalid action selected")

				# -----------------------------
				# 4. MARK SUCCESS
				# -----------------------------
				row.status = "Success"
				row.message = message
				row.leave_allocation = la.name

				success += 1

			except Exception as e:
				# -----------------------------
				# 5. MARK FAILURE
				# -----------------------------
				row.status = "Failed"
				row.message = str(e)
				failed += 1

		# -----------------------------
		# 6. UPDATE PARENT STATUS
		# -----------------------------
		if success and not failed:
			self.status = "Completed"
		elif success and failed:
			self.status = "Partially Completed"
		else:
			self.status = "Failed"

		# -----------------------------
		# 7. FINAL USER MESSAGE
		# -----------------------------
		frappe.msgprint(
			_("Processing Complete: {0} Success, {1} Failed").format(success, failed),
			indicator="green" if success else "red"
		)

