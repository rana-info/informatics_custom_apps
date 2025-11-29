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
		
		if getdate(self.to_date)<getdate(self.from_date):
			frappe.throw("To Date can't be less than From Date")
		dr=frappe.db.get_value("zzDeputation Request",{"from_date":["between",[self.from_date,self.to_date]],"employee":self.employee,"docstatus":["!=",2]},["name"])
		dr1=frappe.db.get_value("zzDeputation Request",{"to_date":["between",[self.from_date,self.to_date]],"employee":self.employee,"docstatus":["!=",2]},["name"])
		if dr and dr!=self.name:
			frappe.throw("Deputation Request Already Created between date '{0}' and '{1}'".format(self.from_date,self.to_date))
		elif dr1 and dr1!=self.name:
			frappe.throw("Deputation Request Already Created between date '{0}' and '{1}'".format(self.from_date,self.to_date))
		from datetime import datetime
		
		start_date = getdate(self.from_date)
		end_date = getdate(self.to_date)

		days_difference = (end_date - start_date).days
		if self.plant:
			plant=frappe.get_doc("Branch",self.plant)
			if plant.deputation_minimum_applicable_days > days_difference:
				frappe.throw("Minimum Applicable days Of Deputation Is {0} days.you cannot apply for {1} days".format(plant.deputation_minimum_applicable_days,days_difference))


		if self.plant==self.to_plant:
			frappe.throw("To Plant & From Plant can't be same")
		if self.employee:
			employee=frappe.get_cached_doc("Employee",self.employee)
			if employee.status=="Left":
				frappe.throw(f"This {employee.name} has Left. It should not create a deputation request.")

		
def create_attendance_request(self):
	try:
		dates = []
		current_date = getdate(self.from_date)
		ho=get_holiday_dates_for_employee(self.employee,self.from_date,self.to_date)

		while current_date <= getdate(today()):
			if current_date not in ho: 
				dates.append(current_date.strftime('%Y-%m-%d'))
				current_date += timedelta(days=1)

		for kj in dates:
			attendance = frappe.db.exists("Attendance",{"employee":self.employee,"attendance_date":kj,"docstatus":("!=",2),"status":"Present"})
			on_leave = frappe.get_all("Leave Application", filters={"employee": self.employee,"from_date": ["<=", kj],"to_date": [">=", kj],"docstatus":("!=",2)})
			dc=frappe.db.get_value("Attendance Request",{"from_date":["<=", kj],"to_date":[">=", kj],"employee":self.employee,"docstatus":["!=",2]},["name"])
			if not attendance and not dc and not on_leave and kj not in ho:
				doc=frappe.new_doc("Attendance Request")
				doc.employee=self.employee
				doc.company=self.company
				doc.from_date=getdate(kj)
				doc.to_date=getdate(kj)
				doc.reason="On Duty"
				doc.custom_zzdeputation_request=self.name
				doc.save(ignore_permissions=True)
			else:
				continue
	except Exception as e:
		frappe.log_error("Error while creating Attendance Request from Deputation Request: " + str(self.name))

# @frappe.whitelist()
# def attendance_request_created():
# 	dr=frappe.db.sql("select * from `tabDeputation Request` where docstatus=1 and from_date <='{0}' and to_date >='{0}' ".format(today()),as_dict=1)
# 	for k in dr:
# 		employee=frappe.get_cached_doc("Employee",k.get("employee"))
# 		if employee.status == "Active" and (not employee.relieving_date or getdate(employee.relieving_date) >= getdate(today())):
			
# 			ho=get_holiday_dates_for_employee(k.get("employee"),today(),today())
# 			leave = frappe.get_all("Leave Application", filters={"employee": k.get("employee"),"from_date": ["<=", today()],"to_date": [">=", today()],"docstatus":("!=",2)})
# 			if str(getdate(today())) not in ho and not leave:
# 				dc=frappe.db.get_value("Attendance Request",{"from_date":["<=",today()],"to_date":[">=",today()],"employee":k.get("employee"),"docstatus":["!=",2]},["name"])
# 				attendence = frappe.db.exists("Attendence",{"employee":k.get("employee"),"attendence_date":getdate(today()),"docstatus":("!=",2)})
# 				if not dc and not attendence:
# 					doc=frappe.new_doc("Attendance Request")
# 					doc.employee=k.get("employee")
# 					doc.company=k.get("company")
# 					# doc.plant=k.get0("plant")
# 					doc.from_date=getdate(today())
# 					doc.to_date=getdate(today())
# 					doc.reason="On Duty"
# 					doc.deputation_request=k.get("name")
# 					doc.save(ignore_permissions=True)

@frappe.whitelist()
def attendance_request_created():
	try:
		dr = frappe.db.sql("""SELECT * FROM `tabzzDeputation Request` WHERE docstatus = 1 AND from_date <= %(today)s AND to_date >= %(today)s""", {"today": today()}, as_dict=1)
		# dr=frappe.db.sql("select * from `tabDeputation Request` where docstatus=1 and from_date <='{0}' and to_date >='{0}' ".format(today()),as_dict=1)
		for k in dr:
			employee=frappe.get_cached_doc("Employee",k.get("employee"))
			if k.actual_end_date and  k.actual_end_date < getdate(today()):
				continue
			if employee.status == "Active" and (not employee.relieving_date or getdate(employee.relieving_date) >= getdate(today())):
				
				ho=get_holiday_dates_for_employee(k.get("employee"),today(),today())
				if getdate(today()) not in ho:
					dc=frappe.db.get_value("Attendance Request",{"from_date":["<=",today()],"to_date":[">=",today()],"employee":k.get("employee"),"docstatus":["!=",2]},["name"])
					attendence = frappe.db.exists("Attendance",{"employee":k.get("employee"),"attendance_date":getdate(today()),"docstatus":("!=",2)})
					if not dc and not attendence:
						doc=frappe.new_doc("Attendance Request")
						doc.employee=k.get("employee")
						doc.company=k.get("company")
						# doc.plant=k.get0("plant")
						doc.from_date=getdate(today())
						doc.to_date=getdate(today())
						doc.reason="On Duty"
						doc.deputation_request=k.get("name")
						doc.save(ignore_permissions=True)

	except frappe.ValidationError as e:
		
		frappe.logger().info(f"Skipped creating attendance request for {k.get('employee')} due to validation error: {str(e)}")

@frappe.whitelist()
def on_cancel(deputation_request):
	attendance_requests = frappe.get_all("Attendance Request", filters={
		"deputation_request": deputation_request,
		"docstatus": 0
	}, pluck="name")

	for attendance_request in attendance_requests:
		frappe.get_doc("Attendance Request", attendance_request).delete()