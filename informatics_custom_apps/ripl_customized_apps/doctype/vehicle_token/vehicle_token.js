// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.ui.form.on('Vehicle Token', {
    setup: function(frm) {
        frm.set_query('item', function() {
            return {
                filters: {
                    name: ['in', ['106444', '106446', '106448']]
                }
            };
        });
        frm.set_query('segment', function() {
            return {
                filters: {
                    name: ['not in', ['Common']]
                }
            };
        });
    },
    validate: function(frm) {
        const allowed_items = ['106444', '106446', '106448'];

        if (frm.doc.item && !allowed_items.includes(frm.doc.item)) {
            frappe.throw(__('Item Code must be one of: 106444, 106446, 106448'));
        }

        if (frm.doc.driver_contact && frm.doc.driver_contact.length !== 10) {
            frappe.throw(__('Please enter a valid 10-digit mobile number.'));
        }
    }
});