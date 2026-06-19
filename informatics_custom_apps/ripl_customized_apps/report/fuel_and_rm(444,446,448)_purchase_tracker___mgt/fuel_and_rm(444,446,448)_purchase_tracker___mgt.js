// Copyright (c) 2026, Monil Kamboj and contributors

frappe.query_reports["Fuel and RM(444,446,448) Purchase Tracker - MGT"] = {
	tree: true,
	name_field: "name",
	parent_field: "parent",
	initial_depth: 1,

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;

		if (column.fieldname === "name") {
			if (data.indent === 0) {
				var realGrp = (data.docname || "").replace(/^GRP::/, "").split("::")[0];
				var link = '/app/item-group/' + encodeURIComponent(realGrp);
				value = '<a href="' + link + '" style="color:#1D4ED8;font-weight:900;font-size:13px">' + (data.name || realGrp) + '</a>';
			} else if (data.indent === 1) {
				var realPlant = (data.docname || "").replace(/^[^:]+::/, "").split("::")[0];
				var link2 = '/app/branch/' + encodeURIComponent(realPlant);
				value = '<a href="' + link2 + '" style="color:#0F172A;font-weight:800">' + (data.name || realPlant) + '</a>';
			} else if (data.indent === 2) {
				var parts = (data.docname || "").split("::");
				var poPart = parts[parts.length - 1];
				var link3 = '/app/purchase-order/' + encodeURIComponent(poPart);
				value = '<a href="' + link3 + '" style="color:#374151;font-weight:600">' + (data.name || poPart) + '</a>';
			} else if (data.indent === 3 && data.docname) {
				value = '<span style="color:#6B7280">' + (data.name || "") + '</span>';
			}
		}

		if (data.indent === 0) return '<b style="color:#1D4ED8">' + value + "</b>";
		if (data.indent === 1) return "<b>" + value + "</b>";
		if (data.indent === 2) return '<span style="font-weight:600">' + value + "</span>";
		return value;
	},

	onload: function (report) {
		frappe.call({
			method: "erpnext.accounts.utils.get_fiscal_year",
			args: { date: frappe.datetime.get_today(), company: frappe.defaults.get_user_default("Company") },
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
			if (dt && dt.rowmanager) setTimeout(function () { try { dt.rowmanager.setTreeDepth(1); } catch (e) {} }, 50);
		});
		report.page.add_inner_button(__("Expand All"), function () {
			var dt = frappe.query_report.datatable || report.datatable;
			if (dt && dt.rowmanager) setTimeout(function () { try { dt.rowmanager.expandAllNodes(); } catch (e) {} }, 50);
		});
	},

	after_datatable_render: function () { pis_handle_render(frappe.query_report); },
	refresh: function (report) { pis_destroy_all(); pis_handle_render(report); },

	filters: [
		{ fieldname: "from_date", label: "From Date", fieldtype: "Date" },
		{ fieldname: "to_date",   label: "To Date",   fieldtype: "Date" },
		{
			fieldname: "category", label: "Category", fieldtype: "Select",
			options: "\nFuel\nRM",
			default: ""
		},
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
		},
		{
			fieldname: "supplier", label: "Supplier", fieldtype: "MultiSelectList",
			get_data: function (txt) { return frappe.db.get_link_options("Supplier", txt); }
		}
	]
};


function pis_destroy_all() {
	(window._pisAllCharts||[]).forEach(function(c){ try{c&&c.destroy();}catch(e){} });
	window._pisAllCharts = [];
	window._pisSuppChart = window._pisSuppPlantChart = null;
	$("#pis-wrapper").remove();
}
(function () {
	function pisCleanup() {
		var r = frappe.get_route();
		if (!(r && r[0]==="query-report" && r[1]==="Fuel and RM(444,446,448) Purchase Tracker - MGT"))
			pis_destroy_all();
	}
	$(document).on("page-change", pisCleanup);
	frappe.router.on("change", pisCleanup);
})();


var PAL    = ["#93C5FD","#6EE7B7","#FCA5A5","#FCD34D","#C4B5FD","#F9A8D4","#67E8F9","#FDBA74","#5EEAD4","#A5B4FC"];
var PAL_DK = ["#60A5FA","#34D399","#F87171","#FBBF24","#A78BFA","#F472B6","#22D3EE","#FB923C","#2DD4BF","#818CF8"];
var PAL_BG = ["#EFF6FF","#ECFDF5","#FEF2F2","#FFFBEB","#F5F3FF","#FFF1F2","#F0FDFA","#FFF7ED","#F0FDFA","#EEF2FF"];

function pF(n)  { return (Number(n)||0).toLocaleString("en-IN"); }
function pSF(n) {
	n=Number(n)||0;
	if(n>=1e7) return (n/1e7).toFixed(2).replace(/\.?0+$/,"")+" Cr";
	if(n>=1e5) return (n/1e5).toFixed(2).replace(/\.?0+$/,"")+" L";
	if(n>=1e3) return (n/1e3).toFixed(1).replace(/\.?0+$/,"")+" K";
	return Math.round(n).toString();
}
function FC(p){ return p>=80?"#15803D":p>=50?"#B45309":"#B91C1C"; }
function FB(p){ return p>=80?"#DCFCE7":p>=50?"#FEF9C3":"#FEE2E2"; }
function FBD(p){ return p>=80?"#BBF7D0":p>=50?"#FDE68A":"#FECACA"; }
function pct(ov,rv){ return ov>0?Math.round(rv/ov*100):0; }

function BS(on,sm){
	var sz=sm?"11px":"12px",py=sm?"4px":"6px",px=sm?"10px":"13px";
	return "font-size:"+sz+";padding:"+py+" "+px+";border-radius:8px;cursor:pointer;font-weight:"+(on?"800":"600")+
		";border:1.5px solid "+(on?"#93C5FD":"#D1D5DB")+";background:"+(on?"#DBEAFE":"#F9FAFB")+
		";color:"+(on?"#1D4ED8":"#6B7280")+";transition:all .15s;white-space:nowrap;";
}


