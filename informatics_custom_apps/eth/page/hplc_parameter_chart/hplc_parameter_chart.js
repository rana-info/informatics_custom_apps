// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

frappe.pages["hplc-parameter-chart"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "HPLC Parameter Trend",
		single_column: true,
	});

	new HPLCParameterChart(page);
};

class HPLCParameterChart {
	constructor(page) {
		this.page = page;
		this.colors = ["#2e5c8a", "#c0392b", "#1e8a5f", "#a06cd5", "#d68910", "#0e7c86"];
		this.method_path =
			"informatics_custom_apps.eth.page.hplc_parameter_chart.hplc_parameter_chart";
		this.setup_filters();
		this.setup_body();
		this.load_parameters().then(() => this.refresh());
	}

	setup_filters() {
		this.company_filter = this.page.add_field({
			fieldname: "company",
			label: "Company",
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
			change: () => this.refresh(),
		});
		this.plant_filter = this.page.add_field({
			fieldname: "plant",
			label: "Plant",
			fieldtype: "Link",
			options: "Branch",
			change: () => this.refresh(),
		});
		this.from_date_filter = this.page.add_field({
			fieldname: "from_date",
			label: "From Date",
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			change: () => this.refresh(),
		});
		this.to_date_filter = this.page.add_field({
			fieldname: "to_date",
			label: "To Date",
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			change: () => this.refresh(),
		});
		this.group_filter = this.page.add_field({
			fieldname: "parameter_group",
			label: "Parameter Group",
			fieldtype: "Select",
			options: ["Both", "Sugar Parameters", "Organic and Alcohol Parameters"],
			default: "Both",
			change: () => this.load_parameters().then(() => this.refresh()),
		});
		this.parameter_filter = this.page.add_field({
			fieldname: "parameter",
			label: "Parameter",
			fieldtype: "Select",
			options: [{ label: "All parameters (overlay)", value: "__all__" }],
			default: "__all__",
			change: () => this.refresh(),
		});
	}

	setup_body() {
		this.$root = $(`
			<div class="hplc-chart-root" style="
				--ink:#1b2a4a; --title-red:#e31b1b; --grid:#d8c9a3; margin-top: 10px;
				font-family: var(--font-stack, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif);
			">
				<div class="chart-title" style="color:var(--title-red); font-weight:600; font-size:14px; margin:0 0 10px 2px;"></div><div class="chart-frame" style="padding:14px 18px 10px 8px; background:#fff;"></div>

				<div class="chart-legend" style="display:flex; gap:16px; flex-wrap:wrap; margin:10px 4px 0; font-size:11px;"></div>
			</div>
		`).appendTo(this.page.body);

		this.$title = this.$root.find(".chart-title");
		this.$frame = this.$root.find(".chart-frame");
		this.$legend = this.$root.find(".chart-legend");
	}

	load_parameters() {
		return frappe.call({ method: `${this.method_path}.get_parameter_list` }).then((r) => {
			const options = [{ label: "All parameters (overlay)", value: "__all__" }].concat(
				(r.message || []).map((row) => ({ label: row[0], value: row[0] }))
			);
			this.parameter_filter.df.options = options;
			this.parameter_filter.set_options ? this.parameter_filter.set_options(options) : null;
			this.parameter_filter.refresh();
		});
	}

	get_filter_values() {
		return {
			company: this.company_filter.get_value(),
			plant: this.plant_filter.get_value(),
			from_date: this.from_date_filter.get_value(),
			to_date: this.to_date_filter.get_value(),
			parameter_group: this.group_filter.get_value(),
			parameters:
				this.parameter_filter.get_value() && this.parameter_filter.get_value() !== "__all__"
					? [this.parameter_filter.get_value()]
					: null,
		};
	}

	show_select_filters_message() {
		this.$title.text("");
		this.$frame.html(`
			<div style="padding:60px 0; text-align:center; color:#8d99a6; font-size:13px;">
				Please select filters (Company is required) to view the trend.
			</div>
		`);
		this.$legend.html("");
	}

	refresh() {
		const filters = this.get_filter_values();
		if (!filters.company) {
			this.show_select_filters_message();
			return;
		}

		frappe.call({
			method: `${this.method_path}.get_chart_data`,
			args: filters,
			callback: (r) => this.render(r.message || { labels: [], parameters: [], series: {} }),
		});
	}

