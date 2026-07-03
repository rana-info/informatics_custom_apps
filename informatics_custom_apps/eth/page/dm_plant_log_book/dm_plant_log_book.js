const COLUMN_GROUPS = [
	{
		group: null,
		cols: [
			{ field: "started_time", label: "Started Time in Hours" },
			{ field: "stopped_time", label: "Stoped Times in Hours" },
			{ field: "discharging_time", label: "Discharging Time in Hours" },
			{ field: "total_running_hours", label: "Total Running in Hours" },
		],
	},
	{
		group: "D.M.F",
		cols: [
			{ field: "dmf_inlet_turbidity", label: "Inlet Turbidity (NTU)" },
			{ field: "dmf_outlet_turbidity", label: "Outlet Turbidity (NTU)" },
			{ field: "dmf_inlet_pr", label: "Inlet P.R. KG/CM2" },
			{ field: "dmf_outlet_pr", label: "Outlet P.R. KG/CM2" },
		],
	},
	{
		group: "S.A.C",
		cols: [
			{ field: "sac_inlet_pr", label: "Inlet P.R. KG/CM2" },
			{ field: "sac_outlet_pr", label: "Outlet P.R. KG/CM2" },
			{ field: "sac_ph", label: "PH" },
			{ field: "sac_th", label: "T.H" },
			{ field: "sac_fma", label: "FMA" },
		],
	},
	{
		group: "W.B.A",
		cols: [
			{ field: "wba_inlet_pr", label: "Inlet P.R. KG/CM2" },
			{ field: "wba_outlet_pr", label: "Outlet P.R. KG/CM2" },
			{ field: "wba_outlet_pr_2", label: "Outlet PR KG/CM2" },
		],
	},
	{
		group: "S.B.A",
		cols: [
			{ field: "sba_inlet_pr", label: "Inlet P.R. KG/CM2" },
			{ field: "sba_outlet_pr", label: "Outlet P.R. KG/CM2" },
			{ field: "sba_outlet_ph", label: "Outlet PH" },
			{ field: "sba_outlet_conductivity", label: "Outlet Conductivity /CM" },
			{ field: "sba_outlet_silica", label: "Outlet Silica MG/LTR" },
		],
	},
	{
		group: "Mixed Bed",
		cols: [
			{ field: "mb_inlet_pr", label: "Inlet P.R. KG/CM2" },
			{ field: "mb_outlet_pr", label: "Outlet P.R. KG/CM2" },
			{ field: "mb_before_dosing_ph", label: "Before Dosing PH" },
			{ field: "mb_after_dosing_ph", label: "After Dosing PH" },
			{ field: "mb_outlet_conductivity", label: "Outlet Conductivity /CM" },
			{ field: "mb_outlet_silica", label: "Outlet Silica MG/LTR" },
		],
	},
	{
		group: null,
		cols: [
			{ field: "storage_tank_position", label: "Storage Tank Position" },
			{ field: "remarks", label: "Remarks" },
		],
	},
];

const ALL_FIELDS = COLUMN_GROUPS.flatMap((g) => g.cols.map((c) => c.field));
const APP_METHOD_PATH = "informatics_custom_apps.eth.page.dm_plant_log_book.dm_plant_log_book";

frappe.pages["dm-plant-log-book"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "D.M Plant Log Book",
		single_column: true,
	});
	new DMPlantLog(page);
};

class DMPlantLog {
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
			<div class="dm-plant-log-wrapper" style="padding: 10px 0;">
				<style>
					.dm-plant-log-wrapper table tbody tr.dm-row-even { background: #ffffff; }
					.dm-plant-log-wrapper table tbody tr.dm-row-odd { background: #f2f6fb; }
					.dm-plant-log-wrapper table tbody tr:hover { background: #fff3cd !important; }
					.dm-plant-log-wrapper table tbody tr td:first-child,
					.dm-plant-log-wrapper table tbody tr td:nth-child(2) {
						font-weight: 600;
						background: #e9edf2;
					}
					.dm-plant-log-wrapper table tbody tr:hover td:first-child,
					.dm-plant-log-wrapper table tbody tr:hover td:nth-child(2) {
						background: #ffe9a8;
					}
				</style>
				<div id="dm-status" class="text-muted" style="margin-bottom:10px;"></div>
				<div id="dm-table-holder"></div>
			</div>
		`);
		this.page.body.append(this.$wrap);

		this.$status = this.$wrap.find("#dm-status");
		this.$table_holder = this.$wrap.find("#dm-table-holder");

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
			method: `${APP_METHOD_PATH}.get_dm_log`,
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

		let group_header =
			'<th rowspan="2" style="min-width:40px; padding:6px; background:#f5f5f5; border:1px solid #ddd;">S.No</th>' +
			'<th rowspan="2" style="min-width:110px; padding:6px; background:#f5f5f5; border:1px solid #ddd;">Time in Hrs.</th>';
		let sub_header = "";

		COLUMN_GROUPS.forEach((g) => {
			if (g.group === null) {
				g.cols.forEach((c) => {
					group_header += `<th rowspan="2" style="min-width:110px; padding:6px; background:#f5f5f5; border:1px solid #ddd;">${frappe.utils.escape_html(
						c.label
					)}</th>`;
				});
			} else {
				group_header += `<th colspan="${g.cols.length}" style="padding:6px; background:#eaeaea; border:1px solid #ddd; text-align:center;">${frappe.utils.escape_html(
					g.group
				)}</th>`;
				g.cols.forEach((c) => {
					sub_header += `<th style="min-width:100px; padding:6px; background:#f5f5f5; border:1px solid #ddd;">${frappe.utils.escape_html(
						c.label
					)}</th>`;
				});
			}
		});

		const body_rows = rows
			.map((row, idx) => {
				const cells = ALL_FIELDS.map((field) => {
					const val = row[field] === null || row[field] === undefined ? "" : row[field];
					return `<td style="border:1px solid #ddd; padding:2px;">
						<input type="text"
							class="dm-cell"
							data-row="${idx}"
							data-field="${field}"
							value="${frappe.utils.escape_html(String(val))}"
							style="width:100%; min-width:90px; text-align:right; border:1px solid transparent; padding:6px; box-sizing:border-box; background:transparent;">
					</td>`;
				}).join("");

				const row_class = idx % 2 === 0 ? "dm-row-even" : "dm-row-odd";
				return `<tr class="${row_class}">
					<td style="text-align:center; border:1px solid #ddd; padding:6px;">${row.s_no}</td>
					<td style="border:1px solid #ddd; padding:6px; white-space:nowrap;">${frappe.utils.escape_html(row.time_slot)}</td>
					${cells}
				</tr>`;
			})
			.join("");

		this.$table_holder.html(`
			<div style="overflow-x:auto;">
				<table style="border-collapse:collapse; width:100%;">
					<thead>
						<tr>${group_header}</tr>
						<tr>${sub_header}</tr>
					</thead>
					<tbody>${body_rows}</tbody>
				</table>
			</div>
		`);

		this.$table_holder.off("input", ".dm-cell").on("input", ".dm-cell", (e) => {
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
			method: `${APP_METHOD_PATH}.save_dm_log`,
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