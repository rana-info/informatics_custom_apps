frappe.pages['rm-planning-sheet'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'RM Planning / Ethanol Tender',
		single_column: true
	});

	new RMPlanningSheet(page);
};

class RMPlanningSheet {
	constructor(page) {
		this.page = page;
		this.inject_styles();
		this.setup_filters();
		this.setup_body();
		this.fetch_active_year();
	}

	inject_styles() {
		if (document.getElementById('rm-planning-sheet-style')) return;
		const style = document.createElement('style');
		style.id = 'rm-planning-sheet-style';
		style.innerHTML = `
			.rm-planning-toolbar {
				display: flex;
				align-items: flex-start;
				gap: 16px;
				flex-wrap: wrap;
				background: #f8f9fb;
				border: 1px solid #e3e6ec;
				border-radius: 8px;
				padding: 16px;
				margin-bottom: 16px;
			}
			.rm-planning-toolbar .frappe-control { margin-bottom: 0; min-width: 220px; }
			.rm-toolbar-actions {
				display: flex;
				flex-direction: column;
			}
			.rm-toolbar-actions-spacer {
				visibility: hidden;
				height: 1em;
				margin-bottom: 4px;
				font-size: 12px;
				line-height: 1;
			}
			.rm-toolbar-actions-buttons {
				display: flex;
				gap: 8px;
			}
			.rm-show-data-btn {
				height: 34px;
				padding: 0 20px;
				border-radius: 6px;
				border: none;
				background: #2e5aac;
				color: #fff;
				font-weight: 500;
				cursor: pointer;
			}
			.rm-show-data-btn:hover { background: #244a8f; }
			.rm-show-data-btn:disabled { background: #9fb3d6; cursor: not-allowed; }
			.rm-progress-wrap {
				display: none;
				height: 6px;
				width: 100%;
				background: #e6e9f0;
				border-radius: 4px;
				overflow: hidden;
				margin-bottom: 16px;
			}
			.rm-progress-wrap.active { display: block; }
			.rm-progress-bar {
				height: 100%;
				width: 40%;
				background: #2e5aac;
				border-radius: 4px;
				animation: rm-progress-slide 1.1s ease-in-out infinite;
			}
			@keyframes rm-progress-slide {
				0% { margin-left: -40%; }
				100% { margin-left: 100%; }
			}
			.rm-planning-sheet-wrapper {
				display: grid;
				grid-template-columns: repeat(2, 1fr);
				gap: 20px;
				align-items: start;
			}
			.rm-plant-card {
				border: 1px solid #e3e6ec;
				border-radius: 10px;
				overflow: hidden;
				margin-bottom: 0;
				background: #fff;
				min-width: 0;
			}
			.rm-plant-card-header {
				background: #eef2f9;
				padding: 10px 16px;
				font-weight: 600;
				font-size: 14px;
				color: #24324d;
				border-bottom: 1px solid #e3e6ec;
			}
			.rm-planning-table {
				width: 100%;
				border-collapse: collapse;
				font-size: 13px;
				margin: 0;
			}
			.rm-planning-table th {
				background: #f4f6fa;
				border: 1px solid #e3e6ec;
				padding: 8px 10px;
				text-align: center;
				color: #3b4457;
				font-weight: 600;
			}
			.rm-planning-table td {
				border: 1px solid #e3e6ec;
				padding: 6px 10px;
			}
			.rm-planning-table tr.rm-row-allocation td { background: #fffbe0; }
			.rm-planning-table tr.rm-row-dispatch td { background: #f2f9ff; }
			.rm-planning-table tr.rm-row-total td { background: #eef1f6; font-weight: 600; }
			.rm-planning-table tr.rm-row-net td { background: #fff0e8; font-weight: 700; }
			.rm-planning-table tr.rm-row-purchase td { background: #eaf7ec; font-weight: 700; }
			.rm-planning-table td.rm-label { text-align: left; font-weight: 500; color: #24324d; }
			.rm-empty-state {
				text-align: center;
				color: #8a94a6;
				padding: 40px 0;
				border: 1px dashed #d3d8e2;
				border-radius: 8px;
				grid-column: 1 / -1;
			}
			.rm-no-data-plant {
				padding: 16px;
				color: #8a94a6;
				font-style: italic;
			}
			@media (max-width: 900px) {
				.rm-planning-sheet-wrapper {
					grid-template-columns: 1fr;
				}
			}
			.rm-export-btn {
				height: 34px;
				padding: 0 16px;
				border-radius: 6px;
				border: 1px solid #d3d8e2;
				background: #fff;
				color: #24324d;
				font-weight: 500;
				cursor: pointer;
			}
			.rm-export-btn:hover:not(:disabled) { background: #f4f6fa; }
			.rm-export-btn:disabled { color: #b7bfcc; cursor: not-allowed; }
			@media print {
				body.rm-printing .navbar,
				body.rm-printing .page-head,
				body.rm-printing .layout-side-section,
				body.rm-printing .rm-planning-toolbar,
				body.rm-printing .rm-progress-wrap,
				body.rm-printing .page-actions,
				body.rm-printing .content .page-head,
				body.rm-printing .container .page-head {
					display: none !important;
				}
				body.rm-printing .layout-main-section-wrapper,
				body.rm-printing .layout-main-section {
					margin: 0 !important;
					padding: 0 !important;
					width: 100% !important;
				}
				body.rm-printing .rm-planning-sheet-wrapper {
					display: block !important;
				}
				body.rm-printing .rm-plant-card {
					page-break-inside: avoid;
					break-inside: avoid;
					margin-bottom: 16px !important;
				}
			}
		`;
		document.head.appendChild(style);
	}

