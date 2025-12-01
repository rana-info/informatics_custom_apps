# Copyright (c) 2025, Monil Kamboj and contributors
# For license information, please see license.txt

from datetime import datetime, timedelta
import frappe
from frappe.model.document import Document
from frappe.utils.data import getdate, today
from hrms.hr.utils import get_holiday_dates_for_employee

class zzDeputationRequest(Document):
	
	def on_submit(self):
		frappe.enqueue(
			create_attendance_request,
			self=self,
			queue='long', timeout=1500)
		

	def validate(self):
		
		if getdate(self.to_date) < getdate(self.from_date):
			frappe.throw("To Date can't be less than From Date")

		dr = frappe.db.get_value("zzDeputation Request",
			{"from_date": ["between", [self.from_date, self.to_date]],
			 "employee": self.employee, "docstatus": ["!=", 2]},
			["name"])

		dr1 = frappe.db.get_value("zzDeputation Request",
			{"to_date": ["between", [self.from_date, self.to_date]],
			 "employee": self.employee, "docstatus": ["!=", 2]},
			["name"])

		if dr and dr != self.name:
			frappe.throw("Deputation Request Already Created between date '{0}' and '{1}'".format(self.from_date, self.to_date))
		elif dr1 and dr1 != self.name:
			frappe.throw("Deputation Request Already Created between date '{0}' and '{1}'".format(self.from_date, self.to_date))

		start_date = getdate(self.from_date)
		end_date = getdate(self.to_date)
		days_difference = (end_date - start_date).days

		if self.plant:
			plant = frappe.get_doc("Branch", self.plant)
			if plant.deputation_minimum_applicable_days > days_difference:
				frappe.throw("Minimum Applicable days Of Deputation Is {0} days.you cannot apply for {1} days".format(
					plant.deputation_minimum_applicable_days, days_difference))

		if self.plant == self.to_plant:
			frappe.throw("To Plant & From Plant can't be same")

		if self.employee:
			employee = frappe.get_cached_doc("Employee", self.employee)
			if employee.status == "Left":
				frappe.throw(f"This {employee.name} has Left. It should not create a deputation request.")

	
	def before_cancel(self):
		if frappe.db.exists("Attendance Request",
			{"custom_zzdeputation_request": self.name, "docstatus": 1}):
			frappe.throw("Attendance Request created from this Deputation Request is already submitted. Cannot cancel Deputation Request untill all attendance requests are cancelled!.")
		else:
			frappe.db.delete(
				"Attendance Request",
				{
					"custom_zzdeputation_request": self.name,
					"docstatus":["!=",1]
				}
			)


def create_attendance_request(self):
	try:
		dates = []
		current_date = getdate(self.from_date)
		ho = get_holiday_dates_for_employee(self.employee, self.from_date, self.to_date)

		while current_date <= getdate(today()) and current_date <= getdate(self.to_date):
			if current_date not in ho:
				dates.append(current_date.strftime('%Y-%m-%d'))
			current_date += timedelta(days=1)

		for kj in dates:
			attendance = frappe.db.exists("Attendance",
				{"employee": self.employee, "attendance_date": kj, "docstatus": ("!=", 2), "status": "Present"})

			on_leave = frappe.get_all("Leave Application",
				filters={"employee": self.employee, "from_date": ["<=", kj], "to_date": [">=", kj], "docstatus": ("!=", 2)})

			dc = frappe.db.get_value("Attendance Request",
				{"from_date": ["<=", kj], "to_date": [">=", kj], "employee": self.employee, "docstatus": ["!=", 2]}, ["name"])

			if not attendance and not dc and not on_leave and kj not in ho:
				doc = frappe.new_doc("Attendance Request")
				doc.employee = self.employee
				doc.company = self.company
				doc.from_date = getdate(kj)
				doc.to_date = getdate(kj)
				doc.reason = "On Duty"
				doc.custom_zzdeputation_request = self.name
				doc.save(ignore_permissions=True)

	except Exception as e:
		frappe.log_error("Error while creating Attendance Request from Deputation Request: " + str(self.name))

