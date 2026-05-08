// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["GL Item Asset"] = {
	 filters: [

        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "MultiSelectList",
            reqd: 1,

            get_data: function(txt) {
                return frappe.db.get_link_options("Company", txt);
            }
        },

        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: frappe.datetime.month_start()
        },

        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            default: frappe.datetime.month_end()
        },

        {
            fieldname: "account",
            label: __("Account"),
            fieldtype: "MultiSelectList",

            get_data: function(txt) {
                return frappe.db.get_link_options("Account", txt);
            }
        },

        {
            fieldname: "plant",
            label: __("Plant"),
            fieldtype: "MultiSelectList",

            get_data: function(txt) {
                return frappe.db.get_link_options("Branch", txt);
            }
        },

        {
            fieldname: "segment",
            label: __("Segment"),
            fieldtype: "MultiSelectList",

            get_data: function(txt) {
                return frappe.db.get_link_options("Segment", txt);
            }
        }

    ]
};