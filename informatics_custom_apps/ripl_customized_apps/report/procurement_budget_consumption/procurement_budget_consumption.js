// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["Procurement Budget Consumption"] = {

	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
		},
		{
			fieldname: "fiscal_year",
			label: __("Fiscal Year"),
			fieldtype: "Link",
			options: "Fiscal Year",
		},
		{
			fieldname: "gl_accounts",
			label: __("GL Account"),
			fieldtype: "MultiSelectList",
			get_data: function(txt) {
				return frappe.db.get_link_options("Account", txt);
			}
		},
		{
			fieldname: "plants",
			label: __("Plant"),
			fieldtype: "MultiSelectList",
			get_data: function(txt) {
				return frappe.db.get_link_options("Branch", txt);
			}
		},
		{
			fieldname: "segments",
			label: __("Segment"),
			fieldtype: "MultiSelectList",
			get_data: function(txt) {
				return frappe.db.get_link_options("Segment", txt);
			}
		},
		{
			fieldname: "hide_small_budget",
			label: __("Budget > 1 Only"),
			fieldtype: "Check",
			default: 1
		},
	],

	formatter: function(value, row, column, data, default_formatter) {

		value = default_formatter(value, row, column, data);

		if (!data) return value;

		if (column.fieldname === "total_mr_amount" && flt(data.total_mr_amount)) {
			return `<a class="mr-drilldown"
				data-gl="${data.gl_account || ''}"
				data-cost-center="${data.cost_center || ''}"
				data-plant="${data.plant || ''}"
				data-segment="${data.segment || ''}"
				style="font-weight:bold;">${value}</a>`;
		}

		if (column.fieldname === "po_amount" && flt(data.po_amount)) {
			return `<a class="po-drilldown"
				data-gl="${data.gl_account || ''}"
				data-cost-center="${data.cost_center || ''}"
				data-plant="${data.plant || ''}"
				data-segment="${data.segment || ''}"
				style="font-weight:bold;">${value}</a>`;
		}

		if (column.fieldname === "invoice_amount" && flt(data.invoice_amount)) {
			return `<a class="rc-drilldown"
				data-gl="${data.gl_account || ''}"
				data-cost-center="${data.cost_center || ''}"
				data-plant="${data.plant || ''}"
				data-segment="${data.segment || ''}"
				style="font-weight:bold; color: var(--purple);">${value}</a>`;
		}

		return value;
	},

	after_datatable_render: function() {

		// ── MR drilldown ──
		$(document).off("click", ".mr-drilldown");
		$(document).on("click", ".mr-drilldown", function() {
			frappe.set_route("query-report", "Procurement Budget MR Drilldown", {
				company:      frappe.query_report.get_filter_value("company"),
				fiscal_year:  frappe.query_report.get_filter_value("fiscal_year"),
				gl_account:   $(this).data("gl"),
				cost_center:  $(this).data("cost-center"),
				plant:        $(this).data("plant"),
				segment:      $(this).data("segment")
			});
		});

		// ── PO drilldown ──
		$(document).off("click", ".po-drilldown");
		$(document).on("click", ".po-drilldown", function() {
			frappe.set_route("query-report", "Procurement Budget PO Drilldown", {
				company:      frappe.query_report.get_filter_value("company"),
				fiscal_year:  frappe.query_report.get_filter_value("fiscal_year"),
				gl_account:   $(this).data("gl"),
				cost_center:  $(this).data("cost-center"),
				plant:        $(this).data("plant"),
				segment:      $(this).data("segment")
			});
		});

		// ── RC drilldown ──
		$(document).off("click", ".rc-drilldown");
		$(document).on("click", ".rc-drilldown", function() {
			const gl          = $(this).data("gl");
			const cost_center = $(this).data("cost-center");
			const plant       = $(this).data("plant");
			const segment     = $(this).data("segment");

			frappe.call({
				method: "informatics_custom_apps.ripl_customized_apps.report.procurement_budget_consumption.procurement_budget_consumption.get_rc_invoice_drilldown",
				args: {
					gl_account:   gl,
					cost_center:  cost_center,
					plant:        plant,
					segment:      segment
				},
				freeze: true,
				freeze_message: __("Loading Rate Contract Invoices…"),
				callback: function(r) {
					if (!r.message || !r.message.length) {
						frappe.msgprint(__("No invoices found for this combination."));
						return;
					}
					pbc_show_rc_dialog(gl, cost_center, plant, segment, r.message);
				}
			});
		});
	}
};

