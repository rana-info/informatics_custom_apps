# Copyright (c) 2025, Monil Kamboj and contributors
# For license information, please see license.txt

from calendar import monthrange
from functools import reduce
from itertools import groupby
from typing import Dict, List, Optional, Tuple

import frappe
from frappe import _
from frappe.query_builder.functions import Count, Extract, Sum
from frappe.utils import cint, cstr, getdate

Filters = frappe._dict

status_map = {
	"Present": "P",
	"Absent": "A",
	"Half Day": "HD",
	"Work From Home": "WFH",
	"On Leave": "L",
	"Holiday": "H",
	"Weekly Off": "WO",
}
leave_type_abbrs_map = {}

day_abbr = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def execute(filters: Optional[Filters] = None) -> Tuple:
	filters = frappe._dict(filters or {})

	if not (filters.month and filters.year):
		frappe.throw(_("Please select month and year."))

	leave_type_abbrs_map.update(get_leave_type_abbrs())

	attendance_map = get_attendance_map(filters)
	if not attendance_map:
		frappe.msgprint(_("No attendance records found."), alert=True, indicator="orange")
		return [], [], None, None

	columns = get_columns(filters)
	data = get_data(filters, attendance_map)

	if not data:
		frappe.msgprint(
			_("No attendance records found for this criteria."), alert=True, indicator="orange"
		)
		return columns, [], None, None
	
	message = get_message() if not filters.summarized_view else ""
	message2= get_message_for_abbr() if not filters.summarised_view else ""
	combined_message = f"{message}<br>{message2}"
	chart = get_chart_data(attendance_map, filters) if filters.view_chart_details else None
	
	if filters.get("view_details_on_leave_type") and not filters.get("summarized_view"):
		return columns, data, combined_message, chart
	else:
		return columns,data,message,chart

# def execute(filters: Filters | None = None) -> tuple:
# 	filters = frappe._dict(filters or {})

# 	if not (filters.month and filters.year):
# 		frappe.throw(_("Please select month and year."))
	
# 	leave_type_abbrs_map.update(get_leave_type_abbrs())

# 	attendance_map = get_attendance_map(filters)
# 	if not attendance_map:
# 		frappe.msgprint(_("No attendance records found."), alert=True, indicator="orange")
# 		return [], [], None, None

# 	columns = get_columns(filters)
# 	data = get_data(filters, attendance_map)

# 	if not data:
# 		frappe.msgprint(_("No attendance records found for this criteria."), alert=True, indicator="orange")
# 		return columns, [], None, None

# 	message = get_message() if not filters.summarized_view else ""
# 	message2= get_message_for_abbr() if not filters.summarised_view else ""
# 	combined_message = f"{message}<br>{message2}"
# 	chart = get_chart_data(attendance_map, filters) if filters.view_chart_details else None
	
# 	if filters.get("view_details_on_leave_type") and not filters.get("summarized_view"):
# 		return columns, data, combined_message, chart
# 	else:
# 		return columns,data,message,chart


def get_message() -> str:
	message = ""
	colors = ["green", "red", "orange", "green", "#318AD8", "", ""]

	count = 0
	for status, abbr in status_map.items():
		message += f"""
			<span style='border-left: 2px solid {colors[count]}; padding-right: 12px; padding-left: 5px; margin-right: 3px;'>
				{status} - {abbr}
			</span>
		"""
		count += 1
	return message

def get_message_for_abbr() -> str:
    message = ""
    
    for status, abbr in leave_type_abbrs_map.items():
        message += f"""
            <span style='border-left: 2px solid black; padding-right: 12px; padding-left: 5px; margin-right: 3px;'>
                {status} - {abbr}
            </span>
        """

    return message

def get_leave_type_abbrs() -> Dict[str, str]:
    leave_type_abbrs = {}

    leave_types = frappe.get_all("Leave Type", filters={"custom_abbr": ("!=", "")}, fields=["name", "custom_abbr"])

    for leave_type in leave_types:
        leave_type_abbrs[leave_type.name] = leave_type.custom_abbr

    return leave_type_abbrs

