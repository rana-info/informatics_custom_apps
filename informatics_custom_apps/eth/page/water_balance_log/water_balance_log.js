frappe.pages['water-balance-log'].on_page_load = function(wrapper) {

    // =========================================================
    // PAGE SETUP
    // =========================================================

    let page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Water Balance Dashboard',
        single_column: true
    });


    // =========================================================
    // STATIC PLANTS
    // =========================================================

    const plants = [
        "Buttar Biofuels",
        "RSL Belwara",
        "RSL Buttar",
        "RSL Louhka",
        "RSLD Karnal",
        "Superior Biofuels"
    ];


    // =========================================================
    // PAGE HTML
    // =========================================================

    $(wrapper).find(".layout-main-section").html(`

        <div class="container-fluid">

            <!-- ================================================= -->
            <!-- SECTION A : DAILY DATA -->
            <!-- ================================================= -->

            <div class="card"
                 style="padding:20px; margin-bottom:30px;">

                <h4 style="margin-bottom:20px;">
                    Daily Water Balance Data
                </h4>

                <div class="row">

                    <div class="col-md-3">

                        <label>
                            <b>Date</b>
                        </label>

                        <input
                            type="date"
                            id="daily-date"
                            class="form-control"
                        >

                    </div>

                    <div
                        class="col-md-2"
                        style="margin-top:25px;"
                    >

                        <button
                            class="btn btn-primary"
                            id="load-daily-btn"
                            style="width:100%;"
                        >
                            Show Data
                        </button>

                    </div>

                </div>

            </div>


            <!-- DAILY DATA RESULT -->

            <div id="daily-data"></div>


            <!-- ================================================= -->
            <!-- SECTION B : TREND ANALYSIS -->
            <!-- ================================================= -->

            <div
                class="card"
                style="padding:20px; margin-top:30px; margin-bottom:20px;"
            >

                <h4 style="margin-bottom:20px;">
                    Water Balance Trend Analysis
                </h4>

                <div class="row">

                    <!-- PLANT -->

                    <div class="col-md-3">

                        <label>
                            <b>Plant</b>
                        </label>

                        <select
                            id="trend-plant"
                            class="form-control"
                        >

                            <option value="">
                                Select Plant
                            </option>

                            ${plants.map(
                                plant =>
                                `<option value="${plant}">
                                    ${plant}
                                </option>`
                            ).join('')}

                        </select>

                    </div>


                    <!-- PARAMETER -->

                    <div class="col-md-3">

                        <label>
                            <b>Parameter</b>
                        </label>

                        <select
                            id="trend-parameter"
                            class="form-control"
                        >

                            <option value="">
                                Select Parameter
                            </option>

                        </select>

                    </div>


                    <!-- FROM DATE -->

                    <div class="col-md-2">

                        <label>
                            <b>From Date</b>
                        </label>

                        <input
                            type="date"
                            id="trend-from-date"
                            class="form-control"
                        >

                    </div>


                    <!-- TO DATE -->

                    <div class="col-md-2">

                        <label>
                            <b>To Date</b>
                        </label>

                        <input
                            type="date"
                            id="trend-to-date"
                            class="form-control"
                        >

                    </div>


                    <!-- SHOW TREND -->

                    <div
                        class="col-md-2"
                        style="margin-top:25px;"
                    >

                        <button
                            class="btn btn-primary"
                            id="load-trend-btn"
                            style="width:100%;"
                        >
                            Show Trend
                        </button>

                    </div>

                </div>

            </div>


            <!-- TREND RESULT -->

            <div id="trend-chart"></div>

        </div>

    `);


    // =========================================================
    // SECTION A
    // LOAD DAILY DATA
    // =========================================================

    function loadDailyData() {

        const date =
            $("#daily-date").val();


        if (!date) {

            frappe.msgprint(
                "Please select Date."
            );

            return;

        }


        frappe.call({

            method:
            "informatics_custom_apps.eth.page.water_balance_log.water_balance_log.get_daily_dashboard",

            args: {

                date: date

            },

            callback(r) {

                const result =
                    r.message;


                if (
                    !result ||
                    !result.length
                ) {

                    $("#daily-data").html(`

                        <div class="alert alert-warning">

                            No Water Balance data found
                            for ${date}.

                        </div>

                    `);

                    return;

                }


                renderDailyDashboard(result);

            }

        });

    }


    // =========================================================
    // SECTION A
    // RENDER DAILY DASHBOARD
    // =========================================================

    function renderDailyDashboard(data) {

        let html = `

            <div
                class="card"
                style="padding:0; margin-bottom:30px;"
            >

                <table
                    class="table table-bordered"
                    style="margin-bottom:0;"
                >

                    <thead>

                        <tr>

                            <th
                                style="width:45px;"
                            >
                            </th>

                            <th>
                                Plant
                            </th>

                            <th>
                                Date
                            </th>

                        </tr>

                    </thead>

                    <tbody>

        `;


        data.forEach(
            (plant, index) => {

                const row_id =
                    `water-plant-${index}`;


                html += `

                    <!-- ================================= -->
                    <!-- PLANT HEADER -->
                    <!-- ================================= -->

                    <tr
                        class="plant-row"
                        data-target="${row_id}"
                        style="cursor:pointer;"
                    >

                        <td>

                            <span
                                class="plant-toggle"
                                id="${row_id}-icon"
                            >
                                ▶
                            </span>

                        </td>


                        <td>

                            <b>
                                ${plant.plant}
                            </b>

                        </td>


                        <td>

                            ${plant.date}

                        </td>

                    </tr>


                    <!-- ================================= -->
                    <!-- PLANT DETAILS -->
                    <!-- ================================= -->

                    <tr
                        id="${row_id}"
                        class="plant-details"
                        style="display:none;"
                    >

                        <td
                            colspan="3"
                            style="padding:0;"
                        >

                            <div
                                style="
                                    padding:20px;
                                    background:#f8f9fa;
                                "
                            >

                                ${renderPlantData(plant)}

                            </div>

                        </td>

                    </tr>

                `;

            }
        );


        html += `

                    </tbody>

                </table>

            </div>

        `;


        $("#daily-data").html(
            html
        );


        // =====================================================
        // PLANT EXPAND / COLLAPSE
        // =====================================================

        $(".plant-row").on(
            "click",
            function() {

                const target =
                    $(this).data(
                        "target"
                    );


                const details =
                    $(`#${target}`);


                const icon =
                    $(`#${target}-icon`);


                if (
                    details.is(":visible")
                ) {

                    details.hide();

                    icon.text("▶");

                } else {

                    details.show();

                    icon.text("▼");

                }

            }
        );

    }


    // =========================================================
    // SECTION A
    // RENDER PLANT DATA
    // =========================================================

    function renderPlantData(plant) {

        let html = `

            <table
                class="table table-bordered"
                style="margin-bottom:0;"
            >

                <thead>

                    <tr>

                        <th
                            style="width:60%;"
                        >
                            Parameter
                        </th>

                        <th>
                            Value
                        </th>

                    </tr>

                </thead>

                <tbody>

        `;


        plant.data.forEach(
            d => {

                let display_name =
                    d.label;


                if (
                    d.description
                ) {

                    display_name +=
                        ` — ${d.description.replace(/\n/g, " ")}`;

                }


                html += `

                    <tr>

                        <td>
                            ${display_name}
                        </td>

                        <td>
                            ${d.value}
                        </td>

                    </tr>

                `;

            }
        );


        html += `

                </tbody>

            </table>

        `;


        return html;

    }


    // =========================================================
    // SECTION B
    // LOAD PARAMETERS
    // =========================================================

    function loadParameters() {

        frappe.call({

            method:
            "informatics_custom_apps.eth.page.water_balance_log.water_balance_log.get_parameters",

            callback(r) {

                let options =
                    '<option value="">Select Parameter</option>';


                (r.message || []).forEach(
                    p => {

                        let display_name =
                            p.label;


                        if (
                            p.description
                        ) {

                            display_name +=
                                ` — ${p.description.replace(/\n/g, " ")}`;

                        }


                        options += `

                            <option
                                value="${p.fieldname}"
                            >
                                ${display_name}
                            </option>

                        `;

                    }
                );


                $("#trend-parameter").html(
                    options
                );

            }

        });

    }


    // =========================================================
    // SECTION B
    // LOAD TREND
    // =========================================================

    function loadTrend() {

        const plant =
            $("#trend-plant").val();


        const parameter =
            $("#trend-parameter").val();


        const from_date =
            $("#trend-from-date").val();


        const to_date =
            $("#trend-to-date").val();


        if (
            !plant ||
            !parameter ||
            !from_date ||
            !to_date
        ) {

            frappe.msgprint(
                "Please select Plant, Parameter and Date Range."
            );

            return;

        }


        frappe.call({

            method:
            "informatics_custom_apps.eth.page.water_balance_log.water_balance_log.get_parameter_trend",

            args: {

                plant:
                    plant,

                parameter:
                    parameter,

                from_date:
                    from_date,

                to_date:
                    to_date

            },


            callback(r) {

                const result =
                    r.message;


                if (
                    !result ||
                    !result.data ||
                    !result.data.length
                ) {

                    $("#trend-chart").html(`

                        <div
                            class="alert alert-warning"
                        >

                            No data found for
                            the selected filters.

                        </div>

                    `);

                    return;

                }


                renderTrendChart(
                    result
                );

            }

        });

    }


    // =========================================================
    // SECTION B
    // RENDER TREND CHART
    // =========================================================

    function renderTrendChart(result) {

        let labels = [];

        let values = [];


        // =====================================================
        // CHART DATA
        //
        // 0 values are NOT plotted.
        // They are still shown in Recorded Values table.
        // =====================================================

        result.data.forEach(
            d => {

                if (
                    d.value !== 0 &&
                    d.value !== null &&
                    d.value !== ""
                ) {

                    labels.push(
                        d.date
                    );

                    values.push(
                        d.value
                    );

                }

            }
        );


        $("#trend-chart").html(`

            <div
                class="card"
                style="padding:20px;"
            >

                <div
                    style="margin-bottom:15px;"
                >

                    <div>

                        <b>
                            Plant :
                        </b>

                        ${$("#trend-plant").val()}

                    </div>


                    <div>

                        <b>
                            Parameter :
                        </b>

                        ${result.label}

                    </div>

                </div>


                <div id="trend-graph"></div>


                <div
                    style="margin-top:20px;"
                >

                    <h4>
                        Recorded Values
                    </h4>

                    <div
                        id="trend-values"
                    ></div>

                </div>

            </div>

        `);


        // =====================================================
        // CHART
        // =====================================================

        if (
            labels.length
        ) {

            new frappe.Chart(
                "#trend-graph",
                {

                    title:
                        `${result.label} Trend`,

                    data: {

                        labels:
                            labels,

                        datasets: [

                            {

                                name:
                                    "Actual",

                                values:
                                    values

                            }

                        ]

                    },

                    type:
                        "line",

                    height:
                        350,

                    lineOptions: {

                        hideDots:
                            false,

                        regionFill:
                            false

                    },

                    axisOptions: {

                        min:
                            0

                    }

                }
            );

        } else {

            $("#trend-graph").html(`

                <div
                    class="alert alert-info"
                >

                    No non-zero values available
                    for charting in the selected
                    date range.

                </div>

            `);

        }


        // =====================================================
        // RECORDED VALUES TABLE
        // =====================================================

        let table = `

            <table
                class="table table-bordered"
            >

                <thead>

                    <tr>

                        <th>
                            Date
                        </th>

                        <th>
                            ${result.label}
                        </th>

                    </tr>

                </thead>

                <tbody>

        `;


        result.data.forEach(
            d => {

                table += `

                    <tr>

                        <td>
                            ${d.date}
                        </td>

                        <td>
                            ${d.value}
                        </td>

                    </tr>

                `;

            }
        );


        table += `

                </tbody>

            </table>

        `;


        $("#trend-values").html(
            table
        );

    }


    // =========================================================
    // BUTTON EVENTS
    // =========================================================

    $("#load-daily-btn").on(
        "click",
        function() {

            loadDailyData();

        }
    );


    $("#load-trend-btn").on(
        "click",
        function() {

            loadTrend();

        }
    );


    // =========================================================
    // INITIAL LOADING
    // =========================================================

    loadParameters();

};