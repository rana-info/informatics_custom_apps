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
		this.page       = page;
		this.data       = null;
		this._timer     = null;
		this.view_mode  = 'quarter';
		this.show_zero  = true;
		this.active_key = null;
		this.selected_quarter = null;
		this.expanded_quarters = new Set(); // NEW: tracks which quarter blocks are expanded

		this._inject_styles();
		this._build_layout();
		this._build_filters();
		this._build_menu();
		this.refresh();
	}

	_inject_styles() {
		if ($('#dob3-style').length) return;
		$(`<style id="dob3-style">
		.dob3-wrap * { font-family: 'Inter', system-ui, sans-serif; box-sizing: border-box; }
		.dob3-wrap { padding: 16px 20px 60px; background: #F2F5FA; min-height: 100vh; }

		.dob3-fb {
			background: #fff; border: 1px solid #DDE3EE; border-radius: 10px;
			padding: 14px 18px; margin-bottom: 18px;
			display: flex; flex-wrap: wrap; align-items: flex-end; gap: 10px 14px;
			box-shadow: 0 1px 6px rgba(15,27,60,.05);
		}
		.dob3-fi { display: flex; flex-direction: column; min-width: 130px; max-width: 185px; flex: 1 1 130px; }
		.dob3-fi > label {
			font-size: 10px; font-weight: 700; letter-spacing: .7px;
			text-transform: uppercase; color: #8796A8; margin-bottom: 4px; display: block;
		}
		.dob3-fi .form-control, .dob3-fi .input-with-feedback {
			height: 32px !important; font-size: 13px !important; padding: 3px 9px !important;
			border-radius: 6px !important; border: 1.5px solid #DDE3EE !important; background: #F8FAFD !important;
		}
		.dob3-fi .form-control:focus, .dob3-fi .input-with-feedback:focus {
			border-color: #3B6FE0 !important; box-shadow: 0 0 0 3px rgba(59,111,224,.1) !important;
			background: #fff !important; outline: none !important;
		}
		.dob3-fi .link-btn { display: none !important; }

		.dob3-mode { display: inline-flex; border: 1.5px solid #DDE3EE; border-radius: 7px; overflow: hidden; }
		.dob3-mode button {
			height: 32px; padding: 0 13px; font-size: 12px; font-weight: 600;
			border: none; cursor: pointer; background: #F8FAFD; color: #6B7A8D; white-space: nowrap;
		}
		.dob3-mode button + button { border-left: 1.5px solid #DDE3EE; }
		.dob3-mode button.dob3-active { background: #3B6FE0; color: #fff; }

		.dob3-qpills { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
		.dob3-qpill {
			height: 28px; padding: 0 12px; border-radius: 20px; border: 1.5px solid #C8D4E4;
			background: #F0F4FA; color: #4A6080; font-size: 11.5px; font-weight: 600;
			cursor: pointer; transition: all .12s; white-space: nowrap;
		}
		.dob3-qpill:hover { border-color: #7AAAE0; background: #E6EEFA; color: #2050A0; }
		.dob3-qpill.dob3-active { background: #1B3D6E; border-color: #1B3D6E; color: #C8DEFF; }
		.dob3-qpill-all { background: #3B6FE0; border-color: #3B6FE0; color: #fff; }
		.dob3-qpill-all:hover { background: #2A5FD8; }

		.dob3-toggle { display: inline-flex; align-items: center; gap: 8px; cursor: pointer; user-select: none; }
		.dob3-toggle input { position: absolute; opacity: 0; width: 0; height: 0; }
		.dob3-track {
			position: relative; width: 32px; height: 18px; background: #DDE3EE;
			border-radius: 18px; flex-shrink: 0; transition: background .13s;
		}
		.dob3-thumb {
			position: absolute; top: 2px; left: 2px; width: 14px; height: 14px;
			background: #fff; border-radius: 50%; box-shadow: 0 1px 3px rgba(0,0,0,.2); transition: transform .13s;
		}
		.dob3-toggle input:checked + .dob3-track { background: #3B6FE0; }
		.dob3-toggle input:checked + .dob3-track .dob3-thumb { transform: translateX(14px); }
		.dob3-toggle-lbl { font-size: 10px; font-weight: 700; letter-spacing: .7px; text-transform: uppercase; color: #8796A8; }

		.dob3-btn { height: 32px; padding: 0 16px; font-size: 12.5px; font-weight: 600; border-radius: 6px; border: none; cursor: pointer; transition: all .12s; }
		.dob3-btn-primary { background: #3B6FE0; color: #fff; box-shadow: 0 1px 6px rgba(59,111,224,.3); }
		.dob3-btn-primary:hover { background: #2A5FD8; transform: translateY(-1px); }
		.dob3-btn-default { background: #fff; color: #4A5568; border: 1.5px solid #DDE3EE; }
		.dob3-btn-default:hover { background: #F4F7FB; }

		.dob3-sec {
			font-size: 10.5px; font-weight: 700; letter-spacing: .8px; text-transform: uppercase;
			color: #8796A8; display: flex; align-items: center; gap: 10px; margin: 20px 0 10px;
		}
		.dob3-sec::after { content: ''; flex: 1; height: 1px; background: linear-gradient(90deg, #DDE3EE 0%, transparent 100%); }

		.dob3-card {
			background: #fff; border: 2px solid #d5dde5; border-radius: 14px; padding: 18px;
			box-shadow: 0 3px 10px rgba(31,39,46,.06); margin-bottom: 18px; overflow-x: auto;
		}
		.dob3-card-title {
			font-size: 15px; font-weight: 700; margin-bottom: 12px; color: #24313b;
			display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
		}
		.dob3-badge { font-size: 11px; padding: 3px 10px; border-radius: 30px; font-weight: 600; white-space: nowrap; }
		.dob3-badge-hint { background:#e6f0ff; color:#1d4f9e; border:1px solid #b9d2f5; }
		.dob3-badge-sort { background:#fdf5dc; color:#75621a; border:1px solid #eadfa6; margin-left:auto; }

		.dob3-table-wrap { overflow-x: auto; border-radius: 10px; border: 2px solid #aab8c3; }
		.dob3-sumtbl { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 13.5px; min-width: 460px; }
		.dob3-sumtbl th, .dob3-sumtbl td {
			padding: 9px 14px; border-right: 1px solid #d0dbe4; border-bottom: 1px solid #dde5ec;
			text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums;
		}
		.dob3-sumtbl th:last-child, .dob3-sumtbl td:last-child { border-right: none; }
		.dob3-sumtbl th {
			background: #e8eef4; color: #36474f; font-weight: 700; border-bottom: 2px solid #aab8c3;
			font-size: 10.5px; letter-spacing: .3px; text-transform: uppercase;
		}
		.dob3-rowlabel {
			text-align: left !important; min-width: 220px; font-weight: 700; color: #1f2b34;
			background: #f5f7fa !important; border-right: 3px solid #8fa8bb !important;
			position: sticky; left: 0; z-index: 2;
		}
		.dob3-rowlabel .dob3-sub { font-size: 11px; font-weight: 500; color: #697884; margin-top: 2px; white-space: normal; }
		.dob3-col-ord  { background-color:#f0f7ff; border-left:3px solid #b3d4f0 !important; }
		.dob3-col-supt { background-color:#f0fff5; border-left:3px solid #9ed8b8 !important; }
		.dob3-col-pend { background-color:#fff8f0; border-left:3px solid #e8bb95 !important; }
		th.dob3-col-ord  { background-color:#ddeeff !important; border-left:3px solid #6aace8 !important; }
		th.dob3-col-supt { background-color:#d8f5e4 !important; border-left:3px solid #5dc483 !important; }
		th.dob3-col-pend { background-color:#ffebd9 !important; border-left:3px solid #e09055 !important; }
		.dob3-val-pend-pos  { color:#C0392B; font-weight:700; }
		.dob3-val-pend-neg  { color:#D35400; font-weight:700; }
		.dob3-val-pend-zero { color:#27AE60; }

		.dob3-sumrow { cursor: pointer; transition: background .15s; }
		.dob3-sumrow:hover td:not(.dob3-rowlabel) { filter: brightness(0.96); }
		.dob3-sumrow:hover td.dob3-rowlabel { background: #eef2f6 !important; }
		.dob3-sumrow-active td { border-top: 2px solid #2b7ad4 !important; border-bottom: 2px solid #2b7ad4 !important; }
		.dob3-sumrow-active td.dob3-rowlabel { color:#2367b1; background:#eaf2fc !important; }
		.dob3-chev { float:right; color:#93a4b0; font-weight:800; margin-left:8px; transition: transform .18s; }
		.dob3-sumrow-active .dob3-chev { transform: rotate(90deg); color:#2367b1; }
		.dob3-totalrow td { background: #d8e5ef !important; font-weight: 800 !important; border-top: 3px solid #7a9bb5 !important; }
		.dob3-totalrow td.dob3-rowlabel { background:#cddce8 !important; }

		.dob3-panel { border-left: 6px solid #3B6FE0; }
		.dob3-subrow { cursor: pointer; }
		.dob3-subrow:hover td:not(.dob3-rowlabel) { background-color: rgba(43,122,212,.08) !important; filter:none; }
		.dob3-subrow:hover td.dob3-rowlabel { background-color:#e3edf9 !important; }

		/* Quarter-mode 3-level layout */
		.dob3-qblock {
			background: #fff; border: 2px solid #d5dde5; border-radius: 12px;
			box-shadow: 0 3px 10px rgba(31,39,46,.06); margin-bottom: 18px; overflow: hidden;
		}
		.dob3-qhdr {
			display: flex; align-items: center; gap: 10px;
			background: #1B3D6E; color: #C8DEFF;
			padding: 11px 18px; font-size: 13px; font-weight: 700;
			cursor: pointer; user-select: none;
		}
		.dob3-qhdr:hover { background: #234b85; }
		.dob3-qhdr .dob3-qchev {
			display: inline-block; font-size: 14px; font-weight: 800;
			transition: transform .15s; color:#C8DEFF; flex-shrink:0;
		}
		.dob3-qhdr.dob3-qhdr-open .dob3-qchev { transform: rotate(90deg); }
		.dob3-qhdr .dob3-qhdr-right { margin-left: auto; display:flex; gap:6px; align-items:center; }
		.dob3-qhdr .dob3-badge { font-size:10.5px; }
		.dob3-itemrow { cursor: pointer; transition: background .12s; }
		.dob3-itemrow:hover td:not(.dob3-rowlabel) { filter: brightness(0.95); }
		.dob3-itemrow:hover td.dob3-rowlabel { background:#eef5f0 !important; }
		.dob3-itemrow-active td { border-top: 2px solid #27AE60 !important; border-bottom: 2px solid #27AE60 !important; }
		.dob3-itemrow-active td.dob3-rowlabel { color:#1a7a48; background:#eafaf2 !important; }
		.dob3-custpanel { border-left: 5px solid #27AE60; background:#f8fdf9; }
		.dob3-custpanel .dob3-sumtbl { font-size:13px; }
		.dob3-custrow { cursor: pointer; }
		.dob3-custrow:hover td:not(.dob3-rowlabel) { background-color:rgba(39,174,96,.1) !important; filter:none; }
		.dob3-custrow:hover td.dob3-rowlabel { background-color:#ddf5e8 !important; }
		.dob3-custpanel .dob3-rowlabel { background:#f0faf4 !important; }

		.dob3-tbl { width: 100%; border-collapse: collapse; font-size: 12.5px; min-width: 600px; }
		.dob3-tbl th {
			background: #EEF2FA; color: #3A4A60; font-weight: 700; font-size: 10px;
			letter-spacing: .4px; text-transform: uppercase; padding: 7px 10px;
			border: 1px solid #E0E7F0; text-align: right; white-space: nowrap;
		}
		.dob3-tbl th:first-child, .dob3-tbl th.tl { text-align: left; }
		.dob3-tbl td { padding: 7px 10px; border: 1px solid #EBF0F8; font-variant-numeric: tabular-nums; text-align: right; white-space: nowrap; vertical-align: middle; }
		.dob3-tbl td.tl { text-align: left; }
		.dob3-tbl tr:hover td { background: #F2F6FF; }
		.dob3-tbl tr.dob3-total td { background: #EEF2FA; font-weight: 700; border-top: 2px solid #C8D4E4; }
		.cv-pend-pos  { color: #C0392B; font-weight: 700; background: #FFF0F0; }
		.cv-pend-neg  { color: #D35400; font-weight: 700; background: #FFF6EE; }
		.cv-pend-zero { color: #27AE60; }
		.cv-sup       { color: #2055A0; background: #EBF3FF; }
		.cv-uom       { color: #8796A8; font-style: italic; text-align: center !important; }

		.dob3-item-dialog .modal-body { padding: 0 !important; max-height: 80vh !important; overflow: auto !important; }
		.dob3-item-dialog .table-responsive { max-height: 78vh !important; overflow: auto !important; }
		.dob3-item-dialog .modal-dialog { width: 96vw !important; max-width: 1200px !important; margin: 10px auto !important; }
		.dob3-item-dialog .dob3-tbl thead th { position: sticky !important; top: 0; z-index: 10; }
		.dob3-item-dialog .dob3-dialog-pad { padding: 16px 18px 18px; }

		.dob3-summary { max-width: 520px; }
		.dob3-sum-tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
		.dob3-sum-tbl th {
			background: #EEF2FA; color: #3A4A60; font-weight: 700; font-size: 10px;
			letter-spacing: .4px; text-transform: uppercase; padding: 8px 12px; border: 1px solid #E0E7F0; text-align: right;
		}
		.dob3-sum-tbl th:first-child { text-align: left; }
		.dob3-sum-tbl td { padding: 8px 12px; border: 1px solid #EBF0F8; text-align: right; font-variant-numeric: tabular-nums; }
		.dob3-sum-tbl td:first-child { text-align: left; font-weight: 500; }
		.dob3-sum-tbl tr.dob3-total td { background: #EEF2FA; font-weight: 700; border-top: 2px solid #C8D4E4; }
		.cv-bal-neg  { color: #C0392B; font-weight: 700; background: #FFF0F0; }
		.cv-bal-pos  { color: #1E8449; font-weight: 700; background: #EDFAF2; }
		.cv-bal-zero { color: #9AA3AF; }

		.dob3-skel {
			background: linear-gradient(90deg,#EEF2FA 25%,#DDE6F2 50%,#EEF2FA 75%);
			background-size: 200% 100%; animation: dob3-shimmer 1.3s infinite;
			height: 18px; border-radius: 6px; margin: 10px 0;
		}
		@keyframes dob3-shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
		.dob3-empty { text-align: center; padding: 44px 20px; color: #8796A8; font-size: 15px; }
		.dob3-empty i { font-size: 28px; margin-bottom: 8px; display: block; opacity: .4; }
		</style>`).appendTo('head');
	}

	_build_layout() {
		this.page.body.empty();
		this.$w        = $(`<div class="dob3-wrap"></div>`).appendTo(this.page.body);
		this.$fb       = $(`<div class="dob3-fb"></div>`).appendTo(this.$w);
		this.$sec_main = $(`<div class="dob3-sec">Dispatch Balance</div>`).appendTo(this.$w);
		this.$main     = $(`<div></div>`).appendTo(this.$w);
		this.$sec_sum  = $(`<div class="dob3-sec" style="margin-top:26px;"></div>`).appendTo(this.$w);
		this.$summary  = $(`<div class="dob3-summary"></div>`).appendTo(this.$w);
	}

	_build_filters() {
		const fi = (label, flex_override) => {
			const $d = $(`<div class="dob3-fi"></div>`);
			if (flex_override) $d.css(flex_override);
			$(`<label>${label}</label>`).appendTo($d);
			const $inner = $(`<div></div>`).appendTo($d);
			$d.appendTo(this.$fb);
			return $inner;
		};

		this.f_date = frappe.ui.form.make_control({
			parent: fi('As on Date')[0],
			df: { fieldname:'dob_date', fieldtype:'Date', onchange: () => this._sched() },
			render_input: true,
		});
		this.f_date.set_value(frappe.datetime.get_today());

		this.f_company = frappe.ui.form.make_control({
			parent: fi('Company')[0],
			df: { fieldname:'dob_co', fieldtype:'Link', options:'Company', only_select:1,
				  onchange: () => { this.f_plant.set_value(''); this._sched(); } },
			render_input: true,
		});

		this.f_plant = frappe.ui.form.make_control({
			parent: fi('Plant')[0],
			df: { fieldname:'dob_plant', fieldtype:'Link', options:'Branch', only_select:1,
				  get_query: () => { const co = this.f_company.get_value(); return co ? { filters:{ company:co } } : {}; },
				  onchange: () => this._sched() },
			render_input: true,
		});

		this.f_customer = frappe.ui.form.make_control({
			parent: fi('Customer')[0],
			df: { fieldname:'dob_cust', fieldtype:'Link', options:'Customer', onchange: () => this._sched() },
			render_input: true,
		});

		this.f_item = frappe.ui.form.make_control({
			parent: fi('Item')[0],
			df: { fieldname:'dob_item', fieldtype:'Link', options:'Item', onchange: () => this._sched() },
			render_input: true,
		});

		this.f_pono = frappe.ui.form.make_control({
			parent: fi('P.O. No')[0],
			df: { fieldname:'dob_pono', fieldtype:'Data', onchange: () => this._sched() },
			render_input: true,
		});
		this.f_pono.$input.on('input', () => this._sched());

		const $mode_wrap = fi('View Mode', { flex:'0 0 auto', minWidth:'auto' });
		const $mode = $(`<div class="dob3-mode"></div>`).appendTo($mode_wrap);
		this.$btn_qtr  = $(`<button class="dob3-active">By Quarter</button>`).appendTo($mode);
		this.$btn_item = $(`<button>By Item</button>`).appendTo($mode);
		this.$btn_qtr.on('click',  () => this._set_mode('quarter'));
		this.$btn_item.on('click', () => this._set_mode('item'));

		const $tog_wrap = fi('Options', { flex:'0 0 auto', minWidth:'auto' });
		$(`<label class="dob3-toggle">
			<input type="checkbox" checked/>
			<span class="dob3-track"><span class="dob3-thumb"></span></span>
			<span class="dob3-toggle-lbl">Show Zero Pending</span>
		</label>`).appendTo($tog_wrap).find('input').on('change', (e) => {
			this.show_zero = $(e.target).is(':checked');
			this._render_main();
		});

		const $acts = $(`<div style="display:flex;gap:8px;"></div>`).appendTo(
			fi('&nbsp;', { flex:'0 0 auto', minWidth:'auto' })
		);
		$(`<button class="dob3-btn dob3-btn-primary"><i class="fa fa-refresh"></i> Refresh</button>`)
			.appendTo($acts).on('click', () => this.refresh());
		$(`<button class="dob3-btn dob3-btn-default">Clear</button>`)
			.appendTo($acts).on('click', () => this._clear());

		this.$qpill_row = $(`
			<div style="width:100%;padding-top:6px;border-top:1px solid #EEF2F7;margin-top:2px;">
				<div style="font-size:10px;font-weight:700;letter-spacing:.6px;text-transform:uppercase;color:#8796A8;margin-bottom:6px;">Filter Quarter</div>
				<div class="dob3-qpills"></div>
			</div>`).appendTo(this.$fb).hide();
		this.$qpills = this.$qpill_row.find('.dob3-qpills');
	}

	_build_quarter_pills(quarters) {
		this.$qpills.empty();
		if (!quarters || !quarters.length) { this.$qpill_row.hide(); return; }
		const $all = $(`<button class="dob3-qpill dob3-qpill-all dob3-active">All Quarters</button>`)
			.appendTo(this.$qpills).on('click', () => {
				this.selected_quarter = null;
				this.$qpills.find('.dob3-qpill').removeClass('dob3-active');
				$all.addClass('dob3-active');
				this._render_main();
			});
		for (const q of quarters) {
			const $p = $(`<button class="dob3-qpill">${_esc(q.quarter)}</button>`)
				.appendTo(this.$qpills).on('click', () => {
					this.selected_quarter = q.quarter;
					this.expanded_quarters.add(q.quarter); // NEW: auto-expand the quarter being filtered to
					this.$qpills.find('.dob3-qpill').removeClass('dob3-active');
					$p.addClass('dob3-active');
					this._render_main();
				});
		}
		this.$qpill_row.show();
	}

	_set_mode(mode) {
		this.view_mode = mode;
		this.active_key = null;
		this.$btn_qtr.toggleClass('dob3-active',  mode === 'quarter');
		this.$btn_item.toggleClass('dob3-active', mode === 'item');
		this.$sec_main.text(mode === 'quarter' ? 'Dispatch Balance — By Quarter' : 'Dispatch Balance — By Item');
		this._render_main();
	}

	_sched() { clearTimeout(this._timer); this._timer = setTimeout(() => this.refresh(), 400); }

	_clear() {
		this.f_date.set_value(frappe.datetime.get_today());
		[this.f_company, this.f_plant, this.f_customer, this.f_item, this.f_pono]
			.forEach(f => f.set_value(''));
		this.show_zero = true;
		this.$fb.find('input[type=checkbox]').prop('checked', true);
		this.selected_quarter = null;
		this.$qpills.find('.dob3-qpill').removeClass('dob3-active');
		this.$qpills.find('.dob3-qpill-all').addClass('dob3-active');
		this.refresh();
	}

	_get_filters() {
		return {
			date:      this.f_date.get_value()     || frappe.datetime.get_today(),
			company:   this.f_company.get_value()  || '',
			plant:     this.f_plant.get_value()    || '',
			customer:  this.f_customer.get_value() || '',
			item_code: this.f_item.get_value()     || '',
			po_no:     this.f_pono.get_value()     || '',
		};
	}

	_build_menu() {
		this.page.add_menu_item('Export Excel', () => this._export_excel());
		this.page.add_menu_item('Export PDF',   () => this._export_pdf());
	}

	refresh() {
		this._show_skeleton();
		frappe.call({
			method: 'informatics_custom_apps.ripl_customized_apps.page.dispatch_order_balan.dispatch_order_balan.get_page_data',
			args:   { filters: this._get_filters() },
			callback: (r) => {
				this.data = r.message || {};
				this.active_key = null;

				// NEW: default-expand the most recent (current) quarter so its
				// items are visible without an extra click; other quarters stay collapsed.
				const quarters = this.data.quarters || [];
				this.expanded_quarters = quarters.length
					? new Set([quarters[quarters.length - 1].quarter])
					: new Set();

				this._build_quarter_pills(this.data.quarters);
				this._set_mode(this.view_mode);
				this._render_summary(this.data.today_summary, this.data.as_on);
			},
			error: () => {
				this.$main.html(`<div class="dob3-empty"><i class="fa fa-exclamation-triangle"></i>Failed to load data.</div>`);
			},
		});
	}

	_show_skeleton() {
		const sk = () => `<div class="dob3-skel" style="width:${55+(Math.random()*38|0)}%"></div>`;
		this.$main.html(`<div>${sk()}${sk()}${sk()}</div>`);
		this.$summary.empty(); this.$sec_sum.text('');
	}

	/* ── MAIN TABLE HEADERS (3 columns: Ordered / Supplied / Pending) ── */
	_th(first_label) {
		return `<tr>
			<th class="dob3-rowlabel" style="text-align:left;background:#e8eef4 !important;border-right:3px solid #8fa8bb !important;">${first_label}</th>
			<th class="dob3-col-ord">Ordered</th>
			<th class="dob3-col-supt">Supplied</th>
			<th class="dob3-col-pend">Pending</th>
		</tr>`;
	}

	_render_main() {
		if (!this.data || !this.data.rows) return;
		const all_rows = this.data.rows;
		if (!all_rows.length) {
			this.$main.html(`<div class="dob3-empty"><i class="fa fa-inbox"></i>No dispatch orders found.</div>`);
			return;
		}
		if (this.view_mode === 'quarter') {
			this._render_quarter_mode(all_rows);
		} else {
			this._render_item_mode(all_rows);
		}
	}

	_visible_quarters() {
		const quarters = this.data.quarters || [];
		return this.selected_quarter
			? quarters.filter(q => q.quarter === this.selected_quarter)
			: quarters;
	}

	/* ═══════════════════════════════════════════════════
	   QUARTER MODE  — 3-level inline drill
	   Quarter block (click header to expand/collapse)
	     └─ Item rows (click to expand Customer panel)
	          └─ Customer rows (click to open PO dialog)
	═══════════════════════════════════════════════════ */
	_render_quarter_mode(all_rows) {
		const quarters = this._visible_quarters();
		const $wrap = $(`<div></div>`);

		if (!quarters.length) {
			$wrap.html(`<div class="dob3-empty"><i class="fa fa-inbox"></i>No quarters found.</div>`);
			this.$main.empty().append($wrap);
			return;
		}

		for (const q of quarters) {
			const q_rows = all_rows.filter(r => r.po_date && r.po_date >= q.start_date && r.po_date <= q.effective_end);
			if (!q_rows.length && !this.show_zero) continue;
			this._render_quarter_block($wrap, q, q_rows);
		}

		this.$main.empty().append($wrap);
	}

	_render_quarter_block($wrap, q, q_rows) {
		const agg = _agg(q_rows);
		const expanded = this.expanded_quarters.has(q.quarter); // NEW

		const $block = $(`<div class="dob3-qblock"></div>`).appendTo($wrap);

		// Quarter header bar — now clickable to expand/collapse
		const $hdr = $(`<div class="dob3-qhdr${expanded ? ' dob3-qhdr-open' : ''}">
			<span class="dob3-qchev">›</span>
			<i class="fa fa-calendar" style="opacity:.7;"></i>
			<span>${_esc(q.quarter)}</span>
			<span style="font-size:11px;opacity:.7;">${q.start_date} → ${q.effective_end}</span>
			<div class="dob3-qhdr-right">
				<span class="dob3-badge dob3-badge-hint">Ordered: ${_n(agg.order)}</span>
				<span class="dob3-badge dob3-badge-sort">Supplied: ${_n(agg.supplied)}</span>
				<span class="dob3-badge dob3-badge-pend" style="background:#fff0f0;color:#a02020;border:1px solid #f0b4b4;">Pending: ${_n(agg.pending)}</span>
			</div>
		</div>`).appendTo($block);

		$hdr.on('click', () => {
			if (this.expanded_quarters.has(q.quarter)) {
				this.expanded_quarters.delete(q.quarter);
			} else {
				this.expanded_quarters.add(q.quarter);
			}
			this._render_main();
		});

		if (!expanded) return; // collapsed — don't render the items table

		// Item table inside this quarter
		const item_map = _group(q_rows, r => r.item_code);
		const item_entries = Object.entries(item_map).map(([ic, i_rows]) => ({
			key: ic, label: i_rows[0].item_name || ic, rows: i_rows, agg: _agg(i_rows),
		}));
		const visible_items = this.show_zero ? item_entries : item_entries.filter(e => e.agg.pending > 0);

		if (!visible_items.length) {
			$(`<div class="dob3-empty" style="padding:18px;"><i class="fa fa-inbox"></i>No items.</div>`).appendTo($block);
			return;
		}

		const $tbl_wrap = $(`<div class="dob3-table-wrap" style="border-radius:0;border:none;border-top:2px solid #aab8c3;"></div>`).appendTo($block);
		const $tbody = $(`<table class="dob3-sumtbl"><thead>${this._th('Item')}</thead><tbody></tbody></table>`).appendTo($tbl_wrap).find('tbody');

		const q_key = q.quarter;
		visible_items.forEach(e => {
			const a   = e.agg;
			const epc = _pend_cls(a.pending);
			const composite_key = q_key + '|||' + e.key;
			const is_active = this.active_key === composite_key;

			const $row = $(`<tr class="dob3-itemrow${is_active ? ' dob3-itemrow-active' : ''}" data-ckey="${_esc(composite_key)}">
				<td class="dob3-rowlabel">
					${_esc(e.label)}
					<div class="dob3-sub">${_esc(e.key)}</div>
					<span class="dob3-chev">›</span>
				</td>
				<td class="dob3-col-ord">${_n(a.order)}</td>
				<td class="dob3-col-supt">${_n(a.supplied)}</td>
				<td class="dob3-col-pend ${epc}">${_n(a.pending)}</td>
			</tr>`).appendTo($tbody);

			// If this item is active, render customer panel as a full-width row below
			if (is_active) {
				const $panel_row = $(`<tr><td colspan="4" style="padding:0;border-top:none;"></td></tr>`).appendTo($tbody);
				this._render_customer_panel($panel_row.find('td'), e.rows, q_key, e.label);
			}

			$row.on('click', () => {
				this.active_key = (this.active_key === composite_key) ? null : composite_key;
				this._render_main();
			});
		});

		// Quarter total row
		const ta = _agg(visible_items.map(e => e.rows).flat());
		$(`<tr class="dob3-totalrow">
			<td class="dob3-rowlabel">Total</td>
			<td class="dob3-col-ord">${_n(ta.order)}</td>
			<td class="dob3-col-supt">${_n(ta.supplied)}</td>
			<td class="dob3-col-pend ${_pend_cls(ta.pending)}">${_n(ta.pending)}</td>
		</tr>`).appendTo($tbody);
	}

	_render_customer_panel($container, item_rows, q_label, item_label) {
		const cust_map = _group(item_rows, r => r.customer_name);
		const cust_entries = Object.entries(cust_map).map(([cust, c_rows]) => ({
			key: cust, label: cust, rows: c_rows, agg: _agg(c_rows),
		}));
		const visible = this.show_zero ? cust_entries : cust_entries.filter(e => e.agg.pending > 0);

		const $card = $(`<div class="dob3-card dob3-custpanel" style="margin:0;border-radius:0;box-shadow:none;border-left:5px solid #27AE60;border-right:none;border-bottom:none;"></div>`).appendTo($container);

		if (!visible.length) {
			$card.html(`<div class="dob3-empty" style="padding:14px;"><i class="fa fa-inbox"></i>No customers.</div>`);
			return;
		}

		// FIX: build the title block and the table-wrap as two SEPARATE appends
		// directly onto $card, instead of creating both as sibling root nodes in
		// one jQuery-parsed multi-root string and then trying to `.find()` one
		// out of the other. `.find()` only searches descendants — siblings
		// inside the same parsed collection are never descendants of each other —
		// so the previous code's `$tbl_wrap` was always empty and the table was
		// being appended to nothing. That's why the customer panel never showed.
		$(`<div style="padding:12px 16px 4px;">
			<div class="dob3-card-title" style="font-size:13px;margin-bottom:8px;">
				<i class="fa fa-users" style="color:#27AE60;"></i>
				Customer Wise — ${_esc(item_label)}
				<span class="dob3-badge dob3-badge-hint" style="font-size:10px;">Click customer for PO detail</span>
			</div>
		</div>`).appendTo($card);

		const $tbl_wrap = $(`<div class="dob3-table-wrap" style="margin:0 16px 14px;"></div>`).appendTo($card);
		const $tbody = $(`<table class="dob3-sumtbl"><thead>${this._th('Customer')}</thead><tbody></tbody></table>`)
			.appendTo($tbl_wrap).find('tbody');

		visible.forEach(e => {
			const a  = e.agg;
			const pc = _pend_cls(a.pending);
			$(`<tr class="dob3-custrow">
				<td class="dob3-rowlabel">${_esc(e.label)}<span class="dob3-chev">›</span></td>
				<td class="dob3-col-ord">${_n(a.order)}</td>
				<td class="dob3-col-supt">${_n(a.supplied)}</td>
				<td class="dob3-col-pend ${pc}">${_n(a.pending)}</td>
			</tr>`).appendTo($tbody).on('click', () => {
				this._open_customer_po_dialog(item_label, e.label, e.rows);
			});
		});

		const ta = _agg(visible.map(e => e.rows).flat());
		$(`<tr class="dob3-totalrow">
			<td class="dob3-rowlabel">Total</td>
			<td class="dob3-col-ord">${_n(ta.order)}</td>
			<td class="dob3-col-supt">${_n(ta.supplied)}</td>
			<td class="dob3-col-pend ${_pend_cls(ta.pending)}">${_n(ta.pending)}</td>
		</tr>`).appendTo($tbody);
	}

	/* ═══════════════════════════════════════════════════
	   ITEM MODE  — same as before:
	   Item summary → Customer panel → PO dialog
	═══════════════════════════════════════════════════ */
	_render_item_mode(all_rows) {
		const filter_rows = this.selected_quarter
			? (() => {
				const q = (this.data.quarters || []).find(x => x.quarter === this.selected_quarter);
				return q ? all_rows.filter(r => r.po_date && r.po_date >= q.start_date && r.po_date <= q.effective_end) : all_rows;
			  })()
			: all_rows;

		const item_entries = Object.entries(_group(filter_rows, r => r.item_code)).map(([ic, i_rows]) => ({
			key: ic, label: i_rows[0].item_name || ic, sub: ic, rows: i_rows, agg: _agg(i_rows),
		}));
		const visible = this.show_zero ? item_entries : item_entries.filter(e => e.agg.pending > 0);

		const $wrap = $(`<div></div>`);
		if (!visible.length) {
			$wrap.html(`<div class="dob3-empty"><i class="fa fa-inbox"></i>No pending balance.</div>`);
			this.$main.empty().append($wrap);
			return;
		}

		this._render_item_summary_table($wrap, visible);
		const active = visible.find(e => e.key === this.active_key);
		if (active) this._render_item_customer_panel($wrap, active);
		this.$main.empty().append($wrap);
	}

	_render_item_summary_table($wrap, entries) {
		let totals = { order:0, supplied:0, pending:0 };
		let body = '';

		entries.forEach(e => {
			const a = e.agg;
			totals.order    += a.order;
			totals.supplied += a.supplied;
			totals.pending  += a.pending;
			const pc        = _pend_cls(a.pending);
			const is_active = this.active_key === e.key;
			body += `<tr class="dob3-sumrow${is_active ? ' dob3-sumrow-active' : ''}" data-key="${_esc(e.key)}">
				<td class="dob3-rowlabel">
					${_esc(e.label)}
					<div class="dob3-sub">${_esc(e.sub)}</div>
					<span class="dob3-chev">›</span>
				</td>
				<td class="dob3-col-ord">${_n(a.order)}</td>
				<td class="dob3-col-supt">${_n(a.supplied)}</td>
				<td class="dob3-col-pend ${pc}">${_n(a.pending)}</td>
			</tr>`;
		});

		body += `<tr class="dob3-totalrow">
			<td class="dob3-rowlabel">Total</td>
			<td class="dob3-col-ord">${_n(totals.order)}</td>
			<td class="dob3-col-supt">${_n(totals.supplied)}</td>
			<td class="dob3-col-pend ${_pend_cls(totals.pending)}">${_n(totals.pending)}</td>
		</tr>`;

		const $card = $(`
			<div class="dob3-card">
				<div class="dob3-card-title">
					Item Summary
					<span class="dob3-badge dob3-badge-hint">Click a row for customer detail</span>
					<span class="dob3-badge dob3-badge-sort">Qty in base UOM</span>
				</div>
				<div class="dob3-table-wrap">
					<table class="dob3-sumtbl">
						<thead>${this._th('Item')}</thead>
						<tbody>${body}</tbody>
					</table>
				</div>
			</div>`).appendTo($wrap);

		$card.find('tr.dob3-sumrow').on('click', ev => {
			const key = $(ev.currentTarget).data('key');
			this.active_key = (this.active_key === key) ? null : String(key);
			this._render_main();
		});
	}

	_render_item_customer_panel($wrap, active_entry) {
		const cust_entries = Object.entries(_group(active_entry.rows, r => r.customer_name)).map(([cust, c_rows]) => ({
			key: cust, label: cust, rows: c_rows, agg: _agg(c_rows),
		}));
		const visible = this.show_zero ? cust_entries : cust_entries.filter(e => e.agg.pending > 0);

		const $card = $(`<div class="dob3-card dob3-panel"></div>`).appendTo($wrap);
		const title = `${_esc(active_entry.label)} — Customer Wise Detail`;

		if (!visible.length) {
			$card.html(`<div class="dob3-card-title">${title}</div>
				<div class="dob3-empty" style="padding:20px;"><i class="fa fa-inbox"></i>No customers.</div>`);
			return;
		}

		let body = '';
		visible.forEach(e => {
			const a = e.agg, pc = _pend_cls(a.pending);
			body += `<tr class="dob3-subrow" data-key="${_esc(e.key)}">
				<td class="dob3-rowlabel">${_esc(e.label)}<span class="dob3-chev">›</span></td>
				<td class="dob3-col-ord">${_n(a.order)}</td>
				<td class="dob3-col-supt">${_n(a.supplied)}</td>
				<td class="dob3-col-pend ${pc}">${_n(a.pending)}</td>
			</tr>`;
		});

		$card.html(`
			<div class="dob3-card-title">
				${title}
				<span class="dob3-badge dob3-badge-hint">Click a customer for PO detail</span>
			</div>
			<div class="dob3-table-wrap">
				<table class="dob3-sumtbl">
					<thead>${this._th('Customer')}</thead>
					<tbody>${body}</tbody>
				</table>
			</div>`);

		$card.find('tr.dob3-subrow').on('click', ev => {
			const key = $(ev.currentTarget).data('key');
			const sub = visible.find(e => String(e.key) === String(key));
			if (sub) this._open_customer_po_dialog(active_entry.label, sub.label, sub.rows);
		});
	}

	_open_customer_po_dialog(item_label, customer_name, rows) {
		const dialog = new frappe.ui.Dialog({
			title: `${item_label} — ${customer_name} — PO Wise Detail`,
			size:  'extra-large',
			fields: [{ fieldtype:'HTML', fieldname:'dob3_po_html' }],
		});
		dialog.$wrapper.addClass('dob3-item-dialog');
		dialog.fields_dict.dob3_po_html.$wrapper.html(
			`<div class="dob3-dialog-pad">${this._po_table(rows)}</div>`
		);
		dialog.show();
	}

	_po_table(rows) {
		/* Group by PO No → aggregate per PO */
		const po_map = _group(rows, r => r.po_no || '—');
		const po_entries = Object.entries(po_map).map(([po_no, po_rows]) => ({
			po_no, rows: po_rows, agg: _agg(po_rows),
			po_date: po_rows[0].po_date,
			plant:   po_rows[0].plant,
		})).sort((a, b) => (b.po_date||'').localeCompare(a.po_date||''));

		let h = `<div class="table-responsive"><table class="dob3-tbl">
		<thead><tr>
			<th class="tl">P.O. No</th>
			<th class="tl">P.O. Date</th>
			<th class="tl">Plant</th>
			<th>Order Qty</th>
			<th>Supplied Qty</th>
			<th>Pending Qty</th>
			<th class="tl">Dispatch Orders</th>
		</tr></thead><tbody>`;

		for (const pe of po_entries) {
			const a = pe.agg;
			const pc = _pend_cls(a.pending).replace('dob3-val-pend-', 'cv-pend-');
			const do_links = pe.rows.map(r =>
				`<a href="/app/dispatch-order/${_esc(r.dispatch_order)}" target="_blank">${_esc(r.dispatch_order)}</a>`
			).join(', ');
			h += `<tr>
				<td class="tl"><strong>${_esc(pe.po_no)}</strong></td>
				<td class="tl">${pe.po_date ? frappe.datetime.str_to_user(pe.po_date) : ''}</td>
				<td class="tl">${_esc(pe.plant)}</td>
				<td>${_n(a.order)}</td>
				<td class="cv-sup">${_n(a.supplied)}</td>
				<td class="${pc}">${_n(a.pending)}</td>
				<td class="tl" style="font-size:11px;">${do_links}</td>
			</tr>`;
		}

		const ta = _agg(rows);
		const tc = _pend_cls(ta.pending).replace('dob3-val-pend-', 'cv-pend-');
		h += `<tr class="dob3-total">
			<td colspan="3" class="tl"><strong>Total</strong></td>
			<td>${_n(ta.order)}</td>
			<td class="cv-sup">${_n(ta.supplied)}</td>
			<td class="${tc}">${_n(ta.pending)}</td>
			<td></td>
		</tr>`;
		return h + `</tbody></table></div>`;
	}

	_open_order_dialog(title, rows) {
		const dialog = new frappe.ui.Dialog({
			title: `${title} — Order Wise Detail`,
			size:  'extra-large',
			fields: [{ fieldtype:'HTML', fieldname:'dob3_order_html' }],
		});
		dialog.$wrapper.addClass('dob3-item-dialog');
		dialog.fields_dict.dob3_order_html.$wrapper.html(
			`<div class="dob3-dialog-pad">${this._orders_table(rows)}</div>`
		);
		dialog.show();
	}

	_orders_table(rows) {
		const sorted = [...rows].sort((a, b) => {
			if (a.customer_name !== b.customer_name) return (a.customer_name||'').localeCompare(b.customer_name||'');
			return (b.po_date||'').localeCompare(a.po_date||'');
		});

		let h = `<div class="table-responsive"><table class="dob3-tbl">
		<thead><tr>
			<th class="tl">Customer</th>
			<th class="tl">Dispatch Order</th>
			<th class="tl">P.O. No</th>
			<th class="tl">P.O. Date</th>
			<th>Order Qty</th>
			<th>Supplied Qty</th>
			<th>Pending Qty</th>
			<th class="tl">Plant</th>
			<th>UOM</th>
		</tr></thead><tbody>`;

		for (const r of sorted) {
			const p = r.pending_qty;
			const pc = p > 0 ? 'cv-pend-pos' : p < 0 ? 'cv-pend-neg' : 'cv-pend-zero';
			h += `<tr>
				<td class="tl">${_esc(r.customer_name)}</td>
				<td class="tl"><a href="/app/dispatch-order/${_esc(r.dispatch_order)}" target="_blank">${_esc(r.dispatch_order)}</a></td>
				<td class="tl">${_esc(r.po_no)}</td>
				<td class="tl">${r.po_date ? frappe.datetime.str_to_user(r.po_date) : ''}</td>
				<td>${_n(r.order_qty)}</td>
				<td class="cv-sup">${_n(r.supplied_qty)}</td>
				<td class="${pc}">${_n(p)}</td>
				<td class="tl">${_esc(r.plant)}</td>
				<td class="cv-uom">${_esc(r.uom)}</td>
			</tr>`;
		}

		const ta = _agg(rows);
		const tc = _pend_cls(ta.pending).replace('dob3-val-pend-', 'cv-pend-');
		h += `<tr class="dob3-total">
			<td colspan="4" class="tl"><strong>Total</strong></td>
			<td>${_n(ta.order)}</td>
			<td class="cv-sup">${_n(ta.supplied)}</td>
			<td class="${tc}">${_n(ta.pending)}</td>
			<td></td><td></td>
		</tr>`;
		return h + `</tbody></table></div>`;
	}

	_render_summary(data, as_on) {
		if (!data || !data.length) {
			this.$sec_sum.text("Today's Stock & Dispatch");
			this.$summary.html(`<div class="dob3-empty" style="padding:16px;">No data.</div>`);
			return;
		}
		const dl = (data[0] && data[0].as_on) || as_on;
		this.$sec_sum.html(`Today&#39;s Stock &amp; Dispatch
			<span style="font-weight:500;font-size:11px;color:#8796A8;text-transform:none;letter-spacing:0;">
				— ${frappe.datetime.str_to_user(dl)}
			</span>`);

		const rows_html = data.map(d => {
			const is_t = d.item_code === 'TOTAL';
			const b    = parseFloat(d.balance_qty) || 0;
			const bc   = b < 0 ? 'cv-bal-neg' : b > 0 ? 'cv-bal-pos' : 'cv-bal-zero';
			return `<tr${is_t ? ' class="dob3-total"' : ''}>
				<td>${is_t ? '<strong>Total</strong>' : _esc(d.item_name || d.item_code)}</td>
				<td>${_n(d.stock_qty)}</td>
				<td>${_n(d.dispatch_qty)}</td>
				<td class="${bc}">${_n(b)}</td>
			</tr>`;
		}).join('');

		this.$summary.html(`
			<div class="dob3-card" style="max-width:520px;">
				<table class="dob3-sum-tbl">
					<thead><tr>
						<th style="text-align:left">Item</th>
						<th>Stock</th><th>Dispatched Today</th><th>Balance</th>
					</tr></thead>
					<tbody>${rows_html}</tbody>
				</table>
			</div>`);
	}

	async _export_excel() {
		if (!this.data) { frappe.msgprint('Load data first.'); return; }
		frappe.show_alert({ message:'Preparing Excel…', indicator:'blue' });
		try { await _load_script('https://cdnjs.cloudflare.com/ajax/libs/exceljs/4.4.0/exceljs.min.js'); }
		catch(e) { frappe.msgprint('Could not load ExcelJS.'); return; }

		const wb = new window.ExcelJS.Workbook();
		const ws = wb.addWorksheet('Dispatch Balance');
		const { rows, as_on } = this.data;
		const THIN = { style:'thin', color:{ argb:'FFC8D4E4' } };
		const B  = { top:THIN, left:THIN, bottom:THIN, right:THIN };
		const Hf = { type:'pattern', pattern:'solid', fgColor:{ argb:'FFEEF2FA' } };
		const Pf = { type:'pattern', pattern:'solid', fgColor:{ argb:'FFFFF0F0' } };
		const Sf = { type:'pattern', pattern:'solid', fgColor:{ argb:'FFEBF3FF' } };

		const hdrs = ['Item','Item Code','Plant','Customer','Dispatch Order',
			'P.O. No','P.O. Date','Order Qty','Supplied Qty','Pending Qty','UOM'];

		let r = 1;
		ws.getRow(r).getCell(1).value = `Dispatch Order Balance — As on: ${as_on}`;
		ws.getRow(r).getCell(1).font  = { bold:true, size:13 };
		ws.mergeCells(r, 1, r, hdrs.length);
		r += 2;

		const hr = ws.getRow(r);
		hdrs.forEach((h, i) => {
			const c = hr.getCell(i+1);
			c.value = h; c.font = { bold:true }; c.fill = Hf; c.border = B;
		});
		r += 1;

		for (const row of rows) {
			if (!this.show_zero && row.pending_qty <= 0) continue;
			const xr = ws.getRow(r); let c = 1;
			xr.getCell(c++).value = row.item_name;
			xr.getCell(c++).value = row.item_code;
			xr.getCell(c++).value = row.plant;
			xr.getCell(c++).value = row.customer_name;
			xr.getCell(c++).value = row.dispatch_order;
			xr.getCell(c++).value = row.po_no;
			xr.getCell(c++).value = row.po_date ? frappe.datetime.str_to_user(row.po_date) : '';
			xr.getCell(c++).value = row.order_qty;
			const sc = xr.getCell(c++); sc.value = row.supplied_qty; sc.fill = Sf;
			const pc = xr.getCell(c++); pc.value = row.pending_qty;
			if (row.pending_qty > 0) { pc.fill = Pf; pc.font = { bold:true, color:{ argb:'FFC0392B' } }; }
			xr.getCell(c++).value = row.uom;
			for (let cc = 1; cc <= hdrs.length; cc++) {
				const cell = xr.getCell(cc);
				if (typeof cell.value === 'number') cell.numFmt = '0.000';
				cell.border = B;
			}
			r += 1;
		}

		ws.columns.forEach((col, i) => { col.width = i < 7 ? 18 : 13; });
		const buf = await wb.xlsx.writeBuffer();
		_download_blob(buf, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
			`dispatch-order-balance-${as_on}.xlsx`);
		frappe.show_alert({ message:'Excel downloaded!', indicator:'green' });
	}

	async _export_pdf() {
		if (!this.data) { frappe.msgprint('Load data first.'); return; }
		frappe.show_alert({ message:'Preparing PDF…', indicator:'blue' });
		try {
			await _load_script('https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js');
			await _load_script('https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.8.2/jspdf.plugin.autotable.min.js');
		} catch(e) { frappe.msgprint('Could not load PDF libs.'); return; }

		const { jsPDF } = window.jspdf;
		const doc = new jsPDF({ orientation:'landscape', unit:'pt', format:'a4' });
		const { rows, as_on } = this.data;
		const PW = doc.internal.pageSize.getWidth();
		const PH = doc.internal.pageSize.getHeight();
		const M = 26, FH = 22;
		let curY = M;

		doc.setFont('helvetica','bold'); doc.setFontSize(13); doc.setTextColor(15,27,60);
		doc.text(`Dispatch Order Balance — As on: ${as_on}`, M, curY+10); curY += 22;

		const heads = ['Customer','Dispatch Order','P.O. No','P.O. Date','Order Qty','Supplied Qty','Pending Qty','UOM'];

		for (const [ic, i_rows] of Object.entries(_group(rows, r => r.item_code))) {
			const ia = _agg(i_rows);
			if (!this.show_zero && ia.pending <= 0) continue;
			if (curY + 40 > PH - FH) { doc.addPage(); curY = M; }

			doc.setFillColor(15,39,80); doc.rect(M, curY, PW-M*2, 15,'F');
			doc.setFont('helvetica','bold'); doc.setFontSize(9); doc.setTextColor(220,235,255);
			doc.text(`${i_rows[0].item_name}  (${ic})`, M+6, curY+10); curY += 18;

			const body = i_rows
				.filter(r => this.show_zero || r.pending_qty > 0)
				.map(r => [r.customer_name, r.dispatch_order, r.po_no,
					r.po_date ? frappe.datetime.str_to_user(r.po_date) : '',
					_n(r.order_qty), _n(r.supplied_qty), _n(r.pending_qty), r.uom]);
			if (!body.length) continue;

			const ta = _agg(i_rows.filter(r => this.show_zero || r.pending_qty > 0));
			body.push(['Total','','','' , _n(ta.order), _n(ta.supplied), _n(ta.pending), '']);

			doc.autoTable({
				head:[heads], body, startY:curY,
				margin:{ left:M, right:M, bottom:M+FH },
				styles:{ fontSize:7.5, cellPadding:3, font:'helvetica', textColor:[30,40,55] },
				headStyles:{ fillColor:[238,242,250], textColor:[35,55,90], fontStyle:'bold', fontSize:7 },
				didParseCell:(d) => {
					const ri=d.row.index, ci=d.column.index, is_t=ri===body.length-1;
					if (d.section==='body') {
						if (is_t) { d.cell.styles.fontStyle='bold'; d.cell.styles.fillColor=[238,242,250]; }
						if (ci===5) { d.cell.styles.halign='right'; d.cell.styles.fillColor=[235,245,255]; }
						if (ci===6) {
							const v = parseFloat(d.cell.raw) || 0;
							d.cell.styles.halign='right';
							d.cell.styles.textColor = v>0?[192,57,43]:v<0?[200,90,0]:[30,132,73];
							if (v>0) { d.cell.styles.fillColor=[255,240,240]; d.cell.styles.fontStyle='bold'; }
						}
					}
				},
				theme:'grid',
			});
			curY = doc.lastAutoTable.finalY + 12;
		}

		const tp = doc.internal.getNumberOfPages();
		for (let p=1;p<=tp;p++) {
			doc.setPage(p);
			doc.setDrawColor(225,230,238); doc.setLineWidth(0.4);
			doc.line(M, PH-FH+2, PW-M, PH-FH+2);
			doc.setFont('helvetica','normal'); doc.setFontSize(7); doc.setTextColor(130,140,155);
			doc.text(`Page ${p} of ${tp}`, PW-M, PH-FH+14, {align:'right'});
		}
		doc.save(`dispatch-order-balance-${as_on}.pdf`);
		frappe.show_alert({ message:'PDF downloaded!', indicator:'green' });
	}
}