def get_columns(filters: Filters) -> List[Dict]:
	columns = []

	if filters.group_by:
		columns.append(
			{
				"label": _(filters.group_by),
				"fieldname": frappe.scrub(filters.group_by),
				"fieldtype": "Link",
				"options": "Branch",
				"width": 120,
			}
		)

	columns.extend(
		[
			{
				"label": _("Employee"),
				"fieldname": "employee",
				"fieldtype": "Link",
				"options": "Employee",
				"width": 135,
			},
			{"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 120},
		]
	)

	if filters.summarized_view:
		columns.extend(
			[
				{
					"label": _("Total Present"),
					"fieldname": "total_present",
					"fieldtype": "Float",
					"width": 110,
				},
				{"label": _("Total Leaves"), "fieldname": "total_leaves", "fieldtype": "Float", "width": 110},
				{"label": _("Total Absent"), "fieldname": "total_absent", "fieldtype": "Float", "width": 110},
				{
					"label": _("Total Holidays"),
					"fieldname": "total_holidays",
					"fieldtype": "Float",
					"width": 120,
				},
				{
					"label": _("Unmarked Days"),
					"fieldname": "unmarked_days",
					"fieldtype": "Float",
					"width": 130,
				},
			]
		)
		columns.extend(get_columns_for_leave_types())
		columns.extend(
			[
				{
					"label": _("Total Late Entries"),
					"fieldname": "total_late_entries",
					"fieldtype": "Float",
					"width": 140,
				},
				{
					"label": _("Total Early Exits"),
					"fieldname": "total_early_exits",
					"fieldtype": "Float",
					"width": 140,
				},
			]
		)
	else:
		columns.append({"label": _("Date of Joining"), "fieldname": "doj", "fieldtype": "Data", "width": 120})
		columns.append({"label": _("Shift"), "fieldname": "shift", "fieldtype": "Data", "width": 120})
		columns.append({"label":_("Total Paid Days"),"fieldname":"total_paid_days","fieldtype":"Float","width":100})
		columns.extend(get_columns_for_days(filters))

	return columns


def get_columns_for_leave_types() -> List[Dict]:
	leave_types = frappe.db.get_all("Leave Type", pluck="name")
	types = []
	for entry in leave_types:
		types.append(
			{"label": entry, "fieldname": frappe.scrub(entry), "fieldtype": "Float", "width": 120}
		)

	return types


def get_columns_for_days(filters: Filters) -> List[Dict]:
	total_days = get_total_days_in_month(filters)
	days = []

	for day in range(1, total_days + 1):
		# forms the dates from selected year and month from filters
		date = "{}-{}-{}".format(cstr(filters.year), cstr(filters.month), cstr(day))
		# gets abbr from weekday number
		weekday = day_abbr[getdate(date).weekday()]
		# sets days as 1 Mon, 2 Tue, 3 Wed
		# label = "{} {}".format(cstr(day), weekday)
		label = "{} {}".format(cstr(day), "")
		days.append({"label": label, "fieldtype": "Data", "fieldname": day, "width": 65})
	return days


def get_total_days_in_month(filters: Filters) -> int:
	return monthrange(cint(filters.year), cint(filters.month))[1]


def get_data(filters: Filters, attendance_map: Dict) -> List[Dict]:
	employee_details, group_by_param_values = get_employee_related_details(filters)
	holiday_map = get_holiday_map(filters)
	
	data = []

	if filters.group_by:
		group_by_column = frappe.scrub(filters.group_by)

		for value in group_by_param_values:
			if not value:
				continue

			records = get_rows(employee_details[value], filters, holiday_map, attendance_map)
			print("Records:--->",records)

			if records:
				data.append({group_by_column: frappe.bold(value)})
				data.extend(records)
	else:
		data = get_rows(employee_details, filters, holiday_map, attendance_map)

		print("data:------>",data)

	return data


def get_attendance_map(filters: Filters) -> Dict:
	"""Returns a dictionary of employee wise attendance map as per shifts for all the days of the month like
	{
	    'employee1': {
	            'Morning Shift': {1: 'Present', 2: 'Absent', ...}
	            'Evening Shift': {1: 'Absent', 2: 'Present', ...}
	    },
	    'employee2': {
	            'Afternoon Shift': {1: 'Present', 2: 'Absent', ...}
	            'Night Shift': {1: 'Absent', 2: 'Absent', ...}
	    },
	    'employee3': {
	            None: {1: 'On Leave'}
	    }
	}
	"""
	attendance_list = get_attendance_records(filters)
	
	attendance_map = {}
	leave_map = {}

	for d in attendance_list:
		if d.status == "On Leave":
			leave_map.setdefault(d.employee, []).append(d.day_of_month)
			continue

		attendance_map.setdefault(d.employee, {}).setdefault(d.shift, {})
		attendance_map[d.employee][d.shift][d.day_of_month] = d.status

	# leave is applicable for the entire day so all shifts should show the leave entry
	for employee, leave_days in leave_map.items():
		if employee not in attendance_map:
			attendance_map.setdefault(employee, {}).setdefault(None, {})

		for day in leave_days:
			for shift in attendance_map[employee].keys():
				attendance_map[employee][shift][day] = "On Leave"

	return attendance_map

def get_attendance_records(filters: Filters) -> List[Dict]:
	Attendance = frappe.qb.DocType("Attendance")
	query = (
		frappe.qb.from_(Attendance)
		.select(
			Attendance.employee,
			Extract("day", Attendance.attendance_date).as_("day_of_month"),
			Attendance.status,
			Attendance.shift,
		)
		.where(
			(Attendance.docstatus == 1)
			& (Attendance.company == filters.company)
			& (Extract("month", Attendance.attendance_date) == filters.month)
			& (Extract("year", Attendance.attendance_date) == filters.year)
		)
	)

	if filters.employee:
		query = query.where(Attendance.employee == filters.employee)
	query = query.orderby(Attendance.employee, Attendance.attendance_date)

	return query.run(as_dict=1)


def get_employee_related_details(filters: Filters) -> Tuple[Dict, List]:
	"""Returns
	1. nested dict for employee details
	2. list of values for the group by filter
	"""
	Employee = frappe.qb.DocType("Employee")
	query = (
		frappe.qb.from_(Employee)
		.select(
			Employee.name,
			Employee.employee_name,
			Employee.date_of_joining,
			Employee.designation,
			Employee.grade,
			Employee.department,
			Employee.branch,
			Employee.company,
			Employee.holiday_list,
		)
		.where(Employee.company == filters.company)
	)

	# Keep employees who are not "Left" OR who have any "Present" attendance in the selected month/year
	Attendance = frappe.qb.DocType("Attendance")
	present_subquery = (
		frappe.qb.from_(Attendance)
		.select(Attendance.employee)
		.where(
			(Attendance.docstatus == 1)
			& (Attendance.company == filters.company)
			& (Extract("month", Attendance.attendance_date) == filters.month)
			& (Extract("year", Attendance.attendance_date) == filters.year)
			& (Attendance.status == "Present")
		)
	)

	# Employee.status != "Left" OR Employee.name IN (present_subquery)
	query = query.where((Employee.status != "Left") | (Employee.name.isin(present_subquery)))

	if filters.employee:
		query = query.where(Employee.name == filters.employee)
	if filters.branch:
		query = query.where(Employee.branch == filters.branch)

	group_by = filters.group_by
	if group_by:
		group_by = group_by.lower()
		query = query.orderby(group_by)

	employee_details = query.run(as_dict=True)

	group_by_param_values = []
	emp_map = {}

	if group_by:
		for parameter, employees in groupby(employee_details, key=lambda d: d[group_by]):
			group_by_param_values.append(parameter)
			emp_map.setdefault(parameter, frappe._dict())
			for emp in employees:
				emp_map[parameter][emp.name] = emp
	else:
		for emp in employee_details:
			emp_map[emp.name] = emp

	return emp_map, group_by_param_values

def get_holiday_map(filters: Filters) -> Dict[str, List[Dict]]:
	"""
	Returns a dict of holidays falling in the filter month and year
	with list name as key and list of holidays as values like
	{
	        'Holiday List 1': [
	                {'day_of_month': '0' , 'weekly_off': 1},
	                {'day_of_month': '1', 'weekly_off': 0}
	        ],
	        'Holiday List 2': [
	                {'day_of_month': '0' , 'weekly_off': 1},
	                {'day_of_month': '1', 'weekly_off': 0}
	        ]
	}
	"""
	# add default holiday list too
	holiday_lists = frappe.db.get_all("Holiday List", pluck="name")
	default_holiday_list = frappe.get_cached_value("Company", filters.company, "default_holiday_list")
	holiday_lists.append(default_holiday_list)

	holiday_map = frappe._dict()
	Holiday = frappe.qb.DocType("Holiday")

	for d in holiday_lists:
		if not d:
			continue

		holidays = (
			frappe.qb.from_(Holiday)
			.select(Extract("day", Holiday.holiday_date).as_("day_of_month"), Holiday.weekly_off)
			.where(
				(Holiday.parent == d)
				& (Extract("month", Holiday.holiday_date) == filters.month)
				& (Extract("year", Holiday.holiday_date) == filters.year)
			)
		).run(as_dict=True)

		holiday_map.setdefault(d, holidays)
	

	return holiday_map

def get_rows(
    employee_details: Dict, filters: Filters, holiday_map: Dict, attendance_map: Dict
) -> List[Dict]:
    records = []
    default_holiday_list = frappe.get_cached_value(
        "Company", filters.company, "default_holiday_list"
    )

    for employee, details in employee_details.items():

        emp_holiday_list = []
        emp_holiday_list.append(details.holiday_list or default_holiday_list)
        holidays = []

        if frappe.db.get_single_value(
            "Payroll Settings", "custom_consider_holidays_from_shift_assignment"
        ):
            assignment_holiday_list = get_holiday_list_from_attendance_request(
                employee=details.name, filters=filters
            )
            for d in assignment_holiday_list:
                emp_holiday_list.append(d.holiday)

        for rk in emp_holiday_list:
            holidays = holiday_map.get(rk)

        if filters.summarized_view:
            attendance = get_attendance_status_for_summarized_view(
                employee, filters, holidays
            )

            if not attendance:
                continue

            leave_summary = get_leave_summary(employee, filters)
            entry_exits_summary = get_entry_exits_summary(employee, filters)

            row = {"employee": employee, "employee_name": details.employee_name}
            set_defaults_for_summarized_view(filters, row)
            row.update(attendance)
            row.update(leave_summary)
            row.update(entry_exits_summary)

            records.append(row)

        else:
            employee_attendance = attendance_map.get(employee)
            if not employee_attendance:
                continue

            attendance_for_employee = get_attendance_status_for_detailed_view(
                employee, filters, employee_attendance, holidays
            )

            tpd = get_detailed_paid_days(employee, filters, holidays)

            merged_row = {
                "employee": employee,
				"doj": details.date_of_joining,
                "employee_name": details.employee_name,
                "total_paid_days": tpd.get("total_paid_days"),
                "shift": ", ".join(
                    [str(k) if k else "No Shift" for k in employee_attendance.keys()]
                ),
            }

            total_days = get_total_days_in_month(filters)

            for day in range(1, total_days + 1):
                value = ""
                for shift_row in attendance_for_employee:
                    if shift_row.get(day):
                        value = shift_row.get(day)
                        break
                merged_row[day] = value

            records.append(merged_row)

    return records


# def get_rows(
# 	employee_details: Dict, filters: Filters, holiday_map: Dict, attendance_map: Dict
# ) -> List[Dict]:
# 	records = []
# 	default_holiday_list = frappe.get_cached_value("Company", filters.company, "default_holiday_list")

# 	for employee, details in employee_details.items():
		
# 		emp_holiday_list = []
# 		emp_holiday_list.append(details.holiday_list or default_holiday_list)
# 		holidays = []

# 		if frappe.db.get_single_value("Payroll Settings","custom_consider_holidays_from_shift_assignment"):
# 			assignment_holiday_list = get_holiday_list_from_attendance_request(employee=details.name,filters=filters)
# 			for d in assignment_holiday_list:
# 				emp_holiday_list.append(d.holiday)

# 		for rk in emp_holiday_list:
# 			holidays = holiday_map.get(rk)

# 		if filters.summarized_view:
# 			attendance = get_attendance_status_for_summarized_view(employee, filters, holidays)
			
# 			if not attendance:
# 				continue

# 			leave_summary = get_leave_summary(employee, filters)
# 			entry_exits_summary = get_entry_exits_summary(employee, filters)

# 			row = {"employee": employee, "employee_name": details.employee_name}
# 			set_defaults_for_summarized_view(filters, row)
# 			row.update(attendance)
# 			row.update(leave_summary)
# 			row.update(entry_exits_summary)

# 			records.append(row)
# 		else:
			
			
# 			employee_attendance = attendance_map.get(employee)
# 			if not employee_attendance:
# 				continue

# 			attendance_for_employee = get_attendance_status_for_detailed_view(
# 				employee, filters, employee_attendance, holidays
# 			)
			
# 			tpd = get_detailed_paid_days(employee,filters,holidays)

# 			attendance_for_employee[0].update(
# 				{"employee": employee, "employee_name": details.employee_name,"total_paid_days":tpd.get("total_paid_days")}
# 			)

# 			records.extend(attendance_for_employee)
# 	return records


def get_holiday_list_from_attendance_request(employee,filters):
	'''If in selected month, if there are any shift assignment are exist for the respective employee then this function will return that selcted holiday from attendance request like
	[{'holiday':'Holiday 1','holiday':'Holiday 1'}]
	
	'''
	assignment = frappe.qb.DocType("Shift Assignment")
	assignment_holiday_list = (
		frappe.qb.from_(assignment)
		.select(assignment.holiday)
		.where(
			(assignment.docstatus == 1)
			& (assignment.employee == employee)
			& (
				(
					(Extract("month", assignment.start_date) == filters.month)
					& (Extract("year", assignment.start_date) == filters.year)
				) |
				(
					(Extract("month", assignment.end_date) == filters.month)
					& (Extract("year", assignment.end_date) == filters.year)
				)
			)
		)
	).run(as_dict=True)

	return assignment_holiday_list
	


def set_defaults_for_summarized_view(filters, row):
	for entry in get_columns(filters):
		if entry.get("fieldtype") == "Float":
			row[entry.get("fieldname")] = 0.0


def get_attendance_status_for_summarized_view(
	employee: str, filters: Filters, holidays: List
) -> Dict:
	"""Returns dict of attendance status for employee like
	{'total_present': 1.5, 'total_leaves': 0.5, 'total_absent': 13.5, 'total_holidays': 8, 'unmarked_days': 5}
	"""
	summary, attendance_days = get_attendance_summary_and_days(employee, filters)
	if not any(summary.values()):
		return {}	

	total_days = get_total_days_in_month(filters)
	total_holidays = total_unmarked_days = 0

	for day in range(1, total_days + 1):
		if day in attendance_days:
			continue

		status = get_holiday_status(day, holidays)
		if status in ["Weekly Off", "Holiday"]:
			total_holidays += 1
		elif not status:
			total_unmarked_days += 1
	return {
		"total_present": summary.total_present + summary.total_half_days,
		"total_leaves": summary.total_leaves + summary.total_half_days,
		"total_absent": summary.total_absent,
		"total_holidays": total_holidays,
		"unmarked_days": total_unmarked_days,
	}


def get_attendance_summary_and_days(employee: str, filters: Filters) -> Tuple[Dict, List]:
	Attendance = frappe.qb.DocType("Attendance")

	present_case = (
		frappe.qb.terms.Case()
		.when(((Attendance.status == "Present") | (Attendance.status == "Work From Home")), 1)
		.else_(0)
	)
	sum_present = Sum(present_case).as_("total_present")

	absent_case = frappe.qb.terms.Case().when(Attendance.status == "Absent", 1).else_(0)
	sum_absent = Sum(absent_case).as_("total_absent")

	leave_case = frappe.qb.terms.Case().when(Attendance.status == "On Leave", 1).else_(0)
	sum_leave = Sum(leave_case).as_("total_leaves")

	half_day_case = frappe.qb.terms.Case().when(Attendance.status == "Half Day", 0.5).else_(0)
	sum_half_day = Sum(half_day_case).as_("total_half_days")

	summary = (
		frappe.qb.from_(Attendance)
		.select(
			sum_present,
			sum_absent,
			sum_leave,
			sum_half_day,
		)
		.where(
			(Attendance.docstatus == 1)
			& (Attendance.employee == employee)
			& (Attendance.company == filters.company)
			& (Extract("month", Attendance.attendance_date) == filters.month)
			& (Extract("year", Attendance.attendance_date) == filters.year)
		)
	).run(as_dict=True)

	days = (
		frappe.qb.from_(Attendance)
		.select(Extract("day", Attendance.attendance_date).as_("day_of_month"))
		.distinct()
		.where(
			(Attendance.docstatus == 1)
			& (Attendance.employee == employee)
			& (Attendance.company == filters.company)
			& (Extract("month", Attendance.attendance_date) == filters.month)
			& (Extract("year", Attendance.attendance_date) == filters.year)
		)
	).run(pluck=True)
	return summary[0], days

def get_attendance_status_for_detailed_view(
	employee: str, filters: Filters, employee_attendance: Dict, holidays: List
) -> List[Dict]:
	"""Returns list of shift-wise attendance status for employee
	[
	        {'shift': 'Morning Shift', 1: 'A', 2: 'P', 3: 'A'....},
	        {'shift': 'Evening Shift', 1: 'P', 2: 'A', 3: 'P'....}
	]
	"""
	total_days = get_total_days_in_month(filters)
	attendance_values = []

	for shift, status_dict in employee_attendance.items():
		row = {"shift": shift}
		
		for day in range(1, total_days + 1):
			status = status_dict.get(day)
			if status is None and holidays:
				status = get_holiday_status(day, holidays)
				
			abbr = status_map.get(status, "")
			_status = ""  # Reset _status for each day

			if filters.get("view_details_on_leave_type"):
				if status == "On Leave":
					leave_type = get_leave_type_for_day(employee, filters, day)
					if leave_type:
						leave_abbr_data = abbr_data(leave_type)
						abbr = leave_abbr_data[0].get('custom_abbr') if leave_abbr_data else ""

				if status == "Half Day":
					leave_type = get_leave_type_for_day(employee, filters, day)
					if leave_type:
						leave_type_abbr_data = abbr_data(leave_type)
						_status = f"HD-{leave_type_abbr_data[0].get('custom_abbr')}" if leave_type_abbr_data else ""
					else:
						_status = "HD"

			row[day] = _status if status == "Half Day" else abbr
			
		attendance_values.append(row)

	return attendance_values


def abbr_data(leave_type):
	return frappe.db.sql("""SELECT custom_abbr FROM `tabLeave Type` WHERE leave_type_name = "{0}" """.format(leave_type),as_dict=1)

def get_leave_type_for_day(employee: str, filters: Filters, day: int) -> str:
	"""Returns the leave_type for a specific day."""
	Attendance = frappe.qb.DocType("Attendance")
	leave_type = (
		frappe.qb.from_(Attendance)
		.select(Attendance.leave_type)
		.where(
			(Attendance.docstatus == 1)
			& (Attendance.employee == employee)
			& (Extract("day", Attendance.attendance_date) == day)
			& (Extract("month", Attendance.attendance_date) == filters.month)
			& (Extract("year", Attendance.attendance_date) == filters.year)
		)
	).run(pluck=True)

	return leave_type[0] if leave_type else ""

def get_holiday_status(day: int, holidays: List) -> str:
	status = None
	if holidays:
		for holiday in holidays:
			if day == holiday.get("day_of_month"):
				if holiday.get("weekly_off"):
					status = "Weekly Off"
				else:
					status = "Holiday"
				break
	return status


def get_leave_summary(employee: str, filters: Filters) -> Dict[str, float]:
	"""Returns a dict of leave type and corresponding leaves taken by employee like:
	{'leave_without_pay': 1.0, 'sick_leave': 2.0}
	"""
	Attendance = frappe.qb.DocType("Attendance")
	day_case = frappe.qb.terms.Case().when(Attendance.status == "Half Day", 0.5).else_(1)
	sum_leave_days = Sum(day_case).as_("leave_days")

	leave_details = (
		frappe.qb.from_(Attendance)
		.select(Attendance.leave_type, sum_leave_days)
		.where(
			(Attendance.employee == employee)
			& (Attendance.docstatus == 1)
			& (Attendance.company == filters.company)
			& ((Attendance.leave_type.isnotnull()) | (Attendance.leave_type != ""))
			& (Extract("month", Attendance.attendance_date) == filters.month)
			& (Extract("year", Attendance.attendance_date) == filters.year)
		)
		.groupby(Attendance.leave_type)
	).run(as_dict=True)

	leaves = {}
	for d in leave_details:
		leave_type = frappe.scrub(d.leave_type)
		leaves[leave_type] = d.leave_days

	return leaves

def get_entry_exits_summary(employee: str, filters: Filters) -> Dict[str, float]:
	"""Returns total late entries and total early exits for employee like:
	{'total_late_entries': 5, 'total_early_exits': 2}
	"""
	Attendance = frappe.qb.DocType("Attendance")

	late_entry_case = frappe.qb.terms.Case().when(Attendance.late_entry == "1", "1")
	count_late_entries = Count(late_entry_case).as_("total_late_entries")

	early_exit_case = frappe.qb.terms.Case().when(Attendance.early_exit == "1", "1")
	count_early_exits = Count(early_exit_case).as_("total_early_exits")

	entry_exits = (
		frappe.qb.from_(Attendance)
		.select(count_late_entries, count_early_exits)
		.where(
			(Attendance.docstatus == 1)
			& (Attendance.employee == employee)
			& (Attendance.company == filters.company)
			& (Extract("month", Attendance.attendance_date) == filters.month)
			& (Extract("year", Attendance.attendance_date) == filters.year)
		)
	).run(as_dict=True)

	return entry_exits[0]


@frappe.whitelist()
def get_attendance_years() -> str:
	"""Returns all the years for which attendance records exist"""
	Attendance = frappe.qb.DocType("Attendance")
	year_list = (
		frappe.qb.from_(Attendance).select(Extract("year", Attendance.attendance_date).as_("year")).distinct()
	).run(as_dict=True)

	if year_list:
		year_list.sort(key=lambda d: d.year, reverse=True)
	else:
		year_list = [frappe._dict({"year": getdate().year})]
	
	print("*****************","\n".join(cstr(entry.year) for entry in year_list))

	return "\n".join(cstr(entry.year) for entry in year_list)


def get_chart_data(attendance_map: Dict, filters: Filters) -> Dict:
	days = get_columns_for_days(filters)
	labels = []
	absent = []
	present = []
	leave = []

	for day in days:
		labels.append(day["label"])
		total_absent_on_day = total_leaves_on_day = total_present_on_day = 0

		for employee, attendance_dict in attendance_map.items():
			for shift, attendance in attendance_dict.items():
				attendance_on_day = attendance.get(day["fieldname"])

				if attendance_on_day == "On Leave":
					# leave should be counted only once for the entire day
					total_leaves_on_day += 1
					break
				elif attendance_on_day == "Absent":
					total_absent_on_day += 1
				elif attendance_on_day in ["Present", "Work From Home"]:
					total_present_on_day += 1
				elif attendance_on_day == "Half Day":
					total_present_on_day += 0.5
					total_leaves_on_day += 0.5

		absent.append(total_absent_on_day)
		present.append(total_present_on_day)
		leave.append(total_leaves_on_day)

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{"name": "Absent", "values": absent},
				{"name": "Present", "values": present},
				{"name": "Leave", "values": leave},
			],
		},
		"type": "line",
		"colors": ["red", "green", "blue"],
	}