	setup_filters() {
		this.toolbar = $(`<div class="rm-planning-toolbar"></div>`).appendTo(this.page.body);

		this.plant_filter = frappe.ui.form.make_control({
			parent: this.toolbar,
			df: {
				fieldtype: 'MultiSelectList',
				fieldname: 'plants',
				label: 'Plants',
				get_data: (txt) => {
					return frappe.db.get_link_options('Branch', txt);
				}
			},
			render_input: true
		});

		this.year_filter = frappe.ui.form.make_control({
			parent: this.toolbar,
			df: {
				fieldtype: 'Link',
				fieldname: 'ethanol_supply_year',
				label: 'Ethanol Supply Year',
				options: 'Ethanol Supply Year'
			},
			render_input: true
		});

		this.capacity_filter = frappe.ui.form.make_control({
			parent: this.toolbar,
			df: {
				fieldtype: 'Float',
				fieldname: 'daily_capacity',
				label: 'Daily Capacity (KL/day)',
				reqd: 1,
				description: 'Mandatory: enter the plant\'s full production capacity'
			},
			render_input: true
		});

		this.actions_wrap = $(`
			<div class="rm-toolbar-actions">
				<div class="rm-toolbar-actions-spacer">&nbsp;</div>
				<div class="rm-toolbar-actions-buttons"></div>
			</div>
		`).appendTo(this.toolbar);
		this.actions_buttons = this.actions_wrap.find('.rm-toolbar-actions-buttons');

		this.show_btn = $(`<button class="rm-show-data-btn">Show data</button>`)
			.appendTo(this.actions_buttons)
			.on('click', () => this.refresh());

		this.export_excel_btn = $(`<button class="rm-export-btn" disabled>Export Excel</button>`)
			.appendTo(this.actions_buttons)
			.on('click', () => this.export_excel());

		this.export_pdf_btn = $(`<button class="rm-export-btn" disabled>Export PDF</button>`)
			.appendTo(this.actions_buttons)
			.on('click', () => this.export_pdf());

		this.progress_wrap = $(`<div class="rm-progress-wrap"><div class="rm-progress-bar"></div></div>`)
			.insertAfter(this.toolbar);
	}

	setup_body() {
		this.wrapper = $(`<div class="rm-planning-sheet-wrapper"></div>`).appendTo(this.page.body);
		this.wrapper.html(`<div class="rm-empty-state">Select plant(s) and click "Show data" to load the planning sheet.</div>`);
	}

	fetch_active_year() {
		frappe.call({
			method: 'informatics_custom_apps.ripl_customized_apps.page.rm_planning_sheet.rm_planning_sheet.get_active_supply_year',
			callback: (r) => {
				if (r.message) {
					this.year_filter.set_value(r.message);
				}
			}
		});
	}

	show_progress(state) {
		if (state) {
			this.progress_wrap.addClass('active');
			this.show_btn.prop('disabled', true).text('Loading...');
		} else {
			this.progress_wrap.removeClass('active');
			this.show_btn.prop('disabled', false).text('Show data');
		}
	}

	refresh() {
		const plants = this.plant_filter.get_value() || [];
		if (!plants || !plants.length) {
			frappe.msgprint('Please select at least one plant.');
			return;
		}

		const capacity = this.capacity_filter.get_value();
		if (!capacity || flt(capacity) <= 0) {
			frappe.msgprint('Please enter the Daily Capacity (KL/day) - it is mandatory.');
			return;
		}

		this.show_progress(true);

		frappe.call({
			method: 'informatics_custom_apps.ripl_customized_apps.page.rm_planning_sheet.rm_planning_sheet.get_planning_data',
			args: {
				plants: plants,
				ethanol_supply_year: this.year_filter.get_value(),
				daily_capacity: this.capacity_filter.get_value()
			},
			always: () => this.show_progress(false),
			callback: (r) => {
				if (r.message) {
					this.last_plants = plants;
					this.last_year = this.year_filter.get_value();
					this.last_capacity = this.capacity_filter.get_value();
					this.render(r.message);
				}
			}
		});
	}

	export_excel() {
		if (!this.has_data || !this.last_plants) {
			frappe.msgprint('Please load data first.');
			return;
		}
		if (!this.last_capacity || flt(this.last_capacity) <= 0) {
			frappe.msgprint('Please enter the Daily Capacity (KL/day) and click "Show data" again before exporting.');
			return;
		}

		open_url_post(frappe.request.url, {
			cmd: 'informatics_custom_apps.ripl_customized_apps.page.rm_planning_sheet.rm_planning_sheet.export_planning_excel',
			plants: JSON.stringify(this.last_plants),
			ethanol_supply_year: this.last_year,
			daily_capacity: this.last_capacity
		});
	}

