frappe.pages["srv-clearing-tree"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "SRV Clearing Analysis",
		single_column: true,
	});

	new SRVClearingTree(page);
};

const SRV_METHOD_MODULE =
	"informatics_custom_apps.ripl_customized_apps.page.srv_clearing_tree.srv_clearing_tree";

const SRV_PO_COLORS = [
	{ border: "#60a5fa", header: "#eff6ff" },
	{ border: "#4ade80", header: "#f0fdf4" },
	{ border: "#fbbf24", header: "#fffbeb" },
	{ border: "#f87171", header: "#fef2f2" },
	{ border: "#a78bfa", header: "#f5f3ff" },
	{ border: "#22d3ee", header: "#ecfeff" },
	{ border: "#f472b6", header: "#fdf2f8" },
	{ border: "#a3e635", header: "#f7fee7" },
];

const SRV_CHAIN_COLORS = [
	"#fffbeb",
	"#eff6ff",
	"#f0fdf4",
	"#fef2f2",
	"#f5f3ff",
	"#ecfeff",
	"#fdf2f8",
	"#f7fee7",
	"#fff7ed",
	"#eef2ff",
];

class SRVClearingTree {
	constructor(page) {
		this.page = page;
		this.filters = {};
		this.setup_filters();
		this.setup_body();
		this.set_default_account();
	}

	setup_filters() {
		this.company_field = this.page.add_field({
			fieldname: "company",
			label: "Company",
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
			change: () => {
				this.set_default_account();
			},
		});

		this.account_field = this.page.add_field({
			fieldname: "account",
			label: "Account",
			fieldtype: "Link",
			options: "Account",
			reqd: 1,
			get_query: () => ({
				filters: {
					company: this.company_field.get_value(),
					account_name: ["like", "%SRV%"],
				},
			}),
		});

		this.from_date_field = this.page.add_field({
			fieldname: "from_date",
			label: "From Date",
			fieldtype: "Date",
			default: this.get_fy_start(),
			reqd: 1,
		});

		this.to_date_field = this.page.add_field({
			fieldname: "to_date",
			label: "To Date",
			fieldtype: "Date",
			default: this.get_fy_end(),
			reqd: 1,
		});

		this.supplier_field = this.page.add_field({
			fieldname: "supplier",
			label: "Supplier",
			fieldtype: "Link",
			options: "Supplier",
		});

		this.plant_field = this.page.add_field({
			fieldname: "plant",
			label: "Plant",
			fieldtype: "Link",
			options: "Branch",
			get_query: () => ({
				filters: { company: this.company_field.get_value() },
			}),
		});

		this.run_btn = $(`
			<button type="button" class="btn btn-sm btn-primary srv-inline-run-btn">
				<svg width="13" height="13" viewBox="0 0 16 16" fill="none" style="margin-right:6px;vertical-align:-2px;">
					<path d="M2 3h12v2H2V3zm0 4h12v2H2V7zm0 4h8v2H2v-2z" fill="currentColor"/>
				</svg>
				${__("Show Data")}
			</button>
		`)
			.appendTo(this.page.page_form)
			.on("click", () => this.run());

		this.export_btn = $(`
			<button type="button" class="btn btn-sm btn-default srv-inline-export-btn">
				<svg width="13" height="13" viewBox="0 0 16 16" fill="none" style="margin-right:6px;vertical-align:-2px;">
					<path d="M2 2h8l4 4v8a1 1 0 01-1 1H2a1 1 0 01-1-1V3a1 1 0 011-1z" stroke="currentColor" stroke-width="1.2" fill="none"/>
					<path d="M5 8l1.5 3L8 9l1.5 2L11 8" stroke="currentColor" stroke-width="1.2" fill="none"/>
				</svg>
				${__("Export to Excel")}
			</button>
		`)
			.appendTo(this.page.page_form)
			.on("click", () => this.export_to_excel());
	}

	set_default_account() {
		const company = this.company_field.get_value();
		if (!company) return;

		frappe.call({
			method: `${SRV_METHOD_MODULE}.get_default_account`,
			args: { company },
			callback: (r) => {
				if (r.message) {
					this.account_field.set_value(r.message);
				}
			},
		});
	}

