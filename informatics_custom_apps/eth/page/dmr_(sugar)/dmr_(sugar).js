// Page: dmr-(sugar)  -  Daily Manufacturing Report of Sugar
// Put in:  <app>/<module>/page/dmr_(sugar)/dmr_(sugar).js   (the folder Frappe created for the page)
//
// >>> Set DMR_API to the dotted path of sugar_dmr.py  (no brackets allowed in a Python path) <<<
const DMR_API = "informatics_custom_apps.eth.page.dmr_(sugar).sugar_dmr";
frappe.pages["dmr-(sugar)"].on_page_load = function (wrapper) {
	wrapper.dmr_sugar = new DMRSugar(wrapper);
};

frappe.pages["dmr-(sugar)"].on_page_show = function (wrapper) {
	// SPA re-entry: refresh only if a report was already shown
	if (wrapper.dmr_sugar && wrapper.dmr_sugar.loaded) wrapper.dmr_sugar.load();
};

class DMRSugar {
	constructor(wrapper) {
		this.loaded = false;
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Daily Manufacturing Report - Sugar"),
			single_column: true,
		});
		this.make_filters();
		this.make_actions();
		this.$body = $('<div class="dmrs"></div>').appendTo(this.page.main);
		this.inject_css();
		this.$body.html('<div class="dmrs-empty">Select the date and click <b>Show Data</b>.</div>');
	}

	make_filters() {
		const p = this.page;
		const f = (o) => p.add_field(Object.assign({ change: () => this.on_filter_change() }, o));
		this.f_company = f({ fieldname: "company", label: __("Company"), fieldtype: "Link",
			options: "Company", default: frappe.defaults.get_user_default("Company"), reqd: 1 });
		this.f_plant = f({ fieldname: "plant", label: __("Plant"), fieldtype: "Link", options: "Branch" });
		this.f_date = f({ fieldname: "date", label: __("Date"), fieldtype: "Date",
			default: frappe.datetime.get_today(), reqd: 1 });
		this.f_period = f({ fieldname: "period_from", label: __("Period From"), fieldtype: "Date",
			description: __("blank = 1st of the month") });
		this.f_season = f({ fieldname: "season_from", label: __("Season Start"), fieldtype: "Date",
			description: __("blank = last Crop Day 1") });
		this.f_remarks = p.add_field({ fieldname: "remarks", label: __("Remarks"), fieldtype: "Data" });
		this.f_note = p.add_field({ fieldname: "note", label: __("Note"), fieldtype: "Data" ,hidden:1});
	}

	make_actions() {
		this.page.set_primary_action(__("Show Data"), () => this.load(), "refresh");
		this.page.add_inner_button(__("Print"), () => window.print());
		this.page.add_inner_button(__("Export Excel"), () => this.export_excel());
	}

	on_filter_change() { /* intentionally manual: user presses Show Data */ }

	args() {
		return {
			company: this.f_company.get_value(),
			plant: this.f_plant.get_value(),
			date: this.f_date.get_value(),
			period_from: this.f_period.get_value(),
			season_from: this.f_season.get_value(),
			remarks: this.f_remarks.get_value(),
			note: this.f_note.get_value(),
		};
	}

	load() {
		const a = this.args();
		if (!a.date) return frappe.msgprint(__("Please select a Date"));
		frappe.call({
			method: `${DMR_API}.get_dmr_data`,
			args: a,
			freeze: true,
			freeze_message: __("Building DMR..."),
			callback: (r) => {
				if (!r.message) return;
				this.loaded = true;
				this.render(r.message);
			},
		});
	}

	export_excel() {
		const a = this.args();
		if (!a.date) return frappe.msgprint(__("Please select a Date"));
		open_url_post(`/api/method/${DMR_API}.export_dmr_excel`, a);
	}

	// ---------------------------------------------------------------- render
	fmt(v, dp) {
		if (v === null || v === undefined || v === "") return "";
		if (typeof v !== "number") return frappe.utils.escape_html(String(v));
		if (v === 0) return "-";
		return format_number(v, null, dp === undefined ? 2 : dp);
	}

	render(rep) {
		const m = rep.meta;
		const e = frappe.utils.escape_html;
		let h = `
		<div class="dmrs-title">
			<div class="t1">${e(m.company || "")} ${m.plant ? "- " + e(m.plant) : ""}</div>
			<div class="t2">DAILY MANUFACTURING REPORT - SUGAR</div>
			<div class="t3">
				<span>${e(m.season)}</span>
				<span>Date: <b>${frappe.datetime.str_to_user(m.date)}</b></span>
				<span>Crop Day: <b>${m.crop_day}</b></span>
				<span>Period: ${frappe.datetime.str_to_user(m.period_from)} to ${frappe.datetime.str_to_user(m.date)}</span>
				<span>To date from: ${frappe.datetime.str_to_user(m.season_from)}</span>
			</div>
			${m.has_data ? "" : '<div class="dmrs-warn">No Sugar Process Data found for this date (Day column will be blank).</div>'}
		</div>
		<div class="dmrs-grid">`;

		rep.sections.forEach((s) => {
			const wide = s.type === "process" ? " wide" : "";
			h += `<div class="dmrs-card${wide}"><div class="dmrs-h">${e(s.title)}</div>`;
			h += s.type === "process" ? this.process_table(s) : this.value_table(s);
			h += "</div>";
		});
		h += "</div>";

		if (m.remarks || m.note) {
			h += `<div class="dmrs-card wide"><table class="dmrs-t">
				${m.remarks ? `<tr><td class="lbl" style="width:120px"><b>Remarks</b></td><td>${e(m.remarks)}</td></tr>` : ""}
				${m.note ? `<tr><td class="lbl"><b>Note</b></td><td>${e(m.note)}</td></tr>` : ""}
			</table></div>`;
		}
		this.$body.html(h);
	}

	value_table(s) {
		const e = frappe.utils.escape_html;
		const has_target = s.rows.some((r) => r.target !== null && r.target !== undefined);
		let h = `<table class="dmrs-t"><thead><tr>
			<th>Particulars</th><th>Unit</th><th>Day</th><th>Period</th><th>To Date</th>
			${has_target ? "<th>Target</th><th>Day - Target</th>" : ""}</tr></thead><tbody>`;
		s.rows.forEach((r) => {
			const [d, p, t] = r.values;
			let tgt = "", diff = "";
			if (has_target) {
				if (typeof r.target === "number") {
					tgt = this.fmt(r.target, r.dp);
					if (d !== null && d !== undefined) diff = this.fmt(d - r.target, r.dp);
				} else if (r.target) {
					tgt = e(r.target);
				}
			}
			h += `<tr><td class="lbl">${e(r.label)}</td><td class="u">${e(r.unit || "")}</td>
				<td class="n day">${this.fmt(d, r.dp)}</td><td class="n">${this.fmt(p, r.dp)}</td>
				<td class="n">${this.fmt(t, r.dp)}</td>
				${has_target ? `<td class="n tg">${tgt}</td><td class="n">${diff}</td>` : ""}</tr>`;
		});
		return h + "</tbody></table>";
	}

	process_table(s) {
		const e = frappe.utils.escape_html;
		let h = `<table class="dmrs-t"><thead>
			<tr><th rowspan="2">Particulars</th><th colspan="3">Day</th><th colspan="3">Period</th><th colspan="3">To Date</th></tr>
			<tr>${["Brix", "Pol", "Pty"].map((x) => `<th>${x}</th>`).join("").repeat(3)}</tr></thead><tbody>`;
		s.rows.forEach((r) => {
			h += `<tr><td class="lbl">${e(r.label)}</td>`;
			r.cols.forEach((c, i) => {
				const cl = i === 0 ? "n day" : "n";
				h += `<td class="${cl}">${this.fmt(c.bx, 2)}</td><td class="${cl}">${this.fmt(c.pol, 2)}</td><td class="${cl}">${this.fmt(c.pty, 2)}</td>`;
			});
			h += "</tr>";
		});
		return h + "</tbody></table>";
	}

	inject_css() {
		if ($("#dmrs-css").length) return;
		$(`<style id="dmrs-css">
		.dmrs { padding: 6px 0 30px; color: #334155; }
		.dmrs-empty { padding: 40px; text-align: center; color: #64748b; }
		.dmrs-title { text-align: center; margin-bottom: 12px; padding: 10px; background: #eef6ff;
			border: 1px solid #dbeafe; border-radius: 10px; }
		.dmrs-title .t1 { font-size: 16px; font-weight: 700; color: #1e3a5f; }
		.dmrs-title .t2 { font-size: 15px; font-weight: 700; letter-spacing: .5px; margin: 2px 0; color: #2563eb; }
		.dmrs-title .t3 span { margin: 0 8px; font-size: 12px; color: #64748b; display: inline-block; }
		.dmrs-warn { margin: 8px auto 0; padding: 6px 10px; max-width: 560px; border: 1px solid #fde68a;
			background: #fffbeb; border-radius: 6px; font-size: 12px; color: #92400e; }
		.dmrs-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 440px), 1fr));
			gap: 12px; align-items: start; }
		.dmrs-card { border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; background: #ffffff; }
		.dmrs-card.wide { grid-column: 1 / -1; }
		.dmrs-h { padding: 7px 12px; font-weight: 700; font-size: 12px; color: #1e40af;
			background: #eff6ff; border-bottom: 1px solid #dbeafe; }
		.dmrs-t { width: 100%; table-layout: auto; border-collapse: collapse; font-size: 12px; }
		.dmrs-t th { padding: 4px 6px; text-align: center; color: #475569; font-weight: 600;
			background: #f8fafc; border-bottom: 1px solid #e2e8f0; }
		.dmrs-t td { padding: 3px 6px; border-bottom: 1px solid #f1f5f9; word-break: break-word; }
		.dmrs-t tr:nth-child(even) td { background: #fafcff; }
		.dmrs-t td.lbl { text-align: left; }
		.dmrs-t td.u { color: #94a3b8; text-align: center; }
		.dmrs-t td.n { text-align: right; font-variant-numeric: tabular-nums; }
		.dmrs-t td.day { font-weight: 600; color: #1e40af; background: #f0f7ff !important; }
		.dmrs-t td.tg { color: #64748b; }
		@media (max-width: 700px) { .dmrs-t { font-size: 11px; } .dmrs-t td, .dmrs-t th { padding: 2px 3px; } }
		@media print {
			.navbar, .page-head, .layout-side-section, .sidebar-section, .page-actions { display: none !important; }
			.dmrs-grid { grid-template-columns: 1fr 1fr; gap: 6px; }
			.dmrs-card { break-inside: avoid; }
			.dmrs-t { font-size: 9px; }
			.dmrs-t td, .dmrs-t th { padding: 1px 4px; }
		}
		</style>`).appendTo("head");
	}
}