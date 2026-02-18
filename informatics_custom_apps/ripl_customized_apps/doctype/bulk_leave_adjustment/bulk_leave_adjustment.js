// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bulk Leave Adjustment", {
	refresh(frm) {
    frm.fields_dict["employee"].grid.get_field("leave_type").get_query = function(doc, cdt, cdn) {
        return {
            filters: {
                name: ["in", [
                    "Casual Leave-Sugar",
                    "Earned Leave",
                    "Sick Leave-Sugar",
                    "Sick Leave - Distillery"
                ]]
            }
        };
    };
	},
    company(frm) {
		// Parent field filter
		frm.set_query("plant", function () {
			return {
				filters: {
					company: frm.doc.company
				}
			};
		});

		// Child table field filter
		frm.fields_dict["employee"].grid.get_field("employee").get_query = function(doc, cdt, cdn) {
			return {
				filters: {
					company: doc.company,
                    branch:doc.plant
				}
			};
		};
	}
});
