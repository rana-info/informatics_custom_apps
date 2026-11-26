const PPD_API = "informatics_custom_apps.eth.page.power_plant_dashboard.power_plant_dashboard";

// Branch (Plant) -> allowed Segments. Same map as Material Request / Power Plant Log page.
const PPD_BRANCH_SEGMENT_MAP = {
    "Buttar Biofuels": ["Distillery"],
    "RSL Buttar": ["Sugar", "Power", "Beet"],
    "Lakshmiji Sugar": ["Sugar"],
    "Rana Power": ["Power"],
    "RSL Belwara": ["Sugar", "Power", "Distillery"],
    "RSL Louhka": ["Distillery"],
    "RSL Shahbad": ["Sugar", "Power"],
    "RSLD Karnal": ["Distillery"],
    "RSLD Biofuels-Chhattisgarh": ["Distillery"],
    "Karimganj Biofuels": ["Distillery"],
    "Superior Biofuels": ["Distillery"],
    "ETH Louhka": ["Distillery"],
    "Superior Unn": ["Sugar", "Power"]
};
const PPD_ALL_SEGMENTS = ["Beet", "Sugar", "Distillery", "Power"];

frappe.pages["power-plant-dashboard"].on_page_load = function (wrapper) {

    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Power Plant Dashboard",
        single_column: true
    });

    page.set_primary_action("Refresh", () => {
        loadDashboard();
    });

    $(page.body).html(`
        <div class="row mb-3">

            <div class="col-md-3">
                <label><b>Date</b></label>
                <input type="date" class="form-control" id="dashboard-date">
            </div>

            <div class="col-md-3">
                <label><b>Segment</b></label>
                <select class="form-control" id="dashboard-segment"></select>
            </div>

            <div class="col-md-2">
                <br>
                <button class="btn btn-primary" id="refresh-dashboard">
                    Refresh
                </button>
            </div>

        </div>

        <hr>

        <h4>Daily Plant Readings</h4>

        <div id="plant-summary"></div>

        <hr>

        <h4>Trend Analysis</h4>

        <div id="trend-section">

            <div class="row">

                <div class="col-md-2">
                    <label>From Date</label>
                    <input type="date" id="from-date" class="form-control">
                </div>

                <div class="col-md-2">
                    <label>To Date</label>
                    <input type="date" id="to-date" class="form-control">
                </div>

                <div class="col-md-2">
                    <label>Plant</label>
                    <select id="trend-plant" class="form-control"></select>
                </div>

                <div class="col-md-2">
                    <label>Segment</label>
                    <select id="trend-segment" class="form-control"></select>
                </div>

                <div class="col-md-2">
                    <label>Parameter</label>
                    <select id="trend-parameter" class="form-control"></select>
                </div>

                <div class="col-md-1">
                    <div class="form-check" style="margin-top:32px;">
                        <input
                            class="form-check-input"
                            type="checkbox"
                            id="show-limits"
                        >
                        <label class="form-check-label" for="show-limits">
                            Limits
                        </label>
                    </div>
                </div>

                <div class="col-md-1">
                    <br>
                    <button class="btn btn-primary" id="show-trend">
                        Show Trend
                    </button>
                </div>

            </div>

            <br>

            <div id="trend-chart"></div>

        </div>
    `);

    $("#dashboard-date").val(frappe.datetime.get_today());

    // Dashboard segment filter: "All Segments" + every segment
    let seg_options = '<option value="">All Segments</option>';
    PPD_ALL_SEGMENTS.forEach(s => {
        seg_options += `<option value="${s}">${s}</option>`;
    });
    $("#dashboard-segment").html(seg_options);

    // Trend filters are populated once, so a dashboard refresh doesn't reset them
    populatePlants();
    populateTrendSegments("");
    loadParameters();

    loadDashboard();

    $("#refresh-dashboard").click(loadDashboard);

    $("#dashboard-segment").on("change", loadDashboard);
    $("#dashboard-date").on("change", loadDashboard);

    // Plant change -> only that plant's allowed segments in trend filter
    $("#trend-plant").on("change", function () {
        populateTrendSegments($(this).val());
    });

    $(page.body).on("click", "#show-trend", function () {

        let from_date = $("#from-date").val();
        let to_date = $("#to-date").val();
        let plant = $("#trend-plant").val();
        let segment = $("#trend-segment").val();
        let parameter = $("#trend-parameter").val();

        if (!from_date || !to_date || !plant || !segment || !parameter) {
            frappe.msgprint("Please select all filters.");
            return;
        }

        frappe.call({
            method: PPD_API + ".get_parameter_trend",
            args: {
                from_date,
                to_date,
                plant,
                segment,
                parameter
            },
            callback(r) {
                renderTrendChart(r.message);
            }
        });
    });

}

