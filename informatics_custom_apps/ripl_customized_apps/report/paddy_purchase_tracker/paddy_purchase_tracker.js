frappe.query_reports["Paddy Purchase Tracker"] = {
	filters: [
		{
			fieldname: "from_date",
			label: "From Date",
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: "To Date",
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "warehouse",
			label: "Warehouse",
			fieldtype: "Link",
			options: "Warehouse",
		},
		{
			fieldname: "supplier",
			label: "Supplier",
			fieldtype: "Link",
			options: "Supplier",
		},
		{
			fieldname: "purchase_order",
			label: "Purchase Order",
			fieldtype: "Link",
			options: "Purchase Order",
			hidden: 1,
		},
		{
			fieldname: "drill_type",
			label: "Drill Type",
			fieldtype: "Select",
			options: "\nsupplier\npo\nitem",
			hidden: 1,
		},
	],

	onload: function (report) {
		report.page.add_inner_button(__("⟲ Back to Summary"), function () {
			frappe.query_reports["Paddy Purchase Tracker"].reset_to_summary();
		});
	},

	_set_filters_silently: function (values) {
		const report = frappe.query_report;
		if (!report || !report.filters) return;

		Object.keys(values).forEach((fieldname) => {
			const filter = report.get_filter(fieldname);
			if (!filter) return;
			filter.set_value(values[fieldname], false);
		});

		report.datatable = null;

		report.refresh();
	},

	drill_to_supplier: function (warehouse) {
		this._set_filters_silently({
			supplier: "",
			purchase_order: "",
			drill_type: "supplier",
			warehouse: warehouse,
		});
	},

	drill_to_po: function (supplier) {
		this._set_filters_silently({
			purchase_order: "",
			drill_type: "po",
			supplier: supplier,
		});
	},

	drill_to_item: function (purchase_order) {
		this._set_filters_silently({
			drill_type: "item",
			purchase_order: purchase_order,
		});
	},

	reset_to_summary: function () {
		this._set_filters_silently({
			warehouse: "",
			supplier: "",
			purchase_order: "",
			drill_type: "",
		});
	},

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (
			column.fieldname === "item_name" &&
			data.item_name &&
			data.item_name.includes("UOM factor missing")
		) {
			value = `<span style="color:red;font-weight:600">${value}</span>`;
		}

		let pct = flt(data.pct_received);
		let color = "#d9363e";
		if (pct >= 100) {
			color = "#2e8b57";
		} else if (pct > 0) {
			color = "#e08e0b";
		}

		if (column.fieldname === "warehouse" && data.row_type === "warehouse") {
			let arg = encodeURIComponent(data.warehouse);
			value = `<a href="#" onclick="frappe.query_reports['Paddy Purchase Tracker'].drill_to_supplier(decodeURIComponent('${arg}')); return false;" style="color:${color};font-weight:500">${value}</a>`;
		}

		if (column.fieldname === "supplier_name" && data.row_type === "supplier") {
			let arg = encodeURIComponent(data.supplier);
			value = `<a href="#" onclick="frappe.query_reports['Paddy Purchase Tracker'].drill_to_po(decodeURIComponent('${arg}')); return false;" style="color:${color};font-weight:500">${value}</a>`;
		}

		if (column.fieldname === "purchase_order" && data.row_type === "po") {
			let arg = encodeURIComponent(data.purchase_order);
			value = `<a href="#" onclick="frappe.query_reports['Paddy Purchase Tracker'].drill_to_item(decodeURIComponent('${arg}')); return false;" style="color:${color};font-weight:500">${value}</a>`;
		}

		return value;
	},
};