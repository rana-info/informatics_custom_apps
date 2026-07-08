// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.ui.form.on("Steam Raising Ratio", {
	onload(frm) {
		set_plant_query(frm);
	},

	company(frm) {
		(frm.doc.steam_ratio_item || []).forEach((row) => {
			row.plant = "";
		});
		frm.refresh_field("steam_ratio_item");

		set_plant_query(frm);
	},
});

function set_plant_query(frm) {
	frm.set_query("plant", "steam_ratio_item", function () {
		return {
			filters: {
				company: frm.doc.company,
			},
		};
	});
}