const PRQ_PATH =
	"informatics_custom_apps.ripl_customized_apps.report.payment_request.payment_request";


const PRQ_NEGATIVE_RE = /reject|cancel|return|send back|revert/i;
const prq_esc = (v) => frappe.utils.escape_html(v == null ? "" : String(v));
const prq_link = (type, no) =>
	`<a href="/app/${frappe.router.slug(type)}/${encodeURIComponent(no)}" target="_blank">${prq_esc(no)}</a>`;
const prq_gkey = (party, acct) => `${party}||${acct}`;
const prq_blank = (v) => v === null || v === undefined || String(v).trim() === "";
const prq_company = () => frappe.query_report.get_filter_value("company");
const prq_view = () => frappe.query_report.get_filter_value("view");
const prq_actions_of = (r) => (r.available_actions || "").split(",").map((a) => a.trim()).filter(Boolean);

const prq_checked = () => {
	try {
		return frappe.query_report.get_checked_items() || [];
	} catch (e) {
		return [];
	}
};

function prq_link_options(doctype, txt, filters) {
	return frappe.db.get_link_options(doctype, txt, filters).then((opts) =>
		(opts || []).map((o) => ({
			value: o.value,
			label: o.label || o.value,
			description: o.description || "",
		}))
	);
}

function prq_group_rows(rows, account_of) {
	const groups = [];
	const index = {};
	rows.forEach((r, i) => {
		r._i = i;
		const k = prq_gkey(r.party, account_of(r));
		if (!(k in index)) {
			index[k] = groups.length;
			groups.push({ key: k, rows: [], first: r });
		}
		groups[index[k]].rows.push(r);
	});
	return groups;
}

function prq_cleanup_on_hide(d) {
	d.$wrapper.on("hidden.bs.modal", () => d.$wrapper.remove());
}

function prq_inject_css() {
	if (document.getElementById("prq-css")) return;
	const style = document.createElement("style");
	style.id = "prq-css";
	style.textContent = PRQ_CSS;
	document.head.appendChild(style);
}

