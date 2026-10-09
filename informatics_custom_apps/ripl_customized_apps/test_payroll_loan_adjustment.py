import json
from datetime import date
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate

from informatics_custom_apps.ripl_customized_apps import payroll_loan_adjustment as adjustment
from informatics_custom_apps.ripl_customized_apps import payroll_loan_candidates as candidates


class FakeSchedule:
	def __init__(self):
		self.loan = "LOAN-1"
		self.loan_product = "PRODUCT-1"
		self.monthly_repayment_amount = 6000
		self.repayment_periods = 10
		self.flags = frappe._dict()
		self.repayment_schedule = []
		balance = 54000
		for index, payment_date in enumerate(
			[
				"2025-01-31",
				"2025-02-28",
				"2025-03-31",
				"2025-04-30",
				"2025-05-31",
				"2025-06-30",
				"2025-07-31",
				"2025-08-31",
				"2025-09-30",
				"2025-10-31",
			]
		):
			principal = 6000
			balance = 54000 if index == 0 else max(balance - principal, 0)
			self.repayment_schedule.append(
				frappe._dict(
					{
						"name": f"ROW-{index + 1}",
						"payment_date": payment_date,
						"principal_amount": principal,
						"interest_amount": 0,
						"total_payment": 6000,
						"balance_loan_amount": balance,
						"number_of_days": 30,
					}
				)
			)

	def get_amounts(self, payment_date, balance, *_args):
		principal = min(self.monthly_repayment_amount, balance)
		new_balance = round(balance - principal, 2)
		return 0, principal, new_balance, principal, 30

	def append(self, fieldname, values):
		self.repayment_schedule.append(frappe._dict(values))

	def set(self, fieldname, value):
		setattr(self, fieldname, value)

	def save(self, **_kwargs):
		self.saved = True


