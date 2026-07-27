frappe.pages["cpu-dashboard"].on_page_load = function (wrapper) {
    new CPUDashboard(wrapper);
};


class CPUDashboard {

    constructor(wrapper) {

        this.wrapper = $(wrapper);

        this.page = frappe.ui.make_app_page({
            parent: wrapper,
            title: "CPU Plant Lab Dashboard",
            single_column: true
        });

        this.make_layout();

        this.set_default_date();

        this.bind_events();

        this.load_dashboard();

		this.load_trend_filters();
    }


    // =========================================================
    // LAYOUT
    // =========================================================

    make_layout() {

        this.wrapper.find(".layout-main-section").html(`

            <div class="cpu-dashboard">

                <!-- ================================================= -->
                <!-- SECTION A : DAILY PLANT READINGS -->
                <!-- ================================================= -->

                <div class="section-a">

                    <h3 class="section-title">
                        Daily Plant Readings
                    </h3>

                    <div class="filter-row">

                        <div class="filter-item">

                            <label>
                                Date
                            </label>

                            <input
                                type="date"
                                class="form-control"
                                id="cpu-date"
                            >

                        </div>

                        <div class="filter-item refresh-item">

                            <label>
                                &nbsp;
                            </label>

                            <button
                                class="btn btn-primary"
                                id="cpu-refresh"
                            >
                                Refresh
                            </button>

                        </div>

                    </div>


                    <div
                        id="cpu-daily-readings"
                        class="daily-readings"
                    >

                        <div class="text-muted text-center">
                            Loading...
                        </div>

                    </div>

                </div>


               <!-- ================================================= -->
<!-- SECTION B : TREND ANALYSIS -->
<!-- ================================================= -->

<div class="section-b">

    <h3 class="section-title">
        Trend Analysis
    </h3>

    <div class="trend-filter-row">

        <div class="filter-item">
            <label>Plant</label>

            <select
                class="form-control"
                id="trend-plant"
            >
                <option value="">Select Plant</option>
            </select>
        </div>


        <div class="filter-item">
            <label>Parameter</label>

            <select
                class="form-control"
                id="trend-parameter"
            >
                <option value="">Select Parameter</option>
            </select>
        </div>


        <div class="filter-item">
            <label>Location</label>

            <select
                class="form-control"
                id="trend-location"
            >
                <option value="">Select Location</option>
            </select>
        </div>

    </div>


    <div class="trend-filter-row">

        <div class="filter-item">

            <label>
                From Date
            </label>

            <input
                type="date"
                class="form-control"
                id="trend-from-date"
            >

        </div>


        <div class="filter-item">

            <label>
                To Date
            </label>

            <input
                type="date"
                class="form-control"
                id="trend-to-date"
            >

        </div>


        <div class="trend-options">

            <label class="norm-checkbox">

                <input
                    type="checkbox"
                    id="show-norms"
                >

                <span>
                    Show Norms
                </span>

            </label>

        </div>


        <div class="refresh-item">

            <label>
                &nbsp;
            </label>

            <button
                class="btn btn-primary"
                id="trend-refresh"
            >
                Refresh
            </button>

        </div>

    </div>


    <div
        id="cpu-trend-analysis"
        class="trend-analysis-container"
    >

        <div class="text-muted text-center trend-placeholder">

            Select filters and click Refresh
            to view trend analysis.

        </div>

    </div>

</div>

            </div>

        `);


        this.add_styles();
    }


    // =========================================================
    // DEFAULT DATE
    // =========================================================

    set_default_date() {

        const today = frappe.datetime.get_today();

        this.wrapper
            .find("#cpu-date")
            .val(today);
    }


    // =========================================================
    // EVENTS
    // =========================================================

    bind_events() {

    this.wrapper
        .find("#cpu-refresh")
        .on("click", () => {

            this.load_dashboard();

        });

	this.wrapper
    .find("#trend-refresh")
    .on("click", () => {

        this.load_trend_analysis();

    });


this.wrapper
    .find("#show-norms")
    .on("change", () => {

        // Only redraw the existing chart.
        // Do not make another API call.

        this.render_trend_chart();

    });

}


    // =========================================================
    // LOAD DASHBOARD
    // =========================================================

