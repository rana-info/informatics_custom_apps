frappe.pages['water-balance-log'].on_page_load = function(wrapper) {

    let page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Water Balance Dashboard',
        single_column: true
    });
const plants = [
    "Buttar Biofuels",
        "RSL Belwara",
        "RSL Buttar",
        "RSL Louhka",
        "RSLD Karnal",
        "Superior Biofuels"
];
    $(wrapper).find(".layout-main-section").html(`
        <div class="container-fluid">

            <div class="card" style="padding:20px; margin-bottom:20px;">

                <h4 style="margin-bottom:20px;">
                    Water Balance Trend Analysis
                </h4>

                <div class="row">

                    <div class="col-md-3">
                        <label><b>Plant</b></label>
                        <select id="trend-plant" class="form-control">
                            <option value="">Select Plant</option>
                            ${plants.map(plant => `<option value="${plant}">${plant}</option>`).join('')}
                        </select>
                    </div>

                    <div class="col-md-3">
                        <label><b>Parameter</b></label>
                        <select id="trend-parameter" class="form-control">
                            <option value="">Select Parameter</option>
                        </select>
                    </div>

                    <div class="col-md-2">
                        <label><b>From Date</b></label>
                        <input
                            type="date"
                            id="trend-from-date"
                            class="form-control"
                        >
                    </div>

                    <div class="col-md-2">
                        <label><b>To Date</b></label>
                        <input
                            type="date"
                            id="trend-to-date"
                            class="form-control"
                        >
                    </div>

                    <div class="col-md-2" style="margin-top:25px;">
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

            <div id="trend-chart"></div>

        </div>
    `);


    // ---------------------------------------------------------
    // Load Plants
    // ---------------------------------------------------------

    function loadPlants() {

    let options = '<option value="">Select Plant</option>';

    plants.forEach(plant => {
        options += `
            <option value="${plant}">
                ${plant}
            </option>
        `;
    });

    $("#trend-plant").html(options);
}


    // ---------------------------------------------------------
    // Load Parameters
    // ---------------------------------------------------------

    function loadParameters() {

        frappe.call({

            method:
            "informatics_custom_apps.eth.page.water_balance_log.water_balance_log.get_parameters",

            callback(r) {

                let options = '<option value="">Select Parameter</option>';

                (r.message || []).forEach(p => {

                   let display_name = p.label;

					if (p.description) {
						display_name += ` — ${p.description.replace(/\n/g, " ")}`;
					}

					options += `
						<option value="${p.fieldname}">
							${display_name}
						</option>
					`;

                });

                $("#trend-parameter").html(options);

            }

        });

    }


    // ---------------------------------------------------------
    // Load Trend
    // ---------------------------------------------------------

    function loadTrend() {

        const plant = $("#trend-plant").val();
        const parameter = $("#trend-parameter").val();
        const from_date = $("#trend-from-date").val();
        const to_date = $("#trend-to-date").val();


        if (!plant || !parameter || !from_date || !to_date) {

            frappe.msgprint(
                "Please select Plant, Parameter and Date Range."
            );

            return;

        }


        frappe.call({

            method:
            "informatics_custom_apps.eth.page.water_balance_log.water_balance_log.get_parameter_trend",

            args: {
                plant: plant,
                parameter: parameter,
                from_date: from_date,
                to_date: to_date
            },

            callback(r) {

                const result = r.message;


                if (
                    !result ||
                    !result.data ||
                    !result.data.length
                ) {

                    $("#trend-chart").html(`
                        <div class="alert alert-warning">
                            No data found for the selected filters.
                        </div>
                    `);

                    return;

                }


                renderTrendChart(result);

            }

        });

    }


    // ---------------------------------------------------------
    // Render Trend Chart
    // ---------------------------------------------------------

    function renderTrendChart(result) {

        let labels = [];
		let values = [];

		result.data.forEach(d => {

			// Keep all records in the table,
			// but don't show 0 values in the chart
			if (d.value !== 0 && d.value !== null && d.value !== "") {
				labels.push(d.date);
				values.push(d.value);
			}

});


        $("#trend-chart").html(`

            <div class="card" style="padding:20px;">

                <div style="margin-bottom:15px;">

                    <div>
                        <b>Plant :</b>
                        ${$("#trend-plant").val()}
                    </div>

                    <div>
                        <b>Parameter :</b>
                        ${result.label}
                    </div>

                </div>


                <div id="trend-graph"></div>


                <div style="margin-top:20px;">

                    <h4>Recorded Values</h4>

                    <div id="trend-values"></div>

                </div>

            </div>

        `);


        // -----------------------------------------------------
        // Chart
        // -----------------------------------------------------

        new frappe.Chart("#trend-graph", {

            title: `${result.label} Trend`,

            data: {

                labels: labels,

                datasets: [
                    {
                        name: "Actual",
                        values: values
                    }
                ]

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


        // -----------------------------------------------------
        // Recorded Values Table
        // -----------------------------------------------------

        let table = `

            <table class="table table-bordered">

                <thead>

                    <tr>
                        <th>Date</th>
                        <th>${result.label}</th>
                    </tr>

                </thead>

                <tbody>

        `;


        result.data.forEach(d => {

            table += `

                <tr>

                    <td>${d.date}</td>

                    <td>${d.value}</td>

                </tr>

            `;

        });


        table += `

                </tbody>

            </table>

        `;


        $("#trend-values").html(table);

    }


    // ---------------------------------------------------------
    // Button Event
    // ---------------------------------------------------------

    $("#load-trend-btn").on("click", function() {

        loadTrend();

    });


    // ---------------------------------------------------------
    // Initial Loading
    // ---------------------------------------------------------

    loadPlants();

    loadParameters();

};