// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["Cost Analysis"] = {
	 "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "default": frappe.defaults.get_user_default("Company"),
            "reqd": 1
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.year_start(),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname": "branch",
            "label": __("Plant / Branch"),
            "fieldtype": "Link",
            "options": "Branch",
            "reqd": 0
        },
        {
            "fieldname": "segment",
            "label": __("Segment"),
            "fieldtype": "Link",
            "options": "Segment",
            "reqd": 0
        },
        {
            "fieldname": "show_quantitative_data",
            "label": __("Show Quantitative Data"),
            "fieldtype": "Check",
            "default": 0
        },
        {
            "fieldname": "show_summary",
            "label": __("Show Summary Only"),
            "fieldtype": "Check",
            "default": 0
        },
        {
            "fieldname": "hide_zero_amounts",
            "label": __("Hide Zero Amounts"),
            "fieldtype": "Check",
            "default": 0
        }
    ],

   "formatter": function(value, row, column, data, default_formatter) {
    if (data && data.is_blank_row) {
        return "";
    }

    value = default_formatter(value, row, column, data);

        if (!data) return value;

        if (data.is_quant_header) {
            return `<div style="font-size: 13px; font-weight: 700; color: #1e293b; text-transform: uppercase; padding: 4px 0;">${value}</div>`;
        }

        if (data.is_quant_subtotal) {
            // Total rows now carry indent: 0 (server-side) so the datatable's
            // tree/collapse grouping never nests them under the section
            // header - this is what keeps them visible when the header is
            // collapsed. Since that also strips the native indent-1 padding
            // the detail rows get, add it back manually on the description
            // column so the Total row still looks nested under its header.
            let extra_padding = column.fieldname === "expense_category" ? "padding-left: 22px;" : "";
            return `<span style="font-weight: 700; color: #0f172a; border-top: 1px solid #cbd5e1; border-bottom: 1px solid #cbd5e1; display: block; padding: 2px 0; ${extra_padding}">${value}</span>`;
        }

        if (data.is_header) {
            if (column.fieldname === "expense_category") {
                return `<div style="font-size: 13px; font-weight: 700; color: #1e293b; text-transform: uppercase; letter-spacing: 0.5px; padding: 4px 0;">${value}</div>`;
            } else {
                return "";
            }
        }
        if (column.fieldname === "gl_code" && value) {
            value = `<span style="background-color: #f1f5f9; color: #475569; font-family: monospace; font-size: 11px; font-weight: 600; padding: 2px 6px; border-radius: 4px; border: 1px solid #e2e8f0;">${value}</span>`;
        }

        if (column.fieldname === "budget_amount" || column.fieldname === "budget_per_bl") {
            value = `<span style="color: #7c3aed; font-weight: 600;">${value}</span>`;
        }

        if (column.fieldname.startsWith("per_bl_") || column.fieldname === "total_per_bl") {
            value = `<span style="color: #0369a1; font-weight: 600;">${value}</span>`;
        }

        if (data.is_subtotal) {
            value = `<span style="font-weight: 700; color: #334155; border-bottom: 1px dashed #cbd5e1; display: block; padding: 2px 0;">${value}</span>`;
        }

        if (data.is_total_row) {
            value = `<span style="font-size: 12px; font-weight: 800; color: #0f172a; border-top: 1.5px solid #0f172a; border-bottom: 1.5px solid #0f172a; display: block; padding: 3px 0;">${value}</span>`;
        }

        if (data.is_grand_total) {
            value = `<span style="font-size: 13px; font-weight: 800; color: #0f172a; background-color: #f8fafc; border-top: 2px solid #0f172a; border-bottom: 2px double #0f172a; display: block; padding: 4px 6px; border-radius: 2px;">${value}</span>`;
        }

        // Cell-level Per BL vs Budget Per BL coloring (Requirement: color
        // only the Per BL cell that was actually compared to budget, not
        // the whole row). Each per_bl_<month> and total_per_bl cell carries
        // its own <fieldname>_color computed server-side in the report.py.
        var cell_color = null;
        if (column.fieldname === "total_per_bl") {
            cell_color = data.total_per_bl_color;
        } else if (column.fieldname.startsWith("per_bl_")) {
            cell_color = data[column.fieldname + "_color"];
        }

        if (cell_color === "red") {
            value = `<div style="background-color: #fde2e2; border-radius: 2px; padding: 1px 4px;">${value}</div>`;
        } else if (cell_color === "green") {
            value = `<div style="background-color: #ddf5e2; border-radius: 2px; padding: 1px 4px;">${value}</div>`;
        }

        return value;
    }
};