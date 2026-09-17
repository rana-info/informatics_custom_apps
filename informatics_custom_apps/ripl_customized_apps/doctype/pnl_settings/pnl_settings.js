// Copyright (c) 2026, Rana Informatics and contributors
// For license information, please see license.txt

frappe.ui.form.on("PNL Settings", {
	refresh(frm) {
		refresh_section_options(frm);
	},
});

frappe.ui.form.on("PNL Settings Section", {
	section_name(frm) {
		refresh_section_options(frm);
	},
	sections_add(frm) {
		refresh_section_options(frm);
	},
	sections_remove(frm) {
		refresh_section_options(frm);
	},
});

function refresh_section_options(frm) {
	const options = (frm.doc.sections || [])
		.map((row) => row.section_name)
		.filter((name) => !!name);

	frm.fields_dict.section_accounts.grid.update_docfield_property(
		"section",
		"options",
		options.join("\n")
	);
	frm.fields_dict.section_accounts.grid.refresh();
}