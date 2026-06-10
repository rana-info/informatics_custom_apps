// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["Fuel and RM(444,446,448) Purchase Tracker - MGT"] = {

	tree: true,
	name_field: "name",
	parent_field: "parent",
	initial_depth: 1,

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		if (column.fieldname === "name" && data.doctype && data.docname) {
			value = '<a href="/app/' + frappe.router.slug(data.doctype) + "/" + encodeURIComponent(data.docname) + '">' + value + "</a>";
		}
		if (data.indent === 1) return "<b>" + value + "</b>";
		if (data.indent === 2) return '<span style="font-weight:600">' + value + "</span>";
		return value;
	},

	onload: function (report) {
		frappe.call({
			method: "erpnext.accounts.utils.get_fiscal_year",
			args: {
				date: frappe.datetime.get_today(),
				company: frappe.defaults.get_user_default("Company"),
			},
			callback: function (r) {
				if (!r.message) return;
				if (!frappe.query_report.get_filter_value("from_date"))
					frappe.query_report.set_filter_value("from_date", r.message[1]);
				if (!frappe.query_report.get_filter_value("to_date"))
					frappe.query_report.set_filter_value("to_date", frappe.datetime.get_today());
			},
		});

		report.page.add_inner_button(__("Collapse All"), function () {
			var dt = frappe.query_report.datatable || report.datatable;
			if (!dt || !dt.rowmanager) return;
			setTimeout(function () {
				try { dt.rowmanager.setTreeDepth(1); } catch (e) { console.error("PWC Collapse failed:", e); }
			}, 50);
		});
		report.page.add_inner_button(__("Expand All"), function () {
			var dt = frappe.query_report.datatable || report.datatable;
			if (!dt || !dt.rowmanager) return;
			setTimeout(function () {
				try { dt.rowmanager.expandAllNodes(); } catch (e) { console.error("PWC Expand failed:", e); }
			}, 50);
		});
	},

	after_datatable_render: function (datatable) {
		var report = frappe.query_report;
		var hasData = (report.data || []).some(function (row) { return row.indent === 1; });
		if (hasData) {
			pwc_render(report);
		} else if (window._pwcPendingRender) {
			window._pwcPendingRender = false;
			$("#pwc-wrapper").remove();
			$(".quintal-note-banner").remove();
			$(".layout-main-section").prepend('<div class="quintal-note-banner" style="padding:10px 15px;margin-bottom:10px;border-left:5px solid #93C5FD;background:#EFF6FF;border-radius:6px;font-size:13px;font-weight:500;color:#1e40af;">' + "⚠️ All quantities in this report are in <b>Quintal</b>. &nbsp; 1 Quintal = <b>100 Kg</b>" + "</div>");
		}
		window._pwcPendingRender = false;
	},
    refresh: function (report) {
        $("#pwc-wrapper").remove();
        $(".quintal-note-banner").remove();
        if (window._pwcChart) {
            try { window._pwcChart.destroy(); } catch (e) {}
            window._pwcChart = null;
        }

        var attempts = 0;
        function tryRender() {
            attempts++;
            var hasData = (report.data || []).some(function (row) { return row.indent === 1; });
            if (hasData) {
                pwc_render(report);
            } else if (attempts < 5) {
                setTimeout(tryRender, attempts * 300);
            }
        }
        setTimeout(tryRender, 300);
    },

	filters: [
		{ fieldname: "from_date", label: "From Date", fieldtype: "Date" },
		{ fieldname: "to_date",   label: "To Date",   fieldtype: "Date" },
		{
			fieldname: "company", label: "Company", fieldtype: "MultiSelectList",
			get_data: function (txt) { return frappe.db.get_link_options("Company", txt); }
		},
		{
			fieldname: "plant", label: "Plant", fieldtype: "MultiSelectList",
			get_data: function (txt) {
				var companies = frappe.query_report.get_filter_value("company") || [];
				var f = {};
				if (companies.length) f.company = ["in", companies];
				return frappe.db.get_link_options("Branch", txt, f);
			}
		}
	]
};

var PWC_COLORS = {
	ordered:      "#93C5FD",
	orderedBg:    "#EFF6FF",
	orderedText:  "#1D4ED8",
	received:     "#86EFAC",
	receivedBg:   "#F0FDF4",
	receivedText: "#15803D",
	pending:      "#FCA5A5",
	pendingBg:    "#FEF2F2",
	pendingText:  "#B91C1C",
	barGood:      "#4ADE80",
	barMid:       "#FCD34D",
	barBad:       "#F87171",
};

