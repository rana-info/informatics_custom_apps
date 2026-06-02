frappe.query_reports["Asset Repair Analysis - MGT"] = {
    tree: true,
    name_field: "tree_label",
    parent_field: "parent_asset",
    initial_depth: 0,

    onload: function(report) {

        report.page.add_inner_button(__("Expand All"), function() {
            report.datatable.rowmanager.expandAllNodes();
        });

        report.page.add_inner_button(__("Collapse All"), function() {
            report.datatable.rowmanager.collapseAllNodes();
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
            fieldname: "company",
            label: "Company",
            fieldtype: "MultiSelectList",
            get_data: function(txt) {
                return frappe.db.get_link_options("Company", txt);
            }
        },
        {
            fieldname: "branch",
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
            label: "From Date",
            fieldtype: "Date",
            reqd: 1
        },
        {
            fieldname: "to_date",
            label: "To Date",
            fieldtype: "Date",
            reqd: 1
        }
    ]
};