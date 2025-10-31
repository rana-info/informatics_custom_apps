# Copyright (c) 2025, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import formatdate, flt

def execute(filters=None):

    date = filters.get("date")
    formatted_date = formatdate(date, "dd-MM-yy")

    plants = [
        "Superior Biofuels",
        "RSL Buttar",
        "RSL Louhka",
        "ETH Louhka",
        "RSLD Karnal",
        "Karimganj Biofuels",
        "RSL Belwara"
    ]
    plants = sorted(plants)

    columns = [{"label": f"Date:{formatted_date}", "fieldname": "metric", "fieldtype": "Data", "width": 200}]

    for plant in plants:
        columns.append({
            "label": plant,
            "fieldname": frappe.scrub(plant),
            "fieldtype": "Float",
            "precision": 2,
            "width": 120
        })

    data = [
        {"metric": "Production Ethanol"},
        {"metric": "Production ENA"},
        {"metric": "Total Production"},
        {"metric": "Target Production"},
        {"metric": "Capacity Achieved"},
        {"metric": "Total Capacity Month Till Date"},
        {"metric": "Total Production Month Till Date"},
        {"metric": "Capacity Utilization"},
        {"metric": "Loss in month"},
        {"metric": "Avg Per Day Loss In Month"},
        {"metric": "Alcohol Percentage"},
        {"metric": "Spent Wash Available(In Lakhs)"},
        {"metric": "Average Starch from FCI/DFG/Maize"},
        {"metric": "Ethanol Recovery FCI"},
        {"metric": "Ethanol Recovery DFG"},
        {"metric": "Ethanol Recovery Maize"},
        {"metric": "Steam Avg Bolier Load per Hour"},
        {"metric": "Steam Through PRDS(Ton)"},
        {"metric": "Steam Through Turbine(Ton)"},
        {"metric": "Steam Fuel Ration(Combine)"},
        {"metric": "Steam Cost per Ton"},
        {"metric": "Steam Cost Per BL"},
    ]

    for row in data:
        for plant in plants:
            row[frappe.scrub(plant)] = 0

    data_map = {row["metric"]: row for row in data}

    records = frappe.get_all("zzProduction Overview",
        fields=[
            "plant", "ethanol", "ena", "total_production", "target_production",
            "capacity_achieved", "total_capacity_till_date", "total_actual_production_till_date",
            "capacity_utilization", "loss_in_month", "avg_per_day_loss",
            "alcohol_percentage", "spent_wash_availablein_lakhs", "average_starch_from_fcidfgmaize",
            "fci", "dfg", "maize", "avg_bolier_load_per_hour", "steam_through_prdston",
            "steam_through_turbineton", "steam_fuel_rationcombine", "steam_cost_per_ton",
            "steam_cost_per_bl"
        ],
        filters={"date": date, "docstatus": 1}
    )

    rec_map = {r.plant: r for r in records}

    for row in records:
        plant_key = frappe.scrub(row.plant)

        data_map["Production Ethanol"][plant_key] = flt(row.ethanol, 2)
        data_map["Production ENA"][plant_key] = flt(row.ena, 2)
        data_map["Total Production"][plant_key] = flt(row.total_production, 2)
        data_map["Target Production"][plant_key] = flt(row.target_production, 2)
        data_map["Capacity Achieved"][plant_key] = flt(row.capacity_achieved, 2)
        data_map["Total Capacity Month Till Date"][plant_key] = flt(row.total_capacity_till_date, 2)
        data_map["Total Production Month Till Date"][plant_key] = flt(row.total_actual_production_till_date, 2)
        data_map["Capacity Utilization"][plant_key] = flt(row.capacity_utilization, 2)
        data_map["Loss in month"][plant_key] = flt(row.loss_in_month, 2)
        data_map["Avg Per Day Loss In Month"][plant_key] = flt(row.avg_per_day_loss, 2)
        data_map["Alcohol Percentage"][plant_key] = flt(row.alcohol_percentage, 2)
        data_map["Spent Wash Available(In Lakhs)"][plant_key] = flt(row.spent_wash_availablein_lakhs, 2)

        data_map["Average Starch from FCI/DFG/Maize"][plant_key] = str(row.average_starch_from_fcidfgmaize or "")

        data_map["Ethanol Recovery FCI"][plant_key] = flt(row.fci, 2)
        data_map["Ethanol Recovery DFG"][plant_key] = flt(row.dfg, 2)
        data_map["Ethanol Recovery Maize"][plant_key] = flt(row.maize, 2)
        data_map["Steam Avg Bolier Load per Hour"][plant_key] = flt(row.avg_bolier_load_per_hour, 2)
        data_map["Steam Through PRDS(Ton)"][plant_key] = flt(row.steam_through_prdston, 2)
        data_map["Steam Through Turbine(Ton)"][plant_key] = flt(row.steam_through_turbineton, 2)
        data_map["Steam Fuel Ration(Combine)"][plant_key] = flt(row.steam_fuel_rationcombine, 2)
        data_map["Steam Cost per Ton"][plant_key] = flt(row.steam_cost_per_ton, 2)

    # -------------------------
    # SPECIAL GROUP CALCULATIONS
    # -------------------------

    def calc_special_cost(pair):
        prds_turbine = 0
        steam_cost_ton = 0

        for p in pair:
            if p in rec_map:
                prds_turbine = flt(rec_map[p].steam_through_prdston) + flt(rec_map[p].steam_through_turbineton)
                steam_cost_ton = flt(rec_map[p].steam_cost_per_ton)
                break

        total_prod = sum(flt(rec_map[p].total_production) for p in pair if p in rec_map)

        if total_prod > 0 and prds_turbine > 0 and steam_cost_ton > 0:
            return flt((prds_turbine * steam_cost_ton) / total_prod, 2)
        return 0.00

    # Pair 1: Louhka
    loukha_pair = ["RSL Louhka", "ETH Louhka"]
    loukha_cost = calc_special_cost(loukha_pair)
    for p in loukha_pair:
        if p in plants:
            data_map["Steam Cost Per BL"][frappe.scrub(p)] = loukha_cost

    # Pair 2: Belwara & Karimganj
    belwara_pair = ["RSL Belwara", "Karimganj Biofuels"]
    belwara_cost = calc_special_cost(belwara_pair)
    for p in belwara_pair:
        if p in plants:
            data_map["Steam Cost Per BL"][frappe.scrub(p)] = belwara_cost

    # For all NON special plants → use their own stored value
    special_all = loukha_pair + belwara_pair
    for row in records:
        if row.plant not in special_all:
            data_map["Steam Cost Per BL"][frappe.scrub(row.plant)] = flt(row.steam_cost_per_bl, 2)

    # Ensure starch column is Data type
    for row in data:
        if row["metric"] == "Average Starch from FCI/DFG/Maize":
            for col in columns:
                if col.get("fieldname") != "metric":
                    col["fieldtype"] = "Data"

    return columns, data
