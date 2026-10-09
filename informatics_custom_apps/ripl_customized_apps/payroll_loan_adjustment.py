import json

import frappe
from frappe import _
from frappe.utils import flt, getdate, now_datetime

from .payroll_loan_candidates import (
	_build_candidates,
	_check_hr_manager,
	_currency_precision,
	_get_due_loan_schedules,
	_get_payroll_entry,
	_get_prior_adjustment_log,
	_get_threshold,
)


def _get_unpaid_accruals(loan, posting_date):
	from lending.loan_management.doctype.loan_repayment.loan_repayment import get_accrued_interest_entries

	entries = get_accrued_interest_entries(loan, posting_date)
	return [frappe.get_doc("Loan Interest Accrual", entry.name) for entry in entries]


def _submitted_repayment_for_accrual(accrual_name):
	links = frappe.get_all(
		"Loan Repayment Detail",
		filters={"loan_interest_accrual": accrual_name},
		fields=["parent"],
	)
	for link in links:
		if frappe.db.get_value("Loan Repayment", link.parent, "docstatus") == 1:
			return link.parent
	return None


def _validate_adjustment(employee, candidate, item, precision):
	choice = item.get("schedule_choice")
	if choice not in ("Yes", "No"):
		frappe.throw(_("Select Yes or No for the repayment schedule choice for {0}.").format(employee))
	amount = flt(item.get("hr_amount"), precision)
	if amount < 0 or amount > candidate["scheduled_amount"]:
		frappe.throw(_("HR amount for {0} must be between zero and the scheduled amount.").format(employee))
	if flt(candidate["gross_pay"] - candidate["other_deductions"] - amount, precision) < 0:
		frappe.throw(_("HR amount for {0} would make net salary negative.").format(employee))
	return amount, choice


def _split_repayment_amount(allocation, hr_amount, precision):
	interest_amount = min(flt(hr_amount, precision), flt(allocation["interest_amount"], precision))
	principal_amount = flt(hr_amount - interest_amount, precision)
	if principal_amount > flt(allocation["principal_amount"], precision):
		frappe.throw(_("HR amount exceeds the scheduled principal and interest for loan {0}.").format(allocation["loan"]))
	return interest_amount, principal_amount


def _get_loan_repayment_allocations(employee, start_date, end_date, hr_amount, payroll_entry=None):
	precision = _currency_precision()
	rows = _get_due_loan_schedules(employee, start_date, end_date, payroll_entry)
	grouped = {}
	for row in rows:
		if row["loan"] in grouped:
			frappe.throw(
				_("Loan {0} has multiple repayment instalments due in this payroll period.").format(row["loan"])
			)
		grouped[row["loan"]] = row
	allocations = []
	remaining = flt(hr_amount, precision)
	for row in grouped.values():
		amount = min(remaining, row["scheduled_amount"])
		allocations.append({**row, "hr_amount": flt(amount, precision)})
		remaining = flt(remaining - amount, precision)
	return allocations


def _existing_salary_slip(payroll_entry, employee):
	return frappe.db.exists(
		"Salary Slip",
		{
			"employee": employee,
			"start_date": payroll_entry.start_date,
			"end_date": payroll_entry.end_date,
			"docstatus": ("!=", 2),
		},
	)


def _get_loan_accounting_dimensions(loan_doc):
	from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_accounting_dimensions

	employee = None
	dimensions = {}
	for fieldname in get_accounting_dimensions():
		value = loan_doc.get(fieldname)
		if not value:
			if employee is None:
				employee = frappe.get_cached_doc("Employee", loan_doc.applicant)
			value = employee.get(fieldname)
		if value:
			dimensions[fieldname] = value
	return dimensions


def _schedule_snapshot(schedule):
	row_fields = (
		"name",
		"payment_date",
		"number_of_days",
		"principal_amount",
		"interest_amount",
		"total_payment",
		"balance_loan_amount",
		"is_accrued",
	)
	return json.dumps(
		{
			"monthly_repayment_amount": schedule.monthly_repayment_amount,
			"repayment_periods": schedule.repayment_periods,
			"repayment_schedule": [
				{
					field: str(getdate(row.get(field))) if field == "payment_date" else row.get(field)
					for field in row_fields
					if row.get(field) is not None
				}
				for row in schedule.repayment_schedule
			],
		}
	)


