// Copyright (c) 2026, Monil Kamboj and contributors

frappe.query_reports["Fuel and RM(444,446,448) Purchase Tracker - MGT"] = {
	tree: true,
	name_field: "name",
	parent_field: "parent",
	initial_depth: 1,

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;

		// ── First-column routing ──────────────────────────────────
		if (column.fieldname === "name") {
			if (data.indent === 0) {
				// Item Group: docname = "GRP::RealGroupName" → link to item-group list
				var realGrp = (data.docname || "").replace(/^GRP::/, "").split("::")[0];
				var link = '/app/item-group/' + encodeURIComponent(realGrp);
				value = '<a href="' + link + '" style="color:#1D4ED8;font-weight:900;font-size:13px">' + (data.name || realGrp) + '</a>';
			} else if (data.indent === 1) {
				// Plant / Branch: docname = "GRP::PlantName"
				var realPlant = (data.docname || "").replace(/^[^:]+::/, "").split("::")[0];
				var link2 = '/app/branch/' + encodeURIComponent(realPlant);
				value = '<a href="' + link2 + '" style="color:#0F172A;font-weight:800">' + (data.name || realPlant) + '</a>';
			} else if (data.indent === 2) {
				// PO: docname = "GRP::Plant::PO-XXXX"
				var parts = (data.docname || "").split("::");
				var poPart = parts[parts.length - 1];
				var link3 = '/app/purchase-order/' + encodeURIComponent(poPart);
				value = '<a href="' + link3 + '" style="color:#374151;font-weight:600">' + (data.name || poPart) + '</a>';
			} else if (data.indent === 3 && data.docname) {
				// Item inside PO
				value = '<span style="color:#6B7280">' + (data.name || "") + '</span>';
			}
		}

		// ── Row styling ───────────────────────────────────────────
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

// ════════════════════════════════════════════════════════════════
//  DESTROY / CLEANUP
// ════════════════════════════════════════════════════════════════
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

// ════════════════════════════════════════════════════════════════
//  CONSTANTS
// ════════════════════════════════════════════════════════════════
var PAL    = ["#3B82F6","#10B981","#EF4444","#F59E0B","#8B5CF6","#EC4899","#06B6D4","#F97316","#14B8A6","#6366F1"];
var PAL_DK = ["#1D4ED8","#047857","#B91C1C","#B45309","#6D28D9","#BE185D","#0E7490","#C2410C","#0F766E","#4338CA"];
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

// ── 3D bar plugin ─────────────────────────────────────────────
var P3D={id:"p3d",afterDatasetsDraw:function(chart){
	var ctx=chart.ctx; ctx.save();
	chart.data.datasets.forEach(function(ds,di){
		var meta=chart.getDatasetMeta(di); if(meta.hidden) return;
		var bgs=Array.isArray(ds.backgroundColor)?ds.backgroundColor:[ds.backgroundColor];
		meta.data.forEach(function(bar,i){
			var col=bgs[i%bgs.length]||"#3B82F6", d=6;
			var dk=function(h,a){h=h.replace("#","");if(h.length===3)h=h[0]+h[0]+h[1]+h[1]+h[2]+h[2];return "rgb("+Math.max(0,parseInt(h.substr(0,2),16)-a)+","+Math.max(0,parseInt(h.substr(2,2),16)-a)+","+Math.max(0,parseInt(h.substr(4,2),16)-a)+")";};
			var x=bar.x-bar.width/2,y=bar.y,w=bar.width,h=Math.abs(bar.base-bar.y);
			if(h<2) return;
			ctx.beginPath();ctx.moveTo(x+w,y);ctx.lineTo(x+w+d,y-d);ctx.lineTo(x+w+d,y-d+h);ctx.lineTo(x+w,y+h);ctx.closePath();ctx.fillStyle=dk(col,50);ctx.fill();
			ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+d,y-d);ctx.lineTo(x+w+d,y-d);ctx.lineTo(x+w,y);ctx.closePath();ctx.fillStyle=dk(col,20);ctx.fill();
		});
	});
	ctx.restore();
}};

