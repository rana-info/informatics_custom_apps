// Copyright (c) 2025, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["Department Wise Attendance"] = {
    filters: [
        {
            fieldname: "plant",
            label: __("Plant"),
            fieldtype: "Link",
            options: "Branch",
            reqd: 1
        },
        {
            fieldname: "date",
            label: __("Date"),
            fieldtype: "Date",
            reqd: 1
        }
    ],

    formatter: function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (column.fieldname === "department" && data && data.department) {
            const department = encodeURIComponent(data.department);
            const plant = encodeURIComponent(frappe.query_report.get_filter_value("plant"));
            const date = encodeURIComponent(frappe.query_report.get_filter_value("date"));

            
			const route = `/app/attendance?attendance_date=${date}&plant=${plant}&department=${department}`;

            return `<a href="${route}" target="_blank">${value}</a>`;
        }

        return value;
    }
};