    load_dashboard() {

        const date = this.wrapper
            .find("#cpu-date")
            .val();


        if (!date) {

            frappe.msgprint(
                "Please select a date."
            );

            return;
        }


        const container = this.wrapper
            .find("#cpu-daily-readings");


        container.html(`

            <div class="text-muted text-center"
                 style="padding: 30px;">

                Loading daily plant readings...

            </div>

        `);


        frappe.call({

            method:
                "informatics_custom_apps.eth.page.cpu_dashboard.cpu_dashboard.get_daily_dashboard",

            args: {
                date: date
            },

            freeze: false,

            callback: (r) => {

                if (!r.message) {

                    this.show_no_data(
                        date
                    );

                    return;
                }


                this.render_daily_readings(
                    r.message
                );

            },

            error: () => {

                container.html(`

                    <div class="text-danger text-center"
                         style="padding: 30px;">

                        Failed to load CPU Plant Lab data.

                    </div>

                `);

            }

        });

    }
load_trend_filters() {

    frappe.call({

        method:
            "informatics_custom_apps.eth.page.cpu_dashboard.cpu_dashboard.get_trend_filters",

        callback: (r) => {

            if (!r.message) {
                return;
            }

            const data = r.message;


            // ==============================
            // PLANTS
            // ==============================

            const plantSelect =
                this.wrapper.find("#trend-plant");

            plantSelect
                .empty()
                .append(
                    `<option value="">
                        Select Plant
                    </option>`
                );


            (data.plants || []).forEach(plant => {

                plantSelect.append(`

                    <option value="${this.escape_html(plant)}">

                        ${this.escape_html(plant)}

                    </option>

                `);

            });


            // ==============================
            // PARAMETERS
            // ==============================

            const parameterSelect =
                this.wrapper.find("#trend-parameter");

            parameterSelect
                .empty()
                .append(
                    `<option value="">
                        Select Parameter
                    </option>`
                );


            (data.parameters || []).forEach(parameter => {

                parameterSelect.append(`

                    <option value="${this.escape_html(parameter)}">

                        ${this.escape_html(parameter)}

                    </option>

                `);

            });


            // ==============================
            // LOCATIONS
            // ==============================

            const locationSelect =
                this.wrapper.find("#trend-location");

            locationSelect
                .empty()
                .append(
                    `<option value="">
                        Select Location
                    </option>`
                );


            (data.locations || []).forEach(location => {

                locationSelect.append(`

                    <option value="${this.escape_html(location.fieldname)}">

                        ${this.escape_html(location.label)}

                    </option>

                `);

            });

        }

    });

}
// =========================================================
// LOAD TREND ANALYSIS
// =========================================================

load_trend_analysis() {

    const plant =
        this.wrapper
            .find("#trend-plant")
            .val();


    const parameter =
        this.wrapper
            .find("#trend-parameter")
            .val();


    const location =
        this.wrapper
            .find("#trend-location")
            .val();


    const from_date =
        this.wrapper
            .find("#trend-from-date")
            .val();


    const to_date =
        this.wrapper
            .find("#trend-to-date")
            .val();


    // =====================================================
    // VALIDATION
    // =====================================================

    if (!plant) {

        frappe.msgprint(
            "Please select a Plant."
        );

        return;

    }


    if (!parameter) {

        frappe.msgprint(
            "Please select a Parameter."
        );

        return;

    }


    if (!location) {

        frappe.msgprint(
            "Please select a Location."
        );

        return;

    }


    if (!from_date || !to_date) {

        frappe.msgprint(
            "Please select From Date and To Date."
        );

        return;

    }


    if (from_date > to_date) {

        frappe.msgprint(
            "From Date cannot be greater than To Date."
        );

        return;

    }


    const container =
        this.wrapper
            .find("#cpu-trend-analysis");


    container.html(`

        <div
            class="text-muted text-center"
            style="padding: 30px;"
        >

            Loading trend analysis...

        </div>

    `);


    // =====================================================
    // API CALL
    // =====================================================

    frappe.call({

        method:
            "informatics_custom_apps.eth.page.cpu_dashboard.cpu_dashboard.get_parameter_trend",

        args: {

            plant: plant,

            parameter: parameter,

            location: location,

            from_date: from_date,

            to_date: to_date

        },

        freeze: false,

        callback: (r) => {

            if (!r.message) {

                this.show_no_trend_data();

                return;

            }


            // Store trend data

            this.trend_data =
                r.message;


            // Render chart + table

            this.render_trend_analysis();

        },

        error: () => {

            container.html(`

                <div
                    class="
                        text-danger
                        text-center
                    "
                    style="padding: 30px;"
                >

                    Failed to load trend analysis.

                </div>

            `);

        }

    });

}
render_trend_analysis() {

    const data =
        this.trend_data;


    const records =
        data.data || [];


    const container =
        this.wrapper
            .find("#cpu-trend-analysis");


    if (!records.length) {

        this.show_no_trend_data();

        return;

    }


    let html = `

        <div class="trend-title">

            <strong>

                ${this.escape_html(data.plant)}

                → 

                ${this.escape_html(data.parameter)}

                → 

                ${this.escape_html(data.location)}

                Trend

            </strong>

        </div>


        <div
            id="cpu-trend-chart"
            class="cpu-trend-chart"
        >
        </div>


        <div
    class="recorded-values-header"
    id="recorded-values-toggle"
>

    <strong>

        <span class="recorded-values-icon">
            ▶
        </span>

        Recorded Values (${records.length})

    </strong>

</div>


<div
    class="recorded-values-content"
    style="display: none;"
>

    <div class="table-responsive">

        <table
            class="
                table
                table-bordered
                table-sm
                trend-values-table
            "
        >

            <thead>

                    <tr>

                    <th>
                        Date
                    </th>

                    <th>
                        Value
                    </th>

                    <th>
                        Status
                    </th>

                </tr>

            </thead>

            <tbody>
    `;


    records.forEach(record => {

        let statusClass =
            "trend-status-normal";


        if (record.status === "high") {

            statusClass =
                "trend-status-high";

        }
        else if (record.status === "low") {

            statusClass =
                "trend-status-low";

        }


        html += `

            <tr>

                <td>

                    ${this.escape_html(
                        record.date
                    )}

                </td>


                <td>

                    ${this.escape_html(
                        record.value
                    )}

                </td>


                <td>

                    <span
                        class="
                            trend-status
                            ${statusClass}
                        "
                    >

                        ${this.escape_html(
                            this.format_status(
                                record.status
                            )
                        )}

                    </span>

                </td>

            </tr>

        `;

    });


    html += `

                </tbody>

            </table>

        </div>

    </div>

`;


    container.html(html);


// =====================================================
// RECORDED VALUES DROPDOWN
// =====================================================

this.wrapper
    .find("#recorded-values-toggle")
    .on("click", () => {

        const content =
            this.wrapper
                .find(".recorded-values-content");

        const icon =
            this.wrapper
                .find(".recorded-values-icon");


        if (content.is(":visible")) {

            content.slideUp(200);

            icon.text("▶");

        }
        else {

            content.slideDown(200);

            icon.text("▼");

        }

    });


this.render_trend_chart();

}
render_trend_chart() {

    if (!this.trend_data) {
        return;
    }


    const records =
        this.trend_data.data || [];


    if (!records.length) {
        return;
    }


    const showNorms =
        this.wrapper
            .find("#show-norms")
            .is(":checked");


    const labels =
        records.map(
            record => record.date
        );


    const values =
        records.map(
            record => Number(record.value)
        );


    const datasets = [

        {
            name: "Actual Value",

            values: values

        }

    ];


    if (showNorms) {

        const minNorm =
            Number(
                this.trend_data.min_norm
            );


        const maxNorm =
            Number(
                this.trend_data.max_norm
            );


        if (!isNaN(minNorm)) {

            datasets.push({

                name: "Minimum Norm",

                values:
                    records.map(
                        () => minNorm
                    )

            });

        }


        if (!isNaN(maxNorm)) {

            datasets.push({

                name: "Maximum Norm",

                values:
                    records.map(
                        () => maxNorm
                    )

            });

        }

    }


    const chartContainer =
        this.wrapper
            .find("#cpu-trend-chart");


    chartContainer.empty();


    new frappe.Chart(
        chartContainer[0],
        {

            title:

                `${this.trend_data.parameter} Trend`,

            data: {

                labels: labels,

                datasets: datasets

            },

            type: "line",

            height: 350,

            lineOptions: {

                regionFill: 0,

                hideDots: 0,

                spline: 1

            },

            axisOptions: {

                xAxisMode: "tick",

                yAxisMode: "span"

            },

            tooltipOptions: {

                formatTooltipX:
                    d => d,

                formatTooltipY:
                    d => `${d} ${this.trend_data.unit || ""}`

            }

        }

    );

}
format_status(status) {

    if (status === "high") {

        return "High";

    }


    if (status === "low") {

        return "Low";

    }


    return "Normal";

}
show_no_trend_data() {

    this.wrapper
        .find("#cpu-trend-analysis")
        .html(`

            <div
                class="
                    no-data-message
                    text-center
                "
            >

                No trend data found
                for the selected filters.

            </div>

        `);

}

