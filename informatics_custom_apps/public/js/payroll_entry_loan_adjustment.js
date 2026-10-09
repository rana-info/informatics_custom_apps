const standardGetEmployeeDetails =
	frappe.ui.form.handlers?.["Payroll Entry"]?.get_employee_details?.at(-1);

function escapeLoanAdjustmentHTML(value) {
	return frappe.utils.escape_html(String(value ?? ""));
}

function renderLoanAdjustmentRows(dialog, rows, currency) {
	const precision = cint(frappe.defaults.get_default("currency_precision")) || 2;
	const payrollPeriod = `${frappe.datetime.str_to_user(dialog.frm.doc.start_date)} - ${frappe.datetime.str_to_user(dialog.frm.doc.end_date)}`;
	const body = rows.length
		? rows
		.map((row, index) => {
			const employee = escapeLoanAdjustmentHTML(row.employee);
			const employeeName = escapeLoanAdjustmentHTML(row.employee_name);
			const currentMonthNet = flt(row.gross_pay - row.other_deductions, precision);
			const estimatedNet = flt(row.gross_pay - row.other_deductions - row.scheduled_amount, precision);
			return `<tr data-index="${index}">
				<td><strong>${employee}</strong><br>${employeeName}</td>
				<td class="text-right">${format_currency(currentMonthNet, currency)}</td>
				<td class="text-right estimated-net-pay" data-index="${index}">${format_currency(estimatedNet, currency)}</td>
				<td class="text-right">${format_currency(row.scheduled_amount, currency)}</td>
				<td><input class="form-control input-sm hr-loan-amount" type="number" min="0" step="${1 / 10 ** precision}" value="${flt(row.scheduled_amount, precision)}" data-index="${index}"></td>
				<td><select class="form-control input-sm loan-schedule-choice" data-index="${index}"><option value=""></option><option value="Yes">Yes</option><option value="No">No</option></select></td>
				<td class="text-center"><input class="exclude-loan-employee" type="checkbox" aria-label="${__("Exclude {0} from payroll", [employee])}" data-index="${index}"></td>
			</tr>`;
		})
		.join("")
		: `<tr><td colspan="7" class="text-muted">${__("No employees meet the loan repayment threshold.")}</td></tr>`;

	dialog.fields_dict.employee_rows.$wrapper.html(`
		<div class="loan-adjustment-table-wrap">
			<div class="text-right" style="margin-bottom: 8px">
				<button type="button" class="btn btn-default btn-sm loan-adjustment-refresh">${__("Refresh")}</button>
			</div>
			<div class="text-muted" style="margin-bottom: 8px">${__("Payroll period")}: ${escapeLoanAdjustmentHTML(payrollPeriod)}</div>
			<div style="overflow-x: auto">
				<table class="table table-bordered table-condensed">
					<thead><tr>
						<th>${__("Employee")}</th>
						<th class="text-right">${__("Net salary for current month (before loan deduction)")}</th>
						<th class="text-right">${__("Estimated net after HR loan deduction")}</th>
						<th class="text-right">${__("Scheduled loan deduction")}</th>
						<th>${__("Loan deduction by HR")}</th>
						<th>${__("Increase repayment schedule")}</th>
						<th>${__("Exclude from payroll")}</th>
					</tr></thead>
					<tbody>${body}</tbody>
				</table>
			</div>
		</div>`);

	const wrapper = dialog.fields_dict.employee_rows.$wrapper;
	wrapper.off("click.loanAdjustment", ".loan-adjustment-refresh");
	wrapper.off("input.loanAdjustment", ".hr-loan-amount");
	wrapper.on("click.loanAdjustment", ".loan-adjustment-refresh", () =>
		refreshLoanAdjustmentRows(dialog, currency),
	);
	wrapper.on("input.loanAdjustment", ".hr-loan-amount", (event) => {
		const input = $(event.currentTarget);
		const index = cint(input.attr("data-index"));
		const row = rows[index];
		const amount = Number(input.val());
		const netPay = Number.isFinite(amount)
			? flt(row.gross_pay - row.other_deductions - amount, precision)
			: null;
		const display = netPay === null ? "-" : format_currency(netPay, currency);
		wrapper.find(`.estimated-net-pay[data-index="${index}"]`).text(display);
	});
}

async function refreshLoanAdjustmentRows(dialog, currency) {
	const response = await frappe.call({
		method: "informatics_custom_apps.ripl_customized_apps.payroll_loan_candidates.get_loan_adjustment_candidates",
		args: {
			payroll_entry: dialog.frm.doc.name,
		},
		freeze: true,
		freeze_message: __("Refreshing loan repayment candidates"),
	});
	const rows = response.message?.employees || [];
	if (!rows.length) {
		dialog.loan_adjustment_rows = [];
		renderLoanAdjustmentRows(dialog, rows, currency);
		return;
	}
	dialog.loan_adjustment_rows = rows;
	renderLoanAdjustmentRows(dialog, rows, currency);
}

