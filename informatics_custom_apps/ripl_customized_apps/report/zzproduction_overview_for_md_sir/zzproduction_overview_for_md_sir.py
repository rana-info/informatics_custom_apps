# Copyright (c) 2025, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import formatdate

def execute(filters=None):

    date = filters.get("date")
    formatted_date = formatdate(date, "dd-MM-yy")
    # Fetch all plants involved
    plants = frappe.db.get_all("zzProduction Overview", 
        filters={"date": date,"docstatus":1}, 
        pluck="plant"
    )
    plants = sorted(plants)
    # Format as columns dynamically
    columns = [{"label": f"{formatted_date}", "fieldname": "metric", "fieldtype": "Data", "width": 200}]
    for plant in plants:
        columns.append({"label": plant, "fieldname": frappe.scrub(plant), "fieldtype": "Float", "width": 120})

    # Initialize Report Rows
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
        {"metric": "Steam Cost Per BL"}        
        # Add more metrics here as needed
    ]

    # Convert list -> dict for easy assignment
    data_map = {row["metric"]: row for row in data}

    # Fetch records
    records = frappe.get_all("zzProduction Overview",
        fields=[    "plant",
                    "ethanol",
                    "ena",
                    "target_production",
                    "alcohol_percentage",
                    "spent_wash_availablein_lakhs",
                    "average_starch_from_fcidfgmaize",
                    "fci",
                    "dfg",
                    "maize",
                    "steam_through_prdston",
                    "steam_through_turbineton",
                    "steam_fuel_rationcombine",
                    "steam_cost_per_ton",
                    "total_production",
                    "capacity_achieved",
                    "total_capacity_till_date",
                    "total_actual_production_till_date",
                    "capacity_utilization",
                    "loss_in_month",
                    "avg_per_day_loss",
                    "avg_bolier_load_per_hour",
                    "steam_cost_per_bl"],
        filters={"date": date,"docstatus":1}
    )

    # Fill values in rows (Pivot)
    for row in records:
        plant_key = frappe.scrub(row.plant)
        data_map["Production Ethanol"][plant_key] = row.ethanol
        data_map["Production ENA"][plant_key] = row.ena
        data_map["Total Production"][plant_key] = row.total_production
        data_map["Target Production"][plant_key] = row.target_production
        data_map["Capacity Achieved"][plant_key] = row.capacity_achieved
        data_map["Total Capacity Month Till Date"][plant_key] = row.total_capacity_till_date
        data_map["Total Production Month Till Date"][plant_key] = row.total_actual_production_till_date
        data_map["Capacity Utilization"][plant_key] = row.capacity_utilization
        data_map["Loss in month"][plant_key] = row.loss_in_month
        data_map["Avg Per Day Loss In Month"][plant_key] = row.avg_per_day_loss
        data_map["Alcohol Percentage"][plant_key] = row.alcohol_percentage
        data_map["Spent Wash Available(In Lakhs)"][plant_key] = row.spent_wash_availablein_lakhs
        data_map["Average Starch from FCI/DFG/Maize"][plant_key] = row.average_starch_from_fcidfgmaize
        data_map["Ethanol Recovery FCI"][plant_key] = row.fci
        data_map["Ethanol Recovery DFG"][plant_key] = row.dfg
        data_map["Ethanol Recovery Maize"][plant_key] = row.maize
        data_map["Steam Avg Bolier Load per Hour"][plant_key] = row.avg_bolier_load_per_hour
        data_map["Steam Through PRDS(Ton)"][plant_key] = row.steam_through_prdston
        data_map["Steam Through Turbine(Ton)"][plant_key] = row.steam_through_turbineton
        data_map["Steam Fuel Ration(Combine)"][plant_key] = row.steam_fuel_rationcombine
        data_map["Steam Cost per Ton"][plant_key] = row.steam_cost_per_ton
        data_map["Steam Cost Per BL"][plant_key] = row.steam_cost_per_bl


    return columns, data
