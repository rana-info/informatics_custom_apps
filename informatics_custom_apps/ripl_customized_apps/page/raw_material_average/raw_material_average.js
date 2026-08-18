frappe.pages['raw-material-average'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Raw Material Average Pricing Analysis',
		single_column: true,
	});
	new RawMaterialAverage(page);
};

const METHOD_PREFIX = 'informatics_custom_apps.ripl_customized_apps.page.raw_material_average.raw_material_average';

const MATERIAL_COLORS = {
	'106444': '#f5a25d',
	'106448': '#82c99a',
};
const DEFAULT_MATERIAL_COLOR = '#4a90d9';
const BAR_COLOR = '#5b93f5';

let RMPA_STYLES_INJECTED = false;

class RawMaterialAverage {
	constructor(page) {
		this.page = page;
		this.active_bar_material = null;

		this.setup_filters();
		this.setup_body();
		this.load_filter_options();
	}

	setup_filters() {
		this.company_field = this.page.add_field({
			label: 'Company',
			fieldtype: 'Link',
			options: 'Company',
			fieldname: 'company',
			change: () => this.on_company_change(),
		});

		this.plant_field = this.page.add_field({
			label: 'Plant / Unit',
			fieldtype: 'Select',
			fieldname: 'plant',
			options: [{ label: 'All Plants', value: '' }],
			change: () => this.refresh(),
		});

		this.material_field = this.page.add_field({
			label: 'Raw Material',
			fieldtype: 'Select',
			fieldname: 'material',
			options: [{ label: 'All Materials', value: '' }],
			change: () => this.render(),
		});

		this.to_date_field = this.page.add_field({
			label: 'To Date',
			fieldtype: 'Date',
			fieldname: 'to_date',
			default: frappe.datetime.get_today(),
			change: () => this.refresh(),
		});

		this.page.set_primary_action('Refresh', () => this.refresh(), 'refresh');
	}

	on_company_change() {
	const company = this.company_field.get_value();

	frappe.call({
		method: `${METHOD_PREFIX}.get_filter_options`,
		args: {
			company: company || undefined
		}
	}).then((r) => {
		const data = r.message || {};

		// Reset Plant
		this.plant_field.set_value('');
		this.plant_field.df.options = [
			{ label: 'All Plants', value: '' }
		].concat(
			(data.plants || []).map((p) => ({
				label: p,
				value: p
			}))
		);
		this.plant_field.refresh();

		// Reset Material
		this.material_field.set_value('');
		this.materials = data.materials || [];

		this.material_field.df.options = [
			{ label: 'All Materials', value: '' }
		].concat(
			this.materials.map((m) => ({
				label: m.label,
				value: m.item_code
			}))
		);

		this.material_field.refresh();

		this.refresh();
	});
}
	load_filter_options() {
	return frappe.call({
		method: `${METHOD_PREFIX}.get_filter_options`,
		args: {
			company: undefined
		}
	}).then((r) => {
		const data = r.message || {};

		// Load ALL plants when company is not selected
		this.plant_field.df.options = [
			{ label: 'All Plants', value: '' }
		].concat(
			(data.plants || []).map((p) => ({
				label: p,
				value: p
			}))
		);

		this.plant_field.refresh();

		// Load ALL materials when company is not selected
		this.materials = data.materials || [];

		this.material_field.df.options = [
			{ label: 'All Materials', value: '' }
		].concat(
			this.materials.map((m) => ({
				label: m.label,
				value: m.item_code
			}))
		);

		this.material_field.refresh();

		this.refresh();
	});
}

	setup_body() {
		this.$body = $(`<div class="rmpa-wrapper"></div>`).appendTo(this.page.body);
		this.inject_styles();
	}

	material_color(item_code) {
		return MATERIAL_COLORS[item_code] || DEFAULT_MATERIAL_COLOR;
	}


	format_currency(value) {
		const num = Number(value) || 0;
		return '₹' + num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
	}