function VP(id){return{id:id,afterDatasetsDraw:function(chart){
	var ctx=chart.ctx;
	var ca=chart.chartArea||{top:36,left:0};
	var TOP=ca.top;
	ctx.save();

	var nCols=chart.data.labels.length;

	// ── 1. Draw inside-segment labels where segment is tall enough ──
	var MIN_H_INSIDE=28; // px — minimum segment height to draw inside label
	ctx.font="bold 10px system-ui,sans-serif";
	chart.data.datasets.forEach(function(ds,di){
		var meta=chart.getDatasetMeta(di);
		if(meta.hidden) return;
		meta.data.forEach(function(bar,i){
			var val=ds.data[i]; if(!val) return;
			var h=Math.abs(bar.base-bar.y);
			if(h<MIN_H_INSIDE) return; // too short — skip, handled by total pill

			var lbl=pSF(val);
			var tw=ctx.measureText(lbl).width;
			var bw2=tw+8, bh=15;
			var cx=bar.x, cy=bar.y+h/2; // vertical centre of segment

			// pill background
			ctx.fillStyle="rgba(255,255,255,0.72)";
			ctx.beginPath();
			if(ctx.roundRect) ctx.roundRect(cx-bw2/2,cy-bh/2,bw2,bh,3);
			else ctx.rect(cx-bw2/2,cy-bh/2,bw2,bh);
			ctx.fill();

			// text
			ctx.fillStyle="#0F172A";
			ctx.textAlign="center";
			ctx.textBaseline="middle";
			ctx.fillText(lbl,cx,cy);
		});
	});

	// ── 2. Draw one total pill above each column ──────────────────
	// Collect the topmost Y and total value per column index
	var colTop=[];   // lowest Y value (highest on screen) across all datasets for column i
	var colTotal=[]; // sum of all dataset values for column i
	for(var i=0;i<nCols;i++){ colTop[i]=Infinity; colTotal[i]=0; }

	chart.data.datasets.forEach(function(ds,di){
		var meta=chart.getDatasetMeta(di);
		if(meta.hidden) return;
		meta.data.forEach(function(bar,i){
			var val=ds.data[i]||0;
			colTotal[i]+=val;
			if(bar.y<colTop[i]) colTop[i]=bar.y;
		});
	});

	ctx.font="bold 10px system-ui,sans-serif";
	for(var i=0;i<nCols;i++){
		if(!colTotal[i]) continue;
		var lbl=pSF(colTotal[i]);
		var tw=ctx.measureText(lbl).width;
		var bw2=tw+10, bh=16;
		var cx=chart.getDatasetMeta(0).data[i].x;
		var ly=colTop[i]-bh-5;
		if(ly<TOP) ly=TOP;

		// pill
		ctx.fillStyle="rgba(15,23,42,0.10)";
		ctx.beginPath();
		if(ctx.roundRect) ctx.roundRect(cx-bw2/2,ly,bw2,bh,4);
		else ctx.rect(cx-bw2/2,ly,bw2,bh);
		ctx.fill();

		ctx.fillStyle="#1E293B";
		ctx.textAlign="center";
		ctx.textBaseline="middle";
		ctx.fillText(lbl,cx,ly+bh/2);
	}

	ctx.restore();
}};}


window._pisTimer=null;
function pis_handle_render(report){
	if(window._pisTimer) clearTimeout(window._pisTimer);
	window._pisTimer=setTimeout(function(){
		if((report.data||[]).some(function(r){return r.indent===3;})) pis_render(report);
		else pis_destroy_all();
	},350);
}


function pis_aggregate(rows){
	var groupMap={}, gpMap={}, plantMap={}, piMap={}, suppMap={}, siMap={}, spMap={}, giMap={};
	var poSupp={};
	rows.forEach(function(r){
		if(r.indent===2) poSupp[r.name]={supp:r.supplier||"Unknown",suppName:r.supplier_name||r.supplier||"Unknown"};
	});
	var cGrp="",cPlant="",cPO="";
	rows.forEach(function(r){
		if(r.indent===0){cGrp=(r.name||"").trim()||"No Group";return;}
		if(r.indent===1){cPlant=(r.name||"").trim()||"No Plant";return;}
		if(r.indent===2){cPO=(r.name||"").trim();return;}
		if(r.indent!==3) return;

		var grp=cGrp, plant=cPlant, po=cPO;
		var item=(r.item_name||r.name||"?").trim();
		var uom=(r.uom||"Qtl").trim();
		var ps=poSupp[po]||{supp:"?",suppName:"Unknown Supplier"};
		var supp=ps.suppName;

		var ov=+(r.ordered_value||0),rv=+(r.received_value||0),pv=+(r.pending_value||0);
		var oq=+(r.ordered_qty||0),rq=+(r.received_qty||0),pq=+(r.pending_qty||0);

		function ensure(obj,k,def){if(!obj[k])obj[k]=Object.assign({},def);return obj[k];}
		var Z={ov:0,rv:0,pv:0,oq:0,rq:0,pq:0};
		function add(o){o.ov+=ov;o.rv+=rv;o.pv+=pv;o.oq+=oq;o.rq+=rq;o.pq+=pq;}

		var gm=ensure(groupMap,grp,Object.assign({plants:{},items:{}},Z));
		add(gm);gm.plants[plant]=true;gm.items[item]=true;

		if(!gpMap[grp])gpMap[grp]={};
		var gp=ensure(gpMap[grp],plant,Object.assign({items:{},pos:{}},Z));
		add(gp);gp.items[item]=true;gp.pos[po]=true;

		var pm=ensure(plantMap,plant,Object.assign({groups:{},items:{}},Z));
		add(pm);pm.groups[grp]=true;pm.items[item]=true;

		if(!piMap[plant])piMap[plant]={};
		var pi=ensure(piMap[plant],item,Object.assign({uom:uom,supps:{}},Z));
		add(pi);
		if(!pi.supps[supp+"__d"])pi.supps[supp+"__d"]=Object.assign({},Z);
		add(pi.supps[supp+"__d"]);

		var sm=ensure(suppMap,supp,Object.assign({plants:{},items:{}},Z));
		add(sm);sm.plants[plant]=true;sm.items[item]=true;

		if(!siMap[supp])siMap[supp]={};
		var si=ensure(siMap[supp],item,Object.assign({uom:uom,plants:{}},Z));
		add(si);si.plants[plant]=true;

		if(!spMap[supp])spMap[supp]={};
		var spl=ensure(spMap[supp],plant,Object.assign({items:{}},Z));
		add(spl);
		if(!spl.items[item])spl.items[item]=Object.assign({uom:uom},Z);
		add(spl.items[item]);

		if(!giMap[grp])giMap[grp]={};
		var gi=ensure(giMap[grp],item,Object.assign({uom:uom,plants:{}},Z));
		add(gi);gi.plants[plant]=true;
	});

	var groups=Object.keys(groupMap).sort(function(a,b){return groupMap[b].ov-groupMap[a].ov;});
	var plants=Object.keys(plantMap).sort(function(a,b){return plantMap[b].ov-plantMap[a].ov;});
	var supps =Object.keys(suppMap).sort(function(a,b){return suppMap[b].ov-suppMap[a].ov;});

	return {groupMap,gpMap,plantMap,piMap,suppMap,siMap,spMap,giMap,groups,plants,supps};
}

