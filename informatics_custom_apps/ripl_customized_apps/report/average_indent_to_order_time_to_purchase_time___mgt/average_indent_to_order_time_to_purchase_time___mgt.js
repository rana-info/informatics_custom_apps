frappe.query_reports["Average Indent To Order Time To Purchase Time - MGT"] = {

    onload: function (report) {

        if (report.__bound_back_to_summary) return;
        report.__bound_back_to_summary = true;

        report.page.add_inner_button(__("Back To Summary"), async function () {

            const from_date = frappe.query_report.get_filter_value("from_date");
            const to_date = frappe.query_report.get_filter_value("to_date");

            await frappe.query_report.set_filter_value("show_detail", 0);
            await frappe.query_report.set_filter_value("branch", null);
            await frappe.query_report.set_filter_value("segment", null);
            await frappe.query_report.set_filter_value("drill_metric", null);
            await frappe.query_report.set_filter_value("report_view", "Summary");

            await frappe.query_report.set_filter_value("from_date", from_date);
            await frappe.query_report.set_filter_value("to_date", to_date);

            frappe.query_report.refresh();
        });

        frappe.call({
            method: "erpnext.accounts.utils.get_fiscal_year",
            args: {
                date: frappe.datetime.get_today(),
                company: frappe.defaults.get_user_default("Company")
            },
            callback: function (r) {

                if (!r.message) return;

                if (!frappe.query_report.get_filter_value("from_date")) {
                    frappe.query_report.set_filter_value("from_date", r.message[1]);
                }

                if (!frappe.query_report.get_filter_value("to_date")) {
                    frappe.query_report.set_filter_value("to_date", frappe.datetime.get_today());
                }
            }
        });
    },

    formatter: function (value, row, column, data, default_formatter) {

        value = default_formatter(value, row, column, data);

        const drill_columns = [
            "buyer_delay",
            "supplier_delay",
            "total_procurement_days",
            "delivery_delay"
        ];

        if (data && data.is_summary && drill_columns.includes(column.fieldname)) {

            value = `<a href="javascript:void(0)"
                onclick="show_procurement_detail(
                    '${data.branch || ""}',
                    '${data.segment || ""}',
                    '${column.fieldname}'
                ); return false;">
                ${value}
            </a>`;
        }

        return value;
    },

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
            fieldtype: "Link",
            options: "Branch",
            hidden: 1
        },

        {
            fieldname: "from_date",
            label: "From Date",
            fieldtype: "Date",
            reqd: 1
        },

        {
            fieldname: "to_date",
            label: "To Date",
            fieldtype: "Date",
            reqd: 1
        },

        {
            fieldname: "segment",
            label: "Segment",
            fieldtype: "Data",
            hidden: 1
        },

        {
            fieldname: "drill_metric",
            label: "Drill Metric",
            fieldtype: "Data",
            hidden: 1
        },

        {
            fieldname: "show_detail",
            label: "Show Detail",
            fieldtype: "Check",
            default: 0,
            hidden: 1
        },

     {
			fieldname: "report_view",
			label: "Report View",
			fieldtype: "Select",
			options: "Summary\nDetail",
			default: "Summary",

			on_change: function () {

				const view = frappe.query_report.get_filter_value("report_view");

				if (view === "Summary") {

					frappe.query_report.set_filter_value("show_detail", 0);
					frappe.query_report.set_filter_value("branch", null);
					frappe.query_report.set_filter_value("segment", null);
					frappe.query_report.set_filter_value("drill_metric", null);

					frappe.query_report.refresh();
				}

				if (view === "Detail") {

					frappe.query_report.set_filter_value("show_detail", 1);

					frappe.query_report.refresh();
				}
			}
		}
    ]
};

window.show_procurement_detail = async function (branch, segment, metric) {

    const from_date = frappe.query_report.get_filter_value("from_date");
    const to_date = frappe.query_report.get_filter_value("to_date");

    await frappe.query_report.set_filter_value("branch", branch);
    await frappe.query_report.set_filter_value("segment", segment);
    await frappe.query_report.set_filter_value("drill_metric", metric);
    await frappe.query_report.set_filter_value("show_detail", 1);
    await frappe.query_report.set_filter_value("report_view", "Detail");

    await frappe.query_report.set_filter_value("from_date", from_date);
    await frappe.query_report.set_filter_value("to_date", to_date);

    frappe.query_report.refresh();
};