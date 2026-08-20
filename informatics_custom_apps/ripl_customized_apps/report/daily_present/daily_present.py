import frappe
from datetime import timedelta
import datetime as dt
from frappe.utils.data import get_time, getdate


def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data


def get_columns(filters):
    columns = [
        # {
        #     "fieldname": "department_name",
        #     "label": "Department",
        #     "fieldtype": "Data",
        #     "width": 170
        # },
        {
            "fieldname": "emp_code",
            "label": "Employee",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 130
        },
        {
            "fieldname": "emp_name",
            "label": "Employee Name",
            "fieldtype": "Data",
            "width": 170
        },
        {
            "fieldname": "emp_designation",
            "label": "Designation",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "status",
            "label": "Status",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "shift",
            "label": "Shift",
            "fieldtype": "Data",
            "width": 200
        },
        # {
        #     "fieldname": "attendance_device_id",
        #     "label": "Biometric ID",
        #     "fieldtype": "Data",
        #     "width": 120
        # },
        {
            "fieldname": "checkin_time",
            "label": "Checkin Time",
            "fieldtype": "Datetime",
            "width": 170
        },
        {
            "fieldname": "remarks",
            "label": "Remarks",
            "fieldtype": "Data",
            "width": 170
        }
    ]

    return columns


def get_data(filters):
    worklocation = filters.get("worklocation")
    report_date = filters.get("date")

    employees = frappe.db.sql("""
        SELECT
            e.name AS emp_code,
            e.employee_name AS emp_name,
            e.payroll_cost_center,
            e.f_h_name AS emp_father,
            e.designation AS emp_designation,
            e.worklocation,
            e.department,
            e.default_shift,
            e.attendance_device_id,
            e.holiday_list
        FROM `tabEmployee` e
        WHERE
            e.status = 'Active'
            AND e.worklocation = %(worklocation)s
            AND (
                NOT(
                    e.worklocation = 'Head Office'
                    AND e.branch = 'Head Office-Residence'
                )
                OR EXISTS (
                    SELECT 1
                    FROM `tabEmployee Checkin` ec
                    WHERE ec.employee = e.name
                    AND DATE(ec.time) = %(date)s
                )
            )
        ORDER BY e.employee_name
    """, {"worklocation": worklocation, "date": report_date}, as_dict=True)

    attendance_map = {}
    if employees:
        emp_codes = [e.emp_code for e in employees]
        attendance_records = frappe.db.sql("""
            SELECT
                employee,
                status,
                leave_application,
                attendance_request,
                shift
            FROM `tabAttendance`
            WHERE
                employee IN %(employees)s
                AND attendance_date = %(date)s
                AND docstatus = 1
            ORDER BY creation DESC
        """, {"employees": emp_codes, "date": report_date}, as_dict=True)

        for att in attendance_records:
            if att.employee not in attendance_map:
                attendance_map[att.employee] = att

    # 3. Fetch all checkins for these employees on the date in one go
    checkin_map = {}
    if employees:
        all_checkins = frappe.db.sql("""
            SELECT
                ec.employee AS emp_code,
                ec.log_type,
                ec.custom_work_location,
                ec.custom_actual_punch_time AS actual_time,
                ec.time AS system_time,
                ec.shift
            FROM `tabEmployee Checkin` ec
            WHERE
                ec.employee IN %(employees)s
                AND DATE(ec.time) = %(date)s
            ORDER BY ec.time ASC
        """, {"employees": emp_codes, "date": report_date}, as_dict=True)

        for checkin in all_checkins:
            checkin_map.setdefault(checkin.emp_code, []).append(checkin)

    # 4. Build holiday map for all distinct holiday lists
    holiday_lists = set(e.holiday_list for e in employees if e.holiday_list)
    holiday_map = {}
    if holiday_lists:
        holidays = frappe.db.sql("""
            SELECT
                parent,
                holiday_date,
                weekly_off
            FROM `tabHoliday`
            WHERE
                holiday_date = %(date)s
                AND parent IN %(holiday_lists)s
        """, {"date": report_date, "holiday_lists": list(holiday_lists)}, as_dict=True)

        for h in holidays:
            holiday_map[h.parent] = h

    # 5. Process each employee
    data = []

    for employee in employees:
        emp_code = employee.emp_code
        attendance = attendance_map.get(emp_code)
        checkins = checkin_map.get(emp_code, [])

        # Determine checkin and checkout times
        first_checkin = None
        last_checkout = None

        if checkins:
            # Use actual punch time if available, otherwise fall back to system time
            first_checkin = checkins[0].actual_time or checkins[0].system_time
            if len(checkins) > 1:
                last_checkout = checkins[-1].actual_time or checkins[-1].system_time
            # If only one checkin, checkout stays blank

        # Determine attendance status and related fields
        attendance_status = ""
        leave_application = ""
        attendance_request_id = ""
        status = ""
        remarks = ""
        shift = ""
        indicator = ""

        if attendance:
            attendance_status = attendance.status  # Present, Absent, On Leave, Half Day, etc.
            leave_application = attendance.leave_application or ""
            attendance_request_id = attendance.attendance_request or ""
            shift = attendance.shift or ""

        # Determine shift: attendance shift > shift assignment > default shift
        assigned_shift = get_assigned_shift(emp_code, report_date)
        if not shift:
            shift = assigned_shift or employee.default_shift or ""

        # Determine status and remarks based on attendance + checkin data
        if attendance and attendance.status == "On Leave":
            status = "On Leave"
            attendance_status = "On Leave"
            remarks = ""
            indicator = "blue"

        elif attendance and attendance.status == "Present":
            attendance_status = "Present"

            if checkins:
                status, remarks, indicator = _evaluate_checkin_timing(
                    first_checkin, shift or employee.default_shift, report_date
                )
            else:
                # Present via attendance request but no checkin
                status = "Present"
                remarks = "Marked via Attendance Request" if attendance_request_id else ""
                indicator = "green"

        elif attendance and attendance.status == "Half Day":
            attendance_status = "Half Day"

            if checkins:
                status, remarks, indicator = _evaluate_checkin_timing(
                    first_checkin, shift or employee.default_shift, report_date
                )
                remarks = f"Half Day | {remarks}" if remarks else "Half Day"
            else:
                status = "Half Day"
                remarks = ""
                indicator = "orange"

        elif attendance and attendance.status == "Absent":
            attendance_status = "Absent"
            status = "Absent"
            remarks = ""
            indicator = "red"

        else:
            # No attendance record found
            holiday = holiday_map.get(employee.holiday_list)

            if holiday:
                if holiday.weekly_off:
                    attendance_status = "Weekly Off"
                    status = "Weekly Off"
                    indicator = "green"
                else:
                    attendance_status = "Holiday"
                    status = "Holiday"
                    indicator = "green"
            elif checkins:
                # Has checkin but no attendance marked yet
                attendance_status = "Not Marked"
                status_result, remarks_result, indicator = _evaluate_checkin_timing(
                    first_checkin, shift or employee.default_shift, report_date
                )
                status = status_result
                remarks = remarks_result
            else:
                # No attendance, no checkin, no holiday
                attendance_status = "Absent"
                status = "Absent"
                remarks = ""
                indicator = "red"

        data.append({
            "department_name": employee.department,
            "emp_code": emp_code,
            "payroll_cost_center": employee.payroll_cost_center,
            "emp_name": employee.emp_name,
            "emp_father": employee.emp_father,
            "emp_designation": employee.emp_designation,
            "attendance_status": attendance_status,
            "status": status,
            "shift": shift,
            "attendance_device_id": employee.attendance_device_id,
            "checkin_time": first_checkin or "",
            "checkout_time": last_checkout or "",
            "leave_application": leave_application,
            "attendance_request": attendance_request_id,
            "remarks": remarks,
            "indicator": indicator
        })

    # Filter by status if specified
    status_filter = filters.get("status")
    if status_filter:
        data = [row for row in data if row.get("status") == status_filter]

    return data