def get_detailed_paid_days(employee: str, filters: Filters, holidays: List) -> Dict:
    """
    Returns:
      { "total_paid_days": <float> }

    Notes:
      - Half-days handled in get_total_paid_days()
      - Unmarked days are NOT counted as paid
      - Holidays/WO excluded before DOJ or after relieving_date
    """
    summary, attendance_days = get_total_paid_days(employee, filters)

    if not summary or not any((v for v in summary.values() if v)):
        return {}

    total_present = summary.get("total_present", 0) if isinstance(summary, dict) else getattr(summary, "total_present", 0)
    total_paid_leaves = summary.get("total_paid_leaves", 0) if isinstance(summary, dict) else getattr(summary, "total_paid_leaves", 0)
    total_unpaid_leaves = summary.get("total_unpaid_leaves", 0) if isinstance(summary, dict) else getattr(summary, "total_unpaid_leaves", 0)

    total_days = get_total_days_in_month(filters)

    # --- Determine DOJ and Relieving Date ---
    doj, relieving_date = frappe.db.get_value(
        "Employee", employee, ["date_of_joining", "relieving_date"]
    )

    start_day, end_day = 1, total_days

    # Convert to dates for comparison
    month_start = getdate(f"{filters.year}-{int(filters.month):02d}-01")
    month_end = getdate(f"{filters.year}-{int(filters.month):02d}-{total_days:02d}")

    # (1) Handle DOJ logic — skip days before joining
    if doj:
        doj_date = getdate(doj)
        if doj_date > month_end:
            # Joined after month — no paid days
            return {"total_paid_days": 0}
        if doj_date.year == cint(filters.year) and doj_date.month == cint(filters.month):
            start_day = doj_date.day

    # (2) Handle relieving_date logic — skip days after relieving
    if relieving_date:
        rel_date = getdate(relieving_date)
        if rel_date < month_start:
            # Left before this month started
            return {"total_paid_days": 0}
        if rel_date.year == cint(filters.year) and rel_date.month == cint(filters.month):
            end_day = rel_date.day

    # --- Count Holidays and Unmarked Days only between DOJ and relieving ---
    total_holidays = 0
    total_unmarked_days = 0

    for day in range(start_day, end_day + 1):
        if day in attendance_days:
            continue

        status = get_holiday_status(day, holidays)
        if status in ["Weekly Off", "Holiday"]:
            total_holidays += 1
        elif not status:
            total_unmarked_days += 1

    # --- Compute total paid days ---
    total_paid_days = (
        (total_present or 0)
        + (total_paid_leaves or 0)
        + (total_unpaid_leaves or 0)
        + (total_holidays or 0)
    )

    if total_paid_days > total_days:
        total_paid_days = total_days

    return {"total_paid_days": total_paid_days}




