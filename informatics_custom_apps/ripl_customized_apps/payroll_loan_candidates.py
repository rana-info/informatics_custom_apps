import json

import frappe
from frappe import _
from frappe.utils import cint, flt


THRESHOLD_FIELD = "loan_repayment_threshold_percent"


def _check_hr_manager():
	frappe.only_for("HR Manager")


def _currency_precision():
	return cint(frappe.db.get_default("currency_precision")) or 2


def _get_payroll_entry(name, permission):
	doc = frappe.get_doc("Payroll Entry", name)
	doc.check_permission(permission)
	if doc.docstatus != 0:
		frappe.throw(_("Loan adjustments are only available for draft Payroll Entries."))
	return doc


def _get_threshold(value=None):
	if value is None:
		value = frappe.db.get_single_value("HR Settings", THRESHOLD_FIELD)
	return flt(value if value is not None else 10)


def _preview_salary_amounts(payroll_entry, employee):
	slip = frappe.new_doc("Salary Slip")
	slip.update(
		{
			"employee": employee,
			"company": payroll_entry.company,
			"currency": payroll_entry.currency,
			"exchange_rate": payroll_entry.exchange_rate,
			"start_date": payroll_entry.start_date,
			"end_date": payroll_entry.end_date,
			"posting_date": payroll_entry.posting_date,
			"payroll_frequency": payroll_entry.payroll_frequency,
			"payroll_entry": payroll_entry.name,
			"salary_slip_based_on_timesheet": payroll_entry.salary_slip_based_on_timesheet,
			"deduct_tax_for_unclaimed_employee_benefits": payroll_entry.deduct_tax_for_unclaimed_employee_benefits,
			"deduct_tax_for_unsubmitted_tax_exemption_proof": payroll_entry.deduct_tax_for_unsubmitted_tax_exemption_proof,
		}
	)
	slip.set("earnings", [])
	slip.set("deductions", [])
	slip.set("loans", [])
	if slip.payroll_frequency:
		slip.get_date_details()
	slip.validate_dates()
	slip.get_working_days_details()
	if not slip.check_sal_struct():
		return 0, 0
	slip.set_salary_structure_doc()
	slip.salary_slip_based_on_timesheet = slip._salary_structure_doc.salary_slip_based_on_timesheet or 0
	slip.set_time_sheet()
	slip.pull_sal_struct()
	slip.set_salary_structure_assignment()
	_calculate_salary_amounts_without_loan(slip)

	precision = _currency_precision()
	return flt(slip.gross_pay, precision), flt(slip.total_deduction, precision)


def _calculate_salary_amounts_without_loan(slip):
	from hrms.payroll.doctype.payroll_period.payroll_period import get_period_factor

	if slip.salary_structure:
		slip.calculate_component_amounts("earnings")

	if slip.payroll_period:
		slip.remaining_sub_periods = get_period_factor(
			slip.employee,
			slip.start_date,
			slip.end_date,
			slip.payroll_frequency,
			slip.payroll_period,
			joining_date=slip.joining_date,
			relieving_date=slip.relieving_date,
		)[1]

	slip.gross_pay = slip.get_component_totals("earnings", depends_on_payment_days=1)
	slip.base_gross_pay = flt(
		flt(slip.gross_pay) * flt(slip.exchange_rate), slip.precision("base_gross_pay")
	)
	if slip.salary_structure:
		slip.calculate_component_amounts("deductions")
	slip.set("total_loan_repayment", 0)
	slip.set_precision_for_component_amounts()
	slip.set_net_pay()


def _get_prior_adjustment_log(payroll_entry, employee, loan):
	if not payroll_entry:
		return None
	logs = frappe.get_all(
		"Loan Adjustment Log",
		filters={"payroll_entry": payroll_entry, "employee": employee, "loan": loan},
		fields=["name", "scheduled_amount", "old_accrual_docs", "new_accrual_doc", "schedule_snapshot"],
		order_by="creation desc",
		limit_page_length=1,
	)
	return logs[0] if logs else None


