frappe.ui.form.on("Sales Invoice", {
    refresh(frm) {

        if (frm.doc.docstatus == 2) {
            return;
        }

        if (
            !frappe.user.has_role("Master Admin") &&
            !frappe.user.has_role("SMT Role")
        ) {
            return;
        }

        frm.add_custom_button(
            __("Update Transporter"),
            () => {

                let d = new frappe.ui.Dialog({
                    title: __("Update Transporter"),
                    fields: [
                        {
                            fieldname: "transporter",
                            label: __("Transporter"),
                            fieldtype: "Link",
                            options: "Supplier",
                            reqd: 1,
                            filters: {
                                is_transporter: 1,
                                disabled: 0
                            }
                        }
                    ],
                    primary_action_label: __("Update"),
                    primary_action(values) {

                        frappe.call({
                            method: "informatics_custom_apps.ripl_customized_apps.custom_buttons.update_transporter",
                            args: {
                                sales_invoice: frm.doc.name,
                                transporter: values.transporter
                            },
                            freeze: true,
                            freeze_message: __("Updating Transporter...")
                        }).then(() => {
                            d.hide();
                            frm.reload_doc();
                        });

                    }
                });

                d.show();

            },
            __("Update")
        );

    }
});