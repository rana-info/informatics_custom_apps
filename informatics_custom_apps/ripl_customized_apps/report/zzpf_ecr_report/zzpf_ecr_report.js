// Copyright (c) 2025, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["zzPF ECR Report"] = {
    "filters": [
        {
            "fieldname": "branch",
            "label": __("Branch"),
            "fieldtype": "Link",
            "options": "Branch",
            "reqd": 1
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "reqd": 1
        },
    ],
    onload: function(report) {
        let btn = report.page.add_inner_button(__("Download ECR File"), () => {
            download_text();
        });
        $(btn).attr("title", "Download PF ECR File directly from here");
    },
    // Auto refresh when filters change
    onchange: function(report) {
        report.refresh();
    }
};
