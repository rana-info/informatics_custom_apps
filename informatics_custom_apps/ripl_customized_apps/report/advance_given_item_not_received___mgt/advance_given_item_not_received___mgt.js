// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["Advance Given Item Not Received - MGT"] = {

    // maps a summary column's fieldname -> drill_type value expected by the python side
    drill_type_map: {
        advance_paid: "advance_paid",
        po_amount: "po_amount",
        received_amount: "material_received",
        pending_amount: "pending"
    },

    // drill_types where clicking the Purchase Order link should open the
    // lightweight items popup instead of the generic full-record popup
    po_basic_popup_drill_types: ["advance_paid", "po_amount", "pending", "material_received"],

    onload: function (report) {

        frappe.call({
            method: "erpnext.accounts.utils.get_fiscal_year",
            args: {
                date: frappe.datetime.get_today(),
                company: frappe.defaults.get_user_default("Company")
            },
            callback: function (r) {
                if (!r.message) return;

                if (!frappe.query_report.get_filter_value("from_date")) {
                    frappe.query_report.set_filter_value("from_date", r.message[1]);
                }
                if (!frappe.query_report.get_filter_value("to_date")) {
                    frappe.query_report.set_filter_value("to_date", frappe.datetime.get_today());
                }
            }
        });

        // "Back to Summary" - rendered via add_inner_button (page toolbar API)
        // then moved into the filter row and styled with the standard ERP
        // blue (btn-primary) so it reads as a primary action next to the filters,
        // not a generic page-level button.
        const $back_btn = report.page.add_inner_button(__("Back to Summary"), function () {
            const report_obj = frappe.query_reports["Advance Given Item Not Received - MGT"];
            const restore = report_obj._pre_drill_filters;

            // show Company again FIRST, then set the filter values that
            // trigger the report's data refresh - same ordering fix as the
            // drilldown click handler above, to prevent the flicker
            unlock_drill_filters();

            frappe.query_report.set_filter_value({
                drill_type: "",
                drill_group: "",
                plant: [],
                segment: [],
                company: restore ? restore.company : frappe.query_report.get_filter_value("company")
            });

            report_obj._pre_drill_filters = null;
        });

        style_and_reposition_back_button(report, $back_btn);

        // Lay Company / From Date / To Date out in a single row instead of
        // letting them wrap. Plant and Segment are hidden filters now, so
        // this row is short enough to fit on one line on most screens.
        report.page.wrapper.find(".page-form").css({
            "display": "flex",
            "flex-wrap": "nowrap",
            "align-items": "flex-end",
            "gap": "15px",
            "overflow-x": "auto"
        });

        // Summary -> drilldown navigation (metric columns)
        $(document).off("click", ".drilldown-link").on("click", ".drilldown-link", function (e) {
            e.preventDefault();
            const group = $(this).attr("data-group");
            const type = $(this).attr("data-type");
            const parts = group ? group.split("|||") : ["", ""];
            const branch = parts[0] || "";
            const segment = parts[1] || "";

            const report_obj = frappe.query_reports["Advance Given Item Not Received - MGT"];

            // remember Company as it was before drilling down, once
            // (Plant/Segment are hidden filters now, nothing to restore for them)
            if (!report_obj._pre_drill_filters) {
                report_obj._pre_drill_filters = {
                    company: frappe.query_report.get_filter_value("company") || []
                };
            }

            // hide Company FIRST, then set the filter values that trigger the
            // report's own data refresh - doing it in this order (instead of
            // toggling visibility right after set_filter_value) avoids the
            // layout flicker where the filter row rearranges mid-refresh
            lock_drill_filters();

            frappe.query_report.set_filter_value({
                drill_type: type,
                drill_group: group,
                plant: branch ? [branch] : [],
                company: [],
                segment: segment ? [segment] : []
            });

            frappe.show_alert(`Showing ${type.replace(/_/g, " ")} details`);
        });

        // Plant name in summary -> route straight to the Branch record
        $(document).off("click", ".plant-popup-link").on("click", ".plant-popup-link", function (e) {
            e.preventDefault();
            const branch = $(this).attr("data-branch");
            if (!branch) return;
            frappe.set_route("Form", "Branch", branch);
        });

        // Generic doc preview popup for drill-down Link cells (default case)
        $(document).off("click", ".doc-popup-link").on("click", ".doc-popup-link", function (e) {
            e.preventDefault();
            const doctype = $(this).attr("data-doctype");
            const docname = $(this).attr("data-name");
            if (!doctype || !docname) return;
            show_doc_popup(doctype, docname);
        });

        // Purchase Order link: basic-details popup (Items + Payment ID) instead
        // of the full doc dump, across every drill where a "purchase_order"
        // column can appear (Advance Paid, PO Amount, Pending, Material Received)
        $(document).off("click", ".po-basic-popup-link").on("click", ".po-basic-popup-link", function (e) {
            e.preventDefault();
            const po = $(this).attr("data-name");
            const payment_entry = $(this).attr("data-payment");
            if (!po) return;
            show_po_basic_popup(po, payment_entry);
        });

        // Purchase Receipt link, ONLY inside the Material Received drill:
        // shows the PO(s) tied to that receipt with PO amount, pending
        // amount, and the receipt's item/uom/rate/amount detail.
        $(document).off("click", ".pr-basic-popup-link").on("click", ".pr-basic-popup-link", function (e) {
            e.preventDefault();
            const pr = $(this).attr("data-name");
            if (!pr) return;
            show_pr_basic_popup(pr);
        });

        // if the report loads already scoped to a drilldown (e.g. saved/shared URL),
        // keep the locked-filter state consistent
        if (frappe.query_report.get_filter_value("drill_type")) {
            lock_drill_filters();
        }
    },

    formatter: function (value, row, column, data, default_formatter) {

        if (!data) {
            return default_formatter(value, row, column, data);
        }

        const is_summary_row = !!data.group_by;
        const is_total = data.group_by === "TOTAL" || data.purchase_order === "TOTAL" || data.purchase_receipt === "TOTAL";

        // TOTAL row: never render Link/plant fields as broken links
        if (is_total) {
            if (column.fieldtype === "Link" || column.fieldname === "group_by") {
                value = default_formatter(value, row, column, data);
                return `<span style="font-weight:700">${value}</span>`;
            }
            value = default_formatter(value, row, column, data);
            return `<span style="font-weight:700">${value}</span>`;
        }

        // Summary row: Plant/Segment -> blue link to the Branch record
        if (is_summary_row && column.fieldname === "group_by") {
            const branch_html = `<a href="#" class="plant-popup-link"
                        data-branch="${frappe.utils.escape_html(data.branch)}"
                        style="color:#2490ef; text-decoration:underline; cursor:pointer;">${frappe.utils.escape_html(data.branch)}</a>`;
            return data.segment ? `${branch_html} / ${frappe.utils.escape_html(data.segment)}` : branch_html;
        }

        // Summary row: metric cells drive drilldown navigation (unchanged)
        if (
            is_summary_row &&
            frappe.query_reports["Advance Given Item Not Received - MGT"].drill_type_map[column.fieldname]
        ) {
            value = default_formatter(value, row, column, data);
            const drill_type = frappe.query_reports["Advance Given Item Not Received - MGT"].drill_type_map[column.fieldname];
            return `<a href="#" class="drilldown-link"
                        data-group="${frappe.utils.escape_html(data.drill_group)}"
                        data-type="${drill_type}"
                        style="color:#2490ef; text-decoration:underline; cursor:pointer;">${value}</a>`;
        }

        // Drill-down rows: Link cells open a popup instead of navigating away
        if (!is_summary_row && column.fieldtype === "Link" && value) {
            const current_drill_type = frappe.query_report.get_filter_value("drill_type");

            if (
                column.fieldname === "purchase_order" &&
                frappe.query_reports["Advance Given Item Not Received - MGT"].po_basic_popup_drill_types.includes(current_drill_type)
            ) {
                return `<a href="#" class="po-basic-popup-link"
                            data-name="${frappe.utils.escape_html(value)}"
                            data-payment="${frappe.utils.escape_html(data.payment_entry || "")}"
                            style="color:#2490ef; text-decoration:underline; cursor:pointer;">${frappe.utils.escape_html(value)}</a>`;
            }

            if (column.fieldname === "purchase_receipt" && current_drill_type === "material_received") {
                return `<a href="#" class="pr-basic-popup-link"
                            data-name="${frappe.utils.escape_html(value)}"
                            style="color:#2490ef; text-decoration:underline; cursor:pointer;">${frappe.utils.escape_html(value)}</a>`;
            }

            return `<a href="#" class="doc-popup-link"
                        data-doctype="${frappe.utils.escape_html(column.options)}"
                        data-name="${frappe.utils.escape_html(value)}"
                        style="color:#2490ef; text-decoration:underline; cursor:pointer;">${frappe.utils.escape_html(value)}</a>`;
        }

        return default_formatter(value, row, column, data);
    },

    filters: [
        // Plant and Segment are shown read-only - they're only ever set
        // programmatically when a drilldown link is clicked (see the
        // ".drilldown-link" handler above, which now passes both branch and
        // segment through from data-group), never typed in by the user.
        {
            fieldname: "plant",
            label: "Plant",
            fieldtype: "MultiSelectList",
            readonly: 1
        },
        {
            fieldname: "segment",
            label: "Segment",
            fieldtype: "MultiSelectList",
            readonly: 1
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
        // hidden filters that drive drilldown state - never shown in the filter bar
        {
            fieldname: "drill_type",
            label: "Drill Type",
            fieldtype: "Data",
            hidden: 1
        },
        {
            fieldname: "drill_group",
            label: "Drill Group",
            fieldtype: "Data",
            hidden: 1
        }
    ]
};