def _restore_schedule_snapshot(schedule, snapshot, save=True):
	if isinstance(snapshot, str):
		snapshot = json.loads(snapshot)
	schedule.monthly_repayment_amount = snapshot["monthly_repayment_amount"]
	schedule.repayment_periods = snapshot["repayment_periods"]
	schedule.set("repayment_schedule", [])
	for row in snapshot["repayment_schedule"]:
		schedule.append("repayment_schedule", row)
	schedule.flags.ignore_validate = True
	schedule.flags.ignore_validate_update_after_submit = True
	if save:
		schedule.save(ignore_permissions=True)


def _rebuild_legacy_schedule_baseline(schedule, loan_doc):
	def row_as_dict(row):
		as_dict = getattr(row, "as_dict", None)
		return as_dict() if callable(as_dict) else dict(row)

	rows_by_date = {
		str(row.payment_date): frappe._dict(row_as_dict(row)) for row in schedule.repayment_schedule
	}
	schedule.monthly_repayment_amount = loan_doc.monthly_repayment_amount
	schedule.set("repayment_schedule", [])
	schedule.make_repayment_schedule()
	schedule.set_repayment_period()
	regenerated_rows = [frappe._dict(row_as_dict(row)) for row in schedule.repayment_schedule]
	schedule.set("repayment_schedule", [])
	for row in regenerated_rows:
		previous_row = rows_by_date.get(str(row.payment_date))
		if previous_row:
			row.name = previous_row.name
			row.is_accrued = previous_row.is_accrued
		schedule.append("repayment_schedule", row)
	return _schedule_snapshot(schedule)


def _recalculate_schedule(schedule, current_row, principal_paid, interest_paid, increase_schedule):
	from lending.loan_management.doctype.loan_repayment_schedule.loan_repayment_schedule import (
		add_single_month,
	)

	precision = _currency_precision()
	current_date = getdate(current_row.payment_date)
	future_rows = [row for row in schedule.repayment_schedule if getdate(row.payment_date) > current_date]

	scheduled_principal = flt(current_row.principal_amount, precision)
	outstanding_after_month = flt(
		current_row.balance_loan_amount + scheduled_principal - flt(principal_paid, precision), precision
	)
	current_row.principal_amount = flt(principal_paid, precision)
	current_row.interest_amount = flt(interest_paid, precision)
	current_row.total_payment = flt(principal_paid + interest_paid, precision)
	current_row.balance_loan_amount = outstanding_after_month

	loan_product = frappe.get_cached_doc("Loan Product", schedule.loan_product)
	if increase_schedule:
		balance = outstanding_after_month
		last_payment_date = schedule.repayment_schedule[-1].payment_date
		installment_amount = flt(schedule.monthly_repayment_amount, precision)
		if installment_amount <= 0:
			frappe.throw(_("Loan {0} has no valid monthly repayment amount.").format(schedule.loan))
		for row in future_rows:
			interest, principal, balance, total, days = schedule.get_amounts(
				row.payment_date,
				balance,
				loan_product.repayment_schedule_type,
				loan_product.repayment_date_on,
				0,
			)
			row.principal_amount = principal
			row.interest_amount = interest
			row.total_payment = total
			row.balance_loan_amount = balance
			row.number_of_days = days
			last_payment_date = row.payment_date
		while flt(balance, precision) > 0:
			payment_date = add_single_month(last_payment_date)
			interest, principal, balance, total, days = schedule.get_amounts(
				payment_date,
				balance,
				loan_product.repayment_schedule_type,
				loan_product.repayment_date_on,
				0,
			)
			if principal <= 0:
				frappe.throw(_("Loan {0} repayment amount does not reduce its outstanding balance.").format(schedule.loan))
			if balance < flt(10 ** -precision, precision):
				principal = flt(principal + balance, precision)
				balance = 0
				total = flt(principal + interest, precision)
			schedule.append(
				"repayment_schedule",
				{
					"payment_date": payment_date,
					"principal_amount": principal,
					"interest_amount": interest,
					"total_payment": total,
					"balance_loan_amount": balance,
					"number_of_days": days,
				},
			)
			last_payment_date = payment_date
			if len(schedule.repayment_schedule) > 1200:
				frappe.throw(_("Unable to extend repayment schedule for loan {0}.").format(schedule.loan))
	else:
		installment_count = len(future_rows)
		if not installment_count:
			frappe.throw(_("Loan {0} has no remaining instalments to recalculate.").format(schedule.loan))
		installment_amount = flt(outstanding_after_month / installment_count, precision)
		schedule.monthly_repayment_amount = installment_amount
		balance = outstanding_after_month
		for row in future_rows:
			interest, principal, balance, total, days = schedule.get_amounts(
				row.payment_date,
				balance,
				loan_product.repayment_schedule_type,
				loan_product.repayment_date_on,
				0,
			)
			row.principal_amount = principal
			row.interest_amount = interest
			row.total_payment = total
			row.balance_loan_amount = balance
			row.number_of_days = days
		last_row = future_rows[-1]
		if balance > 0:
			last_row.principal_amount = flt(last_row.principal_amount + balance, precision)
			last_row.balance_loan_amount = 0
			last_row.total_payment = flt(last_row.principal_amount + last_row.interest_amount, precision)

	schedule.repayment_periods = len(schedule.repayment_schedule)
	schedule.flags.ignore_validate = True
	schedule.flags.ignore_validate_update_after_submit = True
	schedule.save(ignore_permissions=True)


