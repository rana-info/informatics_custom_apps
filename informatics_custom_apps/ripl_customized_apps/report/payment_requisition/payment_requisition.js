const PR_METHOD_PATH =
	"informatics_custom_apps.ripl_customized_apps.report.payment_requisition.payment_requisition";

// Payment Request fields the user selects per vendor (must match NATURE_FIELD / SECTION_FIELD in the .py)
// [fieldname, label]: the field is found by fieldname first, then by its label (handles custom_nature etc.)
const PR_VENDOR_FIELDS = [
	["nature", "Nature"],
	["section", "Section"],
];

function pr_link_options(doctype, txt, filters) {
	return frappe.db.get_link_options(doctype, txt, filters).then((opts) =>
		(opts || []).map((o) => ({
			value: o.value,
			label: o.label || o.value,
			description: o.description || "",
		}))
	);
}

frappe.query_reports["Payment Requisition"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
			on_change: function () {
				frappe.query_report.set_filter_value("payable_accounts", []);
			},
		},
		{
			fieldname: "plant",
			label: __("Plant"),
			fieldtype: "MultiSelectList",
			get_data: function (txt) {
				return pr_link_options("Branch", txt);
			},
		},
		{
			fieldname: "segment",
			label: __("Segment"),
			fieldtype: "MultiSelectList",
			get_data: function (txt) {
				return pr_link_options("Segment", txt);
			},
		},
		{
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "MultiSelectList",
			get_data: function (txt) {
				return pr_link_options("Supplier", txt);
			},
		},
		{
			fieldname: "payable_accounts",
			label: __("GL for Payable"),
			fieldtype: "MultiSelectList",
			get_data: function (txt) {
				return pr_link_options("Account", txt, {
					company: frappe.query_report.get_filter_value("company"),
					account_type: "Payable",
					is_group: 0,
				});
			},
		},
		{
			fieldname: "as_on_date",
			label: __("Due As On"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
	],

	get_datatable_options(options) {
		return Object.assign(options, { checkboxColumn: true });
	},

	onload(report) {
		pr_inject_style();
		pr_show_filter_labels(report);
		report.page.add_inner_button(__("Create Payment Request"), () => pr_start_payment());
		report.page.inner_toolbar
			.find("button")
			.filter((i, el) => $(el).text().trim() === __("Create Payment Request"))
			.removeClass("btn-default")
			.addClass("pr-btn-pay");
	},
};

function pr_show_filter_labels(report) {
	const clear_inside = (f) => {
		const $w = f.$wrapper;
		if (!$w || !$w.length) return;

		f.df.placeholder = "";
		$w.find("input, textarea").attr("placeholder", "");

		if (f.df.fieldtype === "MultiSelectList") {
			const empty = !(f.get_value() || []).length;
			if (empty) $w.find(".status-text").text("");
		}
	};

	const apply = () => {
		(report.filters || []).forEach((f) => {
			const $w = f.$wrapper;
			if (!$w || !$w.length) return;

			if (!$w.find(".pr-flabel").length) {
				$("<div class='pr-flabel'></div>")
					.text(f.df.label || "")
					.prependTo($w);
			}

			clear_inside(f);

			if (f.df.fieldtype === "MultiSelectList" && !$w.data("pr-observed")) {
				$w.data("pr-observed", 1);
				new MutationObserver(() => clear_inside(f)).observe($w[0], {
					childList: true,
					subtree: true,
					characterData: true,
				});
			}
		});
	};

	[0, 300, 1000, 2000].forEach((t) => setTimeout(apply, t));
}