// Show/hide a filter entirely from the filter bar
function toggle_filter_visibility(fieldname, show) {
    const filter = frappe.query_report.get_filter(fieldname);
    if (filter) filter.toggle(show);
}

function lock_drill_filters() {
    toggle_filter_visibility("company", false);
}

function unlock_drill_filters() {
    toggle_filter_visibility("company", true);
}

// Moves the "Back to Summary" button (created via page.add_inner_button, which
// places it in the page toolbar) down so it sits immediately to the right of
// the To Date filter, and styles it as a primary/blue action so it visually
// matches the rest of the ERP UI.
function style_and_reposition_back_button(report, $btn) {
    if (!$btn || !$btn.length) return;

    // ERPNext's standard primary/blue button styling
    $btn.removeClass("btn-default").addClass("btn-primary");

    // Wait a tick so the filter row has finished rendering, then move the
    // button to sit right after the To Date field specifically, rather than
    // at the end of the row (which drifted depending on which filters were
    // visible) or in the page toolbar.
    setTimeout(function () {
        const to_date_filter = frappe.query_report.get_filter("to_date");
        const $to_date_wrapper = to_date_filter && to_date_filter.$wrapper;

        if ($to_date_wrapper && $to_date_wrapper.length) {
            $btn.detach();
            $to_date_wrapper.after($btn);
            $btn.css({
                "margin-left": "15px",
                "align-self": "center",
                "flex": "0 0 auto"
            });
        }
    }, 0);
}