# def get_detailed_paid_days(employee: str, filters: Filters, holidays: List) -> Dict:
#     """
#     Returns:
#       { "total_paid_days": <float> }

#     Notes:
#       - half-days are handled inside get_total_paid_days()
#       - unmarked days (no submitted attendance & not a holiday) are NOT counted as paid
#       - Holidays/WO are counted only from employee's DOJ if DOJ falls inside the selected month
#     """
#     # get summary & attendance days
#     summary, attendance_days = get_total_paid_days(employee, filters)

#     # if no summary or all zero -> caller will skip
#     if not summary or not any((v for v in summary.values() if v)):
#         return {}

#     # defensive extraction
#     total_present = summary.get("total_present", 0) if isinstance(summary, dict) else getattr(summary, "total_present", 0)
#     total_paid_leaves = summary.get("total_paid_leaves", 0) if isinstance(summary, dict) else getattr(summary, "total_paid_leaves", 0)
#     total_unpaid_leaves = summary.get("total_unpaid_leaves", 0) if isinstance(summary, dict) else getattr(summary, "total_unpaid_leaves", 0)

#     total_days = get_total_days_in_month(filters)

#     # Determine DOJ and start day for counting holidays/week-offs
#     doj = frappe.get_cached_value("Employee", employee, "date_of_joining")
#     start_day = 1  # default: count holidays from day 1 of month