function pr_inject_style() {
	$("#pr-style, #pr-style-v2, #pr-style-v3, #pr-style-v4, #pr-style-v5, #pr-style-v6").remove();
	if (document.getElementById("pr-style-v7")) return;
	const css = `
		.pr-flabel {
			display: block !important;
			font-size: 14px;
			font-weight: 600;
			color: var(--text-color);
			margin-bottom: 6px;
			line-height: 18px;
			white-space: nowrap;
			overflow: hidden;
			text-overflow: ellipsis;
		}
		.page-form .frappe-control input::placeholder { color: transparent !important; }
		.page-form .frappe-control .placeholder { display: none !important; }
		.page-form .multiselect-list .status-text { min-height: 18px; }
		.page-form, .standard-filter-section { height: auto !important; overflow: visible !important; }
		.pr-wide .modal-dialog { max-width: 96vw !important; width: 96vw !important; }
		.pr-wide .modal-body { overflow-x: hidden; }
		.pr-wide .pr-fixed { table-layout: fixed; width: 100%; }
		.pr-wide .pr-fixed td, .pr-wide .pr-fixed th { overflow-wrap: anywhere; word-break: break-word; white-space: normal; vertical-align: middle; }
		.pr-wide .pr-remarks > div { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
		.pr-btn-pay { color: #fff !important; font-weight: 600 !important; border: none !important; background: #3b82f6 !important; }
		.pr-btn-pay:hover { background: #2563eb !important; }
		.pr-wide .modal-content { background: #f8fafc; }
		.pr-wide .modal-body { background: #f8fafc; }
		.pr-btn-pay[disabled] { opacity: .4; cursor: not-allowed; }
		.pr-card { border: 2px solid var(--pc); border-left-width: 10px; border-radius: 12px; margin-bottom: 30px;
			overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,.08); background: var(--pt); }
		.pr-card-title { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 12px 16px;
			background: color-mix(in srgb, var(--pc) 24%, #fff); color: #111827; border-bottom: 2px solid var(--pc); }
		.pr-card-title b { color: color-mix(in srgb, var(--pc) 65%, #000); }
		.pr-card-title .text-muted { color: #6b7280 !important; }
		.pr-badge { display: inline-flex; align-items: center; justify-content: center; min-width: 28px; height: 28px;
			padding: 0 8px; border-radius: 14px; background: #fff; color: var(--pc); font-weight: 700; font-size: 13px; }
		.pr-card-body { padding: 14px 16px; background: var(--pt); color: #111827; }
		.pr-card-body .text-muted { color: #6b7280 !important; }
		.pr-card-body table { background: #fff; color: #111827; }
		.pr-card-body .pr-stat-box { background: #fff; border: 1px solid var(--pc); border-radius: 8px; padding: 6px 12px; }
		.pr-amt { font-weight: 700 !important; border-width: 2px !important; border-style: solid !important; color: #111827 !important; }
		.pr-amt.pr-full { border-color: #16a34a !important; background: #dcfce7 !important; }
		.pr-amt.pr-part { border-color: #ea580c !important; background: #ffedd5 !important; }
		.pr-amt.pr-zero { border-color: #d1d5db !important; background: #f3f4f6 !important; }
		.pr-legend { display: flex; gap: 18px; flex-wrap: wrap; align-items: center; margin-bottom: 14px; font-size: 12px; }
		.pr-legend span.sw { display: inline-block; width: 14px; height: 14px; border-radius: 3px; margin-right: 5px; vertical-align: middle; border: 2px solid; }
		.pr-vf { display: flex; gap: 16px; flex-wrap: wrap; align-items: flex-end; background: #fff; border: 1px solid var(--pc);
			border-radius: 8px; padding: 10px 14px 4px; margin-bottom: 12px; }
		.pr-vf .pr-vf-slot { min-width: 220px; flex: 1 1 220px; max-width: 320px; }
		.pr-vf .frappe-control { margin-bottom: 8px !important; }
		.pr-vf .pr-vf-copy { margin-bottom: 12px; }
	`;
	$("<style id='pr-style-v7'>").text(css).appendTo("head");
}

const PR_PAYABLE_TYPES = ["Purchase Invoice", "Journal Entry"];
const pr_company = () => frappe.query_report.get_filter_value("company");

