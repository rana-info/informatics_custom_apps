frappe.pages['dispatch-order-balan'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Dispatch Order Balance',
		single_column: true,
	});
	new DispatchOrderBalancePage(page);
};

class DispatchOrderBalancePage {
	constructor(page) {
		this.page   = page;
		this.last_data    = null;
		this._refresh_timer = null;
		this.inject_styles();
		this.make_layout();
		this.make_filters();
		this.make_menu();
		this.refresh();
	}

	inject_styles() {
		if ($('#dob-style').length) return;
		$(`<style id="dob-style">
			@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

			.dob-page-wrap * { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }

			.dob-page-wrap {
				padding: 20px 24px 60px;
				background: #F4F7FB;
				min-height: 100vh;
			}

			.dob-filter-bar {
				display: flex;
				flex-wrap: wrap;
				align-items: flex-end;
				gap: 12px 18px;
				background: #ffffff;
				border: 1px solid #DDE3EE;
				border-radius: 12px;
				padding: 16px 20px 14px;
				margin-bottom: 24px;
				box-shadow: 0 2px 10px rgba(15,27,60,.06);
			}
			.dob-filter-item {
				display: flex;
				flex-direction: column;
				min-width: 150px;
				max-width: 210px;
				flex: 1 1 150px;
			}
			.dob-filter-item label {
				font-size: 11px;
				font-weight: 700;
				letter-spacing: .6px;
				text-transform: uppercase;
				color: #7A8AA0;
				margin-bottom: 5px;
			}
			.dob-filter-item .form-control,
			.dob-filter-item .input-with-feedback {
				height: 34px !important;
				font-size: 13.5px !important;
				padding: 4px 10px !important;
				border-radius: 6px !important;
				border: 1.5px solid #DDE3EE !important;
				background: #F8FAFD !important;
				transition: border-color .15s, box-shadow .15s;
			}
			.dob-filter-item .form-control:focus,
			.dob-filter-item .input-with-feedback:focus {
				border-color: #3B6FE0 !important;
				box-shadow: 0 0 0 3px rgba(59,111,224,.12) !important;
				background: #fff !important;
				outline: none !important;
			}
			.dob-filter-item .link-btn { display: none !important; }

			/* ── Show Zero Pending toggle ────────────────────────────────── */
			.dob-filter-item.dob-filter-check {
				flex: 0 0 auto;
				min-width: auto;
				flex-direction: row;
				align-items: center;
				padding-bottom: 7px;
			}
			.dob-toggle {
				display: flex;
				align-items: center;
				gap: 9px;
				cursor: pointer;
				user-select: none;
			}
			.dob-toggle input[type="checkbox"] {
				position: absolute;
				opacity: 0;
				width: 0;
				height: 0;
			}
			.dob-toggle-track {
				position: relative;
				width: 36px;
				height: 20px;
				background: #DDE3EE;
				border-radius: 20px;
				transition: background .15s;
				flex-shrink: 0;
			}
			.dob-toggle-thumb {
				position: absolute;
				top: 2px;
				left: 2px;
				width: 16px;
				height: 16px;
				background: #fff;
				border-radius: 50%;
				box-shadow: 0 1px 3px rgba(15,27,60,.25);
				transition: transform .15s;
			}
			.dob-toggle input:checked + .dob-toggle-track {
				background: #3B6FE0;
			}
			.dob-toggle input:checked + .dob-toggle-track .dob-toggle-thumb {
				transform: translateX(16px);
			}
			.dob-toggle-label {
				font-size: 11px;
				font-weight: 700;
				letter-spacing: .6px;
				text-transform: uppercase;
				color: #7A8AA0;
			}

			.dob-filter-actions {
				display: flex;
				gap: 8px;
				align-items: flex-end;
				padding-bottom: 1px;
			}
			.dob-btn {
				height: 34px;
				padding: 0 18px;
				font-size: 13px;
				font-weight: 600;
				border-radius: 6px;
				border: none;
				cursor: pointer;
				white-space: nowrap;
				letter-spacing: .1px;
				transition: all .15s;
			}
			.dob-btn-primary {
				background: linear-gradient(135deg, #2A5FD8 0%, #3B6FE0 100%);
				color: #fff;
				box-shadow: 0 2px 8px rgba(42,95,216,.30);
			}
			.dob-btn-primary:hover {
				background: linear-gradient(135deg, #2050C0 0%, #2A5FD8 100%);
				box-shadow: 0 4px 14px rgba(42,95,216,.38);
				transform: translateY(-1px);
			}
			.dob-btn-primary:active { transform: translateY(0); }
			.dob-btn-default {
				background: #fff;
				color: #4A5568;
				border: 1.5px solid #DDE3EE;
			}
			.dob-btn-default:hover {
				background: #F4F7FB;
				border-color: #B0BECC;
			}

			.dob-section-title {
				font-size: 11.5px;
				font-weight: 700;
				letter-spacing: .8px;
				text-transform: uppercase;
				color: #8796A8;
				margin: 28px 0 14px;
				display: flex;
				align-items: center;
				gap: 10px;
			}
			.dob-section-title::after {
				content: '';
				flex: 1;
				height: 1.5px;
				background: linear-gradient(90deg, #DDE3EE 0%, transparent 100%);
				border-radius: 2px;
			}

			.dob-item-block {
				margin-bottom: 24px;
				border-radius: 12px;
				overflow: hidden;
				box-shadow: 0 2px 14px rgba(15,27,60,.08);
				border: 1px solid #DDE3EE;
			}

			.dob-item-heading {
				display: flex;
				align-items: center;
				gap: 10px;
				font-weight: 700;
				font-size: 15px;
				background: linear-gradient(135deg, #0F2750 0%, #1A3E72 100%);
				padding: 13px 18px;
				color: #EEF4FF;
				border-left: 5px solid #4A90E2;
			}
			.dob-badge {
				display: inline-block;
				background: rgba(255,255,255,.18);
				color: #C8DEFF;
				font-size: 11px;
				font-weight: 600;
				padding: 2px 10px;
				border-radius: 20px;
				border: 1px solid rgba(255,255,255,.22);
				letter-spacing: .3px;
			}

			.dob-card {
				overflow: hidden;
			}
			.dob-card .table { margin-bottom: 0; }

			.dob-table {
				width: 100%;
				border-collapse: collapse;
			}
			.dob-table th, .dob-table td {
				border: 1px solid #E4EAF2 !important;
				padding: 8px 13px !important;
				font-size: 14px;
				white-space: nowrap;
				vertical-align: middle !important;
			}
			.dob-table thead th {
				background: #EEF2FA !important;
				font-weight: 700;
				font-size: 11.5px;
				letter-spacing: .5px;
				text-transform: uppercase;
				color: #3A4A60;
				border-bottom: 2px solid #C8D4E4 !important;
				position: sticky;
				top: 0;
				z-index: 2;
			}
			.dob-table tbody tr:hover td {
				background: #F5F8FF !important;
			}
			.dob-total-row td {
				background: #EEF2FA !important;
				font-weight: 700;
				border-top: 2px solid #C8D4E4 !important;
				font-size: 14px;
			}

			.dob-qtr-head { background: #D0E4F8 !important; color: #154E8C !important; }
			.dob-qtr-cell { background: #EAF2FC; color: #1E5FA0; font-weight: 600; }

			.dob-mo-head  { background: #DBF0FF !important; color: #1A6EA8 !important; }
			.dob-mo-cell  { background: #F0F8FF; color: #3A7DC0; }

			.dob-supplied { background: #EBF3FF !important; color: #2055A0 !important; font-weight: 600; }

			.dob-pending-pos  {
				background: #FFF0F0 !important;
				color: #C0392B !important;
				font-weight: 700;
			}
			.dob-pending-zero { color: #27AE60 !important; font-weight: 600; }

			.dob-bal-neg  { background: #FFF0F0 !important; color: #C0392B !important; font-weight: 700; }
			.dob-bal-pos  { background: #EDFAF2 !important; color: #1E8449 !important; font-weight: 700; }
			.dob-bal-zero { color: #9AA3AF !important; }

			.dob-dash { color: #C8D0DA; font-size: 15px; }
			.dob-uom  { color: #6B7A8D; font-size: 12.5px; font-style: italic; }

			.dob-summary-wrap { max-width: 580px; }

			.dob-num { font-variant-numeric: tabular-nums; letter-spacing: .2px; }

			.dob-skeleton {
				background: linear-gradient(90deg,#EEF2FA 25%,#DDE6F2 50%,#EEF2FA 75%);
				background-size: 200% 100%;
				animation: dob-shimmer 1.3s infinite;
				height: 18px;
				border-radius: 6px;
				margin: 10px 0;
			}
			@keyframes dob-shimmer {
				0%  { background-position: 200% 0 }
				100%{ background-position: -200% 0 }
			}
			.dob-empty {
				text-align: center;
				padding: 48px 20px;
				color: #8796A8;
				font-size: 15px;
			}
			.dob-empty i { font-size: 32px; margin-bottom: 10px; display: block; opacity: .4; }
		</style>`).appendTo('head');
	}

