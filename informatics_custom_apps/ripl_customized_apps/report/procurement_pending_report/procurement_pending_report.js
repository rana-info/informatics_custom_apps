frappe.query_reports["Procurement Pending Report"] = {
	filters: [
		{
			fieldname: "plant",
			label: __("Plant"),
			fieldtype: "Link",
			options: "Branch",
		},
		{
			fieldname: "segment",
			label: __("Segment"),
			fieldtype: "Data",
		},
		{
			fieldname: "cost_center",
			label: __("Cost Center"),
			fieldtype: "Link",
			options: "Cost Center",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "only_above_1lakh",
			label: __("Only Above Amount"),
			fieldtype: "Check",
			default: 1,
			description: __("Only count/show documents whose own amount exceeds the threshold set below"),
			on_change: function () {
				// The threshold field is only meaningful while this is
				// checked -- toggle it in step so it's obvious the two
				// are linked, and re-run so unchecking it immediately
				// drops the amount filter instead of waiting for the
				// person to also touch the threshold field.
				toggle_above_amount_field();
				frappe.query_report.refresh();
			},
		},
		{
			// The actual cutoff value, previously hardcoded server-side
			// as a flat 1 Lakh. Now editable here -- the python side
			// reads it straight from this filter (fieldname
			// "above_amount") on every query, so changing it and
			// re-running immediately reflects the new threshold in both
			// the summary counts and every drilldown.
			fieldname: "above_amount",
			label: __("Amount Threshold"),
			fieldtype: "Currency",
			default: 100000,
			description: __("Documents at or below this amount are excluded when 'Only Above Amount' is checked"),
		},
		{
			fieldname: "min_days_delayed",
			label: __("Minimum Days Delayed"),
			fieldtype: "Int",
			default: 10,
			description: __("Only count/show documents delayed by at least this many days"),
		},
		{
			fieldname: "drill_type",
			label: __("Drill Type"),
			fieldtype: "Data",
			hidden: 1,
		},
	],

	_drill_registry: {},
	_detail_registry: {},
	_report: null,

	// Grid fieldname that holds the per-row item name in every
	// item-exploded drilldown. Continuation rows (2nd+ item of the same
	// document) blank out every OTHER column so the grid reads as one
	// merged block per document with an item per line, instead of
	// repeating the same date/supplier/amount/etc. on every row.
	_item_column_fieldname: "item_name",

	// Fields shown inside the "basic details" popup for each drilldown's
	// document link, in display order. Pulled straight from the row data
	// already fetched for the table -- no extra server round-trip.
	// "Items" (item_list) is the full ", "-joined list for the document,
	// built server-side from the same exploded rows -- distinct from the
	// grid's per-row "item_name" column.
	// NOTE: received_pct here is fieldtype "Percent" -- that's fine and
	// intentional. This map only feeds frappe.format() inside the plain
	// dialog popup (show_detail_popup below), which is a different code
	// path from the query-report DataTable grid. The grid column itself
	// (see the .py report's get_po_pending_drilldown_columns) is deliberately
	// "Data", not "Percent" -- see the comment on the received_pct
	// formatter branch below for why.
	_detail_fields_map: {
		indent: [
			{ label: __("Date"), fieldname: "posting_date", fieldtype: "Date" },
			{ label: __("Schedule Date"), fieldname: "schedule_date", fieldtype: "Date" },
			{ label: __("Items"), fieldname: "item_list", fieldtype: "Small Text" },
			{ label: __("Amount"), fieldname: "amount", fieldtype: "Currency" },
			{ label: __("Responsible User"), fieldname: "responsible_user", fieldtype: "Data" },
			{ label: __("Days Delayed"), fieldname: "days_delayed", fieldtype: "Int" },
		],
		purchase_order: [
			{ label: __("Date"), fieldname: "posting_date", fieldtype: "Date" },
			{ label: __("Supplier"), fieldname: "supplier", fieldtype: "Link", options: "Supplier" },
			{ label: __("Items"), fieldname: "item_list", fieldtype: "Small Text" },
			{ label: __("Amount"), fieldname: "amount", fieldtype: "Currency" },
			{ label: __("Received %"), fieldname: "received_pct", fieldtype: "Percent" },
			{ label: __("Days Delayed"), fieldname: "days_delayed", fieldtype: "Int" },
			{ label: __("Responsible User"), fieldname: "responsible_user", fieldtype: "Data" },
		],
		pr: [
			{ label: __("Date"), fieldname: "posting_date", fieldtype: "Date" },
			{ label: __("Supplier"), fieldname: "supplier", fieldtype: "Link", options: "Supplier" },
			{ label: __("Items"), fieldname: "item_list", fieldtype: "Small Text" },
			{ label: __("Amount"), fieldname: "amount", fieldtype: "Currency" },
			{ label: __("Weighment Required"), fieldname: "is_weighment_required", fieldtype: "Data" },
			{ label: __("Weighment Status"), fieldname: "weighment_status", fieldtype: "Data" },
			{ label: __("Days Delayed"), fieldname: "days_delayed", fieldtype: "Int" },
			{ label: __("Responsible User"), fieldname: "responsible_user", fieldtype: "Data" },
		],
		qi: [
			{ label: __("Date"), fieldname: "posting_date", fieldtype: "Date" },
			{ label: __("Purchase Receipt"), fieldname: "purchase_receipt", fieldtype: "Link", options: "Purchase Receipt" },
			{ label: __("Supplier"), fieldname: "supplier", fieldtype: "Link", options: "Supplier" },
			{ label: __("Items"), fieldname: "item_list", fieldtype: "Small Text" },
			{ label: __("Amount"), fieldname: "amount", fieldtype: "Currency" },
			{ label: __("Responsible User"), fieldname: "responsible_user", fieldtype: "Data" },
			{ label: __("Days Delayed"), fieldname: "days_delayed", fieldtype: "Int" },
		],
		prsub: [
			{ label: __("Date"), fieldname: "posting_date", fieldtype: "Date" },
			{ label: __("Supplier"), fieldname: "supplier", fieldtype: "Link", options: "Supplier" },
			{ label: __("Items"), fieldname: "item_list", fieldtype: "Small Text" },
			{ label: __("Amount"), fieldname: "amount", fieldtype: "Currency" },
			{ label: __("Quality Inspection"), fieldname: "quality_inspection", fieldtype: "Link", options: "Quality Inspection" },
			{ label: __("Responsible User"), fieldname: "responsible_user", fieldtype: "Data" },
			{ label: __("Days Delayed"), fieldname: "days_delayed", fieldtype: "Int" },
		],
		pi: [
			{ label: __("Date"), fieldname: "posting_date", fieldtype: "Date" },
			{ label: __("Supplier"), fieldname: "supplier", fieldtype: "Link", options: "Supplier" },
			{ label: __("Items"), fieldname: "item_list", fieldtype: "Small Text" },
			{ label: __("Amount"), fieldname: "amount", fieldtype: "Currency" },
			{ label: __("Responsible User"), fieldname: "responsible_user", fieldtype: "Data" },
			{ label: __("Days Delayed"), fieldname: "days_delayed", fieldtype: "Int" },
		],
	},

	// Single source of truth mapping each summary column's fieldname to
	// its drill_type. Used by BOTH the formatter (to decide which cells
	// are clickable) and drill_down() (to decide which report view to
	// switch to) so the two can never drift out of sync.
	//
	// NOTE: "pending_po" -> "indent" -- this bucket is Material Requests
	// not yet converted into a Purchase Order ("Pending Indents"). It is
	// intentionally NOT called "po" to avoid confusion with the
	// "purchase_order" drilldown below, which is actual pending POs.
	_drill_field_map: {
		pending_po: "indent",
		pending_purchase_order: "purchase_order",
		pending_gate_entry: "pr",
		pending_qi: "qi",
		pending_pr_submission: "prsub",
		pending_pi: "pi",
	},

	// Which doctype each drilldown's rows belong to, so Days Delayed can
	// link straight to the document instead of showing a raw ID column.
	// This is the DEFAULT target -- the "pr" (pending gate entries)
	// drilldown overrides it per-row based on how far that PO's
	// weighment has progressed, see the days_delayed branch in
	// formatter() below.
	_drill_doctype_map: {
		indent: "Material Request",
		purchase_order: "Purchase Order",
		pr: "Purchase Order",
		qi: "Quality Inspection",
		prsub: "Purchase Receipt",
		pi: "Purchase Receipt",
	},

	formatter: function (value, row, column, data, default_formatter) {
		const item_col = frappe.query_reports["Procurement Pending Report"]._item_column_fieldname;

		// Item-exploded drilldowns: the server sends one row per item
		// (see mark_continuation_rows in the .py report), flagging every
		// row after a document's first as "_merged_continuation". Blank
		// every column except the item column on those rows, so the
		// grid reads as one merged block per document -- items stack on
		// their own lines instead of being comma-joined into one cell.
		if (data && data._merged_continuation && column.fieldname !== item_col) {
			return "";
		}

		// Combined Plant / Segment column (summary view). Plant is shown
		// in bold as plain text (not a link) -- segment stays plain text.
		if (column.fieldname === "plant_segment") {
			const plant = data.plant || "";
			const segment = data.segment || "";

			if (!plant && !segment) {
				return `<span class="text-muted">-</span>`;
			}

			let html = "";
			if (plant) {
				html += `<strong class="ppr-plant-name">${frappe.utils.escape_html(plant)}</strong>`;
			}
			if (segment) {
				html += plant
					? ` <span class="text-muted">/</span> ${frappe.utils.escape_html(segment)}`
					: frappe.utils.escape_html(segment);
			}
			return html;
		}

		// Date column: flag rows where NOTHING has moved yet -- these are
		// the priority items (rows are also sorted to the top of these
		// lists server-side where relevant).
		//   drill_type "purchase_order" -> Pending Purchase Orders (POs,
		//                                   0% received, no Gate Entry yet)
		//   drill_type "indent"         -> Pending Indents (MRs, 0% ordered)
		if (column.fieldname === "posting_date") {
			const drill_type = frappe.query_report.get_filter_value("drill_type");
			value = default_formatter(value, row, column, data);

			if (drill_type === "purchase_order" && flt(data.received_pct) === 0) {
				return `<span class="ppr-not-received-badge" title="${__(
					"No Gate Entry created against this PO yet, and nothing received"
				)}">${__("Not Received")}</span> ${value}`;
			}
			if (drill_type === "indent") {
				return `<span class="ppr-not-received-badge" title="${__(
					"No Purchase Order created against this Material Request yet"
				)}">${__("Not Ordered")}</span> ${value}`;
			}
			return value;
		}

		// Received % in the "purchase_order" (pending purchase orders)
		// drilldown: only draw it as a progress bar when there's more
		// than one Purchase Receipt against the PO -- that's the case
		// where "how much has come in so far" is actually ambiguous
		// without one. A single receipt's % is just its own
		// completeness, shown as plain text instead.
		//
		// IMPORTANT: the report column for received_pct is declared as
		// fieldtype "Data" in the .py file, not "Percent". Frappe's
		// DataTable auto-draws its own progress bar for any column typed
		// "Percent", which was rendering underneath/over this custom bar
		// and producing illegible overlapping text. Keep the column
		// fieldtype as "Data" if you touch this again, or the overlap
		// comes back.
		//
		// The wrap below is a single-line flex row (track + label side
		// by side) rather than stacked block elements, so it can't
		// collide vertically with neighboring row content regardless of
		// the grid's row-height handling.
		if (column.fieldname === "received_pct") {
			const pct = flt(data.received_pct || 0);
			const pr_count = cint(data.pr_count || 0);

			if (pr_count > 1) {
				const bar_color = get_received_pct_color(pct);
				return `
					<div class="ppr-progress-wrap" title="${__("{0}% received across {1} Purchase Receipts", [pct.toFixed(1), pr_count])}">
						<div class="ppr-progress-track">
							<div class="ppr-progress-fill"
								style="width: ${Math.min(pct, 100)}%; background-color: ${bar_color};">
							</div>
						</div>
						<span class="ppr-progress-label">${pct.toFixed(0)}%</span>
					</div>
				`;
			}
			// Single (or zero) Purchase Receipts against this PO -- the
			// bare number IS the whole picture here, so no bar is drawn.
			// Tooltip spells that out on hover instead of leaving it
			// unexplained next to rows that do show a bar.
			const tooltip = pr_count === 1
				? __("{0}% received — only 1 Purchase Receipt against this PO, so no bar is needed", [pct])
				: __("{0}% received — no Purchase Receipt raised against this PO yet", [pct]);
			return `<span class="text-muted" title="${tooltip}">${pct}%</span>`;
		}

		// Days Delayed becomes a clickable link in drilldown views -- we
		// don't show a separate ID column at all. Clicking it opens a
		// basic-details popup (styled with standard Frappe dialog/font
		// styling) instead of routing away to the full document.
		if (column.fieldname === "days_delayed" && data.document_no) {
			const drill_type = frappe.query_report.get_filter_value("drill_type");
			let doctype = frappe.query_reports["Procurement Pending Report"]._drill_doctype_map[drill_type];
			let docname = data.document_no;

			// Pending Gate Entries (pr): route to whichever document
			// reflects this PO's current stage --
			//   Weighment created  -> open the Weighment
			//   Gate Entry created (no Weighment yet) -> open the Gate Entry
			//   neither exists yet -> open the Purchase Order (default above,
			//   though in practice every row in this drilldown already has
			//   a Gate Entry, since that's what puts it in this bucket)
			if (drill_type === "pr") {
				if (data.weighment) {
					doctype = "Weighment";
					docname = data.weighment;
				} else if (data.gate_entry) {
					doctype = "Gate Entry";
					docname = data.gate_entry;
				}
			}

			value = default_formatter(value, row, column, data);

			const key = `${drill_type}|${data.document_no}`;
			frappe.query_reports["Procurement Pending Report"]._detail_registry[key] = {
				drill_type: drill_type,
				doctype: doctype,
				docname: docname,
				data: data,
			};
			return `<a href="#" class="ppr-days-link" data-detail-key="${frappe.utils.escape_html(key)}">${value}</a>`;
		}

		value = default_formatter(value, row, column, data);

		// Summary view: every "Pending ..." column is clickable and
		// drills into its matching detail view. Driven entirely off
		// _drill_field_map so adding/removing a drilldown only ever
		// needs to change that one map.
		const drill_map = frappe.query_reports["Procurement Pending Report"]._drill_field_map;
		if (drill_map[column.fieldname]) {
			if (!flt(data[column.fieldname])) {
				return `<span class="text-muted">-</span>`;
			}
			const key = `${column.fieldname}|${data.plant || ""}|${data.segment || ""}`;
			frappe.query_reports["Procurement Pending Report"]._drill_registry[key] = {
				fieldname: column.fieldname,
				plant: data.plant || "",
				segment: data.segment || "",
			};
			value = `<a href="#" class="pending-drill-link" data-key="${frappe.utils.escape_html(key)}">${value}</a>`;
		}
		return value;
	},

	drill_down: function (fieldname, plant, segment) {
		const map = frappe.query_reports["Procurement Pending Report"]._drill_field_map;
		const report = frappe.query_reports["Procurement Pending Report"]._report;
		set_filters_and_refresh_once(report, {
			drill_type: map[fieldname],
			plant: plant,
			segment: segment,
		});
	},

	onload: function (report) {
		frappe.query_reports["Procurement Pending Report"]._report = report;

		inject_styles();
		set_fiscal_year_default();
		watch_datatable_and_merge(report);
		toggle_above_amount_field();

		// "Back to Summary" clears the drilldown filters and refreshes
		// once. NOTE: frappe.set_route("query-report", report_name) was
		// tried here first, but it's a no-op when you're already on that
		// exact route -- Frappe's router only reacts to an ACTUAL route
		// change, so it never reset anything. Clearing the filters via
		// set_filter_value + a single refresh is what actually resets
		// the report content, and Frappe's own filter-change handling
		// already syncs those cleared values into the URL as a side
		// effect -- so a refresh or shared link still lands on summary.
		const back_btn = report.page.add_inner_button(__("Back to Summary"), function () {
			set_filters_and_refresh_once(report, { drill_type: "", plant: "", segment: "" });
		});
		back_btn.removeClass("btn-default").addClass("btn-primary");

		report.page.wrapper.off("click", "a.pending-drill-link");
		report.page.wrapper.on("click", "a.pending-drill-link", function (e) {
			e.preventDefault();
			const key = $(this).attr("data-key");
			const entry = frappe.query_reports["Procurement Pending Report"]._drill_registry[key];
			if (entry) {
				frappe.query_reports["Procurement Pending Report"].drill_down(
					entry.fieldname, entry.plant, entry.segment
				);
			}
		});

		report.page.wrapper.off("click", "a.ppr-days-link");
		report.page.wrapper.on("click", "a.ppr-days-link", function (e) {
			e.preventDefault();
			const key = $(this).attr("data-detail-key");
			const entry = frappe.query_reports["Procurement Pending Report"]._detail_registry[key];
			if (entry) {
				show_detail_popup(entry);
			}
		});

		// The page-level indicator (report.page.set_indicator) lives on
		// the SHARED "query-report" Page instance that every script
		// report reuses -- it was staying visible after navigating away
		// to a different report because nothing ever cleared it. Watch
		// the router and clear it the moment we're no longer on this
		// report.
		frappe.router.off("change", ppr_clear_indicator_on_route_leave);
		frappe.router.on("change", ppr_clear_indicator_on_route_leave);

		// handles the case where the report loads with drill_type already
		// set (e.g. page refresh / shared URL)
		update_drilldown_indicator(report);
	},
};