#     if doj:
#         doj_date = getdate(doj)
#         # If DOJ is after the month end -> employee not present in this month
#         month_end_day = total_days
#         month_end = getdate(f"{cstr(filters.year)}-{cstr(filters.month)}-{month_end_day}")
#         if doj_date > month_end:
#             # employee joined after this month
#             return {"total_paid_days": 0}

#         # If DOJ is within the same month/year, start counting from DOJ day
#         if doj_date.year == cint(filters.year) and doj_date.month == cint(filters.month):
#             start_day = doj_date.day
#         else:
#             # DOJ before this month -> start from day 1 (already default)
#             start_day = 1

#     # Count holidays/weekly offs only from start_day to end of month
#     total_holidays = 0
#     total_unmarked_days = 0
#     for day in range(start_day, total_days + 1):
#         # if attendance submitted for that day, skip (we only consider days without attendance)
#         if day in attendance_days:
#             continue

#         status = get_holiday_status(day, holidays)
#         if status in ["Weekly Off", "Holiday"]:
#             total_holidays += 1
#         elif not status:
#             total_unmarked_days += 1

#     # IMPORTANT: per your requirement, unmarked days are NOT counted as paid days
#     total_paid_days = (
#         (total_present or 0)
#         + (total_paid_leaves or 0)
#         + (total_unpaid_leaves or 0)
#         + (total_holidays or 0)
#     )

