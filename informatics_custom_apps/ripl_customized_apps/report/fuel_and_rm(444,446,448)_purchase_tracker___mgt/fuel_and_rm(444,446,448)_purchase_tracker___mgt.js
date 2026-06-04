// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["Fuel and RM(444,446,448) Purchase Tracker - MGT"] = {

    tree: true,
    name_field: "name",
    parent_field: "parent",
    initial_depth: 1,

    formatter: function(value, row, column, data, default_formatter) {

        value = default_formatter(value, row, column, data);

        if (!data) {
            return value;
        }

        if (
            column.fieldname === "name" &&
            data.doctype &&
            data.docname
        ) {
            value = `<a href="/app/${frappe.router.slug(data.doctype)}/${encodeURIComponent(data.docname)}">
                        ${value}
                    </a>`;
        }

        if (data.indent === 1) {
            return `<b>${value}</b>`;
        }

        if (data.indent === 2) {
            return `<span style="font-weight:600">${value}</span>`;
        }

        return value;
    },

    onload: function(report) {

        report.page.add_inner_button(__("Expand All"), function() {
            report.datatable.rowmanager.expandAllNodes();
        });

            report.page.add_inner_button(__("Collapse All"), function() {

            report.datatable.rowmanager.collapseAllNodes();

            report.refresh();
        });

        frappe.call({
            method: "erpnext.accounts.utils.get_fiscal_year",
            args: {
                date: frappe.datetime.get_today(),
                company: frappe.defaults.get_user_default("Company")
            },
            callback: function(r) {

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
        }
    ]
};