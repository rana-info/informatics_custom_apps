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

                <div class="col-md-3">
                    <label>Plant</label>
                    <select id="trend-plant" class="form-control"></select>
                </div>

                <div class="col-md-3">
                    <label>Parameter</label>
                    <select id="trend-parameter" class="form-control"></select>
                </div>

                <div class="col-md-2">
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

    loadDashboard();

    $("#refresh-dashboard").click(loadDashboard);

}
function loadDashboard() {

    frappe.call({
        method: "informatics_custom_apps.eth.page.power_plant_dashboard.power_plant_dashboard.get_dashboard",

        args: {
            date: $("#dashboard-date").val()
        },

       callback(r) {

    console.log("========== DASHBOARD ==========");
    console.log("Complete Response:");
    console.log(r);

    console.log("Message:");
    console.log(r.message);

    console.log("Plants:");
    console.table(r.message.plants);

    renderPlantSummary(r.message.plants);
}
    });

}
function renderPlantSummary(plants) {
    console.log("Plants received by renderer:");
    console.table(plants);
    let html = `
        <table class="table table-bordered table-hover">

            <thead>

                <tr>
                    <th width="40"></th>
                    <th>Plant</th>
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
                data-plant="${p.plant}">

                <td>▶</td>

                <td><b>${p.plant}</b></td>

                <td>

                    <span class="badge badge-${badge}">
                        ${p.violations}
                    </span>

                </td>

                <td>${p.last_updated || ""}</td>

            </tr>

            <tr
                id="details-${frappe.scrub(p.plant)}"
                style="display:none;">

                <td colspan="4">

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

    let id = "#details-" + frappe.scrub(plant);

    if ($(id).is(":visible")) {

        $(id).hide();

        return;
    }

    $(".plant-details").parent().parent().hide();

    $(id).show();

    loadPlantDetails(
        plant,
        id + " .plant-details"
    );

});
function loadPlantDetails(plant, target) {

    $(target).html("Loading...");

    frappe.call({

        method:
        "informatics_custom_apps.eth.page.power_plant_dashboard.power_plant_dashboard.get_plant_logbook",

        args: {

            plant: plant,

            date: $("#dashboard-date").val()

        },

        callback(r) {

            console.log("Plant Logbook Response");
    console.log(r.message);

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
$("#show-trend").click(function () {

    frappe.call({

        method:
        "informatics_custom_apps.eth.page.power_plant_dashboard.power_plant_dashboard.get_parameter_trend",

        args: {

            from_date: $("#from-date").val(),

            to_date: $("#to-date").val(),

            plant: $("#trend-plant").val(),

            parameter: $("#trend-parameter").val()

        },

        callback(r) {

            console.log("Plant Logbook Response");
            console.log(r.message);

            renderPlantLogbook(target, r.message);

        }

    });

});