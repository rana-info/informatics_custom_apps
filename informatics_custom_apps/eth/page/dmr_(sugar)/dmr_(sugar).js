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

// Headline figures shown as tiles above the tables: [tile label, row label in report]
const DMRS_KPIS = [
	["Cane crushed", "Cane crushed"],
	["Sugar production", "Sugar production"],
	["Recovery", "Recovery (estd.)"],
	["Mill extraction", "Mill extraction"],
	["Hours worked", "Worked hours"],
	["Total stoppage", "Total stoppage"],
];

const DMRS_MIN_COL = 500; // minimum width of one section column (px)
const DMRS_GAP = 14;

class DMRSugar {
	constructor(wrapper) {
		this.loaded = false;
		this.rep = null;
		this.closed = new Set();
		this.with_empty = false;
		this.layout_key = "";
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Daily Manufacturing Report - Sugar"),
			single_column: true,
		});
		this.make_filters();
		this.make_actions();
		this.$body = $('<div class="dmrs"></div>').appendTo(this.page.main);
		this.inject_css();
		this.bind_events();
		this.show_empty();
	}

	make_filters() {
		const p = this.page;
		this.f_company = p.add_field({ fieldname: "company", label: __("Company"), fieldtype: "Link",
			options: "Company", default: frappe.defaults.get_user_default("Company"), reqd: 1,
			change: () => this.on_company_change() });
		// plants are limited to the selected company
		this.f_plant = p.add_field({ fieldname: "plant", label: __("Plant"), fieldtype: "Link",
			options: "Branch", reqd: 1,
			get_query: () => ({ query: `${DMR_API}.plant_query`, filters: { company: this.f_company.get_value() } }),
			change: () => this.refresh_season() });
		this.f_date = p.add_field({ fieldname: "date", label: __("Date"), fieldtype: "Date",
			default: frappe.datetime.get_today(), reqd: 1, change: () => this.refresh_season() });
		// fixed once per plant per season (Sugar DMR Season) - shown here, not typed
		this.f_period = p.add_field({ fieldname: "period_from", label: __("Period From"), fieldtype: "Date",
			read_only: 1, description: __("fixed for the season") });
		this.f_season = p.add_field({ fieldname: "season_from", label: __("Season Start"), fieldtype: "Date",
			read_only: 1, description: __("fixed for the season") });
	}

	on_company_change() {
		if (!this.f_plant) return; // fires once while the page is being built
		if (this.f_plant.get_value()) this.f_plant.set_value(""); // old plant may belong to another company
		else this.refresh_season();
	}

	// Season Start and Period From come from the plant's Sugar DMR Season record
	refresh_season() {
		if (!this.f_plant || !this.f_date || !this.f_season || !this.f_period) return;
		const company = this.f_company.get_value();
		const plant = this.f_plant.get_value();
		const date = this.f_date.get_value();
		if (!company || !plant || !date) {
			this.f_season.set_value("");
			this.f_period.set_value("");
			return;
		}
		const seq = (this._season_req = (this._season_req || 0) + 1);
		frappe.call({
			method: `${DMR_API}.get_season_setting`,
			args: { company, plant, date },
			callback: (r) => {
				if (seq !== this._season_req) return; // a newer selection is already loading
				const st = r.message;
				this.f_season.set_value(st ? st.season_from : "");
				this.f_period.set_value(st ? st.period_from : "");
				if (!st) {
					frappe.show_alert({
						message: __("No season is set up for this plant and date, so default dates are used. Add one under Season Setup."),
						indicator: "orange",
					}, 7);
				}
			},
		});
	}

	make_actions() {
		this.page.set_primary_action(__("Show Data"), () => this.load(), "refresh");
		// this.page.add_inner_button(__("Print"), () => window.print());
		this.page.add_inner_button(__("Season Setup"), () => frappe.set_route("List", "Sugar DMR Season"));
		this.page.add_inner_button(__("Export Excel"), () => this.export_excel());
		this.page.add_inner_button(__("Export PDF"), () => this.export_pdf());
	}

	bind_events() {
		const $b = this.$body;
		$b.on("click", ".dmrs-h", (ev) => this.toggle_card($(ev.currentTarget).closest(".dmrs-card")));
		$b.on("keydown", ".dmrs-h", (ev) => {
			if (ev.key === "Enter" || ev.key === " ") {
				ev.preventDefault();
				this.toggle_card($(ev.currentTarget).closest(".dmrs-card"));
			}
		});
		$b.on("click", ".dmrs-chip", (ev) => {
			const $c = $b.find("#dmrs-sec-" + $(ev.currentTarget).data("i"));
			if (!$c.length) return;
			this.set_open($c, true);
			const calm = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
			$c[0].scrollIntoView({ behavior: calm ? "auto" : "smooth", block: "start" });
		});
		$b.on("click", ".dmrs-emp", (ev) => {
			this.with_empty = !this.with_empty;
			$(ev.currentTarget).attr("aria-pressed", this.with_empty ? "true" : "false")
				.text(this.with_empty ? __("Hide empty rows") : __("Show empty rows"));
			this.layout(true);
		});
		$b.on("click", ".dmrs-all", (ev) => {
			const $btn = $(ev.currentTarget);
			const expanding = $btn.attr("data-open") === "1"; // button currently reads "Expand all"
			if (expanding) this.closed.clear();
			else (this.rep ? this.rep.sections : []).forEach((_, i) => this.closed.add(i));
			$btn.attr("data-open", expanding ? "0" : "1").text(expanding ? __("Collapse all") : __("Expand all"));
			this.layout(true);
		});

		// re-flow the section columns when the available width changes
		$(window).off("resize.dmrs").on("resize.dmrs", frappe.utils.debounce(() => this.layout(false), 150));
		// always print in three columns
		window.__dmrs_active = this;
		if (!window.__dmrs_print_bound) {
			window.__dmrs_print_bound = true;
			window.addEventListener("beforeprint", () => {
				if (window.__dmrs_active && window.__dmrs_active.$body.is(":visible")) window.__dmrs_active.layout(true, 3);
			});
			window.addEventListener("afterprint", () => {
				if (window.__dmrs_active) window.__dmrs_active.layout(true);
			});
		}
	}

	set_open($card, open) {
		const i = parseInt(String($card.attr("id")).replace("dmrs-sec-", ""), 10);
		if (open) this.closed.delete(i); else this.closed.add(i);
		$card.toggleClass("closed", !open);
		$card.find(".dmrs-h").attr("aria-expanded", open ? "true" : "false");
	}

	toggle_card($card) {
		this.set_open($card, $card.hasClass("closed"));
	}

	args() {
		return {
			company: this.f_company.get_value(),
			plant: this.f_plant.get_value(),
			date: this.f_date.get_value(),
		};
	}

	load() {
		const a = this.args();
		if (!a.date || !a.plant) return frappe.msgprint(__("Please select a Plant and a Date"));
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

	// exports follow the page: empty rows are included only when "Show empty rows" is on
	export_args() {
		const a = Object.assign(this.args(), { with_empty: this.with_empty ? 1 : 0 });
		// open_url_post turns undefined into the text "undefined", so send only filled fields
		Object.keys(a).forEach((k) => { if (a[k] === undefined || a[k] === null) delete a[k]; });
		return a;
	}

	export_excel() {
		const a = this.export_args();
		if (!a.date || !a.plant) return frappe.msgprint(__("Please select a Plant and a Date"));
		open_url_post(`/api/method/${DMR_API}.export_dmr_excel`, a);
	}

	export_pdf() {
		const a = this.export_args();
		if (!a.date || !a.plant) return frappe.msgprint(__("Please select a Plant and a Date"));
		open_url_post(`/api/method/${DMR_API}.export_dmr_pdf`, a);
	}

	// ---------------------------------------------------------------- helpers
	show_empty() {
		this.$body.html(`
			<div class="dmrs-empty">
				<div class="dmrs-empty-t">${__("No report loaded")}</div>
				<div class="dmrs-empty-s">${__("Choose a company, plant and date above, then select Show Data.")}</div>
			</div>`);
	}

	fmt(v, dp) {
		if (v === null || v === undefined || v === "") return "";
		if (typeof v !== "number") return frappe.utils.escape_html(String(v));
		if (v === 0) return "\u2013";
		return format_number(v, null, dp === undefined ? 2 : dp);
	}

	fmt_signed(v, dp) {
		if (v === null || v === undefined || typeof v !== "number") return "";
		if (Math.abs(v) < Math.pow(10, -(dp === undefined ? 2 : dp)) / 2) return "\u2013";
		return (v > 0 ? "+" : "") + format_number(v, null, dp === undefined ? 2 : dp);
	}

	// numeric table cell; zero / blank values are muted
	td(v, dp, cls) {
		const muted = v === 0 || v === null || v === undefined || v === "";
		return `<td class="n ${cls || ""}${muted ? " z" : ""}">${this.fmt(v, dp)}</td>`;
	}

	row_empty(r) {
		const z = (v) => v === null || v === undefined || v === "" || v === 0;
		if (r.values) return r.values.every(z);
		if (r.cols) return r.cols.every((c) => z(c.bx) && z(c.pol));
		return false;
	}

	visible_rows(s) {
		return this.with_empty ? s.rows : s.rows.filter((r) => !this.row_empty(r));
	}

	find_row(rep, label) {
		for (const s of rep.sections) {
			if (s.type === "process") continue;
			for (const r of s.rows) if (r.label === label) return r;
		}
		return null;
	}

	// ---------------------------------------------------------------- render
	render(rep) {
		this.rep = rep;
		this.closed = new Set();
		this.layout_key = "";
		const m = rep.meta;
		const e = frappe.utils.escape_html;
		const u = (d) => frappe.datetime.str_to_user(d);

		let h = `
		<header class="dmrs-hero">
			<div class="dmrs-hero-main">
				<div class="dmrs-org">${e(m.company || "")}${m.plant ? `<span class="dmrs-plant">${e(m.plant)}</span>` : ""}</div>
				<h1 class="dmrs-h1">${__("Daily Manufacturing Report: Sugar")}</h1>
				<div class="dmrs-season">${e(m.season || "")}</div>
			</div>
			<dl class="dmrs-facts">
				<div class="f-big"><dt>${__("Report date")}</dt><dd>${u(m.date)}</dd></div>
				<div class="f-big"><dt>${__("Crop day")}</dt><dd>${m.crop_day}</dd></div>
				<div><dt>${__("Period")}</dt><dd>${u(m.period_from)} ${__("to")} ${u(m.date)}</dd></div>
				<div><dt>${__("Season from")}</dt><dd>${u(m.season_from)}</dd></div>
			</dl>
		</header>
		${m.has_data ? "" : `<div class="dmrs-warn">${__("No Sugar Process Data found for this date. The Day column will be blank.")}</div>`}`;

		h += this.kpi_strip(rep);

		h += `<nav class="dmrs-nav" aria-label="${__("Report sections")}">`;
		rep.sections.forEach((s, i) => {
			h += `<button type="button" class="dmrs-chip" data-i="${i}">${e(s.title)}</button>`;
		});
		h += `<span class="dmrs-ctl"><button type="button" class="dmrs-emp" aria-pressed="false">${__("Show empty rows")}</button>
			<button type="button" class="dmrs-all" data-open="0">${__("Collapse all")}</button></span></nav>`;

		h += `<div class="dmrs-sections"></div>`;

		this.$body.html(h);
		this.layout(true);
	}

	// Place the section cards into N independent columns (shortest column first), so
	// short cards never leave holes. The Brix/Pol/Purity table spans the full width.
	layout(force, forced_n) {
		if (!this.rep) return;
		const $host = this.$body.find(".dmrs-sections");
		if (!$host.length) return;
		const w = this.$body.width();
		if (!w && !forced_n) return;

		const n = forced_n || Math.max(1, Math.min(3, Math.floor((w + DMRS_GAP) / (DMRS_MIN_COL + DMRS_GAP))));
		const narrow = !forced_n && w < 560;
		const compact = !forced_n && w < 820;
		const key = n + "/" + narrow + "/" + compact;
		if (!force && key === this.layout_key) return;
		this.layout_key = key;
		this.$body.toggleClass("narrow", narrow).toggleClass("compact", compact);

		const secs = this.rep.sections;
		const col_w = Math.max(280, Math.floor((w - DMRS_GAP * (n - 1)) / n));
		// measure each card at the real column width, then fill the shortest column first
		const measure = (idx) => {
			const $m = $('<div class="dmrs-measure"></div>').css({ width: col_w + "px" }).appendTo(this.$body);
			$m.html(idx.map((i) => `<div class="m" data-i="${i}">${this.card_html(i)}</div>`).join(""));
			const hs = {};
			$m.find(".m").each((_, el) => { hs[$(el).data("i")] = el.offsetHeight; });
			$m.remove();
			return hs;
		};
		let html = "";
		let block = [];
		const flush = () => {
			if (!block.length) return;
			const hs = measure(block);
			const cols = Array.from({ length: n }, () => ({ h: 0, html: "" }));
			block.forEach((i) => {
				const c = cols.reduce((a, b) => (b.h < a.h ? b : a));
				c.html += this.card_html(i);
				c.h += (hs[i] || 0) + DMRS_GAP;
			});
			html += `<div class="dmrs-cols" style="grid-template-columns:repeat(${n},minmax(0,1fr))">`
				+ cols.map((c) => `<div class="dmrs-col">${c.html}</div>`).join("") + "</div>";
			block = [];
		};
		// the wide Brix/Pol/Purity table goes on top; all ordinary cards balance across the columns below it
		const wide = [];
		secs.forEach((s, i) => (s.type === "process" ? wide.push(i) : block.push(i)));
		wide.forEach((i) => { html += `<div class="dmrs-wide">${this.card_html(i)}</div>`; });
		flush();
		$host.html(html);
	}

	card_html(i) {
		const s = this.rep.sections[i];
		const e = frappe.utils.escape_html;
		const closed = this.closed.has(i);
		return `<section class="dmrs-card${closed ? " closed" : ""}" id="dmrs-sec-${i}">
			<div class="dmrs-h" role="button" tabindex="0" aria-expanded="${closed ? "false" : "true"}">
				<span>${e(s.title)}</span><span class="dmrs-chev" aria-hidden="true"></span>
			</div>
			<div class="dmrs-b">${s.type === "process" ? this.process_table(s) : this.value_table(s)}</div>
		</section>`;
	}

	kpi_strip(rep) {
		const e = frappe.utils.escape_html;
		let h = "";
		DMRS_KPIS.forEach(([title, label]) => {
			const r = this.find_row(rep, label);
			if (!r) return;
			const [d, p, t] = r.values;
			h += `<div class="dmrs-kpi">
				<div class="k-l">${e(title)}</div>
				<div class="k-v${d ? "" : " z"}">${this.fmt(d, r.dp)}<span class="k-u">${e(r.unit || "")}</span></div>
				<div class="k-s">
					<span>${__("Period")} <b>${this.fmt(p, r.dp)}</b></span>
					<span>${__("Season")} <b>${this.fmt(t, r.dp)}</b></span>
				</div>
			</div>`;
		});
		return h ? `<div class="dmrs-kpis">${h}</div>` : "";
	}

	value_table(s) {
		const e = frappe.utils.escape_html;
		const vrows = this.visible_rows(s);
		let h = `<table class="dmrs-t fx">
			<colgroup><col class="c-lbl"><col class="c-u"><col class="c-n"><col class="c-n"><col class="c-n"></colgroup>
			<thead><tr>
			<th class="lbl">${__("Particulars")}</th><th class="u"></th>
			<th class="day">${__("Day")}</th><th>${__("Period")}</th><th>${__("To date")}</th></tr></thead><tbody>`;
		vrows.forEach((r) => {
			const [d, p, t] = r.values;
			let tgt = "";
			if (typeof r.target === "number") {
				const diff = d !== null && d !== undefined ? this.fmt_signed(d - r.target, r.dp) : "";
				tgt = `${__("Target")} ${this.fmt(r.target, r.dp)}${diff ? ` (${diff})` : ""}`;
			} else if (r.target) {
				tgt = `${__("Target")} ${e(r.target)}`;
			}
			h += `<tr><td class="lbl">${e(r.label)}${tgt ? `<div class="tgl">${tgt}</div>` : ""}</td>
				<td class="u">${e(r.unit || "")}</td>
				${this.td(d, r.dp, "day")}${this.td(p, r.dp)}${this.td(t, r.dp)}</tr>`;
		});
		if (!vrows.length) h += `<tr><td class="lbl none" colspan="5">${__("No values for this date")}</td></tr>`;
		return h + "</tbody></table>";
	}

	process_table(s) {
		const e = frappe.utils.escape_html;
		const sub = [__("Brix"), __("Pol"), __("Purity")];
		let h = `<table class="dmrs-t fx proc">
			<colgroup><col class="c-lbl">${'<col class="c-p">'.repeat(9)}</colgroup>
			<thead>
			<tr><th class="lbl" rowspan="2">${__("Particulars")}</th>
				<th colspan="3" class="grp day">${__("Day")}</th>
				<th colspan="3" class="grp per">${__("Period")}</th>
				<th colspan="3" class="grp">${__("To date")}</th></tr>
			<tr>${[0, 1, 2].map((g) => sub.map((x, j) =>
				`<th class="${g === 0 ? "day " : ""}${g === 1 ? "per " : ""}${j === 0 ? "gs" : ""}">${x}</th>`).join("")).join("")}</tr>
			</thead><tbody>`;
		this.visible_rows(s).forEach((r) => {
			h += `<tr><td class="lbl">${e(r.label)}</td>`;
			r.cols.forEach((c, i) => {
				const cl = i === 0 ? "day" : i === 1 ? "per" : "";
				h += this.td(c.bx, 2, cl + " gs") + this.td(c.pol, 2, cl) + this.td(c.pty, 2, cl + " pty");
			});
			h += "</tr>";
		});
		return h + "</tbody></table>";
	}

	// ---------------------------------------------------------------- style
	inject_css() {
		$("#dmrs-css").remove();
		$(`<style id="dmrs-css">
		/* Frappe default theme only: every colour comes from Frappe's own CSS variables,
		   so the page follows the site theme (light / dark) with no custom palette. */
		.dmrs {
			--ink: var(--text-color); --mute: var(--text-muted); --faint: var(--text-light, var(--text-muted));
			--line: var(--border-color); --card: var(--card-bg, var(--fg-color));
			--accent: var(--blue-500, #2490ef);
			--accent-ink: color-mix(in srgb, var(--accent) 80%, var(--text-color));
			--tint: color-mix(in srgb, var(--accent) 12%, var(--card-bg, var(--fg-color)));
			--tint-2: color-mix(in srgb, var(--accent) 5%, var(--card-bg, var(--fg-color)));
			padding: 4px 0 36px; color: var(--ink); font-variant-numeric: tabular-nums;
		}
		body[data-route="dmr-(sugar)"] .page-head .container,
		body[data-route="dmr-(sugar)"] .page-body .container { max-width: 100%; }
		.dmrs *, .dmrs *::before, .dmrs *::after { box-sizing: border-box; }

		/* empty state */
		.dmrs-empty { padding: 72px 20px; text-align: center; }
		.dmrs-empty-t { font-size: 16px; font-weight: 600; }
		.dmrs-empty-s { margin-top: 4px; font-size: 13px; color: var(--mute); }

		/* header */
		.dmrs-hero { display: flex; flex-wrap: wrap; gap: 12px 40px; align-items: flex-end; justify-content: space-between;
			padding: 14px 20px; border-radius: var(--border-radius-lg, 12px); border: 1px solid var(--accent); background: var(--tint-2); }
		.dmrs-org { font-size: 13px; color: var(--mute); display: flex; flex-wrap: wrap; gap: 4px 12px; align-items: center; }
		.dmrs-plant { padding: 1px 10px; border: 1px solid var(--accent); border-radius: 99px; background: var(--card); font-size: 12px; color: var(--accent-ink); }
		.dmrs-h1 { margin: 6px 0 2px; font-size: 21px; line-height: 1.15; font-weight: 700; letter-spacing: -.01em; color: var(--accent-ink); }
		.dmrs-season { font-size: 13px; color: var(--mute); }
		.dmrs-facts { display: flex; flex-wrap: wrap; gap: 12px 28px; margin: 0; }
		.dmrs-facts dt { font-size: 11px; font-weight: 500; color: var(--mute); margin: 0 0 2px; }
		.dmrs-facts dd { margin: 0; font-size: 13px; color: var(--ink); }
		.dmrs-facts .f-big dd { font-size: 22px; font-weight: 700; line-height: 1.1; color: var(--accent-ink); }
		.dmrs-warn { margin: 12px 0 0; padding: 9px 14px; border: 1px solid var(--line); border-radius: var(--border-radius-md, 8px);
			background: var(--bg-orange, var(--tint)); color: var(--text-on-orange, var(--ink)); font-size: 12.5px; }

		/* headline tiles */
		.dmrs-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; margin: 10px 0 0; }
		.dmrs-kpi { padding: 9px 12px 8px; border: 1px solid var(--line); border-radius: var(--border-radius-md, 8px); background: var(--card); }
		.dmrs-kpi .k-l { font-size: 12px; color: var(--mute); }
		.dmrs-kpi .k-v { margin: 2px 0 4px; font-size: 21px; line-height: 1.1; font-weight: 700; color: var(--accent-ink); }
		.dmrs-kpi .k-v.z { color: var(--mute); font-weight: 500; }
		.dmrs-kpi .k-u { margin-left: 5px; font-size: 12px; font-weight: 500; color: var(--mute); }
		.dmrs-kpi .k-s { display: flex; flex-wrap: wrap; gap: 2px 14px; font-size: 11.5px; color: var(--mute); }
		.dmrs-kpi .k-s b { font-weight: 600; color: var(--ink); }

		/* section navigation */
		.dmrs-nav { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin: 12px 0 12px; }
		.dmrs-chip, .dmrs-all, .dmrs-emp { max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
			padding: 4px 11px; border: 1px solid var(--line); border-radius: 99px; background: var(--card);
			color: var(--ink); font-size: 12px; cursor: pointer; }
		.dmrs-chip:hover { border-color: var(--accent); }
		.dmrs-ctl { margin-left: auto; display: flex; gap: 6px; }
		.dmrs-emp, .dmrs-all { border-style: dashed; color: var(--mute); }
		.dmrs-emp[aria-pressed="true"] { border-style: solid; border-color: var(--accent); color: var(--accent-ink); background: var(--tint); }
		.dmrs-all:hover, .dmrs-emp:hover { color: var(--ink); }
		.dmrs-chip:focus-visible, .dmrs-all:focus-visible, .dmrs-emp:focus-visible, .dmrs-h:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

		/* layout: independent columns, no holes */
		.dmrs-cols { display: grid; gap: 14px; align-items: start; }
		.dmrs-col { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
		.dmrs-measure { position: absolute; left: -99999px; top: 0; visibility: hidden; pointer-events: none; }
		.dmrs-wide { margin: 14px 0; }
		.dmrs-cols:first-child { margin-top: 0; }

		/* cards */
		.dmrs-card { container-type: inline-size; border: 1px solid var(--line); border-radius: var(--border-radius-md, 8px); overflow: hidden; background: var(--card); scroll-margin-top: 90px; }
		.dmrs-h { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 8px 14px;
			font-size: 13px; font-weight: 600; color: var(--accent-ink); background: var(--tint-2);
			border-bottom: 1px solid var(--line); cursor: pointer; user-select: none; }
		.dmrs-chev { flex: none; width: 7px; height: 7px; border-right: 2px solid var(--mute); border-bottom: 2px solid var(--mute);
			transform: rotate(45deg); transition: transform .15s; margin-right: 3px; }
		.dmrs-card.closed .dmrs-chev { transform: rotate(-45deg); }
		.dmrs-card.closed .dmrs-h { border-bottom-color: transparent; }
		.dmrs-card.closed .dmrs-b { display: none; }

		/* tables */
		.dmrs-t { width: 100%; border-collapse: collapse; font-size: 13px; }
		.dmrs-t.fx { table-layout: fixed; }
		.dmrs-t col.c-n { width: 18%; }
		.dmrs-t col.c-u { width: 8%; }
		.dmrs-t.proc col.c-lbl { width: 20%; }
		.dmrs-t th { padding: 9px 10px; text-align: right; font-size: 12px; font-weight: 600; color: var(--mute);
			border-bottom: 1px solid var(--line); background: var(--card); }
		.dmrs-t th.lbl { text-align: left; padding-left: 14px; }
		.dmrs-t th.day { color: var(--accent-ink); box-shadow: inset 0 -2px 0 var(--accent); }
		.dmrs-t th.grp { text-align: center; border-left: 1px solid var(--line); }
		.dmrs-t th.u { padding: 0; }
		.dmrs-t td { padding: 7px 10px; line-height: 1.35; border-bottom: 1px solid var(--line); }
		.dmrs-t td:last-child, .dmrs-t th:last-child { padding-right: 16px; }
		.dmrs-t tbody tr:last-child td { border-bottom: 0; }
		.dmrs-t tbody tr:hover td { background: var(--tint-2); }
		.dmrs-t td.lbl { text-align: left; padding-left: 14px; overflow-wrap: anywhere; }
		.dmrs-t td.lbl.none { color: var(--mute); text-align: center; padding: 12px; }
		.dmrs-t td.u { text-align: center; font-size: 11px; color: var(--mute); white-space: nowrap; padding-left: 2px; padding-right: 2px; }
		.dmrs-t .tgl { margin-top: 1px; font-size: 11px; color: var(--mute); }
		.dmrs-t td.n { text-align: right; white-space: nowrap; }
		.dmrs-t td.z { color: var(--faint); }
		.dmrs-t td.day, .dmrs-t th.day { background: var(--tint); }
		.dmrs-t td.day { font-weight: 600; color: var(--accent-ink); }
		.dmrs-t td.day.z { color: var(--faint); font-weight: 400; }
		.dmrs-t.proc td.gs, .dmrs-t.proc th.gs { border-left: 1px solid var(--line); }
		.dmrs-t.proc td.pty { font-weight: 600; }

		/* narrow containers */
		.dmrs.narrow .dmrs-hero { padding: 14px 16px; }
		.dmrs.narrow .dmrs-h1 { font-size: 20px; }
		.dmrs.narrow .dmrs-t { font-size: 12.5px; }
		.dmrs.narrow .dmrs-t th, .dmrs.narrow .dmrs-t td { padding-left: 5px; padding-right: 5px; }
		/* not enough width for 9 analysis columns: drop the Period group instead of scrolling */
		.dmrs.compact .dmrs-t.proc .per { display: none; }
		.dmrs.compact .dmrs-t.proc col:nth-child(n+5):nth-child(-n+7) { display: none; }
		.dmrs.compact .dmrs-t.proc col.c-lbl { width: 28%; }

		@media (prefers-reduced-motion: reduce) { .dmrs * { transition: none !important; } }

		@media print {
			@page { size: A4 landscape; margin: 8mm; }
			.navbar, .page-head, .layout-side-section, .sidebar-section, .page-actions, .dmrs-nav { display: none !important; }
			.dmrs { -webkit-print-color-adjust: exact; print-color-adjust: exact; padding: 0; }
			.dmrs-hero { padding: 10px 14px; border-radius: 8px; }
			.dmrs-h1 { font-size: 18px; }
			.dmrs-facts .f-big dd { font-size: 17px; }
			.dmrs-kpis { gap: 6px; margin-top: 6px; grid-template-columns: repeat(6, 1fr); }
			.dmrs-kpi { padding: 6px 8px; }
			.dmrs-kpi .k-v { font-size: 16px; margin: 1px 0 2px; }
			.dmrs-cols, .dmrs-col { gap: 6px; }
			.dmrs-wide { margin: 6px 0; }
			.dmrs-card { break-inside: avoid; border-radius: 6px; }
			.dmrs-card.closed .dmrs-b { display: block; }
			.dmrs-chev { display: none; }
			.dmrs-h { padding: 4px 8px; font-size: 10px; }
			.dmrs-b { overflow: visible; }
			.dmrs-t, .dmrs.narrow .dmrs-t { font-size: 8.5px; }
			.dmrs-t td, .dmrs-t th { padding: 1px 3px; }
			.dmrs-t td:last-child, .dmrs-t th:last-child { padding-right: 4px; }
			.dmrs-t th { font-size: 8px; }
		}
		</style>`).appendTo("head");
	}
}