// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["Procurement Budget Consumption"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company"
        },
        {
            fieldname: "fiscal_year",
            label: __("Fiscal Year"),
            fieldtype: "Link",
            options: "Fiscal Year"
        },
        {
            fieldname: "gl_accounts",
            label: __("GL Accounts"),
            fieldtype: "MultiSelectList",
            get_data: function(txt) {
                return frappe.db.get_link_options(
                    "Account",
                    txt,
                    {
                        company: frappe.query_report.get_filter_value("company"),
                        is_group: 0
                    }
                );
            }
        }
    ]
};