#     if total_paid_days <= total_days:
#         return {"total_paid_days": total_paid_days}
#     elif total_paid_days > total_days:
#         return {"total_paid_days": total_days}


# def get_detailed_paid_days(
#     employee: str, filters: Filters, holidays: List
# ) -> Dict:
#     """
#     Returns:
#       { "total_paid_days": <float> }
#     Notes:
#       - half-days are already handled inside get_total_paid_days()
#       - unmarked days (no submitted attendance & not a holiday) are NOT counted as paid
#     """
#     summary, attendance_days = get_total_paid_days(employee, filters)

#     # if no summary or all zero -> return empty so caller can skip
#     if not summary or not any((v for v in summary.values() if v)):
#         return {}

#     # be defensive: summary may be dict-like; use .get to avoid None
#     total_present = summary.get("total_present", 0) if isinstance(summary, dict) else getattr(summary, "total_present", 0)
#     total_paid_leaves = summary.get("total_paid_leaves", 0) if isinstance(summary, dict) else getattr(summary, "total_paid_leaves", 0)
#     total_unpaid_leaves = summary.get("total_unpaid_leaves", 0) if isinstance(summary, dict) else getattr(summary, "total_unpaid_leaves", 0)

#     total_days = get_total_days_in_month(filters)
#     total_holidays = total_unmarked_days = 0

