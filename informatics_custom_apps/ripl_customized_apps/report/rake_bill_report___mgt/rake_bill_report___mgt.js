// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt
$(document).on("page-change", function() {
    $(".mt-report-note").remove();
});

frappe.query_reports["Rake Bill Report - MGT"] = {

    filters: [

        {
            fieldname: "company",
            label: "Company",
            fieldtype: "MultiSelectList",
            get_data: function (txt) {
                return frappe.db.get_link_options("Company", txt);
            }
        },

        {
            fieldname: "branch",
            label: "Plant",
            fieldtype: "MultiSelectList",
            get_data: async function (txt) {

                let companies = frappe.query_report.get_filter_value("company") || [];
                let filters = {};

                if (companies.length) {
                    filters.company = ["in", companies];
                }

                return frappe.db.get_link_options("Branch", txt, filters);
            }
        },

        {
            fieldname: "segment",
            label: "Segment",
            fieldtype: "MultiSelectList",
            get_data: function (txt) {
                return frappe.db.get_link_options("Segment", txt);
            }
        },

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
            fieldname: "show_detail",
            label: "Show Detailed Report",
            fieldtype: "Check",
            default: 0
        }
    ],

onload: function(report) {

        $(".mt-report-note").remove();

        const note = $(`
            <div class="mt-report-note"
                style="
                    background:#dbeafe;
                    border:1px solid #93c5fd;
                    border-left:5px solid #2563eb;
                    border-radius:6px;
                    padding:12px 16px;
                    margin-bottom:12px;
                    color:#000;
                    font-size:13px;
                    line-height:1.6;">
                <div style="font-weight:700;font-size:14px;">
                    Quantity Conversion Reference
                </div>
                <div>
                    All quantities in this report are displayed in <b>Metric Tons (MT)</b>.
                </div>
                <div>
                    <b>1 MT = 10 Quintals = 1,000 KGS</b>
                </div>
            </div>
        `);

        report.page.main.prepend(note);

        frappe.call({
            method: "erpnext.accounts.utils.get_fiscal_year",
            args: {
                date: frappe.datetime.get_today(),
                company: frappe.defaults.get_user_default("Company")
            },
            callback: function(r) {

                if (!r.message) return;

                if (!frappe.query_report.get_filter_value("from_date")) {
                    frappe.query_report.set_filter_value("from_date", r.message[1]);
                }

                if (!frappe.query_report.get_filter_value("to_date")) {
                    frappe.query_report.set_filter_value("to_date", frappe.datetime.get_today());
                }
            }
        });
    }
}