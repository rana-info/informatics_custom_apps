frappe.pages['item-group-wise-stoc'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Item Group Wise Stock Summary',
		single_column: true,
	});

	wrapper.stock_summary = new StockSummary(page);
};

const GROUP_ORDER = ['Finished Goods', 'Fuel', 'Raw Material', 'General Store'];

const GROUP_CLASS = {
	'Finished Goods': 'fg',
	'Fuel':           'fuel',
	'Raw Material':   'rm',
	'General Store':  'gs',
};

const GROUP_METHOD = {
	'Finished Goods': 'get_finished_goods_detail',
	'Fuel':           'get_fuel_detail',
	'Raw Material':   'get_raw_material_detail',
	'General Store':  'get_general_store_detail',
};

class StockSummary {
	constructor(page) {
		this.page = page;
		this.method_path = 'informatics_custom_apps.ripl_customized_apps.page.item_group_wise_stoc.item_group_wise_stoc';

		this.active_groups   = new Set();
		this.detail_cache    = {};
		this.last_summary    = null;
		this._syncing_filter = false;
		this._rm_plantwise_visible = false;

		this.setup_filters();
		this.setup_body();
		this.inject_styles();
		this.refresh();
	}

	setup_filters() {
		this.company_field = this.page.add_field({
			label:     'Company',
			fieldtype: 'MultiSelectList',
			fieldname: 'company',
			get_data:  (txt) => frappe.db.get_link_options('Company', txt),
			change:    () => this.refresh(),
		});

		this.plant_field = this.page.add_field({
			label:     'Plant',
			fieldtype: 'MultiSelectList',
			fieldname: 'plant',
			get_data:  (txt) => frappe.db.get_link_options('Branch', txt),
			change:    () => this.refresh(),
		});

		this.as_on_date_field = this.page.add_field({
			label:     'As On Date',
			fieldtype: 'Date',
			fieldname: 'as_on_date',
			default:   frappe.datetime.get_today(),
			change:    () => this.refresh(),
		});

		this.item_group_field = this.page.add_field({
			label:     'Item Group',
			fieldtype: 'Select',
			fieldname: 'item_group',
			options:   ['', ...GROUP_ORDER].join('\n'),
			change:    () => this.on_group_filter_change(),
		});

		this.page.set_secondary_action('Refresh', () => this.refresh(), 'refresh');
	}

	get_query_filters() {
		return {
			company:     this.company_field.get_value(),
			plant:       this.plant_field.get_value(),
			as_on_date:  this.as_on_date_field.get_value() || frappe.datetime.get_today(),
		};
	}

	on_group_filter_change() {
		if (this._syncing_filter) return;
		const val = this.item_group_field.get_value();
		this.active_groups = val ? new Set([val]) : new Set();
		this.render_summary(this.last_summary);
		this.render_active_panels();
	}

	sync_filter_field() {
		this._syncing_filter = true;
		const arr = Array.from(this.active_groups);
		this.item_group_field.set_value(arr[0] || '');
		this._syncing_filter = false;
	}

	setup_body() {
		this.$wrapper = $(`<div class="stock-summary-wrapper"></div>`).appendTo(this.page.main);

		this.$summary_card = $(`
			<div class="stock-summary-card">
				<div class="stock-summary-card-title">
					Collapsed Summary
					<span class="unit-badge">₹ in Lakhs</span>
				</div>
				<div class="table-responsive">
					<table class="stock-summary-table">
						<thead><tr class="summary-head-row"></tr></thead>
						<tbody class="summary-body"></tbody>
					</table>
				</div>
			</div>
		`).appendTo(this.$wrapper);

		this.$detail_panels = $(`<div class="detail-panels"></div>`).appendTo(this.$wrapper);
	}

	refresh() {
		this._rm_plantwise_visible = false;
		frappe.call({
			method:          `${this.method_path}.get_collapsed_summary`,
			args:            this.get_query_filters(),
			freeze:          true,
			freeze_message:  'Loading stock summary...',
			callback: (r) => {
				if (r.message) {
					this.last_summary = r.message;
					this.detail_cache = {};
					this.render_summary(r.message);
					this.render_active_panels();
				}
			},
		});
	}