	get_fy_start() {
		const today = frappe.datetime.str_to_obj(frappe.datetime.get_today());
		const year = today.getMonth() >= 3 ? today.getFullYear() : today.getFullYear() - 1;
		return `${year}-04-01`;
	}

	get_fy_end() {
		const today = frappe.datetime.str_to_obj(frappe.datetime.get_today());
		const year = today.getMonth() >= 3 ? today.getFullYear() + 1 : today.getFullYear();
		return `${year}-03-31`;
	}

	get_filter_values() {
		return {
			company: this.company_field.get_value(),
			account: this.account_field.get_value(),
			from_date: this.from_date_field.get_value(),
			to_date: this.to_date_field.get_value(),
			supplier: this.supplier_field.get_value(),
			plant: this.plant_field.get_value(),
		};
	}

	setup_body() {
		if (!document.getElementById("srv-clearing-tree-style")) {
			const style = document.createElement("style");
			style.id = "srv-clearing-tree-style";
			style.textContent = `
				#page-srv-clearing-tree.page-container,
				#page-srv-clearing-tree .page-body,
				#page-srv-clearing-tree .container,
				#page-srv-clearing-tree .page-body > .container {
					max-width: 100% !important;
					width: 100% !important;
					padding-left: 20px !important;
					padding-right: 20px !important;
				}

				.srv-tree-wrapper { padding: 4px 2px 40px; transition: opacity 0.15s ease; width: 100%; }
				.srv-tree-summary-bar {
					display: flex; gap: 24px; padding: 10px 14px; margin-bottom: 12px;
					background: var(--fg-color); border: 1px solid var(--border-color);
					border-radius: var(--border-radius-md); font-size: 13px;
				}
				.srv-tree-summary-bar b { font-size: 14px; }

				.srv-table-scroll {
					overflow: auto; max-height: 74vh;
					border: 1px solid var(--border-color);
					border-radius: var(--border-radius-md);
					width: 100%;
				}
				table.srv-xl-table {
					table-layout: fixed; border-collapse: collapse;
					width: 100%; font-size: 12.5px;
					background: var(--card-bg);
				}
				table.srv-xl-table th, table.srv-xl-table td {
					border: 1px solid var(--border-color);
					border-right: 2px solid #374151;
					padding: 6px 10px;
					white-space: normal;
					word-break: break-word;
					overflow-wrap: break-word;
					vertical-align: top;
				}
				table.srv-xl-table th {
					position: sticky; top: 0; z-index: 2;
					background: var(--subtle-fg);
					font-weight: 600; text-align: left;
					font-size: 11px; text-transform: uppercase; letter-spacing: 0.02em;
					color: var(--text-muted);
				}
				table.srv-xl-table td.srv-num {
					text-align: right; font-variant-numeric: tabular-nums;
					white-space: nowrap;
				}
				table.srv-xl-table td.srv-empty { color: var(--text-muted); text-align: center; }

				tr.srv-group-header.srv-group-header-alert td { background: rgba(209,65,76,0.22) !important; }
				tr.srv-group-header.srv-group-header-rounding td { background: rgba(184,134,11,0.22) !important; }

				tr.srv-chain-start td {
					border-top: 3px solid #111827 !important;
				}

				tr.srv-group-header td {
					font-weight: 700; font-size: 12.5px;
					border-top: 2px solid var(--border-color);
				}

				tr.srv-chain-total td {
					font-weight: 600;
					border-top: 1px solid var(--border-color);
				}

				tr.srv-grand-total td {
					font-weight: 700; font-size: 13.5px; background: var(--subtle-fg);
					border-top: 3px double var(--border-color);
				}

				tr.srv-je-row td { font-style: italic; background: var(--fg-color); }

				.srv-flag {
					font-size: 9.5px; font-weight: 700; text-transform: uppercase;
					letter-spacing: 0.02em; border-radius: 4px; padding: 1px 5px;
					display: inline-block; margin-left: 4px;
				}
				.srv-flag-diff { color: #9a6a00; background: #fdf1d6; }
				.srv-flag-rejected { color: #a4313a; background: #fbe3e5; }
				.srv-flag-matched { color: #1f7a4d; background: #e2f5ea; }
				.srv-flag-rounding { color: #9a6a00; background: #fdf1d6; }

				.srv-amt-diff-pos { color: #1f7a4d; font-weight: 600; }
				.srv-amt-diff-neg { color: #a4313a; font-weight: 600; }
				.srv-amt-diff-zero { color: var(--text-muted); }

				.srv-remarks-cell { white-space: normal; min-width: 220px; }
				.srv-remarks-cell ul { margin: 0; padding-left: 16px; }
				.srv-remarks-cell li { margin-bottom: 2px; line-height: 1.4; }

				.srv-empty { padding: 40px; text-align: center; color: var(--text-muted); }

				#page-srv-clearing-tree .page-form {
					display: flex; flex-wrap: wrap; align-items: flex-end;
					gap: 18px;
					background: var(--card-bg);
					border: 1px solid var(--border-color);
					border-radius: 10px;
					padding: 18px 20px;
					margin-bottom: 16px;
					box-shadow: 0 1px 2px rgba(0,0,0,0.04);
				}
				#page-srv-clearing-tree .page-form .frappe-control {
					margin-bottom: 0;
					min-width: 160px;
				}
				#page-srv-clearing-tree .page-form .control-label {
					font-size: 11px; text-transform: uppercase; letter-spacing: 0.03em;
					color: var(--text-muted); font-weight: 600;
					margin-bottom: 4px;
				}

				#page-srv-clearing-tree .page-actions .btn-primary,
				#page-srv-clearing-tree .page-actions .btn-primary:focus {
					background-color: #eaf2ff;
					border-color: #cfe0ff;
					color: #2563eb;
					box-shadow: none;
				}
				#page-srv-clearing-tree .page-actions .btn-primary:hover {
					background-color: #d9e8ff;
					border-color: #b9d3ff;
					color: #1d4ed8;
				}
				#page-srv-clearing-tree .btn-default,
				#page-srv-clearing-tree .btn-secondary {
					background-color: #f3f4f6;
					border-color: #e5e7eb;
					color: #374151;
					box-shadow: none;
				}
				#page-srv-clearing-tree .btn-default:hover,
				#page-srv-clearing-tree .btn-secondary:hover {
					background-color: #e5e7eb;
				}

				#page-srv-clearing-tree .srv-inline-run-btn {
					display: inline-flex; align-items: center; justify-content: center;
					background-color: #2563eb;
					border-color: #2563eb;
					color: #fff;
					box-shadow: none;
					height: 34px;
					min-width: 130px;
					padding: 0 18px;
					border-radius: 6px;
					font-weight: 600;
					align-self: flex-end;
					margin-left: 4px;
					transition: background-color 0.12s ease;
				}
				#page-srv-clearing-tree .srv-inline-run-btn:hover:not(:disabled) {
					background-color: #1d4ed8;
					border-color: #1d4ed8;
					color: #fff;
				}
				#page-srv-clearing-tree .srv-inline-run-btn:active:not(:disabled) {
					background-color: #1e40af;
				}
				#page-srv-clearing-tree .srv-inline-run-btn:disabled {
					background-color: #93b4f8;
					border-color: #93b4f8;
					cursor: not-allowed;
				}

				#page-srv-clearing-tree .srv-inline-export-btn {
					display: inline-flex; align-items: center; justify-content: center;
					height: 34px;
					min-width: 150px;
					padding: 0 18px;
					border-radius: 6px;
					font-weight: 600;
					align-self: flex-end;
					margin-left: 4px;
				}

				.srv-progress-track {
					position: relative;
					height: 3px;
					width: 100%;
					background: var(--border-color);
					border-radius: 2px;
					overflow: hidden;
					margin-bottom: 14px;
				}
				.srv-progress-bar {
					position: absolute;
					top: 0; left: 0;
					height: 100%;
					width: 40%;
					background: #2563eb;
					border-radius: 2px;
					animation: srv-progress-slide 1.1s ease-in-out infinite;
				}
				@keyframes srv-progress-slide {
					0%   { left: -40%; }
					100% { left: 100%; }
				}
			`;
			document.head.appendChild(style);
		}

		this.$body = $(`<div class="srv-tree-wrapper"></div>`).appendTo(this.page.body);

		this.$progress = $(`
			<div class="srv-progress-track" style="display:none;">
				<div class="srv-progress-bar"></div>
			</div>
		`).insertBefore(this.$body);
	}