@frappe.whitelist()
def attendance_request_created():
	try:
		today_date = getdate(today())

		# Fetch all active deputations
		dr_list = frappe.db.sql("""
			SELECT name, employee, company, from_date, to_date, actual_end_date
			FROM `tabzzDeputation Request`
			WHERE docstatus = 1
			AND from_date <= %(today)s
		""", {"today": today()}, as_dict=1)

		for dr in dr_list:
			emp = dr["employee"]
			dr_name = dr["name"]
			company = dr["company"]

			# Employee must be active
			employee = frappe.get_cached_doc("Employee", emp)
			if not (employee.status == "Active" and
				(not employee.relieving_date or getdate(employee.relieving_date) >= today_date)):
				continue

			# Define date range using earliest and latest applicable dates
			start_date = getdate(dr["from_date"])
			end_date = getdate(dr["actual_end_date"] or dr["to_date"])
			end_date = min(end_date, today_date)

			if end_date < start_date:
				continue

			# Generate full date list
			total_days = (end_date - start_date).days + 1
			all_dates = [start_date + timedelta(days=i) for i in range(total_days)]

			# -------------------------------
			# 1. Holidays — single fetch
			# -------------------------------
			holidays = set(get_holiday_dates_for_employee(emp, start_date, end_date))
			holidays = {getdate(h) for h in holidays}

			# -------------------------------
			# 2. Attendance — bulk fetch
			# -------------------------------
			attendance_rows = frappe.db.sql("""
				SELECT attendance_date
				FROM `tabAttendance`
				WHERE employee = %(emp)s
				AND attendance_date BETWEEN %(start)s AND %(end)s
				AND status = 'Present'
				AND docstatus != 2
			""", {"emp": emp, "start": start_date, "end": end_date})

			attendance_dates = {row[0] for row in attendance_rows}

			# -------------------------------
			# 3. Attendance Request — bulk fetch
			# -------------------------------
			ar_rows = frappe.db.sql("""
				SELECT from_date, to_date
				FROM `tabAttendance Request`
				WHERE employee = %(emp)s
				AND to_date >= %(start)s
				AND from_date <= %(end)s
				AND docstatus != 2
			""", {"emp": emp, "start": start_date, "end": end_date})

			ar_dates = set()
			for fr, to in ar_rows:
				cur = fr
				while cur <= to:
					ar_dates.add(cur)
					cur += timedelta(days=1)

			# -------------------------------
			# 4. Leaves — bulk fetch
			# -------------------------------
			leave_rows = frappe.db.sql("""
				SELECT from_date, to_date
				FROM `tabLeave Application`
				WHERE employee = %(emp)s
				AND to_date >= %(start)s
				AND from_date <= %(end)s
				AND docstatus != 2
			""", {"emp": emp, "start": start_date, "end": end_date})

			leave_dates = set()
			for fr, to in leave_rows:
				cur = fr
				while cur <= to:
					leave_dates.add(cur)
					cur += timedelta(days=1)

			# -------------------------------
			# 5. Decide which dates need attendance requests
			# -------------------------------
			for dt in all_dates:

				# Skip if holiday, attendance exists, leave exists or AR exists
				if (dt in holidays or
					dt in attendance_dates or
					dt in ar_dates or
					dt in leave_dates):
					continue
				else:
					# Create the attendance request
					doc = frappe.new_doc("Attendance Request")
					doc.employee = emp
					doc.company = company
					doc.from_date = dt
					doc.to_date = dt
					doc.reason = "On Duty"
					doc.custom_zzdeputation_request = dr_name
					doc.save(ignore_permissions=True)

	except Exception as e:
		frappe.log_error(f"Error in optimized attendance_request_created: {str(e)}")


# @frappe.whitelist()
# def attendance_request_created():
# 	try:
# 		# Fetch all active deputation requests for today
# 		dr_list = frappe.db.sql("""
# 			SELECT name, employee, company, actual_end_date
# 			FROM `tabzzDeputation Request`
# 			WHERE docstatus = 1 
# 			AND from_date <= %(today)s 
# 			AND to_date >= %(today)s
# 		""", {"today": today()}, as_dict=1)

