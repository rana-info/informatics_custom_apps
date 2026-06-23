frappe.query_reports["Dispatch Order Balance Report"] = {

filters: [
	{ fieldname: "customer", label: "Customer", fieldtype: "Link", options: "Customer" },
	{ fieldname: "po_no", label: "P.O. No", fieldtype: "Data" },
	{ fieldname: "item_code", label: "Item", fieldtype: "Link", options: "Item" },
	{ fieldname: "quarter", label: "Quarter", fieldtype: "Select", options: [""] },
	{ fieldname: "from_date", label: "From Date", fieldtype: "Date" },
	{ fieldname: "to_date", label: "To Date", fieldtype: "Date" }
],

onload(report) {
    frappe.call({
        method: "informatics_custom_apps.ripl_customized_apps.report.dispatch_order_balance_report.dispatch_order_balance_report.get_ethanol_quarters",
        callback(r) {
            const quarters = (r.message || []).map(d => d.quarter).filter(Boolean);

            setTimeout(() => {
                try {
                    const filterObj = report.get_filter("quarter");

                    filterObj.df.options = ["", ...quarters].join("\n");
                    filterObj.last_options = null;

                    filterObj.$input
                        .empty()
                        .append(
                            ["", ...quarters].map(q =>
                                `<option value="${q}">${q}</option>`
                            ).join("")
                        );

                    console.log("✅ Quarters loaded:", quarters);
                } catch(e) {
                    console.error("❌ Quarter filter error:", e);
                }
            }, 500);
        }
    });
},

formatter(value, row, column, data, default_formatter) {

	// ── Totals row ───────────────────────────────────────────────────
	if (data && data.customer_name === "TOTAL") {
	if (column.fieldname === "customer_name") {
	return `<span style="font-weight:500;color:var(--color-text-primary)">TOTAL</span>`;
	}
	if (value === "" || value === null || value === undefined) {
	return "";
	}
	return `<span style="font-weight:500">${default_formatter(value, row, column, data)}</span>`;
}

// ── Quarter sum columns ─────────────────────────────────────────
if (column.fieldname && column.fieldname.startsWith("qsum_")) {
if (value === "" || value === null || value === undefined) {
return `<span style="color:var(--color-border-secondary)">—</span>`;
}
const num = parseFloat(value) || 0;
if (num === 0) {
return `<span style="color:var(--color-text-tertiary);font-weight:500">0.000</span>`;
}
return `<span style="color:#185FA5;font-weight:700">${parseFloat(value).toLocaleString('en-IN', {minimumFractionDigits:3, maximumFractionDigits:3})}</span>`;
}

// ── Month columns ────────────────────────────────────────────────
if (column.fieldname && column.fieldname.startsWith("month_")) {
if (value === "" || value === null || value === undefined) {
// blank = before PO date
return `<span style="color:var(--color-border-secondary)">—</span>`;
}
const num = parseFloat(value) || 0;
if (num === 0) {
return `<span style="color:var(--color-text-tertiary)">0.000</span>`;
}
return `<span style="color:#185FA5;font-weight:500">${parseFloat(value).toLocaleString('en-IN', {minimumFractionDigits:3, maximumFractionDigits:3})}</span>`;
}

// ── Fulfillment % badge ──────────────────────────────────────────
if (column.fieldname === "fulfillment_pct" && data) {
const pct = data.fulfillment_pct || 0;
if (pct >= 100) {
return `<span style="background:#EAF3DE;color:#27500A;padding:2px 9px;border-radius:10px;font-size:11px;font-weight:500">✓ ${pct}%</span>`;
} else if (pct >= 50) {
return `<span style="background:#FAEEDA;color:#633806;padding:2px 9px;border-radius:10px;font-size:11px;font-weight:500">◑ ${pct}%</span>`;
} else if (pct > 0) {
return `<span style="background:#FCEBEB;color:#791F1F;padding:2px 9px;border-radius:10px;font-size:11px;font-weight:500">▼ ${pct}%</span>`;
}
return `<span style="color:var(--color-text-tertiary);font-size:11px">— 0%</span>`;
}

// ── Balance Qty ──────────────────────────────────────────────────
if (column.fieldname === "balance_qty" && data) {
const bal = parseFloat(data.balance_qty) || 0;
const fmt = default_formatter(value, row, column, data);
if (bal === 0) return `<span style="color:#27500A;font-weight:500">${fmt}</span>`;
return `<span style="color:#A32D2D;font-weight:500">${fmt}</span>`;
}

return default_formatter(value, row, column, data);
}
};