    // =========================================================
    // RENDER DAILY READINGS
    // =========================================================

    render_daily_readings(data) {

        const container = this.wrapper
            .find("#cpu-daily-readings");


        const plants = data.plants || [];


        if (!plants.length) {

            this.show_no_data(
                data.date
            );

            return;
        }


        let html = `

            <table class="table table-bordered
                          cpu-plant-table">

                <thead>

                    <tr>

                        <th style="width: 45px;"></th>

                        <th>
                            Plant
                        </th>

                        <th>
                            Violations
                        </th>

                        <th>
                            Last Updated
                        </th>

                    </tr>

                </thead>

                <tbody>
        `;


        plants.forEach((plant, index) => {

            const violationCount =
                Number(
                    plant.violation_count || 0
                );


            const violationClass =
                violationCount > 0
                    ? "violation-danger"
                    : "violation-success";


            html += `

                <!-- PLANT ROW -->

                <tr
                    class="plant-row"
                    data-index="${index}"
                >

                    <td class="expand-cell">

                        <span
                            class="expand-icon"
                            data-index="${index}"
                        >
                            ▶
                        </span>

                    </td>


                    <td>

                        <strong>
                            ${this.escape_html(
                                plant.plant || "-"
                            )}
                        </strong>

                    </td>


                    <td>

                        <span
                            class="
                                violation-badge
                                ${violationClass}
                            "
                        >
                            ${violationCount}
                        </span>

                    </td>


                    <td>

                        ${this.escape_html(
						this.format_datetime(
							plant.last_updated
						)
						)}

                    </td>

                </tr>


                <!-- EXPANDED PLANT DATA -->

                <tr
                    class="plant-detail-row"
                    data-index="${index}"
                    style="display:none;"
                >

                    <td colspan="4">

                        <div
                            class="plant-detail-container"
                        >

                            ${this.render_plant_details(
                                plant
                            )}

                        </div>

                    </td>

                </tr>

            `;

        });


        html += `

                </tbody>

            </table>

        `;


        container.html(html);


        this.bind_plant_rows();

    }


