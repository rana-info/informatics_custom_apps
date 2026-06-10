// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["FG Stock Balance - MGT"] = {
	filters: [
		{
			fieldname: "company",
			label: "Company",
			fieldtype: "MultiSelectList",
			get_data: function (txt) {
				return frappe.db.get_link_options("Company", txt);
			}
		},
		{
			fieldname: "plant",
			label: "Plant",
			fieldtype: "MultiSelectList",
			get_data: async function (txt) {
				let companies = frappe.query_report.get_filter_value("company") || [];
				let filters = {};
				if (companies.length) filters.company = ["in", companies];
				return frappe.db.get_link_options("Branch", txt, filters);
			}
		}
	],
	refresh: function (report) { fgs_handle_render(report); },
	after_datatable_render: function () { fgs_handle_render(frappe.query_report); },
};

// ── Cleanup on route change ──
(function () {
	var reportName = "FG Stock Balance - MGT";
	function fgsCleanup() {
		var r = frappe.get_route();
		if (!(r && r[0] === "query-report" && r[1] === reportName)) {
			$("#fgs-wrapper").remove();
			(window._fgsPerPlantCharts || []).forEach(function (c) { try { c.destroy(); } catch (e) {} });
			window._fgsPerPlantCharts = [];
		}
	}
	$(document).on("page-change", fgsCleanup);
	frappe.router.on("change", fgsCleanup);
})();

window._fgsRenderTimer = null;
function fgs_handle_render(report) {
	if (window._fgsRenderTimer) clearTimeout(window._fgsRenderTimer);
	window._fgsRenderTimer = setTimeout(function () {
		var hasData = (report.data || []).length > 0;
		if (hasData) {
			fgs_render(report);
		} else {
			$("#fgs-wrapper").remove();
			(window._fgsPerPlantCharts || []).forEach(function (c) { try { c.destroy(); } catch (e) {} });
			window._fgsPerPlantCharts = [];
		}
	}, 300);
}

var FGS_PAL = [
	"#93C5FD","#86EFAC","#FCA5A5","#FCD34D","#C4B5FD",
	"#6EE7B7","#FDA4AF","#7DD3FC","#A5F3FC","#FDE68A",
	"#BBF7D0","#FECACA","#BAE6FD","#DDD6FE","#FEF08A",
];
var FGS_PAL_BORDER = [
	"#3B82F6","#22C55E","#EF4444","#F59E0B","#8B5CF6",
	"#10B981","#F43F5E","#0EA5E9","#06B6D4","#EAB308",
	"#16A34A","#DC2626","#0284C7","#7C3AED","#CA8A04",
];

// ── 3D Bar Plugin ──
var FGS_3D_PLUGIN = {
	id: "fgs3dBars",
	afterDatasetsDraw: function (chart) {
		var ctx = chart.ctx;
		ctx.save();
		chart.data.datasets.forEach(function (dataset, di) {
			var meta = chart.getDatasetMeta(di);
			if (meta.hidden) return;
			var bgColors = Array.isArray(dataset.backgroundColor)
				? dataset.backgroundColor : [dataset.backgroundColor];
			meta.data.forEach(function (bar, i) {
				var color = bgColors[i % bgColors.length] || "#93C5FD";
				var depth = 6;
				var darken = function (hex, amt) {
					hex = hex.replace("#", "");
					if (hex.length === 3) hex = hex[0]+hex[0]+hex[1]+hex[1]+hex[2]+hex[2];
					var r = Math.max(0, parseInt(hex.substr(0,2),16) - amt);
					var g = Math.max(0, parseInt(hex.substr(2,2),16) - amt);
					var b = Math.max(0, parseInt(hex.substr(4,2),16) - amt);
					return "rgb("+r+","+g+","+b+")";
				};
				var x = bar.x - bar.width / 2;
				var y = bar.y;
				var w = bar.width;
				var h = Math.abs(bar.base - bar.y);
				if (h < 2) return;
				ctx.beginPath();
				ctx.moveTo(x+w, y); ctx.lineTo(x+w+depth, y-depth);
				ctx.lineTo(x+w+depth, y-depth+h); ctx.lineTo(x+w, y+h);
				ctx.closePath(); ctx.fillStyle = darken(color, 50); ctx.fill();
				ctx.beginPath();
				ctx.moveTo(x, y); ctx.lineTo(x+depth, y-depth);
				ctx.lineTo(x+w+depth, y-depth); ctx.lineTo(x+w, y);
				ctx.closePath(); ctx.fillStyle = darken(color, 22); ctx.fill();
			});
		});
		ctx.restore();
	}
};

