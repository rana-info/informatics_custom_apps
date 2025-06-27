// Copyright (c) 2025, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["GL Report"] = {
    "filters": [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            reqd: 1
        },
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            reqd: 1
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            reqd: 1
        },
        {
            fieldname: "account",
            label: __("Account"),
            fieldtype: "Link",
            options: "Account"
        }
        // ,{
        //     fieldname: "group_by_voucher",
        //     label: __("Group by Voucher"),
        //     fieldtype: "Check"
        // }
    ]
};