const PRQ_CSS = `
/* ---- report: hide checkbox column in informational view (column stays in DOM, so datatable is never rebuilt) ---- */
.prq-no-select .dt-cell--col-0,
.prq-no-select .dt-cell--header-0 { visibility: hidden; pointer-events: none; }

/* ---- workflow action dialog ---- */
.prq-act .modal-dialog { max-width: 96vw !important; width: 96vw !important; }
.prq-act .prq-card { border: 3px solid var(--c); border-radius: 12px; margin-bottom: 24px; overflow: hidden; background: #fff; }
.prq-act .prq-card-h { display:flex; gap:10px; align-items:center; flex-wrap:wrap; padding:10px 16px; background: var(--c); color:#fff; }
.prq-act .prq-card-h .sub { color:#f3f4f6; }
.prq-act .prq-card-b { padding: 12px 16px; color:#111827; }
.prq-act .prq-stat { background:#fff; border:2px solid var(--c); border-radius:8px; padding:6px 12px; min-width:170px; }
.prq-act .prq-stat .v { font-size:15px; font-weight:700; }
.prq-act table { table-layout: fixed; width: 100%; background:#fff; color:#111827; }
.prq-act td, .prq-act th { overflow-wrap:anywhere; vertical-align:middle !important; }
.prq-act .prq-in { font-weight:700; border-width:2px; border-style:solid; }
.prq-act .prq-in.full { border-color:#16a34a; background:#dcfce7; }
.prq-act .prq-in.red  { border-color:#2563eb; background:#dbeafe; }
.prq-act .prq-in.bad  { border-color:#dc2626; background:#fee2e2; }

/* ---- payment entry dialog ---- */
.prq-wide .modal-dialog { max-width: 96vw !important; width: 96vw !important; }
.prq-wide .modal-content { background: #f8fafc; }
.prq-wide .modal-body { padding: 10px 20px 70px; background: #f8fafc; }
.prq-wide .form-section, .prq-wide .form-dashboard-section { padding: 0 !important; border: 0 !important; margin: 0 !important; }
.prq-wide .frappe-control { margin-bottom: 0 !important; }

.prq-wide .prq-top { display: flex; align-items: flex-end; gap: 20px; flex-wrap: wrap; background: #fff; border: 1px solid #e5e7eb;
	border-radius: 10px; padding: 10px 16px; margin-bottom: 6px; }
.prq-wide .prq-pd { width: 190px; min-height: 58px; }
.prq-wide .prq-sum { display: flex; gap: 10px; margin-left: auto; flex-wrap: wrap; }
.prq-wide .prq-sumi { background: #f3f4f6; border-radius: 8px; padding: 4px 14px; min-width: 150px; }
.prq-wide .prq-sumi.tot { background: #111827; }
.prq-wide .prq-sumi .l { display: block; font-size: 10.5px; color: #6b7280; text-transform: uppercase; letter-spacing: .03em; }
.prq-wide .prq-sumi b { font-size: 16px; color: #111827; font-variant-numeric: tabular-nums; }
.prq-wide .prq-sumi.tot .l { color: #9ca3af; }
.prq-wide .prq-sumi.tot b { color: #fff; }
.prq-wide .prq-legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: 11px; color: #6b7280; margin: 2px 4px 10px; align-items: center; }
.prq-wide .prq-dot i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; border: 2px solid; margin-right: 4px; vertical-align: -1px; }

.prq-wide .prq-card { background: #fff; border: 2px solid var(--c); border-radius: 12px; margin-bottom: 30px;
	box-shadow: 0 4px 14px rgba(0,0,0,.10); position: relative; }
.prq-wide .prq-card:not(:last-of-type)::after { content: ""; position: absolute; left: 10%; right: 10%; bottom: -16px;
	border-bottom: 2px dashed #cbd5e1; }
.prq-wide .prq-card-h { display: flex; align-items: center; gap: 12px; padding: 12px 16px; cursor: pointer; user-select: none;
	background: var(--bg); border-radius: 10px 10px 0 0; border-bottom: 2px solid var(--c); }
.prq-wide .prq-card.collapsed .prq-card-h { border-radius: 10px; border-bottom: 0; }
.prq-wide .prq-card-h:hover { filter: brightness(.97); }
.prq-wide .prq-vtag { font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; color: var(--c); }
.prq-wide .prq-no { width: 26px; height: 26px; border-radius: 50%; background: var(--c); color: #fff; font-weight: 700; font-size: 12px;
	display: inline-flex; align-items: center; justify-content: center; flex: none; }
.prq-wide .prq-name { display: flex; flex-direction: column; min-width: 0; }
.prq-wide .prq-name b { font-size: 14.5px; color: #111827; }
.prq-wide .prq-name .sub { font-size: 11.5px; color: #6b7280; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.prq-wide .prq-status { margin-left: 8px; padding: 2px 10px; border-radius: 12px; font-size: 11.5px; font-weight: 700;
	white-space: nowrap; min-width: 128px; text-align: center; }
.prq-wide .prq-status.ready { background: #dcfce7; color: #166534; }
.prq-wide .prq-status.missing { background: #fee2e2; color: #991b1b; }
.prq-wide .prq-status.adv { background: #f3e8ff; color: #6b21a8; }
.prq-wide .prq-status.none { background: #f3f4f6; color: #6b7280; }
.prq-wide .prq-cashbox { margin-left: auto; text-align: right; line-height: 1.2; min-width: 120px; }
.prq-wide .prq-cashbox span { display: block; font-size: 10.5px; color: #6b7280; text-transform: uppercase; letter-spacing: .03em; }
.prq-wide .prq-cashbox b { font-size: 16px; color: #111827; font-variant-numeric: tabular-nums; }
.prq-wide .prq-copy { font-size: 11px !important; padding: 1px 8px !important; }
.prq-wide .prq-chev { color: #9ca3af; font-size: 14px; transition: transform .15s; }
.prq-wide .prq-card.collapsed .prq-chev { transform: rotate(-90deg); }
.prq-wide .prq-card.collapsed .prq-card-b { display: none; }
.prq-wide .prq-card-b { padding: 4px 16px 16px; }

.prq-wide .prq-meta { display: flex; gap: 22px; flex-wrap: wrap; font-size: 12px; color: #6b7280; padding: 8px 0 10px; }
.prq-wide .prq-meta b { color: #111827; font-size: 12.5px; margin-left: 3px; font-variant-numeric: tabular-nums; }

.prq-wide .prq-fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 8px 14px; margin-bottom: 12px; }
.prq-wide .prq-f { min-height: 56px; }
.prq-wide .prq-fields .control-label { font-size: 11px; font-weight: 600; color: #4b5563; margin-bottom: 3px; }
.prq-wide .prq-fc { border-width: 1.5px !important; border-style: solid !important; border-radius: 6px !important; font-weight: 600; height: 30px; }
.prq-wide .prq-fc.ok { border-color: #86efac !important; background: #f0fdf4 !important; }
.prq-wide .prq-fc.need { border-color: #f87171 !important; background: #fef2f2 !important; }
.prq-wide .prq-fc.opt { border-color: #e5e7eb !important; background: #f9fafb !important; }

.prq-wide table.prq-t { table-layout: fixed; width: 100%; background: #fff; color: #111827; margin-bottom: 8px; font-size: 12.5px; }
.prq-wide .prq-t th { font-weight: 700; background: #f9fafb; color: #4b5563; font-size: 11.5px; }
.prq-wide .prq-t td, .prq-wide .prq-t th { padding: 5px 10px !important; overflow-wrap: anywhere; vertical-align: middle !important; border-color: #eceff3 !important; }
.prq-wide .prq-advtitle { font-size: 12px; font-weight: 600; color: #9a3412; margin-bottom: 4px; }
.prq-wide .prq-advtitle .c-note { margin-left: 8px; color: #b45309; font-weight: 600; }
.prq-wide .prq-advbox { max-height: 190px; min-height: 44px; overflow: auto; background: #fff; border: 1px solid #eceff3; border-radius: 6px; }
.prq-wide .prq-advmsg { padding: 12px 10px; font-size: 12px; color: #6b7280; }
.prq-wide .prq-advbox table.prq-t { margin-bottom: 0; }
.prq-wide .prq-advbox th { position: sticky; top: 0; z-index: 1; box-shadow: 0 1px 0 #e5e7eb; }
.prq-wide .prq-t.adv input[type=checkbox] { width: 16px; height: 16px; cursor: pointer; }
.prq-wide .prq-t.adv tr.on td { background: #f3e8ff; }
.prq-wide .prq-chip { display: inline-block; padding: 1px 10px; border-radius: 12px; font-weight: 700; background: #f3e8ff; color: #6b21a8; }
.prq-wide .prq-chip.z { background: #f3f4f6; color: #9ca3af; }
.prq-wide .prq-amt { font-weight: 700; border-width: 1.5px; border-style: solid; border-radius: 6px; height: 28px; }
.prq-wide .prq-amt.full { border-color: #86efac; background: #f0fdf4; }
.prq-wide .prq-amt.part { border-color: #fdba74; background: #fff7ed; }
.prq-wide .prq-amt.zero { border-color: #d1d5db; background: #f3f4f6; }
.prq-wide .prq-amt.bad { border-color: #f87171; background: #fef2f2; }
`;