// ── Value label above bar — drawn AFTER min-bar so always on top ──
// (label plugin is intentionally a no-op; labels are drawn inside makeMinBarPlugin)
function makeLabelPlugin(id) {
	return { id: id, afterDatasetsDraw: function () {} };
}

// ── Min-bar-height enforcer + value label painter (single pass, correct z-order) ──
var MIN_BAR_PX = 28;
function makeMinBarPlugin(id, bgColorsRef) {
	return {
		id: id,
		afterDatasetsDraw: function (chart) {
			var ctx = chart.ctx;
			var fmtS = window._fgsFmtS || function(n){ return String(Math.round(n)); };
			// Top of the chart's plot area — labels must not go above this
			var chartTop = chart.chartArea ? chart.chartArea.top : 36;

			ctx.save();
			chart.data.datasets.forEach(function (dataset, di) {
				var meta = chart.getDatasetMeta(di);
				if (meta.hidden) return;
				var bgColors = bgColorsRef || (Array.isArray(dataset.backgroundColor)
					? dataset.backgroundColor : [dataset.backgroundColor]);

				meta.data.forEach(function (bar, i) {
					var value = dataset.data[i];
					var h = Math.abs(bar.base - bar.y);

					// ── 1. Draw min-height bar overlay for tiny bars ──
					var barTopY = bar.y; // actual rendered top of bar
					if (h < MIN_BAR_PX) {
						var color = bgColors[i % bgColors.length] || "#93C5FD";
						var x = bar.x - bar.width / 2;
						var y = bar.base - MIN_BAR_PX;
						var w = bar.width;
						barTopY = y; // min-bar top
						ctx.beginPath();
						var r = 5;
						ctx.moveTo(x + r, y);
						ctx.lineTo(x + w - r, y);
						ctx.quadraticCurveTo(x + w, y, x + w, y + r);
						ctx.lineTo(x + w, y + MIN_BAR_PX);
						ctx.lineTo(x, y + MIN_BAR_PX);
						ctx.lineTo(x, y + r);
						ctx.quadraticCurveTo(x, y, x + r, y);
						ctx.closePath();
						ctx.fillStyle = color;
						ctx.fill();
						ctx.strokeStyle = FGS_PAL_BORDER[i % FGS_PAL_BORDER.length];
						ctx.lineWidth = 2;
						ctx.stroke();
					}

					// ── 2. Draw value label above the rendered bar top ──
					if (!value) return;
					var label = fmtS(value);
					ctx.font = "800 13px -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif";
					var textW = ctx.measureText(label).width;
					var padX = 6;
					var bw = textW + padX * 2;
					var bh = 18;
					// Position label above bar; clamp so it never clips above chartArea
					var by = barTopY - bh - 4;
					if (by < chartTop) by = chartTop;

					var bx = bar.x - bw / 2;

					// Pill background
					ctx.beginPath();
					if (ctx.roundRect) {
						ctx.roundRect(bx, by, bw, bh, 5);
					} else {
						ctx.rect(bx, by, bw, bh);
					}
					ctx.fillStyle = "rgba(30,64,175,0.13)";
					ctx.fill();

					// Label text
					ctx.fillStyle = "#1e3a8a";
					ctx.textAlign = "center";
					ctx.textBaseline = "middle";
					ctx.fillText(label, bar.x, by + bh / 2);
				});
			});
			ctx.restore();
		}
	};
}

// ── Dynamic chart height based on group count ──
function chartHeight(n) {
	if (n <= 2) return 220;
	if (n <= 4) return 260;
	if (n <= 7) return 290;
	return 320;
}

// ── Layout: decide columns for each plant ──
function buildRows(plants, activeGroups) {
	var rows = [];
	var i = 0;
	while (i < plants.length) {
		var p = plants[i];
		var gc = (activeGroups[p] || []).length;
		if (gc > 4) {
			rows.push([i]);
			i++;
		} else {
			var next = i + 1;
			if (next < plants.length && (activeGroups[plants[next]] || []).length <= 4) {
				rows.push([i, next]);
				i += 2;
			} else {
				rows.push([i]);
				i++;
			}
		}
	}
	return rows;
}