	make_layout() {
		this.page.body.empty();
		this.$wrap = $(`<div class="dob-page-wrap"></div>`).appendTo(this.page.body);
		this.$filter_bar = $(`<div class="dob-filter-bar"></div>`).appendTo(this.$wrap);
		$(`<div class="dob-section-title">Item-wise Dispatch Balance</div>`).appendTo(this.$wrap);
		this.$item_wrap = $(`<div></div>`).appendTo(this.$wrap);
		this.$summary_title = $(`<div class="dob-section-title" style="margin-top:32px;"></div>`).appendTo(this.$wrap);
		this.$summary_wrap  = $(`<div class="dob-summary-wrap"></div>`).appendTo(this.$wrap);
	}

	make_filters() {
		const make_slot = (label, extra_class) => {
			const $item = $(`<div class="dob-filter-item${extra_class ? ' ' + extra_class : ''}"></div>`).appendTo(this.$filter_bar);
			$(`<label>${label}</label>`).appendTo($item);
			const $ctrl_wrap = $(`<div></div>`).appendTo($item);
			return $ctrl_wrap;
		};

		this.f_date = frappe.ui.form.make_control({
			parent: make_slot('As on Date')[0],
			df: {
				fieldname: 'dob_date',
				fieldtype: 'Date',
				onchange: () => this.schedule_refresh(),
			},
			render_input: true,
		});
		this.f_date.set_value(frappe.datetime.get_today());

		this.f_company = frappe.ui.form.make_control({
			parent: make_slot('Company')[0],
			df: {
				fieldname: 'dob_company',
				fieldtype: 'Link',
				options: 'Company',
				only_select: 1,

				onchange: () => {
					this.f_plant.set_value("");
					this.schedule_refresh();
				},
			},
			render_input: true,
		});

		this.f_plant = frappe.ui.form.make_control({
			parent: make_slot('Plant')[0],
			df: {
				fieldname: 'dob_plant',
				fieldtype: 'Link',
				options: 'Branch',
				only_select: 1,

				get_query: () => {
					const company = this.f_company.get_value();

					if (!company) return {};

					return {
						filters: {
							company: company
						}
					};
				},

				onchange: () => this.schedule_refresh(),
			},
			render_input: true,
		});

		this.f_customer = frappe.ui.form.make_control({
			parent: make_slot('Customer')[0],
			df: {
				fieldname: 'dob_customer',
				fieldtype: 'Link',
				options: 'Customer',
				onchange: () => this.schedule_refresh(),
			},
			render_input: true,
		});

		this.f_item = frappe.ui.form.make_control({
			parent: make_slot('Item')[0],
			df: {
				fieldname: 'dob_item',
				fieldtype: 'Link',
				options: 'Item',
				onchange: () => this.schedule_refresh(),
			},
			render_input: true,
		});

		this.f_po_no = frappe.ui.form.make_control({
			parent: make_slot('P.O. No')[0],
			df: {
				fieldname: 'dob_po_no',
				fieldtype: 'Data',
				onchange: () => this.schedule_refresh(),
			},
			render_input: true,
		});
		this.f_po_no.$input.on('input', () => this.schedule_refresh());

		// ── Show Zero Pending — plain native toggle, not a Frappe Check
		// control, so we fully control the markup/layout ourselves.
		const $check_item = $(`<div class="dob-filter-item dob-filter-check"></div>`).appendTo(this.$filter_bar);
		const $toggle = $(`
			<label class="dob-toggle">
				<input type="checkbox" />
				<span class="dob-toggle-track"><span class="dob-toggle-thumb"></span></span>
				<span class="dob-toggle-label">Show Zero Pending</span>
			</label>
		`).appendTo($check_item);
		this.f_show_zero_pending = $toggle.find('input[type=checkbox]');
		this.f_show_zero_pending.on('change', () => this.schedule_refresh());

		const $actions = $(`<div class="dob-filter-actions"></div>`).appendTo(this.$filter_bar);
		$(`<button class="dob-btn dob-btn-primary"><i class="fa fa-refresh"></i>&nbsp; Refresh</button>`)
			.appendTo($actions).on('click', () => this.refresh());
		$(`<button class="dob-btn dob-btn-default">Clear</button>`)
			.appendTo($actions).on('click', () => this.clear_filters());
	}

