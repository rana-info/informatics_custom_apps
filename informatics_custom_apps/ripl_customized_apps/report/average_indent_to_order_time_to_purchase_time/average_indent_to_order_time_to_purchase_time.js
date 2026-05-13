// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["Average Indent To Order Time To Purchase Time"] = {
    "filters": [
        {
            fieldname: "company",
            label: "Company",
            fieldtype: "Link",
			reqd:1,
            options: "Company"
        },
        {
            fieldname: "branch",
            label: "Plant",
            fieldtype: "MultiSelectList",
            get_data: function(txt) {
                return frappe.db.get_link_options("Branch", txt);
            }
        }
    ]
};