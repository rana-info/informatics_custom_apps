// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["SRV Clearing Analysis"] = {
	 filters: [

        {
            fieldname: "from_date",
            label: "From Date",
            fieldtype: "Date",
            reqd: 1,
            default: get_fy_start()
        },
        {
            fieldname: "to_date",
            label: "To Date",
            fieldtype: "Date",
            reqd: 1,
            default: get_fy_end()
        },
        {
            fieldname: "company",
            label: "Company",
            fieldtype: "Link",
            options: "Company",
            default: frappe.defaults.get_user_default("Company"),
            reqd: 1
        },
        {
            fieldname: "account",
            label: "Account",
            fieldtype: "Link",
            reqd: 1,
            options: "Account",
            get_query: function () {
                return {
                    filters: {
                        company: frappe.query_report.get_filter_value("company")
                    }
                };
            }
        },
        {
            fieldname: "supplier",
            label: "Supplier",
            fieldtype: "Link",
            options: "Supplier"
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

    ],
};


// ---------------------------------------------------
// FY helpers (April - March)
// ---------------------------------------------------
function get_fy_start() {
    const today = frappe.datetime.str_to_obj(frappe.datetime.get_today());
    const year = today.getMonth() >= 3 ? today.getFullYear() : today.getFullYear() - 1;
    return `${year}-04-01`;
}

function get_fy_end() {
    const today = frappe.datetime.str_to_obj(frappe.datetime.get_today());
    const year = today.getMonth() >= 3 ? today.getFullYear() + 1 : today.getFullYear();
    return `${year}-03-31`;
}