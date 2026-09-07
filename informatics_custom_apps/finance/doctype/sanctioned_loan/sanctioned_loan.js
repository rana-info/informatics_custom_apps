// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sanctioned Loan", {

    refresh(frm) {

        setTimeout(() => {
            set_loan_status_indicator(frm);
        }, 200);

        update_loan_dashboard(frm);

        if (frm.doc.docstatus === 1) {
            add_loan_actions(frm);
        }
    },

    validate(frm) {
        validate_disbursement_amount(frm);
        validate_repayment_amount(frm);
    },

    sanctioned_amount(frm) {
        validate_disbursement_amount(frm);
    },

    repayment_amount(frm) {
        validate_repayment_amount(frm);
    },

    loan_interest(frm) {
        validate_repayment_amount(frm);
    }
});


// ==========================================================
// ACTIONS
// ==========================================================

function add_loan_actions(frm) {

    frm.add_custom_button(
        __("Add Disbursement"),
        function () {
            add_disbursement(frm);
        },
        __("Actions")
    );

    frm.add_custom_button(
        __("Generate Repayment Schedule"),
        function () {
            generate_repayment_schedule(frm);
        },
        __("Actions")
    );

    frm.add_custom_button(
        __("Create Loan Repayment"),
        function () {
            create_loan_repayment(frm);
        },
        __("Actions")
    );
}


// ==========================================================
// ADD DISBURSEMENT
// ==========================================================

function add_disbursement(frm) {

    const dialog = new frappe.ui.Dialog({

        title: __("Add Loan Disbursement"),

        fields: [

            {
                fieldname: "disbursement_date",
                fieldtype: "Date",
                label: __("Disbursement Date"),
                default: frappe.datetime.get_today(),
                reqd: 1
            },

            {
                fieldname: "disbursement_amount",
                fieldtype: "Currency",
                label: __("Disbursement Amount"),
                reqd: 1
            },

            {
                fieldname: "reference_number",
                fieldtype: "Data",
                label: __("Reference Number")
            }

        ],

        primary_action_label: __("Add Disbursement"),

        primary_action(values) {

            const amount = flt(
                values.disbursement_amount
            );

            if (amount <= 0) {

                frappe.msgprint({
                    title: __("Invalid Amount"),
                    message: __(
                        "Disbursement Amount must be greater than zero."
                    ),
                    indicator: "red"
                });

                return;
            }

            frappe.call({

                method: "add_disbursement",

                doc: frm.doc,

                args: {
                    disbursement_date:
                        values.disbursement_date,

                    disbursement_amount:
                        amount,

                    reference_number:
                        values.reference_number
                },

                freeze: true,

                freeze_message:
                    __("Adding disbursement..."),

                callback(r) {

                    if (!r.exc) {

                        dialog.hide();

                        frm.reload_doc();

                        frappe.show_alert({
                            message: __(
                                "Disbursement added successfully."
                            ),
                            indicator: "green"
                        });
                    }
                }
            });
        }
    });

    dialog.show();
}

function set_loan_status_indicator(frm) {

    let status = frm.doc.loan_status;

    // For a new / unsaved document
    if (frm.is_new()) {
        status = "Draft";
    }

    // Submitted loan with no disbursement
    if (!status && frm.doc.docstatus === 0) {
        status = "Draft";
    }

    if (!status) {
        return;
    }

    let indicator = "blue";

    if (status === "Active") {
        indicator = "green";
    }
    else if (status === "Closed") {
        indicator = "green";
    }
    else if (status === "Draft") {
        indicator = "orange";
    }

    frm.page.set_indicator(
        __(status),
        indicator
    );
}

// ==========================================================
// GENERATE REPAYMENT SCHEDULE
// ==========================================================

function generate_repayment_schedule(frm) {

    frappe.confirm(

        __(
            "The pending repayment schedule will be recalculated. " +
            "Paid and partially paid entries will be preserved. Continue?"
        ),

        function () {

            frappe.call({

                method:
                    "generate_repayment_schedule",

                doc: frm.doc,

                freeze: true,

                freeze_message:
                    __("Generating repayment schedule..."),

                callback(r) {

                    if (!r.exc) {

                        frm.reload_doc();

                        frappe.show_alert({
                            message: __(
                                "Repayment schedule generated successfully."
                            ),
                            indicator: "green"
                        });
                    }
                }
            });
        }
    );
}