	run() {
		const filters = this.get_filter_values();

		if (!filters.company || !filters.account || !filters.from_date || !filters.to_date) {
			frappe.show_alert({
				message: __("Company, Account, From Date and To Date are required."),
				indicator: "orange",
			});
			return;
		}

		this.filters = filters;
		this.run_btn.prop("disabled", true);
		this.$progress.show();
		this.$body.css("opacity", 0.5);

		frappe.call({
			method: `${SRV_METHOD_MODULE}.get_data`,
			args: { filters },
			callback: (r) => {
				const result = (r.message && r.message.data) || [];
				this.render(result);
			},
			always: () => {
				this.run_btn.prop("disabled", false);
				this.$progress.hide();
				this.$body.css("opacity", 1);
			},
		});
	}

	get_earliest_date_from_rows(rows) {
		const dates = [];
		rows.forEach((row) => {
			[row.debit_date, row.credit_date, row.posting_date].forEach((d) => {
				if (d) {
					String(d)
						.split(",")
						.map((s) => s.trim())
						.filter(Boolean)
						.forEach((s) => dates.push(s));
				}
			});
		});
		dates.sort();
		return dates.length ? dates[0] : "9999-12-31";
	}

	unique(list) {
		return [...new Set((list || []).filter(Boolean))];
	}