def _make_replacement_accrual(
	loan_doc, schedule_row, posting_date, principal_amount, interest_amount, old_accruals, accounting_dimensions=None
):
	if not principal_amount and not interest_amount:
		return None

	from lending.loan_management.doctype.loan_repayment.loan_repayment import get_pending_principal_amount

	precision = _currency_precision()
	accrual = frappe.new_doc("Loan Interest Accrual")
	accrual.loan = loan_doc.name
	accrual.applicant_type = loan_doc.applicant_type
	accrual.applicant = loan_doc.applicant
	for fieldname, value in (accounting_dimensions or _get_loan_accounting_dimensions(loan_doc)).items():
		accrual.set(fieldname, value)
	accrual.loan_product = loan_doc.loan_product
	accrual.loan_account = loan_doc.loan_account
	accrual.interest_income_account = loan_doc.interest_income_account
	accrual.is_term_loan = loan_doc.is_term_loan
	accrual.pending_principal_amount = flt(get_pending_principal_amount(loan_doc), precision)
	accrual.interest_amount = flt(interest_amount, precision)
	accrual.payable_principal_amount = flt(principal_amount, precision)
	accrual.total_pending_interest_amount = flt(interest_amount, precision)
	accrual.penalty_amount = 0
	accrual.posting_date = posting_date
	accrual.due_date = schedule_row.payment_date
	accrual.repayment_schedule_name = schedule_row.name
	accrual.accrual_type = "Regular"
	if old_accruals:
		accrual.process_loan_interest_accrual = old_accruals[0].process_loan_interest_accrual
	accrual.flags.ignore_permissions = True
	accrual.insert()
	accrual.submit()
	frappe.db.set_value("Repayment Schedule", schedule_row.name, "is_accrued", 1)
	return accrual


