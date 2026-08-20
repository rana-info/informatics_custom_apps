import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import nowdate, getdate, flt, formatdate

from hrms.hr.doctype.leave_ledger_entry.leave_ledger_entry import (
    create_leave_ledger_entry
)


class zzLeavesAdjustmentTool(Document):

    def validate(self):
        if self.docstatus == 0:
            if self.amended_from or self.status == "Cancelled":
                self.status = "Draft"

            for row in self.leaves_data:
                if self.amended_from or row.status == "Cancelled":
                    row.status = "Draft"
                    row.remarks = None
                    row.leave_ledger_entry = None
                    row.comment = None

        # Filter out rows with 0 or empty leave_count on save
        valid_rows = []
        for row in self.leaves_data:
            count = abs(flt(row.leave_count or 0))
            if count > 0:
                row.leave_count = count
                valid_rows.append(row)

        if not valid_rows and self.leaves_data:
            frappe.throw(_("Cannot save document with 0 leave count. Please enter a leave count greater than 0 for at least one employee."))

        self.leaves_data = valid_rows

        # Validate that all rows have a Leave Allocation linked
        missing_alloc = []
        for row in self.leaves_data:
            if not getattr(row, "leave_allocation", None):
                missing_alloc.append(
                    f"Row {row.idx}: {row.employee} ({row.leave_type})"
                )

        if missing_alloc:
            frappe.throw(
                _("Leave Allocation is missing for the following rows. Please use 'Get Employees' to auto-populate data, or ensure your CSV file includes the Leave Allocation ID column:<br><br>{0}").format(
                    "<br>".join(missing_alloc)
                ),
                title=_("Missing Leave Allocation")
            )

    def on_submit(self):

        any_partial = False
        updated_count = 0
        failed_count = 0

        for row in self.leaves_data:

            emp = row.employee
            leave_type = row.leave_type
            start = getattr(row, "from_date", None) or self.from_date
            end = getattr(row, "to_date", None) or self.to_date
            count = abs(flt(row.leave_count or 0))

            # Normalize leave_count to positive value on child row and persist it
            row.leave_count = count
            row.db_set("leave_count", count)

            emp_doc = frappe.get_doc("Employee", emp)

            if emp_doc.company != self.company or emp_doc.branch != self.branch:
                frappe.throw(
                    _("Employee {0} does not belong to Company {1} and Plant {2}").format(
                        emp, self.company, self.branch
                    )
                )

            allocation_name = getattr(row, "leave_allocation", None)

            if not allocation_name:
                row.status = "Failed"
                row.remarks = "No Leave Allocation linked — cannot process"
                row.db_set("status", row.status)
                row.db_set("remarks", row.remarks)
                any_partial = True
                failed_count += 1
                continue

            allocation_doc = frappe.get_doc("Leave Allocation", allocation_name)

            ledger_dict = dict(
                doctype="Leave Ledger Entry",
                employee=allocation_doc.employee,
                employee_name=allocation_doc.employee_name,
                leave_type=allocation_doc.leave_type,
                transaction_type=allocation_doc.doctype,
                transaction_name=allocation_doc.name,
                is_carry_forward=1,
                is_expired=0,
                is_lwp=0,
                leaves=count,
                from_date=self.from_date,
                to_date=self.to_date,
                company=self.company
            )

            lle_doc = frappe.get_doc(ledger_dict)
            lle_doc.flags.ignore_permissions = 1
            lle_doc.submit()

            text = _("{0} leaves were allocated via Leave Adjustment Tool on {1}").format(
                frappe.bold(count),
                frappe.bold(formatdate(nowdate()))
            )

            comment_doc = allocation_doc.add_comment(comment_type="Info", text=text)

            row.status = "Updated"
            row.remarks = f"{count} leaves allocated successfully"
            row.leave_ledger_entry = lle_doc.name
            if comment_doc:
                row.comment = comment_doc.name
                row.db_set("comment", comment_doc.name)
            row.db_set("status", row.status)
            row.db_set("remarks", row.remarks)
            row.db_set("leave_ledger_entry", lle_doc.name)
            updated_count += 1

        self.status = "Partially Updated" if any_partial else "Updated"
        self.db_set("status", self.status)

        frappe.msgprint(
            _("Bulk Leave Processing Completed")
            + "<br><br>"
            + _("Updated: {0}").format(frappe.bold(updated_count))
            + "<br>"
            + _("Failed: {0}").format(frappe.bold(failed_count)),
            title=_("Processing Summary"),
            indicator="green" if failed_count == 0 else "orange"
        )

    def on_cancel(self):
        cancelled_count = 0
        for row in self.leaves_data:
            if not row.employee or not row.leave_allocation:
                continue

            entries_to_delete = []

            lle_name = getattr(row, "leave_ledger_entry", None)
            if lle_name and frappe.db.exists("Leave Ledger Entry", lle_name):
                entries_to_delete.append(lle_name)
            else:
                entries_to_delete = frappe.get_all(
                    "Leave Ledger Entry",
                    filters={
                        "employee": row.employee,
                        "leave_type": row.leave_type,
                        "transaction_type": "Leave Allocation",
                        "transaction_name": row.leave_allocation,
                        "is_carry_forward": 1,
                        "is_expired": 0,
                        "from_date": self.from_date,
                        "to_date": self.to_date,
                        "leaves": row.leave_count,
                        "docstatus": 1
                    },
                    pluck="name"
                )

            for entry_name in entries_to_delete:
                frappe.db.set_value("Leave Ledger Entry", entry_name, "docstatus", 2)
                frappe.delete_doc("Leave Ledger Entry", entry_name, force=1, ignore_permissions=True)
                cancelled_count += 1

            # Post a reversal comment on the linked Leave Allocation document
            if frappe.db.exists("Leave Allocation", row.leave_allocation):
                alloc_doc = frappe.get_doc("Leave Allocation", row.leave_allocation)
                cancel_text = _("{0} leaves were reversed because Leave Adjustment Tool {1} was cancelled on {2}").format(
                    frappe.bold(row.leave_count or 0),
                    frappe.bold(self.name),
                    frappe.bold(formatdate(nowdate()))
                )
                alloc_doc.add_comment(comment_type="Info", text=cancel_text)

            row.db_set("status", "Cancelled")
            row.db_set("remarks", "Allocation reversed on cancellation")

        self.status = "Cancelled"
        self.db_set("status", self.status)

        # frappe.msgprint(
        #     _("Document cancelled successfully. Reversed/Deleted {0} Leave Ledger Entry record(s).").format(
        #         frappe.bold(cancelled_count)
        #     ),
        #     title=_("Cancellation Summary"),
        #     indicator="orange"
        # )


