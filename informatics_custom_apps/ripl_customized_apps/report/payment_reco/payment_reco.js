// Copyright (c) 2024, Your Company and contributors
// Payment Reconciliation Report — mirrors Payment Reconciliation form filters exactly

frappe.query_reports["Payment Reco"] = {

 filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            default: frappe.defaults.get_default("company"),
			reqd : 1        
        },
        {
            fieldname: "party_type",
            label: __("Party type"),
            fieldtype: "Link",
            options: "DocType",
			reqd :1,
            get_query() {
                return {
                    filters: {
                        name: ["in", Object.keys(frappe.boot.party_account_types || {})],
                    },
                };
            },
            on_change() {
                frappe.query_report.set_filter_value("party", "");
            },
        },
        {
            fieldname: "party",
            label: __("Party"),
            fieldtype: "Dynamic Link",
            options: "party_type",
        },
        {
            fieldname: "receivable_payable_account",
            label: __("Account"),
            fieldtype: "Link",
            options: "Account",
            get_query() {
                const company    = frappe.query_report.get_filter_value("company");
                const party_type = frappe.query_report.get_filter_value("party_type");
                const filters    = { is_group: 0 };
                if (company)    filters.company = company;
                if (party_type) filters.account_type = frappe.boot.party_account_types[party_type];
                return { filters };
            },
        },
        {
            fieldname: "section",
            label: __("Section"),
            fieldtype: "Select",
            options: "\nPayment\nJournal Entry\nDr/Cr Note\nInvoice\nAllocation",
        },
        {
            fieldname: "from_payment_date",
            label: __("From payment date"),
            fieldtype: "Date",
        },
        {
            fieldname: "to_payment_date",
            label: __("To payment date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
        },
        {
            fieldname: "from_invoice_date",
            label: __("From invoice date"),
            fieldtype: "Date",
        },
        {
            fieldname: "to_invoice_date",
            label: __("To invoice date"),
            fieldtype: "Date",
        },
        {
            fieldname: "payment_name",
            label: __("Payment reference"),
            fieldtype: "Data",
        },
        {
            fieldname: "invoice_name",
            label: __("Invoice number"),
            fieldtype: "Data",
        },
        {
            fieldname: "bank_cash_account",
            label: __("Bank / cash account"),
            fieldtype: "Link",
            options: "Account",
            get_query() {
                const company = frappe.query_report.get_filter_value("company");
                return {
                    filters: [
                        ["Account", "is_group",     "=", 0],
                        ["Account", "account_type", "in", ["Bank", "Cash"]],
                        ...(company ? [["Account", "company", "=", company]] : []),
                    ],
                };
            },
        },
        {
            fieldname: "cost_center",
            label: __("Cost center"),
            fieldtype: "Link",
            options: "Cost Center",
            get_query() {
                const company = frappe.query_report.get_filter_value("company");
                return { filters: { is_group: 0, ...(company ? { company } : {}) } };
            },
        },
        {
            fieldname: "minimum_payment_amount",
            label: __("Min payment amount"),
            fieldtype: "Currency",
        },
        {
            fieldname: "maximum_payment_amount",
            label: __("Max payment amount"),
            fieldtype: "Currency",
        },
        {
            fieldname: "minimum_invoice_amount",
            label: __("Min invoice amount"),
            fieldtype: "Currency",
        },
        {
            fieldname: "maximum_invoice_amount",
            label: __("Max invoice amount"),
            fieldtype: "Currency",
        },
        {
            fieldname: "payment_limit",
            label: __("Payment row limit"),
            fieldtype: "Int",
            default: 0,   // 0 = unlimited
        },
        {
            fieldname: "invoice_limit",
            label: __("Invoice row limit"),
            fieldtype: "Int",
            default: 0,   // 0 = unlimited
        },
    ],
 
 
    formatter(value, row, column, data, default_formatter) {
        if (!data) return value;
 
        value = default_formatter(value, row, column, data);
 
        // Section badge colours
        if (column.fieldname === "section" && data.section) {
            const palette = {
                "Payment":       ["#E6F1FB", "#185FA5"],
                "Journal Entry": ["#EEEDFE", "#534AB7"],
                "Dr/Cr Note":    ["#FBEAF0", "#993556"],
                "Invoice":       ["#EAF3DE", "#3B6D11"],
                "Allocation":    ["#FAEEDA", "#854F0B"],
            };
            const [bg, fg] = palette[data.section] || ["#F1EFE8", "#5F5E5A"];
            return `<span style="
                background:${bg}; color:${fg};
                border-radius:10px; padding:2px 8px;
                font-size:11px; font-weight:500; white-space:nowrap;
            ">${__(data.section)}</span>`;
        }
 
        // Highlight non-zero difference amounts in amber
        if (column.fieldname === "difference_amount" && flt(data.difference_amount) !== 0) {
            return `<span style="color:#854F0B; font-weight:500;">${value}</span>`;
        }
 
        // Highlight fully-outstanding invoices in red
        if (column.fieldname === "outstanding_amount" && flt(data.outstanding_amount) > 0) {
            return `<span style="color:#A32D2D;">${value}</span>`;
        }
 
        // Zero outstanding = reconciled, show in green
        if (column.fieldname === "outstanding_amount" && value && flt(data.outstanding_amount) === 0) {
            return `<span style="color:#0F6E56;">${value}</span>`;
        }
 
        // Advance payments highlighted
        if (column.fieldname === "is_advance" && data.is_advance) {
            return `<span style="
                background:#FAEEDA; color:#633806;
                border-radius:10px; padding:2px 8px; font-size:11px;
            ">Advance</span>`;
        }
 
        return value;
    },
 
 
    onload(report) {
        this._report = report;
    },
 
    after_datatable_render(datatable) {
        const wrapper = cur_page.page.wrapper.find(".report-summary");
        wrapper.remove();
 
        const data = frappe.query_report.data || [];
        if (!data.length) return;
 
        const summary = _build_summary(data);
 
        const bar = $(`
            <div class="report-summary" style="
                display:grid;
                grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
                gap:10px; padding:12px 0 20px;
            ">
                ${summary.map(s => `
                    <div style="
                        background:var(--fg-color);
                        border:0.5px solid var(--border-color);
                        border-radius:8px; padding:14px 16px;
                    ">
                        <div style="font-size:11px; color:var(--text-muted); margin-bottom:4px;">
                            ${__(s.label)}
                        </div>
                        <div style="font-size:20px; font-weight:500; color:${s.color};">
                            ${s.value}
                        </div>
                    </div>
                `).join("")}
            </div>
        `);
 
        cur_page.page.wrapper
            .find(".datatable-wrapper")
            .before(bar);
    },
};
 
 
/**
 * Build KPI summary cards from the raw report data.
 * @param {Array} data
 * @returns {Array<{label, value, color}>}
 */
