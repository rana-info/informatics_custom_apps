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

// Change these two to match your app/module path
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
		this.suppress_date_change = false;

		// Select an existing ID to read/update it
		this.id_field = this.page.add_field({
			fieldname: "existing_log",
			label: "Existing Log (ID)",
			fieldtype: "Link",
			options: "CPU Plant Lab Log",
			change: () => this.load_by_id(),
		});

		// Or pick/change a date - loads that date's log if one exists,
		// otherwise starts a blank entry for a new one
		this.date_field = this.page.add_field({
			fieldname: "log_date",
			label: "Date",
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			change: () => {
				if (this.suppress_date_change) return;
				this.docname = null;
				this.id_field.set_value("");
				this.load_by_date();
			},
		});

		this.page.set_primary_action("Save", () => this.save(), "octicon octicon-check");
		this.page.add_inner_button("New", () => this.new_entry());

		this.$body = $('<div class="cpu-lab-log-wrapper" style="margin-top: 15px;"></div>').appendTo(
			this.page.body
		);

		this.load_by_date();
	}

	get_log_date() {
		return this.date_field.get_value() || frappe.datetime.get_today();
	}

	new_entry() {
		this.docname = null;
		this.suppress_date_change = true;
		this.id_field.set_value("");
		this.date_field.set_value(frappe.datetime.get_today());
		this.suppress_date_change = false;
		// get_lab_log returns a blank grid automatically when no record exists for the date
		this.load_by_date();
	}

	load_by_date() {
		frappe.call({
			method: `${APP_METHOD_PATH}.get_lab_log`,
			args: { log_date: this.get_log_date() },
			freeze: true,
			callback: (r) => {
				this.docname = r.message.name;
				this.suppress_date_change = true;
				this.id_field.set_value(this.docname || "");
				this.suppress_date_change = false;
				this.render(r.message.rows);
			},
		});
	}

	load_by_id() {
		const docname = this.id_field.get_value();
		if (!docname) {
			this.load_by_date();
			return;
		}

		frappe.call({
			method: `${APP_METHOD_PATH}.get_lab_log_by_name`,
			args: { docname },
			freeze: true,
			callback: (r) => {
				this.docname = r.message.name;
				this.suppress_date_change = true;
				this.date_field.set_value(r.message.log_date);
				this.suppress_date_change = false;
				this.render(r.message.rows);
			},
		});
	}

	render(rows) {
		this.rows = rows;

		const location_headers = LOCATIONS.map(
			(loc) => `<th style="min-width:110px;">${frappe.utils.escape_html(loc.label)}</th>`
		).join("");

		let body_rows = rows
			.map((row, idx) => {
				const cells = LOCATIONS.map((loc) => {
					const val = row[loc.field] === null || row[loc.field] === undefined ? "" : row[loc.field];
					return `<td>
						<input type="text"
							class="form-control cpu-cell"
							data-row="${idx}"
							data-field="${loc.field}"
							value="${val}"
							style="min-width:100px; text-align:right;">
					</td>`;
				}).join("");

				return `<tr>
					<td style="text-align:center;">${row.s_no}</td>
					<td>${frappe.utils.escape_html(row.parameter)}</td>
					<td>${frappe.utils.escape_html(row.unit || "")}</td>
					${cells}
				</tr>`;
			})
			.join("");

		this.$body.html(`
			<div class="table-responsive">
				<table class="table table-bordered table-sm cpu-lab-log-table">
					<thead>
						<tr>
							<th style="min-width:50px;">S.No</th>
							<th style="min-width:150px;">Description</th>
							<th style="min-width:70px;">Unit</th>
							${location_headers}
						</tr>
					</thead>
					<tbody>
						${body_rows}
					</tbody>
				</table>
			</div>
		`);

		this.$body.off("change", ".cpu-cell").on("change", ".cpu-cell", (e) => {
			const $el = $(e.currentTarget);
			const row_idx = $el.data("row");
			const field = $el.data("field");
			const value = $el.val();
			this.rows[row_idx][field] = value === "" ? null : parseFloat(value);
		});
	}

	save() {
		frappe.call({
			method: `${APP_METHOD_PATH}.save_lab_log`,
			args: {
				log_date: this.get_log_date(),
				rows: this.rows,
				docname: this.docname,
			},
			freeze: true,
			freeze_message: "Saving...",
			callback: (r) => {
				this.docname = r.message.name;
				this.suppress_date_change = true;
				this.id_field.set_value(this.docname);
				this.suppress_date_change = false;
				frappe.show_alert({ message: `Saved: ${this.docname}`, indicator: "green" });
			},
		});
	}
}