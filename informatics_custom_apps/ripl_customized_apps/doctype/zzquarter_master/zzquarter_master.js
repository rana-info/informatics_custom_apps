// Copyright (c) 2025, Monil Kamboj and contributors
// For license information, please see license.txt


frappe.ui.form.on('zzQuarter Master', {
	refresh: function(frm) {
		frm.set_query("cost_center", function() {
			return {
				filters: {
					"company":frm.doc.company,
					"is_group":0

				}
			};
		});
	}
});
