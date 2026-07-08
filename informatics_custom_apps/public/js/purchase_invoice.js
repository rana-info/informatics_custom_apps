frappe.ui.form.on("Purchase Invoice", {
    refresh(frm) {

        if (frm.doc.docstatus !== 1) {
            return;
        }

        const allowed_roles = ["Master Admin"];

        const has_permission = allowed_roles.some(role =>
            frappe.user.has_role(role)
        );

        if (!has_permission) {
            return;
        }

        frm.add_custom_button(
            __("ITC Claim Period"),
            () => {

                frappe.prompt(
                    [
                        {
                            fieldname: "itc_claim_period",
                            label: "ITC Claim Period",
                            fieldtype: "Data",
                            reqd: 1,
                            default: frm.doc.itc_claim_period,
                            description: __("Enter in MMYYYY format (e.g. 072026)")
                        }
                    ],
                    (values) => {

                        frappe.call({
                            method: "informatics_custom_apps.ripl_customized_apps.custom_buttons.update_itc_claim_period",
                            args: {
                                purchase_invoice: frm.doc.name,
                                itc_claim_period: values.itc_claim_period
                            },
                            freeze: true,
                            freeze_message: __("Updating ITC Claim Period...")
                        }).then(() => {
                            frm.reload_doc();
                        });

                    },
                    __("Update ITC Claim Period"),
                    __("Save")
                );

            },
            __("Update")
        );
    }
});