// Plant list limited to the selected company (same query as the DMR page)
frappe.ui.form.on("Sugar DMR Season", {
	setup(frm) {
		frm.set_query("plant", () => ({
			query: "informatics_custom_apps.eth.page.dmr_(sugar).sugar_dmr.plant_query",
			filters: { company: frm.doc.company },
		}));
	},
});