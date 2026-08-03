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

    vehicle_number: function(frm) {
        if (frm.doc.vehicle_number) {
            frm.set_value('vehicle_number', frm.doc.vehicle_number.toUpperCase().replace(/\s+/g, ''));
        }
    },

    validate: function(frm) {
        const allowed_items = ['106444', '106446', '106448'];

        if (frm.doc.vehicle_number) {
            frm.doc.vehicle_number = frm.doc.vehicle_number.toUpperCase().replace(/\s+/g, '');
            const vehicle_regex = /^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}$/;
            if (!vehicle_regex.test(frm.doc.vehicle_number)) {
                frappe.throw(__('Invalid Vehicle Number format. Expected e.g. KA01AB1234'));
            }
        }

        if (frm.doc.item && !allowed_items.includes(frm.doc.item)) {
            frappe.throw(__('Item Code must be one of: 106444, 106446, 106448'));
        }

        if (frm.doc.driver_contact && !/^[6-9]\d{9}$/.test(String(frm.doc.driver_contact))) {
            frappe.throw(__('Please enter a valid 10-digit mobile number.'));
        }
    }
});