	schedule_refresh() {
		clearTimeout(this._refresh_timer);
		this._refresh_timer = setTimeout(() => this.refresh(), 400);
	}

	clear_filters() {
		this.f_date.set_value(frappe.datetime.get_today());
		this.f_company.set_value('');
		this.f_plant.set_value('');
		this.f_customer.set_value('');
		this.f_item.set_value('');
		this.f_po_no.set_value('');
		this.f_show_zero_pending.prop('checked', false);
		this.refresh();
	}

	make_menu() {
		this.page.add_menu_item('Export Excel', () => this.export_excel());
		this.page.add_menu_item('Export PDF', () => this.export_pdf());
	}

	get_filter_values() {
		return {
			date:      this.f_date.get_value()      || frappe.datetime.get_today(),
			company:   this.f_company.get_value()   || '',
			plant:     this.f_plant.get_value()     || '',
			customer:  this.f_customer.get_value()  || '',
			item_code: this.f_item.get_value()      || '',
			po_no:     this.f_po_no.get_value()     || '',
			show_zero_pending: this.f_show_zero_pending.is(':checked') ? 1 : 0,
		};
	}

	get_user_meta() {
		const full_name = (frappe.user && typeof frappe.user.full_name === 'function')
			? frappe.user.full_name()
			: (frappe.session.user_fullname || frappe.session.user);
		const timestamp = frappe.datetime.str_to_user(frappe.datetime.now_datetime());
		return { user: full_name || frappe.session.user || 'Unknown User', timestamp };
	}

	refresh() {
		this.show_skeleton();
		frappe.call({
			method: 'informatics_custom_apps.ripl_customized_apps.page.dispatch_order_balan.dispatch_order_balan.get_page_data',
			args:   { filters: this.get_filter_values() },
			callback: (r) => {
				this.last_data = r.message || {};
				this.render_item_tables(this.last_data.item_tables);
				this.render_summary(this.last_data.today_summary, this.last_data.as_on);
			},
			error: () => {
				this.$item_wrap.html(
					`<div class="dob-empty">
						<i class="fa fa-exclamation-triangle"></i>
						Failed to load data. Please try again.
					</div>`
				);
				this.$summary_wrap.empty();
			},
		});
	}