	render_summary(data) {
		if (!data) return;
		const { plants, rows, total } = data;

		const $head = this.$summary_card.find('.summary-head-row').empty();
		$head.append(`<th class="row-label-col">Group</th>`);
		plants.forEach((p, idx) =>
			$head.append(`<th class="plant-col plant-col-${idx % 4}">${frappe.utils.escape_html(p)}</th>`)
		);

		const $body = this.$summary_card.find('.summary-body').empty();

		rows.forEach((row) => {
			const cls       = GROUP_CLASS[row.label] || '';
			const is_active = this.active_groups.has(row.label);

			const $tr = $(`
				<tr class="summary-row group-${cls} ${is_active ? 'summary-row-active' : ''}"
				    data-group="${row.label}">
					<td class="row-label-col">
						<span class="group-dot"></span>
						${frappe.utils.escape_html(row.label)}
					</td>
					${plants.map((p, idx) => `<td class="num-cell plant-col plant-col-${idx % 4}">${this.format_value(row[p])}</td>`).join('')}
				</tr>
			`);

			$tr.on('click', () => this.toggle_group(row.label));
			$body.append($tr);
		});

		const $total_tr = $(`
			<tr class="summary-total-row">
				<td class="row-label-col">Total</td>
				${plants.map((p, idx) => `<td class="num-cell plant-col plant-col-${idx % 4}">${this.format_value(total[p])}</td>`).join('')}
			</tr>
		`);
		$body.append($total_tr);
	}

	toggle_group(label) {
		if (this.active_groups.has(label)) {
			this.active_groups.delete(label);
		} else {
			this.active_groups.clear();
			this.active_groups.add(label);
		}
		this._rm_plantwise_visible = false;
		this.sync_filter_field();
		this.render_summary(this.last_summary);
		this.render_active_panels();
	}

	render_active_panels() {
		this.$detail_panels.empty();

		GROUP_ORDER
			.filter((g) => this.active_groups.has(g))
			.forEach((label) => {
				const cls = GROUP_CLASS[label] || '';

				let extra_badge = '';
				if (label === 'Fuel') {
					extra_badge = `<span class="qty-badge">Qty in Qtl</span><span class="avg-badge">Avg in ₹/Qtl</span>`;
				} else if (label === 'Finished Goods') {
					extra_badge = `<span class="avg-badge">Avg Rate in ₹</span>`;
				} else if (label === 'Raw Material') {
					extra_badge = `<span class="qty-badge">Qty in Qtl</span><span class="avg-badge">Avg in ₹/Qtl</span><span class="monthly-badge">Monthly Avg (3 Mo)</span><span class="days-badge">Days Stock</span>`;
				}

				const rm_button = (label === 'Raw Material')
					? `<button class="btn btn-sm rm-plantwise-btn" id="rm-plantwise-toggle-btn">
							🏭 Plant Wise Report
						</button>`
					: '';

				const $card = $(`
					<div class="detail-panel-card group-${cls}" id="detail-panel-${cls}">
						<div class="detail-panel-title">
							${frappe.utils.escape_html(label)} — Group Wise Detail
							<span class="unit-badge">₹ in Lakhs</span>
							${extra_badge}
							<span class="sort-badge">↓ Sorted by Value</span>
							${rm_button}
						</div>
						<div class="detail-panel-body">
							<div class="detail-loading">Loading…</div>
						</div>
					</div>
				`);

				this.$detail_panels.append($card);
				this.load_detail(label, $card.find('.detail-panel-body'));

				if (label === 'Raw Material') {
					$card.find('#rm-plantwise-toggle-btn').on('click', () => {
						this.toggle_rm_plantwise_report();
					});
				}
			});

		if (this._rm_plantwise_visible && this.active_groups.has('Raw Material') && this.detail_cache['Raw Material']) {
			this._append_rm_plantwise_card(this.detail_cache['Raw Material']);
		}
	}

	load_detail(label, $body) {
		if (this.detail_cache[label]) {
			this._render_by_label(label, $body, this.detail_cache[label]);
			return;
		}

		const method_name = GROUP_METHOD[label];

		if (!method_name) {
			$body.html(`<div class="detail-loading">Detail view for <strong>${frappe.utils.escape_html(label)}</strong> is coming soon.</div>`);
			return;
		}

		frappe.call({
			method:   `${this.method_path}.${method_name}`,
			args:     this.get_query_filters(),
			callback: (r) => {
				if (r.message) {
					this.detail_cache[label] = r.message;
					this._render_by_label(label, $body, r.message);

					if (label === 'Raw Material' && this._rm_plantwise_visible) {
						this._append_rm_plantwise_card(r.message);
					}
				}
			},
		});
	}