// ── value label plugin ────────────────────────────────────────
function VP(id){return{id:id,afterDatasetsDraw:function(chart){
	var ctx=chart.ctx, top=(chart.chartArea||{top:36}).top; ctx.save();
	chart.data.datasets.forEach(function(ds,di){
		var meta=chart.getDatasetMeta(di); if(meta.hidden) return;
		var bgs=Array.isArray(ds.backgroundColor)?ds.backgroundColor:[ds.backgroundColor];
		meta.data.forEach(function(bar,i){
			var val=ds.data[i]; if(!val) return;
			var h=Math.abs(bar.base-bar.y), topY=bar.y;
			if(h<18){var col=bgs[i%bgs.length]||"#3B82F6",bx=bar.x-bar.width/2,by=bar.base-18,bw=bar.width;topY=by;ctx.beginPath();ctx.moveTo(bx+4,by);ctx.lineTo(bx+bw-4,by);ctx.quadraticCurveTo(bx+bw,by,bx+bw,by+4);ctx.lineTo(bx+bw,by+18);ctx.lineTo(bx,by+18);ctx.lineTo(bx,by+4);ctx.quadraticCurveTo(bx,by,bx+4,by);ctx.closePath();ctx.fillStyle=col;ctx.fill();}
			var lbl=pSF(val),bh=16,lblY=topY-bh-3;
			ctx.font="700 10px system-ui,sans-serif";
			var tw=ctx.measureText(lbl).width,bw2=tw+8;
			if(lblY<top) lblY=top;
			ctx.beginPath();if(ctx.roundRect)ctx.roundRect(bar.x-bw2/2,lblY,bw2,bh,3);else ctx.rect(bar.x-bw2/2,lblY,bw2,bh);ctx.fillStyle="rgba(15,23,42,.12)";ctx.fill();
			ctx.fillStyle="#0F172A";ctx.textAlign="center";ctx.textBaseline="middle";
			ctx.fillText(lbl,bar.x,lblY+bh/2);
		});
	});
	ctx.restore();
}};}

// ════════════════════════════════════════════════════════════════
//  RENDER TRIGGER
// ════════════════════════════════════════════════════════════════
window._pisTimer=null;
function pis_handle_render(report){
	if(window._pisTimer) clearTimeout(window._pisTimer);
	window._pisTimer=setTimeout(function(){
		if((report.data||[]).some(function(r){return r.indent===3;})) pis_render(report);
		else pis_destroy_all();
	},350);
}