	show_skeleton() {
		const sk = () => `<div class="dob-skeleton" style="width:${60 + (Math.random()*35|0)}%;"></div>`;
		this.$item_wrap.html(`<div style="padding:10px 0">${sk()}${sk()}${sk()}${sk()}</div>`);
		this.$summary_wrap.empty();
		this.$summary_title.text('');
	}

	render_item_tables(item_data) {
		const items = (item_data && item_data.items)           || [];
		const qcols = (item_data && item_data.quarter_columns) || [];
		const mcols = (item_data && item_data.month_columns)   || [];

		if (!items.length) {
			this.$item_wrap.html(
				`<div class="dob-empty">
					<i class="fa fa-inbox"></i>
					No dispatch orders found for the selected filters.
				</div>`
			);
			return;
		}
		const html = items.map(item => this.render_item_block(item, qcols, mcols)).join('');
		this.$item_wrap.html(html);
	}

	render_item_block(item, qcols, mcols) {
		const q_heads = qcols.map(c =>
			`<th class="text-right dob-qtr-head">${esc(c.label)}</th>`).join('');
		const m_heads = mcols.map(c =>
			`<th class="text-right dob-mo-head">${esc(c.label)}</th>`).join('');

		const rows  = item.rows.map(r => this.render_row(r, qcols, mcols, false)).join('');
		const total = this.render_row(item.total, qcols, mcols, true);

		return `
		<div class="dob-item-block">
			<div class="dob-item-heading">
				${esc(item.item_name || item.item_code)}
				<span class="dob-badge">${esc(item.item_code)}</span>
			</div>
			<div class="dob-card">
				<div style="overflow-x:auto;">
					<table class="table dob-table" style="min-width:740px;">
						<thead>
							<tr>
								<th>OMC / Customer</th>
								${q_heads}
								${m_heads}
								<th class="text-right">Order Qty</th>
								<th class="text-right">Supplied Qty</th>
								<th class="text-center">UOM</th>
								<th class="text-right">Pending Qty</th>
								<th>P.O. No</th>
								<th>P.O. Date</th>
							</tr>
						</thead>
						<tbody>${rows}${total}</tbody>
					</table>
				</div>
			</div>
		</div>`;
	}

	render_row(row, qcols, mcols, is_total) {
		const label_html = is_total ? '<strong>Total</strong>' : esc(row.customer_name || '');
		const q_cells    = qcols.map(c => this.val_cell(row[c.fieldname], 'q')).join('');
		const m_cells    = mcols.map(c => this.val_cell(row[c.fieldname], 'm')).join('');
		const pending    = parseFloat(row.pending_qty) || 0;
		const pend_cls   = pending > 0 ? 'dob-pending-pos' : 'dob-pending-zero';
		const uom        = is_total ? '' : esc(row.uom || '');

		return `
		<tr${is_total ? ' class="dob-total-row"' : ''}>
			<td>${label_html}</td>
			${q_cells}
			${m_cells}
			<td class="text-right dob-num">${raw_num(row.order_qty)}</td>
			<td class="text-right dob-supplied dob-num">${raw_num(row.supplied_qty)}</td>
			<td class="text-center dob-uom">${uom}</td>
			<td class="text-right dob-num ${pend_cls}">${raw_num(pending)}</td>
			<td>${is_total ? '' : esc(row.po_no || '')}</td>
			<td>${is_total ? '' : (row.po_date ? frappe.datetime.str_to_user(row.po_date) : '')}</td>
		</tr>`;
	}

	val_cell(value, type) {
		if (value === '' || value === null || value === undefined)
			return `<td class="text-right dob-dash">—</td>`;
		const num = parseFloat(value) || 0;
		if (num === 0)
			return `<td class="text-right dob-num" style="color:#9AA3AF;">0.000</td>`;
		const cls = type === 'q' ? 'dob-qtr-cell' : 'dob-mo-cell';
		return `<td class="text-right dob-num ${cls}">${raw_num(value)}</td>`;
	}

	render_summary(data, as_on) {
		if (!data || !data.length) {
			this.$summary_title.text("Today's Stock & Dispatch");
			this.$summary_wrap.html(`<div class="dob-empty" style="padding:20px;">No stock/dispatch data found.</div>`);
			return;
		}
		const date_lbl = (data[0] && data[0].as_on) || as_on || frappe.datetime.get_today();
		this.$summary_title.html(
			`Today&#39;s Stock &amp; Dispatch
			<span style="font-weight:500;font-size:12px;color:#8796A8;text-transform:none;letter-spacing:0;">
				&nbsp;as on ${frappe.datetime.str_to_user(date_lbl)}
			</span>`
		);

		const rows = data.map(d => {
			const is_t    = d.item_code === 'TOTAL';
			const lbl     = is_t ? '<strong>Total</strong>' : esc(d.item_name || d.item_code);
			const b       = parseFloat(d.balance_qty) || 0;
			const bal_cls = b < 0 ? 'dob-bal-neg' : b > 0 ? 'dob-bal-pos' : 'dob-bal-zero';
			return `
			<tr${is_t ? ' class="dob-total-row"' : ''}>
				<td>${lbl}</td>
				<td class="text-right dob-num">${raw_num(d.stock_qty)}</td>
				<td class="text-right dob-num">${raw_num(d.dispatch_qty)}</td>
				<td class="text-right dob-num ${bal_cls}">${raw_num(b)}</td>
			</tr>`;
		}).join('');

		this.$summary_wrap.html(`
			<div class="dob-item-block" style="max-width:2020px;">
				<table class="table dob-table">
					<thead>
						<tr>
							<th>Feed Stock</th>
							<th class="text-right">Stock</th>
							<th class="text-right">Dispatch</th>
							<th class="text-right">Balance</th>
						</tr>
					</thead>
					<tbody>${rows}</tbody>
				</table>
			</div>`);
	}