	_render_by_label(label, $body, data) {
		if (label === 'Fuel') {
			this.render_fuel_detail($body, data);
		} else if (label === 'Raw Material') {
			this.render_rm_detail($body, data);
		} else if (label === 'General Store') {
			this.render_gs_detail($body, data);
		} else {
			this.render_detail($body, data);
		}
	}

	toggle_rm_plantwise_report() {
		if (this._rm_plantwise_visible) {
			$('#rm-plantwise-report-card').remove();
			this._rm_plantwise_visible = false;
			$('#rm-plantwise-toggle-btn').removeClass('btn-primary').addClass('btn-default');
		} else {
			this._rm_plantwise_visible = true;
			$('#rm-plantwise-toggle-btn').removeClass('btn-default').addClass('btn-primary');
			const data = this.detail_cache['Raw Material'];
			if (data) {
				this._append_rm_plantwise_card(data);
			}
		}
	}

	_append_rm_plantwise_card(data) {
		$('#rm-plantwise-report-card').remove();

		const { plants, groups } = data;

		const plant_totals = {};
		plants.forEach(p => {
			plant_totals[p] = { qty: 0, value_lakh: 0, value_raw: 0, monthly: 0 };
		});

		groups.forEach(g => {
			plants.forEach(p => {
				plant_totals[p].qty        += (g.qty[p]   || 0);
				plant_totals[p].value_lakh += (g.value[p] || 0);
				plant_totals[p].value_raw  += (g.value[p] || 0) * 100000;
				plant_totals[p].monthly    += (g.monthly_consumption && g.monthly_consumption[p]) || 0;
			});
		});

		const head = `
			<tr>
				<th class="row-label-col">Plant</th>
				<th class="pwrm-col pwrm-qty">Stock Qty (Qtl)</th>
				<th class="pwrm-col pwrm-value">Stock Value (Lakh)</th>
				<th class="pwrm-col pwrm-monthly">Avg of 3 Months Consumption</th>
				<th class="pwrm-col pwrm-days">Days Stock</th>
			</tr>
		`;

		let body_rows = '';
		let grand_qty     = 0;
		let grand_value   = 0;
		let grand_monthly = 0;

		plants.forEach(p => {
			const t   = plant_totals[p];
			const qty = Math.round(t.qty * 100) / 100;
			const val = Math.round(t.value_lakh * 100) / 100;
			const mon = Math.round(t.monthly * 100) / 100;
			const days = mon > 0 ? Math.round(qty / (mon / 30) * 10) / 10 : 0;

			grand_qty     += qty;
			grand_value   += val;
			grand_monthly += mon;

			body_rows += `
				<tr class="pwrm-data-row">
					<td class="row-label-col">${frappe.utils.escape_html(p)}</td>
					<td class="num-cell pwrm-col pwrm-qty">${this.format_value(qty)}</td>
					<td class="num-cell pwrm-col pwrm-value">${this.format_value(val)}</td>
					<td class="num-cell pwrm-col pwrm-monthly">${this.format_value(mon)}</td>
					<td class="num-cell pwrm-col pwrm-days">${this.format_days(days)}</td>
				</tr>
			`;
		});

		const grand_days = grand_monthly > 0
			? Math.round(grand_qty / (grand_monthly / 30) * 10) / 10
			: 0;

		const total_row = `
			<tr class="pwrm-total-row">
				<td class="row-label-col">Total (All RMs)</td>
				<td class="num-cell pwrm-col pwrm-qty">${this.format_value(Math.round(grand_qty * 100) / 100)}</td>
				<td class="num-cell pwrm-col pwrm-value">${this.format_value(Math.round(grand_value * 100) / 100)}</td>
				<td class="num-cell pwrm-col pwrm-monthly">${this.format_value(Math.round(grand_monthly * 100) / 100)}</td>
				<td class="num-cell pwrm-col pwrm-days">${this.format_days(grand_days)}</td>
			</tr>
		`;

		const $card = $(`
			<div class="detail-panel-card group-rm pwrm-report-card" id="rm-plantwise-report-card">
				<div class="detail-panel-title">
					Raw Material — Plant Wise Summary
					<span class="unit-badge">₹ in Lakhs</span>
					<span class="qty-badge">Qty in Qtl</span>
					<span class="monthly-badge">Monthly Avg (3 Mo)</span>
					<button class="btn btn-sm btn-danger pwrm-close-btn" id="rm-plantwise-close-btn">✕ Close</button>
				</div>
				<div class="table-responsive">
					<table class="stock-summary-table pwrm-table">
						<thead>${head}</thead>
						<tbody>${body_rows}${total_row}</tbody>
					</table>
				</div>
			</div>
		`);

		$('#detail-panel-rm').after($card);

		$card.find('#rm-plantwise-close-btn').on('click', () => {
			this.toggle_rm_plantwise_report();
		});
	}