	refresh() {
		const company = this.company_field.get_value();

		this.$body.html(`
			<div class="rmpa-loading-state">
				<div class="rmpa-spinner"></div>
				<div>Crunching the numbers…</div>
			</div>
		`);

		frappe.call({
			method: `${METHOD_PREFIX}.get_report_data`,
			args: {
				company: company || undefined,
				to_date: this.to_date_field.get_value(),
				plant: this.plant_field.get_value() || undefined,
			},
		}).then((r) => {
			this.data = r.message || { months: [], summary_rows: [], trend: { months: [], series: {} }, plant_price_comparison: {}, materials: [], price_uom: 'Quintal' };
			this.materials = this.data.materials && this.data.materials.length ? this.data.materials : this.materials;
			this.active_bar_material = this.material_field.get_value() || (this.materials[0] && this.materials[0].item_code) || null;
			this.render();
		});
	}

	render() {
		this.$body.empty();
		if (!this.data) return;

		this.render_summary_table();
		this.render_trend_card();
		this.render_bar_card();
	}


	render_summary_table() {
		const price_uom = this.data.price_uom || 'Quintal';
		const selected_material = this.material_field.get_value();
		let rows = this.data.summary_rows || [];
		if (selected_material) {
			rows = rows.filter((r) => r.item_code === selected_material);
		}

		const $card = $(`<div class="rmpa-card rmpa-fade-in"></div>`);
		$card.append(`
			<div class="rmpa-card-title">Plant-wise Summary</div>
			<div class="rmpa-card-subtitle">Current procurement and stock position by plant and raw material.</div>
		`);

		if (!rows.length) {
			$card.append(`<div class="rmpa-empty-state">No data for the selected filters.</div>`);
			this.$body.append($card);
			return;
		}

		const table_rows = this.build_grouped_rows(rows);

		$card.append(`
			<div class="rmpa-table-scroll">
				<table class="table rmpa-table">
					<thead>
						<tr>
							<th>Plant / Unit</th>
							<th>Raw Material</th>
							<th class="text-right">Last Month Carrying Qty</th>
							<th class="text-right">Last Month Purchase Price (₹ / ${price_uom})</th>
							<th class="text-right">Current Month Days Covered</th>
							<th class="text-right">Current Month Consumption</th>
							<th class="text-right">Current Month Consumption Price (₹ / ${price_uom})</th>
							<th class="text-right">% of Past Consumption</th>
						</tr>
					</thead>
					<tbody>${table_rows}</tbody>
				</table>
			</div>
			<div class="rmpa-card-footnote">
				<strong>Days Covered = Carrying Qty ÷ Average Daily Consumption &nbsp;•&nbsp;
				% of Past Consumption = Current Month Consumption ÷ Avg. Monthly Consumption (previous 6 months) × 100</strong>
			</div>
		`);

		this.$body.append($card);
	}

	build_grouped_rows(rows) {
		let html = '';
		let i = 0;
		while (i < rows.length) {
			const plant = rows[i].plant;
			let span = 1;
			while (i + span < rows.length && rows[i + span].plant === plant) span++;

			for (let j = 0; j < span; j++) {
				const r = rows[i + j];
				html += '<tr>';
				if (j === 0) {
					html += `<td rowspan="${span}" class="rmpa-plant-cell"><span class="rmpa-plant-chip">${frappe.utils.escape_html(r.plant)}</span></td>`;
				}
				html += `
					<td>
						<span class="rmpa-material-dot" style="background:${this.material_color(r.item_code)}"></span>
						${frappe.utils.escape_html(r.label)}
					</td>
					<td class="text-right">${r.last_month_carrying_qty.toLocaleString()} ${r.uom}</td>
					<td class="text-right">${this.format_currency(r.last_month_purchase_price)}</td>
					<td class="text-right">${r.current_month_days_covered !== null ? r.current_month_days_covered + ' Days' : '—'}</td>
					<td class="text-right">${r.current_month_consumption.toLocaleString()} ${r.uom}</td>
					<td class="text-right">${this.format_currency(r.current_month_consumption_price)}</td>
					<td class="text-right">${r.pct_of_past_consumption !== null ? r.pct_of_past_consumption + '%' : '—'}</td>
				</tr>`;
			}
			i += span;
		}
		return html;
	}