// Build one scorecard block. prefix = "fuel" or "rm"
function pisCategoryCard(prefix, icon, label, colorAccent, colorBg, colorBorder) {
	var pId  = "pis-"+prefix+"-pct-num";
	var ovId = "pis-"+prefix+"-val-ov";
	var rvId = "pis-"+prefix+"-val-rv";
	var pvId = "pis-"+prefix+"-val-pv";
	var pgId = "pis-"+prefix+"-progressbar";
	var plId = "pis-"+prefix+"-progresslabel";
	var stId = "pis-"+prefix+"-statusbadge";
	var smId = "pis-"+prefix+"-statusmsg";
	var pnId = "pis-"+prefix+"-pct-lbl";

	return "<div id='pis-"+prefix+"-card' style='flex:1;min-width:320px;background:#fff;"
		+"border-radius:18px;border:2px solid "+colorBorder+";box-shadow:0 4px 20px rgba(0,0,0,0.06);"
		+"padding:24px 26px;display:flex;flex-direction:column;gap:14px'>"
		// Header
		+"<div style='display:flex;align-items:center;gap:10px;margin-bottom:2px'>"
		+"<div style='width:36px;height:36px;border-radius:10px;background:"+colorBg+";display:flex;align-items:center;justify-content:center;font-size:18px'>"+icon+"</div>"
		+"<div>"
		+"<p style='margin:0;font-size:16px;font-weight:900;color:#0F172A'>"+label+"</p>"
		+"<p style='margin:0;font-size:11px;color:#94A3B8;font-weight:600'>Purchase Tracker</p>"
		+"</div>"
		+"<div id='"+stId+"' style='margin-left:auto;display:inline-flex;align-items:center;background:#FEF9C3;border:1.5px solid #FDE68A;border-radius:99px;padding:5px 14px'>"
		+"<span id='"+smId+"' style='font-size:12px;font-weight:800;color:#B45309'>Loading…</span>"
		+"</div>"
		+"</div>"
		// Stat tiles
		+"<div style='display:flex;gap:10px;flex-wrap:wrap'>"
		+miniStat(ovId,"Ordered","#1D4ED8","#DBEAFE","#93C5FD")
		+miniStat(rvId,"Received","#15803D","#DCFCE7","#86EFAC")
		+miniStat(pvId,"Pending","#B91C1C","#FEE2E2","#FCA5A5")
		// pct box
		+"<div id='pis-"+prefix+"-pctbox' style='flex:0 0 110px;background:#FEF9C3;border:2px solid #FDE68A;"
		+"border-radius:14px;padding:14px 16px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center'>"
		+"<div id='"+pId+"' style='font-size:36px;font-weight:900;color:#B45309;line-height:1'>—</div>"
		+"<div id='"+pnId+"' style='font-size:11px;font-weight:700;color:#B45309;margin-top:4px'>Delivery Rate</div>"
		+"</div>"
		+"</div>"
		// Progress bar
		+"<div>"
		+"<div style='display:flex;justify-content:space-between;margin-bottom:5px'>"
		+"<span style='font-size:11px;color:#94A3B8;font-weight:600'>Delivery progress</span>"
		+"<span id='"+plId+"' style='font-size:11px;font-weight:800;color:#B45309'>—</span>"
		+"</div>"
		+"<div style='height:10px;background:#F1F5F9;border-radius:99px;overflow:hidden'>"
		+"<div id='"+pgId+"' style='height:100%;width:0%;background:#B45309;border-radius:99px;transition:width .6s ease'></div>"
		+"</div>"
		+"</div>"
		+"</div>";
}

function miniStat(id, label, tc, bg, bd) {
	return "<div style='flex:1;min-width:100px;background:"+bg+";border:1.5px solid "+bd+";"
		+"border-radius:12px;padding:14px 16px'>"
		+"<p style='margin:0;font-size:10px;color:"+tc+";font-weight:700;text-transform:uppercase;letter-spacing:.5px'>"+label+"</p>"
		+"<p id='"+id+"' style='margin:6px 0 0;font-size:20px;font-weight:900;color:"+tc+";line-height:1'>—</p>"
		+"</div>";
}

function pisApplyCategoryTotals(prefix, GT) {
	var gP = pct(GT.ov, GT.rv);
	var remaining = GT.ov - GT.rv;
	var statusMsg = gP>=80 ? "✅ On track"
		: gP>=50 ? "⚠️ Partial"
		: "🔴 Behind";

	function setHtml(id, html) { var el=document.getElementById(id); if(el) el.innerHTML=html; }
	function setStyle(id, prop, val) { var el=document.getElementById(id); if(el) el.style[prop]=val; }

	setHtml("pis-"+prefix+"-val-ov", "₹"+pSF(GT.ov));
	setHtml("pis-"+prefix+"-val-rv", "₹"+pSF(GT.rv));
	setHtml("pis-"+prefix+"-val-pv", "₹"+pSF(remaining));
	setHtml("pis-"+prefix+"-pct-num", gP+"%");
	setHtml("pis-"+prefix+"-pct-lbl", "Delivery Rate");
	setHtml("pis-"+prefix+"-progresslabel", gP+"% of ₹"+pSF(GT.ov)+" delivered");
	setHtml("pis-"+prefix+"-statusmsg", statusMsg);

	// Colors
	var box = document.getElementById("pis-"+prefix+"-pctbox");
	if(box){ box.style.background=FB(gP); box.style.borderColor=FBD(gP); }
	setStyle("pis-"+prefix+"-pct-num","color",FC(gP));
	setStyle("pis-"+prefix+"-pct-lbl","color",FC(gP));

	var bar = document.getElementById("pis-"+prefix+"-progressbar");
	if(bar){ bar.style.width=gP+"%"; bar.style.background=FC(gP); }
	setStyle("pis-"+prefix+"-progresslabel","color",FC(gP));

	var badge = document.getElementById("pis-"+prefix+"-statusbadge");
	if(badge){ badge.style.background=FB(gP); badge.style.borderColor=FBD(gP); }
	setStyle("pis-"+prefix+"-statusmsg","color",FC(gP));
}


function pisFetchCategoryTotals(report, category, prefix) {
	var fv = {};
	try { fv = frappe.query_report.get_filter_values ? frappe.query_report.get_filter_values() : {}; } catch(e) {}
	// Override category; keep other filters (date, company, plant, supplier)
	var filters = Object.assign({}, fv, { category: category });

	frappe.call({
		method: "frappe.desk.query_report.run",
		args: { report_name: report.report_name, filters: filters },
		callback: function(r) {
			var rows = (r.message && r.message.result) || [];
			var GT = { ov: 0, rv: 0, pv: 0 };
			rows.forEach(function(row) {
				if (row.indent === 0) {
					GT.ov += +(row.ordered_value || 0);
					GT.rv += +(row.received_value || 0);
					GT.pv += +(row.pending_value || 0);
				}
			});
			pisApplyCategoryTotals(prefix, GT);
		}
	});
}