frappe.query_reports["Payment Request"] = {
	onload() {
		prq_inject_css();
	},

	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "view",
			label: __("View"),
			fieldtype: "Select",
			options: ["My Actions", "Ready for Payment", "All Open"].join("\n"),
			default: "My Actions",
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "plant",
			label: __("Plant"),
			fieldtype: "MultiSelectList",
			get_data: (txt) => prq_link_options("Branch", txt),
		},
		{
			fieldname: "segment",
			label: __("Segment"),
			fieldtype: "MultiSelectList",
			get_data: (txt) => prq_link_options("Segment", txt),
		},
		{
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "MultiSelectList",
			get_data: (txt) => prq_link_options("Supplier", txt),
		},
	],

	get_datatable_options(options) {
		return Object.assign(options, { checkboxColumn: true });
	},

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		const f = column.fieldname;
		const inner = String(value).replace(/^\s*<div[^>]*>/i, "").replace(/<\/div>\s*$/i, "");
		const numeric = f === "paid_amount" || f === "max_amount";
		const tag = (fg, bg) => {
			const span = `<span style="display:inline-block;color:${fg};background:${bg};font-weight:600;padding:1px 8px;border-radius:10px">${inner}</span>`;
			return numeric ? `<div style="text-align:right">${span}</div>` : span;
		};
		if (f === "pr_state") {
			if (/reject|cancel/i.test(data.pr_state || "")) return tag("#991b1b", "#fee2e2");
			return data.pr_docstatus === 1 ? tag("#166534", "#dcfce7") : tag("#92400e", "#fef3c7");
		}
		if (f === "available_actions" && data.available_actions) return tag("#1e40af", "#dbeafe");
		if (f === "status") {
			if (data.status === __("Fully Processed")) return tag("#166534", "#dcfce7");
			if (data.status === __("Partly Processed")) return tag("#9a3412", "#ffedd5");
			return tag("#1e40af", "#dbeafe");
		}
		if (f === "paid_amount" && flt(data.paid_amount) > 0) return tag("#166534", "#dcfce7");
		if (f === "max_amount") return flt(data.max_amount) > 0 ? tag("#166534", "#dcfce7") : tag("#991b1b", "#fee2e2");
		return value;
	},

	after_datatable_render() {
		const report = frappe.query_report;
		if (!report) return;
		const $root = $(report.$report || report.page.main);
		$root.toggleClass("prq-no-select", prq_view() === "All Open");
		setTimeout(prq_refresh_buttons, 0);
	},
};


function prq_refresh_buttons() {
	const report = frappe.query_report;
	if (!report || !report.page) return;
	report.page.clear_inner_toolbar();
	if (prq_view() === "All Open") return; 

	const data = report.data || [];
	const actions = [...new Set(data.flatMap(prq_actions_of))];
	actions.forEach((action) => {
		const $b = report.page.add_inner_button(__(action), () => prq_do_action(action));
		if ($b && $b.removeClass) {
			$b.removeClass("btn-default").addClass(PRQ_NEGATIVE_RE.test(action) ? "btn-danger" : "btn-success");
		}
	});

	if (data.some((r) => r.can_pay)) {
		const $b = report.page.add_inner_button(__("Create Payment Entry"), () => prq_start_payment());
		if ($b && $b.removeClass) $b.removeClass("btn-default").addClass("btn-primary");
	}
}

function prq_results_table(results, with_pe) {
	let h = `<table class="table table-bordered table-sm"><thead><tr>
		<th>${__("Payment Request")}</th>${with_pe ? `<th>${__("Payment Entry")}</th>` : ""}
		<th>${__("State")}</th><th>${__("Actions Applied")}</th></tr></thead><tbody>`;
	results.forEach((x) => {
		if (x.error) {
			h += `<tr><td>${prq_link("Payment Request", x.payment_request)}</td>
				<td colspan="${with_pe ? 3 : 2}" class="text-danger">${prq_esc(x.error)}</td></tr>`;
			return;
		}
		const no_pe = with_pe && !x.payment_entry;
		const state = no_pe
			? __("Settled via advance")
			: x.docstatus === 1 && with_pe ? __("Submitted") : x.state || (x.docstatus === 1 ? __("Approved") : __("Draft"));
		h += `<tr><td>${prq_link("Payment Request", x.payment_request)}</td>
			${with_pe ? `<td>${no_pe ? '<span class="text-muted">-</span>' : prq_link("Payment Entry", x.payment_entry)}</td>` : ""}
			<td>${prq_esc(state)}</td>
			<td>${(x.actions || []).length ? prq_esc(x.actions.join(" → ")) : '<span class="text-muted">-</span>'}
			${x.amount_changed ? `<br><small style="color:#1e40af;font-weight:600">${format_currency(x.old_amount)} → ${format_currency(x.new_amount)}</small>` : ""}
			${x.settled ? `<br><small style="color:#9a3412;font-weight:600">${__("Settled via advance")}: ${format_currency(x.settled)}</small>` : ""}</td></tr>`;
	});
	return h + `</tbody></table>`;
}

let prq_busy = false;

function prq_do_action(action) {
	const rows = prq_checked().filter((r) => prq_actions_of(r).includes(action));
	if (!rows.length) {
		frappe.msgprint(__("Select Payment Requests where '{0}' is available to you.", [action]));
		return;
	}
	if (prq_busy) return;
	prq_busy = true;
	frappe.call({
		method: `${PRQ_PATH}.get_advance_summary`,
		args: { company: prq_company(), names: rows.map((r) => r.payment_request) },
		freeze: true,
		callback(r) {
			prq_busy = false;
			prq_action_dialog(action, rows, r.message || { requests: {}, suppliers: [] });
		},
		error() {
			prq_busy = false;
		},
	});
}