	render(rows) {
		this.$body.empty();

		if (!rows.length) {
			this.$body.append(`<div class="srv-empty">${__("No data for the selected filters.")}</div>`);
			return;
		}

		const totalRow = rows.find((r) => r.posting_date === "Total");
		const dataRows = rows.filter((r) => r.posting_date !== "Total");

		const allRoots = dataRows.filter((r) => !r.parent);

		const roots = allRoots.filter((root) => root.je || Math.abs(root.net_impact || 0) > 0.005);

		const childrenByParent = {};
		dataRows
			.filter((r) => r.parent)
			.forEach((r) => {
				(childrenByParent[r.parent] = childrenByParent[r.parent] || []).push(r);
			});

		const ordered = roots
			.map((root) => {
				const children = childrenByParent[root.id] || [];
				return {
					root,
					children,
					earliest: this.get_earliest_date_from_rows(root.je ? [root] : children),
				};
			})
			.sort((a, b) => (a.earliest < b.earliest ? -1 : a.earliest > b.earliest ? 1 : 0));

		this.$body.append(this.render_summary_bar(roots, totalRow));

		const $scroll = $(`<div class="srv-table-scroll"></div>`);
		const $table = $(`
			<table class="srv-xl-table">
				<colgroup>
					<col style="width:7%">
					<col style="width:9%">
					<col style="width:14%">
					<col style="width:12%">
					<col style="width:10%">
					<col style="width:10%">
					<col style="width:10%">
					<col style="width:8%">
					<col style="width:auto">
				</colgroup>
				<thead>
					<tr>
						<th>${__("Date")}</th>
						<th>${__("Type")}</th>
						<th>${__("Document")}</th>
						<th>${__("Supplier")}</th>
						<th>${__("Debit")}</th>
						<th>${__("Credit")}</th>
						<th>${__("Net")}</th>
						<th>${__("Case")}</th>
						<th>${__("Remarks — What's Missing")}</th>
					</tr>
				</thead>
				<tbody></tbody>
			</table>
		`);
		const $tbody = $table.find("tbody");

		const html_parts = [];

		let po_idx = 0;

		ordered.forEach(({ root, children }) => {
			if (root.je) {
				html_parts.push(this.render_je_row(root));
				return;
			}
			const po_colors = SRV_PO_COLORS[po_idx % SRV_PO_COLORS.length];
			po_idx++;
			html_parts.push(...this.build_group_rows(root, children, po_colors));
		});

		if (totalRow) {
			html_parts.push(this.build_grand_total(totalRow));
		}

		$tbody.get(0).innerHTML = html_parts.join("");

		$scroll.append($table);
		this.$body.append($scroll);
	}