def _apply_one_loan(payroll_entry, allocation, schedule_choice):
	loan_doc = frappe.get_doc("Loan", allocation["loan"])
	schedule = frappe.get_doc("Loan Repayment Schedule", allocation["schedule"])
	prior_adjustment = _get_prior_adjustment_log(payroll_entry.name, loan_doc.applicant, loan_doc.name)
	if prior_adjustment:
		if prior_adjustment.schedule_snapshot:
			_restore_schedule_snapshot(schedule, prior_adjustment.schedule_snapshot, save=False)
		else:
			_rebuild_legacy_schedule_baseline(schedule, loan_doc)
	schedule_row = next(
		row
		for row in schedule.repayment_schedule
		if getdate(row.payment_date) == getdate(allocation["payment_date"])
	)
	schedule_snapshot = _schedule_snapshot(schedule)
	accounting_dimensions = _get_loan_accounting_dimensions(loan_doc)
	old_accruals = _get_unpaid_accruals(loan_doc.name, payroll_entry.end_date)
	for accrual in old_accruals:
		for fieldname, value in accounting_dimensions.items():
			if not accrual.get(fieldname):
				accrual.flags.ignore_validate_update_after_submit = True
				accrual.set(fieldname, value)
		accrual.flags.ignore_permissions = True
		accrual.cancel()
		if accrual.repayment_schedule_name and frappe.db.exists(
			"Repayment Schedule", accrual.repayment_schedule_name
		):
			frappe.db.set_value("Repayment Schedule", accrual.repayment_schedule_name, "is_accrued", 1)

	interest_paid, principal_paid = _split_repayment_amount(
		allocation, allocation["hr_amount"], _currency_precision()
	)
	_recalculate_schedule(
		schedule, schedule_row, principal_paid, interest_paid, schedule_choice == "Yes"
	)
	new_accrual = _make_replacement_accrual(
		loan_doc,
		schedule_row,
		payroll_entry.end_date,
		principal_paid,
		interest_paid,
		old_accruals,
		accounting_dimensions,
	)
	if not new_accrual:
		frappe.db.set_value("Repayment Schedule", schedule_row.name, "is_accrued", 1)

	log = frappe.get_doc(
		{
			"doctype": "Loan Adjustment Log",
			"employee": loan_doc.applicant,
			"loan": loan_doc.name,
			"payroll_entry": payroll_entry.name,
			"scheduled_amount": allocation["scheduled_amount"],
			"hr_amount": allocation["hr_amount"],
			"schedule_choice": schedule_choice,
			"schedule_snapshot": schedule_snapshot,
			"old_accrual_docs": json.dumps(
				list(
					dict.fromkeys(
						[*(json.loads(prior_adjustment.old_accrual_docs or "[]") if prior_adjustment else []),
						*[doc.name for doc in old_accruals]]
					)
				)
			),
			"new_accrual_doc": new_accrual.name if new_accrual else None,
			"user": frappe.session.user,
			"timestamp": now_datetime(),
		}
	)
	log.insert(ignore_permissions=True)
	return log.name


def _cancel_adjustment_accrual(accrual_name):
	if not accrual_name or not frappe.db.exists("Loan Interest Accrual", accrual_name):
		return
	accrual = frappe.get_doc("Loan Interest Accrual", accrual_name)
	if accrual.docstatus == 1:
		accrual.flags.ignore_permissions = True
		accrual.cancel()


def _recreate_cancelled_accrual(accrual_name):
	original = frappe.get_doc("Loan Interest Accrual", accrual_name)
	if original.docstatus != 2:
		return original.name

	restored = frappe.copy_doc(original)
	restored.docstatus = 0
	restored.amended_from = original.name
	restored.flags.ignore_permissions = True
	restored.insert()
	restored.submit()
	if restored.repayment_schedule_name:
		frappe.db.set_value("Repayment Schedule", restored.repayment_schedule_name, "is_accrued", 1)
	return restored.name


def _reverse_loan_adjustment_logs(loan, loan_logs, schedule_names=None):
	loan_logs.sort(key=lambda log: log.creation)
	original_accrual_names = json.loads(loan_logs[0].old_accrual_docs or "[]")
	for accrual_name in dict.fromkeys(log.new_accrual_doc for log in reversed(loan_logs)):
		_cancel_adjustment_accrual(accrual_name)

	if schedule_names is None:
		schedule_names = frappe.get_all(
			"Loan Repayment Schedule",
			filters={"loan": loan, "docstatus": 1, "status": "Active"},
			pluck="name",
		)
	for schedule_name in schedule_names:
		schedule = frappe.get_doc("Loan Repayment Schedule", schedule_name)
		snapshot = next((log.schedule_snapshot for log in loan_logs if log.schedule_snapshot), None)
		if snapshot:
			_restore_schedule_snapshot(schedule, snapshot)
		else:
			loan_doc = frappe.get_doc("Loan", loan)
			_rebuild_legacy_schedule_baseline(schedule, loan_doc)
			schedule.flags.ignore_validate = True
			schedule.flags.ignore_validate_update_after_submit = True
			schedule.save(ignore_permissions=True)

	for accrual_name in original_accrual_names:
		_recreate_cancelled_accrual(accrual_name)