def _evaluate_checkin_timing(checkin_time, shift_name, report_date):
    """
    Evaluate whether a checkin is on time or late based on shift configuration.

    Special case: For "General Shift-9:30-17:30", even checkin at exactly
    the shift start time (9:30) is considered late.

    Returns:
        tuple: (status, remarks, indicator)
    """
    if not shift_name:
        return ("Present", "On Time", "green")

    try:
        shift_doc = frappe.get_doc("Shift Type", shift_name)
    except frappe.DoesNotExistError:
        return ("Present", "On Time", "green")

    shift_start_time = dt.datetime.combine(
        getdate(report_date),
        get_time(shift_doc.start_time)
    )

    grace_period_minutes = shift_doc.late_entry_grace_period or 0

    # Special case: "General Shift-9:30-17:30" — even 9:30 is late
    is_general_shift = (shift_name == "General Shift-9:30-17:30")

    if is_general_shift:
        # Late if checkin time >= shift start (no grace at all)
        if checkin_time >= shift_start_time:
            late_duration = checkin_time - shift_start_time
            late_minutes = int(late_duration.total_seconds() // 60)
            if late_minutes == 0:
                return ("Late", "Late (checked in at shift start)", "orange")
            else:
                return ("Late", f"Late by {late_minutes} minutes", "orange")
        else:
            return ("Present", "On Time", "green")
    else:
        # Standard logic: late if checkin > shift_start + grace period
        grace_threshold = shift_start_time + timedelta(minutes=grace_period_minutes)

        if checkin_time > grace_threshold:
            late_duration = checkin_time - shift_start_time
            late_minutes = int(late_duration.total_seconds() // 60)
            return ("Late", f"Late by {late_minutes} minutes", "orange")
        else:
            return ("Present", "On Time", "green")


def get_assigned_shift(emp_code, date):
    shift_assign = frappe.get_all(
        "Shift Assignment",
        filters={
            "employee": emp_code,
            "start_date": ("<=", date),
            "end_date": (">=", date)
        },
        fields=["shift_type"],
        order_by="creation desc",
        limit=1
    )

    if shift_assign:
        return shift_assign[0].shift_type

    return None