	render_trend_card() {
		const trend = this.data.trend || { months: [], series: {} };
		const price_uom = this.data.price_uom || 'Quintal';
		const materials = this.materials || [];

		const $card = $(`<div class="rmpa-card rmpa-fade-in"></div>`);
		$card.append(`
			<div class="rmpa-card-title">Raw Material Purchase Price — 6 Month Trend</div>
			<div class="rmpa-card-subtitle">Historical purchase price comparison (₹ per ${price_uom}) for Rice, Maize and FCI.</div>
		`);

		const datasets = materials
			.map((m) => ({ item_code: m.item_code, label: m.label, color: this.material_color(m.item_code), values: trend.series[m.item_code] || [] }))
			.filter((d) => d.values.some((v) => v));

		if (!trend.months.length || !datasets.length) {
			$card.append(`<div class="rmpa-empty-state">No trend data for the selected filters.</div>`);
			this.$body.append($card);
			return;
		}

		const $legend = $(`<div class="rmpa-legend"></div>`);
		datasets.forEach((d) => {
			$legend.append(`
				<span class="rmpa-legend-item">
					<span class="rmpa-dot" style="background:${d.color}"></span>${frappe.utils.escape_html(d.label)}
				</span>
			`);
		});
		$card.append($legend);

		const $chart_area = $(`<div class="rmpa-chart-area"></div>`);
		$card.append($chart_area);
		this.$body.append($card);

		this.render_advanced_line_chart($chart_area, trend.months, datasets);
	}