def _get_active_adjustment_logs(payroll_entry, employees, loans):
	if not payroll_entry or not loans:
		return []
	logs = frappe.get_all(
		"Loan Adjustment Log",
		filters={
			"payroll_entry": payroll_entry,
			"employee": ("in", employees),
			"loan": ("in", loans),
		},
		fields=[
			"payroll_entry",
			"employee",
			"loan",
			"creation",
			"scheduled_amount",
			"old_accrual_docs",
			"new_accrual_doc",
		],
		order_by="creation desc",
	)
	if not logs:
		return []
	payroll_entries = {
		entry.name
		for entry in frappe.get_all(
			"Payroll Entry",
			filters={"name": ("in", list({log.payroll_entry for log in logs}))},
			fields=["name", "docstatus"],
		)
		if entry.docstatus != 2
	}
	return [log for log in logs if log.payroll_entry in payroll_entries]


def _restore_prior_schedule_row(row, adjustment_log, accruals=None):
	if not adjustment_log:
		return row

	old_accrual_names = json.loads(adjustment_log.old_accrual_docs or "[]")
	if not old_accrual_names:
		return row
	if accruals is None:
		accrual_names = [old_accrual_names[0]]
		if adjustment_log.new_accrual_doc:
			accrual_names.append(adjustment_log.new_accrual_doc)
		accruals = {
			accrual.name: accrual
			for accrual in frappe.get_all(
				"Loan Interest Accrual",
				filters={"name": ("in", accrual_names)},
				fields=["name", "payable_principal_amount", "interest_amount"],
			)
		}
	original_accrual = accruals.get(old_accrual_names[0])
	if not original_accrual:
		return row
	prior_new_accrual = accruals.get(adjustment_log.new_accrual_doc)
	original_principal = flt(original_accrual.payable_principal_amount, _currency_precision())
	previous_principal_paid = flt(
		prior_new_accrual.payable_principal_amount if prior_new_accrual else 0, _currency_precision()
	)
	previous_interest_paid = flt(
		prior_new_accrual.interest_amount if prior_new_accrual else 0, _currency_precision()
	)
	row.scheduled_amount = flt(adjustment_log.scheduled_amount, _currency_precision())
	row.interest_amount = flt(original_accrual.interest_amount, _currency_precision())
	row.principal_amount = original_principal
	row.balance_loan_amount = flt(
		row.balance_loan_amount
		- original_principal
		- flt(original_accrual.interest_amount, _currency_precision())
		+ previous_principal_paid
		+ previous_interest_paid,
		_currency_precision(),
	)
	return row


def _get_due_loan_schedules_for_employees(employees, start_date, end_date, payroll_entry=None):
	employees = list(dict.fromkeys(employees))
	due_by_employee = {employee: [] for employee in employees}
	if not employees:
		return due_by_employee

	loans = frappe.get_all(
		"Loan",
		filters={
			"applicant_type": "Employee",
			"applicant": ("in", employees),
			"docstatus": 1,
			"repay_from_salary": 1,
			"status": ("!=", "Closed"),
		},
		fields=[
			"name",
			"applicant",
			"disbursement_date",
			"posting_date",
			"repayment_start_date",
			"loan_account",
			"interest_income_account",
			"loan_product",
			"is_term_loan",
		],
	)
	if not loans:
		return due_by_employee

	loan_by_name = {loan.name: loan for loan in loans}
	schedules = frappe.get_all(
		"Loan Repayment Schedule",
		filters={"loan": ("in", list(loan_by_name)), "status": "Active", "docstatus": 1},
		fields=[
			"name",
			"loan",
			"loan_product",
			"repayment_method",
			"monthly_repayment_amount",
			"repayment_periods",
			"rate_of_interest",
		],
	)
	if not schedules:
		return due_by_employee
	schedule_by_name = {schedule.name: schedule for schedule in schedules}

	rows = frappe.get_all(
		"Repayment Schedule",
		filters={
			"parent": ("in", [schedule.name for schedule in schedules]),
			"payment_date": ("between", [start_date, end_date]),
		},
		fields=[
			"name",
			"parent",
			"payment_date",
			"principal_amount",
			"interest_amount",
			"total_payment",
			"balance_loan_amount",
			"number_of_days",
		],
		order_by="payment_date asc, idx asc",
	)
	if not rows:
		return due_by_employee
	prior_logs = {}
	for log in _get_active_adjustment_logs(payroll_entry, employees, list(loan_by_name)):
		prior_logs.setdefault((log.employee, log.loan), log)

	accrual_names = set()
	for log in prior_logs.values():
		old_accrual_names = json.loads(log.old_accrual_docs or "[]")
		if old_accrual_names:
			accrual_names.add(old_accrual_names[0])
		if log.new_accrual_doc:
			accrual_names.add(log.new_accrual_doc)
	accruals = {}
	if accrual_names:
		accruals = {
			accrual.name: accrual
			for accrual in frappe.get_all(
				"Loan Interest Accrual",
				filters={"name": ("in", list(accrual_names))},
				fields=["name", "payable_principal_amount", "interest_amount"],
			)
		}

	for row in rows:
		schedule = schedule_by_name[row.parent]
		loan = loan_by_name[schedule.loan]
		adjustment_log = prior_logs.get((loan.applicant, loan.name))
		if adjustment_log:
			row = _restore_prior_schedule_row(row, adjustment_log, accruals)
		due_by_employee[loan.applicant].append(
			{
				"loan": loan.name,
				"start_date": loan.disbursement_date or loan.posting_date or loan.repayment_start_date,
				"schedule": schedule.name,
				"schedule_row": row.name,
				"payment_date": row.payment_date,
				"scheduled_amount": flt(
					row.get("scheduled_amount", row.total_payment), _currency_precision()
				),
				"principal_amount": flt(row.principal_amount, _currency_precision()),
				"interest_amount": flt(row.interest_amount, _currency_precision()),
				"balance_loan_amount": flt(row.balance_loan_amount, _currency_precision()),
			}
		)
	for due_loans in due_by_employee.values():
		due_loans.sort(key=lambda item: (str(item["start_date"] or ""), item["loan"], str(item["payment_date"])))
	return due_by_employee


