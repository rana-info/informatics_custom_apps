// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt
frappe.query_reports["Stock Summary Report"] = {
     filters: [
       {
            fieldname: "to_date",
            label: "As On Date",
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.get_today()
        },
        {
            fieldname: "company",
            label: "Company",
            fieldtype: "Link",
            options: "Company"
        },
        {
            fieldname: "plant",
            label: "Plant",
            fieldtype: "Link",
            options: "Branch",

            get_query: function () {
                let company = frappe.query_report.get_filter_value("company");

                return {
                    filters: {
                        company: company
                    }
                };
            }
        },

        {
            fieldname: "segment",
            label: "Segment",
            fieldtype: "Link",
            options: "Segment"  // change if your doctype name differs
        }
    ]
};