	render_advanced_line_chart($wrap, months, datasets) {
		$wrap.empty();

		const width = 1200, height = 320;
		const padding = { top: 24, right: 30, bottom: 42, left: 80 };
		const plot_w = width - padding.left - padding.right;
		const plot_h = height - padding.top - padding.bottom;

		const all_values = datasets.flatMap((d) => d.values);
		const max_val = Math.max(...all_values, 0);
		const nice_max = this.nice_axis_max(max_val);
		const tick_count = 4;

		const x_for = (i) => padding.left + (months.length > 1 ? (i / (months.length - 1)) * plot_w : plot_w / 2);
		const y_for = (v) => padding.top + plot_h - (nice_max ? (v / nice_max) * plot_h : 0);

		const svg_ns = 'http://www.w3.org/2000/svg';
		const $svg = $(document.createElementNS(svg_ns, 'svg'));
		$svg.attr({ viewBox: `0 0 ${width} ${height}`, class: 'rmpa-line-svg' });

		const $defs = $(document.createElementNS(svg_ns, 'defs'));
		$svg.append($defs);

		const ticks = [];
		for (let i = 0; i <= tick_count; i++) ticks.push(Math.round((nice_max / tick_count) * i));
		ticks.forEach((t) => {
			const y = y_for(t);
			const $line = $(document.createElementNS(svg_ns, 'line'));
			$line.attr({ x1: padding.left, x2: width - padding.right, y1: y, y2: y, class: 'rmpa-grid-line' });
			$svg.append($line);
			const $label = $(document.createElementNS(svg_ns, 'text'));
			$label.attr({ x: padding.left - 10, y: y + 4, class: 'rmpa-axis-text', 'text-anchor': 'end' });
			$label.text(this.format_currency(t));
			$svg.append($label);
		});

		months.forEach((m, i) => {
			const $label = $(document.createElementNS(svg_ns, 'text'));
			$label.attr({ x: x_for(i), y: height - 10, class: 'rmpa-axis-text', 'text-anchor': 'middle' });
			$label.text(m);
			$svg.append($label);
		});

		datasets.forEach((d, idx) => {
			const points = d.values.map((v, i) => [x_for(i), y_for(v)]);
			const line_path = this.smooth_path(points);
			const area_path = `${line_path} L${x_for(points.length - 1)},${padding.top + plot_h} L${x_for(0)},${padding.top + plot_h} Z`;

			const gradient_id = `rmpa-grad-${idx}`;
			const $gradient = $(document.createElementNS(svg_ns, 'linearGradient'));
			$gradient.attr({ id: gradient_id, x1: 0, y1: 0, x2: 0, y2: 1 });
			$gradient.append($(document.createElementNS(svg_ns, 'stop')).attr({ offset: '0%', 'stop-color': d.color, 'stop-opacity': 0.32 }));
			$gradient.append($(document.createElementNS(svg_ns, 'stop')).attr({ offset: '100%', 'stop-color': d.color, 'stop-opacity': 0 }));
			$defs.append($gradient);

			const $area = $(document.createElementNS(svg_ns, 'path'));
			$area.attr({ d: area_path, fill: `url(#${gradient_id})`, stroke: 'none' });
			$svg.append($area);

			const $path = $(document.createElementNS(svg_ns, 'path'));
			$path.attr({ d: line_path, class: 'rmpa-line-path', stroke: d.color, fill: 'none' });
			$svg.append($path);

			points.forEach((p) => {
				const $dot = $(document.createElementNS(svg_ns, 'circle'));
				$dot.attr({ cx: p[0], cy: p[1], r: 3.5, class: 'rmpa-line-dot', fill: d.color, stroke: '#fff', 'stroke-width': 1.5 });
				$svg.append($dot);
			});
		});

		const $hover_line = $(document.createElementNS(svg_ns, 'line'));
		$hover_line.attr({ class: 'rmpa-hover-line', y1: padding.top, y2: padding.top + plot_h, x1: -100, x2: -100 });
		$svg.append($hover_line);

		const $overlay = $(document.createElementNS(svg_ns, 'rect'));
		$overlay.attr({ x: padding.left, y: padding.top, width: plot_w, height: plot_h, fill: 'transparent', class: 'rmpa-hover-overlay' });
		$svg.append($overlay);

		const $tooltip = $(`<div class="rmpa-chart-tooltip"></div>`);
		$wrap.css('position', 'relative');
		$wrap.append($svg);
		$wrap.append($tooltip);

		requestAnimationFrame(() => {
			$svg.find('.rmpa-line-path').each(function () {
				const len = this.getTotalLength();
				this.style.strokeDasharray = len;
				this.style.strokeDashoffset = len;
				this.getBoundingClientRect();
				this.style.transition = 'stroke-dashoffset 1.1s cubic-bezier(.4,0,.2,1)';
				this.style.strokeDashoffset = 0;
			});
		});

		$overlay.on('mousemove', (e) => {
			const rect = $svg[0].getBoundingClientRect();
			const scale_x = width / rect.width;
			const mouse_x = (e.clientX - rect.left) * scale_x;
			let closest = 0, closest_dist = Infinity;
			months.forEach((_, i) => {
				const dist = Math.abs(x_for(i) - mouse_x);
				if (dist < closest_dist) { closest_dist = dist; closest = i; }
			});
			$hover_line.attr({ x1: x_for(closest), x2: x_for(closest) }).css('opacity', 1);

			const rows = datasets.map((d) => `
				<div class="rmpa-tooltip-row">
					<span class="rmpa-dot" style="background:${d.color}"></span>
					<span class="rmpa-tooltip-label">${frappe.utils.escape_html(d.label)}</span>
					<span class="rmpa-tooltip-value">${this.format_currency(d.values[closest] || 0)}</span>
				</div>
			`).join('');
			$tooltip.html(`<div class="rmpa-tooltip-month">${months[closest]}</div>${rows}`);

			const wrap_w = $wrap.width() || width;
			const wrap_h = $wrap.height() || height;
			const tooltip_x = (x_for(closest) / width) * wrap_w;
			const tooltip_y = (padding.top / height) * wrap_h;
			$tooltip.css({ opacity: 1, left: Math.min(tooltip_x + 14, wrap_w - 180), top: tooltip_y });
		});

		$overlay.on('mouseleave', () => {
			$hover_line.css('opacity', 0);
			$tooltip.css('opacity', 0);
		});
	}

