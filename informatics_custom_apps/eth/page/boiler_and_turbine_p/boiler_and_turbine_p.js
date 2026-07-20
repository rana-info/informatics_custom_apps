frappe.pages['boiler-and-turbine-p'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Boiler & Turbine Parameters',
		single_column: true
	});

	wrapper.boiler_turbine_instance = new BoilerTurbineDashboard(page, wrapper);
};

frappe.pages['boiler-and-turbine-p'].on_page_show = function(wrapper) {
	// Re-render on every page visit — Frappe's SPA routing doesn't
	// otherwise re-trigger this for a page that's already been built once.
	if (wrapper.boiler_turbine_instance) {
		wrapper.boiler_turbine_instance.refresh();
	}
};

class BoilerTurbineDashboard {
	constructor(page, wrapper) {
		this.page = page;
		this.wrapper = wrapper;
		this.filters = {
			company: frappe.defaults.get_user_default("Company") || "",
			plant: "",
			date: frappe.datetime.get_today()
		};

		this.make_filters();
		this.make_body();
		this.refresh();
	}

	make_filters() {
		this.company_field = this.page.add_field({
			fieldname: "company",
			label: "Company",
			fieldtype: "Link",
			options: "Company",
			default: this.filters.company,
			reqd: 1,
			change: () => {
				this.filters.company = this.company_field.get_value();
				this.refresh();
			}
		});

		this.plant_field = this.page.add_field({
			fieldname: "plant",
			label: "Plant",
			fieldtype: "Link",
			options: "Branch",
			default: this.filters.plant,
			reqd: 1,
			get_query: () => {
				return {
					filters: this.filters.company ? { company: this.filters.company } : {}
				};
			},
			change: () => {
				this.filters.plant = this.plant_field.get_value();
				this.refresh();
			}
		});

		this.date_field = this.page.add_field({
			fieldname: "date",
			label: "Date",
			fieldtype: "Date",
			default: this.filters.date,
			reqd: 1,
			change: () => {
				this.filters.date = this.date_field.get_value();
				this.refresh();
			}
		});
	}

	make_body() {
		this.$body = $(`<div class="boiler-turbine-body" style="margin-top: 15px;"></div>`).appendTo(this.page.body);
	}

	refresh() {
		if (!(this.filters.company && this.filters.plant && this.filters.date)) {
			this.$body.html(`<div class="text-muted" style="padding: 20px;">
				Select Company, Plant and Date to view data.
			</div>`);
			return;
		}

		this.$body.html(`<div class="text-muted" style="padding: 20px;">Loading...</div>`);

		frappe.call({
			method: "informatics_custom_apps.eth.page.boiler_and_turbine_p.boiler_and_turbine_p.get_boiler_turbine_data",
			args: {
				company: this.filters.company,
				plant: this.filters.plant,
				date: this.filters.date
			},
			callback: (r) => {
				const data = r.message || {};
				if (!data.parent || !(data.rows || []).length) {
					this.$body.html(`<div class="text-muted" style="padding: 20px;">
						No record found for ${frappe.utils.escape_html(this.filters.plant)}
						on ${frappe.datetime.str_to_user(this.filters.date)}.
					</div>`);
					return;
				}
				this.render_table(data.rows);
			}
		});
	}

	format_time(val) {
		// Time fields come back as "HH:MM:SS" strings — trim to "HH:MM".
		if (!val) return "";
		return val.toString().slice(0, 4);
	}

	format_number(val) {
		if (val === null || val === undefined || val === "") return "";
		return frappe.format(val, { fieldtype: "Float" });
	}

	render_table(rows) {
		const header_cells = [
			"Description", "Range", "Engg Units",
			"Max Value", "Time", "Min Value", "Time", "Avg Value"
		].map(h => `<th style="background:#aed4fb; padding:6px 10px; border:1px solid #999; text-align:center;">${h}</th>`).join("");

		const body_rows = rows.map(row => `
			<tr>
				<td style="padding:6px 10px; border:1px solid #999;">${frappe.utils.escape_html(row.parameter_name || "")}</td>
				<td style="padding:6px 10px; border:1px solid #999; text-align:center;">${frappe.utils.escape_html(row.range || "")}</td>
				<td style="padding:6px 10px; border:1px solid #999; text-align:center;">${frappe.utils.escape_html(row.engg_units || "")}</td>
				<td style="padding:6px 10px; border:1px solid #999; text-align:center;">${this.format_number(row.max_value)}</td>
				<td style="padding:6px 10px; border:1px solid #999; text-align:center;">${this.format_time(row.max_value_time)}</td>
				<td style="padding:6px 10px; border:1px solid #999; text-align:center;">${this.format_number(row.min_value)}</td>
				<td style="padding:6px 10px; border:1px solid #999; text-align:center;">${this.format_time(row.min_value_time)}</td>
				<td style="padding:6px 10px; border:1px solid #999; text-align:center;">${this.format_number(row.average_value)}</td>
			</tr>
		`).join("");

		this.$body.html(`
			<table style="width:100%; border-collapse: collapse; font-size: 13px;">
				<thead><tr>${header_cells}</tr></thead>
				<tbody>${body_rows}</tbody>
			</table>
			${this.render_totals_table(rows)}
		`);
	}

	render_totals_table(rows) {
		// Only sum-type parameters carry a meaningful total (row.total is
		// null for avg-type parameters like pressure/temperature).
		const total_rows = rows.filter(row => row.total !== null && row.total !== undefined);
		if (!total_rows.length) return "";

		const cells = total_rows.map(row => `
			<tr>
				<td style="padding:6px 10px; border:1px solid #999;">${frappe.utils.escape_html(row.parameter_name || "")}</td>
				<td style="padding:6px 10px; border:1px solid #999; text-align:center; font-weight:600;">${this.format_number(row.total)}</td>
				<td style="padding:6px 10px; border:1px solid #999; text-align:center;">${frappe.utils.escape_html(row.engg_units || "")}</td>
			</tr>
		`).join("");

		return `
			<div style="margin-top: 20px; font-weight: 600; margin-bottom: 6px;">Totals</div>
			<table style="width:100%; max-width: 500px; border-collapse: collapse; font-size: 13px;">
				<thead>
					<tr>
						<th style="background:#aed4fb; padding:6px 10px; border:1px solid #999; text-align:left;">Description</th>
						<th style="background:#aed4fb; padding:6px 10px; border:1px solid #999; text-align:center;">Total</th>
						<th style="background:#aed4fb; padding:6px 10px; border:1px solid #999; text-align:center;">Engg Units</th>
					</tr>
				</thead>
				<tbody>${cells}</tbody>
			</table>
		`;
	}
}