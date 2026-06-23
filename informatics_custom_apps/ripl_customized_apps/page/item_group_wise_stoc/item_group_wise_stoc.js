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

// Groups that support drilling further down into an Item Code + Item Name
// wise breakup (via a popup dialog) when a row in their detail table is
// clicked. Maps group label -> whitelisted method name on the backend.
const ITEM_DETAIL_METHOD = {
	'Finished Goods': 'get_finished_goods_item_detail',
	'General Store':  'get_general_store_item_detail',
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

		this.inv_health_field = this.page.add_field({
			label:     'Show Inventory Health',
			fieldtype: 'Check',
			fieldname: 'show_inventory_health',
			change:    () => this.render_active_panels(),
		});

		this.page.set_secondary_action('Refresh', () => this.refresh(), 'refresh');
	}

	_get_show_inv_health() {
		return this.inv_health_field ? !!this.inv_health_field.get_value() : false;
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

		const show_ih    = this._get_show_inv_health();
		const active_arr = GROUP_ORDER.filter((g) => this.active_groups.has(g));

		// ── No group active: optionally show overall Inventory Health ─────────
		if (active_arr.length === 0) {
			if (show_ih) {
				const $ihc = $('<div class="ih-outer-container"></div>').appendTo(this.$detail_panels);
				this.load_and_render_inv_health($ihc, null);
			}
			return;
		}

		// ── One group active ──────────────────────────────────────────────────
		active_arr.forEach((label) => {
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

			const click_hint = ITEM_DETAIL_METHOD[label]
				? `<span class="click-hint-badge">Click a row for item-wise detail</span>`
				: '';

			const $card = $(`
				<div class="detail-panel-card group-${cls}" id="detail-panel-${cls}">
					<div class="detail-panel-title">
						${frappe.utils.escape_html(label)} — Group Wise Detail
						<span class="unit-badge">₹ in Lakhs</span>
						${extra_badge}
						${click_hint}
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

			// Inventory Health panel for this group (appended after the group card;
			// RM plant-wise card will be inserted between via .after() so the order
			// becomes: [group card] → [RM plantwise card] → [IH card]).
			if (show_ih) {
				const $ihc = $('<div class="ih-outer-container"></div>').appendTo(this.$detail_panels);
				this.load_and_render_inv_health($ihc, label);
			}
		});

		if (this._rm_plantwise_visible && this.active_groups.has('Raw Material') && this.detail_cache['Raw Material']) {
			this._append_rm_plantwise_card(this.detail_cache['Raw Material']);
		}
	}

	// ── Inventory Health ────────────────────────────────────────────────────
	load_and_render_inv_health($container, item_group) {
		const cache_key = 'inv_health_' + (item_group || '__all__');

		$container.html(`
			<div class="detail-panel-card ih-panel-card ih-loading-placeholder">
				<div class="detail-loading">⏳ Loading Inventory Health…</div>
			</div>
		`);

		if (this.detail_cache[cache_key]) {
			this.render_inv_health_card($container, this.detail_cache[cache_key], item_group);
			return;
		}

		frappe.call({
			method: `${this.method_path}.get_inventory_health`,
			args:   { ...this.get_query_filters(), item_group: item_group || '' },
			callback: (r) => {
				if (r.message) {
					this.detail_cache[cache_key] = r.message;
					this.render_inv_health_card($container, r.message, item_group);
				} else {
					$container.html(`
						<div class="detail-panel-card ih-panel-card">
							<div class="detail-loading">No inventory health data found.</div>
						</div>
					`);
				}
			},
			error: () => {
				$container.html(`
					<div class="detail-panel-card ih-panel-card">
						<div class="detail-loading">Failed to load inventory health.</div>
					</div>
				`);
			},
		});
	}

	render_inv_health_card($container, data, item_group) {
		const { rows } = data;

		const title = item_group
			? `${item_group} — Inventory Health`
			: 'Inventory Health — All Groups';

		const head = `
			<tr>
				<th class="row-label-col ih-corner-header">Plant</th>
				<th class="ih-col ih-total-inv">Total Inventory Value</th>
				<th class="ih-col ih-slow">Slow Moving<br><small>90–180 days</small></th>
				<th class="ih-col ih-nonmoving">Non Moving<br><small>180–365 days</small></th>
				<th class="ih-col ih-dead">Dead Stock<br><small>&gt;365 days</small></th>
			</tr>
		`;

		let body = '';
		let grand_total     = 0;
		let grand_slow      = 0;
		let grand_nonmoving = 0;
		let grand_dead      = 0;

		(rows || []).forEach((r) => {
			grand_total     += r.total_value  || 0;
			grand_slow      += r.slow_moving  || 0;
			grand_nonmoving += r.non_moving   || 0;
			grand_dead      += r.dead_stock   || 0;

			// ── Store raw numeric values as data-* attributes so the click
			//    handler can pass them directly into the drilldown dialog.
			//    This ensures the stat cards in the dialog always match the
			//    values shown in this summary table row exactly.
			body += `
				<tr class="ih-data-row"
				    data-plant="${frappe.utils.escape_html(r.plant)}"
				    data-total="${r.total_value  || 0}"
				    data-slow="${r.slow_moving   || 0}"
				    data-nonmoving="${r.non_moving || 0}"
				    data-dead="${r.dead_stock    || 0}">
					<td class="row-label-col">
						${frappe.utils.escape_html(r.plant)}
						<span class="click-chevron">›</span>
					</td>
					<td class="num-cell ih-col ih-total-inv">${this.format_value(r.total_value)}</td>
					<td class="num-cell ih-col ih-slow">${this.format_value(r.slow_moving)}</td>
					<td class="num-cell ih-col ih-nonmoving">${this.format_value(r.non_moving)}</td>
					<td class="num-cell ih-col ih-dead">${this.format_value(r.dead_stock)}</td>
				</tr>
			`;
		});

		body += `
			<tr class="ih-total-row">
				<td class="row-label-col">Total</td>
				<td class="num-cell ih-col ih-total-inv">${this.format_value(Math.round(grand_total     * 100) / 100)}</td>
				<td class="num-cell ih-col ih-slow">${this.format_value(Math.round(grand_slow       * 100) / 100)}</td>
				<td class="num-cell ih-col ih-nonmoving">${this.format_value(Math.round(grand_nonmoving  * 100) / 100)}</td>
				<td class="num-cell ih-col ih-dead">${this.format_value(Math.round(grand_dead       * 100) / 100)}</td>
			</tr>
		`;

		$container.html(`
			<div class="detail-panel-card ih-panel-card">
				<div class="detail-panel-title">
					📊 ${frappe.utils.escape_html(title)}
					<span class="unit-badge">₹ in Lakhs</span>
					<span class="click-hint-badge">Click a plant for item-wise detail</span>
					<span class="ih-legend-slow">● Slow 90–180d</span>
					<span class="ih-legend-nonmoving">● Non-Moving 180–365d</span>
					<span class="ih-legend-dead">● Dead &gt;365d</span>
				</div>
				<div class="table-responsive">
					<table class="stock-summary-table ih-table">
						<thead>${head}</thead>
						<tbody>${body}</tbody>
					</table>
				</div>
			</div>
		`);

		// ── Read the raw values stored on the row and pass them into the
		//    dialog so its stat cards are guaranteed to match this table.
		$container.find('tr.ih-data-row').on('click', (ev) => {
			const $row     = $(ev.currentTarget);
			const plant_name = $row.data('plant');
			const known = {
				total_value: parseFloat($row.data('total'))      || 0,
				slow:        parseFloat($row.data('slow'))       || 0,
				non_moving:  parseFloat($row.data('nonmoving'))  || 0,
				dead:        parseFloat($row.data('dead'))       || 0,
			};
			this.open_inv_health_item_dialog(plant_name, item_group, known);
		});
	}

	// ── Inventory Health item-wise drilldown popup ──────────────────────────
	// `known` carries the exact totals shown in the parent IH summary row so
	// the four stat cards in the dialog always match that row, regardless of
	// any difference in how the backend aggregates the item-level detail.
	open_inv_health_item_dialog(plant_name, item_group, known = null) {
		if (!plant_name) return;

		const dialog = new frappe.ui.Dialog({
			title: `${plant_name} — Inventory Ageing Detail${item_group ? ' (' + item_group + ')' : ''}`,
			size: 'extra-large',
			fields: [{ fieldtype: 'HTML', fieldname: 'ih_item_detail_html' }],
		});

		dialog.$wrapper.addClass('stock-summary-item-dialog');
		dialog.fields_dict.ih_item_detail_html.$wrapper.html(`<div class="detail-loading">Loading…</div>`);
		dialog.show();

		frappe.call({
			method:   `${this.method_path}.get_inventory_health_item_detail`,
			args:     { ...this.get_query_filters(), item_group: item_group || '', target_plant: plant_name },
			callback: (r) => {
				if (!r.message || !r.message.items || !r.message.items.length) {
					dialog.fields_dict.ih_item_detail_html.$wrapper.html(
						`<div class="detail-loading">No item-wise data found for "${frappe.utils.escape_html(plant_name)}".</div>`
					);
					return;
				}

				// Override the backend-computed totals with the values from the
				// parent IH summary row so the dialog stat cards match exactly.
				if (known) {
					r.message.total_value   = known.total_value;
					r.message.bucket_totals = r.message.bucket_totals || {};
					r.message.bucket_totals.slow       = known.slow;
					r.message.bucket_totals.non_moving = known.non_moving;
					r.message.bucket_totals.dead       = known.dead;
				}

				dialog.fields_dict.ih_item_detail_html.$wrapper.html(this.build_ih_item_table_html(r.message));
			},
			error: () => {
				dialog.fields_dict.ih_item_detail_html.$wrapper.html(
					`<div class="detail-loading">Failed to load inventory health detail.</div>`
				);
			},
		});
	}

	build_ih_item_table_html(data) {
		const { items, bucket_totals, total_value } = data;

		const bucket_meta = {
			fresh:      { label: 'Moving (<90d)', cls: 'days-badge-green',    row_cls: '' },
			slow:       { label: 'Slow Moving',   cls: 'days-badge-amber',   row_cls: 'ih-row-slow' },
			non_moving: { label: 'Non Moving',    cls: 'ih-badge-nonmoving', row_cls: 'ih-row-nonmoving' },
			dead:       { label: 'Dead Stock',    cls: 'days-badge-red',     row_cls: 'ih-row-dead' },
		};

		const item_count = items.length;

		// Order by days since last movement descending — longest-idle first.
		const sorted_items = [...items].sort((a, b) => {
			const da = (a.days_since_movement === null || a.days_since_movement === undefined) ? Infinity : a.days_since_movement;
			const db = (b.days_since_movement === null || b.days_since_movement === undefined) ? Infinity : b.days_since_movement;
			return db - da;
		});

		const summary = `
			<div class="ih-dialog-summary">
				<div class="ih-stat-card ih-stat-total">
					<div class="ih-stat-label">Total Inventory · ${item_count} item${item_count === 1 ? '' : 's'}</div>
					<div class="ih-stat-value"><span class="ih-stat-currency">₹</span>${this.format_value(total_value)}<span class="ih-stat-unit">L</span></div>
				</div>
				<div class="ih-stat-card ih-stat-slow">
					<div class="ih-stat-label">Slow Moving</div>
					<div class="ih-stat-value"><span class="ih-stat-currency">₹</span>${this.format_value(bucket_totals.slow)}<span class="ih-stat-unit">L</span></div>
				</div>
				<div class="ih-stat-card ih-stat-nonmoving">
					<div class="ih-stat-label">Non-Moving</div>
					<div class="ih-stat-value"><span class="ih-stat-currency">₹</span>${this.format_value(bucket_totals.non_moving)}<span class="ih-stat-unit">L</span></div>
				</div>
				<div class="ih-stat-card ih-stat-dead">
					<div class="ih-stat-label">Dead Stock</div>
					<div class="ih-stat-value"><span class="ih-stat-currency">₹</span>${this.format_value(bucket_totals.dead)}<span class="ih-stat-unit">L</span></div>
				</div>
			</div>
		`;

		const head = `
			<tr>
				<th class="row-label-col gs-corner-header">Item</th>
				<th class="ih-item-col">Qty</th>
				<th class="ih-item-col">UOM</th>
				<th class="ih-item-col">Value (Lakh)</th>
				<th class="ih-item-col ih-item-col-wide">Last Movement</th>
				<th class="ih-item-col ih-item-col-wide">Status</th>
			</tr>
		`;

		let body = '';
		sorted_items.forEach((it) => {
			const meta = bucket_meta[it.bucket] || bucket_meta.fresh;
			const days_label = (it.days_since_movement === null || it.days_since_movement === undefined)
				? 'No movement on record'
				: `${it.days_since_movement} days ago`;

			body += `
				<tr class="ih-item-row ${meta.row_cls}">
					<td class="row-label-col">
						<strong>${frappe.utils.escape_html(it.item_name || it.item_code)}</strong>
						<div class="item-name-sub">${frappe.utils.escape_html(it.item_code)}</div>
					</td>
					<td class="num-cell ih-item-col">${this.format_value(it.qty)}</td>
					<td class="num-cell ih-item-col">${frappe.utils.escape_html(it.uom || '-')}</td>
					<td class="num-cell ih-item-col">${this.format_value(it.value)}</td>
					<td class="num-cell ih-item-col ih-item-col-wide">${days_label}</td>
					<td class="num-cell ih-item-col ih-item-col-wide"><span class="days-pill ${meta.cls}">${meta.label}</span></td>
				</tr>
			`;
		});

		body += `
			<tr class="gs-grand-total-row">
				<td class="row-label-col">Total (${item_count} Item${item_count === 1 ? '' : 's'})</td>
				<td class="num-cell ih-item-col"></td>
				<td class="num-cell ih-item-col"></td>
				<td class="num-cell ih-item-col">${this.format_value(total_value)}</td>
				<td class="num-cell ih-item-col ih-item-col-wide"></td>
				<td class="num-cell ih-item-col ih-item-col-wide"></td>
			</tr>
		`;

		return `
			<div class="ih-dialog-content">
				${summary}
				<div class="table-responsive">
					<table class="stock-summary-table group-detail-table item-detail-table ih-item-table">
						<thead>${head}</thead>
						<tbody>${body}</tbody>
					</table>
				</div>
			</div>
		`;
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
			this.render_gs_detail($body, data, label);
		} else {
			this.render_detail($body, data, label);
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
				<th class="pwrm-col pwrm-monthly">Monthly Avg<br>(Last 3 Mo)</th>
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

	render_detail($body, data, group_label) {
		const { plants, groups } = data;
		const clickable = !!ITEM_DETAIL_METHOD[group_label];

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

				body += `<tr${clickable ? ` class="detail-item-row" data-sublabel="${frappe.utils.escape_html(g.label)}"` : ''}>`;

				if (i === 0) {
					body += `<td class="row-label-col" rowspan="3">
						${frappe.utils.escape_html(g.label)}
						${clickable ? '<span class="click-chevron">›</span>' : ''}
					</td>`;
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

		if (clickable) {
			$body.find('tr.detail-item-row').on('click', (ev) => {
				const sub_label = $(ev.currentTarget).data('sublabel');
				this.open_item_detail_dialog(group_label, sub_label);
			});
		}
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
			<th class="metric-sub-col metric-sub-col-monthly ${extra_class}">Monthly Avg<br>(Last 3 Mo)</th>
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

	render_gs_detail($body, data, group_label) {
		const { plants, groups } = data;
		const clickable = !!ITEM_DETAIL_METHOD[group_label];

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
			const row_cls = [
				is_pesticide ? 'gs-pesticide-row' : '',
				clickable ? 'gs-detail-row' : '',
			].filter(Boolean).join(' ');

			body += `
				<tr class="${row_cls}"${clickable ? ` data-sublabel="${frappe.utils.escape_html(g.label)}"` : ''}>
					<td class="row-label-col">
						${is_pesticide ? '<span class="pesticide-warn-icon">⚠</span>' : ''}${frappe.utils.escape_html(g.label)}
						${clickable ? '<span class="click-chevron">›</span>' : ''}
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

		if (clickable) {
			$body.find('tr.gs-detail-row').on('click', (ev) => {
				const sub_label = $(ev.currentTarget).data('sublabel');
				this.open_item_detail_dialog(group_label, sub_label);
			});
		}
	}

	// ── Item Code + Item Name wise drill-down popup ─────────────────────────
	open_item_detail_dialog(group_label, sub_label) {
		const method_name = ITEM_DETAIL_METHOD[group_label];
		if (!method_name || !sub_label) return;

		const dialog = new frappe.ui.Dialog({
			title: `${sub_label} — Item Wise Detail`,
			size: 'extra-large',
			fields: [{ fieldtype: 'HTML', fieldname: 'item_detail_html' }],
		});

		dialog.$wrapper.addClass('stock-summary-item-dialog');

		dialog.fields_dict.item_detail_html.$wrapper.html(`<div class="detail-loading">Loading…</div>`);
		dialog.show();

		frappe.call({
			method:   `${this.method_path}.${method_name}`,
			args:     { ...this.get_query_filters(), label: sub_label },
			callback: (r) => {
				if (!r.message || !r.message.items || !r.message.items.length) {
					dialog.fields_dict.item_detail_html.$wrapper.html(
						`<div class="detail-loading">No item-wise data found for "${frappe.utils.escape_html(sub_label)}".</div>`
					);
					return;
				}
				const html = (group_label === 'Finished Goods')
					? this.build_fg_item_table_html(r.message)
					: this.build_gs_item_table_html(r.message);
				dialog.fields_dict.item_detail_html.$wrapper.html(html);
			},
			error: () => {
				dialog.fields_dict.item_detail_html.$wrapper.html(
					`<div class="detail-loading">Failed to load item-wise detail.</div>`
				);
			},
		});
	}

	build_fg_item_table_html(data) {
		const { plants, items, total, uom } = data;

		const head_row1 = `
			<tr class="fuel-header-row1">
				<th class="row-label-col fuel-corner-header" rowspan="2">Item</th>
				${plants.map((p, idx) => `
					<th colspan="3" class="plant-group-header plant-col-${idx % 4}">
						${frappe.utils.escape_html(p)}
					</th>
				`).join('')}
				<th colspan="3" class="plant-group-header total-col">Total</th>
			</tr>
		`;

		const metric_trio = (extra_class) => `
			<th class="metric-sub-col ${extra_class}">Qty${uom ? ' (' + frappe.utils.escape_html(uom) + ')' : ''}</th>
			<th class="metric-sub-col ${extra_class}">Value (Lakh)</th>
			<th class="metric-sub-col last-sub-col ${extra_class}">Avg Rate (₹)</th>
		`;

		const head_row2 = `
			<tr class="fuel-header-row2">
				${plants.map((p, idx) => metric_trio(`plant-col-${idx % 4}`)).join('')}
				${metric_trio('total-col')}
			</tr>
		`;

		let body = '';
		items.forEach((it) => {
			const plant_cells = plants.map((p, idx) => {
				const qty   = it.qty[p]   || 0;
				const value = it.value[p] || 0;
				const avg   = it.avg[p]   || 0;
				const cls = `plant-col plant-col-${idx % 4}`;
				return `
					<td class="num-cell ${cls}">${this.format_value(qty)}</td>
					<td class="num-cell ${cls}">${this.format_value(value)}</td>
					<td class="num-cell ${cls} last-sub">${this.format_value(avg)}</td>
				`;
			}).join('');

			body += `
				<tr>
					<td class="row-label-col">
						<strong>${frappe.utils.escape_html(it.item_name || it.item_code)}</strong>
						<div class="item-name-sub">${frappe.utils.escape_html(it.item_code)}</div>
					</td>
					${plant_cells}
					<td class="num-cell total-col">${this.format_value(it.total_qty)}</td>
					<td class="num-cell total-col">${this.format_value(it.total_value)}</td>
					<td class="num-cell total-col">${this.format_value(it.total_avg)}</td>
				</tr>
			`;
		});

		const total_plant_cells = plants.map((p, idx) => {
			const qty   = (total.qty   && total.qty[p])   || 0;
			const value = (total.value && total.value[p]) || 0;
			const avg   = (total.avg   && total.avg[p])   || 0;
			const cls = `plant-col plant-col-${idx % 4}`;
			return `
				<td class="num-cell ${cls}">${this.format_value(qty)}</td>
				<td class="num-cell ${cls}">${this.format_value(value)}</td>
				<td class="num-cell ${cls} last-sub">${this.format_value(avg)}</td>
			`;
		}).join('');

		body += `
			<tr class="gs-grand-total-row">
				<td class="row-label-col">Total (All Items)</td>
				${total_plant_cells}
				<td class="num-cell total-col">${this.format_value(total.total_qty)}</td>
				<td class="num-cell total-col">${this.format_value(total.total_value)}</td>
				<td class="num-cell total-col">${this.format_value(total.total_avg)}</td>
			</tr>
		`;

		return `
			<div class="table-responsive">
				<table class="stock-summary-table group-detail-table fuel-flat-table item-detail-table">
					<thead>${head_row1}${head_row2}</thead>
					<tbody>${body}</tbody>
				</table>
			</div>
		`;
	}

	build_gs_item_table_html(data) {
		const { plants, items, total } = data;

		const head = `
			<tr>
				<th class="row-label-col gs-corner-header">Item</th>
				${plants.map((p, idx) => `
					<th class="plant-col plant-col-${idx % 4}">
						${frappe.utils.escape_html(p)}
					</th>
				`).join('')}
				<th class="total-col">Total</th>
			</tr>
		`;

		let body = '';
		items.forEach((it) => {
			const plant_cells = plants.map((p, idx) => {
				const value = it.value[p] || 0;
				return `<td class="num-cell plant-col plant-col-${idx % 4}">${this.format_value(value)}</td>`;
			}).join('');

			body += `
				<tr>
					<td class="row-label-col">
						<strong>${frappe.utils.escape_html(it.item_name || it.item_code)}</strong>
						<div class="item-name-sub">${frappe.utils.escape_html(it.item_code)}</div>
					</td>
					${plant_cells}
					<td class="num-cell total-col">${this.format_value(it.total_value)}</td>
				</tr>
			`;
		});

		body += `
			<tr class="gs-grand-total-row">
				<td class="row-label-col">Total (All Items)</td>
				${plants.map((p, idx) => `<td class="num-cell plant-col plant-col-${idx % 4}">${this.format_value((total.value && total.value[p]) || 0)}</td>`).join('')}
				<td class="num-cell total-col">${this.format_value(total.total_value)}</td>
			</tr>
		`;

		return `
			<div class="table-responsive">
				<table class="stock-summary-table group-detail-table gs-flat-table item-detail-table">
					<thead>${head}</thead>
					<tbody>${body}</tbody>
				</table>
			</div>
		`;
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

		.click-hint-badge {
			font-size: 12px;
			padding: 3px 10px;
			border-radius: 30px;
			font-weight: 600;
			background: #e6f0ff;
			color: #1d4f9e;
			border: 1px solid #b9d2f5;
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
			transform: translateZ(0);
			-webkit-transform: translateZ(0);
			backface-visibility: hidden;
		}

		.item-name-sub {
			font-size: 12px;
			font-weight: 500;
			color: #697884;
			margin-top: 2px;
			white-space: normal;
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

		.summary-row:hover td:not(.row-label-col) {
			filter: brightness(0.96);
		}

		.summary-row:hover td.row-label-col {
			background: #eef2f6 !important;
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

		.metric-sub-col-monthly {
			min-width: 92px !important;
			max-width: 110px !important;
			white-space: normal !important;
			text-align: center !important;
			line-height: 1.25;
		}

		.last-sub-col {
			border-right: 3px solid #9cb0bf !important;
		}

		td.last-sub {
			border-right: 3px solid #b8c8d4 !important;
		}

		.fuel-flat-table tbody tr:hover td:not(.row-label-col),
		.rm-flat-table tbody tr:hover td:not(.row-label-col),
		.gs-flat-table tbody tr:hover td:not(.row-label-col) {
			filter: brightness(0.96);
		}

		.fuel-flat-table tbody tr:hover td.row-label-col,
		.rm-flat-table tbody tr:hover td.row-label-col,
		.gs-flat-table tbody tr:hover td.row-label-col {
			background: #eef2f6 !important;
		}

		.fuel-flat-table tbody tr:nth-child(even) td:not(.row-label-col),
		.rm-flat-table tbody tr:nth-child(even) td:not(.row-label-col),
		.gs-flat-table tbody tr:nth-child(even) td:not(.row-label-col) {
			filter: brightness(0.985);
		}

		.fuel-flat-table tbody tr:nth-child(even) td.row-label-col,
		.rm-flat-table tbody tr:nth-child(even) td.row-label-col,
		.gs-flat-table tbody tr:nth-child(even) td.row-label-col {
			background: #eef1f4 !important;
		}

		.rm-flat-table .metric-sub-col-monthly {
			min-width: 92px !important;
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

		.gs-pesticide-row:hover td.row-label-col {
			filter: none;
			background-color: #ffd699 !important;
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
		.pwrm-monthly {
			background-color: #f5f0ff !important;
			border-left: 3px solid #c9b0f0 !important;
			min-width: 96px !important;
			max-width: 120px !important;
		}
		.pwrm-days    { background-color: #fff8f0 !important; border-left: 3px solid #e8bb95 !important; }

		th.pwrm-qty     { background-color: #d8f5e4 !important; }
		th.pwrm-value   { background-color: #ddeeff !important; }
		th.pwrm-monthly {
			background-color: #ebe0ff !important;
			white-space: normal !important;
			text-align: center !important;
			line-height: 1.25;
		}
		th.pwrm-days    { background-color: #ffebd9 !important; }

		.pwrm-table tbody .pwrm-data-row:hover td:not(.row-label-col) {
			filter: brightness(0.96);
		}

		.pwrm-table tbody .pwrm-data-row:hover td.row-label-col {
			background: #eef2f6 !important;
		}

		.pwrm-table tbody .pwrm-data-row:nth-child(even) td:not(.row-label-col) {
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

		/* ── Item-wise drill-down (Finished Goods / General Store) ───────── */

		.detail-item-row,
		.gs-detail-row {
			cursor: pointer;
		}

		.detail-item-row:hover td:not(.row-label-col),
		.gs-detail-row:hover td:not(.row-label-col) {
			background-color: rgba(43, 122, 212, 0.08) !important;
			filter: none;
		}

		.detail-item-row:hover td.row-label-col,
		.gs-detail-row:hover td.row-label-col {
			background-color: #e3edf9 !important;
		}

		.click-chevron {
			float: right;
			color: #93a4b0;
			font-weight: 800;
			margin-left: 8px;
		}

		.item-detail-table .row-label-col {
			min-width: 230px;
		}

		/* ── Item-wise drill-down dialog ────────────────────────────────────── */
		.stock-summary-item-dialog .modal-body {
			padding: 0 !important;
			max-height: 80vh !important;
			overflow: auto !important;
		}

		.stock-summary-item-dialog .table-responsive {
			max-height: 78vh !important;
			overflow-y: auto !important;
			overflow-x: auto !important;
			position: relative;
		}

		.stock-summary-item-dialog .item-detail-table thead th {
			position: sticky !important;
			top: 0;
			background: #edf2f7 !important;
			z-index: 20;
		}

		.stock-summary-item-dialog .item-detail-table .row-label-col {
			position: sticky !important;
			left: 0;
			background: #f6f8fb !important;
			z-index: 30;
		}

		.stock-summary-item-dialog .item-detail-table thead .row-label-col {
			top: 0;
			left: 0;
			z-index: 40 !important;
		}

		.stock-summary-item-dialog .modal-dialog {
			width: 96vw !important;
			max-width: 1680px !important;
			margin: 10px auto !important;
		}

		.stock-summary-item-dialog .modal-content {
			height: 92vh !important;
		}

		.stock-summary-item-dialog .modal-body {
			max-height: calc(92vh - 60px) !important;
			overflow: auto !important;
		}

		/* ── Inventory Health table ──────────────────────────────────────────── */

		.ih-panel-card {
			border-left: 6px solid #e11d48 !important;
			background: #fff8f9 !important;
		}

		.ih-corner-header {
			background: #fdf0f3 !important;
			font-weight: 800;
			vertical-align: middle !important;
		}

		.ih-col {
			min-width: 150px;
			text-align: right !important;
		}

		.ih-total-inv {
			background-color: #eff6ff !important;
			border-left: 4px solid #6aace8 !important;
			font-weight: 700 !important;
			color: #1e3a6e !important;
		}

		th.ih-total-inv { background-color: #dbeafe !important; }

		.ih-slow {
			background-color: #fffbeb !important;
			border-left: 3px solid #fcd34d !important;
			color: #78350f !important;
		}

		th.ih-slow { background-color: #fef3c7 !important; }

		.ih-nonmoving {
			background-color: #fff7ed !important;
			border-left: 3px solid #fb923c !important;
			color: #7c2d12 !important;
		}

		th.ih-nonmoving { background-color: #ffedd5 !important; }

		.ih-dead {
			background-color: #fef2f2 !important;
			border-left: 3px solid #f87171 !important;
			color: #7f1d1d !important;
		}

		th.ih-dead { background-color: #fee2e2 !important; }

		.ih-data-row { cursor: pointer; }

		.ih-data-row:hover td:not(.row-label-col) { filter: brightness(0.96); }
		.ih-data-row:hover td.row-label-col { background: #f5e7ea !important; }
		.ih-data-row:nth-child(even) td:not(.row-label-col) { filter: brightness(0.985); }

		.ih-total-row td {
			background: #fce7eb !important;
			font-weight: 800 !important;
			color: #881337 !important;
			border-top: 3px solid #e11d48 !important;
		}

		.ih-total-row .row-label-col {
			background: #fbd5dc !important;
			color: #881337 !important;
		}

		.ih-legend-slow, .ih-legend-nonmoving, .ih-legend-dead {
			font-size: 12px;
			padding: 3px 10px;
			border-radius: 30px;
			font-weight: 600;
		}

		.ih-legend-slow      { background: #fef3c7; color: #78350f; border: 1px solid #fcd34d; }
		.ih-legend-nonmoving { background: #ffedd5; color: #7c2d12; border: 1px solid #fb923c; }
		.ih-legend-dead      { background: #fee2e2; color: #7f1d1d; border: 1px solid #f87171; }

		.ih-table thead th small {
			display: block;
			font-weight: 500;
			font-size: 11px;
			opacity: 0.8;
			margin-top: 2px;
		}

		.ih-item-col {
			min-width: 130px;
			text-align: right !important;
		}

		.ih-item-col-wide {
			min-width: 170px;
		}

		.ih-badge-nonmoving {
			background: #ffedd5;
			color: #7c2d12;
			border: 1px solid #fb923c;
		}

		/* ── IH item-wise dialog: stat cards ─────────────────────────────────── */

		.ih-dialog-content {
			padding: 20px 22px 22px;
		}

		.ih-dialog-summary {
			display: flex;
			gap: 12px;
			flex-wrap: nowrap;
			margin-bottom: 20px;
		}

		.ih-stat-card {
			flex: 1 1 0;
			min-width: 0;
			background: #f8fafc;
			border: 1.5px solid #e2e8f0;
			border-left: 5px solid #94a3b8;
			border-radius: 12px;
			padding: 12px 16px;
			display: flex;
			flex-direction: column;
			gap: 6px;
		}

		.ih-stat-label {
			font-size: 11px;
			font-weight: 700;
			text-transform: uppercase;
			letter-spacing: 0.04em;
			color: #64748b;
			white-space: nowrap;
			overflow: hidden;
			text-overflow: ellipsis;
		}

		.ih-stat-value {
			font-size: 20px;
			font-weight: 800;
			color: #1f2937;
			white-space: nowrap;
			display: flex;
			align-items: baseline;
			gap: 3px;
		}

		.ih-stat-currency {
			font-size: 13px;
			font-weight: 700;
			opacity: 0.7;
		}

		.ih-stat-unit {
			font-size: 12px;
			font-weight: 600;
			opacity: 0.6;
			margin-left: 2px;
		}

		.ih-stat-total     { border-left-color: #6aace8; background: #eff6ff; }
		.ih-stat-total .ih-stat-value { color: #1e3a6e; }

		.ih-stat-slow      { border-left-color: #fcd34d; background: #fffbeb; }
		.ih-stat-slow .ih-stat-value { color: #92400e; }

		.ih-stat-nonmoving { border-left-color: #fb923c; background: #fff7ed; }
		.ih-stat-nonmoving .ih-stat-value { color: #7c2d12; }

		.ih-stat-dead      { border-left-color: #f87171; background: #fef2f2; }
		.ih-stat-dead .ih-stat-value { color: #991b1b; }

		.ih-item-table .row-label-col {
			min-width: 260px;
		}

		.ih-item-row:hover td:not(.row-label-col) {
			filter: brightness(0.96);
		}
		.ih-item-row:hover td.row-label-col {
			background-color: #f1f5f9 !important;
		}
		.ih-item-row:nth-child(even) td:not(.row-label-col) {
			filter: brightness(0.99);
		}

		.ih-row-slow td.row-label-col {
			border-left: 4px solid #fcd34d !important;
		}
		.ih-row-nonmoving td.row-label-col {
			border-left: 4px solid #fb923c !important;
		}
		.ih-row-dead td.row-label-col {
			border-left: 4px solid #f87171 !important;
		}

		</style>`).appendTo('head');
	}
}