window._pwcActiveFilter = null;

(function () {
    var reportName = "Fuel and RM(444,446,448) Purchase Tracker - MGT";

    function pwcCleanup() {
        var currentRoute = frappe.get_route();
        var onThisReport = currentRoute &&
            currentRoute[0] === "query-report" &&
            currentRoute[1] === reportName;
        if (!onThisReport) {
            $("#pwc-wrapper").remove();
            $(".quintal-note-banner").remove();
            if (window._pwcChart) {
                try { window._pwcChart.destroy(); } catch (e) {}
                window._pwcChart = null;
            }
        }
    }

    $(document).on("page-change", pwcCleanup);
    frappe.router.on("change", pwcCleanup);
})();

function pwc_render(report) {

	var plants = [];
	(report.data || []).forEach(function (row) {
		if (row.indent === 1) {
			plants.push({
				name:     String(row.name || ""),
				ordered:  parseFloat(row.ordered_value  || 0),
				received: parseFloat(row.received_value || 0),
				pending:  parseFloat(row.pending_value  || 0),
			});
		}
	});

	// ── Clean up previous renders ──
	$("#pwc-wrapper").remove();
	$(".quintal-note-banner").remove();

	var currentFilterVal = frappe.query_report.get_filter_value("plant") || [];
	if (!currentFilterVal.length) window._pwcActiveFilter = null;

	// ── Step 1: Banner at very top (prepend to layout-main-section) ──
	$(".layout-main-section").prepend(
		'<div class="quintal-note-banner" style="padding:10px 15px;margin-bottom:10px;border-left:5px solid #93C5FD;background:#EFF6FF;border-radius:6px;font-size:13px;font-weight:500;color:#1e40af;">' +
		"⚠️ All quantities in this report are in <b>Quintal</b>. &nbsp; 1 Quintal = <b>100 Kg</b>" +
		"</div>"
	);

	if (!plants.length) return;

	var fmt    = function (n) { return Number(n).toLocaleString("en-IN"); };
	var fmtShort = function (n) {
		if (n >= 1e7)  return (n / 1e7).toFixed(2).replace(/\.?0+$/, "") + " Cr";
		if (n >= 1e5)  return (n / 1e5).toFixed(1).replace(/\.?0+$/, "") + " L";
		if (n >= 1e3)  return (n / 1e3).toFixed(1).replace(/\.?0+$/, "") + " K";
		return String(Math.round(n));
	};

	var totalOrdered  = plants.reduce(function (s, p) { return s + p.ordered;  }, 0);
	var totalReceived = plants.reduce(function (s, p) { return s + p.received; }, 0);
	var totalPending  = plants.reduce(function (s, p) { return s + p.pending;  }, 0);

	var clearBtnHtml = window._pwcActiveFilter
		? "<button id='pwc-clear' style='font-size:13px;padding:6px 16px;border-radius:6px;cursor:pointer;border:1px solid #fca5a5;background:#fef2f2;font-weight:600;color:#b91c1c;display:inline-flex;align-items:center;gap:5px' onclick=\"pwcClearFilter()\">"
		  + "<span style='font-size:16px;line-height:1'>&#8592;</span> Back &nbsp;<span style='opacity:.7;font-weight:400'>(" + window._pwcActiveFilter + ")</span>"
		  + "</button>"
		: "<button id='pwc-clear' style='display:none' onclick=\"pwcClearFilter()\">&#8592; Back</button>";

	var trows = plants.map(function (p) {
		var pct = p.ordered > 0 ? Math.round((p.received / p.ordered) * 100) : 0;
		var bc  = pct >= 80 ? PWC_COLORS.barGood : pct >= 50 ? PWC_COLORS.barMid : PWC_COLORS.barBad;
		var isActive = window._pwcActiveFilter === p.name;
		return "<tr style='border-bottom:1px solid #f3f4f6;cursor:pointer;" + (isActive ? "background:#eff6ff;" : "") + "' "
			+ "onclick=\"pwcFilterPlant('" + p.name.replace(/'/g, "\\'") + "')\" "
			+ "title='Click to filter report by " + p.name + "'>"
			+ "<td style='padding:11px 14px;font-weight:600;font-size:13px;color:#374151'>"
			+ (isActive ? "<span style='color:#2563eb;margin-right:5px'>▶</span>" : "")
			+ p.name + "</td>"
			+ "<td style='padding:11px 14px;text-align:right;font-size:13px;font-weight:600;color:" + PWC_COLORS.orderedText + "'>" + fmt(p.ordered) + "</td>"
			+ "<td style='padding:11px 14px;text-align:right;font-size:13px;font-weight:600;color:" + PWC_COLORS.receivedText + "'>" + fmt(p.received) + "</td>"
			+ "<td style='padding:11px 14px;text-align:right;font-size:13px;font-weight:600;color:" + PWC_COLORS.pendingText + "'>" + fmt(p.pending) + "</td>"
			+ "<td style='padding:11px 14px;text-align:right'>"
			+ "<div style='display:flex;align-items:center;gap:6px;justify-content:flex-end'>"
			+ "<div style='width:64px;height:7px;border-radius:99px;background:#f3f4f6;overflow:hidden'>"
			+ "<div style='height:100%;width:" + pct + "%;background:" + bc + ";border-radius:99px'></div></div>"
			+ "<span style='font-size:13px;font-weight:700;color:#6b7280;min-width:36px;text-align:right'>" + pct + "%</span>"
			+ "</div></td></tr>";
	}).join("");

	// ── Step 2: pwc-wrapper inserted AFTER the filters (page-form) ──
	$(".layout-main-section .page-form.flex").after(
		"<div id='pwc-wrapper' style='background:#fff;border:1px solid #f3f4f6;border-radius:12px;padding:20px;margin-bottom:16px;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;box-shadow:0 1px 4px rgba(0,0,0,0.06)'>"

		+ "<div style='display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:16px'>"
		+ "<div>"
		+ "<p style='margin:0;font-size:16px;font-weight:700;color:#111'>Plant-wise Procurement Status</p>"
		+ "<p style='margin:4px 0 0;font-size:12px;color:#9ca3af'>Fuel &amp; RM (444,446,448) &nbsp;·&nbsp; Quintal &nbsp;·&nbsp; <span style='color:#3b82f6'>Click a bar or row to filter</span></p>"
		+ "</div>"
		+ "<div style='display:flex;gap:6px;align-items:center;flex-wrap:wrap'>"
		+ "<button id='pwc-grouped' style='font-size:13px;padding:6px 14px;border-radius:6px;cursor:pointer;border:1px solid #bfdbfe;background:#EFF6FF;font-weight:700;color:#1d4ed8' onclick=\"window.pwcDraw('grouped')\">Grouped</button>"
		+ "<button id='pwc-stacked' style='font-size:13px;padding:6px 14px;border-radius:6px;cursor:pointer;border:1px solid #e5e7eb;background:#fff;font-weight:400;color:#6b7280' onclick=\"window.pwcDraw('stacked')\">Stacked</button>"
		+ clearBtnHtml
		+ "</div></div>"

		+ "<div style='display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:16px'>"
		+ "<div style='background:" + PWC_COLORS.orderedBg + ";border-radius:8px;padding:14px;border:1px solid #bfdbfe'><p style='margin:0 0 4px;font-size:11px;color:#60a5fa;text-transform:uppercase;letter-spacing:.06em;font-weight:700'>Total Ordered</p><p style='margin:0;font-size:22px;font-weight:800;color:" + PWC_COLORS.orderedText + "'>" + fmt(totalOrdered) + "</p></div>"
		+ "<div style='background:" + PWC_COLORS.receivedBg + ";border-radius:8px;padding:14px;border:1px solid #bbf7d0'><p style='margin:0 0 4px;font-size:11px;color:#4ade80;text-transform:uppercase;letter-spacing:.06em;font-weight:700'>Total Received</p><p style='margin:0;font-size:22px;font-weight:800;color:" + PWC_COLORS.receivedText + "'>" + fmt(totalReceived) + "</p></div>"
		+ "<div style='background:" + PWC_COLORS.pendingBg + ";border-radius:8px;padding:14px;border:1px solid #fecaca'><p style='margin:0 0 4px;font-size:11px;color:#f87171;text-transform:uppercase;letter-spacing:.06em;font-weight:700'>Total Pending</p><p style='margin:0;font-size:22px;font-weight:800;color:" + PWC_COLORS.pendingText + "'>" + fmt(totalPending) + "</p></div>"
		+ "</div>"

		+ "<div style='display:flex;gap:16px;margin-bottom:10px;font-size:13px;color:#6b7280'>"
		+ "<span><span style='display:inline-block;width:12px;height:12px;border-radius:3px;background:" + PWC_COLORS.ordered + ";margin-right:5px;vertical-align:middle'></span>Ordered</span>"
		+ "<span><span style='display:inline-block;width:12px;height:12px;border-radius:3px;background:" + PWC_COLORS.received + ";margin-right:5px;vertical-align:middle'></span>Received</span>"
		+ "<span><span style='display:inline-block;width:12px;height:12px;border-radius:3px;background:" + PWC_COLORS.pending + ";margin-right:5px;vertical-align:middle'></span>Pending</span>"
		+ "</div>"

		+ "<div id='pwc-canvas-wrap' style='position:relative;width:100%;height:520px;margin-bottom:18px;cursor:pointer'>"
		+ "<canvas id='pwc-canvas'></canvas>"
		+ "</div>"

		+ "<p style='font-size:13px;font-weight:700;color:#374151;margin:0 0 8px'>Plant breakdown</p>"
		+ "<div style='border:1px solid #f3f4f6;border-radius:8px;overflow:hidden'>"
		+ "<table style='width:100%;border-collapse:collapse;font-size:13px;table-layout:fixed'>"
		+ "<thead><tr style='background:#f9fafb'>"
		+ "<th style='text-align:left;padding:10px 14px;font-weight:700;color:#6b7280;border-bottom:1px solid #f3f4f6;width:30%'>Plant</th>"
		+ "<th style='text-align:right;padding:10px 14px;font-weight:700;color:" + PWC_COLORS.orderedText + ";border-bottom:1px solid #f3f4f6'>Ordered</th>"
		+ "<th style='text-align:right;padding:10px 14px;font-weight:700;color:" + PWC_COLORS.receivedText + ";border-bottom:1px solid #f3f4f6'>Received</th>"
		+ "<th style='text-align:right;padding:10px 14px;font-weight:700;color:" + PWC_COLORS.pendingText + ";border-bottom:1px solid #f3f4f6'>Pending</th>"
		+ "<th style='text-align:right;padding:10px 14px;font-weight:700;color:#6b7280;border-bottom:1px solid #f3f4f6'>Fulfillment</th>"
		+ "</tr></thead><tbody>" + trows + "</tbody></table></div>"
		+ "</div>"
	);

	window._pwcPlants = plants;
	window._pwcChart  = null;
	window._pwcFmtShort = fmtShort;

	window.pwcFilterPlant = function (plantName) {
		if (window._pwcActiveFilter === plantName) { window.pwcClearFilter(); return; }
		window._pwcActiveFilter = plantName;
		window._pwcPendingRender = true;
		frappe.query_report.set_filter_value("plant", [plantName]);
		frappe.query_report.refresh();
	};

	window.pwcClearFilter = function () {
		window._pwcActiveFilter = null;
		window._pwcPendingRender = true;
		frappe.query_report.set_filter_value("plant", []);
		frappe.query_report.refresh();
	};

	window.pwcDraw = function (mode) {
		var canvas = document.getElementById("pwc-canvas");
		if (!canvas) return;
		var wrap = document.getElementById("pwc-canvas-wrap");
		if (wrap) { canvas.width = wrap.offsetWidth || 700; canvas.height = wrap.offsetHeight || 520; }

		if (window._pwcChart) { try { window._pwcChart.destroy(); } catch (e) {} window._pwcChart = null; }

		var g = document.getElementById("pwc-grouped");
		var s = document.getElementById("pwc-stacked");
		if (g) { g.style.background = mode === "grouped" ? PWC_COLORS.orderedBg : "#fff"; g.style.fontWeight = mode === "grouped" ? "700" : "400"; g.style.color = mode === "grouped" ? "#1d4ed8" : "#6b7280"; }
		if (s) { s.style.background = mode === "stacked" ? PWC_COLORS.orderedBg : "#fff"; s.style.fontWeight = mode === "stacked" ? "700" : "400"; s.style.color = mode === "stacked" ? "#1d4ed8" : "#6b7280"; }

		var activeIdx = window._pwcActiveFilter
			? window._pwcPlants.findIndex(function (p) { return p.name === window._pwcActiveFilter; }) : -1;

		function barColors(base) {
			return window._pwcPlants.map(function (_, i) {
				return (activeIdx === -1 || i === activeIdx) ? base : base + "55";
			});
		}

		var labelBgMap  = { "Ordered": "#1e40af", "Received": "#14532d", "Pending": "#7f1d1d" };
		var labelFgMap  = { "Ordered": "#fff",    "Received": "#fff",    "Pending": "#fff"    };

		var dataLabelPlugin = {
			id: "pwcDataLabels",
			afterDatasetsDraw: function (chart) {
				var ctx = chart.ctx;
				ctx.save();
				chart.data.datasets.forEach(function (dataset, di) {
					var meta = chart.getDatasetMeta(di);
					if (meta.hidden) return;
					var bg = labelBgMap[dataset.label] || "#374151";
					var fg = labelFgMap[dataset.label] || "#fff";

					meta.data.forEach(function (bar, i) {
						var value = dataset.data[i];
						if (!value) return;

						var barH = Math.abs(bar.base - bar.y);
						var barW = bar.width || 20;
						var label = window._pwcFmtShort(value);

						var fs = Math.max(10, Math.min(14, Math.floor(barW * 0.38)));
						ctx.font = "bold " + fs + "px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";

						var textW = ctx.measureText(label).width;
						var pad   = 4;
						var pillW = textW + pad * 2;
						var pillH = fs + pad * 2;

						if (barH >= pillH + 8) {
							var pillX = bar.x - pillW / 2;
							var pillY = bar.y + 6;

							ctx.fillStyle = bg;
							ctx.beginPath();
							ctx.roundRect
								? ctx.roundRect(pillX, pillY, pillW, pillH, pillH / 2)
								: (function () {
									var r = pillH / 2;
									ctx.moveTo(pillX + r, pillY);
									ctx.arcTo(pillX + pillW, pillY, pillX + pillW, pillY + pillH, r);
									ctx.arcTo(pillX + pillW, pillY + pillH, pillX, pillY + pillH, r);
									ctx.arcTo(pillX, pillY + pillH, pillX, pillY, r);
									ctx.arcTo(pillX, pillY, pillX + pillW, pillY, r);
									ctx.closePath();
								})();
							ctx.fill();

							ctx.fillStyle = fg;
							ctx.textAlign = "center";
							ctx.textBaseline = "top";
							ctx.fillText(label, bar.x, pillY + pad);
						} else {
							ctx.fillStyle = bg;
							ctx.textAlign = "center";
							ctx.textBaseline = "bottom";
							ctx.font = "bold " + Math.max(11, fs) + "px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
							ctx.fillText(label, bar.x, bar.y - 3);
						}
					});
				});
				ctx.restore();
			}
		};

		window._pwcChart = new Chart(canvas, {
			type: "bar",
			plugins: [dataLabelPlugin],
			data: {
				labels: window._pwcPlants.map(function (p) { return p.name; }),
				datasets: [
					{ label: "Ordered",  data: window._pwcPlants.map(function (p) { return p.ordered;  }), backgroundColor: barColors(PWC_COLORS.ordered),  borderRadius: 5, borderSkipped: false },
					{ label: "Received", data: window._pwcPlants.map(function (p) { return p.received; }), backgroundColor: barColors(PWC_COLORS.received), borderRadius: 5, borderSkipped: false },
					{ label: "Pending",  data: window._pwcPlants.map(function (p) { return p.pending;  }), backgroundColor: barColors(PWC_COLORS.pending),  borderRadius: 5, borderSkipped: false }
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				layout: { padding: { top: 36 } },
				onClick: function (evt, elements) {
					if (!elements || !elements.length) return;
					var plant = window._pwcPlants[elements[0].index];
					if (plant) window.pwcFilterPlant(plant.name);
				},
				plugins: {
					legend: { display: false },
					tooltip: {
						titleFont: { size: 14, weight: "bold" },
						bodyFont:  { size: 13 },
						padding: 10,
						callbacks: {
							label: function (c) {
								return "  " + c.dataset.label + ": " + Number(c.parsed.y).toLocaleString("en-IN") + " Qt";
							},
							afterBody: function () { return ["", "  Click to filter · click again to clear"]; }
						}
					}
				},
				scales: {
					x: {
						stacked: mode === "stacked",
						grid: { display: false },
						ticks: { color: "#6b7280", font: { size: 13, weight: "600" }, maxRotation: 20 }
					},
					y: {
						stacked: mode === "stacked",
						beginAtZero: true,
						grid: { color: "rgba(0,0,0,0.04)" },
						ticks: {
							color: "#6b7280",
							font: { size: 13 },
							callback: function (v) { return window._pwcFmtShort(v); }
						}
					}
				}
			}
		});
	};

	function drawWhenReady() {
		requestAnimationFrame(function () { requestAnimationFrame(function () { window.pwcDraw("grouped"); }); });
	}

	if (typeof Chart !== "undefined") {
		drawWhenReady();
	} else {
		var script = document.createElement("script");
		script.src = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js";
		script.onload = drawWhenReady;
		script.onerror = function () { console.error("PWC: Chart.js failed to load"); };
		document.head.appendChild(script);
	}
}