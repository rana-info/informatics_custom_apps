// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["GL Item"] = {
	 "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "MultiSelectList",
            "options": "Company",
            "reqd": 1,
            "get_data": function(txt) {
                return frappe.db.get_link_options("Company", txt);
            },
            on_change: function() {
                frappe.query_report.set_filter_value("account", []);
                frappe.query_report.set_filter_value("plant", []);
                frappe.query_report.set_filter_value("segment", []);
            }
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname": "account",
            "label": __("GL Account"),
            "fieldtype": "MultiSelectList",
            "get_data": function(txt) {
                let companies = frappe.query_report.get_filter_value("company");
                return frappe.db.get_link_options("Account", txt, {
                    company: ["in", companies || []]
                });
            }
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
