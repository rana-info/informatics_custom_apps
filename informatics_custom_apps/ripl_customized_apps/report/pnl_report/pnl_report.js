frappe.query_reports["PNL Report"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "branch",
			label: __("Plant / Branch"),
			fieldtype: "MultiSelectList",
			get_data: function (txt) {
				return frappe.db.get_link_options("Branch", txt);
			},
			description: __("Leave blank to include all plants."),
		},
		{
			fieldname: "view",
			label: __("View"),
			fieldtype: "Select",
			options: ["Detailed", "Summary"],
			default: "Detailed",
			reqd: 1,
			description: __(
				"Detailed shows every account under each Section with its Subtotal (Schedule sheet). Summary shows only the rolled-up Summary lines."
			),
			on_change: function () {
				frappe.query_report.refresh();
			},
		},
		{
			fieldname: "hide_zero",
			label: __("Hide Zero Rows / Columns"),
			fieldtype: "Check",
			default: 0,
			description: __("Exclude rows and plant/segment columns that are entirely zero."),
			on_change: function () {
				frappe.query_report.refresh();
			},
		},
	],

	onload: function (report) {
		const today = frappe.datetime.get_today();
		frappe.db
			.get_list("Fiscal Year", {
				filters: [
					["year_start_date", "<=", today],
					["year_end_date", ">=", today],
				],
				fields: ["year_start_date"],
				limit_page_length: 1,
			})
			.then((rows) => {
				if (rows && rows.length) {
					report.set_filter_value("from_date", rows[0].year_start_date);
					frappe.query_report.refresh();
				}
			});
	},

	formatter: function (value, row, column, data, default_formatter) {
		if (data && data.is_divider) {
			return `<div style="border-top:2px solid #000;height:1px;margin:10px -8px 0;"></div>`;
		}

		const isValueCol = column.fieldname !== "description";
		const isSectionHeader =
			data && data.indent === 0 && data.is_bold && row && row.meta && row.meta.isLeaf === false;

		if (isSectionHeader && isValueCol) {
			const isCollapsed = !!(row && row.meta && row.meta.isTreeNodeClose);
			if (!isCollapsed) return "";
		}

		value = default_formatter(value, row, column, data);
		if (data && (data.is_bold || data.is_total)) {
			value = `<b>${value}</b>`;
		}
		return value;
	},

	after_datatable_render: function (datatable) {
		if (datatable.wrapper.dataset.pnlToggleBound) return;
		datatable.wrapper.dataset.pnlToggleBound = "1";

		const valueColIndexes = datatable.datamanager
			.getColumns()
			.filter((c) => c.fieldname !== "description")
			.map((c) => c.colIndex);

		datatable.wrapper.addEventListener("click", function (e) {
			const $toggle = e.target.closest(".dt-tree-node__toggle");
			if (!$toggle) return;

			const $cell = $toggle.closest(".dt-cell");
			if (!$cell) return;

			const rowIndex = parseInt($cell.dataset.rowIndex, 10);
			if (isNaN(rowIndex)) return;

			const row = datatable.datamanager.getRow(rowIndex);
			if (!row) return;

			valueColIndexes.forEach((colIndex) => {
				const cell = row[colIndex];
				if (cell) datatable.cellmanager.refreshCell(cell, true);
			});
		});
	},
};