	async export_excel() {
		if (!this.last_data) { frappe.msgprint('Load data first.'); return; }
		frappe.show_alert({ message:'Preparing Excel…', indicator:'blue' });
		try { await this.load_excel_libs(); }
		catch(e) { frappe.msgprint('Could not load Excel libraries. Check internet connection.'); return; }

		const ExcelJS = window.ExcelJS;
		const wb = new ExcelJS.Workbook();
		wb.creator = 'Dispatch Order Balance';
		wb.created = new Date();

		const { user, timestamp } = this.get_user_meta();
		const { item_tables: it={}, today_summary: ts=[], as_on } = this.last_data;
		const qcols = it.quarter_columns || [];
		const mcols = it.month_columns   || [];
		const items = it.items           || [];

		const ws = wb.addWorksheet('Dispatch Balance');

		const FIXED_AFTER  = ['Order Qty','Supplied Qty','UOM','Pending Qty','P.O. No','P.O. Date'];
		const ncols        = Math.max(1 + qcols.length + mcols.length + FIXED_AFTER.length, 4);

		const HEADER_FILL   = { type:'pattern', pattern:'solid', fgColor:{ argb:'FFEEF2FA' } };
		const Q_FILL        = { type:'pattern', pattern:'solid', fgColor:{ argb:'FFD0E4F8' } };
		const M_FILL        = { type:'pattern', pattern:'solid', fgColor:{ argb:'FFDBF0FF' } };
		const TOTAL_FILL    = { type:'pattern', pattern:'solid', fgColor:{ argb:'FFEEF2FA' } };
		const ITEM_BAR_FILL = { type:'pattern', pattern:'solid', fgColor:{ argb:'FF0F2750' } };
		const PEND_FILL     = { type:'pattern', pattern:'solid', fgColor:{ argb:'FFFFF0F0' } };
		const THIN   = { style:'thin', color:{ argb:'FFC8D4E4' } };
		const BORDER = { top:THIN, left:THIN, bottom:THIN, right:THIN };
		const set_borders = (row, count) => { for (let c=1; c<=count; c++) row.getCell(c).border = BORDER; };

		let r = 1;
		const title_row = ws.getRow(r);
		title_row.getCell(1).value = `Dispatch Order Balance — As on: ${as_on || ''}`;
		title_row.getCell(1).font  = { bold:true, size:13, color:{ argb:'FF0F1B3C' } };
		title_row.getCell(1).note  = `Generated by: ${user}\n${timestamp}`;
		ws.mergeCells(r, 1, r, ncols);
		r += 2;

		items.forEach(item => {
			const head_bar = ws.getRow(r);
			head_bar.getCell(1).value = `${item.item_name || item.item_code}  (${item.item_code})`;
			ws.mergeCells(r, 1, r, ncols);
			for (let c = 1; c <= ncols; c++) {
				const cell = head_bar.getCell(c);
				cell.fill = ITEM_BAR_FILL;
				cell.font = { bold:true, size:11, color:{ argb:'FFEEF4FF' } };
			}
			head_bar.height = 20;
			r += 1;

			const col_labels = ['OMC / Customer', ...qcols.map(c=>c.label), ...mcols.map(c=>c.label), ...FIXED_AFTER];
			const col_head = ws.getRow(r);
			col_labels.forEach((label, i) => {
				const cell = col_head.getCell(i + 1);
				cell.value = label;
				cell.font  = { bold:true, color:{ argb:'FF3A4A60' } };
				cell.alignment = { horizontal: i === 0 ? 'left' : 'center', vertical:'middle' };
				const is_q = i >= 1 && i <= qcols.length;
				const is_m = i > qcols.length && i <= qcols.length + mcols.length;
				cell.fill = is_q ? Q_FILL : is_m ? M_FILL : HEADER_FILL;
			});
			set_borders(col_head, ncols);
			r += 1;

			[...item.rows, item.total].forEach(rd => {
				const is_t = rd.customer_name === 'TOTAL';
				const xrow = ws.getRow(r);
				let c = 1;
				xrow.getCell(c++).value = is_t ? 'Total' : (rd.customer_name || '');
				qcols.forEach(qc => xrow.getCell(c++).value = num_or_blank(rd[qc.fieldname]));
				mcols.forEach(mc => xrow.getCell(c++).value = num_or_blank(rd[mc.fieldname]));
				xrow.getCell(c++).value = num_or_blank(rd.order_qty);
				xrow.getCell(c++).value = num_or_blank(rd.supplied_qty);
				xrow.getCell(c++).value = is_t ? '' : (rd.uom || '');
				const pend_cell = xrow.getCell(c++);
				pend_cell.value = num_or_blank(rd.pending_qty);
				xrow.getCell(c++).value = is_t ? '' : (rd.po_no || '');
				xrow.getCell(c++).value = is_t ? '' : (rd.po_date ? frappe.datetime.str_to_user(rd.po_date) : '');

				for (let cc = 1; cc <= ncols; cc++) {
					const cell = xrow.getCell(cc);
					if (typeof cell.value === 'number') cell.numFmt = '0.000';
					if (is_t) { cell.font = { bold:true }; cell.fill = TOTAL_FILL; }
				}
				if ((parseFloat(rd.pending_qty) || 0) > 0) {
					pend_cell.font = { bold:true, color:{ argb:'FFC0392B' } };
					pend_cell.fill = PEND_FILL;
				}
				set_borders(xrow, ncols);
				r += 1;
			});
			r += 1;
		});

		if (ts.length) {
			const sum_head = ws.getRow(r);
			sum_head.getCell(1).value = `TODAY'S STOCK & DISPATCH — ${ts[0].as_on || as_on || ''}`;
			sum_head.getCell(1).font  = { bold:true, size:11, color:{ argb:'FF0F1B3C' } };
			ws.mergeCells(r, 1, r, 4);
			r += 1;

			const sum_col_head = ws.getRow(r);
			['Feed Stock','Stock','Dispatch','Balance'].forEach((label, i) => {
				const cell = sum_col_head.getCell(i + 1);
				cell.value = label;
				cell.font  = { bold:true, color:{ argb:'FF3A4A60' } };
				cell.fill  = HEADER_FILL;
				cell.alignment = { horizontal: i === 0 ? 'left' : 'center' };
			});
			set_borders(sum_col_head, 4);
			r += 1;

			ts.forEach(d => {
				const is_t = d.item_code === 'TOTAL';
				const xrow = ws.getRow(r);
				xrow.getCell(1).value = is_t ? 'Total' : (d.item_name || d.item_code);
				xrow.getCell(2).value = num_or_blank(d.stock_qty);
				xrow.getCell(3).value = num_or_blank(d.dispatch_qty);
				const bal_cell = xrow.getCell(4);
				bal_cell.value = num_or_blank(d.balance_qty);
				for (let cc = 1; cc <= 4; cc++) {
					const cell = xrow.getCell(cc);
					if (typeof cell.value === 'number') cell.numFmt = '0.000';
					if (is_t) { cell.font = { bold:true }; cell.fill = TOTAL_FILL; }
				}
				const bal = parseFloat(d.balance_qty) || 0;
				if (bal !== 0 && !is_t) {
					bal_cell.font = { bold:true, color:{ argb: bal < 0 ? 'FFC0392B' : 'FF1E8449' } };
				}
				set_borders(xrow, 4);
				r += 1;
			});
		}

		ws.getColumn(1).width = 26;
		for (let c = 2; c <= ncols; c++) ws.getColumn(c).width = 13;

		const buffer = await wb.xlsx.writeBuffer();
		this.download_blob(buffer,
			'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
			`dispatch-order-balance-${as_on}.xlsx`);
		frappe.show_alert({ message:'Excel downloaded!', indicator:'green' });
	}