#     for day in range(1, total_days + 1):
#         if day in attendance_days:
#             continue

#         status = get_holiday_status(day, holidays)
#         if status in ["Weekly Off", "Holiday"]:
#             total_holidays += 1
#         elif not status:
#             total_unmarked_days += 1

#     # DEBUG prints (optional)
#     # print("Holidays:", total_holidays)
#     # print("Unmarked days (not counted as paid):", total_unmarked_days)
#     # print("Present:", total_present, "Paid Leaves:", total_paid_leaves, "Unpaid Leaves:", total_unpaid_leaves)

#     # IMPORTANT: do NOT add total_unmarked_days to paid days.
#     total_paid_days = (
#         (total_present or 0)
#         + (total_paid_leaves or 0)
#         # + (total_unpaid_leaves or 0)
#         + (total_holidays or 0)
#     )

#     return {
#         "total_paid_days": total_paid_days,
#         # if you want to return helper values, you can also include them:
#         # "total_present": total_present,
#         # "total_paid_leaves": total_paid_leaves,
#         # "total_unpaid_leaves": total_unpaid_leaves,
#         # "total_holidays": total_holidays,
#         # "total_unmarked_days": total_unmarked_days
#     }


# def get_detailed_paid_days(
# 	employee: str, filters: Filters, holidays: List
# ) -> Dict:
# 	"""Returns dict of attendance status for employee like
# 	{'total_present': 1.5, 'total_leaves': 0.5, 'total_absent': 13.5, 'total_holidays': 8, 'unmarked_days': 5}
# 	"""
# 	summary, attendance_days = get_total_paid_days(employee, filters)
# 	if not any(summary.values()):
# 		return {}	

# 	total_days = get_total_days_in_month(filters)
# 	total_holidays = total_unmarked_days = 0

# 	for day in range(1, total_days + 1):
# 		if day in attendance_days:
# 			continue

# 		status = get_holiday_status(day, holidays)
# 		if status in ["Weekly Off", "Holiday"]:
# 			total_holidays += 1
# 		elif not status:
# 			total_unmarked_days += 1
	
# 	print("hildays count:--------->",total_holidays)

# 	print("Total Present:--->",summary.total_present)
# 	print("Total Paid Leaves:--->",summary.total_paid_leaves)
# 	print("Total UnPaid Leaves:--->",summary.total_unpaid_leaves)
# 	print("Total Paid Half Leaves:--->",summary.total_paid_half_days)
# 	print("Total UnPaid Half Leaves:--->",summary.total_unpaid_half_days)
# 	print("Total Unmarked Days:--->",total_unmarked_days)
	



# 	return {
# 		"total_paid_days": (
# 		(summary.total_present or 0)
# 		+ (summary.total_paid_leaves or 0)
# 		+ (summary.total_unpaid_leaves or 0)
# 		+ (total_holidays or 0)
# 		+ (total_unmarked_days or 0)
# )

# 		# "total_paid_days":summary.total_present + total_holidays + summary.total_paid_leaves + summary.total_unpaid_leaves + summary.total_paid_half_days + summary.total_unpaid_half_days + total_unmarked_days		
# 	}

