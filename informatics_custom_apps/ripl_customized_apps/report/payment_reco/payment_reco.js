// Copyright (c) 2024, Your Company and contributors
// Payment Reconciliation Report — mirrors Payment Reconciliation form filters exactly

frappe.query_reports["Payment Reco"] = {

	filters: [
		// ── Row 1 ──────────────────────────────────────────────────────────────
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
			on_change: function () {
				frappe.query_report.set_filter_value("receivable_payable_account", "");
				frappe.query_report.set_filter_value("default_advance_account", "");
			},
		},
		{
			fieldname: "party_type",
			label: __("Party Type"),
			fieldtype: "Select",
			options: "Customer\nSupplier\nEmployee\nShareHolder",
			default: "Supplier",
			reqd: 1,
			on_change: function () {
				frappe.query_report.set_filter_value("party", "");
				frappe.query_report.set_filter_value("receivable_payable_account", "");
				frappe.query_report.set_filter_value("default_advance_account", "");

				// update party Link doctype
				let party_type = frappe.query_report.get_filter_value("party_type");
				frappe.query_report.filters.forEach((f) => {
					if (f.fieldname === "party") {
						f.df.options = party_type;
						f.refresh();
					}
				});
			},
		},
		{
			fieldname: "party",
			label: __("Party"),
			fieldtype: "Link",
			options: "Supplier",
			get_query: function () {
				return { doctype: frappe.query_report.get_filter_value("party_type") };
			},
		},
		{
			fieldname: "receivable_payable_account",
			label: __("Receivable / Payable Account"),
			fieldtype: "Link",
			options: "Account",
			get_query: function () {
				let company    = frappe.query_report.get_filter_value("company");
				let party_type = frappe.query_report.get_filter_value("party_type");
				let account_type =
					["Customer", "Employee", "ShareHolder"].includes(party_type)
						? "Receivable"
						: "Payable";
				return {
					filters: { company, account_type, is_group: 0 },
				};
			},
		},
		{
			fieldname: "default_advance_account",
			label: __("Default Advance Account"),
			fieldtype: "Link",
			options: "Account",
			get_query: function () {
				return {
					filters: {
						company : frappe.query_report.get_filter_value("company"),
						is_group: 0,
					},
				};
			},
		},

		// ── Row 2 — Invoice date range ─────────────────────────────────────────
		{
			fieldname: "from_invoice_date",
			label: __("From Invoice Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -6),
		},
		{
			fieldname: "to_invoice_date",
			label: __("To Invoice Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},

		// ── Row 3 — Payment date range ─────────────────────────────────────────
		{
			fieldname: "from_payment_date",
			label: __("From Payment Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -6),
		},
		{
			fieldname: "to_payment_date",
			label: __("To Payment Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},

		// ── Row 4 — Amount ranges ──────────────────────────────────────────────
		{
			fieldname: "minimum_invoice_amount",
			label: __("Minimum Invoice Amount"),
			fieldtype: "Currency",
		},
		{
			fieldname: "maximum_invoice_amount",
			label: __("Maximum Invoice Amount"),
			fieldtype: "Currency",
		},
		{
			fieldname: "minimum_payment_amount",
			label: __("Minimum Payment Amount"),
			fieldtype: "Currency",
		},
		{
			fieldname: "maximum_payment_amount",
			label: __("Maximum Payment Amount"),
			fieldtype: "Currency",
		},

		// ── Row 5 — Misc ───────────────────────────────────────────────────────
		{
			fieldname: "branch",
			label: __("Branch"),
			fieldtype: "Link",
			options: "Branch",
		},
		{
			fieldname: "cost_center",
			label: __("Cost Center"),
			fieldtype: "Link",
			options: "Cost Center",
			get_query: function () {
				return {
					filters: {
						company : frappe.query_report.get_filter_value("company"),
						is_group: 0,
					},
				};
			},
		},
		{
			fieldname: "invoice_name",
			label: __("Invoice No"),
			fieldtype: "Data",
		},
		{
			fieldname: "payment_name",
			label: __("Payment / Reference No"),
			fieldtype: "Data",
		},
		{
			fieldname: "reconciliation_status",
			label: __("Reconciliation Status"),
			fieldtype: "MultiSelectList",
			get_data: function(txt) {
				let options = ["Unreconciled", "Partially Reconciled", "Fully Reconciled"];
				return options.filter(o => o.toLowerCase().includes(txt.toLowerCase()));
			}
		},
	],

	// ── Row formatter ────────────────────────────────────────────────────────

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (!data) return value;

		// Section badge
		if (column.fieldname === "section") {
			if (data.section === __("Invoice")) {
				value = `<span class="indicator-pill blue">${__("Invoice")}</span>`;
			} else if (data.section === __("Payment")) {
				value = `<span class="indicator-pill purple">${__("Payment")}</span>`;
			}
		}

		// Status badge
		if (column.fieldname === "reconciliation_status") {
			const color_map = {
				[__("Unreconciled")]        : "red",
				[__("Partially Reconciled")]: "orange",
				[__("Fully Reconciled")]    : "green",
			};
			const color = color_map[data.reconciliation_status];
			if (color) {
				value = `<span class="indicator-pill ${color}">${data.reconciliation_status}</span>`;
			}
		}

		// Highlight outstanding amount in red when > 0
		if (column.fieldname === "outstanding_amount") {
			const amt = parseFloat(data.outstanding_amount) || 0;
			if (amt > 0) {
				value = `<strong style="color:var(--red-600)">${value}</strong>`;
			}
		}

		return value;
	},

	onload: function (report) {
		// Sync party field doctype on initial load
		let party_type = frappe.query_report.get_filter_value("party_type");
		if (party_type) {
			report.filters.forEach((f) => {
				if (f.fieldname === "party") {
					f.df.options = party_type;
					f.refresh();
				}
			});
		}
	},
};