	async export_pdf() {
		if (!this.last_data) { frappe.msgprint('Load data first.'); return; }
		frappe.show_alert({ message:'Preparing PDF…', indicator:'blue' });
		try { await this.load_pdf_libs(); }
		catch(e) { frappe.msgprint('Could not load PDF libraries. Check internet connection.'); return; }

		const { jsPDF }  = window.jspdf;
		const doc        = new jsPDF({ orientation:'landscape', unit:'pt', format:'a4' });
		const { item_tables:it={}, today_summary:ts=[], as_on } = this.last_data;
		const qcols = it.quarter_columns || [];
		const mcols = it.month_columns   || [];
		const items = it.items           || [];
		const { user, timestamp } = this.get_user_meta();

		const PAGE_W = doc.internal.pageSize.getWidth();
		const PAGE_H = doc.internal.pageSize.getHeight();
		const MARGIN = 28;
		const ITEM_BAR_H = 17;
		const FOOTER_H   = 26;
		let curY = MARGIN;

		const fv = this.get_filter_values();
		const fp = [];
		if (fv.company)   fp.push(`Company: ${fv.company}`);
		if (fv.plant)     fp.push(`Plant: ${fv.plant}`);
		if (fv.customer)  fp.push(`Customer: ${fv.customer}`);
		if (fv.po_no)     fp.push(`P.O. No: ${fv.po_no}`);
		if (fv.item_code) fp.push(`Item: ${fv.item_code}`);
		if (fv.show_zero_pending) fp.push(`Show Zero Pending: Yes`);

		doc.setFont('helvetica','bold'); doc.setFontSize(14); doc.setTextColor(15,27,60);
		doc.text(`Dispatch Order Balance  —  As on: ${as_on||''}`, MARGIN, curY);
		curY += 16;
		if (fp.length) {
			doc.setFont('helvetica','normal'); doc.setFontSize(9); doc.setTextColor(100,110,120);
			doc.text(`Filters: ${fp.join('   |   ')}`, MARGIN, curY);
			curY += 12;
		}
		curY += 8;

		const draw_item_bar = (y, item) => {
			doc.setFont('helvetica','bold'); doc.setFontSize(10);
			doc.setFillColor(15, 39, 80);
			doc.rect(MARGIN, y, PAGE_W - MARGIN*2, ITEM_BAR_H, 'F');
			doc.setTextColor(220,235,255);
			doc.text(`${item.item_name||item.item_code}  (${item.item_code})`, MARGIN+7, y+11.5);
			doc.setTextColor(0,0,0);
		};

		const COL_OMC      = 0;
		const COL_Q_START  = 1;
		const COL_Q_END    = COL_Q_START + qcols.length - 1;
		const COL_M_START  = COL_Q_START + qcols.length;
		const COL_M_END    = COL_M_START + mcols.length - 1;
		const COL_ORDER    = COL_M_START + mcols.length;
		const COL_SUPPLIED = COL_ORDER + 1;
		const COL_UOM      = COL_SUPPLIED + 1;
		const COL_PENDING  = COL_UOM + 1;
		const COL_PO_NO    = COL_PENDING + 1;
		const COL_PO_DATE  = COL_PO_NO + 1;

		const head_cols = [
			'OMC / Customer',
			...qcols.map(c=>c.label),
			...mcols.map(c=>c.label),
			'Order Qty','Supplied Qty','UOM','Pending Qty','P.O. No','P.O. Date',
		];

		for (const item of items) {
			if (curY + 40 > PAGE_H) { doc.addPage(); curY = MARGIN; }

			const table_start_page = doc.internal.getNumberOfPages();

			draw_item_bar(curY, item);
			curY += 19;

			const body = [...item.rows, item.total].map(r => {
				const is_t = r.customer_name === 'TOTAL';
				return [
					is_t ? 'Total' : (r.customer_name||''),
					...qcols.map(c => raw_num(r[c.fieldname])),
					...mcols.map(c => raw_num(r[c.fieldname])),
					raw_num(r.order_qty),
					raw_num(r.supplied_qty),
					is_t ? '' : (r.uom||''),
					raw_num(r.pending_qty),
					is_t ? '' : (r.po_no||''),
					is_t ? '' : (r.po_date ? frappe.datetime.str_to_user(r.po_date) : ''),
				];
			});

			doc.autoTable({
				head:  [head_cols],
				body,
				startY: curY,
				margin: { left:MARGIN, right:MARGIN, top: MARGIN + 19 + 8, bottom: MARGIN + FOOTER_H },
				styles: { fontSize:8, cellPadding:3.5, lineColor:[200,210,225], lineWidth:0.3,
					textColor:[30,40,55], font:'helvetica' },
				headStyles: { fillColor:[238,242,250], textColor:[35,55,90],
					fontStyle:'bold', fontSize:7.5, halign:'center' },
				columnStyles: {
					[COL_OMC]:      { cellWidth:82, halign:'left' },
					[COL_ORDER]:    { halign:'right' },
					[COL_SUPPLIED]: { halign:'right' },
					[COL_UOM]:      { halign:'center', cellWidth:26 },
					[COL_PENDING]:  { halign:'right' },
					[COL_PO_NO]:    { halign:'left'  },
					[COL_PO_DATE]:  { halign:'left', cellWidth:46 },
				},
				didParseCell: (data) => {
					const ci = data.column.index;
					const ri = data.row.index;
					if (data.section === 'head') {
						if (qcols.length && ci>=COL_Q_START && ci<=COL_Q_END)
							{ data.cell.styles.fillColor=[195,224,250]; data.cell.styles.textColor=[15,60,130]; }
						if (mcols.length && ci>=COL_M_START && ci<=COL_M_END)
							{ data.cell.styles.fillColor=[215,238,255]; data.cell.styles.textColor=[20,90,155]; }
						if (ci>=COL_Q_START && ci<=COL_PENDING)
							data.cell.styles.halign='right';
					}
					if (data.section === 'body') {
						const is_t = ri === body.length - 1;
						if (is_t) { data.cell.styles.fontStyle='bold'; data.cell.styles.fillColor=[238,242,250]; }
						if (qcols.length && ci>=COL_Q_START && ci<=COL_Q_END)
							{ data.cell.styles.halign='right'; data.cell.styles.fillColor=is_t?[228,241,255]:[234,242,252];
							  data.cell.styles.textColor=[20,80,160]; data.cell.styles.fontStyle='bold'; }
						if (mcols.length && ci>=COL_M_START && ci<=COL_M_END)
							{ data.cell.styles.halign='right'; data.cell.styles.fillColor=is_t?[228,241,255]:[240,248,255];
							  data.cell.styles.textColor=[30,100,185]; }
						if (ci===COL_SUPPLIED)
							{ data.cell.styles.fillColor=[235,245,255]; data.cell.styles.textColor=[25,80,165]; data.cell.styles.halign='right'; }
						if (ci===COL_PENDING) {
							const v = parseFloat(data.cell.raw)||0;
							data.cell.styles.halign='right';
							data.cell.styles.textColor = v>0 ? [192,57,43] : [30,132,73];
							if (v>0) data.cell.styles.fillColor=[255,240,240];
							data.cell.styles.fontStyle = v>0 ? 'bold' : 'normal';
						}
						if (ci===COL_UOM)
							{ data.cell.styles.halign='center'; data.cell.styles.textColor=[107,122,141]; data.cell.styles.fontSize=7.5; }
					}
				},
				didDrawPage: (data) => {
					if (data.pageNumber > table_start_page) draw_item_bar(MARGIN, item);
				},
				theme: 'grid',
			});
			curY = doc.lastAutoTable.finalY + 16;
		}

		if (ts.length) {
			if (curY + 80 > PAGE_H) { doc.addPage(); curY = MARGIN; }
			doc.setFont('helvetica','bold'); doc.setFontSize(11); doc.setTextColor(15,27,60);
			doc.text(`Today's Stock & Dispatch  —  ${as_on||''}`, MARGIN, curY+11);
			curY += 20;

			const sum_body = ts.map(d => {
				const is_t = d.item_code==='TOTAL';
				return [is_t?'Total':(d.item_name||d.item_code),
					raw_num(d.stock_qty), raw_num(d.dispatch_qty), raw_num(d.balance_qty)];
			});
			doc.autoTable({
				head: [['Feed Stock','Stock','Dispatch','Balance']],
				body: sum_body,
				startY: curY,
				margin: { left:MARGIN, right:MARGIN, bottom: MARGIN + FOOTER_H },
				tableWidth: 320,
				styles: { fontSize:8.5, cellPadding:4, lineColor:[200,210,225], lineWidth:0.3, font:'helvetica' },
				headStyles: { fillColor:[238,242,250], textColor:[35,55,90], fontStyle:'bold' },
				columnStyles: { 0:{halign:'left'}, 1:{halign:'right'}, 2:{halign:'right'}, 3:{halign:'right'} },
				didParseCell: (data) => {
					const ri = data.row.index;
					if (data.section==='body') {
						const is_t = ri===sum_body.length-1;
						if (is_t) { data.cell.styles.fontStyle='bold'; data.cell.styles.fillColor=[238,242,250]; }
						if (data.column.index===3) {
							const v = parseFloat(data.cell.raw)||0;
							data.cell.styles.textColor = v<0?[192,57,43]:v>0?[30,132,73]:[154,163,175];
							if (v<0) data.cell.styles.fillColor=[255,240,240];
							if (v>0) data.cell.styles.fillColor=[237,250,240];
						}
					}
				},
				theme: 'grid',
			});
		}

		const total_pages = doc.internal.getNumberOfPages();
		for (let p = 1; p <= total_pages; p++) {
			doc.setPage(p);
			doc.setDrawColor(225,230,238);
			doc.setLineWidth(0.5);
			doc.line(MARGIN, PAGE_H - FOOTER_H + 4, PAGE_W - MARGIN, PAGE_H - FOOTER_H + 4);
			doc.setFont('helvetica','normal'); doc.setFontSize(7.5); doc.setTextColor(120,130,145);
			doc.text(`Generated by: ${user}   |   ${timestamp}`, MARGIN, PAGE_H - FOOTER_H + 16);
			doc.text(`Page ${p} of ${total_pages}`, PAGE_W - MARGIN, PAGE_H - FOOTER_H + 16, { align:'right' });
		}

		doc.save(`dispatch-order-balance-${as_on}.pdf`);
		frappe.show_alert({ message:'PDF downloaded!', indicator:'green' });
	}