function prq_action_dialog(action, rows, info) {
	prq_inject_css();
	const readonly = PRQ_NEGATIVE_RE.test(action);
	const requests = info.requests || {};
	const supMap = {};
	(info.suppliers || []).forEach((s) => (supMap[prq_gkey(s.party, s.party_account)] = s));

	rows.forEach((r) => (r._q = requests[r.payment_request] || {}));
	const groups = prq_group_rows(rows, (r) => r._q.party_account);

	const sw = (c, bg, t) =>
		`<span><span style="display:inline-block;width:14px;height:14px;border-radius:3px;margin-right:5px;vertical-align:middle;border:2px solid ${c};background:${bg}"></span>${t}</span>`;
	let html = `<div style="display:flex;gap:18px;flex-wrap:wrap;margin-bottom:12px;font-size:12px">
		<b>${__("Request amount")}:</b>
		${sw("#16a34a", "#dcfce7", __("Full invoice amount"))}
		${sw("#2563eb", "#dbeafe", __("Reduced"))}
		${sw("#dc2626", "#fee2e2", __("Invalid / out of limit"))}
		<b style="margin-left:14px">${__("Advance")}:</b>
		${sw("#6b7280", "#f3f4f6", __("None"))}
		${sw("#ea580c", "#ffedd5", __("Partly covers request"))}
		${sw("#9333ea", "#f3e8ff", __("Covers whole request"))}
	</div>`;

	groups.forEach((g, gi) => {
		const s = supMap[g.key] || { advances: [], advance_total: 0 };
		const f = g.first;
		html += `<div class="prq-card" data-g="${gi}" style="--c:#6b7280">
			<div class="prq-card-h"><b style="font-size:15px">${gi + 1}. ${prq_esc(f.supplier_name || f.party)}</b>
				<span class="sub">${prq_esc(f.party)} &middot; ${prq_esc(f._q.party_account || "")}</span>
				<span class="prq-badge" style="margin-left:auto;background:#fff;color:#111827;border-radius:12px;padding:2px 10px;font-weight:700"></span></div>
			<div class="prq-card-b">
			<div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:10px">
				<div class="prq-stat"><div class="text-muted small">${__("Request Total (this move)")}</div><div class="v g-total"></div></div>
				<div class="prq-stat"><div class="text-muted small">${__("Advance Available (Debit)")}</div><div class="v">${format_currency(s.advance_total)}</div></div>
				<div class="prq-stat"><div class="text-muted small">${__("Net after Advance")}</div><div class="v g-net"></div></div>
			</div>
			<table class="table table-bordered table-sm" style="margin-bottom:8px"><thead><tr>
				<th style="width:17%">${__("Payment Request")}</th><th style="width:17%">${__("Voucher")}</th>
				<th class="text-right">${__("Current Request")}</th><th class="text-right">${__("Invoice Outstanding")}</th>
				<th class="text-right">${__("Allowed Range")}</th><th class="text-right" style="width:160px">${__("New Request Amount")}</th></tr></thead><tbody>`;
		g.rows.forEach((r) => {
			const q = r._q;
			html += `<tr><td>${prq_link("Payment Request", r.payment_request)}</td>
				<td>${prq_link(r.reference_doctype, r.reference_name)}</td>
				<td class="text-right">${format_currency(r.grand_total)}</td>
				<td class="text-right">${q.invoice_outstanding == null ? "-" : format_currency(q.invoice_outstanding)}</td>
				<td class="text-right small text-muted">${format_currency(q.min_amount || 0)} – ${format_currency(q.max_amount || 0)}</td>
				<td><input type="number" class="form-control input-sm text-right prq-in" data-i="${r._i}" step="0.01"
					value="${r.grand_total}" ${readonly ? "disabled" : ""}></td></tr>`;
		});
		html += `</tbody></table>`;
		if ((s.advances || []).length) {
			html += `<div class="small" style="margin-bottom:4px;font-weight:600;color:#9a3412">${__("Unreconciled advances / debit entries for this supplier (information only)")}</div>
				<table class="table table-bordered table-sm" style="margin-bottom:0"><thead><tr>
				<th style="width:20%">${__("Voucher")}</th><th style="width:95px">${__("Date")}</th><th style="width:14%">${__("Linked PO")}</th>
				<th>${__("Remarks")}</th><th class="text-right" style="width:120px">${__("Amount")}</th></tr></thead><tbody>`;
			s.advances.forEach((a) => {
				const pos = (a.purchase_orders || []).map((po) => prq_link("Purchase Order", po)).join(", ");
				html += `<tr style="background:#fffbeb"><td>${prq_link(a.voucher_type, a.voucher_no)} <small class="text-muted">${prq_esc(a.voucher_type)}</small></td>
					<td>${frappe.datetime.str_to_user(a.posting_date)}</td><td>${pos || '<span class="text-muted">-</span>'}</td>
					<td title="${prq_esc(a.remarks)}">${a.remarks ? prq_esc(a.remarks) : '<span class="text-muted">-</span>'}</td>
					<td class="text-right" style="font-weight:700;color:#9a3412">${format_currency(a.amount)}</td></tr>`;
			});
			html += `</tbody></table>`;
		} else {
			html += `<div class="text-muted small">${__("No advances available for this supplier.")}</div>`;
		}
		html += `</div></div>`;
	});
	html += `<div style="text-align:right;font-size:15px;padding:4px 6px">${__("Total Request")}: <b class="prq-grand"></b></div>`;
	if (readonly) {
		html += `<div style="margin-top:12px;border:3px solid #dc2626;border-radius:10px;padding:10px 14px;background:#fef2f2">
			<label style="font-weight:700;color:#991b1b">${__("Reason for {0} (mandatory)", [prq_esc(__(action))])} *</label>
			<textarea class="form-control prq-reason" rows="3" style="border:2px solid #dc2626"
				placeholder="${__("Tell the requester why this is being sent back / rejected")}"></textarea></div>`;
	}

	const recalc = () => {
		let grand = 0;
		d.$wrapper.find(".prq-in").each(function () {
			const r = rows[$(this).data("i")];
			const v = flt($(this).val());
			const q = r._q;
			const bad = v <= 0 || v < flt(q.min_amount) - 0.005 || v > flt(q.max_amount) + 0.005;
			const full = q.invoice_outstanding != null && Math.abs(v - flt(q.invoice_outstanding)) < 0.005;
			$(this).removeClass("full red bad").addClass(bad ? "bad" : full ? "full" : "red");
			r._v = v;
			r._bad = bad;
		});
		groups.forEach((g, gi) => {
			const s = supMap[g.key] || { advance_total: 0 };
			const total = g.rows.reduce((a, r) => a + flt(r._v), 0);
			const adv = flt(s.advance_total);
			let color = "#6b7280", label = __("No advance");
			if (adv > 0 && adv + 0.005 >= total) { color = "#9333ea"; label = __("Advance covers whole request"); }
			else if (adv > 0) { color = "#ea580c"; label = __("Advance partly covers request"); }
			const $c = d.$wrapper.find(`.prq-card[data-g="${gi}"]`);
			$c.css("--c", color);
			$c.find(".prq-badge").text(label).css("color", color);
			$c.find(".g-total").text(format_currency(total));
			$c.find(".g-net").text(format_currency(Math.max(total - adv, 0)));
			grand += total;
		});
		d.$wrapper.find(".prq-grand").text(format_currency(grand));
	};

	const d = new frappe.ui.Dialog({
		title: __("{0}: review advance and request amount", [__(action)]),
		size: "extra-large",
		fields: [{ fieldname: "body", fieldtype: "HTML", options: html }],
		primary_action_label: __(action),
		primary_action() {
			recalc();
			const reason = (d.$wrapper.find(".prq-reason").val() || "").trim();
			if (readonly && !reason) {
				d.$wrapper.find(".prq-reason").focus();
				frappe.msgprint(__("Please enter the reason for {0}.", [__(action)]));
				return;
			}
			if (!readonly) {
				const bad = rows.filter((r) => r._bad);
				if (bad.length) {
					frappe.msgprint(
						__("Request amount is outside the allowed range for: {0}", [bad.map((r) => r.payment_request).join(", ")])
					);
					return;
				}
			}
			const $btn = d.get_primary_btn();
			$btn.prop("disabled", true);
			frappe.call({
				method: `${PRQ_PATH}.apply_request_action`,
				args: {
					rows: rows.map((r) => ({ payment_request: r.payment_request, amount: readonly ? 0 : r._v })),
					action,
					reason: readonly ? reason : "",
				},
				freeze: true,
				freeze_message: __("Applying {0}...", [action]),
				callback(res) {
					const results = ((res.message || {}).results || []).map((x) => ({ ...x, actions: [action] }));
					d.hide();
					frappe.msgprint({ title: __(action), message: prq_results_table(results, false), wide: true });
					frappe.query_report.refresh();
				},
				error() {
					$btn.prop("disabled", false);
				},
			});
		},
	});
	d.$wrapper.addClass("prq-act");
	d.$wrapper.on("input", ".prq-in", recalc);
	prq_cleanup_on_hide(d);
	d.show();
	recalc();
}

