// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["Items Stock Summary Report"] = {
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
            "fieldname": "plant",
            "label": __("Plant"),
            "fieldtype": "MultiSelectList",
            "get_data": function(txt) {
                let companies = frappe.query_report.get_filter_value("company");
                return frappe.db.get_link_options("Branch", txt, {
                    company: ["in", companies || []]
                });
            }
        },
        {
            "fieldname": "segment",
            "label": __("Segment"),
            "fieldtype": "MultiSelectList",
            "get_data": function(txt) {
                return frappe.db.get_link_options("Segment", txt);
            }
        }
    ]
};