def restore_loan_adjustments_on_payroll_cancel(doc, method=None):
	loan_logs = frappe.get_all(
		"Loan Adjustment Log",
		filters={"payroll_entry": doc.name},
		fields=[
			"name",
			"loan",
			"creation",
			"old_accrual_docs",
			"new_accrual_doc",
			"schedule_snapshot",
		],
		order_by="creation asc",
	)
	logs_by_loan = {}
	for log in loan_logs:
		logs_by_loan.setdefault(log.loan, []).append(log)
	schedule_names_by_loan = {}
	if logs_by_loan:
		for schedule in frappe.get_all(
			"Loan Repayment Schedule",
			filters={
				"loan": ("in", list(logs_by_loan)),
				"docstatus": 1,
				"status": "Active",
			},
			fields=["name", "loan"],
		):
			schedule_names_by_loan.setdefault(schedule.loan, []).append(schedule.name)
	for loan, logs in logs_by_loan.items():
		_reverse_loan_adjustment_logs(loan, logs, schedule_names_by_loan.get(loan, []))


@frappe.whitelist(methods=["POST"])
def apply_loan_repayment_adjustments(
	payroll_entry, adjustments, threshold_percent=None, excluded_employees=None
):
	_check_hr_manager()
	payroll_entry = _get_payroll_entry(payroll_entry, "write")
	if isinstance(adjustments, str):
		adjustments = json.loads(adjustments)
	if isinstance(excluded_employees, str):
		excluded_employees = json.loads(excluded_employees)
	if not isinstance(adjustments, list):
		frappe.throw(_("Loan repayment adjustments must be provided as a list."))
	if excluded_employees is None:
		excluded_employees = []
	if not isinstance(excluded_employees, list):
		frappe.throw(_("Employees to exclude must be provided as a list."))

	threshold = _get_threshold(threshold_percent)
	eligible = {row["employee"]: row for row in _build_candidates(payroll_entry, threshold)}
	excluded_set = set(excluded_employees)
	if not eligible and not adjustments and not excluded_set:
		return {"adjusted_logs": [], "skipped": []}
	if not excluded_set.issubset(eligible):
		frappe.throw(_("The employee list changed. Refresh the adjustment dialog and try again."))
	precision = _currency_precision()
	seen_employees = set()
	prepared = []
	skipped = []
	for item in adjustments:
		employee = item.get("employee")
		if employee in seen_employees:
			frappe.throw(_("The employee list changed. Refresh the adjustment dialog and try again."))
		seen_employees.add(employee)
		if employee in excluded_set:
			frappe.throw(_("An excluded employee cannot also have a loan adjustment."))
		existing_slip = _existing_salary_slip(payroll_entry, employee)
		if existing_slip:
			skipped.append(
				{"employee": employee, "reason": _("Salary Slip {0} already exists.").format(existing_slip)}
			)
			continue
		if employee not in eligible:
			frappe.throw(_("The employee list changed. Refresh the adjustment dialog and try again."))
		candidate = eligible[employee]
		amount, choice = _validate_adjustment(employee, candidate, item, precision)
		allocations = _get_loan_repayment_allocations(
			employee, payroll_entry.start_date, payroll_entry.end_date, amount, payroll_entry.name
		)
		prepared.append({"employee": employee, "choice": choice, "allocations": allocations})

	if set(eligible) - seen_employees - excluded_set:
		frappe.throw(_("Apply an amount and schedule choice for every employee in the dialog."))

	ready = []
	for item in prepared:
		blocked = None
		for allocation in item["allocations"]:
			for accrual in _get_unpaid_accruals(allocation["loan"], payroll_entry.end_date):
				repayment = _submitted_repayment_for_accrual(accrual.name)
				if repayment:
					blocked = _("Accrual {0} is linked to submitted Loan Repayment {1}.").format(
						accrual.name, repayment
					)
					break
			if blocked:
				break
		if blocked:
			skipped.append({"employee": item["employee"], "reason": blocked})
		else:
			ready.append(item)

	savepoint = "loan_repayment_adjustments"
	frappe.db.savepoint(savepoint)
	try:
		logs = []
		for item in ready:
			for allocation in item["allocations"]:
				logs.append(_apply_one_loan(payroll_entry, allocation, item["choice"]))
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		raise

	return {"adjusted_logs": logs, "skipped": skipped}