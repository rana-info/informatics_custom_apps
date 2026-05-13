// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["Fuel and RM (444,446,448) Quality Rejection Report"] = {
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
            get_data: function(txt) {
                return frappe.db.get_list("Warehouse", {
                    fields: ["custom_branch"],
                    filters: {
                        custom_branch: ["like", `%${txt}%`]
                    },
                    distinct: 1,
                    limit: 20
                }).then(r => {
                    return r.map(d => ({
                        value: d.custom_branch,
                        description: d.custom_branch
                    }));
                });
            }
        }
    ]
};