function pr_get_selected_rows() {
	const dt = frappe.query_report.datatable;
	const cols = dt.getColumns();
	const idx = (id) => cols.findIndex((c) => c.id === id);
	const cells = dt.getRows();

	return dt.rowmanager
		.getCheckedRows()
		.map((i) => {
			const row = cells[i];
			const val = (id) => (row[idx(id)] ? row[idx(id)].content : null);
			return {
				party: val("party"),
				supplier_name: val("supplier_name"),
				party_account: val("party_account"),
				plant: val("plant"),
				segment: val("segment"),
				voucher_no: val("voucher_no"),
				bill_type: val("bill_type"),
				due_date: val("due_date"),
				due_amount: flt(val("due_amount")),
			};
		})
		.filter((r) => r.voucher_no);
}

function pr_start_payment() {
	const rows = pr_get_selected_rows();
	if (!rows.length) {
		frappe.msgprint(__("Select at least one invoice first."));
		return;
	}
	const invalid = rows.filter((r) => !PR_PAYABLE_TYPES.includes(r.bill_type));
	if (invalid.length) {
		frappe.msgprint(
			__("Payment Request cannot be created against {0}. Select invoices only.", [
				invalid.map((r) => `${r.bill_type} ${r.voucher_no}`).join(", "),
			])
		);
		return;
	}

	frappe.call({
		method: `${PR_METHOD_PATH}.get_advance_summary`,
		args: { company: pr_company(), rows: rows },
		freeze: true,
		callback(r) {
			// load the Payment Request meta so Nature / Section use the exact field definitions (type, options, label)
			frappe.model.with_doctype("Payment Request", () => {
				const all_fields = (frappe.get_meta("Payment Request") || {}).fields || [];
				const vendor_fields = PR_VENDOR_FIELDS.map(
					([fieldname, label]) =>
						frappe.meta.get_docfield("Payment Request", fieldname) ||
						all_fields.find((df) => (df.label || "").trim().toLowerCase() === label.toLowerCase())
				).filter(Boolean);
				pr_show_dialog(rows, r.message || [], vendor_fields);
			});
		},
	});
}

