# Copyright (c) 2026, Yash and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import bold, safe_eval, _
from frappe.model.document import Document
from frappe.utils.data import cint, flt, format_datetime, get_link_to_form
from datetime import date
from frappe.utils import (
	ceil,
	floor,
	getdate,
	nowdate,
	formatdate,
)
from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on, get_leave_details

class zzBulkLeaveEncashment(Document):
	def validate(self):
		today = nowdate()

		if self.payroll_date and getdate(self.payroll_date) > getdate(today):
			frappe.throw(_("Payroll Date ({0}) cannot be greater than Today's Date ({1}).").format(
				formatdate(self.payroll_date), formatdate(today)
			))

		if self.bulk_leave_encashment_details:
			for d in self.bulk_leave_encashment_details:
				if d.employee:
					relieving_date = frappe.db.get_value("Employee", d.employee, "relieving_date")
					if relieving_date:
						frappe.throw(_("Row {0}: Relieving date ({1}) is set for Employee {2} ({3}). Please remove the relieving date first.").format(
							d.idx, formatdate(relieving_date), d.employee, d.employee_name or d.employee
						))

				if d.employee and d.leave_type:
					try:
						bal = get_leave_balance_on(
							employee=d.employee,
							leave_type=d.leave_type,
							date=today,
							to_date=today,
							consider_all_leaves_in_the_allocation_period=True,
							for_consumption=False
						)
						d.available_balance = flt(bal or 0)
					except Exception:
						pass

					max_allowed = flt(d.available_balance) - flt(d.leave_application or 0)
					if flt(d.encashable_days) > max_allowed:
						frappe.throw(_("Row {0}: Encashable Days ({1}) cannot be greater than Available Balance minus Leave Application ({2}) for Employee {3}.").format(
							d.idx, d.encashable_days, max_allowed, d.employee
						))

					if flt(d.encashable_days) <= 0:
						frappe.throw(_("Row {0}: Encashable Days must be greater than 0 for Employee {1}.").format(
							d.idx, d.employee
						))

				if not d.salary_structure_assignment:
					frappe.throw(_("Row {0}: Active Salary Structure Assignment not found for Employee {1}.").format(
						d.idx, d.employee
					))

				if not d.formula:
					frappe.throw(_("Row {0}: Formula not defined for Earning Component in Leave Type {1}.").format(
						d.idx, d.leave_type
					))

				is_record_exist = frappe.db.sql("""select bd.name,bd.parent from `tabBulk Leave Encashment Details` bd
									inner join `tabBulk Leave Encashment` b on bd.parent = b.name
									where b.docstatus = 1 and bd.parent != %s and bd.season = %s and bd.branch = %s and bd.work_location = %s
									and bd.from_date = %s and bd.to_date = %s and bd.payroll_date = %s and bd.employee = %s and bd.leave_type = %s """,
									(self.name or "",self.season,self.branch,self.work_location,self.from_date,self.to_date,self.payroll_date,d.employee,d.leave_type),as_dict=1)
				if is_record_exist:
					rec = frappe.get_cached_doc("Bulk Leave Encashment Details",{"parent":is_record_exist[0]["parent"]})
					frappe.throw(_("Row {0}: Existing record {1} already found for Employee {2}.").format(
						d.idx, get_link_to_form('zzBulk Leave Encashment', rec.parent), d.employee
					))
	
	@frappe.whitelist()
	def get_all_employees(self,company,branch,work_location):
		employees = frappe.get_all(
			"Employee", 
			filters = {"company":company,"branch":branch,"worklocation":work_location},
			fields=["name", "employee_name", "status"]
		)
		return employees 

	@frappe.whitelist()
	def get_emp_data(self, employee=None):
		conditions = []
		emp = []
		if employee:
			if isinstance(employee, str):
				try:
					employee = json.loads(employee)
				except Exception:
					employee = [e.strip() for e in employee.split(",") if e.strip()]
			employee_list = ", ".join([f"'{p}'" for p in employee])
			conditions.append(f"l.employee IN ({employee_list})")
			emp.append(f"bd.employee IN ({employee_list})")

		emp_data = " AND ".join(emp) if emp else "1=1"
		conditions_str = " AND ".join(conditions) if conditions else "1=1"

		if not self.payroll_date:
			frappe.throw("Please Set Posting Date First")
		if not self.season:
			frappe.throw("Please Select Season First")
		if not self.work_location:
			frappe.throw("Please Select Work Location First")
		if not self.based_on:
			frappe.throw("Please select Based On first")

		existing_data_dict = frappe._dict()
		employee_data = frappe.db.sql("""select employee,leave_type from `tabBulk Leave Encashment Details` bd
						join `tabBulk Leave Encashment` b on bd.parent = b.name
						where b.docstatus = 1 and bd.parent != %s and bd.season = %s and bd.branch = %s and bd.work_location = %s
						and bd.from_date = %s and bd.to_date = %s and bd.payroll_date = %s AND {0}""".format(emp_data),
					(self.name or "",self.season,self.branch,self.work_location,self.from_date,self.to_date,self.payroll_date),as_dict=1)
		if employee_data:
			for j in employee_data:
				existing_data_dict[j.employee] = j.leave_type

		data = frappe.db.sql("""
            SELECT l.employee, l.transaction_type, l.leave_type,
				SUM(CASE WHEN l.transaction_type = 'Leave Allocation' THEN l.leaves ELSE 0 END) AS allocation_sum,
                SUM(CASE WHEN l.transaction_type = 'Leave Application' THEN l.leaves ELSE 0 END) AS application_sum,
				e.branch, e.employee_name, e.payroll_cost_center, e.designation, e.department, e.employee
            FROM `tabLeave Ledger Entry` l
            LEFT JOIN `tabEmployee` e ON l.employee = e.name
			LEFT JOIN `tabLeave Type` lt ON l.leave_type = lt.name
			WHERE l.from_date >= %s
				AND l.from_date <= %s
                AND l.company = %s AND e.branch = %s
				AND e.worklocation = %s
                AND (l.transaction_type = 'Leave Allocation' OR l.transaction_type = 'Leave Application')
				AND lt.custom_allow_seasonal_encashment = 1
				AND l.is_expired != 1
				AND e.status = 'Active'
				AND l.is_carry_forward !=1 AND {0}
            GROUP BY l.employee, l.leave_type
        """.format(conditions_str), (self.from_date, self.to_date, self.company, self.branch, self.work_location), as_dict=1)

		if not data:
			frappe.throw("No Data Found")

		today = nowdate()
		self.bulk_leave_encashment_details = []
		for d in data:
			salary_details = self.get_salary_details(d)
			leave_application_taken = flt(-d.application_sum)

			try:
				bal = get_leave_balance_on(
					employee=d.employee,
					leave_type=d.leave_type,
					date=today,
					to_date=today,
					consider_all_leaves_in_the_allocation_period=True,
					for_consumption=False
				)
				avail_balance = flt(bal or 0)
			except Exception:
				avail_balance = 0.0

			encashable_days = avail_balance - leave_application_taken

			if d.employee not in existing_data_dict or existing_data_dict[d.employee] != d.leave_type:
				self.append("bulk_leave_encashment_details",{
					"employee":d.employee,
					"employee_name":d.employee_name,
					"payroll_cost_center":d.payroll_cost_center,
					"department":d.department,
					"leave_allocation":d.allocation_sum,
					"leave_application":leave_application_taken,
					"designation":d.designation,
					"leave_type":d.leave_type,
					"available_balance":avail_balance,
					"encashable_days":encashable_days,
					"salary_structure_assignment":salary_details.get("salary_structure_assignment"),
					"salary_structure":salary_details.get("salary_structure"),
					"formula":salary_details.get("formula"),
					"earning_component":salary_details.get("earning_component"),
					"season":self.season,
					"branch":self.branch,
					"work_location":self.work_location,
					"from_date":self.from_date,
					"to_date":self.to_date,
					"payroll_date":self.payroll_date,
					"remarks": ""
				})
		
	def get_salary_details(self,d):
		datadict = frappe._dict()
		leave = frappe.get_cached_doc("Leave Type",d.leave_type)
		if not leave.custom_allow_seasonal_encashment:
			frappe.throw("Leave Type {} is not encashable".format(get_link_to_form("Leave Type",leave.name)))
		
		if leave.custom_allow_seasonal_encashment and not leave.custom_earning_component:
			frappe.throw("Earning component for seasonal encashment is not defined on Leave Type {}".format(get_link_to_form("Leave Type",leave.name)))
		
		earning_component = leave.custom_earning_component 
		
		datadict.update({"leave_type":leave.name,"earning_component":earning_component})	
		salary_componet = frappe.get_cached_doc("Salary Component",earning_component)
		if not salary_componet.formula:
			frappe.throw("Formula is not defined on Salary Component {}".format(get_link_to_form("Salary Component",salary_componet.name)))
		datadict.update({"formula":salary_componet.formula})
		ssa= frappe.get_value("Salary Structure Assignment",{"employee":d.employee,"docstatus":1},order_by ="creation DESC")
		if ssa:
			datadict.update({"salary_structure_assignment":ssa})
			ss = frappe.get_value("Salary Structure Assignment",ssa,"salary_structure")
			datadict.update({"salary_structure":ss})
		return datadict

	def on_submit(self):
		frappe.msgprint(
			title=_("Creating Leave Encashment"),
			indicator="orange",
			alert=True,
			realtime=True,
			msg=_("Creating Leave Encashment action enqueued in background")
		)
		frappe.enqueue(
			"informatics_custom_apps.ripl_customized_apps.doctype.zzbulk_leave_encashment.zzbulk_leave_encashment.process_leave_encashment",
			docname=self.name,
			queue="long", 
			enqueue_after_commit=True
		)

	def on_cancel(self):
		frappe.msgprint(
			title=_("Cancelling Leave Encashment"),
			indicator="orange",
			alert=True,
			realtime=True,
			msg=_("Cancellation of Leave Encashment action enqueued in background")
		)
		frappe.enqueue(
			"informatics_custom_apps.ripl_customized_apps.doctype.zzbulk_leave_encashment.zzbulk_leave_encashment.process_cancellation",
			docname=self.name,
			queue="long",
			enqueue_after_commit=True
		)

	def create_leave_encashment(self):
		for d in self.bulk_leave_encashment_details:
			if d.remarks and d.remarks.startswith("Failed"):
				continue

			if flt(d.encashable_days) <= 0:
				d.db_set("remarks", "Failed: Encashable days must be greater than 0")
				continue

			max_allowed = flt(d.available_balance) - flt(d.leave_application or 0)
			if flt(d.encashable_days) > max_allowed:
				d.db_set("remarks", f"Failed: Encashable days ({d.encashable_days}) cannot be greater than Available Balance minus Leave Application ({max_allowed})")
				continue

			try:
				self.encashment_based_on()

				leave_period = frappe.db.get_value("Leave Period", {"company": self.company, "is_active": 1})
				if not leave_period:
					d.db_set("remarks", f"Failed: No active leave period for company {self.company}")
					continue

				if not d.salary_structure_assignment:
					d.db_set("remarks", "Failed: No active Salary Structure Assignment found")
					continue

				encashment_amount = flt(self.get_encashment_data(d))
				if encashment_amount <= 0:
					d.db_set("remarks", "Failed: Encashment amount must be greater than 0")
					continue

				le = frappe.new_doc("Leave Encashment")
				le.employee = d.employee
				le.leave_period = leave_period
				le.leave_type = d.leave_type
				le.encashment_days = d.encashable_days
				le.encashment_date = self.payroll_date
				le.encashment_amount = encashment_amount
				le.custom_bulk_leave_encashment = self.name
				le.save(ignore_permissions=True)
				le.submit()

				d.db_set("remarks", f"Successful: Created {le.name}")
			except Exception as e:
				frappe.db.rollback()
				error_msg = str(e).replace("<br>", " ").strip()
				if len(error_msg) > 140:
					error_msg = error_msg[:137] + "..."
				d.db_set("remarks", f"Failed: {error_msg}")
				frappe.db.commit()

	def cancel_leave_encashments(self):
		encashments = frappe.get_all(
			"Leave Encashment",
			filters={
				"custom_bulk_leave_encashment": self.name,
				"docstatus": 1
			},
			pluck="name"
		)

		for le_name in encashments:
			try:
				le_doc = frappe.get_doc("Leave Encashment", le_name)
				le_doc.flags.ignore_permissions = True
				le_doc.cancel()
			except Exception as e:
				frappe.log_error(
					message=f"Failed to cancel Leave Encashment {le_name}: {str(e)}",
					title="Bulk Leave Encashment Cancellation Error"
				)

		for d in self.bulk_leave_encashment_details:
			if d.remarks and d.remarks.startswith("Successful"):
				d.db_set("remarks", "Cancelled: Leave encashment reversed")

	def get_encashment_data(self, d):
		whitelisted_globals = {
            "int": int,
            "float": float,
            "long": int,
            "round": round,
            "date": date,
            "getdate": getdate,
            "ceil": ceil,
            "floor": floor,
        }
		data = frappe._dict()
		emp = frappe.get_cached_doc("Employee", d.employee)
		data.update(emp.as_dict())
		if d.salary_structure_assignment:
			salary_structure_assignment = frappe.get_cached_doc("Salary Structure Assignment", d.salary_structure_assignment)
			data.update(salary_structure_assignment.as_dict())
		data.update(d.as_dict())
		days = eval_formula(d, whitelisted_globals, data)
		return days
	
	def get_leave_details(self,employee,leave_type,date):
		data = get_leave_details(employee,date=date)
		if leave_type in data["leave_allocation"]:
			return data["leave_allocation"][leave_type]
		else:
			return {}
	
	def encashment_based_on(self):
		if self.based_on == "Custom":
			from hrms.hr.doctype.leave_encashment.leave_encashment import LeaveEncashment
			
			def custom_set_encashment_amount(self):
				if not hasattr(self, "_salary_structure"):
					self.set_salary_structure()
			def custom_set_encashment_days(self):
				pass
			setattr(LeaveEncashment,"set_encashment_amount",custom_set_encashment_amount)
			setattr(LeaveEncashment,"set_encashment_days",custom_set_encashment_days)

def sanitize_expression(string: str | None = None) -> str | None:
	if not string:
		return None

	parts = string.strip().splitlines()
	string = " ".join(parts)

	return string

def eval_formula(d,whitelisted_globals,data):
	try:
		amount = 0.0
		if d.get("formula"):
			formula = sanitize_expression(d.get("formula"))
			if formula:
				amount = flt(
					safe_eval(formula, whitelisted_globals, data)
				)
		if amount:
			return amount
	except Exception as e:
		frappe.throw(title="Formula Error", msg=f"Please check the formula: {str(e)}")

def process_leave_encashment(docname):
	doc = frappe.get_doc("zzBulk Leave Encashment", docname)
	doc.create_leave_encashment()

def process_cancellation(docname):
	doc = frappe.get_doc("zzBulk Leave Encashment", docname)
	doc.cancel_leave_encashments()




