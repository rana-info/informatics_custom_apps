frappe.pages['general-and-pesticid'].on_page_load = function (wrapper) {

	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'General & Pesticides Stock',
		single_column: true
	});

	if (!document.getElementById('gp-font-link')) {
		const l = document.createElement('link');
		l.id = 'gp-font-link'; l.rel = 'stylesheet';
		l.href = 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap';
		document.head.appendChild(l);
	}

	$('#gp-css').remove();
	$('<style id="gp-css">').text(`
		.gp-root, .gp-root * { box-sizing: border-box; font-family: 'Inter', sans-serif; }
		.gp-root { display: flex; min-height: 100vh; background: #F0F4F8; }

		/* ── SIDEBAR ── */
		.gp-sidebar {
			width: 210px; flex-shrink: 0;
			background: linear-gradient(180deg, #0F2044 0%, #1A3560 100%);
			display: flex; flex-direction: column;
			padding: 24px 0 24px; min-height: 100vh; position: sticky; top: 0; align-self: flex-start;
		}
		.gp-sidebar-logo {
			display: flex; align-items: center; gap: 10px;
			padding: 0 18px 22px; border-bottom: 1px solid rgba(255,255,255,0.08); margin-bottom: 10px;
		}
		.gp-sidebar-logo-icon {
			width: 32px; height: 32px; border-radius: 8px;
			background: linear-gradient(135deg,#3B82F6,#06B6D4);
			display: flex; align-items: center; justify-content: center; font-size: 16px;
		}
		.gp-sidebar-logo-text { font-size: 14px; font-weight: 700; color: #fff; }
		.gp-sidebar-logo-sub  { font-size: 10px; color: rgba(255,255,255,0.4); }
		.gp-nav-section { font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: rgba(255,255,255,0.25); padding: 14px 18px 4px; }
		.gp-nav-item {
			display: flex; align-items: center; gap: 10px;
			padding: 10px 18px; font-size: 13px; font-weight: 500;
			color: rgba(255,255,255,0.5); cursor: pointer;
			border-left: 3px solid transparent; transition: all .15s; user-select: none;
		}
		.gp-nav-item:hover  { color: rgba(255,255,255,0.85); background: rgba(255,255,255,0.05); }
		.gp-nav-item.active { color: #fff; border-left-color: #3B82F6; background: rgba(59,130,246,0.13); }
		.gp-nav-icon { font-size: 15px; width: 18px; text-align: center; }
		.gp-nav-divider { height: 1px; background: rgba(255,255,255,0.07); margin: 8px 18px; }

		/* ── MAIN ── */
		.gp-main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
		.gp-topbar {
			background: #fff; border-bottom: 1px solid #E8EEF4;
			padding: 0 26px; height: 56px; display: flex; align-items: center;
			justify-content: space-between; flex-shrink: 0; position: sticky; top: 0; z-index: 10;
		}
		.gp-topbar-left { font-size: 15px; font-weight: 700; color: #1E293B; display: flex; align-items: center; gap: 8px; }
		.gp-topbar-date { font-size: 11px; font-weight: 500; color: #94A3B8; background: #F1F5F9; border-radius: 20px; padding: 2px 10px; }
		.gp-topbar-right { display: flex; align-items: center; gap: 12px; }
		.gp-topbar-badge { font-size: 11px; font-weight: 600; padding: 3px 11px; border-radius: 20px; background: #DBEAFE; color: #1D4ED8; }
		.gp-topbar-badge.pest { background: #FEF3C7; color: #92400E; }
		.gp-refresh-btn {
			background: #1A3560; color: #fff; border: none; border-radius: 7px;
			padding: 6px 14px; font-size: 12px; font-weight: 600; cursor: pointer;
			font-family: 'Inter',sans-serif; display: flex; align-items: center; gap: 5px;
		}
		.gp-refresh-btn:hover { background: #0F2044; }
		.gp-content { padding: 22px 26px 60px; flex: 1; overflow-y: auto; }

		/* ── VIEWS ── */
		.gp-view { display: none; }
		.gp-view.active { display: block; }

		/* ── SECTION BANNER ── */
		.gp-section-banner {
			border-radius: 12px; padding: 16px 22px; margin-bottom: 20px;
			display: flex; align-items: center; gap: 14px;
		}
		.gp-section-banner.store  { background: linear-gradient(135deg,#EFF6FF,#DBEAFE); border: 1px solid #BFDBFE; }
		.gp-section-banner.pest   { background: linear-gradient(135deg,#FFFBEB,#FEF3C7); border: 1px solid #FDE68A; }
		.gp-section-banner-icon   { font-size: 28px; }
		.gp-section-banner-title  { font-size: 18px; font-weight: 800; color: #1E293B; }
		.gp-section-banner-sub    { font-size: 12px; font-weight: 500; color: #64748B; margin-top: 2px; }

		/* ── KPI ROW ── */
		.gp-kpi-row { display: grid; grid-template-columns: repeat(4,1fr); gap: 13px; margin-bottom: 20px; }
		.gp-kpi-card {
			background: #fff; border-radius: 13px; padding: 18px 20px;
			border: 1px solid #E8EEF4; position: relative; overflow: hidden;
		}
		.gp-kpi-card::before { content:''; position:absolute; top:0; left:0; right:0; height:3px; }
		.gp-kpi-card.c-blue::before   { background: linear-gradient(90deg,#3B82F6,#60A5FA); }
		.gp-kpi-card.c-green::before  { background: linear-gradient(90deg,#10B981,#34D399); }
		.gp-kpi-card.c-orange::before { background: linear-gradient(90deg,#F97316,#FB923C); }
		.gp-kpi-card.c-purple::before { background: linear-gradient(90deg,#8B5CF6,#A78BFA); }
		.gp-kpi-card.c-amber::before  { background: linear-gradient(90deg,#F59E0B,#FBBF24); }
		.gp-kpi-label { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: .6px; color: #94A3B8; margin-bottom: 6px; }
		.gp-kpi-val   { font-size: 24px; font-weight: 800; color: #1E293B; line-height: 1; letter-spacing: -.4px; margin-bottom: 4px; }
		.gp-kpi-sub   { font-size: 11px; color: #64748B; font-weight: 500; }
		.gp-kpi-icon  {
			position: absolute; top: 16px; right: 16px;
			width: 34px; height: 34px; border-radius: 9px;
			display: flex; align-items: center; justify-content: center; font-size: 17px;
		}
		.c-blue   .gp-kpi-icon { background:#DBEAFE; }
		.c-green  .gp-kpi-icon { background:#D1FAE5; }
		.c-orange .gp-kpi-icon { background:#FED7AA; }
		.c-purple .gp-kpi-icon { background:#EDE9FE; }
		.c-amber  .gp-kpi-icon { background:#FEF3C7; }

		/* ── TAB BAR ── */
		.gp-tab-bar {
			display: flex; align-items: center;
			background: #fff; border-radius: 10px 10px 0 0;
			border: 1px solid #E8EEF4; border-bottom: none; padding: 0 20px;
		}
		.gp-tab {
			padding: 13px 16px; font-size: 13px; font-weight: 600;
			color: #94A3B8; cursor: pointer; border-bottom: 2px solid transparent; transition: all .15s;
		}
		.gp-tab:hover  { color: #475569; }
		.gp-tab.active { color: #3B82F6; border-bottom-color: #3B82F6; }
		.gp-tab-spacer { flex: 1; }
		.gp-vtbtn {
			font-size: 11px; font-weight: 600; padding: 5px 11px; border-radius: 6px;
			border: 1px solid #E8EEF4; background: #F8FAFC; color: #64748B;
			cursor: pointer; transition: all .15s; font-family: 'Inter',sans-serif;
		}
		.gp-vtbtn.active { background: #1A3560; color: #fff; border-color: #1A3560; }

		/* ── CHART PANEL ── */
		.gp-main-panel {
			background: #fff; border-radius: 0 0 13px 13px;
			border: 1px solid #E8EEF4; border-top: none;
			padding: 20px 22px 18px;
			display: grid; grid-template-columns: 1fr 280px;
			gap: 22px; margin-bottom: 20px; align-items: start;
		}
		.gp-chart-title { font-size: 13px; font-weight: 700; color: #1E293B; margin-bottom: 14px; }
		.gp-chart-wrap  { position: relative; height: 300px; }
		.gp-rank-title  { font-size: 13px; font-weight: 700; color: #1E293B; margin-bottom: 12px; }
		.gp-rank-row { display:flex; align-items:center; gap:9px; padding:7px 0; border-bottom:1px solid #F1F5F9; }
		.gp-rank-row:last-child { border-bottom:none; }
		.gp-rank-num { width:22px; height:22px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:10px; font-weight:700; flex-shrink:0; }
		.gp-rank-num.top { background:#1A3560; color:#fff; }
		.gp-rank-num.mid { background:#F1F5F9; color:#64748B; }
		.gp-rank-name    { flex:1; font-size:12px; font-weight:500; color:#334155; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
		.gp-rank-val     { font-size:12px; font-weight:700; color:#1E293B; text-align:right; white-space:nowrap; }
		.gp-rank-subval  { font-size:10px; font-weight:500; color:#94A3B8; text-align:right; white-space:nowrap; }

		/* ── PIE SECTION ── */
		.gp-sec-hd {
			font-size: 12px; font-weight: 700; color: #64748B;
			text-transform: uppercase; letter-spacing: .7px;
			margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center;
		}
		.gp-sec-hd span { font-size:11px; font-weight:500; color:#94A3B8; text-transform:none; letter-spacing:0; }
		.gp-pie-card {
			background: #fff; border: 1.5px solid #E8EEF4; border-radius: 14px;
			padding: 22px 24px 18px; margin-bottom: 16px;
			cursor: pointer; transition: border-color .18s, box-shadow .18s;
		}
		.gp-pie-card:hover  { border-color: #93C5FD; box-shadow: 0 4px 18px rgba(59,130,246,0.09); }
		.gp-pie-card.active { border-color: #3B82F6; box-shadow: 0 4px 20px rgba(59,130,246,0.14); }
		.gp-pie-card-hd { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:18px; }
		.gp-pie-card-name  { font-size:16px; font-weight:800; color:#1E293B; }
		.gp-pie-card-sub   { font-size:12px; font-weight:500; color:#94A3B8; margin-top:2px; }
		.gp-pie-card-badges { display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end; }
		.gp-badge-qty { font-size:13px; font-weight:700; color:#1D4ED8; background:#DBEAFE; border-radius:7px; padding:4px 12px; }
		.gp-badge-val { font-size:13px; font-weight:700; color:#065F46; background:#D1FAE5; border-radius:7px; padding:4px 12px; }
		.gp-pie-body { display:grid; grid-template-columns:1fr 1fr; gap:16px; align-items:start; }
		.gp-donut-svg-wrap { width:100%; aspect-ratio:8/5; flex-shrink:0; position:relative; overflow:hidden; }
		.gp-donut-svg-wrap svg { width:100%; height:100%; display:block; overflow:hidden; }
		.gp-leg-table { width:100%; border-collapse:collapse; }
		.gp-leg-table th { font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:.5px; color:#94A3B8; padding:5px 8px; border-bottom:2px solid #F1F5F9; text-align:left; }
		.gp-leg-table th:last-child, .gp-leg-table td:last-child { text-align:right; }
		.gp-leg-table td { padding:8px 8px; border-bottom:1px solid #F8FAFC; font-size:13px; color:#1E293B; font-weight:500; }
		.gp-leg-table tr:last-child td { border-bottom:none; }
		.gp-leg-table tr:hover td { background:#F8FAFC; }
		.gp-leg-dot-cell { display:flex; align-items:center; gap:8px; }
		.gp-leg-dot { width:9px; height:9px; border-radius:50%; flex-shrink:0; }
		.gp-leg-plant-name { font-weight:600; color:#334155; }
		.gp-pct-badge { font-size:11px; font-weight:700; border-radius:10px; padding:2px 7px; white-space:nowrap; }
		.gp-bar-inline-wrap { background:#F1F5F9; border-radius:3px; height:5px; width:100%; margin-top:3px; min-width:60px; }
		.gp-bar-inline-fill { height:100%; border-radius:3px; }

		/* Items panel */
		.gp-items-panel { display:none; background:#F8FAFC; border:1px solid #E8EEF4; border-radius:12px; padding:18px 20px; margin-bottom:16px; }
		.gp-items-panel.open { display:block; }
		.gp-items-panel-hd { display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; }
		.gp-items-panel-title { font-size:14px; font-weight:700; color:#1E293B; }
		.gp-items-close { background:#E8EEF4; border:none; border-radius:50%; width:26px; height:26px; font-size:13px; color:#64748B; cursor:pointer; display:flex; align-items:center; justify-content:center; }
		.gp-items-close:hover { background:#DDE5EF; }
		.gp-items-table { width:100%; border-collapse:collapse; font-size:13px; }
		.gp-items-table th { font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:.5px; color:#94A3B8; padding:5px 8px; border-bottom:2px solid #E8EEF4; text-align:left; }
		.gp-items-table td { padding:8px 8px; border-bottom:1px solid #F1F5F9; color:#1E293B; font-weight:500; vertical-align:middle; }
		.gp-items-table tr:hover td { background:#F1F5F9; }
		.gp-items-table tr:last-child td { border-bottom:none; }
		.gp-rank-badge { display:inline-flex; align-items:center; justify-content:center; width:22px; height:22px; border-radius:50%; font-size:11px; font-weight:700; }
		.gp-rank-badge.top3 { background:#1A3560; color:#fff; }
		.gp-rank-badge.rest { background:#F1F5F9; color:#64748B; }
		.gp-bar-mini-wrap { background:#F1F5F9; border-radius:3px; height:5px; width:80px; margin-top:3px; }
		.gp-bar-mini-fill { height:100%; border-radius:3px; }

		/* ── PLANTS VIEW ── */
		.gp-plant-table-wrap { background:#fff; border:1px solid #E8EEF4; border-radius:12px; overflow:hidden; }
		.gp-plant-table { width:100%; border-collapse:collapse; font-size:13px; }
		.gp-plant-table th { background:#F8FAFC; font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:.5px; color:#64748B; padding:10px 14px; border-bottom:2px solid #E8EEF4; text-align:left; }
		.gp-plant-table td { padding:10px 14px; border-bottom:1px solid #F8FAFC; color:#1E293B; font-weight:500; }
		.gp-plant-table tr:hover td { background:#F8FAFC; }
		.gp-plant-table tr:last-child td { border-bottom:none; }

		.gp-loading { text-align:center; padding:32px; font-size:13px; color:#94A3B8; }
		.gp-empty-state { text-align:center; padding:60px 20px; color:#94A3B8; font-size:14px; }

		@media (max-width:960px) {
			.gp-sidebar { display:none; }
			.gp-kpi-row { grid-template-columns:repeat(2,1fr); }
			.gp-main-panel { grid-template-columns:1fr; }
			.gp-pie-body { grid-template-columns:1fr; }
		}
	`).appendTo('head');

	$(page.body).css({ padding:'0', background:'#F0F4F8' });
	const root = $('<div class="gp-root">').appendTo(page.body);
	load_gp_dashboard(root);
};