// ════════════════════════════════════════════════════════════════
//  DATA AGGREGATION
// ════════════════════════════════════════════════════════════════
function pis_aggregate(rows){
	// Maps
	var groupMap={}, gpMap={}, plantMap={}, piMap={}, suppMap={}, siMap={}, spMap={}, giMap={};
	// poSupp: capture supplier from indent-2 rows
	var poSupp={};
	rows.forEach(function(r){
		if(r.indent===2) poSupp[r.name]={supp:r.supplier||"Unknown",suppName:r.supplier_name||r.supplier||"Unknown"};
	});
	// walk tree tracking context
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

		// groupMap
		var gm=ensure(groupMap,grp,Object.assign({plants:{},items:{}},Z));
		add(gm);gm.plants[plant]=true;gm.items[item]=true;

		// gpMap[grp][plant]
		if(!gpMap[grp])gpMap[grp]={};
		var gp=ensure(gpMap[grp],plant,Object.assign({items:{},pos:{}},Z));
		add(gp);gp.items[item]=true;gp.pos[po]=true;

		// plantMap
		var pm=ensure(plantMap,plant,Object.assign({groups:{},items:{}},Z));
		add(pm);pm.groups[grp]=true;pm.items[item]=true;

		// piMap[plant][item] — supps stores detail keyed "suppName__d"
		if(!piMap[plant])piMap[plant]={};
		var pi=ensure(piMap[plant],item,Object.assign({uom:uom,supps:{}},Z));
		add(pi);
		if(!pi.supps[supp+"__d"])pi.supps[supp+"__d"]=Object.assign({},Z);
		add(pi.supps[supp+"__d"]);

		// suppMap
		var sm=ensure(suppMap,supp,Object.assign({plants:{},items:{}},Z));
		add(sm);sm.plants[plant]=true;sm.items[item]=true;

		// siMap[supp][item]
		if(!siMap[supp])siMap[supp]={};
		var si=ensure(siMap[supp],item,Object.assign({uom:uom,plants:{}},Z));
		add(si);si.plants[plant]=true;

		// spMap[supp][plant]
		if(!spMap[supp])spMap[supp]={};
		var spl=ensure(spMap[supp],plant,Object.assign({items:{}},Z));
		add(spl);
		if(!spl.items[item])spl.items[item]=Object.assign({uom:uom},Z);
		add(spl.items[item]);

		// giMap[grp][item]
		if(!giMap[grp])giMap[grp]={};
		var gi=ensure(giMap[grp],item,Object.assign({uom:uom,plants:{}},Z));
		add(gi);gi.plants[plant]=true;
	});

	var groups=Object.keys(groupMap).sort(function(a,b){return groupMap[b].ov-groupMap[a].ov;});
	var plants=Object.keys(plantMap).sort(function(a,b){return plantMap[b].ov-plantMap[a].ov;});
	var supps =Object.keys(suppMap).sort(function(a,b){return suppMap[b].ov-suppMap[a].ov;});

	return {groupMap,gpMap,plantMap,piMap,suppMap,siMap,spMap,giMap,groups,plants,supps};
}