function fgs_render(report) {
	$("#fgs-wrapper").remove();
	(window._fgsPerPlantCharts || []).forEach(function (c) { try { c.destroy(); } catch (e) {} });
	window._fgsPerPlantCharts = [];

	var rows = report.data || [];
	if (!rows.length) return;

	var fmt  = function (n) { return Number(n).toLocaleString("en-IN"); };
	var fmtS = function (n) {
		if (n >= 1e7) return (n / 1e7).toFixed(2) + " Cr";
		if (n >= 1e5) return (n / 1e5).toFixed(1) + " L";
		if (n >= 1e3) return (n / 1e3).toFixed(1) + " K";
		return String(Math.round(n));
	};
	window._fgsFmtS = fmtS;
	window._fgsFmt  = fmt;

	// ── Aggregate ──
	var plantMap     = {};
	var plantItemMap = {};

	rows.forEach(function (r) {
		var p     = (r.plant      || "").trim();
		var ig    = (r.item_group || "Unknown").trim();
		var ic    = (r.item_code  || r.item_name || ig).trim();
		var iname = (r.item_name  || r.item_code || ig).trim();
		var uom   = (r.stock_uom  || "").trim();
		if (!p || p === "Plant Missing") return;

		var qty   = parseFloat(r.qty   || 0);
		var value = parseFloat(r.value || 0);

		if (!plantMap[p]) plantMap[p] = { qty: 0, value: 0 };
		plantMap[p].qty   += qty;
		plantMap[p].value += value;

		if (!plantItemMap[p])     plantItemMap[p]     = {};
		if (!plantItemMap[p][ig]) plantItemMap[p][ig] = { qty: 0, value: 0, uoms: {}, items: {} };
		plantItemMap[p][ig].qty   += qty;
		plantItemMap[p][ig].value += value;
		if (uom) plantItemMap[p][ig].uoms[uom] = (plantItemMap[p][ig].uoms[uom] || 0) + 1;

		if (!plantItemMap[p][ig].items[ic])
			plantItemMap[p][ig].items[ic] = { name: iname, uom: uom, qty: 0, value: 0 };
		plantItemMap[p][ig].items[ic].qty   += qty;
		plantItemMap[p][ig].items[ic].value += value;
		if (uom && !plantItemMap[p][ig].items[ic].uom)
			plantItemMap[p][ig].items[ic].uom = uom;
	});

	var plants = Object.keys(plantMap).sort(function (a, b) {
		return plantMap[b].value - plantMap[a].value;
	});

	var activeGroups = {};
	plants.forEach(function (p) {
		activeGroups[p] = Object.keys(plantItemMap[p] || {})
			.filter(function (ig) { return plantItemMap[p][ig].qty > 0; })
			.sort(function (a, b) { return plantItemMap[p][b].value - plantItemMap[p][a].value; });
	});

	window._fgsPlants        = plants;
	window._fgsPlantMap      = plantMap;
	window._fgsPlantItemMap  = plantItemMap;
	window._fgsActiveGroups  = activeGroups;
	window._fgsMode          = "qty";

	var layoutRows = buildRows(plants, activeGroups);

	var plantCardsHTML = layoutRows.map(function (row) {
		var cols = row.length;
		return "<div style='display:grid;grid-template-columns:" + (cols === 2 ? "1fr 1fr" : "1fr") + ";gap:16px;margin-bottom:16px'>"
			+ row.map(function (pi) {
				var p  = plants[pi];
				var gc = activeGroups[p].length;
				var h  = chartHeight(gc);
				return "<div class='fgs-plant-card' data-pi='" + pi + "'"
					+ " style='border:1.5px solid #e2e8f0;border-radius:16px;padding:20px;"
					+ "background:#fff;box-shadow:0 4px 14px rgba(0,0,0,0.07)'>"

					+ "<div style='display:flex;align-items:center;gap:10px;margin-bottom:14px'>"
					+ "<span style='display:inline-flex;align-items:center;justify-content:center;"
					+ "width:28px;height:28px;border-radius:7px;"
					+ "background:" + FGS_PAL[pi % FGS_PAL.length] + ";color:#1e293b;"
					+ "font-size:12px;font-weight:900;border:2px solid "
					+ FGS_PAL_BORDER[pi % FGS_PAL_BORDER.length] + ";flex-shrink:0'>"
					+ (pi + 1) + "</span>"
					+ "<div style='flex:1;min-width:0'>"
					+ "<span style='font-size:15px;font-weight:800;color:#0f172a'>" + p + "</span>"
					+ "<span class='fgs-plant-chart-sub' style='font-size:11px;color:#94a3b8;margin-left:8px'>"
					+ "— Qty by Item Group</span>"
					+ "</div>"
					+ "<span style='font-size:11px;color:#3b82f6;font-weight:600;white-space:nowrap'>"
					+ "💡 Click bar</span>"
					+ "</div>"

					+ "<div style='position:relative;height:" + h + "px'>"
					+ "<canvas id='fgs-plant-" + pi + "'></canvas>"
					+ "</div>"
					+ "<div id='fgs-drill-" + pi + "' style='display:none;margin-top:16px'></div>"
					+ "</div>";
			}).join("")
			+ "</div>";
	}).join("");

	$(".layout-main-section .page-form.flex").after(
		"<div id='fgs-wrapper' style='"
		+ "background:linear-gradient(160deg,#f8faff 0%,#ffffff 60%,#f0fdf4 100%);"
		+ "border:1.5px solid #e2e8f0;border-radius:18px;padding:28px;"
		+ "margin-bottom:18px;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;"
		+ "box-shadow:0 8px 32px rgba(59,130,246,0.10),0 2px 8px rgba(0,0,0,0.06)'>"

		+ "<div style='display:flex;align-items:center;justify-content:space-between;"
		+ "flex-wrap:wrap;gap:10px;margin-bottom:24px;padding-bottom:20px;border-bottom:2px solid #e2e8f0'>"
		+ "<div>"
		+ "<p style='margin:0;font-size:21px;font-weight:900;color:#0f172a;letter-spacing:-0.4px'>"
		+ "📊 Plant × Item Group Breakdown</p>"
		+ "<p style='margin:6px 0 0;font-size:13px;color:#94a3b8;font-weight:500'>"
		+ "Click any bar to drill down into items &nbsp;·&nbsp; "
		+ "<span style=\"color:#3b82f6;font-weight:700\">Toggle Qty / Value</span></p>"
		+ "</div>"
		+ "<div style='display:flex;gap:8px;align-items:center;flex-wrap:wrap'>"
		+ "<button id='fgs-by-qty' style='font-size:13px;padding:9px 20px;border-radius:9px;cursor:pointer;"
		+ "border:2px solid #bfdbfe;background:#EFF6FF;font-weight:800;color:#1d4ed8;"
		+ "box-shadow:0 3px 8px rgba(59,130,246,0.2)' onclick=\"fgsSwitch('qty')\">📦 By Qty </button>"
		+ "<button id='fgs-by-value' style='font-size:13px;padding:9px 20px;border-radius:9px;cursor:pointer;"
		+ "border:2px solid #e2e8f0;background:#f8fafc;font-weight:600;color:#64748b;"
		+ "box-shadow:0 2px 5px rgba(0,0,0,0.06)' onclick=\"fgsSwitch('value')\">💰 By Value</button>"
		+ "</div></div>"

		+ plantCardsHTML
		+ "</div>"
	);

	function drawWhenReady() {
		var maxWait = 50, waited = 0;
		function tryDraw() {
			var allReady = window._fgsPlants.every(function (_, pi) {
				return !!document.getElementById("fgs-plant-" + pi);
			});
			if (allReady) { drawAllPlantCharts("qty"); }
			else if (waited < maxWait) { waited++; setTimeout(tryDraw, 100); }
		}
		setTimeout(tryDraw, 50);
	}

	if (typeof Chart !== "undefined") { drawWhenReady(); }
	else {
		var s = document.createElement("script");
		s.src = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js";
		s.onload = drawWhenReady;
		document.head.appendChild(s);
	}
}