/* ═══════════════════════════════════════════════════════════════ */
function load_gp_dashboard(root) {

	frappe.dom.freeze('Loading dashboard…');

	frappe.call({
		method: 'informatics_custom_apps.ripl_customized_apps.page.general_and_pesticid.general_and_pesticid.get_item_group_chart',
		callback(r) {
			frappe.dom.unfreeze();
			const msg       = r.message || {};
			const storeRows = msg.store_items || [];
			const pestRows  = msg.pesticides  || [];

			/* ── PALETTE ── */
			const COLORS = [
				{bg:'#BFDBFE',border:'#3B82F6'},
				{bg:'#BBF7D0',border:'#22C55E'},
				{bg:'#FED7AA',border:'#F97316'},
				{bg:'#E9D5FF',border:'#A855F7'},
				{bg:'#FEF08A',border:'#CA8A04'},
				{bg:'#FBCFE8',border:'#EC4899'},
				{bg:'#A5F3FC',border:'#06B6D4'},
				{bg:'#D1FAE5',border:'#10B981'},
				{bg:'#FCA5A5',border:'#EF4444'},
				{bg:'#C7D2FE',border:'#6366F1'},
				{bg:'#F5D0A9',border:'#D97706'},
				{bg:'#CFFAFE',border:'#0891B2'},
			];

			const fmt = v => v >= 10000000 ? (v/10000000).toFixed(2)+' Cr'
						   : v >= 100000   ? (v/100000).toFixed(2)+' L'
						   : v >= 1000     ? (v/1000).toFixed(1)+'k'
						   : String(Math.round(v));

			/* ── Parse rows ── */
			function parseRows(rows) {
				const itemGroups = [];
				const plants     = {};
				rows.forEach(row => {
					const plant = row.branch || row.plant || row.warehouse || '';
					const group = row.item_group || '';
					if (group && !itemGroups.includes(group)) itemGroups.push(group);
					if (plant) {
						if (!plants[plant]) plants[plant] = {};
						plants[plant][group] = { qty: flt(row.qty), value: flt(row.stock_value || 0) };
					}
				});
				const plantNames = Object.keys(plants);
				const groupQty   = itemGroups.map(g => plantNames.reduce((s,p) => s + (plants[p][g]?.qty   || 0), 0));
				const groupVal   = itemGroups.map(g => plantNames.reduce((s,p) => s + (plants[p][g]?.value || 0), 0));
				return { itemGroups, plants, plantNames, groupQty, groupVal };
			}

			const store = parseRows(storeRows);
			const pest  = parseRows(pestRows);

			if (!storeRows.length && !pestRows.length) {
				$('<div class="gp-main">').append('<div class="gp-empty-state">No stock data found.</div>').appendTo(root);
				return;
			}

			/* ── SIDEBAR ── */
			const sidebar = $(`
				<div class="gp-sidebar">
					<div class="gp-sidebar-logo">
						<div class="gp-sidebar-logo-icon">🌿</div>
						<div>
							<div class="gp-sidebar-logo-text">Stock Hub</div>
							<div class="gp-sidebar-logo-sub">Gen & Pesticides</div>
						</div>
					</div>
					<div class="gp-nav-section">Store Items</div>
					<div class="gp-nav-item active" data-view="store-dashboard"><span class="gp-nav-icon">📊</span> Dashboard</div>
					<div class="gp-nav-item" data-view="store-plants"><span class="gp-nav-icon">🏭</span> Plants</div>
					<div class="gp-nav-divider"></div>
					<div class="gp-nav-section">Pesticides</div>
					<div class="gp-nav-item" data-view="pest-dashboard"><span class="gp-nav-icon">🌿</span> Dashboard</div>
					<div class="gp-nav-item" data-view="pest-plants"><span class="gp-nav-icon">🏭</span> Plants</div>
				</div>
			`).appendTo(root);

			/* ── MAIN ── */
			const main   = $('<div class="gp-main">').appendTo(root);
			const topbar = $(`
				<div class="gp-topbar">
					<div class="gp-topbar-left" id="gp-topbar-title">
						Store Items — Dashboard
						<span class="gp-topbar-date">${new Date().toLocaleDateString('en-IN',{day:'2-digit',month:'short',year:'numeric'})}</span>
					</div>
					<div class="gp-topbar-right">
						<span class="gp-topbar-badge" id="gp-badge-store">🏭 ${store.plantNames.length} Plants</span>
						<span class="gp-topbar-badge pest" id="gp-badge-pest">🌿 ${pest.plantNames.length} Plants</span>
						<button class="gp-refresh-btn" id="gp-refresh-btn">↻ Refresh</button>
					</div>
				</div>
			`).appendTo(main);

			topbar.find('#gp-refresh-btn').on('click', () => { root.empty(); load_gp_dashboard(root); });

			const content = $('<div class="gp-content">').appendTo(main);

			/* ══════════════════════════════════════════════════════════
			   GENERIC DASHBOARD VIEW BUILDER
			══════════════════════════════════════════════════════════ */
			function buildDashboardView(viewId, dataset, cfg) {
				const { itemGroups, plants, plantNames, groupQty, groupVal } = dataset;
				const totalQty  = groupQty.reduce((a,b) => a+b, 0);
				const totalVal  = groupVal.reduce((a,b) => a+b, 0);
				const topGi     = groupQty.indexOf(Math.max(...groupQty));
				const topGroup  = itemGroups[topGi] || '—';
				const plantTotQ = plantNames.map(p => itemGroups.reduce((s,g) => s + (plants[p][g]?.qty || 0), 0));
				const topPi     = plantTotQ.indexOf(Math.max(...plantTotQ));
				const topPlant  = plantNames[topPi] || '—';

				const plantColorIdx = {};
				plantNames.forEach((p,i) => { plantColorIdx[p] = i; });

				const view = $(`<div class="gp-view" id="${viewId}">`).appendTo(content);

				/* Banner */
				view.append(`
					<div class="gp-section-banner ${cfg.bannerCls}">
						<div class="gp-section-banner-icon">${cfg.icon}</div>
						<div>
							<div class="gp-section-banner-title">${cfg.title}</div>
							<div class="gp-section-banner-sub">${cfg.subtitle} · ${itemGroups.length} groups · ${plantNames.length} plants</div>
						</div>
					</div>
				`);

				/* KPI cards */
				const kpiRow = $('<div class="gp-kpi-row">').appendTo(view);
				[
					{ label:'Total Qty',    val:format_number(totalQty),            sub:itemGroups.length+' Item Groups',          icon:'📦', cls:'c-blue'   },
					{ label:'Stock Value',  val:'₹ '+fmt(totalVal),                 sub:'Current valuation',                       icon:'💰', cls:'c-green'  },
					{ label:'Top Category',val:topGroup,                            sub:format_number(groupQty[topGi])+' units',   icon:'🏆', cls:'c-orange' },
					{ label:'Top Plant',   val:topPlant,                            sub:format_number(plantTotQ[topPi])+' units',  icon:'🏭', cls:'c-purple' },
				].forEach(k => kpiRow.append(`
					<div class="gp-kpi-card ${k.cls}">
						<div class="gp-kpi-icon">${k.icon}</div>
						<div class="gp-kpi-label">${k.label}</div>
						<div class="gp-kpi-val">${k.val}</div>
						<div class="gp-kpi-sub">${k.sub}</div>
					</div>
				`));

				/* Tab bar */
				const uid    = viewId.replace(/[^a-z]/g,'');
				const tabBar = $(`
					<div class="gp-tab-bar">
						<div class="gp-tab active" data-tab="qty">Quantity</div>
						<div class="gp-tab" data-tab="value">Value (₹)</div>
						<div class="gp-tab-spacer"></div>
						<div style="display:flex;gap:4px;">
							<button class="gp-vtbtn active" data-m="qty">Qty</button>
							<button class="gp-vtbtn" data-m="value">Value</button>
						</div>
					</div>
				`).appendTo(view);

				/* Chart + rank panel */
				$(`
					<div class="gp-main-panel">
						<div>
							<div class="gp-chart-title" id="${uid}-chart-title">Stock Qty by Item Group</div>
							<div class="gp-chart-wrap"><canvas id="${uid}-bar-canvas"></canvas></div>
						</div>
						<div>
							<div class="gp-rank-title" id="${uid}-rank-title">Top Groups by Qty</div>
							<div id="${uid}-rank-list"></div>
						</div>
					</div>
				`).appendTo(view);

				/* Pie section header */
				view.append(`
					<div class="gp-sec-hd">
						<span>PLANT-WISE BREAKDOWN PER ITEM GROUP</span>
						<span>Click any card to see items ↓</span>
					</div>
				`);
				const pieContainer = $(`<div id="${uid}-pie-container">`).appendTo(view);

				/* ── Bar label plugin ── */
				const barLabelPlugin = {
					id: 'gpBarLabels_'+uid,
					afterDatasetsDraw(chart) {
						const { ctx, data } = chart;
						const isVal = chart._gpIsVal;
						ctx.save();
						chart.getDatasetMeta(0).data.forEach((bar, i) => {
							const val = data.datasets[0].data[i];
							if (!val) return;
							const label = isVal ? '₹'+fmt(val) : format_number(val);
							ctx.font = '600 11px Inter, sans-serif';
							ctx.fillStyle = '#334155';
							ctx.textAlign = 'center';
							ctx.textBaseline = 'bottom';
							ctx.fillText(label, bar.x, bar.y - 4);
						});
						ctx.restore();
					}
				};

				let barInst = null;
				function updateBarAndRank(metric) {
					const isVal = metric === 'value';
					const data  = isVal ? groupVal : groupQty;
					$(`#${uid}-chart-title`).text((isVal ? 'Stock Value (₹)' : 'Stock Qty') + ' by Item Group');
					$(`#${uid}-rank-title`).text('Top Groups by ' + (isVal ? 'Value' : 'Qty'));
					const canvas = document.getElementById(`${uid}-bar-canvas`);
					if (barInst) { barInst.destroy(); barInst = null; }
					if (canvas) {
						barInst = new Chart(canvas, {
							type: 'bar',
							plugins: [barLabelPlugin],
							data: {
								labels: itemGroups,
								datasets: [{
									data,
									backgroundColor: itemGroups.map((_,i) => COLORS[i%COLORS.length].bg),
									borderColor    : itemGroups.map((_,i) => COLORS[i%COLORS.length].border),
									borderWidth:2, borderRadius:6, borderSkipped:false
								}]
							},
							options: {
								responsive:true, maintainAspectRatio:false,
								layout:{ padding:{ top:24 } },
								plugins:{ legend:{display:false}, tooltip:{enabled:false} },
								scales:{
									x:{ ticks:{font:{family:'Inter',size:11,weight:'500'},color:'#64748B',maxRotation:30}, grid:{display:false}, border:{display:false} },
									y:{ ticks:{font:{family:'Inter',size:11},color:'#94A3B8',callback:v=>isVal?'₹'+fmt(v):fmt(v)}, grid:{color:'#F1F5F9'}, border:{display:false} }
								}
							}
						});
						barInst._gpIsVal = isVal;
					}
					const sorted = itemGroups.map((g,i) => ({name:g,qty:groupQty[i],value:groupVal[i]}))
						.sort((a,b) => isVal ? b.value-a.value : b.qty-a.qty);
					const rankEl = $(`#${uid}-rank-list`).empty();
					sorted.slice(0,8).forEach((d,i) => {
						rankEl.append(`
							<div class="gp-rank-row">
								<span class="gp-rank-num ${i<3?'top':'mid'}">${i+1}</span>
								<span class="gp-rank-name" title="${d.name}">${d.name}</span>
								<div style="text-align:right;">
									<div class="gp-rank-val">${isVal?'₹'+fmt(d.value):format_number(d.qty)}</div>
									<div class="gp-rank-subval">${isVal?format_number(d.qty)+' units':'₹'+fmt(d.value)}</div>
								</div>
							</div>
						`);
					});
				}

				tabBar.on('click', '.gp-tab', function() {
					tabBar.find('.gp-tab,.gp-vtbtn').removeClass('active');
					$(this).addClass('active');
					const m = $(this).data('tab');
					tabBar.find(`.gp-vtbtn[data-m="${m}"]`).addClass('active');
					updateBarAndRank(m);
				});
				tabBar.on('click', '.gp-vtbtn', function() {
					tabBar.find('.gp-tab,.gp-vtbtn').removeClass('active');
					$(this).addClass('active');
					const m = $(this).data('m');
					tabBar.find(`.gp-tab[data-tab="${m}"]`).addClass('active');
					updateBarAndRank(m);
				});

				/* ══════════════════════════════════════════════════════
				   SVG DONUT  — handles 1-plant (full ring) and N-plant
				══════════════════════════════════════════════════════ */
				function buildSVGDonut(containerId, chartData) {
					const VW=800, VH=500, CX=400, CY=250;
					const R_OUT=140, R_IN=86, ELBOW_R=170;
					const LINE_H=26, MIN_PCT=0.03, L_TICK_X=228, R_TICK_X=572;
					const svgNS = 'http://www.w3.org/2000/svg';

					const svg = document.createElementNS(svgNS, 'svg');
					svg.setAttribute('viewBox', `0 0 ${VW} ${VH}`);
					svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
					svg.setAttribute('width', '100%');
					svg.setAttribute('height', '100%');

					const polar   = (cx,cy,r,a) => ({ x: cx + r*Math.cos(a), y: cy + r*Math.sin(a) });
					const arcPath = (cx,cy,rO,rI,a1,a2) => {
						const p1=polar(cx,cy,rO,a1), p2=polar(cx,cy,rO,a2);
						const p3=polar(cx,cy,rI,a2), p4=polar(cx,cy,rI,a1);
						const lg = (a2-a1) > Math.PI ? 1 : 0;
						return `M${p1.x} ${p1.y} A${rO} ${rO} 0 ${lg} 1 ${p2.x} ${p2.y} L${p3.x} ${p3.y} A${rI} ${rI} 0 ${lg} 0 ${p4.x} ${p4.y}Z`;
					};

					const total      = chartData.reduce((s,d) => s+d.qty, 0) || 1;
					let   startAngle = -Math.PI / 2;
					const sliceLayer = document.createElementNS(svgNS, 'g');
					const labelLayer = document.createElementNS(svgNS, 'g');
					svg.appendChild(sliceLayer);
					const rawLabels  = [];

					/* ── Single-plant special case: arc math is degenerate for 360° ── */
					if (chartData.length === 1) {
						const clr = COLORS[plantColorIdx[chartData[0].plant] % COLORS.length];
						const rMid = (R_OUT + R_IN) / 2;

						/* Filled ring */
						const outerRing = document.createElementNS(svgNS, 'circle');
						outerRing.setAttribute('cx', CX);
						outerRing.setAttribute('cy', CY);
						outerRing.setAttribute('r',  rMid);
						outerRing.setAttribute('fill',         'none');
						outerRing.setAttribute('stroke',       clr.bg);
						outerRing.setAttribute('stroke-width', R_OUT - R_IN);
						sliceLayer.appendChild(outerRing);

						/* Border ring */
						const borderRing = document.createElementNS(svgNS, 'circle');
						borderRing.setAttribute('cx', CX);
						borderRing.setAttribute('cy', CY);
						borderRing.setAttribute('r',  rMid);
						borderRing.setAttribute('fill',         'none');
						borderRing.setAttribute('stroke',       clr.border);
						borderRing.setAttribute('stroke-width', '2');
						sliceLayer.appendChild(borderRing);

						/* Hover effect via JS */
						outerRing.addEventListener('mouseenter', () => outerRing.setAttribute('stroke', clr.border));
						outerRing.addEventListener('mouseleave', () => outerRing.setAttribute('stroke', clr.bg));

						/* Single label on the right at 3 o'clock */
						rawLabels.push({
							mid:      0,
							anchorPt: polar(CX, CY, R_OUT + 8, 0),
							elbowPt:  polar(CX, CY, ELBOW_R,   0),
							naturalY: polar(CX, CY, ELBOW_R,   0).y,
							onRight:  true,
							label:    chartData[0].plant,
							qty:      chartData[0].qty,
							pct:      100,
							clr,
							show:     true
						});

					} else {
						/* ── Normal multi-slice path ── */
						chartData.forEach((d) => {
							const frac  = d.qty / total;
							const sweep = frac * 2 * Math.PI;
							const end   = startAngle + sweep;
							const mid   = startAngle + sweep / 2;
							const clr   = COLORS[plantColorIdx[d.plant] % COLORS.length];

							const path = document.createElementNS(svgNS, 'path');
							path.setAttribute('d',            arcPath(CX, CY, R_OUT, R_IN, startAngle, end));
							path.setAttribute('fill',         clr.bg);
							path.setAttribute('stroke',       clr.border);
							path.setAttribute('stroke-width', '2');
							path.style.transition = 'fill .12s';
							path.addEventListener('mouseenter', () => path.setAttribute('fill', clr.border));
							path.addEventListener('mouseleave', () => path.setAttribute('fill', clr.bg));
							sliceLayer.appendChild(path);

							const onRight = Math.cos(mid) >= 0;
							rawLabels.push({
								mid,
								anchorPt: polar(CX, CY, R_OUT + 8, mid),
								elbowPt:  polar(CX, CY, ELBOW_R,   mid),
								naturalY: polar(CX, CY, ELBOW_R,   mid).y,
								onRight,
								label: d.plant,
								qty:   d.qty,
								pct:   Math.round(frac * 100),
								clr,
								show:  frac >= MIN_PCT
							});
							startAngle = end;
						});
					}

					/* ── De-overlap labels ── */
					function deOverlap(items) {
						items.sort((a,b) => a.naturalY - b.naturalY);
						for (let i=1; i<items.length; i++)
							if (items[i].adjY - items[i-1].adjY < LINE_H)
								items[i].adjY = items[i-1].adjY + LINE_H;
						for (let i=items.length-2; i>=0; i--)
							if (items[i+1].adjY - items[i].adjY < LINE_H)
								items[i].adjY = items[i+1].adjY - LINE_H;
						items.forEach(it => { it.adjY = Math.max(20, Math.min(VH-20, it.adjY)); });
					}
					const leftItems  = rawLabels.filter(l => l.show && !l.onRight).map(l => ({...l, adjY: l.naturalY}));
					const rightItems = rawLabels.filter(l => l.show &&  l.onRight).map(l => ({...l, adjY: l.naturalY}));
					deOverlap(leftItems);
					deOverlap(rightItems);
					svg.appendChild(labelLayer);

					/* ── Draw leader lines + text ── */
					[...leftItems, ...rightItems].forEach(info => {
						const tickX  = info.onRight ? R_TICK_X : L_TICK_X;
						const finalY = info.adjY;
						const ang = info.mid, asz = 5;
						const ax = info.anchorPt.x, ay = info.anchorPt.y;

						/* Arrow tip at slice edge */
						const arrow = document.createElementNS(svgNS, 'polygon');
						arrow.setAttribute('points', [
							`${ax},${ay}`,
							`${ax - asz*Math.cos(ang-0.45)},${ay - asz*Math.sin(ang-0.45)}`,
							`${ax - asz*Math.cos(ang+0.45)},${ay - asz*Math.sin(ang+0.45)}`
						].join(' '));
						arrow.setAttribute('fill', info.clr.border);
						labelLayer.appendChild(arrow);

						const mkLine = (x1,y1,x2,y2,dash) => {
							const l = document.createElementNS(svgNS, 'line');
							l.setAttribute('x1', x1); l.setAttribute('y1', y1);
							l.setAttribute('x2', x2); l.setAttribute('y2', y2);
							l.setAttribute('stroke',       info.clr.border);
							l.setAttribute('stroke-width', '1.3');
							l.setAttribute('stroke-linecap', 'round');
							if (dash) l.setAttribute('stroke-dasharray', '3 2');
							return l;
						};

						/* Diagonal leg */
						labelLayer.appendChild(mkLine(info.anchorPt.x, info.anchorPt.y, info.elbowPt.x, info.elbowPt.y, false));
						/* Vertical adjust (dashed) if label was nudged */
						if (Math.abs(info.elbowPt.y - finalY) > 2)
							labelLayer.appendChild(mkLine(info.elbowPt.x, info.elbowPt.y, info.elbowPt.x, finalY, true));
						/* Horizontal tick */
						labelLayer.appendChild(mkLine(info.elbowPt.x, finalY, tickX, finalY, false));

						/* Dot at tick end */
						const dot = document.createElementNS(svgNS, 'circle');
						dot.setAttribute('cx', tickX); dot.setAttribute('cy', finalY);
						dot.setAttribute('r', '2.5'); dot.setAttribute('fill', info.clr.border);
						labelLayer.appendChild(dot);

						/* Text */
						const anchor    = info.onRight ? 'start' : 'end';
						const textX     = info.onRight ? tickX + 5 : tickX - 5;
						const shortName = info.label.length > 18 ? info.label.slice(0,17)+'…' : info.label;

						const mkText = (x,y,content,size,weight,fill) => {
							const t = document.createElementNS(svgNS, 'text');
							t.setAttribute('x', x); t.setAttribute('y', y);
							t.setAttribute('text-anchor',  anchor);
							t.setAttribute('font-family',  'Inter, sans-serif');
							t.setAttribute('font-size',    size);
							t.setAttribute('font-weight',  weight);
							t.setAttribute('fill',         fill);
							t.textContent = content;
							return t;
						};
						labelLayer.appendChild(mkText(textX, finalY-4, shortName, '10.5', '700', '#1E293B'));
						labelLayer.appendChild(mkText(textX, finalY+9, `${format_number(info.qty)} · ${info.pct}%`, '10', '600', info.clr.border));
					});

					/* Centre label */
					const mkCentre = (y, content, size, weight, fill) => {
						const t = document.createElementNS(svgNS, 'text');
						t.setAttribute('x', CX); t.setAttribute('y', y);
						t.setAttribute('text-anchor', 'middle');
						t.setAttribute('font-family', 'Inter, sans-serif');
						t.setAttribute('font-size',   size);
						t.setAttribute('font-weight', weight);
						t.setAttribute('fill',        fill);
						t.textContent = content;
						svg.appendChild(t);
					};
					mkCentre(CY+6,  chartData.length, '28', '800', '#1E293B');
					mkCentre(CY+21, 'PLANTS',          '9',  '600', '#94A3B8');

					const wrap = document.getElementById(containerId);
					if (wrap) wrap.appendChild(svg);
				}

				/* ── Pie cards ── */
				function buildPieCards() {
					itemGroups.forEach((group, gi) => {
						const cardUid   = `${uid}-${gi}`;
						const plantData = plantNames
							.map(p => ({ plant:p, qty:plants[p][group]?.qty||0, value:plants[p][group]?.value||0 }))
							.filter(d => d.qty > 0 || d.value > 0)
							.sort((a,b) => b.qty - a.qty);
						const gQty = groupQty[gi], gVal = groupVal[gi], maxQ = plantData[0]?.qty || 1;

						const card = $(`
							<div class="gp-pie-card" data-cuid="${cardUid}">
								<div class="gp-pie-card-hd">
									<div>
										<div class="gp-pie-card-name">${group}</div>
										<div class="gp-pie-card-sub">${plantData.length} plant(s) with stock</div>
									</div>
									<div class="gp-pie-card-badges">
										<div class="gp-badge-qty">📦 ${format_number(gQty)}</div>
										${gVal > 0 ? `<div class="gp-badge-val">₹ ${fmt(gVal)}</div>` : ''}
									</div>
								</div>
								<div class="gp-pie-body">
									<div class="gp-donut-svg-wrap" id="gp-donut-wrap-${cardUid}"></div>
									<div style="overflow-x:auto;">
										<table class="gp-leg-table">
											<thead><tr>
												<th>Plant</th><th>Qty</th><th>Value (₹)</th><th>Share</th>
												<th style="min-width:80px;">Distribution</th>
											</tr></thead>
											<tbody id="gp-leg-body-${cardUid}"></tbody>
										</table>
									</div>
								</div>
							</div>
						`);
						pieContainer.append(card);

						const tbody = $(`#gp-leg-body-${cardUid}`);
						plantData.forEach(d => {
							const ci   = plantColorIdx[d.plant] % COLORS.length;
							const clr  = COLORS[ci];
							const pct  = gQty ? Math.round(d.qty / gQty * 100) : 0;
							const barW = Math.round(d.qty / maxQ * 100);
							tbody.append(`
								<tr>
									<td><div class="gp-leg-dot-cell"><span class="gp-leg-dot" style="background:${clr.border};"></span><span class="gp-leg-plant-name">${d.plant}</span></div></td>
									<td style="font-weight:700;">${format_number(d.qty)}</td>
									<td style="font-weight:600;color:#059669;">${d.value > 0 ? '₹'+fmt(d.value) : '—'}</td>
									<td><span class="gp-pct-badge" style="background:${clr.bg};color:${clr.border};">${pct}%</span></td>
									<td><div class="gp-bar-inline-wrap"><div class="gp-bar-inline-fill" style="width:${barW}%;background:${clr.border};"></div></div></td>
								</tr>
							`);
						});

						buildSVGDonut(`gp-donut-wrap-${cardUid}`, plantData);

						card.on('click', function() {
							const panel   = $(`#gp-items-panel-${cardUid}`);
							const wasOpen = panel.hasClass('open');
							pieContainer.find('.gp-items-panel').removeClass('open');
							pieContainer.find('.gp-pie-card').removeClass('active');
							if (!wasOpen) {
								$(this).addClass('active');
								panel.addClass('open');
								loadItems(cardUid, group, cfg.category);
								setTimeout(() => panel[0]?.scrollIntoView({behavior:'smooth', block:'nearest'}), 60);
							}
						});

						const panel = $(`
							<div class="gp-items-panel" id="gp-items-panel-${cardUid}">
								<div class="gp-items-panel-hd">
									<div class="gp-items-panel-title">📦 Items — ${group}</div>
									<button class="gp-items-close" title="Close">&#x2715;</button>
								</div>
								<div id="gp-items-body-${cardUid}"><div class="gp-loading">Loading…</div></div>
							</div>
						`);
						pieContainer.append(panel);
						panel.find('.gp-items-close').on('click', e => {
							e.stopPropagation();
							panel.removeClass('open');
							pieContainer.find(`.gp-pie-card[data-cuid="${cardUid}"]`).removeClass('active');
						});
					});
				}

				return function init() {
					updateBarAndRank('qty');
					buildPieCards();
				};
			}

			/* ── Items loader ── */
			function loadItems(cardUid, group, category) {
				const bodyEl = $(`#gp-items-body-${cardUid}`);
				if (!bodyEl.find('.gp-loading').length) return;
				frappe.call({
					method: 'informatics_custom_apps.ripl_customized_apps.page.general_and_pesticid.general_and_pesticid.get_items_for_group',
					args: { item_group: group, category: category },
					callback(ir) {
						const items = (ir.message || []).sort((a,b) => flt(b.qty) - flt(a.qty));
						if (!items.length) { bodyEl.html('<div class="gp-loading">No items found.</div>'); return; }
						const iTotal = items.reduce((s,d) => s + flt(d.qty), 0) || 1;
						let tRows = '';
						items.forEach((d,i) => {
							const qty  = flt(d.qty);
							const val  = flt(d.stock_value || d.value || 0);
							const qpct = Math.round(qty / iTotal * 100);
							const ci   = i % COLORS.length;
							tRows += `<tr>
								<td><span class="gp-rank-badge ${i<3?'top3':'rest'}">${i+1}</span></td>
								<td>
									<div style="font-weight:700;">${d.item_name || d.item_code}</div>
									<div style="font-size:11px;color:#94A3B8;">${d.item_code} · ${d.real_item_group || ''}</div>
								</td>
								<td><div style="font-weight:700;">${format_number(qty)}</div><div style="font-size:10px;color:#94A3B8;">${d.uom || '—'}</div></td>
								<td style="font-weight:700;color:#059669;">${val > 0 ? '₹'+fmt(val) : '—'}</td>
								<td>
									<div style="font-size:11px;font-weight:700;color:${COLORS[ci].border};margin-bottom:3px;">${qpct}%</div>
									<div class="gp-bar-mini-wrap"><div class="gp-bar-mini-fill" style="width:${qpct}%;background:${COLORS[ci].border};"></div></div>
								</td>
							</tr>`;
						});
						bodyEl.html(`<div style="overflow-x:auto;"><table class="gp-items-table"><thead><tr><th>#</th><th>Item</th><th>Qty</th><th>Value (₹)</th><th>Qty Share</th></tr></thead><tbody>${tRows}</tbody></table></div>`);
					}
				});
			}

			/* ── Plants view builder ── */
			function buildPlantsView(viewId, dataset) {
				const { itemGroups, plants, plantNames } = dataset;
				const plantTotQ = plantNames.map(p => itemGroups.reduce((s,g) => s + (plants[p][g]?.qty   || 0), 0));
				const plantTotV = plantNames.map(p => itemGroups.reduce((s,g) => s + (plants[p][g]?.value || 0), 0));
				const totalQty  = plantTotQ.reduce((a,b) => a+b, 0);
				const plantRows = plantNames
					.map((p,i) => ({ name:p, qty:plantTotQ[i], value:plantTotV[i] }))
					.sort((a,b) => b.qty - a.qty);
				const maxPQ = plantRows[0]?.qty || 1;

				const view = $(`<div class="gp-view" id="${viewId}">`).appendTo(content);
				view.append(`<div class="gp-sec-hd" style="margin-bottom:16px;"><span>ALL PLANTS</span><span>${plantNames.length} plants</span></div>`);
				const ptWrap = $('<div class="gp-plant-table-wrap">').appendTo(view);
				let pRows = '';
				plantRows.forEach((d,i) => {
					const barW  = Math.round(d.qty / maxPQ * 100);
					const ci    = i % COLORS.length;
					const share = totalQty ? Math.round(d.qty / totalQty * 100) : 0;
					pRows += `<tr>
						<td><span class="gp-rank-badge ${i<3?'top3':'rest'}">${i+1}</span></td>
						<td style="font-weight:700;">${d.name}</td>
						<td style="font-weight:700;">${format_number(d.qty)}</td>
						<td style="font-weight:600;color:#059669;">${d.value > 0 ? '₹'+fmt(d.value) : '—'}</td>
						<td style="min-width:120px;">
							<div style="font-size:11px;font-weight:700;color:${COLORS[ci].border};margin-bottom:3px;">${share}%</div>
							<div style="background:#F1F5F9;border-radius:3px;height:6px;"><div style="width:${barW}%;background:${COLORS[ci].border};height:100%;border-radius:3px;"></div></div>
						</td>
					</tr>`;
				});
				ptWrap.html(`
					<table class="gp-plant-table">
						<thead><tr><th>#</th><th>Plant</th><th>Total Qty</th><th>Stock Value</th><th>Share</th></tr></thead>
						<tbody>${pRows}</tbody>
					</table>
				`);
			}

			/* ── Build all 4 views ── */
			const initStore = buildDashboardView('gp-view-store-dashboard', store, {
				icon:'📦', title:'Store Items', subtitle:'All store item groups',
				bannerCls:'store', category:'store_items'
			});
			buildPlantsView('gp-view-store-plants', store);

			const initPest = buildDashboardView('gp-view-pest-dashboard', pest, {
				icon:'🌿', title:'Pesticides', subtitle:'GST slab breakdown',
				bannerCls:'pest', category:'pesticides'
			});
			buildPlantsView('gp-view-pest-plants', pest);

			/* ── Sidebar nav ── */
			const VIEW_TITLES = {
				'store-dashboard' : 'Store Items — Dashboard',
				'store-plants'    : 'Store Items — Plants',
				'pest-dashboard'  : 'Pesticides — Dashboard',
				'pest-plants'     : 'Pesticides — Plants',
			};

			sidebar.on('click', '.gp-nav-item', function() {
				const viewKey = $(this).data('view');
				if (!viewKey) return;
				sidebar.find('.gp-nav-item').removeClass('active');
				$(this).addClass('active');
				$('#gp-topbar-title').contents().first().replaceWith(VIEW_TITLES[viewKey] || viewKey);
				content.find('.gp-view').removeClass('active');
				$(`#gp-view-${viewKey}`).addClass('active');
				content[0].scrollTop = 0;
			});

			/* Set first view active */
			$('#gp-view-store-dashboard').addClass('active');

			/* ── Init charts after Chart.js ── */
			function initAll() { initStore(); initPest(); }
			if (window.Chart) { initAll(); }
			else {
				const s = document.createElement('script');
				s.src = 'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js';
				s.onload = initAll;
				document.head.appendChild(s);
			}
		},
		error() {
			frappe.dom.unfreeze();
			frappe.msgprint({ title:'Error', message:'Unable to load stock summary', indicator:'red' });
		}
	});
}