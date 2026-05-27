// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["GL Item Asset"] = {
	
    filters: [

        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            reqd: 1,
            default: frappe.defaults.get_user_default("Company")
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
            default: frappe.datetime.get_today()
        },

        {
            fieldname: "account",
            label: __("Account"),
            fieldtype: "Link",
            options: "Account"
        },

        {
            fieldname: "plant",
            label: __("Plant"),
            fieldtype: "Link",
            options: "Branch"
        },

        {
            fieldname: "segment",
            label: __("Segment"),
            fieldtype: "Link",
            options: "Segment"
        }

    ]

};