function pr_show_dialog(rows, summary, vendor_fields) {
	vendor_fields = vendor_fields || [];
	pr_inject_style();
	const esc = frappe.utils.escape_html;
	const link = (type, no) =>
		`<a href="/app/${frappe.router.slug(type)}/${encodeURIComponent(no)}" target="_blank">${esc(no)}</a>`;
	const gkey = (r) => `${r.party}||${r.party_account}`;
	const blank = (v) => v === null || v === undefined || String(v).trim() === "";

	const sumMap = {};
	summary.forEach((s) => (sumMap[`${s.party}||${s.party_account}`] = s));

	const groups = [];
	const gIndex = {};
	rows.forEach((r, i) => {
		r._i = i;
		const k = gkey(r);
		if (!(k in gIndex)) {
			gIndex[k] = groups.length;
			groups.push({ key: k, rows: [], paid: [], first: r, ctrls: {} });
		}
		groups[gIndex[k]].rows.push(r);
	});

	const PALETTE = [
		["#2563eb", "#dbeafe"], ["#16a34a", "#dcfce7"], ["#9333ea", "#f3e8ff"],
		["#ea580c", "#ffedd5"], ["#0d9488", "#ccfbf1"], ["#be123c", "#ffe4e6"],
	];

	let changed = false;

	const stat = (label, cls, inner) =>
		`<div class="pr-stat-box" style="min-width:170px"><div class="text-muted small">${label}</div>
		<div class="${cls}" style="font-size:15px;font-weight:600">${inner}</div></div>`;

	const cardInner = (g, gi) => {
		const s = sumMap[g.key] || { advances: [], advance_total: 0, invoice_pos: {} };
		const f = g.first;
		const invTotal = g.rows.reduce((a, r) => a + r.due_amount, 0);
		let h = `<div class="pr-card-title"><span class="pr-badge">${gi + 1}</span>
			<b style="font-size:15px">${esc(f.supplier_name || f.party)}</b>
			<span class="text-muted">${esc(f.party)} &middot; ${esc(f.party_account)}</span></div>
			<div class="pr-card-body">
			<div style="display:flex;gap:28px;flex-wrap:wrap;margin-bottom:10px">
				${stat(__("Invoices Due (Credit)"), "", format_currency(invTotal))}
				${stat(__("Advance Available (Debit)"), flt(s.advance_total) ? "text-success" : "", format_currency(s.advance_total))}
				${stat(__("Request Amount"), "pr-pay", "")}
			</div>`;

		if (vendor_fields.length) {
			h += `<div class="pr-vf">
				${vendor_fields.map((df) => `<div class="pr-vf-slot" data-g="${gi}" data-k="${df.fieldname}"></div>`).join("")}
				${groups.length > 1
					? `<button type="button" class="btn btn-default btn-xs pr-vf-copy" tabindex="-1" data-g="${gi}"
						title="${__("Copy these values to all other vendors")}">${__("Copy to all vendors")}</button>`
					: ""}
			</div>`;
		}

		h += `<table class="table table-bordered table-sm pr-fixed" style="margin-bottom:8px">
				<thead><tr><th style="width:24%">${__("Invoice")}</th><th>${__("PO No")}</th><th style="width:95px">${__("Due Date")}</th>
				<th class="text-right" style="width:120px">${__("Due Amount")}</th><th class="text-right" style="width:150px">${__("Request Amount")}</th></tr></thead><tbody>`;
		g.rows.forEach((r) => {
			const pos = ((s.invoice_pos || {})[r.voucher_no] || [])
				.map((po) => link("Purchase Order", po))
				.join(", ");
			h += `<tr><td>${link(r.bill_type, r.voucher_no)} <small class="text-muted">${esc(r.bill_type)}</small></td>
				<td>${pos || '<span class="text-muted">-</span>'}</td>
				<td>${r.due_date ? frappe.datetime.str_to_user(r.due_date) : ""}</td>
				<td class="text-right">${format_currency(r.due_amount)}</td>
				<td><input type="number" class="form-control input-sm text-right pr-amt" data-i="${r._i}"
					min="0" max="${r.due_amount}" step="0.01" value="${r.due_amount}"></td></tr>`;
		});
		h += `</tbody></table>`;

		if (s.advances.length) {
			h += `<div class="text-muted small" style="margin-bottom:4px">${__("Advances / debit entries available for this supplier (for information only - not reconciled here)")}</div>
				<table class="table table-bordered table-sm pr-fixed" style="margin-bottom:0">
				<thead><tr><th style="width:20%">${__("Voucher")}</th><th style="width:95px">${__("Date")}</th><th style="width:14%">${__("Linked PO")}</th>
				<th>${__("Remarks")}</th><th class="text-right" style="width:110px">${__("Amount")}</th></tr></thead><tbody>`;
			s.advances.forEach((a) => {
				const pos = (a.purchase_orders || []).map((po) => link("Purchase Order", po)).join(", ");
				h += `<tr><td>${link(a.voucher_type, a.voucher_no)} <small class="text-muted">${esc(a.voucher_type)}</small></td>
					<td>${frappe.datetime.str_to_user(a.posting_date)}</td>
					<td>${pos || '<span class="text-muted">-</span>'}</td>
					<td class="pr-remarks" title="${esc(a.remarks || "")}"><div>${a.remarks ? esc(a.remarks) : '<span class="text-muted">-</span>'}</div></td>
					<td class="text-right">${format_currency(a.amount)}</td></tr>`;
			});
			h += `</tbody></table>`;
		} else {
			h += `<div class="text-muted small">${__("No advances available for this supplier.")}</div>`;
		}
		return h + `</div>`;
	};

	let html = `<div class="pr-legend"><b>${__("Payment Amount colour")}:</b>
		<span><span class="sw" style="border-color:#16a34a;background:#dcfce7"></span>${__("Full amount")}</span>
		<span><span class="sw" style="border-color:#ea580c;background:#ffedd5"></span>${__("Part payment")}</span>
		<span><span class="sw" style="border-color:#9ca3af;background:#e5e7eb"></span>${__("Zero (skipped)")}</span></div>`;
	groups.forEach((g, gi) => {
		const [pc, pt] = PALETTE[gi % PALETTE.length];
		html += `<div class="pr-card" data-g="${gi}" style="--pc:${pc};--pt:${pt}">${cardInner(g, gi)}</div>`;
	});
	html += `<div class="pr-grand" style="display:flex;gap:40px;justify-content:flex-end;font-size:15px;padding:4px 6px">
		<div>${__("Total Payment")}: <b class="g-pay"></b></div></div>`;

	const collect = (gi) => {
		const sel = gi === undefined ? ".pr-amt" : `.pr-card[data-g="${gi}"] .pr-amt`;
		const out = [];
		let ok = true;
		d.$wrapper.find(sel).each(function () {
			const r = rows[$(this).data("i")];
			const pay = flt($(this).val());
			if (pay < 0 || pay > r.due_amount + 0.005) {
				frappe.msgprint(__("Payment Amount for {0} must be between 0 and {1}", [r.voucher_no, format_currency(r.due_amount)]));
				ok = false;
				return false;
			}
			if (pay > 0) out.push({ ...r, pay_amount: pay });
		});
		if (ok && !out.length) {
			frappe.msgprint(__("Enter a Payment Amount for at least one invoice."));
			return null;
		}
		return ok ? out : null;
	};

	// Nature / Section chosen per vendor; only vendors that actually have an amount to request are validated
	const collect_vendor_fields = (out) => {
		const payingKeys = new Set(out.map((r) => gkey(r)));
		const result = {};
		const missing = [];
		const conflicts = [];

		groups.forEach((g) => {
			if (!payingKeys.has(g.key)) return;
			const party = g.first.party;
			const vals = {};
			const miss = [];
			vendor_fields.forEach((df) => {
				const v = g.ctrls[df.fieldname] ? g.ctrls[df.fieldname].get_value() : "";
				vals[df.fieldname] = v;
				if (blank(v)) miss.push(__(df.label));
			});
			if (miss.length) {
				missing.push(`<b>${esc(g.first.supplier_name || party)}</b>: ${miss.map(esc).join(", ")}`);
				return;
			}
			if (result[party] && vendor_fields.some((df) => result[party][df.fieldname] !== vals[df.fieldname])) {
				conflicts.push(esc(g.first.supplier_name || party));
				return;
			}
			result[party] = vals;
		});

		if (missing.length) {
			frappe.msgprint({
				title: __("Please select Nature and Section for each vendor"),
				message: missing.join("<br>"),
				indicator: "red",
			});
			return null;
		}
		if (conflicts.length) {
			frappe.msgprint({
				title: __("Different values for the same supplier"),
				message: __("{0} appears under more than one payable account. Use the same Nature and Section in each card.", [
					conflicts.join(", "),
				]),
				indicator: "red",
			});
			return null;
		}
		return result;
	};

	const recalc = () => {
		let gp = 0;
		d.$wrapper.find(".pr-card").each(function () {
			const $c = $(this);
			if (!$c.find(".pr-amt").length) return;
			let pay = 0;
			$c.find(".pr-amt").each(function () {
				const v = flt($(this).val());
				const due = rows[$(this).data("i")].due_amount;
				pay += v;
				$(this).removeClass("pr-full pr-part pr-zero")
					.addClass(v <= 0 ? "pr-zero" : Math.abs(v - due) < 0.005 ? "pr-full" : "pr-part");
			});
			$c.find(".pr-pay").text(format_currency(pay));
			gp += pay;
		});
		d.$wrapper.find(".g-pay").text(format_currency(gp));
	};

	const common = (cb) => {
		const v = d.get_values();
		if (!v || !v.posting_date) return;
		cb(v);
	};

	const call = (out, v, vendor_values, cb) =>
		frappe.call({
			method: `${PR_METHOD_PATH}.create_payment_requests`,
			args: {
				company: pr_company(),
				rows: out,
				posting_date: v.posting_date || frappe.datetime.get_today(),
				vendor_fields: vendor_values,
			},
			freeze: true,
			freeze_message: __("Creating payment request..."),
			callback: (r) => cb(r.message || {}),
		});

	const submitAll = () => {
		const out = collect();
		if (!out) return;
		const vendor_values = collect_vendor_fields(out);
		if (!vendor_values) return;
		common((v) =>
			call(out, v, vendor_values, (res) => {
				changed = true;
				d.hide();
				frappe.msgprint({
					title: __("Done"),
					message:
						`${__("Draft Payment Requests")}:<br>` +
						(res.payment_requests || [])
							.map((n) => `<a href="/app/payment-request/${n}" target="_blank">${n}</a>`)
							.join("<br>"),
				});
			})
		);
	};

	const d = new frappe.ui.Dialog({
		title: __("Create Payment Request"),
		size: "extra-large",
		fields: [
			{ fieldname: "posting_date", label: __("Request Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
			{ fieldtype: "Section Break" },
			{ fieldname: "body", fieldtype: "HTML", options: html },
		],
		primary_action_label: __("Create Payment Request"),
		primary_action() {
			submitAll();
		},
	});
	d.onhide = () => {
		if (changed) frappe.query_report.refresh();
	};

	d.$wrapper.addClass("pr-wide");
	d.$wrapper.on("input", ".pr-amt", recalc);
	d.show();

	// per-vendor Nature / Section controls (built after the dialog is in the DOM)
	groups.forEach((g, gi) => {
		vendor_fields.forEach((df) => {
			const $p = d.$wrapper.find(`.pr-vf-slot[data-g="${gi}"][data-k="${df.fieldname}"]`);
			if (!$p.length) return;
			const c = frappe.ui.form.make_control({
				df: {
					fieldtype: df.fieldtype,
					fieldname: df.fieldname,
					label: __(df.label),
					options: df.options,
					reqd: 1,
				},
				parent: $p,
				render_input: true,
			});
			c.refresh();
			g.ctrls[df.fieldname] = c;
		});
	});

	// copy one vendor's Nature / Section to every other vendor
	d.$wrapper.on("click", ".pr-vf-copy", function () {
		const src = groups[$(this).data("g")];
		groups.forEach((g) => {
			if (g === src) return;
			vendor_fields.forEach((df) => {
				const v = src.ctrls[df.fieldname] && src.ctrls[df.fieldname].get_value();
				if (!blank(v) && g.ctrls[df.fieldname]) g.ctrls[df.fieldname].set_value(v);
			});
		});
	});

	// Keyboard flow: Nature -> Section -> amounts (top to bottom) -> next vendor -> primary button.
	// Document links are skipped by Tab so they never steal focus between fields.
	d.$wrapper.find(".pr-card a").attr("tabindex", "-1");
	d.$wrapper.on("focus", ".pr-amt", function () {
		this.select();
	});
	d.$wrapper.on("keydown", ".pr-amt", function (e) {
		if (e.key !== "Enter") return;
		e.preventDefault();
		const all = d.$wrapper.find(".pr-amt").toArray();
		const next = all[all.indexOf(this) + 1];
		if (next) next.focus();
		else d.get_primary_btn().focus();
	});
	setTimeout(() => d.$wrapper.find(".pr-vf input, .pr-vf select").first().focus(), 300);

	d.$wrapper
		.find(".modal-footer .btn-primary, .modal-footer .btn-modal-primary")
		.removeClass("btn-primary")
		.addClass("pr-btn-pay");
	recalc();
}