const standardGetEmployeeDetails =
	frappe.ui.form.handlers?.["Payroll Entry"]?.get_employee_details?.at(-1);

function escapeLoanAdjustmentHTML(value) {
	return frappe.utils.escape_html(String(value ?? ""));
}

function getLoanAdjustmentNegativeEmployees(dialog, rows) {
	const precision = cint(frappe.defaults.get_default("currency_precision")) || 2;
	const wrapper = dialog.fields_dict.employee_rows.$wrapper;
	const negativeEmployees = [];
	for (const [index, row] of rows.entries()) {
		const excluded = wrapper
			.find(`.exclude-loan-employee[data-index="${index}"]`)
			.is(":checked");
		if (excluded) continue;
		const amountInput = wrapper.find(`.hr-loan-amount[data-index="${index}"]`);
		const amount = Number(amountInput.val());
		if (!Number.isFinite(amount)) continue;
		const netAfterAdjustment = flt(row.gross_pay - row.other_deductions - amount, precision);
		if (netAfterAdjustment < 0) {
			negativeEmployees.push({
				employee: row.employee,
				netAfterAdjustment,
			});
		}
	}
	return negativeEmployees;
}

function updateLoanAdjustmentWarningStatus(dialog, rows) {
	const wrapper = dialog.fields_dict.employee_rows.$wrapper;
	const status = wrapper.find(".loan-adjustment-status");
	const negativeEmployees = getLoanAdjustmentNegativeEmployees(dialog, rows);
	const primaryButton = dialog.get_primary_btn && dialog.get_primary_btn();
	if (negativeEmployees.length) {
		const details = negativeEmployees
			.map(({ employee, netAfterAdjustment }) => {
				return `${escapeLoanAdjustmentHTML(employee)} (${format_currency(netAfterAdjustment, dialog.frm.doc.currency)})`;
			})
			.join(", ");
		status
			.removeClass("text-muted text-success")
			.addClass("text-warning")
			.html(
				`${__("Warning")}: ${__("Net salary remains negative for")}: ${details}. ${__("Adjust the HR loan amount or exclude the employee before continuing.")}`,
			);
		if (primaryButton) primaryButton.prop("disabled", true);
		return false;
	}
	status
		.removeClass("text-warning text-danger")
		.addClass("text-muted")
		.text(__("No negative net payroll values after HR loan adjustments."));
	if (primaryButton) primaryButton.prop("disabled", false);
	return true;
}

function renderLoanAdjustmentRows(dialog, rows, currency) {
	const precision = cint(frappe.defaults.get_default("currency_precision")) || 2;
	const payrollPeriod = `${frappe.datetime.str_to_user(dialog.frm.doc.start_date)} - ${frappe.datetime.str_to_user(dialog.frm.doc.end_date)}`;
	const body = rows.length
		? rows
		.map((row, index) => {
			const employee = escapeLoanAdjustmentHTML(row.employee);
			const employeeName = escapeLoanAdjustmentHTML(row.employee_name);
			const scheduledThisMonth = flt(
				row.hr_default_amount ?? row.scheduled_amount,
				precision,
			);
			const defaultHrAmount = flt(row.scheduled_amount, precision);
			const currentMonthNet = flt(row.gross_pay - row.other_deductions, precision);
			const estimatedNet = flt(row.gross_pay - row.other_deductions - defaultHrAmount, precision);
			return `<tr data-index="${index}">
				<td><strong>${employee}</strong><br>${employeeName}</td>
				<td class="text-right">${format_currency(currentMonthNet, currency)}</td>
				<td class="text-right estimated-net-pay" data-index="${index}">${format_currency(estimatedNet, currency)}</td>
				<td class="text-right">${format_currency(row.scheduled_amount, currency)}</td>
				<td class="text-right">${format_currency(scheduledThisMonth, currency)}</td>
				<td><input class="form-control input-sm hr-loan-amount" type="number" min="0" step="${1 / 10 ** precision}" value="${defaultHrAmount}" data-index="${index}"></td>
				<td><select class="form-control input-sm loan-schedule-choice" data-index="${index}"><option value="Yes" selected>Yes</option><option value="No">No</option></select></td>
				<td class="text-center"><input class="exclude-loan-employee" type="checkbox" aria-label="${__("Exclude {0} from payroll", [employee])}" data-index="${index}"></td>
			</tr>`;
		})
		.join("")
		: `<tr><td colspan="8" class="text-muted">${__("No employees meet the loan repayment threshold.")}</td></tr>`;

	dialog.fields_dict.employee_rows.$wrapper.html(`
		<div class="loan-adjustment-table-wrap">
			<div class="loan-adjustment-status text-muted" role="status" style="margin-bottom: 8px"></div>
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
						<th class="text-right">${__("Scheduled this month deduction")}</th>
						<th>${__("Loan deduction by HR")}</th>
						<th>${__("Increase repayment schedule")}</th>
						<th>${__("Exclude from payroll")}</th>
					</tr></thead>
					<tbody>${body}</tbody>
				</table>
			</div>
		</div>`);

	const wrapper = dialog.fields_dict.employee_rows.$wrapper;
	wrapper.find(".hr-loan-amount").each(function () {
		const input = $(this);
		const index = cint(input.attr("data-index"));
		const defaultValue = flt(rows[index]?.scheduled_amount, precision);
		if (input.val() === "" || !Number.isFinite(Number(input.val()))) {
			input.val(defaultValue);
		}
	});
	wrapper.off("click.loanAdjustment", ".loan-adjustment-refresh");
	wrapper.off("input.loanAdjustment", ".hr-loan-amount");
	wrapper.off("change.loanAdjustment", ".loan-schedule-choice");
	wrapper.off("change.loanAdjustment", ".exclude-loan-employee");
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
		updateLoanAdjustmentWarningStatus(dialog, rows);
	});
	wrapper.on("change.loanAdjustment", ".loan-schedule-choice", () => {
		updateLoanAdjustmentWarningStatus(dialog, rows);
	});
	wrapper.on("change.loanAdjustment", ".exclude-loan-employee", () => {
		updateLoanAdjustmentWarningStatus(dialog, rows);
	});
	updateLoanAdjustmentWarningStatus(dialog, rows);
}

