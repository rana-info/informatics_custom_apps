const LOCATIONS = [
	{ field: "cpu_feed", label: "CPU Feed" },
	{ field: "eqt_tank", label: "EQT-Tank" },
	{ field: "ct_tank", label: "CT-Tank" },
	{ field: "reactor_inlet", label: "Reactor inlet" },
	{ field: "reactor_outlet", label: "Reactor Outlet" },
	{ field: "aeration_tank", label: "Aeration Tank" },
	{ field: "sec_clarifier_outlet", label: "Sec. clarifier Outlet" },
	{ field: "hrscc_outlet", label: "HRSCC Outlet" },
	{ field: "mgf_outlet", label: "MGF Outlet" },
	{ field: "acf_outlet", label: "ACF outlet" },
	{ field: "uv_outlet", label: "UV - Outlet" },
];

const APP_METHOD_PATH = "informatics_custom_apps.eth.page.cpu_plant_lab_log_bo.cpu_plant_lab_log_bo";

frappe.pages["cpu-plant-lab-log-bo"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "CPU Plant Lab Log Book",
		single_column: true,
	});
	new CPULabLog(page);
};

class CPULabLog {
	constructor(page) {
		this.page = page;
		this.docname = null;
		this.rows = [];

		this.page.set_primary_action("Save", () => this.save());
		this.page.set_secondary_action("New", () => this.new_entry());

		// Build everything as plain HTML - no frappe field controls involved,
		// so there is nothing that can silently fail to initialize.
		this.$wrap = $(`
			<div class="cpu-lab-log-wrapper" style="padding: 10px 0;">
				<div id="cpu-self-test" class="alert alert-info" style="margin-bottom:15px;">
					Checking connection to server...
				</div>
				<div style="display:flex; gap:20px; align-items:flex-end; margin-bottom:15px; flex-wrap:wrap;">
					<div>
						<label style="display:block; font-weight:600; margin-bottom:4px;">Existing Log (ID)</label>
						<select id="cpu-id-select" class="form-control" style="min-width:220px;">
							<option value="">-- New Entry --</option>
						</select>
					</div>
					<div>
						<label style="display:block; font-weight:600; margin-bottom:4px;">Date</label>
						<input type="date" id="cpu-date-input" class="form-control" style="min-width:160px;">
					</div>
					<div id="cpu-status" class="text-muted"></div>
				</div>
				<div id="cpu-table-holder"></div>
			</div>
		`);

		this.page.body.empty().append(this.$wrap);

		this.$id_select = this.$wrap.find("#cpu-id-select");
		this.$date_input = this.$wrap.find("#cpu-date-input");
		this.$status = this.$wrap.find("#cpu-status");
		this.$table_holder = this.$wrap.find("#cpu-table-holder");
		this.$self_test = this.$wrap.find("#cpu-self-test");

		this.$date_input.val(frappe.datetime.get_today());

		this.$id_select.on("change", () => this.on_id_change());
		this.$date_input.on("change", () => this.on_date_change());

		this.run_self_test();
	}

	set_status(text, is_error) {
		this.$status.text(text || "");
		this.$status.css("color", is_error ? "#d1242f" : "#888");
	}

	run_self_test() {
		frappe.call({
			method: `${APP_METHOD_PATH}.ping`,
			callback: (r) => {
				if (r && r.message && r.message.ok) {
					this.$self_test.remove();
					this.load_id_list();
					this.load_by_date(this.$date_input.val());
				} else {
					this.$self_test
						.removeClass("alert-info")
						.addClass("alert-danger")
						.text("Server responded but with an unexpected result. Check console.");
					console.error("[cpu-lab-log] ping unexpected response:", r);
				}
			},
			error: (r) => {
				this.$self_test
					.removeClass("alert-info")
					.addClass("alert-danger")
					.html(
						"Cannot reach the server method <code>" +
							APP_METHOD_PATH +
							".ping</code>. This means either:<br>" +
							"1) the path in APP_METHOD_PATH doesn't match your app/module folder, or<br>" +
							"2) <code>bench build</code> / <code>bench clear-cache</code> hasn't been run since this file was added, or<br>" +
							"3) there's a Python error in cpu_plant_lab_log_bo.py preventing it from loading.<br>" +
							"Open the browser Network tab, find the failed request, and check the response body for the traceback."
					);
				console.error("[cpu-lab-log] ping FAILED:", r);
			},
		});
	}

	load_id_list() {
		frappe.call({
			method: `${APP_METHOD_PATH}.list_existing_logs`,
			callback: (r) => {
				const logs = (r && r.message) || [];
				this.$id_select.find("option:not(:first)").remove();
				logs.forEach((log) => {
					this.$id_select.append(
						`<option value="${log.name}">${log.name} (${log.log_date})</option>`
					);
				});
			},
			error: (r) => {
				console.error("[cpu-lab-log] list_existing_logs FAILED:", r);
			},
		});
	}