/**
 * Grays out / disables the "Amount Threshold" filter when "Only Above
 * Amount" is unchecked, so it's visually obvious the field has no effect
 * right now (its value is still sent, python just ignores it in that
 * case -- see only_above_1lakh_clause in the .py report).
 */
function toggle_above_amount_field() {
	const checked = cint(frappe.query_report.get_filter_value("only_above_1lakh"));
	const field = frappe.query_report.get_filter("above_amount");
	if (field && field.df) {
		field.df.read_only = !checked;
		field.refresh();
	}
}

/**
 * Bound once (re-registered per onload, de-duped via .off() above) to the
 * router's "change" event. Clears this report's indicator the instant the
 * route moves away from "Procurement Pending Report", so it can't bleed
 * into whatever other script report the page instance gets reused for
 * next.
 */
function ppr_clear_indicator_on_route_leave() {
	const route = frappe.get_route();
	const is_this_report = route[0] === "query-report" && route[1] === "Procurement Pending Report";
	const report = frappe.query_reports["Procurement Pending Report"]._report;
	if (!is_this_report && report && report.page) {
		report.page.clear_indicator();
	}
}

/**
 * Basic-details popup for a drilldown row's document link. Renders the
 * fields already present in the row (no extra server call) as a plain
 * Frappe-styled label/value table inside a standard frappe.ui.Dialog, so
 * fonts/spacing/colors match the rest of the desk. Includes an "Open
 * Full Record" button for anyone who does want to navigate through.
 */