    // =========================================================
    // PLANT DETAILS
    // =========================================================

    render_plant_details(plant) {

        const rows =
            plant.rows || [];


        if (!rows.length) {

            return `

                <div class="text-muted"
                     style="padding: 20px;">

                    No CPU Plant Lab readings
                    found for this plant.

                </div>

            `;

        }


        let html = `

            <div class="plant-detail-header">

                <strong>
                    ${this.escape_html(
                        plant.plant || ""
                    )}
                </strong>

            </div>


            <div class="table-responsive">

                <table
                    class="
                        table
                        table-bordered
                        table-sm
                        cpu-detail-table
                    "
                >

                    <thead>

                        <tr>

                            <th>
                                No.
                            </th>

                            <th>
                                Parameter
                            </th>

                            <th>
                                Unit
                            </th>

                            <th>
                                EQT-Tank
                            </th>

                            <th>
                                CT-Tank
                            </th>

                            <th>
                                Reactor Inlet
                            </th>

                            <th>
                                Reactor Outlet
                            </th>

                            <th>
                                Aeration Tank
                            </th>

                            <th>
                                Sec. Clarifier Outlet
                            </th>

                            <th>
                                HRSCC Outlet
                            </th>

                            <th>
                                MGF Outlet
                            </th>

                            <th>
                                ACF Outlet
                            </th>

                            <th>
                                UV Outlet
                            </th>

                        </tr>

                    </thead>

                    <tbody>

        `;


        rows.forEach((row, index) => {

            html += `

                <tr>

                    <td>
                        ${row.s_no || index + 1}
                    </td>

                    <td>
                        <strong>
                            ${this.escape_html(
                                row.parameter || "-"
                            )}
                        </strong>
                    </td>

                    <td>
                        ${this.escape_html(
                            row.unit || "-"
                        )}
                    </td>

                    ${this.render_value_cell(
                        row,
                        "eqt_tank"
                    )}

                    ${this.render_value_cell(
                        row,
                        "ct_tank"
                    )}

                    ${this.render_value_cell(
                        row,
                        "reactor_inlet"
                    )}

                    ${this.render_value_cell(
                        row,
                        "reactor_outlet"
                    )}

                    ${this.render_value_cell(
                        row,
                        "aeration_tank"
                    )}

                    ${this.render_value_cell(
                        row,
                        "sec_clarifier_outlet"
                    )}

                    ${this.render_value_cell(
                        row,
                        "hrscc_outlet"
                    )}

                    ${this.render_value_cell(
                        row,
                        "mgf_outlet"
                    )}

                    ${this.render_value_cell(
                        row,
                        "acf_outlet"
                    )}

                    ${this.render_value_cell(
                        row,
                        "uv_outlet"
                    )}

                </tr>

            `;

        });


        html += `

                    </tbody>

                </table>

            </div>

        `;


        return html;
    }


