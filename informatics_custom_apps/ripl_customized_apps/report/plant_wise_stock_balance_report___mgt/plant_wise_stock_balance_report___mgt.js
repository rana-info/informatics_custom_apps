// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["Plant Wise Stock Balance Report - MGT"] = {
    filters: [
       {
            fieldname: "company",
            label: "Company",
            fieldtype: "MultiSelectList",
            get_data: function(txt) {
                return frappe.db.get_link_options("Company", txt);
            }
        },

        {
            fieldname: "plant",
            label: "Plant",
            fieldtype: "MultiSelectList",
            get_data: async function(txt) {

                let companies = frappe.query_report.get_filter_value("company") || [];
                let filters = {};

                if (companies.length) {
                    filters.company = ["in", companies];
                }

                return frappe.db.get_link_options(
                    "Branch",
                    txt,
                    filters
                );
            }
        },
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1
        },

        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1
        }
    ]
};