const prq_cache = {};
const prq_mode_types = {};

function prq_start_payment() {
	const rows = prq_checked().filter((r) => r.can_pay);
	if (!rows.length) {
		frappe.msgprint(__("Select approved Payment Requests first (View: Ready for Payment)."));
		return;
	}
	if (prq_busy) return;
	const company = prq_company();
	if (prq_cache[company]) {
		prq_show_dialog(rows, prq_cache[company].modes, prq_cache[company].req_fields);
		return;
	}
	prq_busy = true;
	frappe.dom.freeze(__("Loading..."));
	Promise.all([
		frappe.xcall("frappe.client.get_list", {
			doctype: "Mode of Payment Account",
			parent: "Mode of Payment",
			filters: { company },
			fields: ["parent"],
			limit_page_length: 0,
		}),
		frappe.xcall(`${PRQ_PATH}.get_payment_entry_fields`),
	])
		.then(([m, req_fields]) => {
			const modes = [...new Set((m || []).map((x) => x.parent))];
			prq_cache[company] = { modes, req_fields: req_fields || [] };
			prq_show_dialog(rows, modes, req_fields || []);
		})
		.catch(() => frappe.msgprint(__("Could not load payment settings. Please try again.")))
		.finally(() => {
			prq_busy = false;
			frappe.dom.unfreeze();
		});
}