function show_detail_popup(entry) {
	const { drill_type, doctype, docname, data } = entry;
	const fields = frappe.query_reports["Procurement Pending Report"]._detail_fields_map[drill_type] || [];

	const rows_html = fields
		.filter((f) => data[f.fieldname] !== undefined && data[f.fieldname] !== null && data[f.fieldname] !== "")
		.map((f) => {
			const df = { fieldtype: f.fieldtype, fieldname: f.fieldname, options: f.options };
			const formatted = frappe.format(data[f.fieldname], df);
			return `
				<div class="row" style="padding: 4px 0;">
					<div class="col-xs-5 text-muted">${frappe.utils.escape_html(f.label)}</div>
					<div class="col-xs-7">${formatted}</div>
				</div>
			`;
		})
		.join("");

	const dialog = new frappe.ui.Dialog({
		title: doctype ? `${doctype}: ${docname}` : docname,
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "detail_html",
				options: `<div class="ppr-detail-popup">${rows_html || `<div class="text-muted">${__("No details available")}</div>`}</div>`,
			},
		],
		primary_action_label: __("Open Full Record"),
		primary_action: function () {
			dialog.hide();
			if (doctype) {
				frappe.set_route(frappe.router.slug(doctype), docname);
			}
		},
	});

	dialog.show();
}

