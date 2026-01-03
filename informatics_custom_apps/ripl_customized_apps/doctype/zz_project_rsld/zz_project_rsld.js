// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.ui.form.on("zz Project RSLD", {
	refresh(frm) {
        if(frm.doc.task_id){
             frm.add_custom_button(__('Add Message'), () => {
            show_message_dialog(frm);
        });
        }
	function show_message_dialog(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __('Send Message'),
        fields: [
            {
                fieldname: 'message',
                fieldtype: 'Small Text',
                label: __('Message'),
                reqd: 1
            }
        ],
        primary_action_label: __('Send'),   
        primary_action(values) {
            frappe.call({
                method: 'add_message',
                doc: frm.doc,
                args: {
                    message: values.message   
                },
                callback() {
                    frappe.msgprint(__('Message added'));
                    dialog.hide();
                    frm.reload_doc();
                }
            });
        }
    });

    dialog.show();
}
    }
});