// Generic full-detail popup (used for Branch, Payment Entry, etc.)
function show_doc_popup(doctype, docname) {
    frappe.model.with_doctype(doctype, function () {
        frappe.db.get_doc(doctype, docname).then((doc) => {
            const meta = frappe.get_meta(doctype);
            const skip_fields = ["name", "owner", "creation", "modified", "modified_by", "docstatus", "idx"];
            const skip_fieldtypes = ["Section Break", "Column Break", "Tab Break", "HTML", "Table", "Button", "Attach", "Attach Image"];

            let rows = "";
            (meta.fields || []).forEach((df) => {
                if (df.hidden || skip_fields.includes(df.fieldname)) return;
                if (skip_fieldtypes.includes(df.fieldtype)) return;

                const val = doc[df.fieldname];
                if (val === undefined || val === null || val === "") return;

                rows += `<tr>
                            <td style="padding:4px 10px; font-weight:600; white-space:nowrap; vertical-align:top;">${__(df.label || df.fieldname)}</td>
                            <td style="padding:4px 10px;">${frappe.utils.escape_html(String(val))}</td>
                         </tr>`;
            });

            const d = new frappe.ui.Dialog({
                title: `${__(doctype)}: ${docname}`,
                fields: [
                    {
                        fieldtype: "HTML",
                        fieldname: "preview_html",
                        options: `<div style="max-height:60vh; overflow-y:auto;">
                                    <table style="width:100%; border-collapse:collapse;">${rows}</table>
                                  </div>`
                    }
                ],
                primary_action_label: __("Open Full Record"),
                primary_action: function () {
                    d.hide();
                    frappe.set_route("Form", doctype, docname);
                }
            });

            d.show();
        });
    });
}