/**
 * Sets multiple report filters and triggers exactly ONE refresh, instead
 * of one refresh per filter (which is what caused the flicker/"glitching"
 * when going back to summary -- drill_type, plant, and segment were each
 * independently triggering their own report run in quick succession).
 *
 * We temporarily no-op the report's refresh method while looping through
 * set_filter_value calls, then restore it and call the real refresh once,
 * ourselves. The heading/indicator is cleared immediately so nothing
 * stale is visible during the transition, then rebuilt once the single
 * refresh has actually completed.
 */
function set_filters_and_refresh_once(report, filters_obj) {
	if (!report) return;

	report.page.clear_indicator();

	const original_refresh = frappe.query_report.refresh.bind(frappe.query_report);
	frappe.query_report.refresh = () => Promise.resolve();

	Object.keys(filters_obj).forEach((fieldname) => {
		frappe.query_report.set_filter_value(fieldname, filters_obj[fieldname]);
	});

	frappe.query_report.refresh = original_refresh;

	const result = frappe.query_report.refresh();
	if (result && typeof result.then === "function") {
		result.then(() => update_drilldown_indicator(report));
	} else {
		update_drilldown_indicator(report);
	}
}

function set_fiscal_year_default() {
	setTimeout(() => {
		if (frappe.query_report.get_filter_value("from_date")) {
			return; // don't clobber a value the user (or URL) already set
		}

		const fy = frappe.defaults.get_default("fiscal_year");

		const apply_date = (year_start_date) => {
			if (!year_start_date) return;
			frappe.query_report.set_filter_value("from_date", year_start_date);
			frappe.query_report.refresh();
		};

		if (fy) {
			frappe.db.get_value("Fiscal Year", fy, "year_start_date").then((r) => {
				if (r.message && r.message.year_start_date) {
					apply_date(r.message.year_start_date);
				} else {
					fallback_lookup_fiscal_year(apply_date);
				}
			}).catch(() => fallback_lookup_fiscal_year(apply_date));
		} else {
			fallback_lookup_fiscal_year(apply_date);
		}
	}, 300);
}