	render(data) {
		const { labels, parameters, series } = data;
		if (!labels.length) {
			this.$title.text("No samples found for the selected filters");
			this.$frame.html("");
			this.$legend.html("");
			return;
		}

		const selected = this.parameter_filter.get_value();
		if (selected && selected !== "__all__") {
			this.$title.text(`${selected} — Date-wise Trend`);
			this.draw_chart(labels, [
				{ name: selected, color: this.colors[0], values: series[selected] || [], showLabels: true },
			]);
			this.$legend.html("");
		} else {
			this.$title.text("All Parameters — Date-wise Trend");
			const seriesList = parameters.map((name, i) => ({
				name,
				color: this.colors[i % this.colors.length],
				values: series[name] || [],
				showLabels: false,
			}));
			this.draw_chart(labels, seriesList);
			this.$legend.html(
				seriesList
					.map(
						(s) => `<div style="display:flex;align-items:center;gap:6px;">
							<span style="width:12px;height:12px;border-radius:2px;background:${s.color};display:inline-block;"></span>${frappe.utils.escape_html(s.name)}
						</div>`
					)
					.join("")
			);
		}
	}

	nice_max(max) {
		const step = max <= 20 ? 5 : max <= 60 ? 10 : max <= 150 ? 25 : 50;
		return { top: Math.ceil((max * 1.15) / step) * step, step };
	}

		draw_chart(labels, seriesList) {
		const W = 900, H = 340;
		const padL = 46, padR = 16, padT = 16, padB = 34;
		const plotW = W - padL - padR, plotH = H - padT - padB;

		const allVals = seriesList.flatMap((s) => s.values.filter((v) => v !== null && v !== undefined));
		const { top, step } = this.nice_max(Math.max(...allVals, 1));
		const yFor = (v) => padT + plotH - (v / top) * plotH;
		const xFor = (i) => padL + (i / Math.max(labels.length - 1, 1)) * plotW;

		let gridSvg = "";
		for (let v = 0; v <= top; v += step) {
			const y = yFor(v);
			gridSvg += `<line x1="${padL}" y1="${y}" x2="${W - padR}" y2="${y}" stroke="#d8c9a3" stroke-width="1"/>`;
			gridSvg += `<text x="${padL - 8}" y="${y + 3}" text-anchor="end" font-size="8" font-weight="400" fill="#777">${v}</text>`;
		}

		let xLabelsSvg = "";
		labels.forEach((lab, i) => {
			if (labels.length > 14 && i % 2 !== 0) return;
			xLabelsSvg += `<text x="${xFor(i)}" y="${H - padB + 16}" text-anchor="middle" font-size="8" font-weight="400" fill="#777">${lab}</text>`;
		});

		let seriesSvg = "";
		seriesList.forEach((s) => {
			const pts = s.values.map((v, i) => (v === null || v === undefined ? null : [xFor(i), yFor(v)]));
			const pathPts = pts.filter(Boolean);
			const path = pathPts.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
			seriesSvg += `<path d="${path}" fill="none" stroke="${s.color}" stroke-width="2.4"/>`;

			pts.forEach((p, i) => {
				if (!p) return;
				const [x, y] = p;
				seriesSvg += `<circle cx="${x}" cy="${y}" r="4" fill="${s.color}" stroke="#fff" stroke-width="1"/>`;
				if (s.showLabels) {
					const v = s.values[i];
					const prev = s.values[i - 1], next = s.values[i + 1];
					const isLocalDip = prev !== undefined && prev !== null && v < prev && (next === undefined || next === null || v <= next);
					const dy = isLocalDip ? 16 : -10;
					seriesSvg += `<text x="${x}" y="${y + dy}" text-anchor="middle" font-size="8" font-weight="400" fill="${s.color}">${v}</text>`;
				}
			});
		});

		this.$frame.html(`
			<svg viewBox="0 0 ${W} ${H}" width="100%">
				${gridSvg}
				<line x1="${padL}" y1="${padT}" x2="${padL}" y2="${H - padB}" stroke="#333" stroke-width="1"/>
				<line x1="${padL}" y1="${H - padB}" x2="${W - padR}" y2="${H - padB}" stroke="#333" stroke-width="1"/>
				${xLabelsSvg}
				${seriesSvg}
			</svg>
		`);
	}
}