function populatePlants() {

    const plants = [
        "Buttar Biofuels",
        "RSL Belwara",
        "RSL Buttar",
        "RSL Louhka",
        "RSLD Karnal",
        "Superior Biofuels"
    ];

    let options = '<option value="">Select Plant</option>';

    plants.forEach(function (plant) {
        options += `<option value="${plant}">${plant}</option>`;
    });

    $("#trend-plant").html(options);
}

function populateTrendSegments(plant) {

    if (!plant) {
        $("#trend-segment").html('<option value="">Select Segment</option>');
        return;
    }

    const allowed = PPD_BRANCH_SEGMENT_MAP[plant] || PPD_ALL_SEGMENTS;

    // a plant with a single segment is auto-selected
    let options = allowed.length === 1
        ? ""
        : '<option value="">Select Segment</option>';

    allowed.forEach(function (segment) {
        options += `<option value="${segment}">${segment}</option>`;
    });

    $("#trend-segment").html(options);
}

function loadParameters() {

    frappe.call({
        method: PPD_API + ".get_parameters",

        callback(r) {

            let options = '<option value="">Select Parameter</option>';

            r.message.forEach(p => {

                options += `
                <option value="${p.fieldname}">
                    ${p.section ? p.section + " → " : ""}${p.label}
                </option>`;
            });

            $("#trend-parameter").html(options);
        }
    });

}

function loadDashboard() {

    frappe.call({
        method: PPD_API + ".get_dashboard",

        args: {
            date: $("#dashboard-date").val(),
            segment: $("#dashboard-segment").val()
        },

        callback(r) {
            renderPlantSummary(r.message.plants);
        }
    });

}

function plantRowId(plant, segment) {
    return "details-" + frappe.scrub(plant + " " + (segment || "none"));
}

function renderPlantSummary(plants) {

    if (!plants || !plants.length) {
        $("#plant-summary").html(`
            <div class="alert alert-warning">
                No logbooks found for the selected date / segment.
            </div>
        `);
        return;
    }

    let html = `
        <table class="table table-bordered table-hover">

            <thead>

                <tr>
                    <th width="40"></th>
                    <th>Plant</th>
                    <th>Segment</th>
                    <th>Violations</th>
                    <th>Last Updated</th>
                </tr>

            </thead>

            <tbody>
    `;

    plants.forEach(p => {

        let badge = "success";

        if (p.violations > 0)
            badge = "danger";

        html += `

            <tr class="plant-row"
                data-plant="${frappe.utils.escape_html(p.plant)}"
                data-segment="${frappe.utils.escape_html(p.segment || "")}">

                <td>▶</td>

                <td><b>${p.plant}</b></td>

                <td>${p.segment || ""}</td>

                <td>

                    <span class="badge badge-${badge}">
                        ${p.violations}
                    </span>

                </td>

                <td>${p.last_updated || ""}</td>

            </tr>

            <tr
                id="${plantRowId(p.plant, p.segment)}"
                style="display:none;">

                <td colspan="5">

                    <div class="plant-details">
                        Loading...
                    </div>

                </td>

            </tr>
        `;

    });

    html += "</tbody></table>";

    $("#plant-summary").html(html);

}

$(document).on("click", ".plant-row", function () {

    let plant = $(this).data("plant");
    let segment = $(this).data("segment");

    let id = "#" + plantRowId(plant, segment);

    if ($(id).is(":visible")) {

        $(id).hide();

        return;
    }

    $(".plant-details").parent().parent().hide();

    $(id).show();

    loadPlantDetails(
        plant,
        segment,
        id + " .plant-details"
    );

});

function loadPlantDetails(plant, segment, target) {

    $(target).html("Loading...");

    frappe.call({

        method: PPD_API + ".get_plant_logbook",

        args: {
            plant: plant,
            segment: segment,
            date: $("#dashboard-date").val()
        },

        callback(r) {
            renderPlantLogbook(target, r.message);
        }

    });

}