def _get_due_loan_schedules(employee, start_date, end_date, payroll_entry=None):
	return _get_due_loan_schedules_for_employees(
		[employee], start_date, end_date, payroll_entry
	).get(employee, [])


def _build_candidates(payroll_entry, threshold):
	from hrms.payroll.doctype.payroll_entry.payroll_entry import get_employee_list

	employee_list = get_employee_list(
		filters=payroll_entry.make_filters(), as_dict=True, ignore_match_conditions=True
	)
	due_loans_by_employee = _get_due_loan_schedules_for_employees(
		[employee.employee for employee in employee_list],
		payroll_entry.start_date,
		payroll_entry.end_date,
		payroll_entry.name,
	)
	precision = _currency_precision()
	eligible = []
	for employee_row in employee_list:
		employee = employee_row.employee
		due_loans = due_loans_by_employee.get(employee, [])
		if not due_loans:
			continue

		gross_pay, other_deductions = _preview_salary_amounts(payroll_entry, employee)
		scheduled_amount = flt(sum(item["scheduled_amount"] for item in due_loans), precision)
		net_after_loan = flt(gross_pay - other_deductions - scheduled_amount, precision)
		if _is_eligible(gross_pay, other_deductions, scheduled_amount, threshold, precision):
			eligible.append(
				{
					"employee": employee,
					"employee_name": employee_row.employee_name,
					"gross_pay": gross_pay,
					"other_deductions": other_deductions,
					"scheduled_amount": scheduled_amount,
					"net_after_loan": net_after_loan,
					"loans": [
						{
							"loan": item["loan"],
							"scheduled_amount": item["scheduled_amount"],
							"payment_date": str(item["payment_date"]),
						}
						for item in due_loans
					],
				}
			)
	return eligible


def _is_eligible(gross_pay, other_deductions, loan_repayment, threshold, precision=None):
	precision = precision or _currency_precision()
	net_after_loan = flt(gross_pay - other_deductions - loan_repayment, precision)
	return net_after_loan <= 0 or net_after_loan < flt(gross_pay * threshold / 100, precision)


@frappe.whitelist()
def get_loan_adjustment_candidates(payroll_entry, threshold_percent=None):
	payroll_entry = _get_payroll_entry(payroll_entry, "read")
	threshold = _get_threshold(threshold_percent)
	if threshold < 0:
		frappe.throw(_("Threshold percentage cannot be negative."))
	return {"threshold_percent": threshold, "employees": _build_candidates(payroll_entry, threshold)}