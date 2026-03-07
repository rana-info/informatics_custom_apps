frappe.ui.form.on('Asset', {
    refresh: function(frm) {
        if (!frm.doc.available_for_use_date || !frm.doc.purchase_date && frappe.user.has_role("Master Admin")) {
            frm.add_custom_button(__('Add Date'), function() {
                frappe.prompt(
                    [
                        {
                            label: __("Required Date"),
                            fieldname: "required_date",
                            fieldtype: "Date",
                            reqd: 1
                        }
                    ],
                    function(values) {
                        frappe.call({
                            method: "informatics_custom_apps.api.add_asset_date",
                            args: {
                                docname: frm.doc.name,
                                required_date: values.required_date
                            },
                            callback: function(r) {
                                if (!r.exc) {
                                    frappe.show_alert({
                                        message: __('Date Added Successfully'),
                                        indicator: 'green'
                                    }, 7); // alert timeout (in seconds)

                                    frm.reload_doc();
                                }
                            }
                        });
                    },
                    __("Add Date"),
                    __("Submit")
                );
            }, __("Actions"));
        }
    }
});