function pbc_show_rc_dialog(gl, cost_center, plant, segment, rows) {

	const invoiceMap = {};
	rows.forEach(row => {
		if (!invoiceMap[row.invoice]) {
			invoiceMap[row.invoice] = {
				invoice:  row.invoice,
				supplier: row.supplier,
				contract: row.contract,
				items:    [],
				subtotal: 0
			};
		}
		invoiceMap[row.invoice].items.push(row);
		invoiceMap[row.invoice].subtotal += flt(row.amount);
	});

	const invoices   = Object.values(invoiceMap);
	const grandTotal = invoices.reduce((s, inv) => s + inv.subtotal, 0);
	const fmt        = (n) => frappe.format(n, { fieldtype: "Currency" });


	function buildFlatRows(invoiceList) {
		const flat = [];
		invoiceList.forEach((inv, idx) => {
			const bg = idx % 2 === 0 ? "#ffffff" : "#f8fafc";
			inv.items.forEach((item, iIdx) => {
				flat.push({ type: "item", inv, item, iIdx, bg });
			});
			flat.push({ type: "subtotal", inv });
		});
		flat.push({ type: "total", grandTotal });
		return flat;
	}

	let flatRows     = buildFlatRows(invoices);
	let filteredRows = flatRows;

	const ROW_H = 36; 

	function renderRow(vr) {
		if (vr.type === "total") {
			return `<tr style="height:${ROW_H}px;background:#1e3a8a;">
				<td colspan="6" style="padding:0 12px;font-weight:900;font-size:13px;color:#fff;">Grand Total</td>
				<td style="padding:0 12px;text-align:right;font-weight:900;font-size:13px;color:#fff;">${fmt(vr.grandTotal)}</td>
			</tr>`;
		}
		if (vr.type === "subtotal") {
			return `<tr style="height:${ROW_H}px;background:#eff6ff;border-top:1px solid #bfdbfe;">
				<td colspan="6" style="padding:0 12px;font-weight:800;color:#1d4ed8;font-size:12px;">
					↳ ${vr.inv.invoice} total
				</td>
				<td style="padding:0 12px;text-align:right;font-weight:900;color:#1d4ed8;">${fmt(vr.inv.subtotal)}</td>
			</tr>`;
		}
		const { inv, item, iIdx, bg } = vr;
		const isFirst = iIdx === 0;
		return `<tr style="height:${ROW_H}px;background:${bg};border-bottom:1px solid #f0f4f8;">
			<td style="padding:0 12px;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
				${isFirst ? `<a href="/app/purchase-invoice/${inv.invoice}" target="_blank"
					style="font-weight:700;color:#2563eb;">${inv.invoice}</a>` : ""}
			</td>
			<td style="padding:0 12px;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
				${isFirst ? `<span style="font-weight:600;">${inv.supplier}</span>` : ""}
			</td>
			<td style="padding:0 12px;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
				${isFirst ? `<a href="/app/contract/${inv.contract}" target="_blank"
					style="color:#7c3aed;font-weight:600;">${inv.contract}</a>` : ""}
			</td>
			<td style="padding:0 12px;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
				<a href="/app/item/${item.item_code}" target="_blank"
					style="color:#2563eb;font-weight:600;">${item.item_code}</a>
				${item.item_name && item.item_name !== item.item_code
					? `<span style="color:#6b7280;margin-left:4px;">${item.item_name}</span>`
					: ""}
			</td>
			<td style="padding:0 12px;text-align:right;font-size:12px;">${flt(item.qty).toFixed(2)}</td>
			<td style="padding:0 12px;text-align:right;font-size:12px;">${fmt(item.rate)}</td>
			<td style="padding:0 12px;text-align:right;font-weight:700;font-size:12px;">${fmt(item.amount)}</td>
		</tr>`;
	}

	const COLS = `<colgroup>
		<col style="width:15%"><col style="width:16%"><col style="width:13%">
		<col style="width:28%"><col style="width:7%">
		<col style="width:10%"><col style="width:11%">
	</colgroup>`;

	const TH = (label, align = "left") =>
		`<th style="padding:8px 12px;text-align:${align};font-size:12px;font-weight:800;color:#374151;white-space:nowrap;">${label}</th>`;

	const metaHtml = `
		<!-- ① Frozen top: meta info + search + column headers ────────────── -->
		<div style="position:sticky;top:0;z-index:20;background:#fff;padding-bottom:4px;">

			<div style="font-size:12px;color:#6b7280;margin-bottom:6px;line-height:1.6;">
				<strong>GL:</strong> ${gl} &nbsp;·&nbsp;
				<strong>Cost Centre:</strong> ${cost_center}
				${plant   ? `&nbsp;·&nbsp;<strong>Plant:</strong> ${plant}`     : ""}
				${segment ? `&nbsp;·&nbsp;<strong>Segment:</strong> ${segment}` : ""}
				&nbsp;&nbsp;<span id="pbc-row-count" style="color:#374151;font-size:11px;"></span>&nbsp;&nbsp;<span id="pbc-inv-count" style="color:#374151;font-size:11px;font-weight:600;"></span>
			</div>

			<input id="pbc-search" type="text" placeholder="Search invoice, supplier, item…"
				style="width:100%;padding:6px 10px;border:1px solid #d1d5db;border-radius:6px;
					font-size:13px;margin-bottom:6px;box-sizing:border-box;">

			<table style="width:100%;border-collapse:collapse;table-layout:fixed;">
				${COLS}
				<thead>
					<tr style="background:#f1f5f9;border-bottom:2px solid #e2e8f0;">
						${TH("Invoice")}
						${TH("Supplier")}
						${TH("Contract")}
						${TH("Item")}
						${TH("Qty",    "right")}
						${TH("Rate",   "right")}
						${TH("Amount", "right")}
					</tr>
				</thead>
			</table>
		</div>

		<!-- ② Scrollable body — no thead inside ──────────────────────────── -->
		<div id="pbc-scroll" style="max-height:420px;overflow-y:auto;">
			<div id="pbc-spacer-top" style="height:0px;pointer-events:none;"></div>
			<table style="width:100%;border-collapse:collapse;table-layout:fixed;">
				${COLS}
				<tbody id="pbc-tbody"></tbody>
			</table>
			<div id="pbc-spacer-bot" style="height:0px;pointer-events:none;"></div>
		</div>`;

	const d = new frappe.ui.Dialog({
		title:                __("Rate Contract Invoices"),
		size:                 "extra-large",
		fields:               [{ fieldtype: "HTML", fieldname: "rc_html" }],
		primary_action_label: __("⬇ Export CSV"),
		primary_action: function() {
			pbc_export_rc_csv(invoices, grandTotal, gl, cost_center, plant, segment);
		}
	});

	d.fields_dict.rc_html.$wrapper.html(metaHtml);

	d.$wrapper.one("shown.bs.modal", function() {

		const root     = d.$wrapper[0];                            
		const scroller = root.querySelector("#pbc-scroll");
		const tbody    = root.querySelector("#pbc-tbody");
		const spacerT  = root.querySelector("#pbc-spacer-top");
		const spacerB  = root.querySelector("#pbc-spacer-bot");
		const countEl  = root.querySelector("#pbc-row-count");
		const searchEl  = root.querySelector("#pbc-search");
		const invCountEl = root.querySelector("#pbc-inv-count");

		const BUFFER = 15;
		let startIdx = 0;

		function paint() {
			const scrollTop = scroller.scrollTop;
			const viewportH = scroller.clientHeight;

			const visStart = Math.max(0, Math.floor(scrollTop / ROW_H) - BUFFER);
			const visEnd   = Math.min(
				filteredRows.length,
				Math.ceil((scrollTop + viewportH) / ROW_H) + BUFFER
			);

			if (visStart === startIdx && tbody.children.length === (visEnd - visStart)) return;
			startIdx = visStart;

			tbody.innerHTML = filteredRows.slice(visStart, visEnd).map(vr => renderRow(vr)).join("");

			spacerT.style.height = (visStart * ROW_H) + "px";
			spacerB.style.height = Math.max(0, (filteredRows.length - visEnd) * ROW_H) + "px";
		}

		function updateCount() {
			const totalRows    = flatRows.length;
			const filteredRows_ = filteredRows.length;
			const invSet = new Set();
			filteredRows.forEach(vr => { if (vr.type === "item") invSet.add(vr.inv.invoice); });
			const invCount = invSet.size;
			const totalInv = invoices.length;

			countEl.textContent = filteredRows_ < totalRows
				? `Showing ${filteredRows_.toLocaleString()} / ${totalRows.toLocaleString()} rows`
				: `${totalRows.toLocaleString()} rows`;

			invCountEl.textContent = invCount < totalInv
				? `· ${invCount.toLocaleString()} / ${totalInv.toLocaleString()} invoices`
				: `· ${totalInv.toLocaleString()} invoice${totalInv !== 1 ? "s" : ""}`;
		}

		let searchTimer;
		searchEl.addEventListener("input", function() {
			clearTimeout(searchTimer);
			searchTimer = setTimeout(() => {
				const q = this.value.trim().toLowerCase();
				if (!q) {
					filteredRows = flatRows;
				} else {
					const matchingInvoices = new Set();
					invoices.forEach(inv => {
						if (
							inv.invoice.toLowerCase().includes(q)  ||
							inv.supplier.toLowerCase().includes(q) ||
							inv.contract.toLowerCase().includes(q) ||
							inv.items.some(it =>
								(it.item_name || "").toLowerCase().includes(q) ||
								(it.item_code || "").toLowerCase().includes(q)
							)
						) {
							matchingInvoices.add(inv.invoice);
						}
					});
					filteredRows = buildFlatRows(
						invoices.filter(inv => matchingInvoices.has(inv.invoice))
					);
				}
				scroller.scrollTop = 0;
				startIdx = 0;   // reset so paint() doesn't short-circuit
				paint();
				updateCount();
			}, 200);
		});

		let rafPending = false;
		scroller.addEventListener("scroll", () => {
			if (rafPending) return;
			rafPending = true;
			requestAnimationFrame(() => { paint(); rafPending = false; });
		}, { passive: true });

		updateCount();
		paint();
	});

	d.show(); 
}