class TestPayrollLoanAdjustment(FrappeTestCase):
	def test_adjustment_log_doctype_controller_loads(self):
		self.assertEqual(frappe.new_doc("Loan Adjustment Log").doctype, "Loan Adjustment Log")

	def test_payroll_entry_cancellation_hook_is_registered(self):
		from informatics_custom_apps import hooks

		self.assertEqual(
			hooks.doc_events["Payroll Entry"]["on_cancel"],
			"informatics_custom_apps.ripl_customized_apps.payroll_loan_adjustment.restore_loan_adjustments_on_payroll_cancel",
		)

	def test_loan_interest_accrual_accepts_accounting_dimensions(self):
		accrual = frappe.new_doc("Loan Interest Accrual")
		for fieldname in ("branch", "segment", "section"):
			accrual.set(fieldname, f"TEST-{fieldname.upper()}")
			self.assertEqual(accrual.get(fieldname), f"TEST-{fieldname.upper()}")

	def test_default_threshold_is_ten_percent(self):
		self.assertEqual(candidates._get_threshold(), 10)

	def test_negative_net_pay_is_eligible(self):
		self.assertTrue(candidates._is_eligible(15000, 10000, 6000, 10, 2))

	def test_zero_net_pay_is_eligible(self):
		self.assertTrue(candidates._is_eligible(15000, 9000, 6000, 10, 2))

	def test_positive_net_pay_below_threshold_is_eligible(self):
		self.assertTrue(candidates._is_eligible(15000, 9000, 5500, 10, 2))

	def test_net_pay_at_threshold_is_not_eligible(self):
		self.assertFalse(candidates._is_eligible(15000, 9000, 4500, 10, 2))

	def test_no_due_loan_returns_no_candidates(self):
		with (
			patch(
				"hrms.payroll.doctype.payroll_entry.payroll_entry.get_employee_list",
				return_value=[frappe._dict(employee="EMP-1", employee_name="Employee One")],
			),
			patch.object(candidates, "_get_due_loan_schedules_for_employees", return_value={"EMP-1": []}) as due_lookup,
			patch.object(candidates, "_preview_salary_amounts") as preview,
		):
			payroll_entry = frappe._dict(
				make_filters=MagicMock(return_value={}),
				start_date="2025-01-01",
				end_date="2025-01-31",
			)
			self.assertEqual(candidates._build_candidates(payroll_entry, 10), [])
			due_lookup.assert_called_once_with(["EMP-1"], "2025-01-01", "2025-01-31", None)
			preview.assert_not_called()

	def test_salary_preview_calculates_components_without_lending_repayment(self):
		slip = MagicMock()
		slip.salary_structure = "SAL-STRUCTURE-1"
		slip.payroll_period = None
		slip.exchange_rate = 1
		slip.get_component_totals.side_effect = [15000, 9000]
		slip.precision.return_value = 2

		candidates._calculate_salary_amounts_without_loan(slip)

		self.assertEqual(slip.gross_pay, 15000)
		self.assertEqual(slip.base_gross_pay, 15000)
		slip.calculate_component_amounts.assert_any_call("earnings")
		slip.calculate_component_amounts.assert_any_call("deductions")
		slip.set.assert_any_call("total_loan_repayment", 0)
		slip.set_net_pay.assert_called_once_with()

	def test_candidate_builder_batches_loan_lookup_across_employees(self):
		employees = [frappe._dict(employee=f"EMP-{index}", employee_name=f"Employee {index}") for index in range(3)]
		payroll_entry = frappe._dict(
			make_filters=MagicMock(return_value={}),
			start_date="2025-01-01",
			end_date="2025-01-31",
			name="PE-1",
		)
		with (
			patch(
				"hrms.payroll.doctype.payroll_entry.payroll_entry.get_employee_list",
				return_value=employees,
			),
			patch.object(
				candidates,
				"_get_due_loan_schedules_for_employees",
				return_value={employee.employee: [] for employee in employees},
			) as due_lookup,
			patch.object(candidates, "_preview_salary_amounts") as preview,
		):
			self.assertEqual(candidates._build_candidates(payroll_entry, 10), [])

		due_lookup.assert_called_once_with(
			["EMP-0", "EMP-1", "EMP-2"], "2025-01-01", "2025-01-31", "PE-1"
		)
		preview.assert_not_called()

	def test_schedule_candidate_lookup_ignores_adjustment_logs_for_cancelled_payroll(self):
		logs = [
			frappe._dict(payroll_entry="PE-CANCELLED", employee="EMP-1", loan="LOAN-1"),
			frappe._dict(payroll_entry="PE-ACTIVE", employee="EMP-1", loan="LOAN-1"),
		]
		entries = [
			frappe._dict(name="PE-CANCELLED", docstatus=2),
			frappe._dict(name="PE-ACTIVE", docstatus=0),
		]
		with patch("frappe.get_all", side_effect=[logs, entries]):
			active_logs = candidates._get_active_adjustment_logs("PE-ACTIVE", ["EMP-1"], ["LOAN-1"])

		self.assertEqual([log.payroll_entry for log in active_logs], ["PE-ACTIVE"])

	def test_previous_adjustment_restores_original_schedule_baseline(self):
		row = frappe._dict(
			scheduled_amount=6000,
			principal_amount=0,
			interest_amount=6000,
			balance_loan_amount=78000,
		)
		original = frappe._dict(payable_principal_amount=26000, interest_amount=0)
		previous = frappe._dict(payable_principal_amount=0)
		log = frappe._dict(
			old_accrual_docs='["ACCRUAL-ORIGINAL"]',
			new_accrual_doc="ACCRUAL-PREVIOUS",
			scheduled_amount=26000,
		)
		with patch.object(candidates, "_currency_precision", return_value=2):
			candidates._restore_prior_schedule_row(
				row, log, {"ACCRUAL-ORIGINAL": original, "ACCRUAL-PREVIOUS": previous}
			)

		self.assertEqual(row.scheduled_amount, 26000)
		self.assertEqual(row.principal_amount, 26000)
		self.assertEqual(row.interest_amount, 0)
		self.assertEqual(row.balance_loan_amount, 52000)

	def test_schedule_snapshot_restores_rows_and_parent_values_exactly(self):
		schedule = FakeSchedule()
		snapshot = {
			"monthly_repayment_amount": 26000,
			"repayment_periods": 3,
			"repayment_schedule": [
				{
					"name": "ORIGINAL-ROW",
					"payment_date": "2025-01-31",
					"number_of_days": 30,
					"principal_amount": 26000,
					"interest_amount": 0,
					"total_payment": 26000,
					"balance_loan_amount": 52000,
					"is_accrued": 1,
				}
			],
		}
		adjustment._restore_schedule_snapshot(schedule, snapshot, save=False)

		self.assertEqual(schedule.monthly_repayment_amount, 26000)
		self.assertEqual(schedule.repayment_periods, 3)
		self.assertEqual(len(schedule.repayment_schedule), 1)
		self.assertEqual(schedule.repayment_schedule[0].name, "ORIGINAL-ROW")
		self.assertEqual(schedule.repayment_schedule[0].balance_loan_amount, 52000)

	def test_schedule_snapshot_serializes_date_objects(self):
		schedule = frappe._dict(
			monthly_repayment_amount=26000,
			repayment_periods=1,
			repayment_schedule=[
				frappe._dict(
					name="ROW-1",
					payment_date=date(2026, 7, 1),
					principal_amount=26000,
					interest_amount=0,
					total_payment=26000,
					balance_loan_amount=52000,
				)
			],
		)

		snapshot = json.loads(adjustment._schedule_snapshot(schedule))

		self.assertEqual(snapshot["repayment_schedule"][0]["payment_date"], "2026-07-01")

	def test_legacy_schedule_rebuild_removes_adjustment_instalment(self):
		class LegacySchedule(FakeSchedule):
			def make_repayment_schedule(self):
				self.repayment_schedule = []
				for index, payment_date in enumerate(("2026-07-01", "2026-08-01", "2026-09-01")):
					self.repayment_schedule.append(
						frappe._dict(
							name=f"GENERATED-{index + 1}",
							payment_date=payment_date,
							number_of_days=1,
							principal_amount=26000,
							interest_amount=0,
							total_payment=26000,
							balance_loan_amount=52000 - index * 26000,
							is_accrued=0,
						)
					)

			def set_repayment_period(self):
				self.repayment_periods = len(self.repayment_schedule)

		schedule = LegacySchedule()
		schedule.repayment_schedule = [
			frappe._dict(
				name=f"OLD-{index + 1}",
				payment_date=payment_date,
				number_of_days=1,
				principal_amount=0 if index == 0 else 26000,
				interest_amount=6000 if index == 0 else 0,
				total_payment=6000 if index == 0 else 26000,
				balance_loan_amount=78000 - index * 26000,
				is_accrued=int(index < 3),
			)
			for index, payment_date in enumerate(
				("2026-07-01", "2026-08-01", "2026-09-01", "2026-10-01")
			)
		]
		loan = frappe._dict(monthly_repayment_amount=26000)

		snapshot = json.loads(adjustment._rebuild_legacy_schedule_baseline(schedule, loan))

		self.assertEqual(schedule.repayment_periods, 3)
		self.assertEqual([row["payment_date"] for row in snapshot["repayment_schedule"]], [
			"2026-07-01", "2026-08-01", "2026-09-01"
		])
		self.assertEqual([row["name"] for row in snapshot["repayment_schedule"]], ["OLD-1", "OLD-2", "OLD-3"])
		self.assertEqual(snapshot["repayment_schedule"][0]["principal_amount"], 26000)

	def test_cancelled_accrual_is_recreated_as_amended_submission(self):
		original = frappe._dict(
			name="ACCRUAL-OLD",
			docstatus=2,
			repayment_schedule_name="ROW-1",
		)
		restored = frappe._dict(
			flags=frappe._dict(),
			repayment_schedule_name="ROW-1",
			insert=MagicMock(),
			submit=MagicMock(),
		)
		with patch("frappe.get_doc", return_value=original), patch(
			"frappe.copy_doc", return_value=restored
		), patch("frappe.db.set_value") as set_value:
			name = adjustment._recreate_cancelled_accrual("ACCRUAL-OLD")

		self.assertEqual(name, restored.name)
		self.assertEqual(restored.docstatus, 0)
		self.assertEqual(restored.amended_from, "ACCRUAL-OLD")
		self.assertTrue(restored.flags.ignore_permissions)
		restored.insert.assert_called_once_with()
		restored.submit.assert_called_once_with()
		set_value.assert_called_once_with("Repayment Schedule", "ROW-1", "is_accrued", 1)

	def test_payroll_cancel_reverses_adjustment_after_core_cancellation(self):
		schedule = FakeSchedule()
		log = frappe._dict(
			creation="2026-01-01",
			old_accrual_docs='["ACCRUAL-OLD"]',
			new_accrual_doc="ACCRUAL-NEW",
			schedule_snapshot=json.dumps(
				{
					"monthly_repayment_amount": 26000,
					"repayment_periods": 3,
					"repayment_schedule": [
						{
							"name": "ORIGINAL-ROW",
							"payment_date": "2025-01-31",
							"principal_amount": 26000,
							"interest_amount": 0,
							"total_payment": 26000,
							"balance_loan_amount": 52000,
						}
					],
				}
			),
		)
		with (
			patch.object(adjustment, "_cancel_adjustment_accrual") as cancel_new,
			patch("frappe.db.get_value", return_value="EMP-1"),
			patch("frappe.get_all", return_value=["SCHEDULE-1"]),
			patch("frappe.get_doc", return_value=schedule),
			patch.object(adjustment, "_recreate_cancelled_accrual") as restore_old,
		):
			adjustment._reverse_loan_adjustment_logs("LOAN-1", [log])

		cancel_new.assert_called_once_with("ACCRUAL-NEW")
		restore_old.assert_called_once_with("ACCRUAL-OLD")
		self.assertEqual(schedule.monthly_repayment_amount, 26000)
		self.assertEqual(schedule.repayment_periods, 3)
		self.assertEqual(schedule.repayment_schedule[0].name, "ORIGINAL-ROW")

	def test_cancelled_payroll_deletes_adjustment_logs_after_restoration(self):
		log = frappe._dict(name="LOG-1", loan="LOAN-1")
		doc = frappe._dict(name="PE-1")
		with patch("frappe.db.exists", return_value=True), patch("frappe.get_all", return_value=[log]), patch.object(
			adjustment, "_reverse_loan_adjustment_logs"
		) as reverse, patch("frappe.delete_doc") as delete_doc:
			adjustment.restore_loan_adjustments_on_payroll_cancel(doc)

		reverse.assert_called_once()
		delete_doc.assert_called_once_with("Loan Adjustment Log", "LOG-1", ignore_permissions=True)

	def test_cancelled_payroll_preserves_adjustment_logs_if_restoration_fails(self):
		log = frappe._dict(name="LOG-1", loan="LOAN-1")
		doc = frappe._dict(name="PE-1")
		with patch("frappe.db.exists", return_value=True), patch("frappe.get_all", return_value=[log]), patch.object(
			adjustment, "_reverse_loan_adjustment_logs", side_effect=RuntimeError("restore failed")
		), patch("frappe.delete_doc") as delete_doc:
			with self.assertRaisesRegex(RuntimeError, "restore failed"):
				adjustment.restore_loan_adjustments_on_payroll_cancel(doc)

		delete_doc.assert_not_called()

	def test_hr_amount_above_scheduled_amount_is_rejected(self):
		candidate = {"gross_pay": 15000, "other_deductions": 9000, "scheduled_amount": 6000}
		with self.assertRaises(frappe.ValidationError):
			adjustment._validate_adjustment(
				"EMP-1", candidate, {"hr_amount": 6000.01, "schedule_choice": "Yes"}, 2
			)

	def test_hr_amount_that_makes_net_negative_is_rejected(self):
		candidate = {"gross_pay": 15000, "other_deductions": 10000, "scheduled_amount": 6000}
		with self.assertRaises(frappe.ValidationError):
			adjustment._validate_adjustment(
				"EMP-1", candidate, {"hr_amount": 5100, "schedule_choice": "No"}, 2
			)

	def test_increase_choice_appends_instalment_and_preserves_payment(self):
		schedule = FakeSchedule()
		current = schedule.repayment_schedule[0]
		with patch.object(adjustment, "_currency_precision", return_value=2), patch(
			"frappe.get_cached_doc",
			return_value=frappe._dict(
				repayment_schedule_type="Monthly as per repayment start date",
				repayment_date_on="End of the current month",
			),
		):
			adjustment._recalculate_schedule(schedule, current, 4000, 0, True)

		self.assertEqual(schedule.monthly_repayment_amount, 6000)
		self.assertEqual(len(schedule.repayment_schedule), 11)
		self.assertEqual(current.principal_amount, 4000)
		self.assertEqual(current.interest_amount, 0)
		self.assertEqual(schedule.repayment_schedule[-1].principal_amount, 2000)
		self.assertGreater(getdate(schedule.repayment_schedule[-1].payment_date), getdate("2025-10-31"))
		self.assertTrue(schedule.saved)

	def test_no_choice_preserves_count_and_recalculates_total(self):
		schedule = FakeSchedule()
		current = schedule.repayment_schedule[0]
		with patch.object(adjustment, "_currency_precision", return_value=2), patch(
			"frappe.get_cached_doc",
			return_value=frappe._dict(
				repayment_schedule_type="Monthly as per repayment start date",
				repayment_date_on="End of the current month",
			),
		):
			adjustment._recalculate_schedule(schedule, current, 4000, 0, False)

		future_rows = schedule.repayment_schedule[1:]
		self.assertEqual(len(future_rows), 9)
		self.assertEqual(schedule.monthly_repayment_amount, 6222.22)
		self.assertEqual(round(sum(row.principal_amount for row in future_rows), 2), 56000)
		self.assertEqual(future_rows[-1].balance_loan_amount, 0)

	def test_hr_amount_follows_scheduled_principal_interest_split(self):
		class FakeAccrual(frappe._dict):
			def __init__(self):
				super().__init__()
				self.flags = frappe._dict()

			def set(self, fieldname, value):
				self[fieldname] = value

			def insert(self):
				self.inserted = True

			def submit(self):
				self.submitted = True

		accrual = FakeAccrual()
		loan = frappe._dict(
			name="LOAN-1",
			applicant_type="Employee",
			applicant="EMP-1",
			branch="BRANCH-1",
			segment="SEGMENT-1",
			section="SECTION-1",
			loan_product="PRODUCT-1",
			loan_account="LOAN-ACCOUNT",
			interest_income_account="INTEREST-ACCOUNT",
			is_term_loan=1,
		)
		schedule_row = frappe._dict(name="ROW-1", payment_date="2025-01-31")
		old = frappe._dict(process_loan_interest_accrual="PROCESS-1")
		with patch("frappe.new_doc", return_value=accrual), patch.object(
			adjustment, "_currency_precision", return_value=2
		), patch(
			"lending.loan_management.doctype.loan_repayment.loan_repayment.get_pending_principal_amount",
			return_value=60000,
		), patch(
			"erpnext.accounts.doctype.accounting_dimension.accounting_dimension.get_accounting_dimensions",
			return_value=["branch", "segment", "section"],
		), patch("frappe.db.set_value"):
			result = adjustment._make_replacement_accrual(loan, schedule_row, "2025-01-31", 4000, 0, [old])

		self.assertIs(result, accrual)
		self.assertEqual(accrual.interest_amount, 0)
		self.assertEqual(accrual.payable_principal_amount, 4000)
		self.assertEqual(accrual.branch, "BRANCH-1")
		self.assertEqual(accrual.segment, "SEGMENT-1")
		self.assertEqual(accrual.section, "SECTION-1")
		self.assertEqual(accrual.due_date, "2025-01-31")
		self.assertTrue(accrual.flags.ignore_permissions)
		self.assertTrue(accrual.inserted)
		self.assertTrue(accrual.submitted)

	def test_old_accrual_is_cancelled_and_log_links_replacement(self):
		loan = frappe._dict(
			name="LOAN-1",
			applicant="EMP-1",
			branch="BRANCH-1",
			segment="SEGMENT-1",
			section="SECTION-1",
		)
		class FakeOldAccrual(frappe._dict):
			def set(self, fieldname, value):
				self[fieldname] = value

		old = FakeOldAccrual(
			name="ACCRUAL-OLD",
			repayment_schedule_name="ROW-1",
			branch=None,
			segment=None,
			section=None,
			flags=frappe._dict(),
			cancel=MagicMock(),
		)
		schedule = FakeSchedule()
		new_accrual = frappe._dict(name="ACCRUAL-NEW")
		log = frappe._dict(insert=MagicMock())

		def get_doc(doctype, _name=None):
			if isinstance(doctype, dict):
				log.update(doctype)
				return log
			return loan if doctype == "Loan" else schedule

		allocation = {
			"loan": "LOAN-1",
			"schedule": "SCHEDULE-1",
			"schedule_row": "ROW-1",
			"payment_date": "2025-01-31",
			"scheduled_amount": 6000,
			"principal_amount": 6000,
			"interest_amount": 0,
			"hr_amount": 4000,
		}
		payroll_entry = frappe._dict(name="PE-1", end_date="2025-01-31")
		with (
			patch("frappe.get_doc", side_effect=get_doc),
			patch.object(adjustment, "_get_unpaid_accruals", return_value=[old]),
			patch(
				"erpnext.accounts.doctype.accounting_dimension.accounting_dimension.get_accounting_dimensions",
				return_value=["branch", "segment", "section"],
			),
			patch.object(adjustment, "_recalculate_schedule"),
			patch.object(adjustment, "_make_replacement_accrual", return_value=new_accrual) as make_new,
			patch("frappe.db.exists", return_value=True),
			patch("frappe.db.set_value"),
		):
			adjustment._apply_one_loan(payroll_entry, allocation, "Yes")

		old.cancel.assert_called_once_with()
		self.assertEqual(old.branch, "BRANCH-1")
		self.assertEqual(old.segment, "SEGMENT-1")
		self.assertEqual(old.section, "SECTION-1")
		self.assertTrue(old.flags.ignore_validate_update_after_submit)
		self.assertTrue(old.flags.ignore_permissions)
		make_new.assert_called_once()
		self.assertEqual(log.new_accrual_doc, "ACCRUAL-NEW")
		self.assertEqual(log.old_accrual_docs, '["ACCRUAL-OLD"]')
		self.assertEqual(len(json.loads(log.schedule_snapshot)["repayment_schedule"]), 10)
		log.insert.assert_called_once_with(ignore_permissions=True)

	def test_error_rolls_back_adjustment_savepoint(self):
		payroll_entry = frappe._dict(
			name="PE-1", docstatus=0, start_date="2025-01-01", end_date="2025-01-31"
		)
		candidate = {
			"employee": "EMP-1",
			"gross_pay": 15000,
			"other_deductions": 9000,
			"scheduled_amount": 6000,
		}
		allocation = {"loan": "LOAN-1", "hr_amount": 4000}
		threshold_before = frappe.db.get_single_value("HR Settings", "loan_repayment_threshold_percent")

		def fail_after_writing(*_args):
			frappe.db.set_value("HR Settings", "HR Settings", "loan_repayment_threshold_percent", 25)
			raise RuntimeError("injected failure")

		with (
			patch.object(adjustment, "_check_hr_manager"),
			patch.object(adjustment, "_get_payroll_entry", return_value=payroll_entry),
			patch.object(adjustment, "_build_candidates", return_value=[candidate]),
			patch.object(adjustment, "_get_loan_repayment_allocations", return_value=[allocation]),
			patch.object(adjustment, "_get_unpaid_accruals", return_value=[]),
			patch.object(adjustment, "_apply_one_loan", side_effect=fail_after_writing),
			patch("frappe.db.exists", return_value=None),
		):
			with self.assertRaisesRegex(RuntimeError, "injected failure"):
				adjustment.apply_loan_repayment_adjustments(
					"PE-1",
					[{"employee": "EMP-1", "hr_amount": 4000, "schedule_choice": "Yes"}],
					threshold_percent=10,
				)

		self.assertEqual(
			frappe.db.get_single_value("HR Settings", "loan_repayment_threshold_percent"),
			threshold_before,
		)

	def test_non_hr_manager_is_rejected(self):
		with patch("frappe.only_for", side_effect=RuntimeError("Not permitted")):
			with self.assertRaisesRegex(RuntimeError, "Not permitted"):
				adjustment._check_hr_manager()

	def test_linked_submitted_repayment_is_skipped(self):
		payroll_entry = frappe._dict(
			name="PE-1", docstatus=0, start_date="2025-01-01", end_date="2025-01-31"
		)
		candidate = {
			"employee": "EMP-1",
			"gross_pay": 15000,
			"other_deductions": 9000,
			"scheduled_amount": 6000,
		}
		allocation = {"loan": "LOAN-1", "hr_amount": 4000}
		accrual = frappe._dict(name="ACCRUAL-1")
		with (
			patch.object(adjustment, "_check_hr_manager"),
			patch.object(adjustment, "_get_payroll_entry", return_value=payroll_entry),
			patch.object(adjustment, "_build_candidates", return_value=[candidate]),
			patch.object(adjustment, "_get_loan_repayment_allocations", return_value=[allocation]),
			patch.object(adjustment, "_get_unpaid_accruals", return_value=[accrual]),
			patch.object(adjustment, "_submitted_repayment_for_accrual", return_value="LR-1"),
			patch.object(adjustment, "_apply_one_loan") as apply_loan,
			patch("frappe.db.exists", return_value=None),
			patch("frappe.db.savepoint"),
		):
			result = adjustment.apply_loan_repayment_adjustments(
				"PE-1",
				[{"employee": "EMP-1", "hr_amount": 4000, "schedule_choice": "No"}],
				threshold_percent=10,
			)

		self.assertEqual(result["skipped"][0]["employee"], "EMP-1")
		self.assertIn("LR-1", result["skipped"][0]["reason"])
		apply_loan.assert_not_called()

	def test_existing_salary_slip_is_skipped(self):
		payroll_entry = frappe._dict(
			name="PE-1", docstatus=0, start_date="2025-01-01", end_date="2025-01-31"
		)
		candidate = {
			"employee": "EMP-1",
			"gross_pay": 15000,
			"other_deductions": 9000,
			"scheduled_amount": 6000,
		}
		with (
			patch.object(adjustment, "_check_hr_manager"),
			patch.object(adjustment, "_get_payroll_entry", return_value=payroll_entry),
			patch.object(adjustment, "_build_candidates", return_value=[]),
			patch.object(adjustment, "_get_loan_repayment_allocations", return_value=[]),
			patch.object(adjustment, "_apply_one_loan") as apply_loan,
			patch("frappe.db.exists", return_value="SS-1"),
		):
			result = adjustment.apply_loan_repayment_adjustments(
				"PE-1",
				[{"employee": "EMP-1", "hr_amount": 4000, "schedule_choice": "No"}],
				threshold_percent=10,
			)

		self.assertIn("SS-1", result["skipped"][0]["reason"])
		apply_loan.assert_not_called()

	def test_excluded_employee_is_not_adjusted(self):
		payroll_entry = frappe._dict(
			name="PE-1", docstatus=0, start_date="2025-01-01", end_date="2025-01-31"
		)
		candidate = {
			"employee": "EMP-1",
			"gross_pay": 15000,
			"other_deductions": 9000,
			"scheduled_amount": 6000,
		}
		with (
			patch.object(adjustment, "_check_hr_manager"),
			patch.object(adjustment, "_get_payroll_entry", return_value=payroll_entry),
			patch.object(adjustment, "_build_candidates", return_value=[candidate]),
			patch.object(adjustment, "_apply_one_loan") as apply_loan,
			patch("frappe.db.savepoint"),
		):
			result = adjustment.apply_loan_repayment_adjustments(
				"PE-1", [], threshold_percent=10, excluded_employees=["EMP-1"]
			)

		self.assertEqual(result["adjusted_logs"], [])
		apply_loan.assert_not_called()

	def test_multiple_loans_receive_amount_oldest_first(self):
		rows = [
			{"loan": "LOAN-OLD", "start_date": "2020-01-01", "scheduled_amount": 6000},
			{"loan": "LOAN-NEW", "start_date": "2021-01-01", "scheduled_amount": 6000},
		]
		with patch.object(adjustment, "_get_due_loan_schedules", return_value=rows), patch.object(
			adjustment, "_currency_precision", return_value=2
		):
			allocations = adjustment._get_loan_repayment_allocations("EMP-1", "2025-01-01", "2025-01-31", 8000)

		self.assertEqual([(row["loan"], row["hr_amount"]) for row in allocations], [("LOAN-OLD", 6000), ("LOAN-NEW", 2000)])

	def test_salary_slip_loan_deduction_matches_hr_amount_and_keeps_net_positive(self):
		slip = frappe.new_doc("Salary Slip")
		slip.update(
			{
				"employee": "EMP-1",
				"company": "_Test Company",
				"currency": "INR",
				"exchange_rate": 1,
				"start_date": "2025-01-01",
				"end_date": "2025-01-31",
			}
		)
		slip._salary_structure_doc = frappe._dict(salary_component="Basic")
		slip.append("earnings", {"salary_component": "Basic", "amount": 15000})
		slip.append("deductions", {"salary_component": "Other Deduction", "amount": 9000})
		slip.append(
			"loans",
			{
				"loan": "LOAN-1",
				"loan_account": "LA",
				"interest_income_account": "IA",
				"total_payment": 4000,
				"interest_amount": 4000,
				"principal_amount": 0,
			},
		)
		amounts = {
			"payable_amount": 4000,
			"interest_amount": 4000,
			"payable_principal_amount": 0,
		}
		with patch(
			"lending.loan_management.doctype.loan_repayment.loan_repayment.calculate_amounts",
			return_value=amounts,
		):
			slip.calculate_net_pay(skip_tax_breakup_computation=True)

		self.assertEqual(slip.total_loan_repayment, 4000)
		self.assertGreaterEqual(slip.net_pay, 0)
		self.assertEqual(slip.net_pay, 2000)