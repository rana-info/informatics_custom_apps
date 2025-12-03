import frappe
from frappe.utils import getdate
from hrms.hr.utils import get_earned_leaves,update_previous_leave_allocation,check_effective_date
# def execute():
    
#     frappe.flags.current_date = getdate("2025-10-31")
    
#     from hrms.hr.utils import allocate_earned_leaves
    
#     allocate_earned_leaves()
    
#     frappe.flags.current_date = None
    
#     frappe.db.commit()
def execute():
    
    frappe.flags.current_date = getdate("2025-10-31")
    
    allocate_earned_leaves()
    
    frappe.flags.current_date = None
    
    frappe.db.commit()
    

from datetime import datetime
def allocate_earned_leaves():
	"""Allocate earned leaves to Employees"""
	e_leave_types = get_earned_leaves()
	today = frappe.flags.current_date or getdate()
	
	for e_leave_type in e_leave_types:
		leave_allocations = get_leave_allocations(today, e_leave_type.name)
		
		for allocation in leave_allocations:

			if not allocation.leave_policy_assignment and not allocation.leave_policy:
				continue
			leave_ledger_entry = get_leave_ledger_entry(allocation,e_leave_type.name)
			
			if not leave_ledger_entry:
				continue
			leave_policy = (
				allocation.leave_policy
				if allocation.leave_policy
				else frappe.db.get_value(
					"Leave Policy Assignment", allocation.leave_policy_assignment, ["leave_policy"]
				)
			)

			annual_allocation = frappe.db.get_value(
				"Leave Policy Detail",
				filters={"parent": leave_policy, "leave_type": e_leave_type.name},
				fieldname=["annual_allocation"],
			)
			date_of_joining = frappe.db.get_value("Employee", allocation.employee, "date_of_joining")

			from_date = allocation.from_date

			if e_leave_type.allocate_on_day == "Date of Joining":
				from_date = date_of_joining
			if check_effective_date(
				from_date, today, e_leave_type.earned_leave_frequency, e_leave_type.allocate_on_day
			):
				
				update_previous_leave_allocation(allocation, annual_allocation, e_leave_type, date_of_joining)


def get_leave_allocations(date, leave_type):
	employee = frappe.qb.DocType("Employee")
	leave_allocation = frappe.qb.DocType("Leave Allocation")
	query = (
		frappe.qb.from_(leave_allocation)
		.join(employee)
		.on(leave_allocation.employee == employee.name)
		.select(
			leave_allocation.name,
			leave_allocation.employee,
			leave_allocation.from_date,
			leave_allocation.to_date,
			leave_allocation.leave_policy_assignment,
			leave_allocation.leave_policy,
		)
		.where(
			(date >= leave_allocation.from_date)
			& (date <= leave_allocation.to_date)
			& (leave_allocation.docstatus == 1)
			& (leave_allocation.leave_type == leave_type)
			& (employee.status != "Left")
			& (employee.date_of_joining.between("2025-10-01", "2025-10-31"))

		)
	)
	return query.run(as_dict=1) or []

def get_leave_ledger_entry(allocation,leave_type):
    lle = frappe.qb.DocType("Leave Ledger Entry")

    query = (
        frappe.qb.from_(lle)
        .select(lle.name)
        .where(
           (lle.from_date == allocation.from_date)
            & (lle.employee == allocation.employee)
			& (lle.leave_type ==leave_type)
			& (lle.docstatus == 1)
        )
        .limit(1)
    )
    return query.run(as_dict=True)

	