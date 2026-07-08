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
			{ field: "sac_th", label: "T.H" }
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

// Fields that hold free text and should wrap / show full content instead of a
// narrow right-aligned number box.
const TEXT_FIELDS = new Set(["remarks", "storage_tank_position"]);

// Widths (px) for the 6 frozen columns: S.No, Time in Hrs.,
// Started Time, Stopped Time, Discharging Time, Total Running Hours
const STICKY_WIDTHS = [34, 100, 55, 55, 55, 55];
const STICKY_LEFT = (() => {
	const left = [];
	let acc = 0;
	STICKY_WIDTHS.forEach((w) => {
		left.push(acc);
		acc += w;
	});
	return left;
})();

frappe.pages["dm-plant-log-book"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "D.M Plant Log Book",
		single_column: true,
	});
	wrapper.dm_plant_log_instance = new DMPlantLog(page);
};

frappe.pages["dm-plant-log-book"].on_page_show = function (wrapper) {
	if (wrapper.dm_plant_log_instance) {
		wrapper.dm_plant_log_instance.on_selection_change();
	}
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
			<div class="dm-plant-log-wrapper" style="padding: 20px 0;">
				<style>
					.dm-plant-log-wrapper table {
						font-size: 13px;
						border-collapse: separate;
						border-spacing: 0;
					}
					.dm-plant-log-wrapper table th,
					.dm-plant-log-wrapper table td {
						padding: 20px 5px !important;
					}
					.dm-plant-log-wrapper table tbody tr.dm-row-even { background: #ffffff; }
					.dm-plant-log-wrapper table tbody tr.dm-row-odd { background: #f2f6fb; }
					.dm-plant-log-wrapper table tbody tr:hover { background: #fff3cd !important; }
					.dm-plant-log-wrapper .dm-cell {
						padding: 2px !important;
						font-size: 13px;
					}
					.dm-plant-log-wrapper .dm-cell-text {
						resize: none;
						overflow: hidden;
						white-space: normal;
						word-break: break-word;
						text-align: left !important;
						line-height: 1.3;
						font-family: inherit;
					}

					/* Frozen columns */
					.dm-plant-log-wrapper table .sticky-col {
						position: sticky;
						z-index: 2;
						background: #e9edf2;
					}
					.dm-plant-log-wrapper table thead .sticky-col {
						z-index: 4;
						background: #f5f5f5;
					}
					.dm-plant-log-wrapper table tbody tr.dm-row-even .sticky-col { background: #e9edf2; }
					.dm-plant-log-wrapper table tbody tr.dm-row-odd .sticky-col { background: #dbe6f0; }
					.dm-plant-log-wrapper table tbody tr:hover .sticky-col { background: #ffe9a8 !important; }
					.dm-plant-log-wrapper table .sticky-col:last-child {
						box-shadow: 2px 0 4px -2px rgba(0,0,0,0.25);
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
			`<th rowspan="2" class="sticky-col" style="left:${STICKY_LEFT[0]}px; width:${STICKY_WIDTHS[0]}px; min-width:${STICKY_WIDTHS[0]}px; border:1px solid #ddd;">S.No</th>` +
			`<th rowspan="2" class="sticky-col" style="left:${STICKY_LEFT[1]}px; width:${STICKY_WIDTHS[1]}px; min-width:${STICKY_WIDTHS[1]}px; border:1px solid #ddd;">Time in Hrs.</th>`;
		let sub_header = "";
		let sticky_idx = 2;
		let first_null_group_done = false;

		COLUMN_GROUPS.forEach((g) => {
			if (g.group === null) {
				g.cols.forEach((c) => {
					if (!first_null_group_done) {
						// Frozen fields: started_time, stopped_time, discharging_time, total_running_hours
						group_header += `<th rowspan="2" class="sticky-col" style="left:${STICKY_LEFT[sticky_idx]}px; width:${STICKY_WIDTHS[sticky_idx]}px; min-width:${STICKY_WIDTHS[sticky_idx]}px; border:1px solid #ddd;">${frappe.utils.escape_html(
							c.label
						)}</th>`;
						sticky_idx++;
					} else {
						// Trailing null group: storage_tank_position, remarks - not frozen, wider for text
						const width = c.field === "remarks" ? 220 : 100;
						group_header += `<th rowspan="2" style="min-width:${width}px; background:#f5f5f5; border:1px solid #ddd;">${frappe.utils.escape_html(
							c.label
						)}</th>`;
					}
				});
				first_null_group_done = true;
			} else {
				group_header += `<th colspan="${g.cols.length}" style="background:#eaeaea; border:1px solid #ddd; text-align:center;">${frappe.utils.escape_html(
					g.group
				)}</th>`;
				g.cols.forEach((c) => {
					sub_header += `<th style="min-width:50px; background:#f5f5f5; border:1px solid #ddd;">${frappe.utils.escape_html(
						c.label
					)}</th>`;
				});
			}
		});

		const body_rows = rows
			.map((row, idx) => {
				const cells = ALL_FIELDS.map((field, field_i) => {
					const val = row[field] === null || row[field] === undefined ? "" : row[field];
					// First 4 fields in ALL_FIELDS are the frozen ones (started_time, stopped_time, discharging_time, total_running_hours)
					const is_sticky = field_i < 4;
					const left_style = is_sticky ? `left:${STICKY_LEFT[2 + field_i]}px;` : "";
					const is_text = TEXT_FIELDS.has(field);

					if (is_text) {
						const width = field === "remarks" ? 220 : 100;
						return `<td style="${left_style} border:1px solid #ddd; min-width:${width}px;">
							<textarea
								class="dm-cell dm-cell-text"
								data-row="${idx}"
								data-field="${field}"
								rows="1"
								style="width:100%; min-width:${width - 10}px; border:1px solid transparent; padding:3px; box-sizing:border-box; background:transparent; font-size:13px;"
							>${frappe.utils.escape_html(String(val))}</textarea>
						</td>`;
					}

					return `<td class="${is_sticky ? "sticky-col" : ""}" style="${left_style} border:1px solid #ddd;">
						<input type="text"
							class="dm-cell"
							data-row="${idx}"
							data-field="${field}"
							value="${frappe.utils.escape_html(String(val))}"
							style="width:100%; min-width:45px; text-align:right; border:1px solid transparent; padding:2px; box-sizing:border-box; background:transparent; font-size:13px;">
					</td>`;
				}).join("");

				const row_class = idx % 2 === 0 ? "dm-row-even" : "dm-row-odd";
				return `<tr class="${row_class}">
					<td class="sticky-col" style="left:${STICKY_LEFT[0]}px; text-align:center; border:1px solid #ddd;">${row.s_no}</td>
					<td class="sticky-col" style="left:${STICKY_LEFT[1]}px; border:1px solid #ddd; white-space:nowrap;">${frappe.utils.escape_html(row.time_slot)}</td>
					${cells}
				</tr>`;
			})
			.join("");

		this.$table_holder.html(`
			<div style="overflow-x:auto;">
				<table style="width:100%;">
					<thead>
						<tr>${group_header}</tr>
						<tr>${sub_header}</tr>
					</thead>
					<tbody>${body_rows}</tbody>
				</table>
			</div>
		`);

		// Auto-grow textareas (remarks / storage tank position) to fit their content
		this.$table_holder.find(".dm-cell-text").each((_, el) => {
			el.style.height = "auto";
			el.style.height = el.scrollHeight + "px";
		});

		this.$table_holder.off("input", ".dm-cell").on("input", ".dm-cell", (e) => {
			const $el = $(e.currentTarget);
			this.rows[$el.data("row")][$el.data("field")] = $el.val();
			if ($el.hasClass("dm-cell-text")) {
				e.currentTarget.style.height = "auto";
				e.currentTarget.style.height = e.currentTarget.scrollHeight + "px";
			}
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