function pbc_export_rc_csv(invoices, grandTotal, gl, cost_center, plant, segment) {

	const escCsv = (v) => {
		const s = (v === null || v === undefined) ? "" : String(v);
		return s.includes(",") || s.includes('"') || s.includes("\n")
			? `"${s.replace(/"/g, '""')}"`
			: s;
	};

	const headers = ["Invoice", "Supplier", "Contract", "Item Code", "Item Name",
		"Qty", "Rate", "Amount"];

	const rows = [headers.join(",")];

	invoices.forEach(inv => {
		inv.items.forEach(item => {
			rows.push([
				escCsv(inv.invoice),
				escCsv(inv.supplier),
				escCsv(inv.contract),
				escCsv(item.item_code),
				escCsv(item.item_name),
				escCsv(flt(item.qty).toFixed(2)),
				escCsv(flt(item.rate).toFixed(2)),
				escCsv(flt(item.amount).toFixed(2)),
			].join(","));
		});
		rows.push([
			escCsv(`↳ ${inv.invoice} Total`), "", "", "", "", "", "",
			escCsv(flt(inv.subtotal).toFixed(2))
		].join(","));
		rows.push("");
	});

	rows.push(["Grand Total", "", "", "", "", "", "",
		escCsv(flt(grandTotal).toFixed(2))].join(","));

	const meta = [
		`"GL: ${gl}"`,
		`"Cost Centre: ${cost_center}"`,
		plant   ? `"Plant: ${plant}"`     : "",
		segment ? `"Segment: ${segment}"` : "",
	].filter(Boolean).join(",");

	const csvContent = [meta, "", rows.join("\n")].join("\n");

	const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
	const url  = URL.createObjectURL(blob);
	const a    = document.createElement("a");
	a.href     = url;
	a.download = `RC_Invoices_${gl}_${cost_center}${plant ? "_" + plant : ""}${segment ? "_" + segment : ""}.csv`
		.replace(/[^a-zA-Z0-9_\-\.]/g, "_");
	document.body.appendChild(a);
	a.click();
	document.body.removeChild(a);
	URL.revokeObjectURL(url);
}