@frappe.whitelist()
def get_employee_leave_data(company, branch, leave_period=None, from_date=None, to_date=None, selected_employees=None):
    if isinstance(selected_employees, str):
        import json
        try:
            selected_employees = json.loads(selected_employees)
        except Exception:
            selected_employees = [e.strip() for e in selected_employees.split(",") if e.strip()]

    if not from_date or not to_date:
        if leave_period:
            lp = frappe.db.get_value("Leave Period", leave_period, ["from_date", "to_date"], as_dict=True)
            if lp:
                from_date = from_date or lp.get("from_date")
                to_date = to_date or lp.get("to_date")

    filters = {
        "company": company,
        "branch": branch,
        "status": "Active"
    }
    if selected_employees:
        filters["name"] = ["in", selected_employees]

    employees = frappe.get_all("Employee", filters=filters, fields=["name", "employee_name"])

    if not employees:
        return []

    emp_name_map = {e.name: e.employee_name for e in employees}
    emp_ids = list(emp_name_map.keys())

    target_leave_types = ["Earned Leave", "Sick Leave-Sugar"]

    alloc_filters = {
        "employee": ["in", emp_ids],
        "leave_type": ["in", target_leave_types],
        "docstatus": 1
    }

    if from_date and to_date:
        alloc_filters["from_date"] = ["<=", to_date]
        alloc_filters["to_date"] = [">=", from_date]

    allocations = frappe.get_all(
        "Leave Allocation",
        filters=alloc_filters,
        fields=["name", "employee", "leave_type", "from_date", "to_date", "creation"],
        order_by="from_date desc, creation desc"
    )

    seen = set()
    result = []
    for alloc in allocations:
        key = (alloc.employee, alloc.leave_type)
        if key not in seen:
            seen.add(key)
            result.append({
                "employee": alloc.employee,
                "employee_name": emp_name_map.get(alloc.employee),
                "leave_type": alloc.leave_type,
                "leave_allocation": alloc.name
            })

    return result