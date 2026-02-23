# Copyright (c) 2026, Monil Kamboj
# Bulk Leave Adjustment Tool

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

		self.set("employee", valid_rows)

	# ---------------------------------------------------------

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

				if not row.leaves_count:
					raise Exception("Leaves must be provided")

				if action == "Allocate" and flt(row.leaves_count) <= 0:
					raise Exception("Leaves must be greater than 0 for allocation")

				if action == "Expire" and flt(row.leaves_count) == 0:
					raise Exception("Leaves must be non-zero for expiry")

				posting_date = getdate(self.posting_date) if self.posting_date else getdate(today())

				# -----------------------------
				# 2. FETCH LEAVE ALLOCATION
				# -----------------------------
				allocation_name = frappe.db.get_value(
					"Leave Allocation",
					{
						"employee": row.employee,
						"leave_type": row.leave_type,
						"from_date": row.from_date,
						"to_date": row.to_date,
						"docstatus": 1
					},
					"name"
				)

				if not allocation_name:
					raise Exception("No submitted Leave Allocation found for selected period")

				la = frappe.get_doc("Leave Allocation", allocation_name)

				# =========================================================
				# 3A. ALLOCATE (Correction / Carry Forward Adjustment)
				# =========================================================
				if action == "Allocate":

					# ---- BASIC VALIDATION ----
					if flt(row.leaves_count) <= 0:
						raise Exception("Leaves must be greater than 0 for allocation")

					# ---- OPTIONAL: MAX CF LIMIT CHECK FROM LEAVE TYPE ----
					max_cf = frappe.db.get_value(
						"Leave Type",
						row.leave_type,
						"maximum_carry_forwarded_leaves"
					) or 0

					if max_cf:
						current_balance = flt(get_leave_balance_on(
							row.employee,
							row.leave_type,
							row.to_date
						))

						if current_balance + flt(row.leaves_count) > max_cf:
							allowed = max_cf - current_balance
							raise Exception(
								f"Cannot allocate {row.leaves_count}. Only {allowed} leaves allowed as per maximum carry forward limit"
							)

					# ---- CREATE LLE ENTRY ----
					cf_date = getdate(row.from_date)
					lle = frappe.new_doc("Leave Ledger Entry")
					lle.employee = row.employee
					lle.leave_type = row.leave_type
					lle.company = self.company
					lle.transaction_type = "Leave Allocation"
					lle.transaction_name = la.name
					lle.is_carry_forward = 1
					lle.leaves = flt(row.leaves_count)
					lle.from_date = getdate(row.from_date)
					lle.to_date = getdate(row.to_date)
					lle.insert(ignore_permissions=True)
					lle.submit()
					# ---- COMMENT ----
					lle.add_comment(
						"Info",
						_("{0} leaves manually allocated via Bulk Adjustment on {1} by {2}").format(
							frappe.bold(row.leaves_count),
							frappe.bold(posting_date),
							frappe.bold(frappe.session.user)
						)
					)

					# also comment on allocation document
					la.add_comment(
						"Info",
						_("{0} leaves manually allocated via Bulk Adjustment on {1} by {2}").format(
							frappe.bold(row.leaves_count),
							frappe.bold(posting_date),
							frappe.bold(frappe.session.user)
						)
					)

					message = f"{row.leaves_count} leaves allocated (manual adjustment)"

				# =========================================================
				# 3B. EXPIRE
				# =========================================================
				elif action == "Expire":

					# normalize value (accept +2 or -2 both)
					expire_qty = abs(flt(row.leaves_count))

					if expire_qty == 0:
						raise Exception("Leaves must be greater than 0 for expiry")

					# -----------------------------
					# CURRENT AVAILABLE BALANCE
					# -----------------------------
					available = flt(get_leave_balance_on(
						la.employee,
						la.leave_type,
						la.to_date
					))

					if expire_qty > available:
						raise Exception(
							f"Cannot expire {expire_qty} leaves. Only {available} leaves available"
						)

					# expiry date = first day of allocation period
					expiry_date = getdate(la.from_date)

					# -----------------------------
					# CALCULATE NEW ALLOCATION TOTAL
					# -----------------------------
					# new_total = flt(la.total_leaves_allocated) - expire_qty

					# if new_total < 0:
					# 	raise Exception("Resulting allocation cannot be negative")

					# -----------------------------
					# CHECK IF EXPIRY LLE ALREADY EXISTS
					# -----------------------------
					existing_lle_name = frappe.db.get_value(
						"Leave Ledger Entry",
						{
							"employee": la.employee,
							"leave_type": la.leave_type,
							"transaction_type": "Leave Allocation",
							"transaction_name": la.name,
							"from_date": expiry_date,
							"to_date": expiry_date,
							"is_expired": 1,
							"docstatus": 1
						},
						"name",
						order_by="creation desc"
					)

					if existing_lle_name:
						# -----------------------------
						# UPDATE EXISTING LLE
						# -----------------------------
						existing_lle = frappe.get_doc("Leave Ledger Entry", existing_lle_name)

						new_lle_value = flt(existing_lle.leaves) - expire_qty   # e.g. -5 - 2 = -7

						frappe.db.set_value(
							"Leave Ledger Entry",
							existing_lle.name,
							"leaves",
							new_lle_value
						)

						existing_lle.add_comment(
							"Info",
							_("{0} more leaves expired via Bulk Adjustment on {1} by {2} (updated existing entry)").format(
								frappe.bold(expire_qty),
								frappe.bold(expiry_date),
								frappe.bold(frappe.session.user)
							)
						)

					else:
						# -----------------------------
						# CREATE NEW EXPIRY LLE
						# -----------------------------
						create_additional_leave_ledger_entry(
							la,
							-expire_qty,
							expiry_date
						)

						ledger_name = frappe.db.get_value(
							"Leave Ledger Entry",
							{
								"employee": la.employee,
								"leave_type": la.leave_type,
								"transaction_type": "Leave Allocation",
								"transaction_name": la.name,
								"from_date": expiry_date,
								"leaves": -expire_qty
							},
							"name",
							order_by="creation desc"
						)

						if ledger_name:
							frappe.db.set_value(
								"Leave Ledger Entry",
								ledger_name,
								{
									"is_expired": 1,
									"from_date": expiry_date,
									"to_date": expiry_date
								}
							)

							lle_doc = frappe.get_doc("Leave Ledger Entry", ledger_name)
							lle_doc.add_comment(
								"Info",
								_("{0} leaves expired via Bulk Adjustment on {1} by {2}").format(
									frappe.bold(expire_qty),
									frappe.bold(expiry_date),
									frappe.bold(frappe.session.user)
								)
							)

					# -----------------------------
					# UPDATE ALLOCATION TOTAL
					# -----------------------------
					# la.db_set("total_leaves_allocated", new_total, update_modified=False)

					# -----------------------------
					# COMMENT ON ALLOCATION
					# -----------------------------
					la.add_comment(
						"Info",
						_("{0} leaves expired via Bulk Adjustment on {1} by {2}").format(
							frappe.bold(expire_qty),
							frappe.bold(expiry_date),
							frappe.bold(frappe.session.user)
						)
					)

					message = f"{expire_qty} leaves expired"

				else:
					raise Exception("Invalid action selected")

				# -----------------------------
				# 4. SUCCESS MARK
				# -----------------------------
				row.status = "Success"
				row.message = message
				row.leave_allocation = la.name

				success += 1

			except Exception as e:
				row.status = "Failed"
				row.message = str(e)
				failed += 1

		# -----------------------------
		# 5. FINAL STATUS
		# -----------------------------
		if success and not failed:
			self.status = "Completed"
		elif success and failed:
			self.status = "Partially Completed"
		else:
			self.status = "Failed"

		# -----------------------------
		# 6. USER MESSAGE
		# -----------------------------
		frappe.msgprint(
			_("Processing Complete: {0} Success, {1} Failed").format(success, failed),
			indicator="green" if success else "red"
		)