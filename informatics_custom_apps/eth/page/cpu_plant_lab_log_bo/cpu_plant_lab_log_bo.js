const LOCATIONS = [
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
	wrapper.cpu_lab_log_instance = new CPULabLog(page);
};

frappe.pages["cpu-plant-lab-log-bo"].on_page_show = function (wrapper) {
	if (wrapper.cpu_lab_log_instance) {
		wrapper.cpu_lab_log_instance.on_selection_change();
	}
};

class CPULabLog {
	constructor(page) {
		this.page = page;
		this.docname = null;
		this.rows = [];
		this.loading = false;
		this.request_seq = 0;

		this.page.set_primary_action("Save", () => this.save());
		this.page.set_secondary_action("New", () => this.new_entry());

		this.company_field = this.page.add_field({
			fieldname: "company",
			label: "Company",
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
			change: () => {
				if (this.loading) return;
				this.on_company_change();
			},
		});

		this.plant_field = this.page.add_field({
			fieldname: "plant",
			label: "Plant",
			fieldtype: "Link",
			options: "Branch",
			reqd: 1,
			get_query: () => {
				const company = this.company_field.get_value();
				return company ? { filters: { company } } : {};
			},
			change: () => {
				if (this.loading) return;
				this.on_selection_change();
			},
		});

		this.date_field = this.page.add_field({
			fieldname: "log_date",
			label: "Date",
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			change: () => {
				if (this.loading) return;
				this.on_selection_change();
			},
		});

		this.$wrap = $(`
			<div class="cpu-lab-log-wrapper" style="padding: 10px 0;">
				<style>
					.cpu-lab-log-wrapper table tbody tr.cpu-row-even { background: #ffffff; }
					.cpu-lab-log-wrapper table tbody tr.cpu-row-odd { background: #f2f6fb; }
					.cpu-lab-log-wrapper table tbody tr:hover { background: #fff3cd !important; }
					.cpu-lab-log-wrapper table tbody tr td:first-child,
					.cpu-lab-log-wrapper table tbody tr td:nth-child(2),
					.cpu-lab-log-wrapper table tbody tr td:nth-child(3) {
						font-weight: 600;
						background: #e9edf2;
					}
					.cpu-lab-log-wrapper table tbody tr:hover td:first-child,
					.cpu-lab-log-wrapper table tbody tr:hover td:nth-child(2),
					.cpu-lab-log-wrapper table tbody tr:hover td:nth-child(3) {
						background: #ffe9a8;
					}
				</style>
				<div id="cpu-status" class="text-muted" style="margin-bottom:10px;"></div>
				<div id="cpu-table-holder"></div>
			</div>
		`);
		this.page.body.append(this.$wrap);

		this.$status = this.$wrap.find("#cpu-status");
		this.$table_holder = this.$wrap.find("#cpu-table-holder");

		this.load_user_defaults();
	}

	set_status(text, is_error) {
		this.$status.text(text || "");
		this.$status.css("color", is_error ? "#d1242f" : "#888");
	}

	load_user_defaults() {
		frappe.call({
			method: `${APP_METHOD_PATH}.get_user_default_company_plant`,
			callback: (r) => {
				const defaults = (r && r.message) || {};
				if (!defaults.company && !defaults.plant) return;

				this.loading = true;
				if (defaults.company) this.company_field.set_value(defaults.company);
				this.loading = false;
				this.company_field.refresh();

				frappe.after_ajax(() => {
					this.loading = true;
					if (defaults.plant) this.plant_field.set_value(defaults.plant);
					this.loading = false;
					this.plant_field.refresh();
					this.on_selection_change();
				});
			},
			error: () => {
				this.set_status("Could not load default company/plant.", true);
			},
		});
	}

	get_selection() {
		return {
			company: this.company_field.get_value(),
			plant: this.plant_field.get_value(),
			log_date: this.date_field.get_value(),
		};
	}

	on_company_change() {
		this.docname = null;
		this.loading = true;
		this.plant_field.set_value("");
		this.loading = false;
		this.plant_field.refresh();
		this.$table_holder.empty();
	}

	on_selection_change() {
		const { company, plant, log_date } = this.get_selection();
		this.docname = null;
		if (!company || !plant || !log_date) {
			this.$table_holder.empty();
			return;
		}
		this.load_log(log_date, company, plant);
	}

	new_entry() {
		this.docname = null;
		this.loading = true;
		this.date_field.set_value(frappe.datetime.get_today());
		this.loading = false;
		this.on_selection_change();
	}

	load_log(log_date, company, plant) {
		const seq = ++this.request_seq;
		this.set_status("Loading...");
		frappe.call({
			method: `${APP_METHOD_PATH}.get_lab_log`,
			args: { log_date, company, plant },
			callback: (r) => {
				if (seq !== this.request_seq) return;
				this.set_status("");
				if (!r || !r.message) {
					this.set_status("No data returned.", true);
					return;
				}
				this.docname = r.message.name;
				this.render(r.message.rows);
			},
			error: () => {
				if (seq !== this.request_seq) return;
				this.set_status("Failed to load log.", true);
			},
		});
	}

	render(rows) {
		this.rows = rows;

		const location_headers = LOCATIONS.map(
			(loc) =>
				`<th style="min-width:110px; padding:6px; background:#f5f5f5; border:1px solid #ddd;">${frappe.utils.escape_html(
					loc.label
				)}</th>`
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
							value="${frappe.utils.escape_html(String(val))}"
							style="width:100%; min-width:90px; text-align:right; border:1px solid transparent; padding:6px; box-sizing:border-box; background:transparent;">
					</td>`;
				}).join("");

				const row_class = idx % 2 === 0 ? "cpu-row-even" : "cpu-row-odd";
				return `<tr class="${row_class}">
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
			this.rows[$el.data("row")][$el.data("field")] = $el.val();
		});
	}

	save() {
		const { company, plant, log_date } = this.get_selection();
		if (!company || !plant || !log_date) {
			frappe.msgprint("Select Company, Plant and Date first.");
			return;
		}
		if (!this.rows || !this.rows.length) {
			frappe.msgprint("Nothing to save yet - wait for the table to load first.");
			return;
		}

		this.set_status("Saving...");
		frappe.call({
			method: `${APP_METHOD_PATH}.save_lab_log`,
			args: {
				log_date,
				company,
				plant,
				rows: this.rows,
				docname: this.docname,
			},
			callback: (r) => {
				this.set_status("");
				if (!r || !r.message) {
					this.set_status("Save did not return a result.", true);
					return;
				}
				this.docname = r.message.name;
				frappe.show_alert({ message: `Saved: ${this.docname}`, indicator: "green" });
			},
			error: (r) => {
				this.set_status("Save failed.", true);
				frappe.msgprint({
					title: "Save failed",
					indicator: "red",
					message:
						(r && r.responseJSON && (r.responseJSON._server_messages || r.responseJSON.exc)) ||
						"Please try again or check with your administrator.",
				});
			},
		});
	}
}