// ════════════════════════════════════════════════════════════════
//  MAIN RENDER
// ════════════════════════════════════════════════════════════════
function pis_render(report){
	pis_destroy_all();
	window._pisAllCharts=[];
	var rows=report.data||[];
	var D=pis_aggregate(rows);
	window._PI=D;
	window._PIS_MODE="ov";

	// Grand totals
	var GT={ov:0,rv:0,pv:0,oq:0,rq:0,pq:0};
	D.plants.forEach(function(p){var m=D.plantMap[p];GT.ov+=m.ov;GT.rv+=m.rv;GT.pv+=m.pv;GT.oq+=m.oq;GT.rq+=m.rq;GT.pq+=m.pq;});
	var gP=pct(GT.ov,GT.rv);

	// ─────────────────────────────────────────────────────────
	// LAYER 1 — HEADLINE SCORECARD  (super simple, layman-friendly)
	// ─────────────────────────────────────────────────────────
	var remaining=GT.ov-GT.rv;
	var statusMsg = gP>=80
		? "✅ On track — most orders delivered"
		: gP>=50
		? "⚠️ Partially delivered — follow-up needed"
		: "🔴 Significantly behind — urgent action needed";
	var statusBg  = gP>=80?"#DCFCE7":gP>=50?"#FEF9C3":"#FEE2E2";
	var statusBd  = gP>=80?"#86EFAC":gP>=50?"#FDE68A":"#FCA5A5";

	var layer1 =
		"<div style='background:#fff;border-radius:20px;padding:28px 32px;border:1.5px solid #E2E8F0;box-shadow:0 4px 24px rgba(59,130,246,0.08);margin-bottom:4px'>"
		// status badge
		+"<div style='display:inline-flex;align-items:center;gap:8px;background:"+statusBg+";border:1.5px solid "+statusBd+";border-radius:99px;padding:7px 18px;margin-bottom:20px'>"
		+"<span style='font-size:13px;font-weight:800;color:"+FC(gP)+"'>"+statusMsg+"</span></div>"
		// big number + label
		+"<div style='display:flex;flex-wrap:wrap;gap:24px;align-items:stretch;margin-bottom:20px'>"
		+bigStat("Total Ordered",GT.ov,"How much we planned to buy","#1D4ED8","#DBEAFE","#93C5FD")
		+bigStat("Delivered So Far",GT.rv,"What we actually received","#15803D","#DCFCE7","#86EFAC")
		+bigStat("Still Pending",remaining,"What hasn't arrived yet","#B91C1C","#FEE2E2","#FCA5A5")
		+"<div style='flex:1;min-width:160px;background:"+FB(gP)+";border:2px solid "+FBD(gP)+";border-radius:16px;padding:20px 24px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center'>"
		+"<div style='font-size:48px;font-weight:900;color:"+FC(gP)+";line-height:1'>"+gP+"%</div>"
		+"<div style='font-size:13px;font-weight:700;color:"+FC(gP)+";margin-top:6px'>Delivery Rate</div>"
		+"<div style='font-size:11px;color:"+FC(gP)+";margin-top:4px'>"+D.plants.length+" plants &middot; "+D.supps.length+" suppliers</div>"
		+"</div>"
		+"</div>"
		// overall progress bar
		+"<div style='margin-bottom:6px;display:flex;justify-content:space-between'>"
		+"<span style='font-size:12px;color:#94A3B8;font-weight:600'>Overall delivery progress</span>"
		+"<span style='font-size:12px;font-weight:800;color:"+FC(gP)+"'>"+gP+"% of ₹"+pSF(GT.ov)+" delivered</span>"
		+"</div>"
		+"<div style='height:12px;background:#F1F5F9;border-radius:99px;overflow:hidden;box-shadow:inset 0 2px 4px rgba(0,0,0,0.06)'>"
		+"<div style='height:100%;width:"+gP+"%;background:linear-gradient(90deg,"+FC(gP)+","+FC(gP)+"cc);border-radius:99px;transition:width .6s ease'></div>"
		+"</div>"
		+"</div>";

	// ─────────────────────────────────────────────────────────
	// LAYER 2 — PLANT SCORECARD TILES  (one tile per plant)
	// ─────────────────────────────────────────────────────────
	var plantTiles = D.plants.map(function(plant,pi){
		var pm=D.plantMap[plant];
		var p=pct(pm.ov,pm.rv);
		var col=PAL[pi%PAL.length], cdk=PAL_DK[pi%PAL_DK.length], cbg=PAL_BG[pi%PAL_BG.length];
		var grpCount=Object.keys(pm.groups).length;
		return "<div style='break-inside:avoid;margin-bottom:14px;border:2px solid "+col+"28;border-radius:16px;padding:18px 20px;"
			+"background:linear-gradient(135deg,"+cbg+" 0%,#fff 70%);box-shadow:0 3px 14px "+col+"15;cursor:pointer;"
			+"transition:transform .15s,box-shadow .15s'"
			+" onmouseover=\"this.style.transform='translateY(-2px)';this.style.boxShadow='0 8px 24px "+col+"28'\""
			+" onmouseout=\"this.style.transform='';this.style.boxShadow='0 3px 14px "+col+"15'\""
			+" onclick=\"pisShowPlantDetail('"+plant.replace(/'/g,"\\'")+"',"+pi+")\">"
			+"<div style='display:flex;align-items:flex-start;gap:12px'>"
			+"<div style='width:36px;height:36px;min-width:36px;border-radius:10px;background:linear-gradient(135deg,"+col+","+cdk+");color:#fff;font-weight:900;font-size:14px;display:flex;align-items:center;justify-content:center;box-shadow:0 3px 8px "+col+"44'>"+(pi+1)+"</div>"
			+"<div style='flex:1;min-width:0'>"
			+"<div style='font-size:15px;font-weight:900;color:#0F172A;word-break:break-word'>"+plant+"</div>"
			+"<div style='font-size:11px;color:#94A3B8;margin-top:2px'>"+grpCount+" groups &middot; tap to explore</div>"
			+"</div>"
			+"<div style='text-align:right;flex-shrink:0'>"
			+"<div style='font-size:22px;font-weight:900;color:"+FC(p)+"'>"+p+"%</div>"
			+"<div style='font-size:10px;font-weight:700;color:"+FC(p)+"'>delivered</div>"
			+"</div></div>"
			+"<div style='margin-top:12px'>"
			+"<div style='height:7px;background:#E2E8F0;border-radius:99px;overflow:hidden'>"
			+"<div style='height:100%;width:"+p+"%;background:linear-gradient(90deg,"+col+","+cdk+");border-radius:99px'></div></div>"
			+"<div style='display:flex;justify-content:space-between;margin-top:6px'>"
			+"<span style='font-size:11px;color:#94A3B8'>Ordered: <b style=\"color:#1D4ED8\">₹"+pSF(pm.ov)+"</b></span>"
			+"<span style='font-size:11px;color:#94A3B8'>Pending: <b style=\"color:"+FC(p)+"\">₹"+pSF(pm.pv)+"</b></span>"
			+"</div>"
			+"</div>"
			+"</div>";
	}).join("");

	// Layer 2 chart area (single overview bar — all plants)
	var layer2 =
		"<div style='background:#fff;border-radius:20px;border:1.5px solid #E2E8F0;box-shadow:0 4px 20px rgba(0,0,0,0.05);overflow:hidden;margin-bottom:4px'>"
		+"<div style='padding:22px 28px;border-bottom:1.5px solid #F1F5F9;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px'>"
		+"<div><p style='margin:0;font-size:17px;font-weight:900;color:#0F172A'>🏭 Plant-by-Plant Breakdown</p>"
		+"<p style='margin:4px 0 0;font-size:12px;color:#94A3B8'>Click any plant card to see its groups &amp; items in detail below</p></div>"
		+"<div style='display:flex;gap:8px;flex-wrap:wrap'>"
		+"<button id='m-ov' onclick='pisMode(\"ov\")' style='"+BS(true)+"'>₹ Ordered</button>"
		+"<button id='m-rv' onclick='pisMode(\"rv\")' style='"+BS(false)+"'>₹ Received</button>"
		+"<button id='m-pv' onclick='pisMode(\"pv\")' style='"+BS(false)+"'>₹ Pending</button>"
		+"</div>"
		+"</div>"
		+"<div style='padding:24px 28px;display:flex;flex-wrap:wrap;gap:20px'>"
		// tiles grid
		+"<div style='flex:1;min-width:260px;columns:2 240px;column-gap:14px'>"+plantTiles+"</div>"
		// overview bar chart
		+"<div style='flex:2;min-width:300px'>"
		+"<div style='position:relative;height:280px'><canvas id='c-overview'></canvas></div>"
		+"</div>"
		+"</div>"
		// plant detail panel (hidden, shown on click)
		+"<div id='plant-detail-panel' style='display:none;border-top:1.5px solid #F1F5F9;padding:24px 28px'></div>"
		+"</div>";

	// ─────────────────────────────────────────────────────────
	// LAYER 3 — SUPPLIER SNAPSHOT
	// ─────────────────────────────────────────────────────────
	var suppTiles = D.supps.slice(0,8).map(function(s,i){
		var sm=D.suppMap[s];
		var p=pct(sm.ov,sm.rv);
		var col=PAL[i%PAL.length];
		return "<div style='break-inside:avoid;margin-bottom:12px;padding:14px 16px;border-radius:12px;"
			+"background:#F8FAFC;border:1.5px solid #E2E8F0;cursor:pointer;transition:background .12s'"
			+" onmouseover=\"this.style.background='#EFF6FF'\" onmouseout=\"this.style.background='#F8FAFC'\""
			+" onclick=\"pisShowSuppDetail('"+s.replace(/'/g,"\\'")+"',"+i+")\">"
			+"<div style='display:flex;align-items:center;gap:10px'>"
			+"<span style='width:28px;height:28px;min-width:28px;border-radius:8px;background:"+col+";color:#fff;font-size:11px;font-weight:900;display:flex;align-items:center;justify-content:center'>"+(i+1)+"</span>"
			+"<div style='flex:1;min-width:0'>"
			+"<div style='font-size:12px;font-weight:800;color:#1E293B;white-space:nowrap;overflow:hidden;text-overflow:ellipsis'>"+s+"</div>"
			+"<div style='font-size:11px;color:#94A3B8;margin-top:1px'>"+Object.keys(sm.items).length+" items &middot; "+Object.keys(sm.plants).length+" plants</div>"
			+"</div>"
			+"<div style='text-align:right;flex-shrink:0'>"
			+"<div style='font-size:16px;font-weight:900;color:"+FC(p)+"'>"+p+"%</div>"
			+"<div style='font-size:10px;color:#94A3B8;margin-top:1px'>₹"+pSF(sm.ov)+" ord</div>"
			+"</div></div>"
			+"<div style='margin-top:8px;height:5px;background:#E2E8F0;border-radius:99px;overflow:hidden'>"
			+"<div style='height:100%;width:"+p+"%;background:"+col+";border-radius:99px'></div>"
			+"</div></div>";
	}).join("");

	var layer3 =
		"<div style='background:#fff;border-radius:20px;border:1.5px solid #E2E8F0;box-shadow:0 4px 20px rgba(0,0,0,0.05);overflow:hidden;margin-bottom:4px'>"
		+"<div style='padding:22px 28px;border-bottom:1.5px solid #F1F5F9;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px'>"
		+"<div><p style='margin:0;font-size:17px;font-weight:900;color:#0F172A'>🤝 Supplier Performance</p>"
		+"<p style='margin:4px 0 0;font-size:12px;color:#94A3B8'>Click any supplier to see what they supply &amp; where</p></div>"
		+"</div>"
		+"<div style='padding:24px 28px;display:flex;flex-wrap:wrap;gap:20px'>"
		+"<div style='flex:1;min-width:260px;columns:2 220px;column-gap:14px'>"+suppTiles+"</div>"
		+"<div style='flex:2;min-width:300px'>"
		+"<div style='position:relative;height:280px'><canvas id='c-supp-bar'></canvas></div>"
		+"</div>"
		+"</div>"
		+"<div id='supp-detail-panel' style='display:none;border-top:1.5px solid #F1F5F9;padding:24px 28px'></div>"
		+"</div>";

	// ─────────────────────────────────────────────────────────
	// LAYER 4 — FULL DATA TABLE  (collapsible)
	// ─────────────────────────────────────────────────────────
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

	// ─────────────────────────────────────────────────────────
	// INJECT ALL LAYERS
	// ─────────────────────────────────────────────────────────
	$(".layout-main-section .page-form.flex").after(
		"<div id='pis-wrapper' style='"
		+"font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif;"
		+"padding:4px 0 20px;'>"

		// Accordion-style section headers
		+sectionWrap("1","🎯 At a Glance","The big picture in seconds",layer1,true)
		+sectionWrap("2","🏭 Plants","Delivery by plant — click any tile to dig in",layer2,false)
		+sectionWrap("3","🤝 Suppliers","Who is supplying what and how well",layer3,false)
		+sectionWrap("4","📋 Full Detail","Complete numbers — for accountants & analysts",layer4,false)
		+"</div>"
	);

	// load Chart.js
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
		+"<div style='width:32px;height:32px;border-radius:10px;background:linear-gradient(135deg,#3B82F6,#1D4ED8);"
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
	// redraw charts if opening
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

// ─── big stat card (Layer 1) ──────────────────────────────────
function bigStat(label,val,desc,tc,bg,bd){
	return "<div style='flex:1;min-width:150px;background:"+bg+";border:2px solid "+bd+";border-radius:16px;padding:20px 22px'>"
		+"<p style='margin:0;font-size:11px;color:"+tc+";font-weight:700;text-transform:uppercase;letter-spacing:.6px'>"+label+"</p>"
		+"<p style='margin:8px 0 2px;font-size:28px;font-weight:900;color:"+tc+";line-height:1'>₹"+pSF(val)+"</p>"
		+"<p style='margin:0;font-size:12px;color:"+tc+"88'>"+desc+"</p>"
		+"</div>";
}
// ─── progress cell ────────────────────────────────────────────
function progCell(p){
	return "<div style='display:flex;align-items:center;gap:8px;justify-content:flex-end'>"
		+"<div style='width:60px;height:6px;border-radius:99px;background:#E2E8F0;overflow:hidden'>"
		+"<div style='height:100%;width:"+p+"%;background:"+FC(p)+";border-radius:99px'></div></div>"
		+"<span style='font-size:13px;font-weight:800;color:"+FC(p)+";min-width:34px;text-align:right'>"+p+"%</span>"
		+"</div>";
}

// ════════════════════════════════════════════════════════════════
//  OVERVIEW BAR — all plants
// ════════════════════════════════════════════════════════════════
window._overviewDrawn=false;
function drawOverviewBar(){
	window._overviewDrawn=true;
	var canvas=document.getElementById("c-overview"); if(!canvas) return;
	var D=window._PI, mode=window._PIS_MODE||"ov";
	var plants=D.plants;
	var bgs=plants.map(function(_,i){return PAL[i%PAL.length];});
	var bds=plants.map(function(_,i){return PAL_DK[i%PAL_DK.length];});
	var data=plants.map(function(p){return D.plantMap[p][mode]||0;});
	var labels=plants.map(function(p){return p.length>16?p.substr(0,14)+"…":p;});

	var c=new Chart(canvas,{type:"bar",plugins:[P3D,VP("vov")],
		data:{labels:labels,datasets:[{label:"Value",data:data,backgroundColor:bgs,borderColor:bds,borderWidth:0,borderRadius:8,borderSkipped:false,barPercentage:plants.length<=4?.5:.7,categoryPercentage:.85}]},
		options:{responsive:true,maintainAspectRatio:false,layout:{padding:{top:40,right:10,left:2,bottom:4}},
			onClick:function(evt,els){
				var idx=-1;
				if(els&&els.length)idx=els[0].index;
				else{var rect=canvas.getBoundingClientRect(),xP=(evt.native||evt).clientX-rect.left,meta=c.getDatasetMeta(0),best=999;meta.data.forEach(function(b,i){var d=Math.abs(b.x-xP);if(d<best&&d<(b.width||40)){best=d;idx=i;}});}
				if(idx>=0) pisShowPlantDetail(plants[idx],idx);
			},
			plugins:{legend:{display:false},tooltip:{padding:12,callbacks:{
				title:function(t){return plants[t[0].dataIndex];},
				label:function(c2){var p=plants[c2.dataIndex],pm=window._PI.plantMap[p],pp=pct(pm.ov,pm.rv);
					return["  ₹"+pF(Math.round(c2.parsed.y)),"  Delivery: "+pp+"%","  Click to explore"];
				}
			}}},
			scales:{x:{grid:{display:false},ticks:{color:"#374151",font:{size:11,weight:"600"},maxRotation:35,autoSkip:false}},
				y:{beginAtZero:true,grid:{color:"rgba(0,0,0,0.04)"},ticks:{color:"#6B7280",font:{size:11},callback:function(v){return pSF(v);}}}
			}
		}
	});
	window._pisAllCharts.push(c);
	window._overviewChart=c;
}

// ════════════════════════════════════════════════════════════════
//  SUPPLIER BAR
// ════════════════════════════════════════════════════════════════
window._suppBarDrawn=false;
function drawSuppBar(){
	window._suppBarDrawn=true;
	var canvas=document.getElementById("c-supp-bar"); if(!canvas) return;
	var D=window._PI;
	var s8=D.supps.slice(0,8);
	var bgs=s8.map(function(_,i){return PAL[i%PAL.length];});
	var bds=s8.map(function(_,i){return PAL_DK[i%PAL_DK.length];});
	var data=s8.map(function(s){return D.suppMap[s].ov||0;});
	var labels=s8.map(function(s){return s.length>16?s.substr(0,14)+"…":s;});

	var c=new Chart(canvas,{type:"bar",plugins:[P3D,VP("vsb")],
		data:{labels:labels,datasets:[{label:"Ordered",data:data,backgroundColor:bgs,borderColor:bds,borderWidth:0,borderRadius:8,borderSkipped:false,barPercentage:.65,categoryPercentage:.85}]},
		options:{responsive:true,maintainAspectRatio:false,layout:{padding:{top:40,right:10,left:2,bottom:4}},
			onClick:function(evt,els){
				var idx=-1;
				if(els&&els.length)idx=els[0].index;
				else{var rect=canvas.getBoundingClientRect(),xP=(evt.native||evt).clientX-rect.left,meta=c.getDatasetMeta(0),best=999;meta.data.forEach(function(b,i){var d=Math.abs(b.x-xP);if(d<best&&d<(b.width||40)){best=d;idx=i;}});}
				if(idx>=0) pisShowSuppDetail(s8[idx],idx);
			},
			plugins:{legend:{display:false},tooltip:{padding:12,callbacks:{
				title:function(t){return s8[t[0].dataIndex];},
				label:function(c2){var s=s8[c2.dataIndex],sm=window._PI.suppMap[s],pp=pct(sm.ov,sm.rv);
					return["  Ordered: ₹"+pF(Math.round(c2.parsed.y)),"  Delivered: "+pp+"%","  Click for detail"];
				}
			}}},
			scales:{x:{grid:{display:false},ticks:{color:"#374151",font:{size:11,weight:"600"},maxRotation:35,autoSkip:false}},
				y:{beginAtZero:true,grid:{color:"rgba(0,0,0,0.04)"},ticks:{color:"#6B7280",font:{size:11},callback:function(v){return pSF(v);}}}
			}
		}
	});
	window._pisAllCharts.push(c);
}

// ════════════════════════════════════════════════════════════════
//  MODE TOGGLE
// ════════════════════════════════════════════════════════════════
window.pisMode=function(mode){
	window._PIS_MODE=mode;
	["ov","rv","pv"].forEach(function(k){
		var b=document.getElementById("m-"+k); if(b) b.style.cssText=BS(k===mode);
	});
	// redraw overview
	if(window._overviewChart){try{window._overviewChart.destroy();}catch(e){} window._overviewChart=null;}
	var canvas=document.getElementById("c-overview");
	if(canvas){ drawOverviewBar(); }
};

// ════════════════════════════════════════════════════════════════
//  PLANT DETAIL PANEL (Layer 2 drill)
// ════════════════════════════════════════════════════════════════
window.pisShowPlantDetail=function(plant,pi){
	// open section 2
	var sec=document.getElementById("sec-body-2"); if(sec&&sec.style.display==="none") pisToggleSec("2");
	var panel=document.getElementById("plant-detail-panel"); if(!panel) return;
	if(panel.getAttribute("data-p")===plant&&panel.style.display!=="none"){panel.style.display="none";panel.setAttribute("data-p","");return;}
	panel.setAttribute("data-p",plant);

	var D=window._PI;
	var pm=D.plantMap[plant];
	var col=PAL[pi%PAL.length],cdk=PAL_DK[pi%PAL_DK.length];
	var p=pct(pm.ov,pm.rv);

	// groups in this plant
	var grpList=Object.keys(D.gpMap).filter(function(g){return D.gpMap[g][plant];})
		.sort(function(a,b){return (D.gpMap[b][plant].ov||0)-(D.gpMap[a][plant].ov||0);});

	var grpRows=grpList.map(function(grp,gi){
		var gpd=D.gpMap[grp][plant];
		var gp2=pct(gpd.ov,gpd.rv);
		var gcol=PAL[gi%PAL.length];
		// items in this group+plant
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
			// item sub-rows
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

// ════════════════════════════════════════════════════════════════
//  SUPPLIER DETAIL PANEL (Layer 3 drill)
// ════════════════════════════════════════════════════════════════
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

	// Per-plant breakdown
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

// ════════════════════════════════════════════════════════════════
//  FULL TABLE ROW DRILL (Layer 4)
// ════════════════════════════════════════════════════════════════
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