// ── Draw charts ──
function drawAllPlantCharts(mode) {
	var fmtS = window._fgsFmtS;
	var fmt  = window._fgsFmt;

	document.querySelectorAll(".fgs-plant-chart-sub").forEach(function (el) {
		el.textContent = "— " + (mode === "qty" ? "Qty " : "Value") + " by Item Group";
	});

	(window._fgsPerPlantCharts || []).forEach(function (c) { try { c.destroy(); } catch (e) {} });
	window._fgsPerPlantCharts = [];

	window._fgsPlants.forEach(function (p, pi) {
		var canvas = document.getElementById("fgs-plant-" + pi);
		if (!canvas) return;

		var igMap        = window._fgsPlantItemMap[p] || {};
		var activeGroups = window._fgsActiveGroups[p] || [];
		var n            = activeGroups.length;

		var igLabels = activeGroups.map(function (ig) {
			return ig.replace(/^\d{6}-/, "").replace(/-Mfg(-Beet)?$/, "").replace(/-Mfg-/, " ");
		});
		var igUOMs = activeGroups.map(function (ig) {
			var uoms = igMap[ig] ? igMap[ig].uoms : {};
			var keys = Object.keys(uoms);
			if (!keys.length) return "";
			return keys.sort(function(a,b){ return uoms[b]-uoms[a]; })[0];
		});
		var igData = activeGroups.map(function (ig) {
			return mode === "qty" ? igMap[ig].qty : igMap[ig].value;
		});

		var bgColors     = activeGroups.map(function (_, i) { return FGS_PAL[i % FGS_PAL.length]; });
		var borderColors = activeGroups.map(function (_, i) { return FGS_PAL_BORDER[i % FGS_PAL_BORDER.length]; });

		var barPct = n <= 2 ? 0.45 : n <= 4 ? 0.6 : 0.72;
		var catPct = n <= 2 ? 0.6  : n <= 4 ? 0.7 : 0.8;

		var vals    = igData.filter(function(v){ return v > 0; });
		var maxVal  = Math.max.apply(null, vals);
		var minVal  = Math.min.apply(null, vals);
		var useLog  = vals.length > 1 && minVal > 0 && (maxVal / minVal) > 20;

		var chart = new Chart(canvas, {
			type: "bar",
			plugins: [FGS_3D_PLUGIN, makeLabelPlugin("fgsLbl_"+pi), makeMinBarPlugin("fgsMin_"+pi, bgColors)],
			data: {
				labels: igLabels,
				datasets: [{
					label: mode === "qty" ? "Qty " : "Value",
					data: igData,
					backgroundColor: bgColors,
					borderColor: borderColors,
					borderWidth: 0,
					borderRadius: 6,
					borderSkipped: false,
					barPercentage: barPct,
					categoryPercentage: catPct,
				}]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				// Extra top padding to give room for the taller value labels
				layout: { padding: { top: 44, right: 18, left: 4, bottom: 4 } },
				onClick: function (evt, elements) {
					if (!elements || !elements.length) {
						var rect  = canvas.getBoundingClientRect();
						var xPos  = evt.native ? evt.native.clientX - rect.left : (evt.clientX - rect.left);
						var meta  = chart.getDatasetMeta(0);
						var found = -1, bestDist = 999;
						meta.data.forEach(function(bar, i) {
							var dist = Math.abs(bar.x - xPos);
							if (dist < bestDist && dist < (bar.width || 40)) {
								bestDist = dist; found = i;
							}
						});
						if (found >= 0) {
							fgsShowDrillDown(pi, p, activeGroups[found], igUOMs[found], bgColors[found], borderColors[found]);
						}
						return;
					}
					var idx = elements[0].index;
					fgsShowDrillDown(pi, p, activeGroups[idx], igUOMs[idx], bgColors[idx], borderColors[idx]);
				},
				plugins: {
					legend: { display: false },
					tooltip: {
						titleFont: { size: 13, weight: "bold" },
						bodyFont: { size: 12 },
						padding: 10,
						callbacks: {
							title: function (items) {
								return p + "  ·  " + activeGroups[items[0].dataIndex];
							},
							label: function (c) {
								var uom = igUOMs[c.dataIndex];
								return "  " + (mode === "qty" ? "Qty" : "Value") + ": "
									+ fmt(Math.round(c.parsed.y))
									+ (uom ? " " + uom : "")
									+ "  (" + fmtS(c.parsed.y) + ")";
							},
							afterLabel: function () { return "  🖱 Click to drill down"; }
						}
					}
				},
				scales: {
					x: {
						grid: { display: false },
						ticks: {
							color: "#0f172a",
							font: {
								size: 13,
								weight: "800",
								family: "-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif"
							},
							maxRotation: 35,
							minRotation: 15,
						}
					},
					y: useLog ? {
						type: "logarithmic",
						beginAtZero: false,
						grid: { color: "rgba(0,0,0,0.04)" },
						ticks: {
							color: "#6b7280",
							font: { size: 11, weight: "600" },
							callback: function (v) {
								if (v <= 0) return "";
								return fmtS(v);
							}
						}
					} : {
						beginAtZero: true,
						grid: { color: "rgba(0,0,0,0.04)" },
						ticks: {
							color: "#6b7280",
							font: { size: 11, weight: "600" },
							callback: function (v) { return fmtS(v); }
						}
					}
				}
			}
		});

		window._fgsPerPlantCharts.push(chart);
	});
}