    // =========================================================
    // VALUE CELL
    // =========================================================

	render_value_cell(row, fieldname) {

    const value = row[fieldname];

    const violation =
        row.violations &&
        row.violations[fieldname];


    console.log(
        "FIELD:",
        fieldname,
        "VALUE:",
        value,
        "VIOLATION:",
        violation
    );


    // =====================================================
    // TREAT 0 / NULL / EMPTY AS NOT ENTERED
    // =====================================================

    const isEmpty =
        value === null ||
        value === undefined ||
        value === "" ||
        Number(value) === 0;


    // Do not display or highlight empty values
    if (isEmpty) {

        return `
            <td></td>
        `;

    }


    // =====================================================
    // NORMAL VALUE - WITHIN NORMS
    // =====================================================

    if (!violation) {

        return `
            <td>
                ${this.escape_html(value)}
            </td>
        `;

    }


    // =====================================================
    // DETERMINE VIOLATION TYPE
    // =====================================================

    let violationClass = "";


    if (
        violation.max !== null &&
        violation.max !== undefined &&
        Number(value) > Number(violation.max)
    ) {

        // Above maximum → RED

        violationClass =
            "value-violation-high";

    }
    else if (
        violation.min !== null &&
        violation.min !== undefined &&
        Number(value) < Number(violation.min)
    ) {

        // Below minimum → ORANGE

        violationClass =
            "value-violation-low";

    }


    console.log(
        "Violation:",
        violation,
        "Applied class:",
        violationClass
    );


    return `
        <td class="${violationClass}">
            ${this.escape_html(value)}
        </td>
    `;

	}
    // =========================================================
    // PLANT EXPAND / COLLAPSE
    // =========================================================

    bind_plant_rows() {

        this.wrapper
            .find(".plant-row")
            .on("click", function () {

                const index =
                    $(this).attr(
                        "data-index"
                    );


                const detailRow =
                    $(
                        `.plant-detail-row[data-index="${index}"]`
                    );


                const icon =
                    $(
                        `.expand-icon[data-index="${index}"]`
                    );


                if (
                    detailRow.is(":visible")
                ) {

                    detailRow.hide();

                    icon.text("▶");

                }
                else {

                    detailRow.show();

                    icon.text("▼");

                }

            });

    }


    // =========================================================
    // NO DATA
    // =========================================================

    show_no_data(date) {

        this.wrapper
            .find("#cpu-daily-readings")
            .html(`

                <div
                    class="
                        no-data-message
                        text-center
                    "
                >

                    No CPU Plant Lab Log found
                    for ${this.escape_html(
                        date
                    )}.

                </div>

            `);

    }


    // =========================================================
    // ESCAPE HTML
    // =========================================================

    escape_html(value) {

        if (
            value === null ||
            value === undefined
        ) {

            return "";

        }


        return String(value)
            .replace(
                /&/g,
                "&amp;"
            )
            .replace(
                /</g,
                "&lt;"
            )
            .replace(
                />/g,
                "&gt;"
            )
            .replace(
                /"/g,
                "&quot;"
            )
            .replace(
                /'/g,
                "&#039;"
            );

    }


    // =========================================================
    // STYLES
    // =========================================================