// ==========================================================
// CREATE LOAN REPAYMENT
// ==========================================================

function create_loan_repayment(frm) {

    frappe.call({

        method:
            "get_next_pending_repayment",

        doc: frm.doc,

        freeze: true,

        freeze_message:
            __("Loading repayment details..."),

        callback(r) {

            if (r.exc) {
                return;
            }

            if (!r.message) {

                frappe.msgprint({
                    title: __("No Pending Repayment"),
                    message: __(
                        "There are no pending repayment schedule entries."
                    ),
                    indicator: "green"
                });

                return;
            }

            const schedule = r.message;

            frappe.new_doc(
                "zzLoan Repayment",
                {
                    sanctioned_loan: frm.doc.name,
                    bank: frm.doc.bank,
                    loan_type: frm.doc.loan_type,
                    company: frm.doc.company,
                    plant: frm.doc.plant,

                    schedule_reference: schedule.name,
                    due_date: schedule.payment_date,

                    payment_date:
                        frappe.datetime.get_today(),

                    principal_paid:
                        flt(schedule.principal_amount),

                    interest_paid:
                        flt(schedule.interest_amount),

                    total_paid:
                        flt(schedule.total_payment)
                }
            );
        }
    });
}


// ==========================================================
// VALIDATION
// ==========================================================

function validate_disbursement_amount(frm) {

    let total_disbursed = 0;

    (frm.doc.loan_disbursements || []).forEach(
        row => {
            total_disbursed += flt(
                row.disbursement_amount
            );
        }
    );

    if (
        flt(frm.doc.sanctioned_amount) &&
        total_disbursed > flt(frm.doc.sanctioned_amount)
    ) {

        frappe.msgprint({
            title: __("Invalid Disbursement"),
            message: __(
                "Total Disbursed Amount cannot exceed Sanctioned Amount."
            ),
            indicator: "red"
        });

        frappe.validated = false;
    }
}


function validate_repayment_amount(frm) {

    if (flt(frm.doc.loan_interest) < 0) {

        frappe.msgprint({
            title: __("Invalid Interest"),
            message: __("Loan Interest cannot be negative."),
            indicator: "red"
        });

        frappe.validated = false;
    }

    if (
        flt(frm.doc.repayment_amount) &&
        flt(frm.doc.repayment_amount) <= 0
    ) {

        frappe.msgprint({
            title: __("Invalid Repayment Amount"),
            message: __(
                "Repayment Amount must be greater than zero."
            ),
            indicator: "red"
        });

        frappe.validated = false;
    }
}


// ==========================================================
// DASHBOARD / STATS
// ==========================================================

function update_loan_dashboard(frm) {

    if (!frm.doc.name || frm.is_new()) {
        return;
    }

    if (frm.doc.docstatus === 1) {

        frappe.call({
            method: "get_loan_summary",
            doc: frm.doc,

            callback(r) {

                if (r.exc || !r.message) {
                    return;
                }

                const summary = r.message;

                // Remove default Submitted headline
                frm.dashboard.clear_headline();

                // Show Loan Status instead
                if (summary.loan_status) {
                    frm.dashboard.set_headline(
                        __("{0}", [summary.loan_status]),
                        summary.loan_status === "Closed"
                            ? "green"
                            : "blue"
                    );
                }

                // Outstanding Amount
                frm.dashboard.add_indicator(
                    __("Outstanding: {0}", [
                        format_currency(
                            flt(summary.outstanding_amount)
                        )
                    ]),
                    flt(summary.outstanding_amount) > 0
                        ? "orange"
                        : "green"
                );

                // Paid Amount
                frm.dashboard.add_indicator(
                    __("Paid Amount: {0}", [
                        format_currency(
                            flt(summary.paid_amount)
                        )
                    ]),
                    flt(summary.paid_amount) > 0
                        ? "green"
                        : "gray"
                );
            }
        });
    }
}