	/** Catmull-Rom to cubic-bezier conversion for a smooth SVG path through points. */
	smooth_path(points) {
		if (!points.length) return '';
		if (points.length === 1) return `M${points[0][0]},${points[0][1]}`;

		let d = `M${points[0][0]},${points[0][1]}`;
		for (let i = 0; i < points.length - 1; i++) {
			const p0 = points[i === 0 ? i : i - 1];
			const p1 = points[i];
			const p2 = points[i + 1];
			const p3 = points[i + 2 < points.length ? i + 2 : i + 1];
			const cp1x = p1[0] + (p2[0] - p0[0]) / 6;
			const cp1y = p1[1] + (p2[1] - p0[1]) / 6;
			const cp2x = p2[0] - (p3[0] - p1[0]) / 6;
			const cp2y = p2[1] - (p3[1] - p1[1]) / 6;
			d += ` C${cp1x},${cp1y} ${cp2x},${cp2y} ${p2[0]},${p2[1]}`;
		}
		return d;
	}


	render_bar_card() {
		const materials = this.materials || [];
		const price_uom = this.data.price_uom || 'Quintal';
		if (!materials.length) return;

		if (!this.active_bar_material || !materials.some((m) => m.item_code === this.active_bar_material)) {
			this.active_bar_material = materials[0].item_code;
		}

		const $card = $(`<div class="rmpa-card rmpa-fade-in"></div>`);
		$card.append(`
			<div class="rmpa-card-title">Plant-wise Raw Material Average Price</div>
			<div class="rmpa-card-subtitle">Comparison of average purchase price across plants for the selected raw material.</div>
		`);

		const $toggle = $(`<div class="rmpa-pill-row"></div>`);
		materials.forEach((m) => {
			$toggle.append(`
				<button type="button" class="rmpa-pill ${m.item_code === this.active_bar_material ? 'active' : ''}" data-item="${m.item_code}">
					<span class="rmpa-pill-dot" style="background:${this.material_color(m.item_code)}"></span>
					${frappe.utils.escape_html(m.label)}
				</button>
			`);
		});
		$card.append($toggle);

		const $chart_wrap = $(`<div class="rmpa-hbar-wrap"></div>`);
		$card.append($chart_wrap);
		$card.append(`<div class="rmpa-card-footnote"><strong>Average price = Purchase Amount ÷ Purchase Quantity (₹ per ${price_uom}).</strong></div>`);

		this.$body.append($card);

		const draw = () => {
			const rows = (this.data.plant_price_comparison || {})[this.active_bar_material] || [];
			this.render_horizontal_bar($chart_wrap, rows);
		};
		draw();

		$card.on('click', '.rmpa-pill', (e) => {
			this.active_bar_material = $(e.currentTarget).data('item');
			$card.find('.rmpa-pill').removeClass('active');
			$(e.currentTarget).addClass('active');
			draw();
		});
	}

render_horizontal_bar($wrap, rows) {
	$wrap.empty();

	if (!rows.length) {
		$wrap.html(
			'<div class="rmpa-empty-state">No purchase price data for this material in the selected period.</div>'
		);
		return;
	}

	const max_val = Math.max(...rows.map((r) => Number(r.avg_price) || 0));
	const nice_max = this.nice_axis_max(max_val);
	const tick_count = 4;

	const ticks = [];
	for (let i = 0; i <= tick_count; i++) {
		ticks.push(Math.round((nice_max / tick_count) * i));
	}

	const $rows = $('<div class="rmpa-hbar-rows"></div>');

	rows.forEach((r) => {
		const pct = nice_max
			? Math.min((Number(r.avg_price) / nice_max) * 100, 100)
			: 0;

		$rows.append(`
			<div class="rmpa-hbar-row">
				<div class="rmpa-hbar-label">
					${frappe.utils.escape_html(r.plant)}
				</div>

				<div class="rmpa-hbar-track">
					${ticks.map((_, i) => `
						<div
							class="rmpa-hbar-gridline"
							style="left:${(i / tick_count) * 100}%"
						></div>
					`).join('')}

					<div
						class="rmpa-hbar-fill"
						data-width="${pct}"
						style="width:0%; background:${BAR_COLOR};"
					></div>
				</div>

				<div class="rmpa-hbar-value">
					${this.format_currency(r.avg_price)}
				</div>
			</div>
		`);
	});

	$wrap.append($rows);

	// Axis
	const $axis = $('<div class="rmpa-hbar-axis"></div>');

	$axis.append(`
		<div class="rmpa-hbar-axis-spacer"></div>
		<div class="rmpa-hbar-axis-ticks"></div>
		<div class="rmpa-hbar-axis-value-spacer"></div>
	`);

	const $ticks_row = $axis.find('.rmpa-hbar-axis-ticks');

	ticks.forEach((t, i) => {
		$ticks_row.append(`
			<span style="left:${(i / tick_count) * 100}%">
				${this.format_currency(t)}
			</span>
		`);
	});

	$wrap.append($axis);

	// Animate bars
	requestAnimationFrame(() => {
		$wrap.find('.rmpa-hbar-fill').each(function () {
			const $el = $(this);
			$el.css('width', `${$el.data('width')}%`);
		});
	});
}