function fallback_lookup_fiscal_year(apply_date) {
	frappe.db.get_list("Fiscal Year", {
		filters: [
			["year_start_date", "<=", frappe.datetime.get_today()],
			["year_end_date", ">=", frappe.datetime.get_today()],
		],
		fields: ["year_start_date"],
		limit: 1,
	}).then((records) => {
		if (records && records.length) {
			apply_date(records[0].year_start_date);
		}
	});
}

function update_drilldown_indicator(report) {
	if (!report) return;

	const labelMap = {
		indent: __("Pending Indents"),
		purchase_order: __("Pending Purchase Orders"),
		pr: __("Pending Gate Entries"),
		qi: __("Pending Quality Inspection"),
		prsub: __("Pending Purchase Receipts"),
		pi: __("Pending Invoices"),
	};

	const drill_type = frappe.query_report.get_filter_value("drill_type");
	report.page.clear_indicator();

	if (drill_type && labelMap[drill_type]) {
		const plant = frappe.query_report.get_filter_value("plant");
		const segment = frappe.query_report.get_filter_value("segment");
		const scopeParts = [plant, segment].filter(Boolean);
		const scope = scopeParts.length ? ` — ${scopeParts.join(" / ")}` : "";
		report.page.set_indicator(`${labelMap[drill_type]}${scope}`, "blue");
	}

}