	render_detail($body, data) {
		const { plants, groups } = data;

		const head = `
			<tr>
				<th class="row-label-col">Item Group</th>
				<th class="metric-col"></th>
				<th class="uom-col">UOM</th>
				${plants.map((p, idx) => `
					<th class="plant-col plant-col-${idx % 4}">
						${frappe.utils.escape_html(p)}
					</th>
				`).join('')}
				<th class="total-col">Total</th>
			</tr>
		`;

		let body = '';

		groups.forEach((g) => {
			['qty', 'value', 'avg'].forEach((metric, i) => {
				const metric_label =
					metric === 'qty'   ? 'Qty' :
					metric === 'value' ? 'Value (Lakh)' :
					                     'Avg Rate (₹)';

				let row_total = '';

				if (metric === 'qty' || metric === 'value') {
					row_total = Object.values(g[metric] || {}).reduce((s, v) => s + (v || 0), 0);
				} else if (metric === 'avg') {
					const avg_vals = Object.values(g.avg || {}).filter(v => v);
					row_total = avg_vals.length ? avg_vals.reduce((s, v) => s + v, 0) / avg_vals.length : 0;
				}

				body += `<tr>`;

				if (i === 0) {
					body += `<td class="row-label-col" rowspan="3">${frappe.utils.escape_html(g.label)}</td>`;
				}

				body += `<td class="metric-col">${metric_label}</td>`;

				if (i === 0) {
					body += `<td class="uom-col" rowspan="3">${frappe.utils.escape_html(g.uom || '')}</td>`;
				}

				plants.forEach((p, idx) => {
					body += `<td class="num-cell plant-col plant-col-${idx % 4}">${this.format_value(g[metric][p])}</td>`;
				});

				body += `<td class="num-cell total-col">${this.format_value(row_total)}</td>`;
				body += `</tr>`;
			});
		});

		$body.html(`
			<div class="table-responsive">
				<table class="stock-summary-table group-detail-table">
					<thead>${head}</thead>
					<tbody>${body}</tbody>
				</table>
			</div>
		`);
	}

	render_fuel_detail($body, data) {
		const { plants, groups } = data;

		const head_row1 = `
			<tr class="fuel-header-row1">
				<th class="row-label-col fuel-corner-header" rowspan="2">Fuel Detail</th>
				${plants.map((p, idx) => `
					<th colspan="3" class="plant-group-header plant-col-${idx % 4}">
						${frappe.utils.escape_html(p)}
					</th>
				`).join('')}
				<th colspan="3" class="plant-group-header total-col">Total</th>
			</tr>
		`;

		const metric_trio = (extra_class) => `
			<th class="metric-sub-col ${extra_class}">Qty (Qtl)</th>
			<th class="metric-sub-col ${extra_class}">Value (Lakh)</th>
			<th class="metric-sub-col last-sub-col ${extra_class}">Avg (₹/Qtl)</th>
		`;

		const head_row2 = `
			<tr class="fuel-header-row2">
				${plants.map((p, idx) => metric_trio(`plant-col-${idx % 4}`)).join('')}
				${metric_trio('total-col')}
			</tr>
		`;

		let body = '';

		groups.forEach((g) => {
			const plant_cells = plants.map((p, idx) => {
				const qty   = g.qty[p]   || 0;
				const value = g.value[p] || 0;
				const avg   = g.avg[p]   || 0;
				return `
					<td class="num-cell plant-col plant-col-${idx % 4}">${this.format_value(qty)}</td>
					<td class="num-cell plant-col plant-col-${idx % 4}">${this.format_value(value)}</td>
					<td class="num-cell plant-col plant-col-${idx % 4} last-sub">${this.format_value(avg)}</td>
				`;
			}).join('');

			body += `
				<tr>
					<td class="row-label-col">${frappe.utils.escape_html(g.label)}</td>
					${plant_cells}
					<td class="num-cell total-col">${this.format_value(g.total_qty)}</td>
					<td class="num-cell total-col">${this.format_value(g.total_value)}</td>
					<td class="num-cell total-col">${this.format_value(g.total_avg)}</td>
				</tr>
			`;
		});

		$body.html(`
			<div class="table-responsive">
				<table class="stock-summary-table group-detail-table fuel-flat-table">
					<thead>${head_row1}${head_row2}</thead>
					<tbody>${body}</tbody>
				</table>
			</div>
		`);
	}