	new_entry() {
		this.docname = null;
		this.$id_select.val("");
		this.$date_input.val(frappe.datetime.get_today());
		this.load_by_date(this.$date_input.val());
	}

	on_date_change() {
		this.docname = null;
		this.$id_select.val("");
		this.load_by_date(this.$date_input.val());
	}

	on_id_change() {
		const docname = this.$id_select.val();
		if (!docname) {
			this.load_by_date(this.$date_input.val());
			return;
		}
		this.load_by_id(docname);
	}

	load_by_date(log_date) {
		this.set_status("Loading...");
		frappe.call({
			method: `${APP_METHOD_PATH}.get_lab_log`,
			args: { log_date },
			callback: (r) => {
				this.set_status("");
				if (!r || !r.message) {
					this.set_status("Empty response - see console.", true);
					return;
				}
				this.docname = r.message.name;
				this.$id_select.val(this.docname || "");
				this.render(r.message.rows);
			},
			error: (r) => {
				this.set_status("Failed to load - see console.", true);
				console.error("[cpu-lab-log] get_lab_log FAILED:", r);
			},
		});
	}

	load_by_id(docname) {
		this.set_status("Loading...");
		frappe.call({
			method: `${APP_METHOD_PATH}.get_lab_log_by_name`,
			args: { docname },
			callback: (r) => {
				this.set_status("");
				if (!r || !r.message) {
					this.set_status("Empty response - see console.", true);
					return;
				}
				this.docname = r.message.name;
				this.$date_input.val(r.message.log_date);
				this.render(r.message.rows);
			},
			error: (r) => {
				this.set_status("Failed to load - see console.", true);
				console.error("[cpu-lab-log] get_lab_log_by_name FAILED:", r);
			},
		});
	}

	render(rows) {
		this.rows = rows;

		const location_headers = LOCATIONS.map(
			(loc) => `<th style="min-width:110px; padding:6px; background:#f5f5f5; border:1px solid #ddd;">${frappe.utils.escape_html(loc.label)}</th>`
		).join("");

		const body_rows = rows
			.map((row, idx) => {
				const cells = LOCATIONS.map((loc) => {
					const val = row[loc.field] === null || row[loc.field] === undefined ? "" : row[loc.field];
					return `<td style="border:1px solid #ddd; padding:2px;">
						<input type="text"
							class="cpu-cell"
							data-row="${idx}"
							data-field="${loc.field}"
							value="${val}"
							style="width:100%; min-width:90px; text-align:right; border:1px solid transparent; padding:6px; box-sizing:border-box;">
					</td>`;
				}).join("");

				return `<tr>
					<td style="text-align:center; border:1px solid #ddd; padding:6px;">${row.s_no}</td>
					<td style="border:1px solid #ddd; padding:6px;">${frappe.utils.escape_html(row.parameter)}</td>
					<td style="border:1px solid #ddd; padding:6px;">${frappe.utils.escape_html(row.unit || "")}</td>
					${cells}
				</tr>`;
			})
			.join("");

		this.$table_holder.html(`
			<div style="overflow-x:auto;">
				<table style="border-collapse:collapse; width:100%;">
					<thead>
						<tr>
							<th style="min-width:50px; padding:6px; background:#f5f5f5; border:1px solid #ddd;">S.No</th>
							<th style="min-width:150px; padding:6px; background:#f5f5f5; border:1px solid #ddd;">Description</th>
							<th style="min-width:70px; padding:6px; background:#f5f5f5; border:1px solid #ddd;">Unit</th>
							${location_headers}
						</tr>
					</thead>
					<tbody>${body_rows}</tbody>
				</table>
			</div>
		`);

		this.$table_holder.off("input", ".cpu-cell").on("input", ".cpu-cell", (e) => {
			const $el = $(e.currentTarget);
			const row_idx = $el.data("row");
			const field = $el.data("field");
			this.rows[row_idx][field] = $el.val();
		});
	}

	save() {
		if (!this.rows || !this.rows.length) {
			frappe.msgprint("Nothing to save yet - wait for the table to load first.");
			return;
		}

		this.set_status("Saving...");
		frappe.call({
			method: `${APP_METHOD_PATH}.save_lab_log`,
			args: {
				log_date: this.$date_input.val(),
				rows: this.rows,
				docname: this.docname,
			},
			callback: (r) => {
				this.set_status("");
				if (!r || !r.message) {
					this.set_status("Empty response on save - see console.", true);
					return;
				}
				this.docname = r.message.name;
				this.$id_select.val(this.docname);
				this.load_id_list();
				frappe.show_alert({ message: `Saved: ${this.docname}`, indicator: "green" });
			},
			error: (r) => {
				this.set_status("Save failed - see console.", true);
				console.error("[cpu-lab-log] save_lab_log FAILED:", r);
				frappe.msgprint({
					title: "Save failed",
					indicator: "red",
					message:
						(r && r.responseJSON && (r.responseJSON._server_messages || r.responseJSON.exc)) ||
						"Check the browser console and Network tab.",
				});
			},
		});
	}
}