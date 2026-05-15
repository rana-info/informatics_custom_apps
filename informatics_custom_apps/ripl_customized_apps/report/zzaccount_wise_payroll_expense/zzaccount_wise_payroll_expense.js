// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["zzAccount Wise Payroll Expense"] = {
  filters: [
    {
      fieldname: "company",
      label: "Company",
      fieldtype: "Link",
      options: "Company",
      reqd: 1,
    },

    {
      fieldname: "branch",
      label: "Plant",
      fieldtype: "Link",
      options: "Branch",
      reqd: 1,

      get_query: function () {
        let company = frappe.query_report.get_filter_value("company");

        return {
          filters: {
            company: company,
          },
        };
      },
    },

    {
      fieldname: "from_date",
      label: "From Date",
      fieldtype: "Date",
      reqd: 1,
      default: "2025-04-01",
    },

    {
      fieldname: "to_date",
      label: "To Date",
      fieldtype: "Date",
      reqd: 1,
      default: "2026-03-31",
    },
  ],
};