	render_rm_detail($body, data) {
		const { plants, groups } = data;
		const COLS_PER_PLANT = 5;
		const TOTAL_COLS     = 5;

		const head_row1 = `
			<tr class="fuel-header-row1">
				<th class="row-label-col rm-corner-header" rowspan="2">Raw Material Detail</th>
				${plants.map((p, idx) => `
					<th colspan="${COLS_PER_PLANT}" class="plant-group-header plant-col-${idx % 4}">
						${frappe.utils.escape_html(p)}
					</th>
				`).join('')}
				<th colspan="${TOTAL_COLS}" class="plant-group-header total-col">Total</th>
			</tr>
		`;

		const metric_quintet = (extra_class) => `
			<th class="metric-sub-col ${extra_class}">Qty (Qtl)</th>
			<th class="metric-sub-col ${extra_class}">Value (Lakh)</th>
			<th class="metric-sub-col ${extra_class}">Avg (₹/Qtl)</th>
			<th class="metric-sub-col ${extra_class}">Monthly Consumption(Avg. of Last 3 Months)</th>
			<th class="metric-sub-col last-sub-col ${extra_class}">Days Stock</th>
		`;

		const head_row2 = `
			<tr class="fuel-header-row2">
				${plants.map((p, idx) => metric_quintet(`plant-col-${idx % 4}`)).join('')}
				${metric_quintet('total-col')}
			</tr>
		`;

		let body = '';

		groups.forEach((g) => {
			const plant_cells = plants.map((p, idx) => {
				const qty     = g.qty[p]                  || 0;
				const value   = g.value[p]                || 0;
				const avg     = g.avg[p]                  || 0;
				const monthly = (g.monthly_consumption && g.monthly_consumption[p]) || 0;
				const days    = (g.days_stock && g.days_stock[p])                   || 0;

				const cls = `plant-col plant-col-${idx % 4}`;
				return `
					<td class="num-cell ${cls}">${this.format_value(qty)}</td>
					<td class="num-cell ${cls}">${this.format_value(value)}</td>
					<td class="num-cell ${cls}">${this.format_value(avg)}</td>
					<td class="num-cell ${cls}">${this.format_value(monthly)}</td>
					<td class="num-cell ${cls} last-sub">${this.format_days(days)}</td>
				`;
			}).join('');

			body += `
				<tr>
					<td class="row-label-col">${frappe.utils.escape_html(g.label)}</td>
					${plant_cells}
					<td class="num-cell total-col">${this.format_value(g.total_qty)}</td>
					<td class="num-cell total-col">${this.format_value(g.total_value)}</td>
					<td class="num-cell total-col">${this.format_value(g.total_avg)}</td>
					<td class="num-cell total-col">${this.format_value(g.total_monthly)}</td>
					<td class="num-cell total-col">${this.format_days(g.total_days)}</td>
				</tr>
			`;
		});

		$body.html(`
			<div class="table-responsive">
				<table class="stock-summary-table group-detail-table rm-flat-table">
					<thead>${head_row1}${head_row2}</thead>
					<tbody>${body}</tbody>
				</table>
			</div>
		`);
	}

	render_gs_detail($body, data) {
		const { plants, groups } = data;

		const head = `
			<tr>
				<th class="row-label-col gs-corner-header">General Store Detail</th>
				${plants.map((p, idx) => `
					<th class="plant-col plant-col-${idx % 4}">
						${frappe.utils.escape_html(p)}
					</th>
				`).join('')}
				<th class="total-col">Total</th>
			</tr>
		`;

		let body = '';

		const grand = {};
		plants.forEach(p => { grand[p] = 0; });

		groups.forEach((g) => {
			const plant_cells = plants.map((p, idx) => {
				const value = g.value[p] || 0;
				grand[p] += value;
				const cls = `plant-col plant-col-${idx % 4}`;
				return `<td class="num-cell ${cls}">${this.format_value(value)}</td>`;
			}).join('');

			const is_pesticide = g.label === 'Pesticides';
			const row_cls = is_pesticide ? 'gs-pesticide-row' : '';

			body += `
				<tr class="${row_cls}">
					<td class="row-label-col">
						${is_pesticide ? '<span class="pesticide-warn-icon">⚠</span>' : ''}${frappe.utils.escape_html(g.label)}
					</td>
					${plant_cells}
					<td class="num-cell total-col">${this.format_value(g.total_value)}</td>
				</tr>
			`;
		});

		const overall = Object.values(grand).reduce((s, v) => s + v, 0);
		body += `
			<tr class="gs-grand-total-row">
				<td class="row-label-col">Total</td>
				${plants.map((p, idx) => `<td class="num-cell plant-col plant-col-${idx % 4}">${this.format_value(grand[p])}</td>`).join('')}
				<td class="num-cell total-col">${this.format_value(overall)}</td>
			</tr>
		`;

		$body.html(`
			<div class="table-responsive">
				<table class="stock-summary-table group-detail-table gs-flat-table">
					<thead>${head}</thead>
					<tbody>${body}</tbody>
				</table>
			</div>
		`);
	}