	render_summary_bar(roots, totalRow) {
		const groupRoots = roots.filter((r) => !r.je);
		const allGaps = groupRoots.filter((r) => Math.abs(r.net_impact || 0) > 0.005);
		const realGaps = allGaps.filter((r) => !r.is_rounding_only);
		const roundingGaps = allGaps.filter((r) => r.is_rounding_only);

		return `
			<div class="srv-tree-summary-bar">
				<div><b>${groupRoots.length}</b> ${__("Groups")}</div>
				<div><b style="${realGaps.length ? "color:#a4313a;" : ""}">${realGaps.length}</b> ${__("With Unresolved Gap")}</div>
				${roundingGaps.length ? `<div><b style="color:#9a6a00;">${roundingGaps.length}</b> ${__("Rounding Only")}</div>` : ""}
				${totalRow ? `<div><b>${format_currency(totalRow.net_impact || 0)}</b> ${__("Net Difference")}</div>` : ""}
			</div>
		`;
	}

	po_stripe_style(po_colors) {
		return `border-left:5px solid ${po_colors.border};`;
	}

	build_group_rows(root, children, po_colors) {
		const rows = [];
		const stripe = this.po_stripe_style(po_colors);

		const has_gap = Math.abs(root.net_impact || 0) > 0.005;
		const is_rounding = has_gap && root.is_rounding_only;
		const header_cls =
			(is_rounding ? "srv-group-header-rounding" : has_gap ? "srv-group-header-alert" : "");

		const earliest = this.get_earliest_date_from_rows(children.length ? children : [root]);
		const label = root.purchase_order || root.supplier_name || root.supplier || __("Unlinked Group");

		rows.push(`
			<tr class="srv-group-header ${header_cls}" style="background-color:${po_colors.header};">
				<td style="${stripe}">${frappe.utils.escape_html(earliest)}</td>
				<td colspan="2">
					${frappe.utils.escape_html(label)}
					${root.purchase_order && (root.supplier_name || root.supplier) ? ` — ${frappe.utils.escape_html(root.supplier_name || root.supplier)}` : ""}
				</td>
				<td>${children.length} ${__("voucher(s)")}</td>
				<td colspan="5"></td>
			</tr>
		`);

		const child_by_doc = {};
		children.forEach((c) => {
			const name = c.purchase_invoice || c.purchase_receipt || c.return_pr || c.return_invoice || c.lcv;
			if (name) child_by_doc[name] = c;
		});

		const edges = root.edges || [];

		const pi_docs_all = this.unique(
			children.filter((c) => c.purchase_invoice).map((c) => c.purchase_invoice)
		);

		const consumed = new Set();
		let chain_color_idx = 0;

		pi_docs_all.forEach((pi_name) => {
			const pr_docs = this.unique(
				edges.filter((e) => e.type === "PI-PR" && e.from === pi_name).map((e) => e.to)
			);
			const lcv_docs = this.unique(
				edges
					.filter((e) => e.type === "LCV-PR" && pr_docs.includes(e.to))
					.map((e) => e.from)
			);
			const pi_debit_note_docs = this.unique(
				edges.filter((e) => e.type === "PI-RETURN_PI" && e.from === pi_name).map((e) => e.to)
			);
			const return_pr_docs = this.unique(
				edges
					.filter((e) => e.type === "PR-RETURN_PR" && pr_docs.includes(e.from))
					.map((e) => e.to)
			);
			const return_debit_note_docs = this.unique(
				edges
					.filter((e) => e.type === "RETURN_PR-RETURN_PI" && return_pr_docs.includes(e.from))
					.map((e) => e.to)
			);

			consumed.add(pi_name);
			[...pr_docs, ...lcv_docs, ...pi_debit_note_docs, ...return_pr_docs, ...return_debit_note_docs].forEach(
				(d) => consumed.add(d)
			);

			const chain_steps = [
				{ label: __("PI"), doctype: "Purchase Invoice", name: pi_name, is_anchor: true },
				...pr_docs.map((d) => ({ label: __("PR"), doctype: "Purchase Receipt", name: d })),
				...lcv_docs.map((d) => ({ label: __("LCV"), doctype: "Landed Cost Voucher", name: d, always_show: true })),
				...pi_debit_note_docs.map((d) => ({ label: __("Debit Note (vs PI)"), doctype: "Purchase Invoice", name: d })),
				...return_pr_docs.map((d) => ({ label: __("Return PR"), doctype: "Purchase Receipt", name: d, always_show: true })),
				...return_debit_note_docs.map((d) => ({ label: __("Debit Note (vs Return PR)"), doctype: "Purchase Invoice", name: d })),
			];

			let chain_debit = 0;
			let chain_credit = 0;
			chain_steps.forEach((step) => {
				const c = child_by_doc[step.name];
				chain_debit += c ? c.gl_debit || 0 : 0;
				chain_credit += c ? c.gl_credit || 0 : 0;
			});
			const chain_net = chain_debit - chain_credit;

			if (Math.abs(chain_net) < 0.005) {
				return;
			}

			const chain_color = SRV_CHAIN_COLORS[chain_color_idx % SRV_CHAIN_COLORS.length];
			const is_chain_boundary = chain_color_idx > 0;
			chain_color_idx++;

			const pi_child = child_by_doc[pi_name] || {};
			const remark_cell_html = this.render_remark_cell(pi_child.remarks || "");

			const visible_steps = chain_steps
				.map((step) => {
					const c = child_by_doc[step.name];
					const debit = c ? c.gl_debit || 0 : 0;
					const credit = c ? c.gl_credit || 0 : 0;
					const net = debit - credit;
					return { step, c, debit, credit, net };
				})
				.filter(({ step, net }) => step.is_anchor || step.always_show || Math.abs(net) >= 0.005);

			const remarks_rowspan = visible_steps.length + 1;

			visible_steps.forEach(({ step, c, debit, credit, net }) => {
				const case_label = (c && c.case) || "";
				const case_cls = case_label.includes("Rejected")
					? "srv-flag-rejected"
					: case_label.includes("Rate Difference")
					? "srv-flag-diff"
					: case_label
					? "srv-flag-matched"
					: "";

				const boundary_cls = step.is_anchor && is_chain_boundary ? "srv-chain-start" : "";
				const no_srv_impact = step.always_show && Math.abs(net) < 0.005;
				const type_label = no_srv_impact
					? `${frappe.utils.escape_html(step.label)} <span style="color:var(--text-muted);font-weight:400;font-size:11px;">(${__("no SRV impact")})</span>`
					: frappe.utils.escape_html(step.label);

				const remarks_td = step.is_anchor
					? `<td class="srv-remarks-cell" rowspan="${remarks_rowspan}">${remark_cell_html}</td>`
					: "";

				rows.push(`
					<tr class="${boundary_cls}" style="background-color:${chain_color};">
						<td style="${stripe}">${frappe.utils.escape_html((c && c.posting_date) || "")}</td>
						<td>${type_label}</td>
						<td>${this.render_doc_cell(step.doctype, step.name)}</td>
						<td>${frappe.utils.escape_html((c && (c.supplier_name || c.supplier)) || root.supplier_name || root.supplier || "")}</td>
						<td class="srv-num">${this.fmt_currency(debit)}</td>
						<td class="srv-num">${this.fmt_currency(credit)}</td>
						<td class="srv-num">${this.fmt_diff(net)}</td>
						<td>${case_label ? `<span class="srv-flag ${case_cls}">${frappe.utils.escape_html(case_label)}</span>` : ""}</td>
						${remarks_td}
					</tr>
				`);
			});

			rows.push(`
				<tr class="srv-chain-total" style="background-color:${chain_color};">
					<td colspan="4" style="${stripe}">${__("Chain Total")} — ${frappe.utils.escape_html(pi_name)}</td>
					<td class="srv-num">${this.fmt_currency(chain_debit)}</td>
					<td class="srv-num">${this.fmt_currency(chain_credit)}</td>
					<td class="srv-num">${this.fmt_diff(chain_net)}</td>
					<td></td>
				</tr>
			`);
		});

		children
			.filter((c) => {
				const name = c.purchase_invoice || c.purchase_receipt || c.return_pr || c.return_invoice || c.lcv;
				if (!name || consumed.has(name)) return false;
				return Math.abs(c.net_impact || 0) >= 0.005;
			})
			.forEach((c) => {
				const name = c.purchase_invoice || c.purchase_receipt || c.return_pr || c.return_invoice || c.lcv;
				const meta = this.leftover_doc_meta(c);

				rows.push(`
					<tr style="background-color:${po_colors.header};">
						<td style="${stripe}">${frappe.utils.escape_html(c.posting_date || "")}</td>
						<td>${frappe.utils.escape_html(meta.label)}</td>
						<td>${this.render_doc_cell(meta.doctype, name)}</td>
						<td>${frappe.utils.escape_html(c.supplier_name || c.supplier || "")}</td>
						<td class="srv-num">${this.fmt_currency(c.gl_debit)}</td>
						<td class="srv-num">${this.fmt_currency(c.gl_credit)}</td>
						<td class="srv-num">${this.fmt_diff(c.net_impact)}</td>
						<td></td>
						<td class="srv-remarks-cell">${this.render_remark_cell(c.remarks || "")}</td>
					</tr>
				`);
			});

		return rows;
	}

