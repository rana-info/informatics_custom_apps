// Copyright (c) 2025, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["RGP Balance"] = {
	"filters": [
       {
            fieldname: "plant",
            label: __("Plant"),
            fieldtype: "Link",
            options: "Branch",
            reqd: 1
        },
		{
            fieldname: "se",
            label: __("Stock Entry"),
            fieldtype: "Link",
            options: "Stock Entry",
            reqd: 1,
			get_query: function (report) {
                let plant = frappe.query_report.get_filter_value('plant');
                if (plant) {
                    return {
                        filters: {
                            Branch: plant,
                            stock_entry_type: "Send to Subcontractor"
                        }
                    };
                }
            }
        }

	]
};
