// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

// report.js

frappe.query_reports["Group Wise Purchase Order Status"] = {

      onload: function (report) {

        report.page.add_inner_button(__("Refresh"), function () {
            frappe.query_report.refresh();
        });

        report.page.add_inner_button(__("Clear Filters"), function () {
            frappe.query_report.clear_filters();
        });

		        frappe.call({
            method: "erpnext.accounts.utils.get_fiscal_year",
            args: {
                date: frappe.datetime.get_today(),
                company: frappe.defaults.get_user_default("Company")
            },
            callback: function (r) {

                if (!r.message) return;

                if (!frappe.query_report.get_filter_value("from_date")) {
                    frappe.query_report.set_filter_value("from_date", r.message[1]);
                }

                if (!frappe.query_report.get_filter_value("to_date")) {
                    frappe.query_report.set_filter_value("to_date", frappe.datetime.get_today());
                }
            }
        });

    },
    
    filters: [

        {
            fieldname: "from_date",
            label: "From Date",
            fieldtype: "Date"
        },

        {
            fieldname: "to_date",
            label: "To Date",
            fieldtype: "Date"
        },

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
    get_data: function (txt) {

        let companies = frappe.query_report.get_filter_value("company");

        return frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Warehouse",
                fields: ["custom_branch"],
                filters: companies ? [
                    ["company", "in", companies],
                    ["custom_branch", "like", `%${txt}%`]
                ] : [
                    ["custom_branch", "like", `%${txt}%`]
                ],
                limit_page_length: 1000
            }
        }).then(r => {

            let plants = [...new Set(
                (r.message || [])
                    .map(d => d.custom_branch)
                    .filter(Boolean)
            )];

            return plants.map(p => ({
                value: p,
                description: p
            }));
        });
    }
},

        {
            fieldname: "item_group",
            label: "Item Group",
            fieldtype: "MultiSelectList",
            get_data: function(txt) {
                return frappe.db.get_link_options("Item Group", txt);
            }
        }

    ]
};
