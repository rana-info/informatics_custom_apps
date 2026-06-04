// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["Advance Given Item Not Received - MGT"] = {
	onload: function(report) {

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
                    frappe.query_report.set_filter_value(
                        "to_date",
                        frappe.datetime.get_today()
                    );
                }
            }
        });
    },
formatter: function(value, row, column, data, default_formatter) {

    // Hide percentage columns in TOTAL row
    if (
        data &&
        (data.purchase_order === "TOTAL" || data.group_by === "TOTAL") &&
        ["material_received_percent", "advance_paid_percent"].includes(column.fieldname)
    ) {
        return "";
    }

    value = default_formatter(value, row, column, data);

    if (
        data &&
        (data.purchase_order === "TOTAL" || data.group_by === "TOTAL") &&
        !["material_received_percent", "advance_paid_percent"].includes(column.fieldname)
    ) {
        value = `<span style="font-weight:700">${value}</span>`;
    }

    return value;
},

    filters: [

        {
            fieldname: "company",
            label: __("Company"),
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
            reqd: 1,
        },

        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            reqd: 1,
        },

		{
			fieldname: "view_by",
			label: __("View By"),
			fieldtype: "Select",
			options: "\nStatus Wise\nSupplier Wise\nPlant Wise\nPO Wise",
			default: "Status Wise",
			reqd: 1
		}
    ]
};