function prq_show_dialog(rows, modes, req_fields) {
	prq_inject_css();
	let changed = false;
	let pd = null;

	const groups = prq_group_rows(rows, (r) => r.party_account);
	rows.forEach((r) => (r._settle = 0));
	groups.forEach((g) => {
		Object.assign(g, { _sel: 0, _adv: 0, _bank: 0, ctrls: {}, defs: [] });
		g.maxTotal = g.rows.reduce((a, r) => a + flt(r.max_amount), 0);
	});

	const row_default = { branch: "plant", segment: "segment" };
	groups.forEach((g) => {
		g.defs = [
			{
				key: "mode_of_payment",
				df: {
					fieldtype: "Link",
					fieldname: "mode_of_payment",
					label: __("Mode of Payment"),
					options: "Mode of Payment",
					default: modes.length === 1 ? modes[0] : "",
					get_query: () => ({ filters: { name: ["in", modes.length ? modes : ["__none__"]], enabled: 1 } }),
				},
			},
			{ key: "reference_no", bank: 1, df: { fieldtype: "Data", fieldname: "reference_no", label: __("Cheque/Reference No") } },
			{ key: "reference_date", bank: 1, df: { fieldtype: "Date", fieldname: "reference_date", label: __("Cheque/Reference Date") } },
		];
		req_fields.forEach((f) => {
			const src = row_default[f.fieldname];
			const vals = src ? [...new Set(g.rows.map((r) => r[src]).filter(Boolean))] : [];
			g.defs.push({
				key: "x_" + f.fieldname,
				name: f.fieldname,
				extra: 1,
				df: {
					fieldtype: f.fieldtype,
					fieldname: "x_" + f.fieldname,
					label: __(f.label),
					options: f.options,
					default: vals.length === 1 ? vals[0] : f.default,
				},
			});
		});
	});

	const PALETTE = [
		["#2563eb", "#dbeafe"], ["#16a34a", "#dcfce7"], ["#ea580c", "#ffedd5"],
		["#9333ea", "#f3e8ff"], ["#0d9488", "#ccfbf1"], ["#e11d48", "#ffe4e6"],
	];
	const dot = (c, bg, t) => `<span class="prq-dot"><i style="border-color:${c};background:${bg}"></i>${t}</span>`;
	const multi = groups.length > 1;

	// ---- markup ----
	let html = `<div class="prq-top">
		<div class="prq-pd"></div>
		<div class="prq-sum">
			<div class="prq-sumi"><span class="l">${__("Vendors")}</span><b>${groups.length}</b></div>
			<div class="prq-sumi"><span class="l">${__("Settled by Advance")}</span><b class="prq-settled-total">0</b></div>
			<div class="prq-sumi tot"><span class="l">${__("Total Payment")}</span><b class="prq-total">0</b></div>
		</div>
		${multi ? `<button type="button" class="btn btn-default btn-sm prq-toggle-all">${__("Collapse all")}</button>` : ""}
	</div>
	<div class="prq-legend">
		<b>${__("Fields")}:</b> ${dot("#86efac", "#f0fdf4", __("Filled"))} ${dot("#f87171", "#fef2f2", __("Mandatory - missing"))} ${dot("#e5e7eb", "#f9fafb", __("Not needed"))}
		<b style="margin-left:10px">${__("Cash amount")}:</b> ${dot("#86efac", "#f0fdf4", __("Full"))} ${dot("#fdba74", "#fff7ed", __("Part"))} ${dot("#d1d5db", "#f3f4f6", __("Zero"))} ${dot("#f87171", "#fef2f2", __("Over limit"))}
		<span style="margin-left:10px">${__("Click a vendor header to collapse / expand it")}</span>
	</div>`;

	groups.forEach((g, gi) => {
		const f = g.first;
		const [pc, pbg] = PALETTE[gi % PALETTE.length];
		html += `<div class="prq-card" data-g="${gi}" style="--c:${pc};--bg:${pbg}">
			<div class="prq-card-h" data-g="${gi}">
				<span class="prq-no">${gi + 1}</span>
				<div class="prq-name"><span class="prq-vtag">${__("Vendor")} ${gi + 1} ${__("of")} ${groups.length}</span><b>${prq_esc(f.supplier_name || f.party)}</b>
					<span class="sub">${prq_esc(f.party)} &middot; ${prq_esc(f.party_account)}</span></div>
				<span class="prq-status none" data-g="${gi}">${__("No payment")}</span>
				<div class="prq-cashbox"><span>${__("Cash to Pay")}</span><b class="c-cash-h">0</b></div>
				${multi ? `<button type="button" class="btn btn-default btn-xs prq-copy" data-g="${gi}"
					title="${__("Copy Mode of Payment and the other common fields (not cheque no / date) to all vendors")}">${__("Copy fields to all")}</button>` : ""}
				<span class="prq-chev">&#9660;</span>
			</div>
			<div class="prq-card-b">
			<div class="prq-meta">
				<span>${__("Payable (Max)")}<b>${format_currency(g.maxTotal)}</b></span>
				<span>${__("Advance available")}<b class="c-adv">…</b></span>
				<span>${__("Can be settled")}<b class="c-can">…</b></span>
				<span>${__("Selected advance")}<b class="c-sel">0</b></span>
				<span>${__("Settling now")}<b class="c-set">0</b></span>
				<span>${__("Cash")}<b class="c-cash">0</b></span>
			</div>
			<div class="prq-fields">
				${g.defs.map((def) => `<div class="prq-f" data-g="${gi}" data-k="${def.key}"></div>`).join("")}
			</div>
			<table class="table table-bordered table-sm prq-t"><thead><tr>
				<th style="width:15%">${__("Payment Request")}</th><th style="width:15%">${__("Voucher")}</th>
				<th class="text-right">${__("Requested")}</th><th class="text-right">${__("Pending")}</th>
				<th class="text-right">${__("Max Payable")}</th>
				<th class="text-right">${__("Settle via Advance")}</th>
				<th class="text-right" style="width:150px">${__("Cash to Pay")}</th></tr></thead><tbody>`;
		g.rows.forEach((r) => {
			html += `<tr><td>${prq_link("Payment Request", r.payment_request)}</td>
				<td>${prq_link(r.reference_doctype, r.reference_name)}</td>
				<td class="text-right">${format_currency(r.grand_total)}</td>
				<td class="text-right">${format_currency(r.pending_amount)}</td>
				<td class="text-right">${format_currency(r.max_amount)}</td>
				<td class="text-right"><span class="prq-chip z prq-set" data-i="${r._i}">${format_currency(0)}</span></td>
				<td><input type="number" class="form-control input-sm text-right prq-amt" data-i="${r._i}"
					min="0" max="${r.max_amount}" step="0.01" value="${r.max_amount}"></td></tr>`;
		});
		html += `</tbody></table>
			<div class="prq-advtitle">${__("Advances / debit entries - tick to reconcile against the invoices above (oldest first)")}
				<span class="c-note"></span></div>
			<div class="prq-advbox"><div class="prq-advmsg">${__("Loading advances...")}</div></div>
		</div></div>`;
	});

	const d = new frappe.ui.Dialog({
		title: __("Create Payment Entry"),
		size: "extra-large",
		fields: [{ fieldname: "body", fieldtype: "HTML", options: html }],
		primary_action_label: __("Create Payment Entry"),
		primary_action() {
			const posting_date = pd && pd.get_value();
			if (!posting_date) {
				frappe.msgprint(__("Posting Date is required."));
				return;
			}
			const out = collect();
			if (!out) return;
			const refs = collect_refs();
			if (!refs) return;
			const $btn = d.get_primary_btn();
			$btn.prop("disabled", true); // no double submit
			frappe.call({
				method: `${PRQ_PATH}.create_payment_entries`,
				args: {
					company: prq_company(),
					rows: out,
					advances: ticked(),
					posting_date,
					references: refs,
				},
				freeze: true,
				freeze_message: __("Reconciling advances and creating Payment Entries..."),
				callback(r) {
					changed = true;
					d.hide();
					frappe.msgprint({
						title: __("Payment Entries"),
						message: prq_results_table((r.message || {}).results || [], true),
						wide: true,
					});
				},
				error() {
					$btn.prop("disabled", false);
				},
			});
		},
	});
	d.onhide = () => {
		if (changed) frappe.query_report.refresh();
	};
	d.$wrapper.addClass("prq-wide");
	prq_cleanup_on_hide(d);

	const $w = d.$wrapper;
	const $amt = {}, $set = {};
	rows.forEach((r) => {
		$amt[r._i] = $w.find(`.prq-amt[data-i="${r._i}"]`);
		$set[r._i] = $w.find(`.prq-set[data-i="${r._i}"]`);
	});
	groups.forEach((g, gi) => {
		g.$card = $w.find(`.prq-card[data-g="${gi}"]`);
		g.$status = $w.find(`.prq-status[data-g="${gi}"]`);
	});
	const $total = $w.find(".prq-total");
	const $settledTotal = $w.find(".prq-settled-total");

	// ---- state helpers ----
	const pays_of = (g) => g.rows.some((r) => flt($amt[r._i].val()) > 0);
	const is_needed = (g, def) => pays_of(g) && (!def.bank || g._bank);

	// colour every vendor field + the status chip: green = filled, red = mandatory but empty, grey = not needed
	const paint = () => {
		groups.forEach((g) => {
			let n_missing = 0;
			const pays = pays_of(g);
			g.defs.forEach((def) => {
				const c = g.ctrls[def.key];
				if (!c) return;
				const filled = !prq_blank(c.get_value());
				const needed = pays && (!def.bank || g._bank);
				if (needed && !filled) n_missing++;
				const cls = filled ? "ok" : needed ? "need" : "opt";
				c.$wrapper.find("input, select, textarea").removeClass("ok need opt").addClass("prq-fc " + cls);
			});
			const settle = g.rows.reduce((a, r) => a + flt(r._settle), 0);
			let cls = "none", txt = __("No payment");
			if (pays) {
				cls = n_missing ? "missing" : "ready";
				txt = n_missing ? __("{0} field(s) missing", [n_missing]) : __("Ready");
			} else if (settle > 0) {
				cls = "adv";
				txt = __("Settled via advance");
			}
			g.$status.attr("class", "prq-status " + cls).text(txt);
		});
	};

	const load_bank = (g) => {
		const mp = g.ctrls.mode_of_payment && g.ctrls.mode_of_payment.get_value();
		const apply = (type) => {
			if ((g.ctrls.mode_of_payment.get_value() || "") !== (mp || "")) return; // user changed it meanwhile
			g._bank = type === "Bank" ? 1 : 0;
			paint();
		};
		if (!mp) return apply("");
		if (mp in prq_mode_types) return apply(prq_mode_types[mp]);
		frappe.db.get_value("Mode of Payment", mp, "type").then((r) => {
			prq_mode_types[mp] = ((r.message || {}).type) || "";
			apply(prq_mode_types[mp]);
		});
	};

	const build_controls = () => {
		pd = frappe.ui.form.make_control({
			df: { fieldtype: "Date", fieldname: "posting_date", label: __("Posting Date"), reqd: 1 },
			parent: $w.find(".prq-pd"),
			render_input: true,
		});
		pd.refresh();
		pd.set_value(frappe.datetime.get_today());
		groups.forEach((g, gi) => {
			g.defs.forEach((def) => {
				const $p = $w.find(`.prq-f[data-g="${gi}"][data-k="${def.key}"]`);
				const df = Object.assign({}, def.df, { reqd: 0 });
				const default_value = df.default;
				delete df.default;
				df.change = () => (def.key === "mode_of_payment" ? load_bank(g) : paint());
				const c = frappe.ui.form.make_control({ df, parent: $p, render_input: true });
				c.refresh();
				g.ctrls[def.key] = c;
				if (!prq_blank(default_value)) c.set_value(default_value);
			});
		});
		groups.forEach(load_bank);
	};

	const totals = () => {
		let cash = 0, settled = 0;
		groups.forEach((g) => {
			let gc = 0, gs = 0;
			g.rows.forEach((r) => {
				const $i = $amt[r._i];
				const v = flt($i.val());
				const s = flt(r._settle);
				const max = flt(r.max_amount);
				r._cash = v;
				gc += v;
				gs += s;
				const cls = v < 0 || v + s > max + 0.005 ? "bad" : v <= 0 ? "zero" : Math.abs(v + s - max) < 0.005 ? "full" : "part";
				$i.removeClass("full part zero bad").addClass(cls);
			});
			const $c = g.$card;
			$c.find(".c-set").text(format_currency(gs));
			$c.find(".c-cash, .c-cash-h").text(format_currency(gc));
			const unused = flt(flt(g._sel) - gs, 2);
			$c.find(".c-note").text(unused > 0.005 ? __("({0} of the selected advance will stay unused)", [format_currency(unused)]) : "");
			cash += gc;
			settled += gs;
		});
		$total.text(format_currency(cash));
		$settledTotal.text(format_currency(settled));
		paint();
	};

	const allocate = (only) => {
		groups.forEach((g, gi) => {
			if (only !== undefined && only !== gi) return;
			const $c = g.$card;
			let avail = 0;
			$c.find(".prq-adv").each(function () {
				$(this).closest("tr").toggleClass("on", this.checked);
				if (this.checked) avail += flt($(this).data("amt"));
			});
			g._sel = flt(avail, 2);
			g.rows.forEach((r) => {
				const max = flt(r.max_amount);
				const s = flt(Math.min(avail, max), 2);
				avail = flt(avail - s, 2);
				r._settle = s;
				$set[r._i].text(format_currency(s)).toggleClass("z", s <= 0);
				$amt[r._i].val(flt(max - s, 2));
			});
			$c.find(".c-sel").text(format_currency(g._sel));
			const $all = $c.find(".prq-adv");
			$c.find(".prq-all").prop("checked", $all.length > 0 && $all.filter(":checked").length === $all.length);
		});
		// one button: with advances ticked it reconciles them first, then creates the Payment Entry
		const n_ticked = $w.find(".prq-adv:checked").length;
		d.get_primary_btn().text(n_ticked ? __("Reconcile & Create Payment Entry") : __("Create Payment Entry"));
		totals();
	};

	const render_advances = (gi, res) => {
		const g = groups[gi];
		const $c = g.$card;
		const advances = (res && res.advances) || [];
		const total = flt(res && res.advance_total);
		g._adv = total;
		$c.find(".c-adv").text(res ? format_currency(total) : "-");
		$c.find(".c-can").text(res ? format_currency(Math.min(total, g.maxTotal)) : "-");
		const $box = $c.find(".prq-advbox");
		if (!advances.length) {
			$box.html(`<div class="prq-advmsg">${res ? __("No advances available for this supplier.") : __("Could not load advances.")}</div>`);
			return;
		}
		let h = `<table class="table table-bordered table-sm prq-t adv"><thead><tr>
			<th style="width:40px;text-align:center"><input type="checkbox" class="prq-all" title="${__("Select all")}"></th>
			<th style="width:20%">${__("Voucher")}</th><th style="width:100px">${__("Date")}</th><th style="width:14%">${__("Linked PO")}</th>
			<th>${__("Remarks")}</th><th class="text-right" style="width:120px">${__("Amount")}</th></tr></thead><tbody>`;
		advances.forEach((a) => {
			const pos = (a.purchase_orders || []).map((po) => prq_link("Purchase Order", po)).join(", ");
			h += `<tr>
				<td class="text-center"><input type="checkbox" class="prq-adv" data-amt="${a.amount}"
					data-vt="${prq_esc(a.voucher_type)}" data-vn="${prq_esc(a.voucher_no)}" data-rr="${prq_esc(a.reference_row)}"></td>
				<td>${prq_link(a.voucher_type, a.voucher_no)} <small class="text-muted">${prq_esc(a.voucher_type)}</small></td>
				<td>${frappe.datetime.str_to_user(a.posting_date)}</td>
				<td>${pos || '<span class="text-muted">-</span>'}</td>
				<td title="${prq_esc(a.remarks)}">${a.remarks ? prq_esc(a.remarks) : '<span class="text-muted">-</span>'}</td>
				<td class="text-right" style="font-weight:700;color:#9a3412">${format_currency(a.amount)}</td></tr>`;
		});
		$box.html(h + "</tbody></table>");
	};

	function collect() {
		const out = [];
		for (const r of rows) {
			const cash = flt($amt[r._i].val());
			const s = flt(r._settle);
			if (cash < 0 || cash + s > flt(r.max_amount) + 0.005) {
				frappe.msgprint(
					__("Cash + advance settlement for {0} must not exceed {1}", [r.payment_request, format_currency(r.max_amount)])
				);
				return null;
			}
			if (cash > 0 || s > 0) out.push({ payment_request: r.payment_request, pay_amount: cash, settle_amount: s });
		}
		if (!out.length) {
			frappe.msgprint(__("Enter an amount for at least one Payment Request."));
			return null;
		}
		return out;
	}

	function ticked() {
		const out = [];
		$w.find(".prq-adv:checked").each(function () {
			const $c = $(this);
			out.push({ voucher_type: $c.data("vt"), voucher_no: $c.data("vn"), reference_row: $c.data("rr") });
		});
		return out;
	}


	function collect_refs() {
		const refs = {};
		const problems = [];
		groups.forEach((g) => {
			const val = {};
			g.defs.forEach((def) => (val[def.key] = g.ctrls[def.key].get_value()));
			const missing = g.defs.filter((def) => is_needed(g, def) && prq_blank(val[def.key])).map((def) => def.df.label);
			if (missing.length) {
				problems.push(`<b>${prq_esc(g.first.supplier_name || g.first.party)}</b>: ${missing.map(prq_esc).join(", ")}`);
			}
			const extra = {};
			g.defs.filter((def) => def.extra).forEach((def) => (extra[def.name] = val[def.key]));
			refs[g.key] = {
				mode_of_payment: val.mode_of_payment || "",
				reference_no: (val.reference_no || "").trim(),
				reference_date: val.reference_date || "",
				extra_fields: extra,
			};
		});
		if (problems.length) {
			frappe.msgprint({ title: __("Please fill the vendor details"), message: problems.join("<br>"), indicator: "red" });
			return null;
		}
		return refs;
	}

	// ---- events ----
	$w.on("input", ".prq-amt", totals);
	$w.on("change", ".prq-amt", function () {
		const raw = $(this).val();
		const v = flt(raw);
		$(this).val(v ? flt(v, 2) : raw === "" ? "" : 0);
		totals();
	});
	$w.on("input change", ".prq-fields input, .prq-fields select", paint);
	$w.on("change", ".prq-adv", function () {
		allocate($(this).closest(".prq-card").data("g"));
	});
	$w.on("change", ".prq-all", function () {
		const $card = $(this).closest(".prq-card");
		$card.find(".prq-adv").prop("checked", this.checked);
		allocate($card.data("g"));
	});
	$w.on("click", ".prq-card-h", function (e) {
		if ($(e.target).closest("button").length) return;
		$(this).closest(".prq-card").toggleClass("collapsed");
	});
	$w.on("click", ".prq-toggle-all", function () {
		const collapse = $w.find(".prq-card:not(.collapsed)").length > 0;
		$w.find(".prq-card").toggleClass("collapsed", collapse);
		$(this).text(collapse ? __("Expand all") : __("Collapse all"));
	});
	// copy Mode of Payment + Nature / Section etc. (not cheque no / date) from one vendor to all others
	$w.on("click", ".prq-copy", function () {
		const src = groups[$(this).data("g")];
		groups.forEach((g) => {
			if (g === src) return;
			g.defs.forEach((def) => {
				if (def.bank) return;
				const v = src.ctrls[def.key].get_value();
				if (!prq_blank(v)) g.ctrls[def.key].set_value(v);
			});
			load_bank(g);
		});
		paint();
	});

	build_controls();
	allocate();
	d.show();

	groups.forEach((g, gi) => {
		if (!g.first.party_account) return render_advances(gi, { advances: [], advance_total: 0 });
		frappe
			.xcall(`${PRQ_PATH}.get_supplier_advances`, {
				company: prq_company(),
				party: g.first.party,
				account: g.first.party_account,
			})
			.then((res) => render_advances(gi, res))
			.catch(() => render_advances(gi, null));
	});
}