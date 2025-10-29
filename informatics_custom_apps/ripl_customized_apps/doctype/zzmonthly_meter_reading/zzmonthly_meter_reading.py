# Copyright (c) 2025, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils.background_jobs import enqueue
from frappe.utils.data import flt, getdate
import calendar
from datetime import date, datetime, timedelta

class zzMonthlyMeterReading(Document):

	# Get Month last date From Month
	@frappe.whitelist()
	def get_last_date(self):
		current_year = datetime.now().year
		month_name = self.month
		month_number = list(calendar.month_name).index(month_name.capitalize())
		_, last_day = calendar.monthrange(current_year, month_number)
		last_date = getdate(f"{last_day}-{month_number}-{current_year}")
		return last_date

	@frappe.whitelist()
	def before_save(self):
		month_names = [
			"January", "February", "March", "April",
			"May", "June", "July", "August",
			"September", "October", "November", "December"
		]
		current_month_number = month_names.index(self.month.capitalize()) + 1

		for j in self.meter_reading:
			# ---- Basic Calculations ----
			# always compute consumed_units from readings (keeps consistent)
			j.consumed_units = flt(j.closing_reading) - flt(j.opening_reading)
			if j.consumed_units > j.allowed_units:
				j.chargeable_units = j.consumed_units - j.allowed_units
			else:
				j.chargeable_units = 0

			# ---- Fetch Employee and Designation ----
			emp = frappe.db.get_value("Employee", {"quarter": j.quarter_no}, ["name", "designation", "branch"])
			if not emp:
				# no employee for this quarter — skip row (you may also throw if required)
				continue

			emp_name, designation, branch_name = emp
			j.designation = designation
			j.branch = branch_name

			# ---- Determine Allowed Units (preserve existing if present, else compute) ----
			allowed_units = flt(j.allowed_units) or 0
			if branch_name:
				branch = frappe.get_doc("Branch", branch_name)

				for ex in branch.electricity_exemption_details:
					from_month_number = month_names.index(ex.from_month) + 1
					to_month_number = month_names.index(ex.to_month) + 1

					# Skip if designation doesn't match
					if designation != ex.designation:
						continue

					# Case 1: Normal range (e.g., April to October)
					if from_month_number <= to_month_number:
						if from_month_number <= current_month_number <= to_month_number:
							allowed_units = ex.exemption_units
							break

					# Case 2: Wrap-around range (e.g., November to March)
					else:
						if (current_month_number >= from_month_number) or (current_month_number <= to_month_number):
							allowed_units = ex.exemption_units
							break

			j.allowed_units = allowed_units

			# ---- Determine Unit Rate and Amount ----
			qa = frappe.get_doc("zzQuarter Master", j.quarter_no)
			if qa.plant:
				plant_branch = frappe.get_doc("Branch", qa.plant)
				j.unit_rate = plant_branch.electricity_unit_rate
				j.amount = flt(j.chargeable_units) * flt(j.unit_rate)

			# ---- Validation ----
			if qa.expense_type == "Employee" and not j.employee:
				frappe.throw(f"Row {j.idx}: Employee is mandatory.")

	# Fetch Quarter Data
	@frappe.whitelist()
	def get_data(self):
		# Only fetch data when doc is draft (docstatus == 0)
		if self.docstatus == 0:
			self.meter_reading = []

			quarter_list = frappe.db.get_all(
				"zzQuarter Master",
				{"docstatus": 0},
				["name", "expense_type", "salary_component", "cost_center", "plant"]
			)

			month_names = [
				"January", "February", "March", "April",
				"May", "June", "July", "August",
				"September", "October", "November", "December"
			]

			current_month_number = month_names.index(self.month.capitalize()) + 1
			# prefer self.year if provided; fallback to now().year
			current_year = getattr(self, "year", None) or datetime.now().year

			# first day of the current month (used to pick last log before this date)
			first_day_of_current_month = date(current_year, current_month_number, 1)

			for q in quarter_list:
				# Get active employee linked to this quarter
				emp = frappe.db.get_value("Employee", {"quarter": q.get("name"), "status": "Active"}, ["name"])

				if not emp:
					# No active employee in this quarter → skip
					continue

				doc = frappe.get_doc("Employee", emp)

				# Fetch latest Meter Reading Log before current month
				log = frappe.db.get_value(
					"zzMeter Reading Log",
					{
						"employee": emp,
						"quarter": q.get("name"),
						"is_cancelled": 0,
						"posting_date": ("<", first_day_of_current_month)
					},
					["employee", "opening", "consumed_units", "quarter", "posting_date"],
					order_by="posting_date desc"
				)

				opening_reading = flt(log[1]) + flt(log[2]) if log else 0
				allowed_units = 0
				unit_rate = 0

				# ---- Branch & Exemption Logic ----
				if doc.branch:
					branch = frappe.get_doc("Branch", doc.branch)
					unit_rate = branch.electricity_unit_rate

					for ex in branch.electricity_exemption_details:
						from_month_number = month_names.index(ex.from_month) + 1
						to_month_number = month_names.index(ex.to_month) + 1

						# Skip if designation does not match
						if doc.designation != ex.designation:
							continue

						# Case 1: Normal month range (e.g., April to October)
						if from_month_number <= to_month_number:
							if from_month_number <= current_month_number <= to_month_number:
								allowed_units = ex.exemption_units
								break

						# Case 2: Wrap-around range (e.g., November to March)
						else:
							if (current_month_number >= from_month_number) or (current_month_number <= to_month_number):
								allowed_units = ex.exemption_units
								break

				# ---- Append Data to Child Table ----
				self.append("meter_reading", {
					"quarter_no": q.get("name"),
					"opening_reading": opening_reading,
					"employee": emp,
					"employee_name": doc.employee_name,
					"plant": doc.branch,
					"designation": doc.designation,
					"unit_rate": unit_rate,
					"expense_type": q.expense_type,
					"salary_component": q.salary_component,
					"cost_center": q.cost_center,
					"allowed_units": allowed_units
				})

			return True

	# Create Meter Log
	def before_submit(self):
		for k in self.meter_reading:
			# ---- Validation ----
			if flt(k.consumed_units) == 0:
				frappe.throw(f"Row {k.idx}: Consumed Units cannot be zero.")

			# ---- Only create log if reading increased ----
			if flt(k.closing_reading) > flt(k.opening_reading):
				# Check if a log already exists for this reference
				existing_log = frappe.db.exists(
					"zzMeter Reading Log",
					{
						"employee": k.employee,
						"quarter": k.quarter_no,
						"reference_no": self.name,
						"is_cancelled": 0
					}
				)
				if existing_log:
					continue  # prevent duplicate log creation

				# ---- Create new Meter Reading Log ----
				doc = frappe.new_doc("zzMeter Reading Log")
				doc.employee = k.employee
				doc.quarter = k.quarter_no
				doc.opening = k.opening_reading
				doc.consumed_units = k.consumed_units
				doc.closing = k.closing_reading
				doc.posting_date = self.date
				doc.reference_no = self.name
				doc.insert(ignore_permissions=True, ignore_mandatory=True)

	# On cancel cancel logs and linked docs
	def on_cancel(self):
		# Cancel related Meter Reading Log(s)
		logs = frappe.db.get_all("zzMeter Reading Log", {"reference_no": self.name}, ["name"])
		if logs:
			for l in logs:
				log_doc = frappe.get_doc("zzMeter Reading Log", l.get("name"))
				log_doc.is_cancelled = 1
				log_doc.save(ignore_permissions=True)

		# Cancel related Journal Entry if exists (by cheque_no)
		jv_name = frappe.db.get_value("Journal Entry", {"cheque_no": self.name}, "name")
		if jv_name:
			jv = frappe.get_doc("Journal Entry", jv_name)
			try:
				jv.cancel()
			except Exception:
				# handle or log cancellation errors as needed
				pass

		# Cancel related Additional Salary if exists (by ref_docname)
		ad_name = frappe.db.get_value("Additional Salary", {"ref_docname": self.name}, "name")
		if ad_name:
			ad = frappe.get_doc("Additional Salary", ad_name)
			try:
				ad.cancel()
			except Exception:
				# handle or log cancellation errors as needed
				pass

	def on_submit(self):
		for j in self.meter_reading:
			# Employee expense -> Additional Salary
			if j.expense_type == "Employee":
				if flt(j.amount) > 0:
					emp = frappe.get_doc("Employee", j.employee)
					doc = frappe.new_doc("Additional Salary")
					doc.employee = j.employee
					doc.payroll_date = self.date
					# Use employee's company (emp.company) rather than emp.name
					doc.company = getattr(emp, "company", None) or self.company
					doc.amount = j.amount
					doc.salary_component = j.salary_component
					doc.ref_doctype = self.doctype
					doc.ref_docname = self.name
					doc.insert(ignore_permissions=True)
					doc.submit()

			# Distributed expense -> Journal Entry
			if j.expense_type == "Distributed":
				doc = frappe.new_doc("Journal Entry")
				doc.entry_type = "Journal Entry"
				doc.posting_date = self.date
				if j.quarter_no:
					qn = frappe.get_doc("zzQuarter Master", j.quarter_no)
					if qn.plant:
						plant = frappe.get_doc("Branch", qn.plant)
						doc.company = plant.company
						doc.cheque_no = self.name
						doc.cheque_date = self.date
						for k in plant.account_mapping:
							if k.document_name == self.doctype:
								doc.append("accounts", {
									"account": k.debit_account,
									"debit_in_account_currency": j.amount,
									"plant": plant.name,
									"cost_center": j.cost_center
								})
								doc.append("accounts", {
									"account": k.credit_account,
									"credit_in_account_currency": j.amount,
									"plant": plant.name,
									"cost_center": j.cost_center
								})
						doc.insert(ignore_permissions=True)
						doc.submit()