function _build_summary(data) {
    const fmt = v =>
        format_currency(v, frappe.defaults.get_default("currency") || "USD");
 
    const payments   = data.filter(r => r.section === "Payment");
    const journals   = data.filter(r => r.section === "Journal Entry");
    const notes      = data.filter(r => r.section === "Dr/Cr Note");
    const invoices   = data.filter(r => r.section === "Invoice");
    const allocs     = data.filter(r => r.section === "Allocation");
 
    const sumField = (rows, field) =>
        rows.reduce((acc, r) => acc + flt(r[field] || 0), 0);
 
    const totalPayments   = sumField(payments, "amount") + sumField(journals, "amount") + sumField(notes, "amount");
    const totalOutstanding = sumField(invoices, "outstanding_amount");
    const totalAllocated  = sumField(allocs, "allocated_amount");
    const diffCount       = allocs.filter(r => flt(r.difference_amount) !== 0).length;
 
    return [
        {
            label: "Total payments",
            value: fmt(totalPayments),
            color: "#185FA5",
        },
        {
            label: "Unreconciled invoices",
            value: invoices.length,
            color: "#854F0B",
        },
        {
            label: "Outstanding amount",
            value: fmt(totalOutstanding),
            color: "#A32D2D",
        },
        {
            label: "Total allocated",
            value: fmt(totalAllocated),
            color: "#0F6E56",
        },
        {
            label: "Rows with forex diff",
            value: diffCount,
            color: diffCount > 0 ? "#A32D2D" : "#0F6E56",
        },
        {
            label: "Total entries",
            value: data.length,
            color: "var(--text-color)",
        },
    ];
}