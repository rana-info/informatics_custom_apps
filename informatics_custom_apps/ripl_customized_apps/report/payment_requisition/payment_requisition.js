const PR_METHOD_PATH =
	"informatics_custom_apps.ripl_customized_apps.report.payment_requisition.payment_requisition";

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
	$("#pr-style, #pr-style-v2, #pr-style-v3").remove();
	if (document.getElementById("pr-style-v4")) return;
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
		.pr-btn-pay { color: #fff !important; font-weight: 600 !important; border: none !important; background: #2563eb !important; }
		.pr-btn-pay:hover { background: #1d4ed8 !important; }
		.pr-btn-pay[disabled] { opacity: .4; cursor: not-allowed; }
		.pr-card { border: 3px solid var(--pc); border-radius: 12px; margin-bottom: 32px; overflow: hidden;
			box-shadow: 0 4px 14px rgba(0,0,0,.25); background: var(--pt); }
		.pr-card-title { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 12px 16px;
			background: var(--pc); color: #fff; }
		.pr-card-title b { color: #fff; }
		.pr-card-title .text-muted { color: #f3f4f6 !important; }
		.pr-badge { display: inline-flex; align-items: center; justify-content: center; min-width: 28px; height: 28px;
			padding: 0 8px; border-radius: 14px; background: #fff; color: var(--pc); font-weight: 700; font-size: 13px; }
		.pr-card-body { padding: 14px 16px; background: var(--pt); color: #111827; }
		.pr-card-body .text-muted { color: #6b7280 !important; }
		.pr-card-body table { background: #fff; color: #111827; }
		.pr-card-body .pr-stat-box { background: #fff; border: 1px solid #d1d5db; border-radius: 8px; padding: 6px 12px; }
		.pr-amt { font-weight: 700 !important; border-width: 2px !important; border-style: solid !important; color: #111827 !important; }
		.pr-amt.pr-full { border-color: #16a34a !important; background: #dcfce7 !important; }
		.pr-amt.pr-part { border-color: #ea580c !important; background: #ffedd5 !important; }
		.pr-amt.pr-zero { border-color: #9ca3af !important; background: #e5e7eb !important; }
		.pr-legend { display: flex; gap: 18px; flex-wrap: wrap; align-items: center; margin-bottom: 14px; font-size: 12px; }
		.pr-legend span.sw { display: inline-block; width: 14px; height: 14px; border-radius: 3px; margin-right: 5px; vertical-align: middle; border: 2px solid; }
	`;
	$("<style id='pr-style-v4'>").text(css).appendTo("head");
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
			frappe.call({
				method: "frappe.client.get_list",
				args: {
					doctype: "Mode of Payment Account",
					parent: "Mode of Payment",
					filters: { company: pr_company() },
					fields: ["parent"],
					limit_page_length: 0,
				},
				callback(m) {
					const modes = [...new Set((m.message || []).map((x) => x.parent))];
					pr_show_dialog(rows, r.message || [], modes);
				},
			});
		},
	});
}

function pr_show_dialog(rows, summary, modes) {
	modes = modes || [];
	pr_inject_style();
	const esc = frappe.utils.escape_html;
	const link = (type, no) =>
		`<a href="/app/${frappe.router.slug(type)}/${encodeURIComponent(no)}" target="_blank">${esc(no)}</a>`;
	const gkey = (r) => `${r.party}||${r.party_account}`;

	const sumMap = {};
	summary.forEach((s) => (sumMap[`${s.party}||${s.party_account}`] = s));

	const groups = [];
	const gIndex = {};
	rows.forEach((r, i) => {
		r._i = i;
		const k = gkey(r);
		if (!(k in gIndex)) {
			gIndex[k] = groups.length;
			groups.push({ key: k, rows: [], paid: [], first: r });
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
			</div>
			<table class="table table-bordered table-sm pr-fixed" style="margin-bottom:8px">
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

	const call = (out, v, cb) =>
		frappe.call({
			method: `${PR_METHOD_PATH}.create_payment_requests`,
			args: {
				company: pr_company(),
				rows: out,
				posting_date: v.posting_date || frappe.datetime.get_today(),
				mode_of_payment: v.mode_of_payment || "",
			},
			freeze: true,
			freeze_message: __("Creating payment request..."),
			callback: (r) => cb(r.message || {}),
		});

	const submitAll = () => {
		const out = collect();
		if (!out) return;
		common((v) =>
			call(out, v, (res) => {
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
			{ fieldtype: "Column Break" },
			{
				fieldname: "mode_of_payment", label: __("Mode of Payment"), fieldtype: "Link", options: "Mode of Payment",
				get_query: () => ({
					filters: { name: ["in", modes.length ? modes : ["__none__"]], enabled: 1 },
				}),
			},
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

	d.$wrapper
		.find(".modal-footer .btn-primary, .modal-footer .btn-modal-primary")
		.removeClass("btn-primary")
		.addClass("pr-btn-pay");
	recalc();
}