// Minimal popup for Purchase Order, used from the Advance Paid, PO Amount,
// Pending, and Material Received drills: Items (name, uom, rate, amount
// only), plus the Payment ID when the row came from the Advance Paid drill
// (omitted otherwise).
function show_po_basic_popup(purchase_order, payment_entry) {
    frappe.call({
        method: "informatics_custom_apps.ripl_customized_apps.report.advance_given_item_not_received___mgt.advance_given_item_not_received___mgt.get_po_basic_details",
        args: { purchase_order },
        callback: function (r) {
            const items = (r.message && r.message.items) || [];

            let item_rows = items.map((it) => `
                <tr>
                    <td style="padding:4px 10px;">${frappe.utils.escape_html(it.item_name || "")}</td>
                    <td style="padding:4px 10px; text-align:right;">${frappe.format(it.uom, { fieldtype: "Data" })}</td>
                    <td style="padding:4px 10px; text-align:right;">${frappe.format(it.rate, { fieldtype: "Currency" })}</td>
                    <td style="padding:4px 10px; text-align:right;">${frappe.format(it.amount, { fieldtype: "Currency" })}</td>
                </tr>
            `).join("");

            const payment_html = payment_entry
                ? `<div style="margin-bottom:12px;">
                        <span style="font-weight:600;">${__("Payment ID")}:</span>
                        <a href="#" onclick="frappe.set_route('Form', 'Payment Entry', '${payment_entry}'); return false;"
                           style="color:#2490ef; text-decoration:underline;">${frappe.utils.escape_html(payment_entry)}</a>
                   </div>`
                : "";

            const html = `
                ${payment_html}
                <div style="max-height:50vh; overflow-y:auto;">
                    <table style="width:100%; border-collapse:collapse;">
                        <thead>
                            <tr>
                                <th style="text-align:left; padding:4px 10px; border-bottom:1px solid #d1d8dd;">${__("Item")}</th>
                                <th style="text-align:right; padding:4px 10px; border-bottom:1px solid #d1d8dd;">${__("UOM")}</th>
                                <th style="text-align:right; padding:4px 10px; border-bottom:1px solid #d1d8dd;">${__("Rate")}</th>
                                <th style="text-align:right; padding:4px 10px; border-bottom:1px solid #d1d8dd;">${__("Amount")}</th>
                            </tr>
                        </thead>
                        <tbody>${item_rows || `<tr><td colspan="4" style="padding:10px;">${__("No items found")}</td></tr>`}</tbody>
                    </table>
                </div>
            `;

            const d = new frappe.ui.Dialog({
                title: `${__("Purchase Order")}: ${purchase_order}`,
                fields: [{ fieldtype: "HTML", fieldname: "preview_html", options: html }],
                primary_action_label: __("Open Full Record"),
                primary_action: function () {
                    d.hide();
                    frappe.set_route("Form", "Purchase Order", purchase_order);
                }
            });

            d.show();
        }
    });
}