	load_pdf_libs() {
		const load = (src) => new Promise((resolve, reject) => {
			if (document.querySelector(`script[src="${src}"]`)) return resolve();
			const s = document.createElement('script');
			s.src=src; s.onload=resolve;
			s.onerror=()=>reject(new Error(`Failed: ${src}`));
			document.head.appendChild(s);
		});
		return load('https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js')
			.then(()=>load('https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.8.2/jspdf.plugin.autotable.min.js'));
	}

	load_excel_libs() {
		const load = (src) => new Promise((resolve, reject) => {
			if (document.querySelector(`script[src="${src}"]`)) return resolve();
			const s = document.createElement('script');
			s.src=src; s.onload=resolve;
			s.onerror=()=>reject(new Error(`Failed: ${src}`));
			document.head.appendChild(s);
		});
		return load('https://cdnjs.cloudflare.com/ajax/libs/exceljs/4.4.0/exceljs.min.js');
	}

	download_blob(content, mime, filename) {
		const blob = new Blob([content],{type:mime});
		const url  = URL.createObjectURL(blob);
		const a    = document.createElement('a');
		a.href=url; a.download=filename;
		document.body.appendChild(a); a.click(); document.body.removeChild(a);
		setTimeout(()=>URL.revokeObjectURL(url), 1000);
	}
}

function raw_num(val) {
	const n = parseFloat(val);
	if (isNaN(n)) return '';
	return n === 0 ? '0.000' : n.toFixed(3);
}
function num_or_blank(val) {
	if (val === '' || val === null || val === undefined) return null;
	const n = parseFloat(val);
	return isNaN(n) ? null : n;
}
function esc(v) {
	return frappe.utils.escape_html(String(v==null?'':v));
}