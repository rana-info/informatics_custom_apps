// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["Item Ordered And Purchased But Not Issued"] = {
    filters: [

        {
            fieldname: "company",
            label: "Company",
            fieldtype: "Link",
            options: "Company"
        },

        {
            fieldname: "branch",
            label: "Branch",
            fieldtype: "MultiSelectList",

            get_data: function(txt) {
                return frappe.db.get_link_options(
                    "Branch",
                    txt
                );
            }
        },

        {
            fieldname: "item_group",
            label: "Item Group",
            fieldtype: "Link",
            options: "Item Group"
        },

        {
            fieldname: "months_range",
            label: "Months",
            fieldtype: "Select",

            options: "\n1-3\n3-6\n6-9\n9-12\n12 Above"
        }
    ]
};