/* ── UTILITIES ── */
function _group(arr, key_fn) {
	const map = {};
	for (const item of arr) {
		const k = key_fn(item);
		(map[k] = map[k] || []).push(item);
	}
	return map;
}

function _agg(rows) {
	let order=0, supplied=0, pending=0;
	for (const r of rows) {
		order    += r.order_qty    || 0;
		supplied += r.supplied_qty || 0;
		pending  += r.pending_qty  || 0;
	}
	return { order, supplied, pending };
}

function _pend_cls(v) {
	return v > 0 ? 'dob3-val-pend-pos' : v < 0 ? 'dob3-val-pend-neg' : 'dob3-val-pend-zero';
}

function _n(v) { const n = parseFloat(v); return isNaN(n) ? '' : n.toFixed(3); }

function _esc(v) { return frappe.utils.escape_html(String(v == null ? '' : v)); }

function _load_script(src) {
	return new Promise((res, rej) => {
		if (document.querySelector(`script[src="${src}"]`)) return res();
		const s = document.createElement('script');
		s.src = src; s.onload = res;
		s.onerror = () => rej(new Error(`Failed: ${src}`));
		document.head.appendChild(s);
	});
}

function _download_blob(content, mime, filename) {
	const blob = new Blob([content], {type:mime});
	const url  = URL.createObjectURL(blob);
	const a    = document.createElement('a');
	a.href=url; a.download=filename;
	document.body.appendChild(a); a.click(); document.body.removeChild(a);
	setTimeout(() => URL.revokeObjectURL(url), 1000);
}