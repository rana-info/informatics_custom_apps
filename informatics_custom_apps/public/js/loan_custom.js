frappe.ui.form.on('Loan', {
    refresh: function(frm) {
        if (frm.doc.status === "Closed" && frappe.user.has_role("HR Manager")) {
            frm.add_custom_button(__('Reopen Loan'), function() {
                frappe.prompt(
                    [
                        {
                            label: __("Reason / Remarks"),
                            fieldname: "reason",
                            fieldtype: "Small Text",
                            reqd: 1
                        }
                    ],
                    function(values) {
                        frappe.call({
                            method: "informatics_custom_apps.api.reopen_loan",
                            args: {
                                loan_name: frm.doc.name,
                                reason: values.reason
                            },
                            callback: function(r) {
                                if (!r.exc) {
                                    frappe.msgprint(__('Loan reopened successfully'));
                                    frm.reload_doc();
                                }
                            }
                        });
                    },
                    __("Reopen Loan"),
                    __("Submit")
                );
            }, __("Actions"));
        }
    }
});
