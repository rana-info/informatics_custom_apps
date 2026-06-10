frappe.query_reports["ECC Budget Report"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "MultiSelectList",
            get_data: function(txt) { return frappe.db.get_link_options("Company", txt); }
        },
        {
            fieldname: "fiscal_year",
            label: __("Fiscal Year"),
            fieldtype: "Link",
            options: "Fiscal Year",
            on_change: function(report) {
                let fy = report.get_filter_value("fiscal_year");
                if (!fy) return;
                frappe.db.get_doc("Fiscal Year", fy).then(doc => {
                    report.set_filter_value("from_date", doc.year_start_date);
                    report.set_filter_value("to_date", frappe.datetime.get_today());
                });
            }
        },
        { fieldname: "from_date", label: __("From Date"), fieldtype: "Date" },
        { fieldname: "to_date", label: __("To Date"), fieldtype: "Date" },
        {
            fieldname: "branch",
            label: __("Plant"),
            fieldtype: "MultiSelectList",
            get_data: function(txt) { return frappe.db.get_link_options("Branch", txt); }
        },
        {
            fieldname: "segment",
            label: __("Segment"),
            fieldtype: "MultiSelectList",
            get_data: function(txt) { return frappe.db.get_link_options("Segment", txt); }
        },
        {
            fieldname: "exclude_small_budget",
            label: __("Exclude Budget Amount < 2"),
            fieldtype: "Check",
            default: 1
        }
    ],
    onload: function(report) {
        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Fiscal Year",
                fields: ["name", "year_start_date", "year_end_date"],
                limit_page_length: 100
            },
            callback: function(r) {
                let today = frappe.datetime.get_today();
                (r.message || []).forEach(function(fy) {
                    if (today >= fy.year_start_date && today <= fy.year_end_date) {
                        report.set_filter_value("fiscal_year", fy.name);
                        report.set_filter_value("from_date", fy.year_start_date);
                        report.set_filter_value("to_date", today);
                    }
                });
            }
        });
    }
};