// ── Drill-down ──
function fgsShowDrillDown(pi, plant, itemGroup, groupUOM, bgColor, borderColor) {
	var panel = document.getElementById("fgs-drill-" + pi);
	if (!panel) return;

	if (panel.getAttribute("data-ig") === itemGroup && panel.style.display !== "none") {
		panel.style.display = "none";
		panel.setAttribute("data-ig", "");
		return;
	}
	panel.setAttribute("data-ig", itemGroup);

	var fmt  = window._fgsFmt;
	var fmtS = window._fgsFmtS;
	var igData = (window._fgsPlantItemMap[plant] || {})[itemGroup];
	if (!igData || !igData.items) { panel.style.display = "none"; return; }

	var items = Object.keys(igData.items)
		.map(function (k) { return igData.items[k]; })
		.filter(function (it) { return it.qty > 0; })
		.sort(function (a, b) { return b.value - a.value; });

	if (!items.length) { panel.style.display = "none"; return; }

	var uomLabel = groupUOM;

	// ── Detect mixed UOMs across items in this group ──
	var distinctUOMs = {};
	items.forEach(function (it) { if (it.uom) distinctUOMs[it.uom] = true; });
	var isMixedUOM = Object.keys(distinctUOMs).length > 1;

	var totalQty   = items.reduce(function (s, it) { return s + it.qty;   }, 0);
	var totalValue = items.reduce(function (s, it) { return s + it.value; }, 0);

	// Avg price is only meaningful when all items share one UOM
	var totalAvgPrice = (!isMixedUOM && totalQty > 0) ? totalValue / totalQty : null;

	var itemRows = items.map(function (it, idx) {
		var vShare    = totalValue > 0 ? ((it.value / totalValue) * 100).toFixed(1) : 0;
		var itemUOM   = it.uom || uomLabel;

		// Per-item avg price: show only when item has a single UOM (it always does)
		// and the group is NOT mixed — if mixed, each item's own UOM is clear but
		// cross-item "vs avg" comparison is meaningless, so hide the column entirely.
		var avgPrice     = it.qty > 0 ? it.value / it.qty : 0;
		var priceVsAvg   = (totalAvgPrice !== null && totalAvgPrice > 0) ? avgPrice / totalAvgPrice : null;

		var rankBg    = idx===0?"#FDE68A":idx===1?"#E2E8F0":idx===2?"#FDDCB5":FGS_PAL[idx%FGS_PAL.length];
		var rankBd    = idx===0?"#F59E0B":idx===1?"#94A3B8":idx===2?"#F97316":FGS_PAL_BORDER[idx%FGS_PAL_BORDER.length];
		var rankClr   = idx===0?"#92400E":idx===1?"#1e293b":idx===2?"#7C2D12":"#1e293b";
		var rankLabel = idx===0?"🥇":idx===1?"🥈":idx===2?"🥉":(idx+1);

		// Build avg price cell content — omit entire cell when mixed UOM
		var avgPriceCell = "";
		if (!isMixedUOM) {
			var priceBg  = priceVsAvg !== null && priceVsAvg <= 1.0 ? "#f0fdf4" : "#fffbeb";
			var priceClr = priceVsAvg !== null && priceVsAvg <= 1.0 ? "#15803D" : "#b45309";
			var priceBd  = priceVsAvg !== null && priceVsAvg <= 1.0 ? "#bbf7d0" : "#fde68a";
			var priceTag = priceVsAvg !== null && priceVsAvg <= 1.0 ? "▼" : "▲";
			avgPriceCell = "<td style='padding:10px 14px;text-align:right'>"
				+ "<div style='display:flex;flex-direction:column;align-items:flex-end;gap:3px'>"
				+ "<span style='font-size:14px;font-weight:900;color:#7c3aed'>₹ " + fmt(Math.round(avgPrice)) + "</span>"
				+ (priceVsAvg !== null
					? "<span style='font-size:11px;font-weight:700;background:" + priceBg + ";color:" + priceClr + ";"
					  + "padding:1px 6px;border-radius:99px;border:1px solid " + priceBd + "'>"
					  + priceTag + " " + (Math.abs(priceVsAvg - 1) * 100).toFixed(1) + "% vs avg</span>"
					: "")
				+ "</div></td>";
		}

		return "<tr style='border-bottom:1px solid #f0f4f8;transition:background .15s'"
			+ " onmouseover=\"this.style.background='#f8faff'\" onmouseout=\"this.style.background=''\">"
			+ "<td style='padding:10px 14px;font-size:13px;font-weight:700;color:#1e293b'>"
			+ "<div style='display:flex;align-items:center;gap:9px'>"
			+ "<span style='display:inline-flex;align-items:center;justify-content:center;"
			+ "width:26px;height:26px;border-radius:6px;background:" + rankBg + ";color:" + rankClr + ";"
			+ "font-size:11px;font-weight:900;border:2px solid " + rankBd + ";flex-shrink:0'>"
			+ rankLabel + "</span>"
			+ "<span>" + it.name + "</span></div></td>"
			+ "<td style='padding:10px 14px;text-align:center'>"
			+ "<span style='font-size:11px;font-weight:700;color:#6366f1;background:#eef2ff;"
			+ "padding:2px 8px;border-radius:99px;border:1px solid #c7d2fe'>" + itemUOM + "</span></td>"
			+ "<td style='padding:10px 14px;text-align:right;font-size:14px;font-weight:900;color:#1D4ED8'>"
			+ fmt(Math.round(it.qty)) + "</td>"
			+ "<td style='padding:10px 14px;text-align:right'>"
			+ "<div style='display:flex;flex-direction:column;align-items:flex-end;gap:2px'>"
			+ "<span style='font-size:14px;font-weight:900;color:#15803D'>" + fmt(Math.round(it.value)) + "</span>"
			+ "<span style='font-size:11px;font-weight:700;color:#22c55e;background:#f0fdf4;"
			+ "padding:1px 6px;border-radius:99px;border:1px solid #bbf7d0'>≈ " + fmtS(it.value) + "</span>"
			+ "</div></td>"
			+ avgPriceCell
			+ "<td style='padding:10px 14px;text-align:right'>"
			+ "<div style='display:flex;align-items:center;gap:6px;justify-content:flex-end'>"
			+ "<div style='width:80px;height:7px;border-radius:99px;background:#e2e8f0;overflow:hidden'>"
			+ "<div style='height:100%;width:" + vShare + "%;background:" + borderColor + ";border-radius:99px'></div></div>"
			+ "<span style='font-size:12px;font-weight:900;color:#374151;min-width:38px;text-align:right'>"
			+ vShare + "%</span></div></td>"
			+ "</tr>";
	}).join("");

	// ── Header row: conditionally include Avg Price column ──
	var avgPriceHeader = !isMixedUOM
		? "<th style='text-align:right;padding:10px 14px;font-weight:800;color:#7c3aed;"
		  + "border-bottom:1.5px solid #e2e8f0;font-size:12px'>Avg Price / " + (uomLabel || "unit") + "</th>"
		: "";

	// ── Footer avg price cell ──
	var avgPriceFooter = !isMixedUOM
		? "<td style='padding:10px 14px;text-align:right'>"
		  + "<div style='display:flex;flex-direction:column;align-items:flex-end;gap:3px'>"
		  + "<span style='font-weight:900;font-size:14px;color:#7c3aed'>₹ " + fmt(Math.round(totalAvgPrice)) + "</span>"
		  + "<span style='font-size:11px;font-weight:600;color:#6b7280'>weighted avg</span>"
		  + "</div></td>"
		: "";

	// ── Summary bar: show avg price only for single-UOM groups ──
	var avgPriceSummary = !isMixedUOM
		? "<div style='text-align:right'>"
		  + "<p style='margin:0;font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.05em'>Avg Price / " + (uomLabel || "unit") + "</p>"
		  + "<p style='margin:0;font-size:18px;font-weight:900;color:#7c3aed'>₹ " + fmt(Math.round(totalAvgPrice)) + "</p>"
		  + "</div>"
		: "";

	// colspan for the footer "Total" label cell: 2 always (Item + UOM cols)
	// remaining cells: Qty, Value, [AvgPrice], ValueShare
	var footerTotalColspan = "2";

	panel.innerHTML =
		"<div style='border:1.5px solid " + borderColor + ";border-radius:12px;overflow:hidden;"
		+ "box-shadow:0 4px 16px rgba(0,0,0,0.09)'>"
		+ "<div style='background:linear-gradient(90deg," + bgColor + "55," + bgColor + "22);"
		+ "padding:12px 16px;display:flex;align-items:center;justify-content:space-between;"
		+ "flex-wrap:wrap;gap:8px;border-bottom:2px solid " + borderColor + "55'>"
		+ "<div style='display:flex;align-items:center;gap:10px'>"
		+ "<span style='font-size:18px'>📂</span>"
		+ "<div>"
		+ "<p style='margin:0;font-size:14px;font-weight:900;color:#0f172a'>" + itemGroup + "</p>"
		+ "<p style='margin:2px 0 0;font-size:12px;color:#64748b;font-weight:500'>"
		+ plant + " &nbsp;·&nbsp; " + items.length + " item(s)"
		+ (uomLabel && !isMixedUOM
			? " &nbsp;·&nbsp; <span style=\"background:#eef2ff;color:#6366f1;font-weight:700;"
			  + "padding:1px 7px;border-radius:99px;border:1px solid #c7d2fe\">" + uomLabel + "</span>"
			: (isMixedUOM
				? " &nbsp;·&nbsp; <span style=\"background:#fef9c3;color:#854d0e;font-weight:700;"
				  + "padding:1px 7px;border-radius:99px;border:1px solid #fde68a\">Mixed UOM</span>"
				: ""))
		+ "</p></div></div>"
		+ "<div style='display:flex;gap:16px;flex-wrap:wrap;align-items:center'>"
		+ "<div style='text-align:right'>"
		+ "<p style='margin:0;font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.05em'>Total Value</p>"
		+ "<p style='margin:0;font-size:18px;font-weight:900;color:#15803D'>₹ " + fmtS(totalValue) + "</p>"
		+ "</div>"
		+ avgPriceSummary
		+ "<button onclick=\"fgsCloseDrill(" + pi + ")\" style='font-size:12px;padding:6px 14px;"
		+ "border-radius:8px;cursor:pointer;border:1.5px solid " + borderColor + ";"
		+ "background:#fff;font-weight:700;color:#374151'>✕ Close</button>"
		+ "</div></div>"
		+ "<table style='width:100%;border-collapse:collapse;background:#fff'>"
		+ "<thead><tr style='background:linear-gradient(90deg,#f8fafc,#f1f5f9)'>"
		+ "<th style='text-align:left;padding:10px 14px;font-weight:800;color:#374151;border-bottom:1.5px solid #e2e8f0;font-size:12px'>Item</th>"
		+ "<th style='text-align:center;padding:10px 14px;font-weight:800;color:#6366f1;border-bottom:1.5px solid #e2e8f0;font-size:12px'>UOM</th>"
		+ "<th style='text-align:right;padding:10px 14px;font-weight:800;color:#1D4ED8;border-bottom:1.5px solid #e2e8f0;font-size:12px'>Qty</th>"
		+ "<th style='text-align:right;padding:10px 14px;font-weight:800;color:#15803D;border-bottom:1.5px solid #e2e8f0;font-size:12px'>Value</th>"
		+ avgPriceHeader
		+ "<th style='text-align:right;padding:10px 14px;font-weight:800;color:#6b7280;border-bottom:1.5px solid #e2e8f0;font-size:12px'>Value Share</th>"
		+ "</tr></thead>"
		+ "<tbody>" + itemRows + "</tbody>"
		+ "<tfoot><tr style='background:linear-gradient(90deg,#f1f5f9,#e8edf5);border-top:2px solid #e2e8f0'>"
		+ "<td colspan='" + footerTotalColspan + "' style='padding:10px 14px;font-weight:900;font-size:14px;color:#0f172a'>▶ Total</td>"
		+ "<td style='padding:10px 14px;text-align:right;font-weight:900;font-size:14px;color:#1D4ED8'>" + fmt(Math.round(totalQty)) + "</td>"
		+ "<td style='padding:10px 14px;text-align:right'>"
		+ "<div style='display:flex;flex-direction:column;align-items:flex-end;gap:2px'>"
		+ "<span style='font-weight:900;font-size:14px;color:#15803D'>" + fmt(Math.round(totalValue)) + "</span>"
		+ "<span style='font-size:11px;font-weight:700;color:#22c55e;background:#f0fdf4;"
		+ "padding:1px 6px;border-radius:99px;border:1px solid #bbf7d0'>≈ " + fmtS(totalValue) + "</span>"
		+ "</div></td>"
		+ avgPriceFooter
		+ "<td style='padding:10px 14px;text-align:right;font-weight:900;font-size:14px;color:#374151'>100%</td>"
		+ "</tr></tfoot></table></div>";

	panel.style.display = "block";
	setTimeout(function () { panel.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, 80);
}

window.fgsCloseDrill = function (pi) {
	var panel = document.getElementById("fgs-drill-" + pi);
	if (panel) { panel.style.display = "none"; panel.setAttribute("data-ig", ""); }
};

window.fgsSwitch = function (mode) {
	window._fgsMode = mode;
	["fgs-by-qty","fgs-by-value"].forEach(function (id) {
		var btn = document.getElementById(id);
		if (!btn) return;
		var active = (id==="fgs-by-qty"&&mode==="qty")||(id==="fgs-by-value"&&mode==="value");
		btn.style.background  = active ? "#EFF6FF" : "#f8fafc";
		btn.style.fontWeight  = active ? "800"     : "600";
		btn.style.color       = active ? "#1d4ed8" : "#64748b";
		btn.style.borderColor = active ? "#bfdbfe" : "#e2e8f0";
		btn.style.boxShadow   = active ? "0 3px 8px rgba(59,130,246,0.2)" : "0 2px 5px rgba(0,0,0,0.06)";
	});
	(window._fgsPlants || []).forEach(function (_, pi) {
		var panel = document.getElementById("fgs-drill-" + pi);
		if (panel) { panel.style.display = "none"; panel.setAttribute("data-ig", ""); }
	});
	drawAllPlantCharts(mode);
};