	nice_axis_max(value) {
		if (!value) return 10;
		const magnitude = Math.pow(10, Math.floor(Math.log10(value)));
		const residual = value / magnitude;
		let nice;
		if (residual <= 1) nice = 1;
		else if (residual <= 2) nice = 2;
		else if (residual <= 4) nice = 4;
		else if (residual <= 5) nice = 5;
		else nice = 10;
		return nice * magnitude;
	}

	inject_styles() {
		if (RMPA_STYLES_INJECTED) return;
		RMPA_STYLES_INJECTED = true;

		$(`
			<style>
				:root {
					--rmpa-font: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', sans-serif;
				}

				.rmpa-wrapper { padding: 14px 2px 30px; font-family: var(--rmpa-font); -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }
				.rmpa-wrapper, .rmpa-wrapper * { box-sizing: border-box; font-family: var(--rmpa-font); }

				.rmpa-card {
					background: #ffffff; border-radius: 14px; padding: 26px 28px;
					box-shadow: 0 1px 2px rgba(16,24,40,0.04), 0 4px 14px rgba(16,24,40,0.05);
					border: 1px solid #eef0f3; margin-bottom: 22px;
					transition: box-shadow .25s ease, transform .25s ease;
				}
				.rmpa-card:hover {
					box-shadow: 0 2px 6px rgba(16,24,40,0.06), 0 10px 24px rgba(16,24,40,0.08);
				}

				@keyframes rmpaFadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
				.rmpa-fade-in { animation: rmpaFadeIn .45s cubic-bezier(.4,0,.2,1) both; }

				.rmpa-card-title { font-size: 18px; font-weight: 700; color: #101828; letter-spacing: -0.015em; line-height: 1.3; }
				.rmpa-card-subtitle { font-size: 13.5px; color: #667085; margin-top: 4px; font-weight: 500; line-height: 1.5; }
				.rmpa-card-footnote { font-size: 13px; color: #667085; margin-top: 18px; line-height: 1.7; letter-spacing: -0.005em; }
				.rmpa-card-footnote strong { color: #344054; font-weight: 700; }

				.rmpa-empty-state, .rmpa-loading-state {
					padding: 46px 20px; text-align: center; color: #98a2b3; font-size: 14px; font-weight: 500;
				}
				.rmpa-loading-state { display: flex; flex-direction: column; align-items: center; gap: 14px; }
				.rmpa-spinner {
					width: 26px; height: 26px; border-radius: 50%;
					border: 3px solid #e4e7ec; border-top-color: #2490ef;
					animation: rmpaSpin .8s linear infinite;
				}
				@keyframes rmpaSpin { to { transform: rotate(360deg); } }

				.rmpa-table-scroll { overflow-x: auto; margin-top: 18px; border-radius: 10px; border: 1px solid #f0f1f3; }
				.rmpa-table { width: 100%; table-layout: fixed; border-collapse: separate; border-spacing: 0; margin: 0; }
				.rmpa-table th {
					font-size: 11px; text-transform: uppercase; letter-spacing: .03em; font-weight: 700;
					color: #667085; background: #f9fafb; padding: 12px 10px; border-bottom: 1px solid #eef0f3;
					white-space: normal; line-height: 1.4; word-break: break-word;
				}
				.rmpa-table td {
					font-size: 13.5px; font-weight: 500; padding: 13px 10px; color: #344054;
					border-bottom: 1px solid #f5f6f8; white-space: normal; word-break: break-word; font-variant-numeric: tabular-nums;
				}
				.rmpa-table th:nth-child(1), .rmpa-table td:nth-child(1) { width: 11%; }
				.rmpa-table th:nth-child(2), .rmpa-table td:nth-child(2) { width: 10%; }
				.rmpa-table th:nth-child(3), .rmpa-table td:nth-child(3) { width: 13%; }
				.rmpa-table th:nth-child(4), .rmpa-table td:nth-child(4) { width: 15%; }
				.rmpa-table th:nth-child(5), .rmpa-table td:nth-child(5) { width: 12%; }
				.rmpa-table th:nth-child(6), .rmpa-table td:nth-child(6) { width: 13%; }
				.rmpa-table th:nth-child(7), .rmpa-table td:nth-child(7) { width: 15%; }
				.rmpa-table th:nth-child(8), .rmpa-table td:nth-child(8) { width: 11%; }
				.rmpa-table td.text-right { font-weight: 600; color: #1d2939; }
				.rmpa-table tbody tr { transition: background .15s ease; }
				.rmpa-table tbody tr:hover { background: #f9fbff; }
				.rmpa-table tbody tr:last-child td { border-bottom: none; }

				.rmpa-plant-chip {
					display: inline-block; background: #f2f4f7; color: #344054; font-weight: 600;
					font-size: 12.5px; padding: 3px 11px; border-radius: 999px;
				}
				.rmpa-plant-cell { vertical-align: middle; background: #fafbfc; border-right: 1px solid #f0f1f3; }
				.rmpa-material-dot, .rmpa-pill-dot {
					display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 7px;
				}

				.rmpa-legend { display: flex; flex-wrap: wrap; gap: 20px; margin: 18px 0 8px; }
				.rmpa-legend-item { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; color: #344054; }
				.rmpa-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
				.rmpa-chart-area { margin-top: 6px; position: relative; }

				.rmpa-line-svg { width: 100%; height: auto; display: block; }
				.rmpa-grid-line { stroke: #eef0f3; stroke-width: 1; }
				.rmpa-axis-text { fill: #98a2b3; font-size: 12px; font-weight: 600; font-family: var(--rmpa-font); font-variant-numeric: tabular-nums; }
				.rmpa-line-path { stroke-width: 2.5; fill: none; stroke-linecap: round; stroke-linejoin: round; }
				.rmpa-line-dot { transition: r .15s ease; cursor: pointer; }
				.rmpa-line-dot:hover { r: 5.5; }
				.rmpa-hover-line { stroke: #d0d5dd; stroke-width: 1; stroke-dasharray: 3 3; opacity: 0; transition: opacity .15s ease; }
				.rmpa-hover-overlay { cursor: crosshair; }

				.rmpa-chart-tooltip {
					position: absolute; pointer-events: none; background: #101828; color: #fff;
					border-radius: 10px; padding: 12px 16px; font-size: 13px; min-width: 160px;
					box-shadow: 0 8px 20px rgba(16,24,40,0.25); opacity: 0; transition: opacity .12s ease, left .08s ease;
					z-index: 10;
				}
				.rmpa-tooltip-month { font-weight: 700; font-size: 13.5px; margin-bottom: 8px; letter-spacing: -0.01em; }
				.rmpa-tooltip-row { display: flex; align-items: center; gap: 8px; padding: 3px 0; }
				.rmpa-tooltip-label { flex: 1; font-weight: 500; color: #d0d5dd; }
				.rmpa-tooltip-value { font-weight: 700; font-variant-numeric: tabular-nums; }

				.rmpa-pill-row { display: flex; gap: 8px; flex-wrap: wrap; margin: 18px 0; }
				.rmpa-pill {
					display: inline-flex; align-items: center; border: 1px solid #d0d5dd; background: #fff; color: #344054;
					font-size: 13px; font-weight: 600; padding: 7px 17px; border-radius: 999px; cursor: pointer;
					transition: background .18s ease, border-color .18s ease, color .18s ease, transform .12s ease;
				}
				.rmpa-pill:hover { background: #f9fafb; transform: translateY(-1px); }
				.rmpa-pill.active { background: #2490ef; border-color: #2490ef; color: #fff; }
				.rmpa-pill.active .rmpa-pill-dot { background: #fff !important; }

				.rmpa-hbar-wrap {
	margin-top: 8px;
	width: 100%;
	overflow: hidden;
}

.rmpa-hbar-rows {
	display: flex;
	flex-direction: column;
	gap: 18px;
	width: 100%;
}

.rmpa-hbar-row {
	display: grid;
	grid-template-columns: 130px minmax(0, 1fr) 100px;
	align-items: center;
	column-gap: 14px;
	width: 100%;
}

.rmpa-hbar-label {
	width: 100%;
	min-width: 0;
	font-size: 13.5px;
	font-weight: 600;
	color: #344054;
	text-align: right;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.rmpa-hbar-track {
	position: relative;
	width: 100%;
	min-width: 0;
	height: 24px;
}

.rmpa-hbar-gridline {
	position: absolute;
	top: -4px;
	bottom: -4px;
	width: 1px;
	background: #eef0f3;
	pointer-events: none;
}

.rmpa-hbar-fill {
	position: relative;
	height: 100%;
	border-radius: 5px;
	min-width: 2px;
	max-width: 100%;
	transition: width .8s cubic-bezier(.4,0,.2,1);
	display: flex;
	align-items: center;
}

.rmpa-hbar-value {
	width: 100%;
	min-width: 0;
	font-size: 13px;
	font-weight: 700;
	color: #344054;
	font-variant-numeric: tabular-nums;
	white-space: nowrap;
	text-align: left;
	overflow: hidden;
	text-overflow: ellipsis;
}

.rmpa-hbar-axis {
	display: grid;
	grid-template-columns: 130px minmax(0, 1fr) 100px;
	column-gap: 14px;
	width: 100%;
	margin-top: 12px;
}

.rmpa-hbar-axis-spacer {
	width: 100%;
}

.rmpa-hbar-axis-ticks {
	position: relative;
	width: 100%;
	height: 18px;
	min-width: 0;
}

.rmpa-hbar-axis-ticks span {
	position: absolute;
	transform: translateX(-50%);
	font-size: 12px;
	color: #98a2b3;
	font-weight: 600;
	font-variant-numeric: tabular-nums;
	white-space: nowrap;
}

.rmpa-hbar-axis-value-spacer {
	width: 100%;
}
			</style>
		`).appendTo('head');
	}
}