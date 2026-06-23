frappe.query_reports["zzRetaining Salary PF ECR Report"] = {
    filters: [
        {
            fieldname: "branch",
            label: __("Branch"),
            fieldtype: "Link",
            options: "Branch",
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
    ],
    onload: function (report) {
        let btn = report.page.add_inner_button(__("Download ECR File"), function () {
            download_text();
        });
        $(btn).attr("title", "Download Retaining Salary PF ECR File");
    }
};

function download_text() {
    let filters = frappe.query_report.get_filter_values();
    console.log("Filters applied:", filters); // Debugging

    frappe.call({
        method: "frappe.desk.query_report.run",
        args: {
            report_name: "zzRetaining Salary PF ECR Report",
            filters: filters
        },
        callback: function (r) {
            if (r.message && r.message.result) {
                let data = r.message.result;
                console.log("Data received from server:", data); // Debugging: Check data returned

                if (Array.isArray(data) && data.length > 0) {
                    let text = convert_to_text(data);  // Convert entire data to text
                    let from_date = new Date(filters.from_date);
                    let to_date = new Date(filters.to_date);
                    let filename = 'Retaining-PF-ECR-' + get_month_name(from_date) + '-' + get_month_name(to_date) + '.txt';
                    download_file(text, filename);
                } else {
                    console.error("Received data is empty or not an array.");
                }
            }
        }
    });
}

function convert_to_text(data) {
    console.log("Data being processed in convert_to_text:", data);  // Debugging

    return data.map(row => {
        console.log("Processing row:", row);  // Debug each row processed
        return [
            row.provident_fund_account || "0",
            row.employee_name || "0",
            row.gross_pay || "0",
            row.pf_salary || "0",
            row.pension_salary || "0",
            row.edli || "0",
            row.pf_12_per || "0",
            row.employee_pension_amount || "0",
            row.employee_pf || "0",
            row.payment_absent_days || "0",
            "0"
        ].join("#~#");
    }).join("\n");
}

function download_file(content, filename) {
    let blob = new Blob([content], { type: 'text/plain;charset=utf-8;' });
    if (navigator.msSaveBlob) {
        navigator.msSaveBlob(blob, filename);
    } else {
        let link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
}

function get_month_name(date) {
    return [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ][date.getMonth()];
}
