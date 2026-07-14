frappe.ui.form.on("Purchase Receipt", {
    refresh(frm) {

        if (frm.is_new() || frm.doc.docstatus !== 0) {
            return;
        }

        const allowed_roles = ["Master Admin", "System Manager"];

        const has_permission = allowed_roles.some(role =>
            frappe.user.has_role(role)
        );

        if (!has_permission) {
            return;
        }

        frm.add_custom_button(
            __("Rejected Warehouse"),
            () => {
                frappe.call({
                    method: "informatics_custom_apps.ripl_customized_apps.custom_buttons.update_rejected_warehouse",
                    args: {
                        purchase_receipt: frm.doc.name
                    },
                    freeze: true
                }).then(() => {
                    frm.reload_doc();
                });
            },
            __("Update")
        );
    }
});