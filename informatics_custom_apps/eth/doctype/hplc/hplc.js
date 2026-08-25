frappe.ui.form.on("HPLC", {
	refresh(frm) {
		frm._hplc_last_urls = frm._hplc_last_urls || {};
		frm._hplc_last_urls.sugar_profile = frm.doc.sugar_profile;
		frm._hplc_last_urls.organic_and_alcohol_profile = frm.doc.organic_and_alcohol_profile;
	},

	sugar_profile(frm) {
		handle_attach_change(frm, "sugar_profile");
	},

	organic_and_alcohol_profile(frm) {
		handle_attach_change(frm, "organic_and_alcohol_profile");
	},
});

function handle_attach_change(frm, fieldname) {
	const old_url = frm._hplc_last_urls && frm._hplc_last_urls[fieldname];
	const new_url = frm.doc[fieldname];

	if (!new_url) {
		if (!frm.is_new() && old_url) {
			clear_hplc_data(frm, fieldname, old_url);
		}
	} else if (!frm.is_new()) {
		parse_hplc_pdf(frm, fieldname);
	} else {
		frappe.dom.freeze(__("Saving document so the PDF can be linked..."));
		frm.save().then(() => {
			frappe.dom.unfreeze();
			parse_hplc_pdf(frm, fieldname);
		}).catch(() => {
			frappe.dom.unfreeze();
			frappe.msgprint(__("Could not save the document automatically. Please save manually and re-attach the file."));
		});
	}

	frm._hplc_last_urls = frm._hplc_last_urls || {};
	frm._hplc_last_urls[fieldname] = new_url;
}

function parse_hplc_pdf(frm, fieldname) {
	const file_url = frm.doc[fieldname];

	frappe.call({
		method: "informatics_custom_apps.eth.doctype.hplc.hplc.parse_hplc_pdf",
		args: {
			docname: frm.doc.name,
			fieldname: fieldname,
			file_url: file_url,
		},
		freeze: true,
		freeze_message: __("Parsing HPLC report..."),
		callback: function (r) {
			if (r.message) {
				frappe.show_alert({
					message: __("Parsed {0} row(s) from {1}", [
						(r.message.rows || []).length,
						fieldname,
					]),
					indicator: "green",
				});
				frm.reload_doc();
			}
		},
	});
}

function clear_hplc_data(frm, fieldname, old_file_url) {
	frappe.call({
		method: "informatics_custom_apps.eth.doctype.hplc.hplc.clear_hplc_data",
		args: {
			docname: frm.doc.name,
			fieldname: fieldname,
			file_url: old_file_url,
		},
		freeze: true,
		freeze_message: __("Removing HPLC data..."),
		callback: function (r) {
			frappe.show_alert({
				message: __("Removed {0} row(s) linked to {1}", [
					(r.message && r.message.removed) || 0,
					fieldname,
				]),
				indicator: "orange",
			});
			frm.reload_doc();
		},
	});
}