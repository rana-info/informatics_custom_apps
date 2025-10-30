# Copyright (c) 2025, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    columns = [
        {"label": "Description", "fieldname": "metric", "fieldtype": "Data", "width": 200},
        {"label": "Loukha", "fieldname": "loukha", "fieldtype": "Float"},
        {"label": "ETH", "fieldname": "eth", "fieldtype": "Float"},
        {"label": "Buttar", "fieldname": "buttar", "fieldtype": "Float"},
        {"label": "RSLD Karnal", "fieldname": "karnal", "fieldtype": "Float"},
        {"label": "KBPL", "fieldname": "kbpl", "fieldtype": "Float"},
        {"label": "Belwara", "fieldname": "belwara", "fieldtype": "Float"},
        {"label": "SBPL", "fieldname": "sbpl", "fieldtype": "Float"}
    ]
    if filters.get("date")=="2025-10-27":
            data = [
                {"metric": "Total Production", "loukha": 287212, "eth": 92255, "buttar": 340288, "karnal": 231336, "kbpl": 265055, "belwara": 85145, "sbpl": 260092},
                {"metric": "Steam Cost Per BL", "loukha": 3.21, "eth":3.21 , "buttar": 4.30, "karnal": 6.62, "kbpl": 6.12, "belwara": 6.12, "sbpl": 4.47},
            ]
    else:
        data = [
            {"metric": "Total Production", "loukha": 0, "eth": 0, "buttar": 0, "karnal": 0, "kbpl": 0, "belwara": 0, "sbpl": 0},
            {"metric": "Steam Cost Per BL", "loukha": 0, "eth":0 , "buttar": 0, "karnal": 0, "kbpl": 0, "belwara": 0, "sbpl": 0},
        ]      
    return columns, data

