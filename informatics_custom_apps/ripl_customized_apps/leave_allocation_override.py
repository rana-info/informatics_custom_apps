import frappe
from frappe.utils import getdate


ORIGINAL_METHOD = "hr_india_compliance.hr_india_compliance_utils.run_leave_allocation_method"


def should_skip_joiner(date_of_joining):
    return bool(date_of_joining and getdate(date_of_joining).day >= 10)


def run_leave_allocation_method(MANUAL_RUN=None, FROM_DATE=None, TO_DATE=None):
    compliance_utils = frappe.get_attr(
        "hr_india_compliance.hr_india_compliance_utils"
    )
    today = frappe.flags.current_date or getdate()

    for leave_type in compliance_utils.get_earned_leaves():
        leave_allocations = compliance_utils.get_leave_allocations(today, leave_type.name)
        for allocation in leave_allocations:
            date_of_joining = frappe.db.get_value(
                "Employee", allocation.employee, "date_of_joining"
            )
            if should_skip_joiner(date_of_joining):
                continue

            if not allocation.leave_policy_assignment and not allocation.leave_policy:
                continue

            leave_policy = (
                allocation.leave_policy
                if allocation.leave_policy
                else frappe.db.get_value(
                    "Leave Policy Assignment",
                    allocation.leave_policy_assignment,
                    "leave_policy",
                )
            )
            annual_allocation = frappe.db.get_value(
                "Leave Policy Detail",
                filters={"parent": leave_policy, "leave_type": leave_type.name},
                fieldname="annual_allocation",
            )
            from_date = allocation.from_date
            if leave_type.allocate_on_day == "Date Of Joining":
                from_date = date_of_joining

            if compliance_utils.check_effective_date(
                from_date,
                today,
                leave_type.earned_leave_frequency,
                leave_type.allocate_on_day,
            ):
                compliance_utils.update_leave_allocation_based_on_attendance(
                    allocation, annual_allocation, leave_type, date_of_joining
                )
            elif MANUAL_RUN == "True":
                compliance_utils.update_leave_allocation_based_on_attendance(
                    allocation,
                    annual_allocation,
                    leave_type,
                    date_of_joining,
                    MANUAL_RUN="True",
                    FROM_DATE=FROM_DATE,
                    TO_DATE=TO_DATE,
                )


def disable_original_scheduler_job():
    job_name = frappe.db.get_value(
        "Scheduled Job Type", {"method": ORIGINAL_METHOD}, "name"
    )
    if job_name:
        frappe.db.set_value("Scheduled Job Type", job_name, "stopped", 1)