/**
 * Watches the report's DOM directly with a MutationObserver instead of
 * trying to hook a specific Frappe/datatable internal method. The
 * datatable library virtualizes rows (it adds/removes cell nodes as you
 * scroll and re-renders wholesale on every filter change or drilldown),
 * and guessing its internal render method name is fragile across Frappe
 * versions. Watching the DOM itself fires for every one of those cases
 * with no version-specific assumptions.
 *
 * The observer callback is coalesced with requestAnimationFrame so a
 * burst of mutations (e.g. scrolling past dozens of virtual rows) only
 * triggers one scan per frame instead of one per mutation.
 */
function watch_datatable_and_merge(report) {
	const ns = frappe.query_reports["Procurement Pending Report"];
	if (ns._merge_observer) return; // already watching, don't double-attach

	const container = report && report.page && report.page.wrapper && report.page.wrapper[0];
	if (!container) return;

	let scheduled = false;
	const run = () => {
		scheduled = false;
		apply_merged_row_styles(report);
	};

	const observer = new MutationObserver(() => {
		if (scheduled) return;
		scheduled = true;
		requestAnimationFrame(run);
	});
	observer.observe(container, { childList: true, subtree: true });
	ns._merge_observer = observer;

	// Run once immediately in case the grid is already on screen.
	apply_merged_row_styles(report);
}

/**
 * Makes the "merged" look actually look merged instead of just blank.
 * The server already sends "" for every column except the item on a
 * continuation row (see mark_continuation_rows in the .py report, and
 * the _merged_continuation check at the top of formatter() above) -- this
 * finds every grid cell whose rendered content is empty and flags it so
 * the CSS below can strip its row divider, so the value from the row
 * above visually flows straight through instead of being cut off by a
 * line.
 *
 * Deliberately keyed off "is this cell's content empty" rather than a
 * specific column index: the datatable library can insert its own
 * leading row-number/checkbox column and reorders columns on drag, so a
 * hard-coded column-index offset would drift. Emptiness is what we
 * actually control from the formatter, so it's what we match on.
 */