	leftover_doc_meta(c) {
		if (c.purchase_receipt) return { label: __("PR"), doctype: "Purchase Receipt" };
		if (c.purchase_invoice) return { label: __("PI"), doctype: "Purchase Invoice" };
		if (c.return_pr) return { label: __("Return PR"), doctype: "Purchase Receipt" };
		if (c.return_invoice) return { label: __("Debit Note"), doctype: "Purchase Invoice" };
		if (c.lcv) return { label: __("LCV"), doctype: "Landed Cost Voucher" };
		return { label: "", doctype: "" };
	}

	shorten_remark_line(line) {
		const rupee = (n) => "₹" + Number(n.replace(/,/g, "")).toLocaleString("en-IN");

		let m;

		if ((m = line.match(/debit and credit differ by less than .* rounding drift/i))) {
			return "Rounding difference only — not a real gap";
		}
		if ((m = line.match(/no Purchase Receipt is linked.*?([\d,]+\.\d{2}) isn't reconciled/i))) {
			return `No PR linked — ${rupee(m[1])} unreconciled`;
		}
		if ((m = line.match(/PO rate differs from the PR rate on (\S+) but no Landed Cost Voucher/i))) {
			return `Rate mismatch on ${m[1]} — no LCV raised yet`;
		}
		if ((m = line.match(/LCV \(([^)]+)\) has adjusted .*? no Debit Note has been raised/i))) {
			return `LCV ${m[1]} not passed to SRV — no debit note`;
		}
		if ((m = line.match(/(\d+) Landed Cost Vouchers raised/i))) {
			return `${m[1]} LCVs raised — check all have a matching debit note`;
		}
		if ((m = line.match(/Return PR \(([^)]+)\).*?no Return Invoice \/ Debit Note has been raised/i))) {
			return `Return PR ${m[1]} — no debit note, SRV still shows full amount`;
		}
		if ((m = line.match(/linked PR\(s\) \(([^)]+)\) don't fully clear this PI \(([\d,]+\.\d{2})/i))) {
			return `PR(s) ${m[1]} don't fully clear PI — ${rupee(m[2])} remaining`;
		}
		if ((m = line.match(/no Purchase Invoice has been booked against this PR.*?\(([\d,]+\.\d{2})/i))) {
			return `No PI booked — ${rupee(m[1])} unbilled`;
		}
		if ((m = line.match(/^(.*?):.*could not be found — cancelled, renamed, or deleted/i))) {
			return `${m[1]}: not found (cancelled/renamed?)`;
		}
		if ((m = line.match(/^(\S+ \S+) exists \(dated ([\d-]+)\) but falls outside the selected date range/i))) {
			return `${m[1]} (${m[2]}) — outside date range`;
		}
		if ((m = line.match(/no document in this chain posted to the SRV account/i))) {
			return "No document in this chain hit SRV — zero impact";
		}
		if ((m = line.match(/still doesn't net to zero \(([\d,]+\.\d{2})\)/i))) {
			return `Unresolved gap — ${rupee(m[1])}, check for cancelled/amended voucher`;
		}

		return line.replace(/^(PI|PR)\s+\S+:\s*/, "").trim();
	}

	is_expected_no_srv_impact_line(line) {
		return /is linked to this chain but never posts to the filtered account/i.test(line);
	}

	render_remark_cell(text) {
		if (!text) return "";
		const lines = text.split("\n").filter(Boolean).filter((l) => !this.is_expected_no_srv_impact_line(l));
		if (!lines.length) return "";

		if (lines.length === 1) {
			return `<span>${frappe.utils.escape_html(this.shorten_remark_line(lines[0]))}</span>`;
		}

		const items = lines
			.map((l) => `<li>${frappe.utils.escape_html(this.shorten_remark_line(l))}</li>`)
			.join("");
		return `<ul style="margin:0;padding-left:14px;">${items}</ul>`;
	}

	render_doc_cell(doctype, value) {
		if (!value) {
			return `<span class="srv-empty">—</span>`;
		}
		return `<a href="/app/${frappe.router.slug(doctype)}/${encodeURIComponent(value)}" target="_blank">${frappe.utils.escape_html(value)}</a>`;
	}

	render_je_row(row) {
		return `
			<tr class="srv-je-row">
				<td>${frappe.utils.escape_html(row.posting_date || "")}</td>
				<td colspan="2">
					${__("Journal Entry")}:
					<a href="/app/journal-entry/${encodeURIComponent(row.je)}" target="_blank">${frappe.utils.escape_html(row.je)}</a>
				</td>
				<td></td>
				<td class="srv-num">${this.fmt_currency(row.gl_debit)}</td>
				<td class="srv-num">${this.fmt_currency(row.gl_credit)}</td>
				<td class="srv-num">${this.fmt_diff(row.net_impact)}</td>
				<td></td>
				<td></td>
			</tr>
		`;
	}

	build_grand_total(row) {
		return `
			<tr class="srv-grand-total">
				<td colspan="4">${__("Grand Total")}</td>
				<td class="srv-num">${this.fmt_currency(row.gl_debit)}</td>
				<td class="srv-num">${this.fmt_currency(row.gl_credit)}</td>
				<td class="srv-num">${this.fmt_diff(row.net_impact)}</td>
				<td></td>
				<td></td>
			</tr>
		`;
	}

	fmt_currency(value) {
		return format_currency(value || 0);
	}

	fmt_diff(value) {
		value = value || 0;
		const cls =
			Math.abs(value) < 0.005
				? "srv-amt-diff-zero"
				: value > 0
				? "srv-amt-diff-pos"
				: "srv-amt-diff-neg";
		return `<span class="${cls}">${format_currency(value)}</span>`;
	}

	export_to_excel() {
		const $table = this.$body.find("table.srv-xl-table");

		if (!$table.length) {
			frappe.show_alert({
				message: __("Load data before exporting."),
				indicator: "orange",
			});
			return;
		}

		const html = `
			<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns="http://www.w3.org/TR/REC-html40">
			<head>
				<meta charset="UTF-8">
				<!--[if gte mso 9]>
				<xml>
					<x:ExcelWorkbook>
						<x:ExcelWorksheets>
							<x:ExcelWorksheet>
								<x:Name>SRV Clearing Analysis</x:Name>
								<x:WorksheetOptions>
									<x:DisplayGridlines/>
								</x:WorksheetOptions>
							</x:ExcelWorksheet>
						</x:ExcelWorksheets>
					</x:ExcelWorkbook>
				</xml>
				<![endif]-->
			</head>
			<body>${$table.prop("outerHTML")}</body>
			</html>
		`;

		const blob = new Blob(["\ufeff" + html], { type: "application/vnd.ms-excel" });
		const url = URL.createObjectURL(blob);

		const company = (this.filters && this.filters.company) || "";
		const from_date = (this.filters && this.filters.from_date) || "";
		const to_date = (this.filters && this.filters.to_date) || "";
		const filename = `SRV_Clearing_Analysis_${company}_${from_date}_to_${to_date}.xls`.replace(/\s+/g, "_");

		const a = document.createElement("a");
		a.href = url;
		a.download = filename;
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
		URL.revokeObjectURL(url);
	}
}