function fetchLoanAdjustmentCandidates(frm) {
	return frappe.call({
		method: "informatics_custom_apps.ripl_customized_apps.payroll_loan_candidates.get_loan_adjustment_candidates",
		args: { payroll_entry: frm.doc.name },
		freeze: true,
		freeze_message: __("Checking loan repayments"),
	});
}

async function refreshLoanAdjustmentRows(dialog, currency) {
	const wrapper = dialog.fields_dict.employee_rows.$wrapper;
	const status = wrapper.find(".loan-adjustment-status");
	status.text(__("Refreshing loan repayment candidates…"));
	try {
		const response = await fetchLoanAdjustmentCandidates(dialog.frm);
		const rows = response.message?.employees || [];
		dialog.loan_adjustment_rows = rows;
		renderLoanAdjustmentRows(dialog, rows, currency);
	} catch (error) {
		status.text(error.message || __("Unable to refresh loan repayment candidates."));
		status.removeClass("text-muted").addClass("text-danger");
	}
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
			const negativeEmployees = getLoanAdjustmentNegativeEmployees(dialog, dialog.loan_adjustment_rows);
			if (negativeEmployees.length) {
				const details = negativeEmployees
					.map(({ employee, netAfterAdjustment }) => `${escapeLoanAdjustmentHTML(employee)} (${format_currency(netAfterAdjustment, frm.doc.currency)})`)
					.join("<br>");
				frappe.msgprint({
					title: __("Warning"),
					message: `${__("Net salary remains negative for the following employee(s) after HR loan adjustment:")}<br><br>${details}<br><br>${__("Adjust the HR loan amount or exclude the employee before continuing.")}`,
					indicator: "orange",
				});
				return;
			}
			adjustmentValues = collectLoanAdjustmentRows(dialog);
		} catch (error) {
			frappe.msgprint(error.message);
			return;
		}
		const primaryButton = dialog.get_primary_btn();
		primaryButton.prop("disabled", true);
		dialog.hide();
		try {
			frm.doc.loan_repayment_adjustment_data = JSON.stringify({
				adjustments: adjustmentValues.adjustments,
				excluded_employees: adjustmentValues.excludedEmployees,
			});
			await runStandardGetEmployeeDetails(frm, adjustmentValues.excludedEmployees);
			// frappe.show_alert({
			// 	message: __("Payroll employees are ready. Loan adjustments and logs will be created when you click Create Salary Slips."),
			// 	indicator: "blue",
			// });
		} catch (error) {
			frappe.msgprint(error.message || __("Unable to apply the loan adjustment."));
		}
	});
	dialog.set_secondary_action_label(__("Cancel"));
	dialog.set_secondary_action(() => dialog.hide());
	dialog.show();
	renderLoanAdjustmentRows(dialog, rows, currency);
}

function runStandardGetEmployeeDetails(frm, excludedEmployees = [], freeze = true) {
	return frappe
		.call({
			doc: frm.doc,
			method: "fill_employee_details",
			freeze,
			freeze_message: __("Fetching Employees"),
		})
		.then((r) => {
			if (r.docs?.[0]?.employees) {
				const excluded = new Set(excludedEmployees);
				frm.doc.employees = r.docs[0].employees.filter((row) => !excluded.has(row.employee));
				frm.doc.number_of_employees = frm.doc.employees.length;
				frm.refresh_field("employees");
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
		return fetchLoanAdjustmentCandidates(frm)
			.then((response) => {
				if (!response.message?.employees?.length) {
					return standardGetEmployeeDetails
						? standardGetEmployeeDetails(frm)
						: runStandardGetEmployeeDetails(frm);
				}
				showLoanAdjustmentDialog(frm, response.message);
			})
			.catch((error) => {
				frappe.msgprint(error.message || __("Unable to check loan repayments."));
			});
	},
});