frappe.ui.form.on("PNL Settings", {
	refresh(frm) {
		refresh_section_options(frm);
	},
	onload_post_render(frm) {
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

frappe.ui.form.on("PNL Settings Account", {
	section_accounts_add(frm) {
		refresh_section_options(frm);
	},
	form_render(frm) {
		refresh_section_options(frm);
	},
});

function refresh_section_options(frm) {
	const grid_field = frm.fields_dict.section_accounts;
	if (!grid_field) return;

	const names = [
		...new Set(
			(frm.doc.sections || [])
				.map((r) => (r.section_name || "").trim())
				.filter(Boolean)
		),
	];
	const options = ["", ...names].join("\n");
	const grid = grid_field.grid;

	const meta_df = frappe.meta.docfield_map["PNL Settings Account"]?.section;
	if (meta_df) meta_df.options = options;

	grid.update_docfield_property("section", "options", options);

	(grid.grid_rows || []).forEach((row) => {
		const inline = row.on_grid_fields_dict && row.on_grid_fields_dict.section;
		if (inline) {
			inline.df.options = options;
			inline.refresh();
		}
		const form_ctrl = row.grid_form && row.grid_form.fields_dict && row.grid_form.fields_dict.section;
		if (form_ctrl) {
			form_ctrl.df.options = options;
			form_ctrl.refresh();
		}
	});
}