function collectLoanAdjustmentRows(dialog) {
	const precision = cint(frappe.defaults.get_default("currency_precision")) || 2;
	const adjustments = [];
	const excludedEmployees = [];
	for (const [index, row] of dialog.loan_adjustment_rows.entries()) {
		const excluded = dialog.fields_dict.employee_rows.$wrapper
			.find(`.exclude-loan-employee[data-index="${index}"]`)
			.is(":checked");
		if (excluded) {
			excludedEmployees.push(row.employee);
			continue;
		}
		const amountInput = dialog.fields_dict.employee_rows.$wrapper.find(`.hr-loan-amount[data-index="${index}"]`);
		const choiceInput = dialog.fields_dict.employee_rows.$wrapper.find(`.loan-schedule-choice[data-index="${index}"]`);
		const amount = Number(amountInput.val());
		if (!Number.isFinite(amount) || amount < 0 || amount > flt(row.scheduled_amount, precision)) {
			throw new Error(
				__("HR amount for {0} must be between zero and the scheduled amount.", [row.employee]),
			);
		}
		if (flt(row.gross_pay - row.other_deductions - amount, precision) < 0) {
			throw new Error(__("HR amount for {0} would make net salary negative.", [row.employee]));
		}
		const scheduleChoice = choiceInput.val();
		if (!["Yes", "No"].includes(scheduleChoice)) {
			throw new Error(__("Choose Yes or No for the repayment schedule for {0}.", [row.employee]));
		}
		adjustments.push({ employee: row.employee, hr_amount: amount, schedule_choice: scheduleChoice });
	}
	return { adjustments, excludedEmployees };
}

function showLoanAdjustmentDialog(frm, response) {
	const rows = response.employees || [];
	const currency = frm.doc.currency;
	const dialog = new frappe.ui.Dialog({
		title: __("Loan Repayment Adjustment Required"),
		size: "extra-large",
		fields: [{ fieldname: "employee_rows", fieldtype: "HTML" }],
	});
	dialog.frm = frm;
	dialog.loan_adjustment_rows = rows;
	dialog.set_primary_action(__("Apply and Continue"), async () => {
		let adjustmentValues;
		try {
			adjustmentValues = collectLoanAdjustmentRows(dialog);
		} catch (error) {
			frappe.msgprint(error.message);
			return;
		}
		const primaryButton = dialog.get_primary_btn();
		primaryButton.prop("disabled", true);
		try {
			const result = await frappe.call({
				method: "informatics_custom_apps.ripl_customized_apps.payroll_loan_adjustment.apply_loan_repayment_adjustments",
				args: {
					payroll_entry: frm.doc.name,
					adjustments: adjustmentValues.adjustments,
					excluded_employees: adjustmentValues.excludedEmployees,
				},
				freeze: true,
				freeze_message: __("Updating loan repayment schedules"),
			});
			dialog.hide();
			if (result.message?.skipped?.length) {
				frappe.msgprint({
					title: __("Some employees were skipped"),
					message: result.message.skipped
						.map((item) => `${escapeLoanAdjustmentHTML(item.employee)}: ${escapeLoanAdjustmentHTML(item.reason)}`)
						.join("<br>"),
				});
			}
			if (!adjustmentValues.excludedEmployees.length && standardGetEmployeeDetails) {
				return standardGetEmployeeDetails(frm);
			}
			return runStandardGetEmployeeDetails(frm, adjustmentValues.excludedEmployees);
		} finally {
			primaryButton.prop("disabled", false);
		}
	});
	dialog.set_secondary_action_label(__("Cancel"));
	dialog.set_secondary_action(() => dialog.hide());
	dialog.show();
	renderLoanAdjustmentRows(dialog, rows, currency);
}

function runStandardGetEmployeeDetails(frm, excludedEmployees = []) {
	return frappe
		.call({
			doc: frm.doc,
			method: "fill_employee_details",
			freeze: true,
			freeze_message: __("Fetching Employees"),
		})
		.then((r) => {
			if (r.docs?.[0]?.employees) {
				if (excludedEmployees.length) {
					const excluded = new Set(excludedEmployees);
					frm.doc.employees = r.docs[0].employees.filter((row) => !excluded.has(row.employee));
					frm.doc.number_of_employees = frm.doc.employees.length;
					frm.refresh_field("employees");
				}
				frm.dirty();
				return frm.save().then(() => r);
			}
			return r;
		})
		.then((r) => {
			frm.refresh();
			if (r.docs?.[0]?.validate_attendance) {
				render_employee_attendance(frm, r.message);
			}
			frm.scroll_to_field("employees");
		});
}

frappe.ui.form.on("Payroll Entry", {
	get_employee_details(frm) {
		return frappe
			.call({
				method: "informatics_custom_apps.ripl_customized_apps.payroll_loan_candidates.get_loan_adjustment_candidates",
				args: { payroll_entry: frm.doc.name },
				freeze: true,
				freeze_message: __("Checking loan repayments"),
			})
			.then((r) => {
				if (!r.message?.employees?.length) {
					return standardGetEmployeeDetails
						? standardGetEmployeeDetails(frm)
						: runStandardGetEmployeeDetails(frm);
				}
				showLoanAdjustmentDialog(frm, r.message);
			});
	},
});