// Minimal popup for Purchase Receipt, used from the Material Received
// drill: groups the receipt's items by their Purchase Order, showing
// PO Number / PO Amount / Pending Amount once per PO, with that PO's
// item/uom/rate/amount detail listed underneath it.
function show_pr_basic_popup(purchase_receipt) {
    frappe.call({
        method: "informatics_custom_apps.ripl_customized_apps.report.advance_given_item_not_received___mgt.advance_given_item_not_received___mgt.get_pr_basic_details",
        args: { purchase_receipt },
        callback: function (r) {
            const items = (r.message && r.message.items) || [];

            // group items by purchase_order, preserving first-seen order
            const groups = {};
            const po_order = [];
            items.forEach((it) => {
                const po = it.purchase_order || "";
                if (!groups[po]) {
                    groups[po] = {
                        po_amount: it.po_amount,
                        pending_amount: it.pending_amount,
                        items: []
                    };
                    po_order.push(po);
                }
                groups[po].items.push(it);
            });

            const groups_html = po_order.map((po) => {
                const g = groups[po];

                const item_rows = g.items.map((it) => `
                    <tr>
                        <td style="padding:4px 10px;">${frappe.utils.escape_html(it.item_name || "")}</td>
                        <td style="padding:4px 10px; text-align:right;">${frappe.format(it.uom, { fieldtype: "Data" })}</td>
                        <td style="padding:4px 10px; text-align:right;">${frappe.format(it.rate, { fieldtype: "Currency" })}</td>
                        <td style="padding:4px 10px; text-align:right;">${frappe.format(it.amount, { fieldtype: "Currency" })}</td>
                    </tr>
                `).join("");

                return `
                    <div style="margin-bottom:14px; border:1px solid #d1d8dd; border-radius:4px; overflow:hidden;">
                        <div style="display:flex; flex-wrap:wrap; gap:28px; padding:8px 10px; background:#f7f8fa; border-bottom:1px solid #d1d8dd; font-weight:600;">
                            <span>${__("Purchase Order")}:
                                <a href="#" onclick="frappe.set_route('Form', 'Purchase Order', '${po}'); return false;"
                                   style="color:#2490ef; text-decoration:underline;">${frappe.utils.escape_html(po)}</a>
                            </span>
                            <span>${__("PO Amount")}: ${frappe.format(g.po_amount, { fieldtype: "Currency" })}</span>
                            <span>${__("Pending Amount")}: ${frappe.format(g.pending_amount, { fieldtype: "Currency" })}</span>
                        </div>
                        <table style="width:100%; border-collapse:collapse;">
                            <thead>
                                <tr>
                                    <th style="text-align:left; padding:4px 10px; border-bottom:1px solid #d1d8dd;">${__("Item")}</th>
                                    <th style="text-align:right; padding:4px 10px; border-bottom:1px solid #d1d8dd;">${__("UOM")}</th>
                                    <th style="text-align:right; padding:4px 10px; border-bottom:1px solid #d1d8dd;">${__("Rate")}</th>
                                    <th style="text-align:right; padding:4px 10px; border-bottom:1px solid #d1d8dd;">${__("Amount")}</th>
                                </tr>
                            </thead>
                            <tbody>${item_rows}</tbody>
                        </table>
                    </div>
                `;
            }).join("");

            const html = `
                <div style="max-height:60vh; overflow-y:auto;">
                    ${groups_html || `<div style="padding:10px;">${__("No items found")}</div>`}
                </div>
            `;

            const d = new frappe.ui.Dialog({
                title: `${__("Purchase Receipt")}: ${purchase_receipt}`,
                size: "extra-large",
                fields: [{ fieldtype: "HTML", fieldname: "preview_html", options: html }],
                primary_action_label: __("Open Full Record"),
                primary_action: function () {
                    d.hide();
                    frappe.set_route("Form", "Purchase Receipt", purchase_receipt);
                }
            });

            d.show();
        }
    });
}