# 		for dr in dr_list:
# 			emp = dr.get("employee")
# 			company = dr.get("company")
# 			dr_name = dr.get("name")

# 			# -------------------------
# 			# 1. Check actual_end_date logic
# 			# -------------------------
# 			if dr.get("actual_end_date") and getdate(dr.get("actual_end_date")) < getdate(today()):
# 				# Deputation ended early → skip
# 				continue

# 			# -------------------------
# 			# 2. Check employee status
# 			# -------------------------
# 			employee = frappe.get_cached_doc("Employee", emp)
# 			if not (employee.status == "Active" and 
# 				(not employee.relieving_date or getdate(employee.relieving_date) >= getdate(today()))):
# 				continue

# 			# -------------------------
# 			# 3. Check holiday for today
# 			# -------------------------
# 			ho = get_holiday_dates_for_employee(emp, today(), today())
# 			if getdate(today()) in ho:
# 				continue  # No attendance request on holiday

# 			# -------------------------
# 			# 4. Check existing attendance OR existing attendance request
# 			# -------------------------
# 			existing_ar = frappe.db.get_value(
# 				"Attendance Request",
# 				{
# 					"from_date": ["<=", today()],
# 					"to_date": [">=", today()],
# 					"employee": emp,
# 					"docstatus": ["!=", 2],
# 				},
# 				["name"]
# 			)

# 			existing_attendance = frappe.db.exists(
# 				"Attendance",
# 				{
# 					"employee": emp,
# 					"attendance_date": getdate(today()),
# 					"docstatus": ("!=", 2),
# 					"status":"Present"
# 				}
# 			)

# 			if existing_ar or existing_attendance:
# 				continue  # Already marked skipped

# 			# -------------------------
# 			# 5. Create attendance request
# 			# -------------------------
# 			doc = frappe.new_doc("Attendance Request")
# 			doc.employee = emp
# 			doc.company = company
# 			doc.from_date = getdate(today())
# 			doc.to_date = getdate(today())
# 			doc.reason = "On Duty"
# 			doc.custom_zzdeputation_request = dr_name
# 			doc.save(ignore_permissions=True)

# 	except Exception as e:
# 		frappe.log_error(f"Error in attendance_request_created: {str(e)}")

# @frappe.whitelist()
# def attendance_request_created():
# 	try:
# 		dr = frappe.db.sql("""
# 			SELECT name,employee FROM `tabzzDeputation Request`
# 			WHERE docstatus = 1 AND from_date <= %(today)s AND to_date >= %(today)s
# 		""", {"today": today()}, as_dict=1)

# 		for k in dr:
# 			employee = frappe.get_cached_doc("Employee", k.get("employee"))

# 			if k.actual_end_date and k.actual_end_date < getdate(today()):
# 				continue

# 			if employee.status == "Active" and (not employee.relieving_date or getdate(employee.relieving_date) >= getdate(today())):

# 				ho = get_holiday_dates_for_employee(k.get("employee"), today(), today())

# 				if getdate(today()) not in ho:
# 					dc = frappe.db.get_value("Attendance Request",
# 						{"from_date": ["<=", today()], "to_date": [">=", today()],
# 						 "employee": k.get("employee"), "docstatus": ["!=", 2]}, ["name"])

# 					attendence = frappe.db.exists("Attendance",
# 						{"employee": k.get("employee"), "attendance_date": getdate(today()), "docstatus": ("!=", 2)})

# 					if not dc and not attendence:
# 						doc = frappe.new_doc("Attendance Request")
# 						doc.employee = k.get("employee")
# 						doc.company = k.get("company")
# 						doc.from_date = getdate(today())
# 						doc.to_date = getdate(today())
# 						doc.reason = "On Duty"
# 						doc.custom_zzdeputation_request = k.get("name")
# 						doc.save(ignore_permissions=True)

# 	except frappe.ValidationError as e:
# 		frappe.logger().info(f"Skipped creating attendance request for {k.get('employee')} due to validation error: {str(e)}")
