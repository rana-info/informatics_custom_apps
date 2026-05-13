// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["Asset Repair Analysis"] = {
    filters: [

        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "MultiSelectList",
            options: "Company",
            reqd: 1,
            get_data: function(txt) {
                return frappe.db.get_link_options("Company", txt);
            }
        },

        {
            fieldname: "branch",
            label: __("Branch"),
            fieldtype: "MultiSelectList",
            options: "Branch",
            get_data: function(txt) {
                return frappe.db.get_link_options("Branch", txt);
            }
        },

        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: frappe.datetime.month_start(),
            reqd: 1
        },

        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            default: frappe.datetime.month_end(),
            reqd: 1
        },

        {
            fieldname: "report_type",
            label: __("Report Type"),
            fieldtype: "Select",
            options: "Summary\nDetailed\nItem Wise",
            default: "Summary",
            reqd: 1
        }

    ]
};