import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import nowdate, getdate, flt, formatdate

from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on


class zzLeavesAdjustmentTool(Document):

    def before_save(self):
        """Auto-populate and correct current_leave_balance for each row using HRMS get_leave_balance_on."""
        today = nowdate()
        corrected_rows = []
        precision = int(frappe.db.get_single_value("System Settings", "float_precision") or 2)

        for row in self.leaves_data:
            if not row.employee or not row.leave_type:
                continue

            try:
                balance = get_leave_balance_on(
                    employee=row.employee,
                    leave_type=row.leave_type,
                    date=today,
                    to_date=today,
                    consider_all_leaves_in_the_allocation_period=True,
                    for_consumption=False
                )
                actual_balance = flt(balance or 0)
            except Exception:
                actual_balance = flt(0)

            # Format as string so "0" explicitly shows in the Data field
            balance_str = f"{actual_balance:.{precision}f}".rstrip("0").rstrip(".")
            if not balance_str or balance_str == "-":
                balance_str = "0"

            old_balance = row.current_leave_balance or "0"
            if old_balance != balance_str:
                corrected_rows.append(
                    f"Row {row.idx}: {row.employee} / {row.leave_type} — "
                    f"corrected from <b>{old_balance}</b> to <b>{balance_str}</b>"
                )
            row.current_leave_balance = balance_str

        if corrected_rows:
            frappe.msgprint(
                _("Current Leave Balance has been corrected for the following rows:<br><br>{0}").format(
                    "<br>".join(corrected_rows)
                ),
                title=_("Leave Balance Corrected"),
                indicator="orange"
            )

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

        # Filter out rows with 0 or empty additional_leaves on save
        valid_rows = []
        for row in self.leaves_data:
            count = abs(flt(row.additional_leaves or 0))
            if count > 0:
                row.additional_leaves = count
                valid_rows.append(row)

        if not valid_rows and self.leaves_data:
            frappe.throw(_("Cannot save document with 0 additional leaves."))

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
            count = abs(flt(row.additional_leaves or 0))

            # Normalize additional_leaves to positive value on child row and persist it
            row.additional_leaves = count
            row.db_set("additional_leaves", count)

            emp_doc = frappe.get_doc("Employee", emp)

            if emp_doc.company != self.company or emp_doc.branch != self.branch:
                frappe.throw(
                    _("Employee {0} does not belong to Company {1} and Plant {2}").format(
                        emp, self.company, self.branch
                    )
                )

            allocation_name = getattr(row, "leave_allocation", None)
            if not allocation_name:
                allocation_name = frappe.db.get_value(
                    "Leave Allocation",
                    {
                        "employee": emp,
                        "leave_type": leave_type,
                        "from_date": start,
                        "to_date": end,
                        "docstatus": 1
                    },
                    "name"
                )

            if not allocation_name:
                row.status = "Failed"
                row.remarks = "No active Leave Allocation found"
                row.db_set("status", row.status)
                row.db_set("remarks", row.remarks)
                any_partial = True
                failed_count += 1
                continue

            allocation_doc = frappe.get_doc("Leave Allocation", allocation_name)

            max_leaves_allowed = flt(frappe.db.get_value("Leave Type", leave_type, "max_leaves_allowed") or 0)
            if max_leaves_allowed > 0:
                today = nowdate()
                try:
                    current_bal = get_leave_balance_on(
                        employee=emp,
                        leave_type=leave_type,
                        date=today,
                        to_date=today,
                        consider_all_leaves_in_the_allocation_period=True,
                        for_consumption=False
                    )
                    current_bal = flt(current_bal or 0)
                except Exception:
                    current_bal = flt(row.current_leave_balance or 0)

                projected_total = current_bal + count
                if projected_total > max_leaves_allowed:
                    exceeded_by = projected_total - max_leaves_allowed
                    precision = int(frappe.db.get_single_value("System Settings", "float_precision") or 2)
                    exceeded_str = f"{exceeded_by:.{precision}f}".rstrip("0").rstrip(".")
                    max_str = f"{max_leaves_allowed:.{precision}f}".rstrip("0").rstrip(".")
                    cur_str = f"{current_bal:.{precision}f}".rstrip("0").rstrip(".")
                    add_str = f"{count:.{precision}f}".rstrip("0").rstrip(".")

                    row.status = "Failed"
                    row.remarks = f"Exceeds max allowed leaves ({max_str}) by {exceeded_str} leaves (Current: {cur_str}, Additional: {add_str})"
                    row.db_set("status", row.status)
                    row.db_set("remarks", row.remarks)
                    any_partial = True
                    failed_count += 1
                    continue

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
        self.status = "Cancelled"
        self.db_set("status", self.status)

        frappe.enqueue(
            "informatics_custom_apps.ripl_customized_apps.doctype.zzleaves_adjustment_tool.zzleaves_adjustment_tool.process_cancellation",
            docname=self.name,
            queue="long",
            timeout=3000
        )

        # frappe.msgprint(
        #     _("Cancellation for document {0} has been queued in the background.").format(
        #         frappe.bold(self.name)
        #     ),
        #     title=_("Cancellation Enqueued"),
        #     indicator="orange"
        # )


def process_cancellation(docname):
    doc = frappe.get_doc("zzLeaves Adjustment Tool", docname)
    cancelled_count = 0

    for row in doc.leaves_data:
        if not row.employee or not row.leave_allocation:
            continue

        if row.status != "Updated":
            row.db_set("status", "Cancelled")
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
                    "from_date": doc.from_date,
                    "to_date": doc.to_date,
                    "leaves": row.additional_leaves,
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
                frappe.bold(row.additional_leaves or 0),
                frappe.bold(doc.name),
                frappe.bold(formatdate(nowdate()))
            )
            alloc_doc.add_comment(comment_type="Info", text=cancel_text)

        row.db_set("status", "Cancelled")
        row.db_set("remarks", "Allocation reversed on cancellation")


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
    today = frappe.utils.nowdate()

    for alloc in allocations:
        key = (alloc.employee, alloc.leave_type)
        if key not in seen:
            seen.add(key)

            # Fetch current leave balance using HRMS core function
            try:
                balance = get_leave_balance_on(
                    employee=alloc.employee,
                    leave_type=alloc.leave_type,
                    date=today,
                    to_date=today,
                    consider_all_leaves_in_the_allocation_period=True,
                    for_consumption=False
                )
                current_leave_balance = frappe.utils.flt(balance or 0)
            except Exception:
                current_leave_balance = 0

            # Format as string so "0" explicitly shows in the grid (Data field, not Float)
            precision = frappe.db.get_single_value("System Settings", "float_precision") or 2
            balance_str = f"{current_leave_balance:.{int(precision)}f}".rstrip("0").rstrip(".")
            if not balance_str or balance_str == "-":
                balance_str = "0"

            result.append({
                "employee": alloc.employee,
                "employee_name": emp_name_map.get(alloc.employee),
                "leave_type": alloc.leave_type,
                "leave_allocation": alloc.name,
                "current_leave_balance": balance_str
            })

    return result