function apply_merged_row_styles(report) {
	if (!report || !report.page) return;
	const wrapper = report.page.wrapper && report.page.wrapper[0];
	if (!wrapper) return;

	const cells = wrapper.querySelectorAll(".dt-cell");
	cells.forEach((cell) => {
		const is_blank = (cell.innerText || cell.textContent || "").trim() === "";
		if (is_blank !== cell.classList.contains("ppr-merged-cell")) {
			cell.classList.toggle("ppr-merged-cell", is_blank);
		}
	});
}

/**
 * Color tier for the received-% progress bar:
 *   0-33%  red    -- barely started, needs attention
 *   34-74% amber  -- partially received
 *   75-99% blue   -- nearly complete
 *   100%   green  -- fully received
 */
function get_received_pct_color(pct) {
	if (pct >= 100) return "#28a745"; // green
	if (pct >= 75) return "#2490ef"; // blue
	if (pct >= 34) return "#f0ad4e"; // amber
	return "#d9534f"; // red
}

function inject_styles() {
	if (document.getElementById("ppr-report-styles")) return;

	const style = document.createElement("style");
	style.id = "ppr-report-styles";
	style.textContent = `
		a.pending-drill-link {
			color: #2490ef;
			text-decoration: none;
			font-weight: 600;
		}
		a.pending-drill-link:hover {
			color: #1a73c7;
			text-decoration: underline;
		}
		.ppr-plant-name {
			color: var(--text-color, #1a1a1a);
			font-weight: 700;
		}
		a.ppr-days-link {
			color: #2490ef;
			text-decoration: none;
			font-weight: 500;
		}
		a.ppr-days-link:hover {
			color: #1a73c7;
			text-decoration: underline;
		}
		.ppr-not-received-badge {
			display: inline-block;
			background: #ffe4e4;
			color: #c53030;
			font-size: 11px;
			font-weight: 600;
			padding: 1px 6px;
			border-radius: 10px;
			margin-right: 6px;
			vertical-align: middle;
		}
		/* Single-line flex row: bar track and % label sit side by side,
		   never stacked, so they can't visually collide with each other
		   or with adjacent cell content under the grid's row height. */
		.ppr-progress-wrap {
			display: flex;
			align-items: center;
			gap: 6px;
			min-width: 90px;
			line-height: 1;
		}
		.ppr-progress-track {
			position: relative;
			flex: 1 1 auto;
			height: 8px;
			background-color: #f0f0f0;
			border-radius: 4px;
			overflow: hidden;
		}
		.ppr-progress-fill {
			position: absolute;
			top: 0;
			left: 0;
			height: 100%;
			border-radius: 4px;
		}
		.ppr-progress-label {
			flex: 0 0 auto;
			font-size: 11px;
			color: #6c757d;
			white-space: nowrap;
		}
		.ppr-detail-popup .row {
			margin: 0;
			border-bottom: 1px solid var(--border-color, #d1d8dd);
		}
		.ppr-detail-popup .row:last-child {
			border-bottom: none;
		}
		/* Blank continuation-row cells (see apply_merged_row_styles):
		   drop the divider lines so the value from the row above reads
		   as one continuous merged block instead of stopping at an
		   empty row. Frappe's datatable has drawn cell borders via
		   plain "border" in some versions and via "box-shadow" in
		   others -- override both so this works either way. The
		   box-shadow override only zeroes the vertical (y) offset,
		   keeping the horizontal (x) offset intact, so the divider
		   between COLUMNS is untouched -- only the line between this
		   row and the next is removed. If your installed version still
		   shows a line here, open devtools on one of these cells,
		   check the Styles/Computed panel for whichever property is
		   actually drawing it, and that exact value can be targeted.
		*/
		.dt-cell.ppr-merged-cell {
			border-top-color: transparent !important;
			border-bottom-color: transparent !important;
			box-shadow: -1px 0 0 0 var(--dt-border-color, var(--border-color, #d1d8dd)) !important;
		}
	`;
	document.head.appendChild(style);
}