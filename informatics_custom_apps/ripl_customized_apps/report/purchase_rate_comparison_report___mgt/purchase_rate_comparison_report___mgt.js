$(document).on("page-change", function() {
    $(".price-legend").remove();
});
frappe.query_reports["Purchase Rate Comparison Report - MGT"] = {

  onload: function(report) {

    $(".price-legend").remove();

    const legend = $(`
        <div class="price-legend"
            style="
                padding:10px 15px;
                margin-bottom:10px;
                border:1px solid #ddd;
                border-radius:6px;
                background:#fafafa;
                font-size:13px;
            ">
            <b>Price Variation Legend:</b>
            &nbsp;&nbsp;
            <span style="color:#1e88e5;font-weight:bold;">● > 5% (Low)</span>
            &nbsp;&nbsp;
            <span style="color:#43a047;font-weight:bold;">● > 10% (Moderate)</span>
            &nbsp;&nbsp;
            <span style="color:#fb8c00;font-weight:bold;">● > 20% (High)</span>
            &nbsp;&nbsp;
            <span style="color:#e53935;font-weight:bold;">● > 40% (Critical)</span>
        </div>
    `);

    report.page.main.prepend(legend);

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
},

    refresh: function(report) {
        add_price_legend(report);
    },

    formatter: function(value, row, column, data, default_formatter) {

    value = default_formatter(value, row, column, data);

    if (
        column.fieldname === "item_display" &&
        data &&
        data.item_code
    ) {
        value = `
            <a href="/app/item/${encodeURIComponent(data.item_code)}">
                ${value}
            </a>
        `;
    }

    let pct = data?.price_variation_percent || 0;

    let bg = "";

    if (pct > 40) {
        bg = "#ffebee";
    } else if (pct > 20) {
        bg = "#fff3e0";
    } else if (pct > 10) {
        bg = "#e8f5e9";
    } else if (pct > 5) {
        bg = "#e3f2fd";
    }

    if (bg && row && row.wrapper) {
        $(row.wrapper).css("background-color", bg);
    }

    if (column.fieldname === "last_rate") {

        if (pct > 40) {
            return `<b style="color:#e53935">${value}</b>`;
        }
        if (pct > 20) {
            return `<b style="color:#fb8c00">${value}</b>`;
        }
        if (pct > 10) {
            return `<b style="color:#43a047">${value}</b>`;
        }
        if (pct > 5) {
            return `<b style="color:#1e88e5">${value}</b>`;
        }
    }

    return value;
},
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "MultiSelectList",
            get_data: function(txt) {
                return frappe.db.get_link_options("Company", txt);
            }
        },
        {
            fieldname: "branch",
            label: "Plant",
            fieldtype: "MultiSelectList",
            get_data: async function(txt) {

                let companies = frappe.query_report.get_filter_value("company") || [];
                let filters = {};

                if (companies.length) {
                    filters.company = ["in", companies];
                }

                return frappe.db.get_link_options(
                    "Branch",
                    txt,
                    filters
                );
            }
        },
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date"
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date"
        },
        {
            fieldname: "price_variation",
            label: __("Price Variation %"),
            fieldtype: "Select",
            options: [
                "",
                "> 5%",
                "> 10%",
                "> 20%",
                "> 40%"
            ].join("\n")
        }
    ]
};

function add_price_legend(report) {

    if (!report || report.report_name !== "Purchase Rate Comparison Report - MGT") {
        return;
    }

    $(".price-legend").remove();

    report.page.main.prepend(`
        <div class="price-legend" style="
            padding:10px 15px;
            margin-bottom:10px;
            border:1px solid #ddd;
            border-radius:6px;
            background:#fafafa;
            font-size:13px;
        ">
            <b>Price Variation Legend:</b>
            &nbsp;&nbsp;
            <span style="color:#1e88e5;font-weight:bold;">● > 5% (Low)</span>
            &nbsp;&nbsp;
            <span style="color:#43a047;font-weight:bold;">● > 10% (Moderate)</span>
            &nbsp;&nbsp;
            <span style="color:#fb8c00;font-weight:bold;">● > 20% (High)</span>
            &nbsp;&nbsp;
            <span style="color:#e53935;font-weight:bold;">● > 40% (Critical)</span>
        </div>
    `);
}