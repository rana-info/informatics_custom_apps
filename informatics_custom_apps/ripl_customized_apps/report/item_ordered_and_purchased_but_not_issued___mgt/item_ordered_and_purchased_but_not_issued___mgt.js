frappe.query_reports["Item Ordered And Purchased But Not Issued - MGT"] = {
    formatter: function (value, row, column, data, default_formatter) {

        value = default_formatter(value, row, column, data);

        if (data && data.item_code === "TOTAL") {
            return `<b>${value}</b>`;
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
            fieldname: "item_group",
            label: "Item Group",
            fieldtype: "MultiSelectList",
            get_data: function (txt) {
                return frappe.db.get_link_options("Item Group", txt);
            }
        },

        {
            fieldname: "age_buckets",
            label: __("Age Buckets"),
            fieldtype: "Data",
            default: "30,90,180,365"
        },

        {
            fieldname: "value_filter",
            label: __("Value Filter"),
            fieldtype: "Select",
            options: [
                "",
                "> 50000",
                "> 100000"
            ].join("\n"),
            default: "> 100000"
        }
    ]
};