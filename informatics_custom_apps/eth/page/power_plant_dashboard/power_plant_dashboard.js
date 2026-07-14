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

    let html = "";

    data.forEach(slot => {

        html += `
            <h5 class="mt-3 mb-2">${slot.time_slot}</h5>

            <table class="table table-bordered table-sm">
                <thead>
                    <tr>
                        <th width="30%">Parameter</th>
                        <th width="12%">Value</th>
                        <th width="10%">Unit</th>
                        <th width="12%">Min</th>
                        <th width="12%">Max</th>
                        <th width="14%">Status</th>
                    </tr>
                </thead>
                <tbody>
        `;

        // Group parameters by section
        let grouped = {};

        slot.values.forEach(v => {

            let section = v.section || "Other";

            if (!grouped[section]) {
                grouped[section] = [];
            }

            grouped[section].push(v);

        });

        Object.keys(grouped).forEach(section => {

            html += `
                <tr class="table-secondary">
                    <th colspan="6">
                        ${section}
                    </th>
                </tr>
            `;

            grouped[section].forEach(v => {

                let style = "";

                if (v.status === "Low") {
                    style = 'style="background:#fff3cd;"';
                }
                else if (v.status === "High") {
                    style = 'style="background:#f8d7da;"';
                }

                let value = (v.value === 0 || v.value === null) ? "" : v.value;

                let min = (v.min === null || v.min === undefined || v.min === 0)
                    ? "-"
                    : v.min;

                let max = (v.max === null || v.max === undefined || v.max === 0)
                    ? "-"
                    : v.max;

                html += `
                    <tr ${style}>
                        <td>${v.label}</td>
                        <td>${value}</td>
                        <td>${v.unit || "-"}</td>
                        <td>${min}</td>
                        <td>${max}</td>
                        <td>${v.status || ""}</td>
                    </tr>
                `;
            });

        });

        html += `
                </tbody>
            </table>
        `;

    });

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