    add_styles() {

        if (
            $("#cpu-dashboard-styles")
                .length
        ) {

            return;

        }


        $("head").append(`

            <style id="cpu-dashboard-styles">

                .cpu-dashboard {
                    padding: 10px 0 40px 0;
                }


                .section-a {
                    margin-top: 10px;
                }


                .section-title {
                    margin-bottom: 20px;
                    font-size: 20px;
                    font-weight: 600;
                }


                .filter-row {
                    display: flex;
                    align-items: flex-end;
                    gap: 20px;
                    margin-bottom: 25px;
                }


                .filter-item {
                    width: 390px;
                }


                .refresh-item {
                    width: auto;
                }


                .filter-item label {
                    display: block;
                    margin-bottom: 6px;
                    font-weight: 500;
                }


                .cpu-plant-table {
                    width: 100%;
                    margin-top: 15px;
                }


                .cpu-plant-table th {
                    font-weight: 600;
                    background: #f8f9fa;
                }


                .cpu-plant-table td,
                .cpu-plant-table th {
                    vertical-align: middle;
                    padding: 10px 12px;
                }


                .plant-row {
                    cursor: pointer;
                }


                .plant-row:hover {
                    background: #f8f9fa;
                }


                .expand-cell {
                    text-align: center;
                }


                .expand-icon {
                    display: inline-block;
                    font-size: 14px;
                    cursor: pointer;
                }


                .violation-badge {
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    min-width: 20px;
                    height: 20px;
                    padding: 2px 7px;
                    border-radius: 50%;
                    color: white;
                    font-size: 12px;
                    font-weight: 600;
                }


                .violation-success {
                    background: #28a745;
                }


                .violation-danger {
                    background: #dc3545;
                }


                .plant-detail-row {
                    background: #fafafa;
                }


                .plant-detail-container {
                    padding: 15px;
                    overflow-x: auto;
                }


                .plant-detail-header {
                    margin-bottom: 15px;
                    font-size: 16px;
                }


                .cpu-detail-table {
                    min-width: 1400px;
                    margin-bottom: 0;
                }


                .cpu-detail-table th {
                    white-space: nowrap;
                    background: #f8f9fa;
                }


                .cpu-detail-table td {
                    white-space: nowrap;
                    vertical-align: middle;
                }


                .cpu-detail-table td.value-violation-high {
				background-color: #f8d7da !important;
				color: #212529 !important;
				}

				.cpu-detail-table td.value-violation-low {
					background-color: #fff3cd !important;
					color: #212529 !important;
				}


                .no-data-message {
                    border: 1px dashed #d1d8dd;
                    border-radius: 8px;
                    padding: 40px;
                    color: #6c757d;
                }
				/* ========================================= */
				/* TREND ANALYSIS */
				/* ========================================= */

				.section-b {
					margin-top: 45px;
					padding-top: 30px;
					border-top: 1px solid #d1d8dd;
				}


				.trend-filter-row {
					display: flex;
					align-items: flex-end;
					gap: 20px;
					margin-bottom: 20px;
				}


				.trend-filter-row .filter-item {
					width: 280px;
				}


				.trend-options {
					display: flex;
					align-items: center;
					height: 38px;
				}


				.norm-checkbox {
					display: flex;
					align-items: center;
					gap: 8px;
					margin-bottom: 0;
					cursor: pointer;
					white-space: nowrap;
				}


				.norm-checkbox input {
					width: 16px;
					height: 16px;
					cursor: pointer;
				}


				.trend-title {
					font-size: 16px;
					margin-top: 30px;
					margin-bottom: 15px;
				}


				.cpu-trend-chart {
					width: 100%;
					min-height: 350px;
					margin-bottom: 35px;
				}


				.recorded-values-header {
					font-size: 16px;
					margin-bottom: 15px;
				}


				.trend-values-table {
					width: 100%;
				}


				.trend-values-table th {
					font-weight: 600;
					background: #f8f9fa;
				}


				.trend-values-table td,
				.trend-values-table th {
					padding: 10px 12px;
					vertical-align: middle;
				}


				.trend-status {
					display: inline-block;
					padding: 3px 10px;
					border-radius: 12px;
					font-size: 12px;
					font-weight: 600;
				}


				.trend-status-normal {
					background: #d4edda;
					color: #155724;
				}


				.trend-status-high {
					background: #f8d7da;
					color: #721c24;
				}


				.trend-status-low {
					background: #fff3cd;
					color: #856404;
				}
                .recorded-values-header {
                    font-size: 16px;
                    margin-top: 20px;
                    margin-bottom: 15px;
                    cursor: pointer;
                    user-select: none;
                    padding: 10px 12px;
                    border: 1px solid #d1d8dd;
                    border-radius: 6px;
                    background: #f8f9fa;
                }


                .recorded-values-header:hover {
                    background: #f1f3f5;
                }


                .recorded-values-icon {
                    display: inline-block;
                    width: 18px;
                    font-size: 12px;
                }


                .recorded-values-content {
                    margin-bottom: 25px;
                }

            </style>

        `);

    }
format_datetime(value) {

    if (!value) {
        return "-";
    }

    // Convert:
    // 2026-07-21 15:59:50.597135
    //
    // To:
    // 2026-07-21 15:59

    return String(value)
        .replace("T", " ")
        .substring(0, 16);

}
}