function pis_render(report){
	pis_destroy_all();
	window._pisAllCharts=[];
	var rows=report.data||[];
	var D=pis_aggregate(rows);
	window._PI=D;

	// Determine which category cards to show based on current filter
	var currentCategory = "";
	try { currentCategory = (frappe.query_report.get_filter_value("category")||"").trim(); } catch(e){}

	var showFuel = !currentCategory || currentCategory === "Fuel";
	var showRM   = !currentCategory || currentCategory === "RM";



	// Build visible cards
	var cardsHtml = "<div style='display:flex;gap:16px;flex-wrap:wrap;align-items:stretch'>";
	if (showFuel) {
		cardsHtml += pisCategoryCard("fuel", "⛽", "Fuel", "#F59E0B", "#FFFBEB", "#FCD34D");
	}
	if (showRM) {
		cardsHtml += pisCategoryCard("rm", "🌾", "Raw Material (RM)", "#7C3AED", "#F5F3FF", "#C4B5FD");
	}
	cardsHtml += "</div>";

	var layer1 =
		"<div style='background:#F8FAFC;border-radius:20px;padding:24px 28px;border:1.5px solid #E2E8F0;"
		+"box-shadow:0 4px 24px rgba(59,130,246,0.05);margin-bottom:4px'>"
		+"<p style='margin:0 0 16px;font-size:12px;font-weight:700;color:#94A3B8'>"
		+(currentCategory
			? "Showing <b style='color:#374151'>"+currentCategory+"</b> — filtered by Category"
			: "Showing both <b style='color:#374151'>Fuel</b> and <b style='color:#374151'>RM</b> — change the Category filter to focus on one")
		+"</p>"
		+cardsHtml
		+"</div>";


	var layer2 =
		"<div style='background:#fff;border-radius:20px;border:1.5px solid #E2E8F0;box-shadow:0 4px 20px rgba(0,0,0,0.05);overflow:hidden;margin-bottom:4px'>"
		+"<div style='padding:22px 28px;border-bottom:1.5px solid #F1F5F9;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px'>"
		+"<div><p style='margin:0;font-size:17px;font-weight:900;color:#0F172A'>🏭 Plant-by-Plant Breakdown</p>"
		+"<p style='margin:4px 0 0;font-size:12px;color:#94A3B8'>Click any bar to see that plant's groups &amp; items in detail below</p></div>"
		+"</div>"
		+"<div style='padding:24px 28px'>"
		+"<div style='position:relative;height:380px'><canvas id='c-overview'></canvas></div>"
		+"</div>"
		+"<div id='plant-detail-panel' style='display:none;border-top:1.5px solid #F1F5F9;padding:24px 28px'></div>"
		+"</div>";


	var layer3 =
		"<div style='background:#fff;border-radius:20px;border:1.5px solid #E2E8F0;box-shadow:0 4px 20px rgba(0,0,0,0.05);overflow:hidden;margin-bottom:4px'>"
		+"<div style='padding:22px 28px;border-bottom:1.5px solid #F1F5F9;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px'>"
		+"<div><p style='margin:0;font-size:17px;font-weight:900;color:#0F172A'>🤝 Supplier Performance</p>"
		+"<p style='margin:4px 0 0;font-size:12px;color:#94A3B8'>Click any bar to see what that supplier supplies &amp; where</p></div>"
		+"</div>"
		+"<div style='padding:24px 28px'>"
		+"<div style='position:relative;height:380px'><canvas id='c-supp-bar'></canvas></div>"
		+"</div>"
		+"<div id='supp-detail-panel' style='display:none;border-top:1.5px solid #F1F5F9;padding:24px 28px'></div>"
		+"</div>";


	var tRows = D.supps.map(function(s,i){
		var sm=D.suppMap[s]; var p=pct(sm.ov,sm.rv);
		var k=encodeURIComponent(s).replace(/%/g,"_");
		return "<tr style='border-bottom:1px solid #F1F5F9;cursor:pointer'"
			+" onmouseover=\"this.style.background='#F8FAFF'\" onmouseout=\"this.style.background=''\""
			+" onclick='pisRowDrill(\""+s.replace(/\\/g,"\\\\").replace(/"/g,"&quot;")+"\",event)'>"
			+"<td style='padding:11px 16px;font-weight:700;color:#1E293B;font-size:13px'>"+(i+1)+". "+s+"</td>"
			+"<td style='padding:11px 16px;text-align:center'><span style='background:#EEF2FF;color:#4F46E5;font-weight:700;font-size:11px;padding:2px 8px;border-radius:99px'>"+Object.keys(sm.items).length+" items</span></td>"
			+"<td style='padding:11px 16px;text-align:center'><span style='background:#FFFBEB;color:#B45309;font-weight:700;font-size:11px;padding:2px 8px;border-radius:99px'>"+Object.keys(sm.plants).length+" plants</span></td>"
			+"<td style='padding:11px 16px;text-align:right;font-weight:800;color:#1D4ED8;font-size:13px'>₹"+pF(Math.round(sm.ov))+"</td>"
			+"<td style='padding:11px 16px;text-align:right;font-weight:800;color:#15803D;font-size:13px'>₹"+pF(Math.round(sm.rv))+"</td>"
			+"<td style='padding:11px 16px;text-align:right;font-weight:800;color:#B91C1C;font-size:13px'>₹"+pF(Math.round(sm.pv))+"</td>"
			+"<td style='padding:11px 16px;text-align:right'>"+progCell(p)+"</td>"
			+"</tr>"
			+"<tr id='srow-"+k+"' style='display:none'><td colspan='7' style='padding:0;background:#F8FAFF'>"
			+"<div id='sinl-"+k+"' style='padding:16px 20px'></div></td></tr>";
	}).join("");

	var layer4 =
		"<div style='background:#fff;border-radius:20px;border:1.5px solid #E2E8F0;box-shadow:0 4px 20px rgba(0,0,0,0.05);overflow:hidden'>"
		+"<div style='padding:18px 24px;border-bottom:1.5px solid #F1F5F9;display:flex;align-items:center;justify-content:space-between;cursor:pointer'"
		+" onclick='pisToggleLayer4()'>"
		+"<div><p style='margin:0;font-size:16px;font-weight:900;color:#0F172A'>📋 Full Supplier Detail Table</p>"
		+"<p style='margin:3px 0 0;font-size:12px;color:#94A3B8'>All "+D.supps.length+" suppliers · click row to expand items</p></div>"
		+"<span id='layer4-chevron' style='font-size:20px;color:#94A3B8;transition:transform .2s'>▼</span>"
		+"</div>"
		+"<div id='layer4-body' style='display:none;overflow-x:auto'>"
		+"<table style='width:100%;border-collapse:collapse;font-size:13px;min-width:680px'>"
		+"<thead><tr style='background:#F9FAFB;border-bottom:1.5px solid #E2E8F0'>"
		+"<th style='text-align:left;padding:11px 16px;font-weight:800;color:#374151'>Supplier</th>"
		+"<th style='text-align:center;padding:11px 16px;font-weight:800;color:#4F46E5'>Items</th>"
		+"<th style='text-align:center;padding:11px 16px;font-weight:800;color:#B45309'>Plants</th>"
		+"<th style='text-align:right;padding:11px 16px;font-weight:800;color:#1D4ED8'>Ordered ₹</th>"
		+"<th style='text-align:right;padding:11px 16px;font-weight:800;color:#15803D'>Received ₹</th>"
		+"<th style='text-align:right;padding:11px 16px;font-weight:800;color:#B91C1C'>Pending ₹</th>"
		+"<th style='text-align:right;padding:11px 16px;font-weight:800;color:#374151'>Delivery</th>"
		+"</tr></thead><tbody>"+tRows+"</tbody></table></div></div>";


	$(".layout-main-section .page-form.flex").after(
		"<div id='pis-wrapper' style='"
		+"font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif;"
		+"padding:4px 0 20px;'>"

		+sectionWrap("1","🎯 At a Glance","Category scorecards — Fuel &amp; RM separated",layer1,true)
		+sectionWrap("2","🏭 Plants","Delivery by plant — click any bar to dig in",layer2,true)
		+sectionWrap("3","🤝 Suppliers","Who is supplying what and how well",layer3,true)
		+sectionWrap("4","📋 Full Detail","Complete numbers — for accountants &amp; analysts",layer4,false)
		+"</div>"
	);

	// Load Chart.js then draw
	function go(){
		var tries=0;
		(function chk(){
			var ok=document.getElementById("c-overview")&&document.getElementById("c-supp-bar");
			if(ok){ drawOverviewBar(); drawSuppBar(); }
			else if(tries++<60) setTimeout(chk,100);
		})();
	}
	if(typeof Chart!=="undefined") requestAnimationFrame(function(){requestAnimationFrame(go);});
	else{
		var sc=document.createElement("script");
		sc.src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js";
		sc.onload=function(){requestAnimationFrame(function(){requestAnimationFrame(go);});};
		document.head.appendChild(sc);
	}

	// Fetch separate Fuel and RM totals (always using other active filters,
	// overriding only the category dimension)
	if (showFuel) pisFetchCategoryTotals(report, "Fuel", "fuel");
	if (showRM)   pisFetchCategoryTotals(report, "RM",   "rm");
}

// ─── section accordion wrapper ───────────────────────────────
function sectionWrap(n,title,sub,inner,open){
	var id="sec-body-"+n;
	return "<div style='background:#fff;border-radius:20px;border:1.5px solid #E2E8F0;"
		+"box-shadow:0 4px 20px rgba(0,0,0,0.04);overflow:hidden;margin-bottom:12px'>"
		+"<div style='padding:18px 26px;background:linear-gradient(90deg,#F8FAFC,#fff);"
		+"border-bottom:"+(open?"1.5px solid #F1F5F9":"none")+";cursor:pointer;display:flex;align-items:center;justify-content:space-between'"
		+" onclick='pisToggleSec(\""+n+"\")'>"
		+"<div style='display:flex;align-items:center;gap:14px'>"
		+"<div style='width:32px;height:32px;border-radius:10px;background:linear-gradient(135deg,#93C5FD,#60A5FA);"
		+"color:#fff;font-weight:900;font-size:13px;display:flex;align-items:center;justify-content:center'>"+n+"</div>"
		+"<div><p style='margin:0;font-size:16px;font-weight:900;color:#0F172A'>"+title+"</p>"
		+"<p style='margin:1px 0 0;font-size:12px;color:#94A3B8'>"+sub+"</p></div></div>"
		+"<span id='sec-chev-"+n+"' style='font-size:16px;color:#94A3B8;transition:transform .2s;"
		+"transform:"+(open?"rotate(180deg)":"rotate(0deg)")+"'>▼</span>"
		+"</div>"
		+"<div id='"+id+"' style='display:"+(open?"block":"none")+"'>"+inner+"</div>"
		+"</div>";
}
window.pisToggleSec=function(n){
	var body=document.getElementById("sec-body-"+n);
	var chev=document.getElementById("sec-chev-"+n);
	if(!body) return;
	var open=body.style.display==="none";
	body.style.display=open?"block":"none";
	if(chev) chev.style.transform=open?"rotate(180deg)":"rotate(0deg)";
	if(open){
		if(n==="2"&&!window._overviewDrawn) drawOverviewBar();
		if(n==="3"&&!window._suppBarDrawn) drawSuppBar();
	}
};
window.pisToggleLayer4=function(){
	var b=document.getElementById("layer4-body"),c=document.getElementById("layer4-chevron");
	if(!b) return;
	var open=b.style.display==="none";
	b.style.display=open?"block":"none";
	if(c) c.style.transform=open?"rotate(180deg)":"rotate(0deg)";
};

// ─── progress cell ────────────────────────────────────────────
function progCell(p){
	return "<div style='display:flex;align-items:center;gap:8px;justify-content:flex-end'>"
		+"<div style='width:60px;height:6px;border-radius:99px;background:#E2E8F0;overflow:hidden'>"
		+"<div style='height:100%;width:"+p+"%;background:"+FC(p)+";border-radius:99px'></div></div>"
		+"<span style='font-size:13px;font-weight:800;color:"+FC(p)+";min-width:34px;text-align:right'>"+p+"%</span>"
		+"</div>";
}


window._overviewDrawn=false;
function drawOverviewBar(){
	window._overviewDrawn=true;
	var canvas=document.getElementById("c-overview"); if(!canvas) return;
	var D=window._PI;
	var plants=D.plants;
	var labels=plants.map(function(p){return p.length>16?p.substr(0,14)+"…":p;});

	var dataRV=plants.map(function(p){return D.plantMap[p].rv||0;});
	var dataPV=plants.map(function(p){return D.plantMap[p].pv||0;});

	var c=new Chart(canvas,{type:"bar",plugins:[VP("vov")],
		data:{labels:labels,datasets:[
			{label:"Received",data:dataRV,backgroundColor:"#A7F3D0",borderColor:"#34D399",borderWidth:1,borderRadius:6,borderSkipped:false,barPercentage:plants.length<=4?.5:.7,categoryPercentage:.85,stack:"s"},
			{label:"Pending", data:dataPV,backgroundColor:"#FECACA",borderColor:"#F87171",borderWidth:1,borderRadius:6,borderSkipped:false,barPercentage:plants.length<=4?.5:.7,categoryPercentage:.85,stack:"s"}
		]},
		options:{responsive:true,maintainAspectRatio:false,layout:{padding:{top:40,right:10,left:2,bottom:4}},
			onClick:function(evt,els){
				var idx=-1;
				if(els&&els.length)idx=els[0].index;
				else{var rect=canvas.getBoundingClientRect(),xP=(evt.native||evt).clientX-rect.left,meta=c.getDatasetMeta(0),best=999;meta.data.forEach(function(b,i){var d=Math.abs(b.x-xP);if(d<best&&d<(b.width||40)){best=d;idx=i;}});}
				if(idx>=0) pisShowPlantDetail(plants[idx],idx);
			},
			plugins:{legend:{display:true,position:"top",labels:{boxWidth:12,font:{size:11,weight:"600"},color:"#374151"}},
				tooltip:{padding:12,callbacks:{
				title:function(t){return plants[t[0].dataIndex];},
				label:function(c2){return "  "+c2.dataset.label+": ₹"+pF(Math.round(c2.parsed.y));},
				afterBody:function(t){var p=plants[t[0].dataIndex],pm=window._PI.plantMap[p],pp=pct(pm.ov,pm.rv);return["  Ordered: ₹"+pF(Math.round(pm.ov)),"  Delivery: "+pp+"%","  Click to explore"];}
			}}},
			scales:{x:{stacked:true,grid:{display:false},ticks:{color:"#374151",font:{size:11,weight:"600"},maxRotation:35,autoSkip:false}},
				y:{stacked:true,beginAtZero:true,grid:{color:"rgba(0,0,0,0.04)"},ticks:{color:"#6B7280",font:{size:11},callback:function(v){return pSF(v);}}}
			}
		}
	});
	window._pisAllCharts.push(c);
	window._overviewChart=c;
}


window._suppBarDrawn=false;
function drawSuppBar(){
	window._suppBarDrawn=true;
	var canvas=document.getElementById("c-supp-bar"); if(!canvas) return;
	var D=window._PI;
	var s8=D.supps.slice(0,8);
	var labels=s8.map(function(s){return s.length>16?s.substr(0,14)+"…":s;});

	var dataRV=s8.map(function(s){return D.suppMap[s].rv||0;});
	var dataPV=s8.map(function(s){return D.suppMap[s].pv||0;});

	var c=new Chart(canvas,{type:"bar",plugins:[VP("vsb")],
		data:{labels:labels,datasets:[
			{label:"Received",data:dataRV,backgroundColor:"#A7F3D0",borderColor:"#34D399",borderWidth:1,borderRadius:6,borderSkipped:false,barPercentage:.65,categoryPercentage:.85,stack:"s"},
			{label:"Pending", data:dataPV,backgroundColor:"#FECACA",borderColor:"#F87171",borderWidth:1,borderRadius:6,borderSkipped:false,barPercentage:.65,categoryPercentage:.85,stack:"s"}
		]},
		options:{responsive:true,maintainAspectRatio:false,layout:{padding:{top:40,right:10,left:2,bottom:4}},
			onClick:function(evt,els){
				var idx=-1;
				if(els&&els.length)idx=els[0].index;
				else{var rect=canvas.getBoundingClientRect(),xP=(evt.native||evt).clientX-rect.left,meta=c.getDatasetMeta(0),best=999;meta.data.forEach(function(b,i){var d=Math.abs(b.x-xP);if(d<best&&d<(b.width||40)){best=d;idx=i;}});}
				if(idx>=0) pisShowSuppDetail(s8[idx],idx);
			},
			plugins:{legend:{display:true,position:"top",labels:{boxWidth:12,font:{size:11,weight:"600"},color:"#374151"}},
				tooltip:{padding:12,callbacks:{
				title:function(t){return s8[t[0].dataIndex];},
				label:function(c2){return "  "+c2.dataset.label+": ₹"+pF(Math.round(c2.parsed.y));},
				afterBody:function(t){var s=s8[t[0].dataIndex],sm=window._PI.suppMap[s],pp=pct(sm.ov,sm.rv);return["  Ordered: ₹"+pF(Math.round(sm.ov)),"  Delivery: "+pp+"%","  Click for detail"];}
			}}},
			scales:{x:{stacked:true,grid:{display:false},ticks:{color:"#374151",font:{size:11,weight:"600"},maxRotation:35,autoSkip:false}},
				y:{stacked:true,beginAtZero:true,grid:{color:"rgba(0,0,0,0.04)"},ticks:{color:"#6B7280",font:{size:11},callback:function(v){return pSF(v);}}}
			}
		}
	});
	window._pisAllCharts.push(c);
}


window.pisShowPlantDetail=function(plant,pi){
	var sec=document.getElementById("sec-body-2"); if(sec&&sec.style.display==="none") pisToggleSec("2");
	var panel=document.getElementById("plant-detail-panel"); if(!panel) return;
	if(panel.getAttribute("data-p")===plant&&panel.style.display!=="none"){panel.style.display="none";panel.setAttribute("data-p","");return;}
	panel.setAttribute("data-p",plant);

	var D=window._PI;
	var pm=D.plantMap[plant];
	var col=PAL[pi%PAL.length],cdk=PAL_DK[pi%PAL_DK.length];
	var p=pct(pm.ov,pm.rv);

	var grpList=Object.keys(D.gpMap).filter(function(g){return D.gpMap[g][plant];})
		.sort(function(a,b){return (D.gpMap[b][plant].ov||0)-(D.gpMap[a][plant].ov||0);});

	var grpRows=grpList.map(function(grp,gi){
		var gpd=D.gpMap[grp][plant];
		var gp2=pct(gpd.ov,gpd.rv);
		var gcol=PAL[gi%PAL.length];
		var items=Object.keys(D.piMap[plant]||{}).filter(function(it){return D.giMap[grp]&&D.giMap[grp][it];})
			.sort(function(a,b){return D.piMap[plant][b].ov-D.piMap[plant][a].ov;});

		var itemRows=items.map(function(item,ii){
			var id=D.piMap[plant][item];
			var ip=pct(id.ov,id.rv);
			var slist=Object.keys(id.supps||{}).filter(function(k){return k.indexOf("__d")===-1;}).join(", ")||"—";
			return "<tr style='border-bottom:1px solid #F8FAFC'>"
				+"<td style='padding:9px 14px;padding-left:48px;font-weight:600;color:#374151;font-size:12px'>"+item
				+"<div style='font-size:10px;color:#94A3B8;margin-top:1px'>"+slist.substr(0,60)+(slist.length>60?"…":"")+"</div></td>"
				+"<td style='padding:9px 14px;text-align:right;font-weight:700;color:#1D4ED8;font-size:12px;white-space:nowrap'>₹"+pSF(id.ov)+"</td>"
				+"<td style='padding:9px 14px;text-align:right;font-weight:700;color:#15803D;font-size:12px;white-space:nowrap'>₹"+pSF(id.rv)+"</td>"
				+"<td style='padding:9px 14px;text-align:right;font-weight:700;color:#B91C1C;font-size:12px;white-space:nowrap'>₹"+pSF(id.pv)+"</td>"
				+"<td style='padding:9px 14px;text-align:right'>"+progCell(ip)+"</td>"
				+"</tr>";
		}).join("");

		return "<tr style='border-bottom:1px solid #F1F5F9;background:"+PAL_BG[gi%PAL_BG.length]+"22'>"
			+"<td style='padding:12px 14px'>"
			+"<div style='display:flex;align-items:center;gap:8px'>"
			+"<span style='width:22px;height:22px;border-radius:6px;background:"+gcol+";color:#fff;font-size:10px;font-weight:900;display:flex;align-items:center;justify-content:center;flex-shrink:0'>"+(gi+1)+"</span>"
			+"<span style='font-weight:800;color:#1E293B;font-size:13px'>"+grp+"</span>"
			+"</div></td>"
			+"<td style='padding:12px 14px;text-align:right;font-weight:800;color:#1D4ED8;font-size:13px'>₹"+pSF(gpd.ov)+"</td>"
			+"<td style='padding:12px 14px;text-align:right;font-weight:800;color:#15803D;font-size:13px'>₹"+pSF(gpd.rv)+"</td>"
			+"<td style='padding:12px 14px;text-align:right;font-weight:800;color:#B91C1C;font-size:13px'>₹"+pSF(gpd.pv)+"</td>"
			+"<td style='padding:12px 14px;text-align:right'>"+progCell(gp2)+"</td>"
			+"</tr>"
			+itemRows;
	}).join("");

	panel.innerHTML=
		"<div style='margin-bottom:14px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;justify-content:space-between'>"
		+"<div style='display:flex;align-items:center;gap:10px'>"
		+"<div style='width:10px;height:32px;border-radius:5px;background:linear-gradient(180deg,"+col+","+cdk+")'></div>"
		+"<div>"
		+"<p style='margin:0;font-size:17px;font-weight:900;color:#0F172A'>"+plant+"</p>"
		+"<p style='margin:2px 0 0;font-size:12px;color:#94A3B8'>"+grpList.length+" groups &middot; "+Object.keys(pm.items).length+" items &middot; "+p+"% delivered</p>"
		+"</div></div>"
		+"<div style='display:flex;gap:10px;flex-wrap:wrap'>"
		+"<span style='font-size:13px;font-weight:800;background:#DBEAFE;color:#1D4ED8;padding:6px 14px;border-radius:8px;border:1px solid #93C5FD'>📦 ₹"+pSF(pm.ov)+"</span>"
		+"<span style='font-size:13px;font-weight:800;background:#DCFCE7;color:#15803D;padding:6px 14px;border-radius:8px;border:1px solid #86EFAC'>✅ ₹"+pSF(pm.rv)+"</span>"
		+"<span style='font-size:13px;font-weight:800;background:#FEE2E2;color:#B91C1C;padding:6px 14px;border-radius:8px;border:1px solid #FCA5A5'>⏳ ₹"+pSF(pm.pv)+"</span>"
		+"<button onclick=\"document.getElementById('plant-detail-panel').style.display='none'\" style='font-size:12px;padding:6px 14px;border-radius:8px;cursor:pointer;border:1.5px solid #D1D5DB;background:#fff;font-weight:700;color:#6B7280'>✕ Close</button>"
		+"</div></div>"
		+"<div style='overflow-x:auto;border-radius:12px;border:1.5px solid #E2E8F0;overflow:hidden'>"
		+"<table style='width:100%;border-collapse:collapse;min-width:560px;font-size:13px'>"
		+"<thead><tr style='background:#F9FAFB;border-bottom:1.5px solid #E2E8F0'>"
		+"<th style='text-align:left;padding:11px 14px;font-weight:800;color:#374151'>Group / Item</th>"
		+"<th style='text-align:right;padding:11px 14px;font-weight:800;color:#1D4ED8'>Ordered ₹</th>"
		+"<th style='text-align:right;padding:11px 14px;font-weight:800;color:#15803D'>Received ₹</th>"
		+"<th style='text-align:right;padding:11px 14px;font-weight:800;color:#B91C1C'>Pending ₹</th>"
		+"<th style='text-align:right;padding:11px 14px;font-weight:800;color:#374151'>Delivery</th>"
		+"</tr></thead><tbody>"+grpRows+"</tbody></table></div>";
	panel.style.display="block";
	setTimeout(function(){panel.scrollIntoView({behavior:"smooth",block:"start"});},80);
};


window.pisShowSuppDetail=function(supp,si){
	var sec=document.getElementById("sec-body-3"); if(sec&&sec.style.display==="none") pisToggleSec("3");
	var panel=document.getElementById("supp-detail-panel"); if(!panel) return;
	if(panel.getAttribute("data-s")===supp&&panel.style.display!=="none"){panel.style.display="none";panel.setAttribute("data-s","");return;}
	panel.setAttribute("data-s",supp);

	var D=window._PI;
	var sm=D.suppMap[supp];
	var col=PAL[si%PAL.length],cdk=PAL_DK[si%PAL_DK.length];
	var p=pct(sm.ov,sm.rv);
	var plantList=Object.keys(sm.plants||{});

	var plantRows=plantList.map(function(plant,pi2){
		var spd=(D.spMap[supp]||{})[plant]||{}; if(!spd.ov) return "";
		var pp=pct(spd.ov,spd.rv);
		var pcol=PAL[pi2%PAL.length];
		var items=Object.keys(spd.items||{}).sort(function(a,b){return spd.items[b].ov-spd.items[a].ov;});
		var iRows=items.map(function(item,ii){
			var id=spd.items[item];
			var ip=pct(id.ov,id.rv);
			return "<tr style='border-bottom:1px solid #F8FAFC'>"
				+"<td style='padding:9px 14px;padding-left:52px;font-weight:600;color:#374151;font-size:12px'>"+item
				+(id.uom?"<span style='color:#94A3B8;margin-left:6px;font-size:10px'>"+id.uom+"</span>":"")+"</td>"
				+"<td style='padding:9px 14px;text-align:right;font-weight:700;color:#1D4ED8;font-size:12px;white-space:nowrap'>₹"+pSF(id.ov)+"</td>"
				+"<td style='padding:9px 14px;text-align:right;font-weight:700;color:#15803D;font-size:12px;white-space:nowrap'>₹"+pSF(id.rv)+"</td>"
				+"<td style='padding:9px 14px;text-align:right;font-weight:700;color:#B91C1C;font-size:12px;white-space:nowrap'>₹"+pSF(id.pv)+"</td>"
				+"<td style='padding:9px 14px;text-align:right'>"+progCell(ip)+"</td>"
				+"</tr>";
		}).join("");
		return "<tr style='border-bottom:1px solid #F1F5F9;background:"+PAL_BG[pi2%PAL_BG.length]+"22'>"
			+"<td style='padding:12px 14px'><div style='display:flex;align-items:center;gap:8px'>"
			+"<span style='width:22px;height:22px;border-radius:6px;background:"+pcol+";color:#fff;font-size:10px;font-weight:900;display:flex;align-items:center;justify-content:center'>"+(pi2+1)+"</span>"
			+"<span style='font-weight:800;color:#1E293B;font-size:13px'>"+plant+"</span>"
			+"</div></td>"
			+"<td style='padding:12px 14px;text-align:right;font-weight:800;color:#1D4ED8;font-size:13px'>₹"+pSF(spd.ov)+"</td>"
			+"<td style='padding:12px 14px;text-align:right;font-weight:800;color:#15803D;font-size:13px'>₹"+pSF(spd.rv)+"</td>"
			+"<td style='padding:12px 14px;text-align:right;font-weight:800;color:#B91C1C;font-size:13px'>₹"+pSF(spd.pv)+"</td>"
			+"<td style='padding:12px 14px;text-align:right'>"+progCell(pp)+"</td>"
			+"</tr>"+iRows;
	}).join("");

	panel.innerHTML=
		"<div style='margin-bottom:14px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;justify-content:space-between'>"
		+"<div style='display:flex;align-items:center;gap:10px'>"
		+"<div style='width:10px;height:32px;border-radius:5px;background:linear-gradient(180deg,"+col+","+cdk+")'></div>"
		+"<div>"
		+"<p style='margin:0;font-size:17px;font-weight:900;color:#0F172A'>"+supp+"</p>"
		+"<p style='margin:2px 0 0;font-size:12px;color:#94A3B8'>"+Object.keys(sm.items).length+" items &middot; "+plantList.length+" plants &middot; "+p+"% delivered</p>"
		+"</div></div>"
		+"<div style='display:flex;gap:10px;flex-wrap:wrap'>"
		+"<span style='font-size:13px;font-weight:800;background:#DBEAFE;color:#1D4ED8;padding:6px 14px;border-radius:8px;border:1px solid #93C5FD'>📦 ₹"+pSF(sm.ov)+"</span>"
		+"<span style='font-size:13px;font-weight:800;background:#DCFCE7;color:#15803D;padding:6px 14px;border-radius:8px;border:1px solid #86EFAC'>✅ ₹"+pSF(sm.rv)+"</span>"
		+"<span style='font-size:13px;font-weight:800;background:#FEE2E2;color:#B91C1C;padding:6px 14px;border-radius:8px;border:1px solid #FCA5A5'>⏳ ₹"+pSF(sm.pv)+"</span>"
		+"<button onclick=\"document.getElementById('supp-detail-panel').style.display='none'\" style='font-size:12px;padding:6px 14px;border-radius:8px;cursor:pointer;border:1.5px solid #D1D5DB;background:#fff;font-weight:700;color:#6B7280'>✕ Close</button>"
		+"</div></div>"
		+"<div style='overflow-x:auto;border-radius:12px;border:1.5px solid #E2E8F0;overflow:hidden'>"
		+"<table style='width:100%;border-collapse:collapse;min-width:560px;font-size:13px'>"
		+"<thead><tr style='background:#F9FAFB;border-bottom:1.5px solid #E2E8F0'>"
		+"<th style='text-align:left;padding:11px 14px;font-weight:800;color:#374151'>Plant / Item</th>"
		+"<th style='text-align:right;padding:11px 14px;font-weight:800;color:#1D4ED8'>Ordered ₹</th>"
		+"<th style='text-align:right;padding:11px 14px;font-weight:800;color:#15803D'>Received ₹</th>"
		+"<th style='text-align:right;padding:11px 14px;font-weight:800;color:#B91C1C'>Pending ₹</th>"
		+"<th style='text-align:right;padding:11px 14px;font-weight:800;color:#374151'>Delivery</th>"
		+"</tr></thead><tbody>"+plantRows+"</tbody></table></div>";
	panel.style.display="block";
	setTimeout(function(){panel.scrollIntoView({behavior:"smooth",block:"start"});},80);
};


window.pisRowDrill=function(supp,evt){
	if(evt) evt.stopPropagation();
	var k=encodeURIComponent(supp).replace(/%/g,"_");
	var row=document.getElementById("srow-"+k);
	var inl=document.getElementById("sinl-"+k);
	if(!row||!inl) return;
	if(row.style.display!=="none"){row.style.display="none";return;}

	var D=window._PI;
	var im=D.siMap[supp]||{};
	var items=Object.keys(im).filter(function(it){return(im[it].ov||0)>0;}).sort(function(a,b){return im[b].ov-im[a].ov;});
	if(!items.length) return;
	var sm=D.suppMap[supp]||{};
	var plantList=Object.keys(sm.plants||{}).join(", ")||"—";

	inl.innerHTML="<p style='margin:0 0 10px;font-size:13px;font-weight:800;color:#374151'>"+supp
		+" <span style='font-weight:500;color:#94A3B8;font-size:11px'>— Plants: "+plantList+"</span></p>"
		+"<table style='width:100%;border-collapse:collapse;font-size:12px'>"
		+"<thead><tr style='background:#EFF6FF;border-bottom:1px solid #BFDBFE'>"
		+"<th style='text-align:left;padding:8px 12px;font-weight:700;color:#374151'>Item</th>"
		+"<th style='text-align:right;padding:8px 12px;font-weight:700;color:#1D4ED8'>Ordered ₹</th>"
		+"<th style='text-align:right;padding:8px 12px;font-weight:700;color:#15803D'>Received ₹</th>"
		+"<th style='text-align:right;padding:8px 12px;font-weight:700;color:#B91C1C'>Pending ₹</th>"
		+"<th style='text-align:right;padding:8px 12px;font-weight:700;color:#6366F1'>Qty (Qtl)</th>"
		+"<th style='text-align:right;padding:8px 12px;font-weight:700;color:#374151'>Delivery</th>"
		+"</tr></thead><tbody>"
		+items.map(function(item){
			var id=im[item];
			var p2=pct(id.ov,id.rv);
			var pl=Object.keys(id.plants||{}).join(", ")||"—";
			return "<tr style='border-bottom:1px solid #F0F4F8'>"
				+"<td style='padding:8px 12px;font-weight:600;color:#1E293B'>"+item
				+"<div style='font-size:10px;color:#94A3B8'>"+pl+"</div></td>"
				+"<td style='padding:8px 12px;text-align:right;color:#1D4ED8;font-weight:700;white-space:nowrap'>₹"+pF(Math.round(id.ov))+"</td>"
				+"<td style='padding:8px 12px;text-align:right;color:#15803D;font-weight:700;white-space:nowrap'>₹"+pF(Math.round(id.rv))+"</td>"
				+"<td style='padding:8px 12px;text-align:right;color:#B91C1C;font-weight:700;white-space:nowrap'>₹"+pF(Math.round(id.pv))+"</td>"
				+"<td style='padding:8px 12px;text-align:right;color:#6366F1;font-weight:700'>"+pF(Math.round(id.oq||0))+"</td>"
				+"<td style='padding:8px 12px;text-align:right'>"+progCell(p2)+"</td>"
				+"</tr>";
		}).join("")
		+"</tbody></table>";
	row.style.display="";
};