	export_pdf() {
		if (!this.has_data) {
			frappe.msgprint('Please load data first.');
			return;
		}

		document.body.classList.add('rm-printing');

		const cleanup = () => {
			document.body.classList.remove('rm-printing');
			window.removeEventListener('afterprint', cleanup);
		};
		window.addEventListener('afterprint', cleanup);

		setTimeout(cleanup, 5000);

		window.print();
	}

	render(data) {
		this.wrapper.empty();
		this.has_data = false;
		this.export_excel_btn.prop('disabled', true);
		this.export_pdf_btn.prop('disabled', true);

		if (!data.plants || !data.plants.length) {
			this.wrapper.html(`<div class="rm-empty-state">No data found.</div>`);
			return;
		}

		this.has_data = true;
		this.export_excel_btn.prop('disabled', false);
		this.export_pdf_btn.prop('disabled', false);

		data.plants.forEach((plant_data) => {
			const card = $(`
				<div class="rm-plant-card">
					<div class="rm-plant-card-header">${frappe.utils.escape_html(plant_data.plant)}</div>
				</div>
			`).appendTo(this.wrapper);

			if (plant_data.no_data) {
				$(`<div class="rm-no-data-plant">No Ethanol Allocation found for this plant / supply year.</div>`).appendTo(card);
				return;
			}

			card.append(this.build_table(plant_data));
		});
	}

	build_table(d) {
		const fmt = (v) => frappe.format(v || 0, { fieldtype: 'Float', precision: 2 });
		const fmt1 = (v) => frappe.format(v || 0, { fieldtype: 'Float', precision: 1 });

		const row = (label, vals, uom, cls) => `
			<tr class="${cls || ''}">
				<td class="rm-label">${label}</td>
				<td class="text-center">${frappe.utils.escape_html(uom || '')}</td>
				<td class="text-right">${fmt(vals.DFG)}</td>
				<td class="text-right">${fmt(vals.Maize)}</td>
				<td class="text-right">${fmt(vals.FCI)}</td>
				<td class="text-right">${fmt((vals.DFG || 0) + (vals.Maize || 0) + (vals.FCI || 0))}</td>
			</tr>`;

		const row_total_only = (label, value, uom, cls) => `
			<tr class="${cls || ''}">
				<td class="rm-label">${label}</td>
				<td class="text-center">${frappe.utils.escape_html(uom || '')}</td>
				<td class="text-right"></td>
				<td class="text-right"></td>
				<td class="text-right"></td>
				<td class="text-right">${fmt1(value)}</td>
			</tr>`;

		const fg_uom = d.fg_uom || 'KL';
		const rm_uom = d.rm_uom || 'Quintal';

		let quarter_rows = '';
		Object.keys(d.quarters || {}).forEach((q) => {
			quarter_rows += row(`${q} Allocation`, d.quarters[q], fg_uom, 'rm-row-allocation');
		});

		let dispatch_rows = '';
		Object.keys(d.dispatch_quarters || {}).forEach((q) => {
			dispatch_rows += row(`${q} Dispatch`, d.dispatch_quarters[q], fg_uom, 'rm-row-dispatch');
		});

		return `
			<table class="rm-planning-table">
				<thead>
					<tr>
						<th>Particulars</th>
						<th>UOM</th>
						<th>DFG</th>
						<th>Maize</th>
						<th>FCI</th>
						<th>Total</th>
					</tr>
				</thead>
				<tbody>
					${quarter_rows}
					${row('Total allocation (A)', d.total_allocation, fg_uom, 'rm-row-total')}
					${dispatch_rows}
					${row('Total dispatch (B)', d.total_dispatch, fg_uom, 'rm-row-total')}
					${row('Pending Dispatch (A-B)', d.pending_dispatch, fg_uom, 'rm-row-net')}
					${row('Total stock in hand (C)', d.stock_in_hand, fg_uom, 'rm-row-total')}
					${row_total_only('No. of Days in Hand (Full Capacity)', d.days_in_hand, 'Days', 'rm-row-net')}
					${row('Net pending production (A-B-C)', d.net_pending, fg_uom, 'rm-row-net')}
					${row('Recovery', d.recovery, '%')}
					${row('Qty of RM required', d.qty_rm_required, rm_uom, 'rm-row-total')}
					${row('RM at factory', d.rm_at_factory, rm_uom)}
					${row('Sauda in hand', d.sauda_in_hand, rm_uom)}
					${row('Sauda not delivered', d.sauda_not_delivered, rm_uom)}
					${row('Net qty need to purchase', d.net_qty_purchase, rm_uom, 'rm-row-total')}
					${row('Rate of RM', d.rate_rm, `₹/${rm_uom}`)}
					${row('Value of RM needs to purchase (Lakhs)', d.value_rm, 'Lakhs', 'rm-row-purchase')}
				</tbody>
			</table>`;
	}
}