function renderPlantLogbook(target, data) {

    if (!data || !data.length) {
        $(target).html(`
            <div class="alert alert-warning">
                No logbook data found.
            </div>
        `);
        return;
    }

    const slots = [
        "9:30 AM",
        "1:30 PM",
        "5:30 PM",
        "9:30 PM",
        "1:30 AM",
        "5:30 AM"
    ];

    let html = `
        <table class="table table-bordered table-sm">

            <thead>

                <tr>

                    <th>Parameter</th>

                    <th>Unit</th>
    `;

    slots.forEach(slot => {
        html += `<th>${slot}</th>`;
    });

    html += `
                    <th style="background:#eef5ff;">Min</th>
                    <th style="background:#eef5ff;">Max</th>

                </tr>

            </thead>

            <tbody>
    `;

    let current_section = "";

    data.forEach(p => {

        if (p.section !== current_section) {

            current_section = p.section;

            html += `
                <tr class="table-secondary">
                    <th colspan="${slots.length + 4}">
                        ${current_section || "Other"}
                    </th>
                </tr>
            `;
        }

        html += `<tr>`;

        html += `<td>${p.label}</td>`;

        html += `<td>${p.unit || ""}</td>`;

        slots.forEach(slot => {

            let cell = p.values[slot] || {};

            let value = cell.value ?? "";

            let status = cell.status || "";

            let style = "";

            if (status === "High") {
                style = 'background:#f8d7da;';
            }
            else if (status === "Low") {
                style = 'background:#fff3cd;';
            }

            html += `
                <td style="${style}">
                    ${value}
                </td>
            `;
        });

        html += `
            <td style="background:#eef5ff;font-weight:600;">
                ${p.min ?? "-"}
            </td>

            <td style="background:#eef5ff;font-weight:600;">
                ${p.max ?? "-"}
            </td>
        `;

        html += `</tr>`;
    });

    html += `
            </tbody>
        </table>
    `;

    $(target).html(html);

}


function renderTrendChart(result) {

    if (!result.data.length) {

        $("#trend-chart").html(`
            <div class="alert alert-warning">
                No data found.
            </div>
        `);

        return;
    }

    const hasMin = result.norm &&
        result.norm.min !== null &&
        result.norm.min !== "" &&
        result.norm.min !== 0;

    const hasMax = result.norm &&
        result.norm.max !== null &&
        result.norm.max !== "" &&
        result.norm.max !== 0;

    let labels = [];
    let values = [];
    let minValues = [];
    let maxValues = [];

    let normal = 0;
    let low = 0;
    let high = 0;

    result.data.forEach(d => {

        labels.push(`${d.date} ${d.time_slot}`);
        values.push(d.value);

        if (hasMin) {
            minValues.push(result.norm.min);
        }

        if (hasMax) {
            maxValues.push(result.norm.max);
        }

        if (hasMin && d.value < result.norm.min) {
            low++;
        }
        else if (hasMax && d.value > result.norm.max) {
            high++;
        }
        else {
            normal++;
        }

    });

    let rangeText = "";

    if (hasMin || hasMax) {

        rangeText = `
            <b>Normal Range :</b>
            ${hasMin ? result.norm.min : "-"}
            -
            ${hasMax ? result.norm.max : "-"}
            ${result.norm.unit || ""}
        `;

    } else {

        rangeText = `
            <b>Normal Range :</b> Not Configured
        `;

    }

    $("#trend-chart").html(`
        <div style="margin-bottom:15px;">

            <div><b>Plant :</b> ${$("#trend-plant").val()}</div>

            <div><b>Segment :</b> ${$("#trend-segment").val()}</div>

            <div>
                <b>Parameter :</b>
                ${$("#trend-parameter option:selected").text()}
            </div>

            <div>${rangeText}</div>

            <br>

            <span class="badge badge-success">
                Normal : ${normal}
            </span>

            <span class="badge badge-warning">
                Low : ${low}
            </span>

            <span class="badge badge-danger">
                High : ${high}
            </span>

        </div>
        <div id="trend-graph"></div>
    `);

    const showLimits = $("#show-limits").is(":checked");

    let datasets = [
        {
            name: "Actual",
            values: values
        }
    ];

    if (showLimits && hasMin) {
        datasets.push({
            name: "Min",
            values: minValues
        });
    }

    if (showLimits && hasMax) {
        datasets.push({
            name: "Max",
            values: maxValues
        });
    }

    new frappe.Chart("#trend-graph", {

        title: `${$("#trend-parameter option:selected").text()} Trend`,

        data: {
            labels: labels,
            datasets: datasets
        },

        type: "line",

        height: 350,

        lineOptions: {
            hideDots: false,
            regionFill: false
        },
        axisOptions: {
            min: 0
        }

    });

    let table = `
        <br>
        <details style="margin-top:20px;">
            <summary><b>Recorded Values (${result.data.length})</b></summary>

            <table class="table table-bordered table-sm table-hover">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Time Slot</th>
                        <th>Value</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
    `;

    result.data.forEach(d => {

        let status = "Normal";
        let badge = "success";

        if (hasMin && d.value < result.norm.min) {
            status = "Low";
            badge = "warning";
        }
        else if (hasMax && d.value > result.norm.max) {
            status = "High";
            badge = "danger";
        }

        table += `
            <tr>
                <td>${d.date}</td>
                <td>${d.time_slot}</td>
                <td>
                    <b>${d.value}</b>
                    ${result.norm ? (result.norm.unit || "") : ""}
                </td>
                <td>
                    <span class="badge badge-${badge}">
                        ${status}
                    </span>
                </td>
            </tr>
        `;
    });

    table += `
                </tbody>
            </table>
        </details>
    `;

    $("#trend-chart").append(table);

}