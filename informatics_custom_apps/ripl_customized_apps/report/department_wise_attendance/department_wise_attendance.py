# Copyright (c) 2025, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe

import frappe

def execute(filters=None):
    date = filters.get("date")
    plant = filters.get("plant")

    columns = [
        {"label": "Department", "fieldname": "department", "fieldtype": "Data", "width": 250},
        {"label": "Total Employees", "fieldname": "total_employees", "fieldtype": "Int", "width": 150},
        {"label": "Present", "fieldname": "present", "fieldtype": "Int", "width": 100},
        {"label": "Absent", "fieldname": "absent", "fieldtype": "Int", "width": 100},
    ]

    data = frappe.db.sql("""
        SELECT
		emp.department AS department,
		COUNT(emp.name) AS total_employees,
		COUNT(CASE WHEN att.status = 'Present' THEN 1 END) AS present,
		COUNT(CASE WHEN att.status IS NULL OR att.status != 'Present' THEN 1 END) AS absent
		FROM
			`tabEmployee` emp
		LEFT JOIN (
			SELECT 
				SUBSTRING_INDEX(employee, ':', 1) AS emp_name,
				status
			FROM 
				`tabAttendance`
			WHERE 
				attendance_date = %s
				AND docstatus != 2
			GROUP BY emp_name  -- ensures one record per employee
		) att
		ON emp.name = att.emp_name
		WHERE
			emp.branch = %s
			AND emp.department IS NOT NULL
			AND emp.status = 'Active'
		GROUP BY
			emp.department
		ORDER BY
			emp.department;

    """, (date, plant), as_dict=True)

    return columns, data