def get_total_paid_days(employee: str, filters) -> Tuple[Dict, List]:
    Attendance = frappe.qb.DocType("Attendance")

    # My Simplified Present logic (which includes Half Day)
    present_case = (
        frappe.qb.terms.Case()
        .when((Attendance.status == "Present") | (Attendance.status == "Work From Home"), 1)
        .when((Attendance.status == "Half Day") & (Attendance.half_day_status == "Present") & (Attendance.leave_type != "Leave Without Pay"), 1)
        .when((Attendance.status == "Half Day") & (Attendance.half_day_status == "Absent") | ((Attendance.status == "Half Day") & (Attendance.half_day_status == "Present") & (Attendance.leave_type == "Leave Without Pay")), 0.5)
        .else_(0)
    )
    sum_present = Sum(present_case).as_("total_present")

    # Absent
    absent_case = frappe.qb.terms.Case().when(Attendance.status == "Absent", 1).else_(0)
    sum_absent = Sum(absent_case).as_("total_absent")

    # Paid and unpaid leave logic
    paid_leave_case = frappe.qb.terms.Case().else_(0)
    unpaid_leave_case = frappe.qb.terms.Case().else_(0)

    # Get paid leave types (is_lwp = 0 means paid)
    leave_types = frappe.get_all("Leave Type", filters={"is_lwp": 0})
    for leave_type in leave_types:
        paid_leave_case = paid_leave_case.when(
            (Attendance.leave_type == leave_type.name) & (Attendance.status == "On Leave"), 1
        ).else_(0)
        unpaid_leave_case = unpaid_leave_case.when(
            (Attendance.leave_type == leave_type.name) & (Attendance.status == "On Leave"), 0
        ).else_(0)

    sum_paid_leave = Sum(paid_leave_case).as_("total_paid_leaves")
    sum_unpaid_leave = Sum(unpaid_leave_case).as_("total_unpaid_leaves")

    #Final summary query
    summary = (
        frappe.qb.from_(Attendance)
        .select(
            sum_present,
            sum_absent,
            sum_paid_leave,
            sum_unpaid_leave
        )
        .where(
            (Attendance.docstatus == 1)
            & (Attendance.employee == employee)
            & (Attendance.company == filters.company)
            & (Extract("month", Attendance.attendance_date) == filters.month)
            & (Extract("year", Attendance.attendance_date) == filters.year)
        )
    ).run(as_dict=True)

    # Distinct attendance days in the month
    days = (
        frappe.qb.from_(Attendance)
        .select(Extract("day", Attendance.attendance_date).as_("day_of_month"))
        .distinct()
        .where(
            (Attendance.docstatus == 1)
            & (Attendance.employee == employee)
            & (Attendance.company == filters.company)
            & (Extract("month", Attendance.attendance_date) == filters.month)
            & (Extract("year", Attendance.attendance_date) == filters.year)
        )
    ).run(pluck=True)

    return summary[0], days

# def get_total_paid_days(employee: str, filters: Filters) -> Tuple[Dict, List]:
#     Attendance = frappe.qb.DocType("Attendance")

#     present_case = (
#         frappe.qb.terms.Case()
#         .when(((Attendance.status == "Present") | (Attendance.status == "Work From Home") | (Attendance.status == "Half Day" and Attendance.half_day_status=="Present")) , 1)
#         .else_(0)
#     )
#     sum_present = Sum(present_case).as_("total_present")

#     absent_case = frappe.qb.terms.Case().when(Attendance.status == "Absent", 1).else_(0)
#     sum_absent = Sum(absent_case).as_("total_absent")

#     paid_leave_case = frappe.qb.terms.Case().else_(0)
#     unpaid_leave_case = frappe.qb.terms.Case().else_(0)
#     paid_half_day_case = frappe.qb.terms.Case().else_(0)
#     unpaid_half_day_case = frappe.qb.terms.Case().else_(0)
    

#     leave_types = frappe.get_all("Leave Type", filters={"is_lwp": 0})
#     for leave_type in leave_types:
#         paid_leave_case = paid_leave_case.when((Attendance.leave_type == leave_type.name) & (Attendance.status == "On Leave"), 1).else_(0)
#         unpaid_leave_case = unpaid_leave_case.when((Attendance.leave_type != leave_type.name) & (Attendance.status == "On_leave"), 0.5).else_(0)
	
#         paid_half_day_case = paid_half_day_case.when((Attendance.status == "Half Day")&(Attendance.leave_type == leave_type.name),0.5).else_(0)
#         unpaid_half_day_case = frappe.qb.terms.Case().when(
# 				(Attendance.status == "Half Day") & 
# 				~((Attendance.leave_type == "Earned Leave") | 
# 				(Attendance.leave_type == "Special Leave") | 
# 				(Attendance.leave_type == "Sick Leave") | 
# 				(Attendance.leave_type == "Casual Leave") | 
# 				(Attendance.leave_type == "Maternity Leave") | 
# 				(Attendance.leave_type == "Paternity Leave") | 
# 				(Attendance.leave_type == "Compensatory Leave") | 
# 				(Attendance.leave_type == "Mutual Leave")), 
# 				0.5
# 				).else_(0)
#     sum_paid_leave = Sum(paid_leave_case).as_("total_paid_leaves")
#     sum_unpaid_leave = Sum(unpaid_leave_case).as_("total_unpaid_leaves")
#     sum_paid_half_day = Sum(paid_half_day_case).as_("total_paid_half_days")
#     sum_unpaid_half_day = Sum(unpaid_half_day_case).as_("total_unpaid_half_days")

#     summary = (
#         frappe.qb.from_(Attendance)
#         .select(
#             sum_present,
#             sum_absent,
#             sum_paid_leave,
# 			sum_unpaid_leave,
#             sum_paid_half_day,
# 			sum_unpaid_half_day
#         )
#         .where(
#             (Attendance.docstatus == 1)
#             & (Attendance.employee == employee)
#             & (Attendance.company == filters.company)
#             & (Extract("month", Attendance.attendance_date) == filters.month)
#             & (Extract("year", Attendance.attendance_date) == filters.year)
#         )
#     ).run(as_dict=True)

#     days = (
#         frappe.qb.from_(Attendance)
#         .select(Extract("day", Attendance.attendance_date).as_("day_of_month"))
#         .distinct()
#         .where(
#             (Attendance.docstatus == 1)
#             & (Attendance.employee == employee)
#             & (Attendance.company == filters.company)
#             & (Extract("month", Attendance.attendance_date) == filters.month)
#             & (Extract("year", Attendance.attendance_date) == filters.year)
#         )
#     ).run(pluck=True)
#     return summary[0], days