	format_value(v) {
		if (v === null || v === undefined || v === '') return '-';
		const n = parseFloat(v);
		if (isNaN(n) || n === 0) return '-';
		const precision = (Math.abs(n) < 0.1) ? 3 : 2;
		return frappe.format(n, { fieldtype: 'Float', precision: precision });
	}

	format_days(v) {
		if (!v || v === 0) return '-';
		const d = Math.round(v);
		let cls = 'days-badge-green';
		if (d < 7)  cls = 'days-badge-red';
		else if (d <= 30) cls = 'days-badge-amber';
		return `<span class="days-pill ${cls}">${d}D</span>`;
	}

	inject_styles() {
		if (document.getElementById('stock-summary-styles')) return;

		$(`<style id="stock-summary-styles">

		.stock-summary-wrapper {
			padding: 10px 0 30px;
		}

		.stock-summary-card,
		.detail-panel-card {
			background: #fff;
			border: 2px solid #d5dde5;
			border-radius: 14px;
			padding: 18px;
			box-shadow: 0 3px 10px rgba(31,39,46,.06);
			margin-bottom: 22px;
			overflow-x: auto;
		}

		.stock-summary-card-title,
		.detail-panel-title {
			font-size: 17px;
			font-weight: 700;
			margin-bottom: 14px;
			color: #24313b;
			display: flex;
			align-items: center;
			gap: 10px;
			flex-wrap: wrap;
		}

		.unit-badge,
		.sort-badge {
			font-size: 12px;
			padding: 3px 10px;
			border-radius: 30px;
			font-weight: 600;
		}

		.unit-badge {
			background: #e8f1fb;
			color: #2962a8;
			border: 1px solid #cfe1f6;
		}

		.sort-badge {
			background: #fdf5dc;
			color: #75621a;
			border: 1px solid #eadfa6;
			margin-left: auto;
		}

		.qty-badge {
			font-size: 12px;
			padding: 3px 10px;
			border-radius: 30px;
			font-weight: 600;
			background: #e6f7ee;
			color: #1a6e3c;
			border: 1px solid #a8dfc0;
		}

		.avg-badge {
			font-size: 12px;
			padding: 3px 10px;
			border-radius: 30px;
			font-weight: 600;
			background: #fff4e0;
			color: #7a4f00;
			border: 1px solid #f0d090;
		}

		.monthly-badge {
			font-size: 12px;
			padding: 3px 10px;
			border-radius: 30px;
			font-weight: 600;
			background: #f0e8ff;
			color: #5a2fa0;
			border: 1px solid #cdb4f0;
		}

		.days-badge {
			font-size: 12px;
			padding: 3px 10px;
			border-radius: 30px;
			font-weight: 600;
			background: #fff0f0;
			color: #a02020;
			border: 1px solid #f0b4b4;
		}

		.days-pill {
			display: inline-block;
			padding: 2px 8px;
			border-radius: 20px;
			font-size: 12px;
			font-weight: 700;
			letter-spacing: 0.3px;
		}

		.days-badge-red   { background: #fde8e8; color: #b91c1c; border: 1px solid #fca5a5; }
		.days-badge-amber { background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; }
		.days-badge-green { background: #d1fae5; color: #065f46; border: 1px solid #6ee7b7; }

		.stock-summary-table {
			width: 100%;
			border-collapse: separate;
			border-spacing: 0;
			font-size: 15px;
			border: 2px solid #aab8c3;
			border-radius: 10px;
			overflow: visible;
		}

		.table-responsive {
			overflow-x: auto;
			-webkit-overflow-scrolling: touch;
			border-radius: 10px;
			border: 2px solid #aab8c3;
		}

		.table-responsive .stock-summary-table {
			border: none;
			border-radius: 0;
		}

		.stock-summary-table th,
		.stock-summary-table td {
			padding: 11px 16px;
			border-right: 1px solid #d0dbe4;
			border-bottom: 1px solid #dde5ec;
			text-align: right;
			white-space: nowrap;
		}

		.stock-summary-table th:last-child,
		.stock-summary-table td:last-child {
			border-right: none;
		}

		.stock-summary-table th {
			background: #e8eef4;
			color: #36474f;
			font-weight: 700;
			border-bottom: 2px solid #aab8c3;
		}

		.row-label-col {
			text-align: left !important;
			min-width: 200px;
			font-weight: 700;
			color: #1f2b34;
			background: #f5f7fa !important;
			border-right: 3px solid #8fa8bb !important;
			position: sticky;
			left: 0;
			z-index: 2;
		}

		.metric-col {
			text-align: center !important;
			width: 80px;
			color: #72818c;
			font-weight: 600;
			background: #f9fbfc !important;
			border-right: 2px solid #c5d2db !important;
		}

		.uom-col {
			text-align: center !important;
			font-weight: 600;
			color: #74838f;
			border-right: 3px solid #8fa8bb !important;
			background: #f5f7fa !important;
		}

		.num-cell {
			font-variant-numeric: tabular-nums;
			font-weight: 600;
			color: #2d3942;
		}

		.plant-col-0 { background-color: #f0f7ff; }
		.plant-col-1 { background-color: #f5f0ff; }
		.plant-col-2 { background-color: #f0fff5; }
		.plant-col-3 { background-color: #fff8f0; }

		th.plant-col-0 { background-color: #ddeeff !important; border-left: 3px solid #6aace8 !important; border-right: 3px solid #6aace8 !important; }
		th.plant-col-1 { background-color: #ebe0ff !important; border-left: 3px solid #a07de0 !important; border-right: 3px solid #a07de0 !important; }
		th.plant-col-2 { background-color: #d8f5e4 !important; border-left: 3px solid #5dc483 !important; border-right: 3px solid #5dc483 !important; }
		th.plant-col-3 { background-color: #ffebd9 !important; border-left: 3px solid #e09055 !important; border-right: 3px solid #e09055 !important; }

		td.plant-col-0 { border-left: 3px solid #b3d4f0 !important; border-right: 1px solid #c8dff0 !important; }
		td.plant-col-1 { border-left: 3px solid #c9b0f0 !important; border-right: 1px solid #d8c8f0 !important; }
		td.plant-col-2 { border-left: 3px solid #9ed8b8 !important; border-right: 1px solid #bce6cd !important; }
		td.plant-col-3 { border-left: 3px solid #e8bb95 !important; border-right: 1px solid #f0cfb0 !important; }

		.total-col {
			background: #e4ecf4 !important;
			font-weight: 800 !important;
			color: #11263a !important;
			border-left: 4px solid #6b8fa8 !important;
		}

		th.total-col {
			background: #d0dfe9 !important;
		}

		.summary-row {
			cursor: pointer;
			transition: background .15s;
		}

		.summary-row:hover td {
			filter: brightness(0.96);
		}

		.summary-row-active td {
			outline: none;
			border-top: 2px solid #2b7ad4 !important;
			border-bottom: 2px solid #2b7ad4 !important;
		}

		.summary-row-active .row-label-col {
			color: #2367b1;
		}

		.summary-total-row {
			background: #d8e5ef;
			font-weight: 800;
		}

		.summary-total-row td {
			border-top: 3px solid #7a9bb5 !important;
		}

		.group-dot {
			width: 10px;
			height: 10px;
			border-radius: 50%;
			display: inline-block;
			margin-right: 10px;
		}

		.group-fg   .group-dot { background: #3b82f6; }
		.group-fuel .group-dot { background: #f59e0b; }
		.group-rm   .group-dot { background: #22c55e; }
		.group-gs   .group-dot { background: #a855f7; }

		.detail-panel-card { border-left: 6px solid #c8d1d9; }
		.group-fg.detail-panel-card   { border-left-color: #3b82f6; }
		.group-fuel.detail-panel-card { border-left-color: #f59e0b; }
		.group-rm.detail-panel-card   { border-left-color: #22c55e; }
		.group-gs.detail-panel-card   { border-left-color: #a855f7; }

		.detail-loading { padding: 16px; color: #7b8a95; }

		.group-detail-table tbody tr:nth-child(3n) td {
			border-bottom: 3px solid #9ab0bf;
		}

		.plant-group-header {
			text-align: center !important;
			font-weight: 800;
			border-bottom: 3px solid #9cb0bf;
		}

		.fuel-corner-header,
		.rm-corner-header,
		.gs-corner-header {
			background: #edf3f8 !important;
			font-weight: 800;
			vertical-align: middle !important;
		}

		.metric-sub-col {
			font-weight: 700;
			min-width: 80px;
			border-right: 1px solid #c3cfd8 !important;
		}

		.last-sub-col {
			border-right: 3px solid #9cb0bf !important;
		}

		td.last-sub {
			border-right: 3px solid #b8c8d4 !important;
		}

		.fuel-flat-table tbody tr:hover td,
		.rm-flat-table tbody tr:hover td,
		.gs-flat-table tbody tr:hover td {
			filter: brightness(0.96);
		}

		.fuel-flat-table tbody tr:nth-child(even) td,
		.rm-flat-table tbody tr:nth-child(even) td,
		.gs-flat-table tbody tr:nth-child(even) td {
			filter: brightness(0.985);
		}

		.rm-flat-table .metric-sub-col:nth-child(4),
		.rm-flat-table .metric-sub-col:nth-child(5) {
			min-width: 110px;
		}

		.gs-flat-table .gs-corner-header {
			border-left: 3px solid #a855f7 !important;
		}

		.gs-pesticide-row td {
			background-color: #fff3e0 !important;
			border-top: 2px solid #fb8c00 !important;
			border-bottom: 2px solid #fb8c00 !important;
		}

		.gs-pesticide-row .row-label-col {
			background-color: #ffe0b2 !important;
			color: #d84315 !important;
			font-weight: 800 !important;
		}

		.gs-pesticide-row .total-col {
			background-color: #ffe0b2 !important;
			color: #d84315 !important;
		}

		.gs-pesticide-row:hover td {
			filter: brightness(0.97);
		}

		.pesticide-warn-icon {
			margin-right: 6px;
		}

		.rm-plantwise-btn {
			margin-left: auto;
			background: #e8f5e9;
			color: #1b5e20;
			border: 1.5px solid #66bb6a;
			border-radius: 20px;
			font-size: 13px;
			font-weight: 700;
			padding: 4px 14px;
			cursor: pointer;
			transition: background 0.15s, color 0.15s;
		}

		.rm-plantwise-btn:hover,
		.rm-plantwise-btn.btn-primary {
			background: #22c55e;
			color: #fff;
			border-color: #16a34a;
		}

		.pwrm-report-card {
			border-left-color: #22c55e !important;
			border-left-width: 6px !important;
			background: #f6fef9 !important;
		}

		.pwrm-close-btn {
			margin-left: auto;
			font-size: 12px;
			padding: 3px 12px;
			border-radius: 20px;
			font-weight: 700;
		}

		.pwrm-col {
			min-width: 130px;
			text-align: right !important;
		}

		.pwrm-qty     { background-color: #f0fff5 !important; border-left: 3px solid #9ed8b8 !important; }
		.pwrm-value   { background-color: #f0f7ff !important; border-left: 3px solid #b3d4f0 !important; }
		.pwrm-monthly { background-color: #f5f0ff !important; border-left: 3px solid #c9b0f0 !important; min-width: 180px !important; }
		.pwrm-days    { background-color: #fff8f0 !important; border-left: 3px solid #e8bb95 !important; }

		th.pwrm-qty     { background-color: #d8f5e4 !important; }
		th.pwrm-value   { background-color: #ddeeff !important; }
		th.pwrm-monthly { background-color: #ebe0ff !important; }
		th.pwrm-days    { background-color: #ffebd9 !important; }

		.pwrm-table tbody .pwrm-data-row:hover td {
			filter: brightness(0.96);
		}

		.pwrm-table tbody .pwrm-data-row:nth-child(even) td {
			filter: brightness(0.985);
		}

		.pwrm-total-row td {
			background: #d8eed8 !important;
			font-weight: 800 !important;
			color: #0a3d1a !important;
			border-top: 3px solid #4caf50 !important;
		}

		.pwrm-total-row .row-label-col {
			background: #c8e6c9 !important;
			color: #1b5e20 !important;
		}

		</style>`).appendTo('head');
	}
}