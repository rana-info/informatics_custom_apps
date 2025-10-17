# Copyright (c) 2025, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

def execute(filters=None):
    # Handle case when report loads without filters
    if not filters:
        filters = {}

    columns = get_columns()
    data = []

    # Run data query only if all filters are filled
    if filters.get("branch") and filters.get("from_date") and filters.get("to_date"):
        data = get_data(filters)

    return columns, data


def get_columns():
    return [
        {"fieldname": "provident_fund_account", "label": "UAN", "fieldtype": "Data", "width": 150},
        {"fieldname": "employee_name", "label": "Employee Name", "fieldtype": "Data", "width": 170},
        {"fieldname": "gross_pay", "label": "Gross Pay", "fieldtype": "Currency", "width": 120},
        {"fieldname": "pf_salary", "label": "PF Salary", "fieldtype": "Currency", "width": 120},
        {"fieldname": "pension_salary", "label": "Pension Salary", "fieldtype": "Currency", "width": 120},
        {"fieldname": "edli", "label": "EDLI", "fieldtype": "Currency", "width": 100},
        {"fieldname": "pf_12_per", "label": "PF", "fieldtype": "Currency", "width": 120},
        {"fieldname": "employee_pension_amount", "label": "EPS", "fieldtype": "Currency", "width": 120},
        {"fieldname": "employee_pf", "label": "EPF", "fieldtype": "Currency", "width": 120},
        {"fieldname": "payment_absent_days", "label": "NCP Days", "fieldtype": "Float", "width": 100}
    ]


def get_data(filters):
    # Query salary slips within filter range
    salary_slips = frappe.db.sql("""
        SELECT 
            name, employee, employee_name, branch, gross_pay, total_working_days, payment_days
        FROM `tabSalary Slip`
        WHERE docstatus = 1
        AND branch = %s
        AND start_date >= %s
        AND end_date <= %s
    """, (filters.branch, filters.from_date, filters.to_date), as_dict=True)

    if not salary_slips:
        frappe.msgprint(f"No Salary Slips found between {filters.from_date} and {filters.to_date} for branch {filters.branch}")
        return []

    data = []

    for slip in salary_slips:
        employee = frappe.get_cached_doc("Employee", slip.employee)

        # Skip if no UAN
        if not employee.provident_fund_account:
            continue

        # Fetch Basic Salary from Salary Detail
        basic_salary = frappe.db.get_value(
            "Salary Detail",
            {"parent": slip.name, "abbr": "B", "parentfield": "earnings"},
            "amount"
        ) or 0

        row = {
		"employee_name": slip.employee_name,
		"provident_fund_account": employee.provident_fund_account,
		"gross_pay": flt(slip.gross_pay),
		"payment_absent_days": flt(slip.total_working_days) - flt(slip.payment_days),
		"pf_salary": min(flt(basic_salary), 15000),
		"pension_salary": min(flt(basic_salary), 15000),
		"edli": min(flt(basic_salary), 15000),
		"pf_12_per": 0,
		"employee_pension_amount": 0,
		"employee_pf": 0,
		}


        salary_details = frappe.db.get_all(
            "Salary Detail",
            filters={"parent": slip.name},
            fields=["salary_component", "amount", "parentfield"]
        )

        for sd in salary_details:
            sc = frappe.get_value(
                "Salary Component",
                sd.salary_component,
                ["custom_pf_12_per", "custom_employee_pension_amount", "custom_employee_pf"],
                as_dict=True
            ) or {}

            if sc.get("custom_pf_12_per"):
                row["pf_12_per"] = flt(sd.amount)
            if sc.get("custom_employee_pension_amount"):
                row["employee_pension_amount"] = flt(sd.amount)
            if sc.get("custom_employee_pf"):
                row["employee_pf"] = flt(sd.amount)

        data.append(row)

    # Sort by employee name for readability
    return sorted(data, key=lambda x: x["employee_name"])
