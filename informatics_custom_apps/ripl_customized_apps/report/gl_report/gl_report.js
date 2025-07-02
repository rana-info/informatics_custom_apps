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
            options: "Account",
            get_query: function (report) {
                let company = frappe.query_report.get_filter_value('company');
                if (company) {
                    return {
                        filters: {
                            company: company
                        }
                    };
                }
            }
        }
    ]
};
