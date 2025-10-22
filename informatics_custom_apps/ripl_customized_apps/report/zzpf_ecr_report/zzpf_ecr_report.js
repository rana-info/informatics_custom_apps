// Copyright (c) 2024, Dexciss Technology Pvt Ltd and contributors
// For license information, please see license.txt

frappe.query_reports["zzPF ECR Report"] = {
    "filters": [
        {
            "fieldname":"branch",
            "label": __("Branch"),
            "fieldtype":"Link",
            "options":"Branch",
            "reqd":1
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "reqd":1
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "reqd":1
        },
    ],
    onload: function(report) {
		let csv_button = report.page.add_inner_button(__("Download ECR File"), function() {
            download_text();
        });
		$(csv_button).attr("title", "Download PF ECR File directly from hear");
		// report.page.add_inner_button(__("Download as CSV"), function() {
        //     download_csv();
        // });
    },
    onchange: function(report) {
        report.refresh();
    },
};

function download_text() {
    var filters = frappe.query_report.get_filter_values();

    frappe.call({
        method: "frappe.desk.query_report.run",
        args: {
            report_name: "zzPF ECR Report",
            filters: filters
        },
        callback: function(r) {
            if (r.message && r.message.result) {
                var data = r.message.result;
                var text = convert_to_text(data);
                var from_date = new Date(filters.from_date);
                var to_date = new Date(filters.to_date);
                var branch_name = filters.branch 
                var filename = 'PF ECR ' + branch_name + get_month_name(from_date) + '-' + get_month_name(to_date) + '.txt';
                download_file(text, filename);
            }
        }
    });
}

function convert_to_text(data) {
    var text_lines = [];
    
    data.forEach(function(row) {
        var line = [
            row.provident_fund_account || "0",
            row.employee_name || "0",
            row.gross_pay || "0",
            row.pf_salary || "0",
            row.pension_salary || "0",
			row.edli || "0",
            row.pf_12_per || "0",
            row.employee_pension_amount || "0",
            row.employee_pf || "0",
            row.payment_absent_days || "0"
        ].map(function(value) {
            return value !== null ? value : "0";
        }).join("#~#");

        line += "#~#0";
        text_lines.push(line);
    });
    download_text
    return text_lines.join("\n");
}

function download_file(content, filename) {
    var blob = new Blob([content], { type: 'text/plain;charset=utf-8;' });
    if (navigator.msSaveBlob) {
        navigator.msSaveBlob(blob, filename);
    } else {
        var link = document.createElement("a");
        if (link.download !== undefined) {
            var url = URL.createObjectURL(blob);
            link.setAttribute("href", url);
            link.setAttribute("download", filename);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    }
}

function get_month_name(date) {
    const monthNames = [
        "January", "February", "March",
        "April", "May", "June",
        "July", "August", "September",
        "October", "November", "December"
    ];
    return monthNames[date.getMonth()];
}

// function download_csv() {
//     var filters = frappe.query_report.get_filter_values();

//     frappe.call({
//         method: "frappe.desk.query_report.run",
//         args: {
//             report_name: "PF ECR Report",
//             filters: filters
//         },
//         callback: function(r) {
//             if (r.message && r.message.result) {
//                 var data = r.message.result;
//                 var csv = convert_to_csv(data);
//                 var filename = 'PF_ECR_Report.csv';
//                 download_file(csv, filename);
//             }
//         }
//     });
// }

// function convert_to_csv(data) {
//     var csv = [];
//     var headers = Object.keys(data[0]);
//     csv.push(headers.join(","));
    
//     data.forEach(function(row) {
//         var values = headers.map(function(header) {
//             return row[header] !== null ? row[header] : "";
//         });
//         csv.push(values.join(","));
//     });
    
//     return csv.join("\n");
// }

// function download_file(content, filename) {
//     var blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
//     if (navigator.msSaveBlob) {
//         navigator.msSaveBlob(blob, filename);
//     } else {
//         var link = document.createElement("a");
//         if (link.download !== undefined) {
//             var url = URL.createObjectURL(blob);
//             link.setAttribute("href", url);
//             link.setAttribute("download", filename);
//             link.style.visibility = 'hidden';
//             document.body.appendChild(link);
//             link.click();
//             document.body.removeChild(link);
//         }
//     }
// }