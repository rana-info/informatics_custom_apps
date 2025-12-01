// Copyright (c) 2025, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.ui.form.on('zzDeputation Request', {
	setup:function(frm){
		frm.set_query("employee", erpnext.queries.employee);
	},
    onload: function(frm) {
        frm.set_query("employee", function() {
            return {filters: {
					"status": "Active",
				}};
            });
        },
    from_date: function(frm) {
    let today = frappe.datetime.nowdate();
    let month_start = frappe.datetime.month_start(today);
    let from = frm.doc.from_date;
    if (from && from < month_start) {
        frappe.msgprint("From Date cannot be earlier than the first day of the current month.");
        frm.set_value("from_date", "");
    }
    },
    to_date: function(frm) {
    let from = frm.doc.from_date;
    let to_date = frm.doc.to_date;
    if (from && to_date< from) {
        frappe.msgprint("To Date cannot be earlier than the from date.");
        frm.set_value("to_date", "");
    }
    },
	to_plant: function(frm) {
		if (frm.doc.to_plant == frm.doc.plant){
			frappe.msgprint("To Plant cannot be same as From Plant");
			frm.set_value("to_plant", "");
		}
	},
	plant: function(frm) {
		frm.set_query("employee", function() {
			return {
				filters: {
					"branch":frm.doc.plant
				}
			};
		});
	},
	company: function(frm) {
		frm.set_query("plant", function() {
			return {
				filters: {
					"company":frm.doc.company
				}
			};
		});
	},
	employee: function(frm) {
		frm.set_query("company", function() {
			return {
				filters: {
					"name":frm.doc.company
				}
			};
		});
		frm.set_query("plant", function() {
			return {
				filters: {
					"name":frm.doc.plant
				}
			};
		});
	},
});
