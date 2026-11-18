# -*- coding: utf-8 -*-
"""
Sugar DMR (Daily Manufacturing Report) - backend

Source of formulas : DMR sheet of "DMR 2025-2026 Report" Excel
                     (daily row formulas = columns A..GL, printed report = GT..GX,
                      monthly report = HJ..HT)
                     + DMR_Punch_18-11-2026.xlsx (calculation block, with ROUND() steps)
Data comes from    : Sugar Process Data, zzStoppages, zzSteam And Power

All maths uses the *Excel column letters* as keys (D = cane crushed, BF = bagasse qty,
BZ = recovery % cane ...) so every line can be traced back to the sheet.

Three columns are produced, exactly like the workbook:
    Day      -> the selected date                        (row 10  of the sheet)
    Period   -> Period From .. selected date             (row 8   of the sheet)
    To Date  -> Season start .. selected date            (row 7   of the sheet)

Season Start / Period From are NOT typed on the page: they are set once per plant per season
in the "Sugar DMR Season" doctype (see sugar_dmr_season/). Plant is filtered by Company.

Exports (whitelisted):
    get_dmr_data      -> JSON for the page
    export_dmr_excel  -> formatted .xlsx (landscape A4, fit to width)
    export_dmr_pdf    -> formatted .pdf  (landscape A4, uses frappe's wkhtmltopdf)

PLACE THIS FILE somewhere importable (no brackets in the path), e.g.
    <your_app>/<module>/sugar_dmr.py
and set DMR_API in dmr-(sugar).js to  "<your_app>.<module>.sugar_dmr"
"""
import io
from datetime import date as _date

import frappe
from frappe.utils import add_days, cint, escape_html, flt, formatdate, get_first_day, getdate

SPD = "Sugar Process Data"
STP = "zzStoppages"
STM = "zzSteam And Power"

# --------------------------------------------------------------------------------------
# CONFIG  (edit here, no other code change needed)
# --------------------------------------------------------------------------------------
CAPACITY = 50000          # ql/day  (HL13 = Av.Crush / 50000 * 100)
BAG_DIVISOR = 2           # 50 kg bags -> quintals   (HA11 = X10/2)
IMB_NORM = 38             # imbibition norm % cane   (GR60)

# Targets / ranges printed in the "Target" column (from GO / labels of column GM)
TARGETS = {
    "cane": 68000,
    "crush_incl": 68000,
    "bag_pol": 1.8,
    "bag_moist": 49.75,
    "pc_pol": 1.55,
    "bag_save_pc": 5,
    "steam_sugar_pc": 38,
    "imb": IMB_NORM,
    "down_time": 0.33,
    "mill_ext": "95.50 - 96.25",
    "rme": "95.75 - 96.50",
}

# Headline figures (same as the tiles on the page): [title, row label in report]
KPIS = [
    ("Cane crushed", "Cane crushed"),
    ("Sugar production", "Sugar production"),
    ("Recovery", "Recovery (estd.)"),
    ("Mill extraction", "Mill extraction"),
    ("Hours worked", "Worked hours"),
    ("Total stoppage", "Total stoppage"),
]

# Optional store-consumption fields. They are NOT in the DocTypes you sent, so the
# section only appears when a field with this fieldname exists on Sugar Process Data.
# (label, unit, fieldname)
CHEMICALS = [
    ("Quick Lime", "ql", "quick_lime"),
    ("Sulphur", "ql", "sulphur"),
    ("Phosphoric Acid", "kg", "phosphoric_acid"),
    ("Flocculant (Juice)", "kg", "flocculant_juice"),
    ("Biocide", "kg", "biocide"),
    ("Bleaching Powder", "kg", "bleaching_powder"),
    ("Amm. Bifluoride", "kg", "amm_bifluoride"),
    ("Boiler Chemicals", "kg", "boiler_chemicals"),
    ("Seed Slurry", "kg", "seed_slurry"),
    ("Viscosity Reducer", "kg", "viscosity_reducer"),
    ("Foamex", "kg", "foamex"),
    ("Lubricants", "ltr", "lubricants"),
    ("Grease", "kg", "grease"),
    ("Caustic Soda", "kg", "caustic_soda"),
    ("Soda Ash", "kg", "soda_ash"),
    ("Hydrochloric Acid", "kg", "hcl"),
    ("C.P.", "kg", "chempol"),
    ("Sodium Chloride", "ql", "sodium_chloride"),
    ("Scale Softener", "kg", "scale_softener"),
]

# --------------------------------------------------------------------------------------
# FIELD MAPS  (Excel column -> DocType field)
# --------------------------------------------------------------------------------------
# s = Sugar Process Data, p = zzStoppages, m = zzSteam And Power
INPUTS = {
    # quantities
    "D": ("s", "cane_crushed_qty"), "C": ("s", "juice_qty"), "E": ("s", "water_qty"),
    "F": ("s", "press_cake_qty"), "G": ("s", "molasses_qty"),
    # sugar bagged (bags)
    "X": ("s", "l_31"), "Y": ("s", "m_30"), "Z": ("s", "m_31"), "AA": ("s", "raw"),
    "AB": ("s", "s_31"), "AC": ("s", "m_31_2"), "AE": ("s", "ex_s_31"),
    # cane receipt
    "DU": ("s", "early_variety"), "DV": ("s", "gen_variety"), "DW": ("s", "reject_cane"),
    "DY": ("s", "burnt_cane"),
    # stoppages (hours)
    "AF": ("p", "cane_feed"), "AG": ("p", "mills"), "AH": ("p", "rake_carrier"),
    "AI": ("p", "donnely_chute"), "AJ": ("p", "clfhouse"), "AK": ("p", "boiling__house"),
    "AL": ("p", "power_turbine"), "AM": ("p", "boiler"),
    "AO": ("p", "electrical"), "AP": ("p", "manufacturing"), "AQ": ("p", "cane"),
    "AR": ("p", "schedule_stoppage"), "AS": ("p", "growers_problem"), "AT": ("p", "power"),
    "AW": ("p", "gross_hours"),
    # steam & power
    "EA": ("m", "boiler_1"), "EB": ("m", "boiler_2"), "EC": ("m", "boiler_3"),
    "EE": ("m", "steam_condense"), "EJ": ("m", "bagasse_sale"),
    "EU": ("m", "power_generation"), "EV": ("m", "powercon_in"), "EW": ("m", "power_use_sug"),
    "EX": ("m", "powe_import"), "EY": ("m", "power_export"), "EZ": ("m", "bio"),
}

# Lab values that are AVERAGED over Period / To-date (Excel row 7/8 = AVERAGE(...)).
# NOTE: the DocType field names follow the sheet's row-3 labels, which are NOT the real
# stream names. The real meaning (row 2 of the sheet / printed report) is in PROCESS_ROWS.
AVG_FIELDS = [
    "primary_juice_bx", "primary_juice_pol", "last_roll_juice_bx", "last_roll_juice_pol",
    "filtered_juice_bx", "filtered_juice_pol", "clear_juice_bx", "clear_juice_pol",
    "syrup_bx_un", "syrup_pol", "syrup_bx", "syarp_pol",
    "a1_massecuite_bx", "a1_massecuite_pol", "ao2_massecuite_bx", "ao2_massecuite_pol",
    "ao3_massecuite_bx", "ao3_massecuite_pol", "a_massecuite_bx", "a_massecuite_pol",
    "b_massecuite_bx", "b_massecuite_pol", "c_massecuite_bx", "c_massecuite_pol",
    "a1_heavy_bx", "a1_heavy_pol", "b_sugar_bx", "b_sugar_pol", "caw_sugar_bx", "caw_sugar_pol",
    "c_1_sugar_bx", "c1_sugar_pol", "mealt", "melt_pol",
    "ah_molasses_bx", "ah_molasses_pol", "al_molasses_bx", "al_molasses_pol",
    "bh_molasses_bx", "bh_molasses_pol", "cl_molasses_bx", "cl_molasses_pol",
    "final_molasses_bx", "final_molasses_pol",
]

# (report label, brix field, pol field)  -> Column HA..HE of the printed report
PROCESS_ROWS = [
    ("Primary Juice", "primary_juice_bx", "primary_juice_pol"),
    ("Mixed Juice", "@mj_bx", "@mj_pol"),                       # weighted: BM*100/BL, BN*100/BL
    ("Last Mill Juice", "last_roll_juice_bx", "last_roll_juice_pol"),
    ("Filtrate Juice", "filtered_juice_bx", "filtered_juice_pol"),
    ("Clear Juice", "clear_juice_bx", "clear_juice_pol"),
    ("Unsulphured Syrup", "syrup_bx_un", "syrup_pol"),
    ("Sulphured Syrup", "syrup_bx", "syarp_pol"),
    ("Sulphited Juice", "a1_massecuite_bx", "a1_massecuite_pol"),         # sheet col CQ/CR
    ("A-Massecuite", "ao2_massecuite_bx", "ao2_massecuite_pol"),           # CS/CT
    ("B-Massecuite", "ao3_massecuite_bx", "ao3_massecuite_pol"),           # CU/CV
    ("C-Massecuite", "a_massecuite_bx", "a_massecuite_pol"),               # CW/CX
    ("C1-Massecuite", "b_massecuite_bx", "b_massecuite_pol"),              # CY/CZ
    ("B-Sugar", "c_massecuite_bx", "c_massecuite_pol"),                    # DA/DB
    ("C Double Cured Sugar", "a1_heavy_bx", "a1_heavy_pol"),               # DC/DD
    ("C Single Cured Sugar", "b_sugar_bx", "b_sugar_pol"),                 # DE/DF
    ("Melt", "caw_sugar_bx", "caw_sugar_pol"),                             # DG/DH
    ("A1-Heavy Molasses", "c_1_sugar_bx", "c1_sugar_pol"),                 # DI/DJ
    ("A-Heavy Molasses", "mealt", "melt_pol"),                             # DK/DL
    ("A-Light Molasses", "ah_molasses_bx", "ah_molasses_pol"),             # DM/DN
    ("B-Heavy Molasses", "al_molasses_bx", "al_molasses_pol"),             # DO/DP
    ("C1-Heavy Molasses", "bh_molasses_bx", "bh_molasses_pol"),            # DQ/DR
    ("CL-Molasses", "cl_molasses_bx", "cl_molasses_pol"),                  # DS/DT
    ("Final (CH) Molasses", "@fm_bx", "@fm_pol"),                          # weighted by BS
]

SUM_KEYS = (
    list(INPUTS)
    + ["BF", "BG", "BI", "BE", "BH", "BJ", "BK", "BL", "BM", "BN", "BO", "BP", "BR", "BS",
       "BU", "BV", "BW", "BX", "BY", "CA", "CB", "CC", "CD", "CE", "CF",
       "AN", "AU", "AV", "ED", "EF", "EH", "EI", "GG"]
    + ["chem_" + c[2] for c in CHEMICALS]
)


# --------------------------------------------------------------------------------------
# DAILY CALCULATION   (one plant, one date)  -  row 10 formulas of the sheet
# --------------------------------------------------------------------------------------
def _g(row, key):
    return flt((row or {}).get(key))


def _rnd(n, d=0):
    """Excel ROUND: half away from zero."""
    m = 10 ** d
    return (1 if n >= 0 else -1) * int(abs(n) * m + 0.5 + 1e-9) / m


def calc_day(s, p, m):
    s, p, m = s or {}, p or {}, m or {}
    d = {}
    for k, (src, f) in INPUTS.items():
        d[k] = _g({"s": s, "p": p, "m": m}[src], f)

    D, C, E, F, G = d["D"], d["C"], d["E"], d["F"], d["G"]
    H, I, J = _g(s, "dirt"), _g(s, "clarification_factor"), _g(s, "unknown_losses")
    K, L = _g(s, "primary_juice_bx"), _g(s, "primary_juice_pol")
    M_, N = _g(s, "mixed_juice_bx"), _g(s, "mixed_juice_pol")
    O, P = _g(s, "last_roll_juice_bx"), _g(s, "last_roll_juice_pol")
    S, T, U = _g(s, "bagasse_moisture"), _g(s, "bagasse_pol"), _g(s, "press_cake_pol")
    V, W = _g(s, "final_molasses_bx"), _g(s, "final_molasses_pol")
    CJ, CK = _g(s, "clear_juice_bx"), _g(s, "clear_juice_pol")

    z = dict.fromkeys(["BF", "BG", "BI", "BE", "BH", "BJ", "BK", "BL", "BM", "BN", "BO", "BP",
                       "BR", "BS", "BU", "BV", "BW", "BX", "BY", "CA", "CB", "CC", "CD", "CE", "CF"], 0.0)
    if D > 0:
        # ---- Bagasse
        BK = C                                                   # C76  gross M.J. qty
        BF = D + E - BK                                          # C68  bagasse qty
        lr_pty = (P * 100 / O) if O else 0                       # E12/E10%  last roller purity
        brix_bag = _rnd(T * 100 / lr_pty, 2) if lr_pty else 0    # E70  Brix % bagasse
        BD = 100 - S - brix_bag                                  # E72  fibre % bagasse
        BE = BF * BD / 100                                       # bagasse fibre qty (not in Excel)
        BG = _rnd(BF * S / 100)                                  # C70  bagasse moisture qty
        BI = _rnd(BF * T / 100)                                  # E68  bagasse pol qty
        BH = BI * O / P if P else 0                              # bagasse Bx qty (not in Excel)

        # ---- Mixed juice
        BJ = _rnd(BK * H / 100)                                  # C78  dirt qty
        BL = BK - BJ                                             # C80  net M.J. qty
        BM = _rnd(BL * M_ / 100)                                 # E76  Bx in M.J.
        BN = _rnd(BL * N / 100)                                  # E78  pol in M.J.
        BO = BM - BN                                             # E80  N.S. in M.J.
        BP = _rnd(F * U / 100)                                   # G76  press-cake pol qty

        # ---- Clear juice
        CL = _rnd(CK * 100 / CJ, 2) if CJ else 0                 # C64  clear juice purity
        CD = BN - BP                                             # G78  pol in clear juice
        CC = _rnd(CD * 100 / CL) if CL else 0                    # G80  Bx in clear juice
        CE = CC - CD                                             # G82  N.S. in clear juice

        # ---- Final molasses
        fm_pty = _rnd(W * 100 / V, 2) if V else 0                # C86  F. molasses purity
        BQ = _rnd(fm_pty / (100 - fm_pty), 3) if fm_pty < 100 else 0   # C88  molasses factor
        BW = V - W                                               # C90  N.S. in final molasses %
        CF = _rnd(CE * 100 / BW) if BW > 0 else 0                # C92  theoretical molasses
        BR = _rnd(CE * BQ)                                       # C94  loss in molasses

        # Not in Excel (blank cells there) - kept from the earlier version
        ns_old = BO - BO * I / 100
        BS = (ns_old * BQ + ns_old) * 100 / V if V else 0        # molasses input qty
        BU = V * BS / 100                                        # final molasses Bx qty
        BV = BS * W / 100                                        # final molasses pol qty

        # ---- Recovery
        BX = _rnd(D * J / 100)                                   # C100 unknown loss qty
        BY = CD - BR - BX                                        # E100 available sugar
        # E102 recovery % cane = ROUND(BY*100/D, 2) -> metrics() derives it from BY / D

        z.update(BF=BF, BG=BG, BI=BI, BE=BE, BH=BH, BJ=BJ, BK=BK, BL=BL, BM=BM, BN=BN, BO=BO,
                 BP=BP, BR=BR, BS=BS, BU=BU, BV=BV, BW=BW, BX=BX, BY=BY,
                 CA=G * V / 100, CB=G * W / 100, CC=CC, CD=CD, CE=CE, CF=CF)
    d.update(z)

    # stoppages
    d["AN"] = sum(d[k] for k in ("AF", "AG", "AH", "AI", "AJ", "AK", "AL", "AM"))
    d["AU"] = d["AO"] + d["AP"] + d["AQ"] + d["AR"] + d["AS"] + d["AT"] + d["AN"]
    d["AV"] = d["AW"] - d["AU"]                                  # hours worked

    # steam & bagasse balance
    d["ED"] = _g(m, "total") or (d["EA"] + d["EB"] + d["EC"])    # steam generated (ton)
    d["EF"] = d["ED"] - d["EE"]                                  # steam consumption
    EG = _g(m, "bagasse_ratio")
    d["EH"] = d["ED"] / EG if EG else 0                          # bagasse consumed
    d["EI"] = (d["BF"] / 10 - d["EH"]) if D > 0 else 0           # bagasse saved
    # GG (steam used in sugar process) is not a DocType field -> custom field if you add it
    d["GG"] = _g(s, "steam_consumption_sugar") or d["EF"]

    for _, _, f in CHEMICALS:
        d["chem_" + f] = _g(s, f)
    for f in AVG_FIELDS:
        d["v_" + f] = _g(s, f)
    return d


# --------------------------------------------------------------------------------------
# AGGREGATION  -  row 7 / row 8 of the sheet
# --------------------------------------------------------------------------------------
def aggregate(days):
    a = {k: sum(d.get(k, 0) for d in days) for k in SUM_KEYS}
    a["n_days"] = len({d.get("_date") for d in days if d.get("D")}) or 0
    for f in AVG_FIELDS:                     # AVERAGE() ignores blanks -> ignore zeros here
        vals = [d["v_" + f] for d in days if d.get("v_" + f)]
        a["v_" + f] = sum(vals) / len(vals) if vals else 0
    return a


def _pty(bx, pol):
    return pol * 100 / bx if bx else 0


def metrics(a, is_day=False):
    x = dict(a)
    D = a["D"]
    dv = lambda n, d: (n / d) if d else 0
    pc = lambda n: dv(n * 100, D)

    # --- weighted analyses (HR/HS columns of the monthly block)
    x["mj_bx"], x["mj_pol"] = dv(a["BM"] * 100, a["BL"]), dv(a["BN"] * 100, a["BL"])
    x["fm_bx"] = dv(a["BU"] * 100, a["BS"]) or a["v_final_molasses_bx"]
    x["fm_pol"] = dv(a["BV"] * 100, a["BS"]) or a["v_final_molasses_pol"]
    x["bag_pol"], x["bag_moist"] = dv(a["BI"] * 100, a["BF"]), dv(a["BG"] * 100, a["BF"])
    x["bag_fibre"], x["pc_pol"] = dv(a["BE"] * 100, a["BF"]), dv(a["BP"] * 100, a["F"])
    x["mill_loss"] = dv(x["bag_pol"] * 100, x["bag_fibre"])      # HD48

    # --- cane / time
    x["crush_incl"] = dv(D * 24, a["AW"])                        # GW11
    x["crush_excl"] = dv(D * 24, a["AV"])                        # GW12
    x["cap_gross"] = x["crush_incl"] * 100 / CAPACITY
    x["cap_net"] = x["crush_excl"] * 100 / CAPACITY
    x["stp_pct"] = dv(a["AU"] * 100, a["AW"])
    x["down_time"] = a["AU"] if is_day else None

    # --- sugar production
    for k, n in (("l31", "X"), ("m30", "Y"), ("m31", "Z"), ("s31", "AB")):
        x[k] = a[n] / BAG_DIVISOR                                # HA11..HA14
    x["sugar"] = x["l31"] + x["m30"] + x["m31"] + x["s31"]       # HA15
    for k in ("l31", "m30", "m31", "s31"):
        x[k + "_pct"] = dv(x[k] * 100, x["sugar"])               # HC11..HC14
    x["sugar_out"] = dv(x["sugar"] * 100, D)                     # GW44
    x["sugar_proc"] = a["BY"] - x["sugar"]                       # GX48 (without BISS)

    # --- control figures
    x["pol_cane"] = pc(a["BI"] + a["BN"])                        # GW24
    x["ns_cane"] = pc(a["BH"] + a["BM"]) - x["pol_cane"]         # GW23
    x["rec"] = dv(a["BY"] * 100, D)                              # GW25 / BZ
    x["tot_loss"] = x["pol_cane"] - x["rec"]                     # GW26
    x["loss_bag"], x["loss_pc"] = pc(a["BI"]), pc(a["BP"])       # GW27, GW28
    x["loss_mol"], x["unk"] = pc(a["BR"]), pc(a["BX"])           # GW29, GW30
    x["fibre"] = pc(a["BE"])                                     # GW31
    x["mj_pc"], x["imb"] = pc(a["BL"]), pc(a["E"])               # GW33, GW34
    x["dry_mill"] = x["mj_pc"] - x["imb"]                        # GW32
    x["bag_pc"], x["fc_pc"] = pc(a["BF"]), pc(a["F"])            # GW35, GW36
    x["mol_in_pc"], x["mol_out_pc"] = pc(a["BS"]), pc(a["G"])    # GW37, GW38
    x["mill_ext"] = dv(a["BN"] * 100, a["BN"] + a["BI"])         # GW39
    x["rme"] = (100 - ((100 - x["mill_ext"]) * (100 - x["fibre"])) / (7 * x["fibre"])) if x["fibre"] else 0  # GW40
    x["java"] = dv(x["pol_cane"] * 100, a["v_primary_juice_pol"])              # GW41
    x["add_water_fibre"] = dv(x["imb"] * 100, x["fibre"])        # GW42
    x["bhr"] = dv(x["rec"] * 100, x["pol_cane"] - x["loss_bag"])               # GW43
    x["overall_rec"] = dv(x["rec"] * 100, x["pol_cane"])         # HL49
    pty_mj = _pty(x["mj_bx"], x["mj_pol"])
    den = 100 - pty_mj * x["bhr"] / 100
    x["vp_fm"] = ((pty_mj - x["bhr"] * pty_mj / 100) * 100 / den) if den else 0   # HL51
    x["rbhr"] = (100 * (85 - x["vp_fm"])) / (85 * (100 - x["vp_fm"])) * 100 if x["vp_fm"] != 100 else 0  # HL48
    x["reduced_overall"] = x["rme"] * x["rbhr"] / 100            # HL50

    # --- targets
    x["bag_save_pc"] = dv(a["EI"] * 10 * 100, D)                 # HD61
    x["bag_cons_pc"] = dv(a["EH"] * 10 * 100, D)                 # HD60
    x["steam_gen_pc"] = dv(a["ED"] * 1000, D)                    # GW61
    x["steam_sugar_pc"] = dv(a["GG"] * 1000, D)                  # GW62
    x["steam_net_pc"] = dv(a["EF"] * 1000, D)                    # HL23
    x["bag_saved_pc2"] = dv(a["EI"] * 1000, D)                   # GW63
    x["fuel_ratio"] = dv(a["ED"], a["EH"])                       # GW64 (EG)
    x["pow_in"] = a["EU"] + a["EX"]                              # GW56
    x["pow_used"] = a["EV"] + a["EW"]                            # GW57
    x["pow_per_tc"] = dv((a["EZ"] + x["pow_used"]) * 10, D)      # GW60
    x["pow_sugar_tc"] = dv(a["EW"] * 10, D)                      # GW65
    x["pow_aux_tc"] = dv((a["EV"] + a["EZ"]) * 10, D)            # GW66
    x["pow_aux_pct"] = dv(a["EV"] * 100, a["EU"])                # GW67
    x["pow_export_mwh"] = a["EY"] / 1000                         # GP21

    # --- cane receipt
    x["DX"] = a["DU"] + a["DV"] + a["DW"]
    x["DZ"] = x["DX"] + a["DY"]
    x["early_pct"], x["gen_pct"] = dv(a["DU"] * 100, x["DZ"]), dv(a["DV"] * 100, x["DZ"])
    x["rej_burnt_pct"] = dv((a["DW"] + a["DY"]) * 100, x["DZ"])

    # --- imbibition
    x["imb_diff"] = x["imb"] - IMB_NORM                          # GR60
    x["imb_tph"] = dv(a["E"], 240) if is_day else None           # GR59 = E/10/24

    # --- purity control (HE col of the day block)
    pt = {lab: _pty(_val(a, x, bx), _val(a, x, pol)) for lab, bx, pol in PROCESS_ROWS}
    x["pj_mj"] = pt["Primary Juice"] - pt["Mixed Juice"]                       # GN57
    x["mj_cj"] = pt["Clear Juice"] - pt["Mixed Juice"]                         # GN59
    x["cj_us"] = pt["Unsulphured Syrup"] - pt["Clear Juice"]                   # GN61
    x["us_ss"] = pt["Sulphured Syrup"] - pt["Unsulphured Syrup"]               # GN63
    x["mj_sj"] = pt["Sulphited Juice"] - pt["Mixed Juice"]                     # GN65
    x["a_mass_bx"], x["a_mass_pty"] = a["v_ao2_massecuite_bx"], pt["A-Massecuite"]   # GN67, GN69
    x["syrup_bx_u"], x["bh_bx"] = a["v_syrup_bx_un"], x["fm_bx"]               # GN70, GN71
    x["al_pty"] = pt["A-Light Molasses"]                                       # GN72

    # --- time account
    x["avail_hrs"] = a["AU"] + a["AV"]                                         # HK63
    for k, n in (("AN", "mech"), ("AO", "elec"), ("AP", "manuf"), ("AQ", "cane"),
                 ("AR", "sched"), ("AS", "grow"), ("AT", "pwr"), ("AU", "total")):
        x["t_" + n] = dv(a[k] * 100, x["avail_hrs"])
    return x


def _val(a, x, key):
    return x[key[1:]] if key.startswith("@") else a["v_" + key]


# --------------------------------------------------------------------------------------
# REPORT LAYOUT   (label, unit, key, decimals)
# --------------------------------------------------------------------------------------
SECTIONS = [
    ("Crushing & Production", [
        ("Cane crushed", "Qtls", "D", 0),
        ("Av. crush / day incl. stoppage", "Qtls", "crush_incl", 0),
        ("Av. crush / day excl. stoppage", "Qtls", "crush_excl", 0),
        ("Capacity utilisation - gross", "%", "cap_gross", 2),
        ("Capacity utilisation - net", "%", "cap_net", 2),
        ("Mixed juice (net)", "Qtls", "BL", 0),
        ("Bagasse", "Qtls", "BF", 0),
        ("Filter cake", "Qtls", "F", 0),
        ("CH molasses input", "Qtls", "BS", 0),
        ("CH molasses output", "Qtls", "G", 0),
        ("Sugar production", "Qtls", "sugar", 0),
        ("Sugar output % cane", "%", "sugar_out", 3),
        ("Available sugar (from cane)", "Qtls", "BY", 0),
        ("Sugar in process", "Qtls", "sugar_proc", 0),
    ]),
    ("Sugar Grades", [
        ("L-31", "Qtls", "l31", 1), ("M-30", "Qtls", "m30", 1),
        ("M-31", "Qtls", "m31", 1), ("S-31", "Qtls", "s31", 1),
        ("L-31 % production", "%", "l31_pct", 2), ("M-30 % production", "%", "m30_pct", 2),
        ("M-31 % production", "%", "m31_pct", 2), ("S-31 % production", "%", "s31_pct", 2),
    ]),
    ("Control Figures (% cane)", [
        ("Non-sugar in cane", "%", "ns_cane", 2),
        ("Pol in cane", "%", "pol_cane", 2),
        ("Recovery (estd.)", "%", "rec", 3),
        ("Total losses", "%", "tot_loss", 3),
        ("Loss in bagasse", "%", "loss_bag", 3),
        ("Loss in filter cake", "%", "loss_pc", 3),
        ("Loss in final molasses", "%", "loss_mol", 3),
        ("Unknown losses", "%", "unk", 3),
        ("Fibre in cane", "%", "fibre", 2),
        ("Dry mill factor", "%", "dry_mill", 2),
        ("Mixed juice", "%", "mj_pc", 2),
        ("Imbibition", "%", "imb", 2),
        ("Bagasse", "%", "bag_pc", 2),
        ("Filter cake", "%", "fc_pc", 2),
        ("CH molasses input", "%", "mol_in_pc", 2),
        ("CH molasses output", "%", "mol_out_pc", 2),
        ("Mill extraction", "%", "mill_ext", 2),
        ("Reduced mill extraction (Deerr)", "%", "rme", 2),
        ("Java ratio", "%", "java", 2),
        ("Added water % fibre", "%", "add_water_fibre", 2),
        ("Boiling house recovery", "%", "bhr", 2),
        ("Virtual purity of final molasses", "%", "vp_fm", 2),
        ("Reduced B.H.R.", "%", "rbhr", 2),
        ("Overall recovery", "%", "overall_rec", 2),
        ("Reduced overall recovery", "%", "reduced_overall", 2),
        ("Imbibition - norm difference", "%", "imb_diff", 2),
        ("Imbibition water", "TPH", "imb_tph", 2),
    ]),
    ("Bagasse / Filter Cake / Molasses", [
        ("Pol % bagasse", "%", "bag_pol", 2),
        ("Moisture % bagasse", "%", "bag_moist", 2),
        ("Fibre % bagasse", "%", "bag_fibre", 2),
        ("Milling loss", "%", "mill_loss", 2),
        ("Pol % filter cake", "%", "pc_pol", 2),
        ("Final molasses Brix", "", "fm_bx", 2),
        ("Final molasses Pol", "", "fm_pol", 2),
        ("Theoretical molasses", "Qtls", "CF", 0),
    ]),
    ("Stoppages / Time Account", [
        ("Mechanical (engineering)", "Hrs", "AN", 2),
        ("Electrical & Instrument", "Hrs", "AO", 2),
        ("Manufacturing", "Hrs", "AP", 2),
        ("Cane", "Hrs", "AQ", 2),
        ("Schedule stoppage", "Hrs", "AR", 2),
        ("Misc. + growers problem", "Hrs", "AS", 2),
        ("Power plant", "Hrs", "AT", 2),
        ("Total stoppage", "Hrs", "AU", 2),
        ("Worked hours", "Hrs", "AV", 2),
        ("Gross hours", "Hrs", "AW", 2),
        ("Down time", "Hrs", "down_time", 2),
        ("Stoppage % gross hours", "%", "stp_pct", 2),
    ]),
    ("Steam & Cogeneration", [
        ("Steam generated", "Ton", "ED", 1),
        ("Steam condensate", "Ton", "EE", 1),
        ("Steam consumption", "Ton", "EF", 1),
        ("Steam generated % cane", "%", "steam_gen_pc", 2),
        ("Steam consumption (sugar) % cane", "%", "steam_sugar_pc", 2),
        ("Steam consumption (net) % cane", "%", "steam_net_pc", 2),
        ("Steam : fuel ratio", "", "fuel_ratio", 2),
        ("Bagasse consumed", "Ton", "EH", 1),
        ("Bagasse consumed % cane", "%", "bag_cons_pc", 2),
        ("Bagasse saved", "Ton", "EI", 1),
        ("Bagasse saved % cane", "%", "bag_save_pc", 2),
        ("Bagasse sale", "MT", "EJ", 1),
    ]),
    ("Power", [
        ("Power generation + import", "KWH", "pow_in", 0),
        ("Power generation", "KWH", "EU", 0),
        ("Power import", "KWH", "EX", 0),
        ("Power consumed (aux + sugar)", "KWH", "pow_used", 0),
        ("  - Auxiliary", "KWH", "EV", 0),
        ("  - Sugar", "KWH", "EW", 0),
        ("Biofuel use", "KWH", "EZ", 0),
        ("Power export", "KWH", "EY", 0),
        ("Power export", "MWH", "pow_export_mwh", 2),
        ("Power consumed / ton cane", "KWH", "pow_per_tc", 2),
        ("Power consumed (sugar) / ton cane", "KWH", "pow_sugar_tc", 2),
        ("Aux. + biofuel / ton cane", "KWH", "pow_aux_tc", 2),
        ("Aux. consumption % generation", "%", "pow_aux_pct", 2),
    ]),
    ("Cane Receipt", [
        ("Early variety", "Qtls", "DU", 0), ("General variety", "Qtls", "DV", 0),
        ("Reject cane", "Qtls", "DW", 0), ("Cane receipt at gate", "Qtls", "DX", 0),
        ("Burnt cane", "Qtls", "DY", 0), ("Total cane", "Qtls", "DZ", 0),
        ("Early variety % cane", "%", "early_pct", 2), ("General variety % cane", "%", "gen_pct", 2),
        ("Reject + burnt % cane", "%", "rej_burnt_pct", 2),
    ]),
    ("Process Control (purity differences / ranges)", [
        ("Purity: Primary juice -> Mixed juice (1.10 to 1.40)", "", "pj_mj", 2),
        ("Purity: Mixed juice -> Clear juice (-0.10 to +0.10)", "", "mj_cj", 2),
        ("Purity: Clear juice -> Unsulphured syrup (0.30 to 0.40)", "", "cj_us", 2),
        ("Purity: Unsulphured -> Sulphured syrup", "", "us_ss", 2),
        ("Purity: Mixed juice -> Sulphited juice (0.80 to 1.75)", "", "mj_sj", 2),
        ("A-Massecuite Brix (91.0 to 94.0)", "", "a_mass_bx", 2),
        ("A-Massecuite purity (90 +)", "", "a_mass_pty", 2),
        ("Unsulphured syrup Brix (65.0 to 68.0)", "", "syrup_bx_u", 2),
        ("BH / final molasses Brix (88 to 93)", "", "bh_bx", 2),
        ("A-Light molasses purity (88 to 92)", "", "al_pty", 2),
    ]),
]


def _chem_sections(avail_fields, x_list):
    rows = []
    for label, unit, f in CHEMICALS:
        if f in avail_fields:
            rows.append((label, unit, "chem_" + f, 2))
            rows.append((label + " % cane", "%", "chem_pc_" + f, 4))
    return rows


# --------------------------------------------------------------------------------------
# DATA ACCESS
# --------------------------------------------------------------------------------------
def _fetch(doctype, date_field, company, plant, d_from, d_to):
    cond = ["`%s` between %%(f)s and %%(t)s" % date_field, "docstatus < 2"]
    vals = {"f": d_from, "t": d_to}
    if company:
        cond.append("company = %(c)s")
        vals["c"] = company
    if plant:
        cond.append("plant = %(p)s")
        vals["p"] = plant
    return frappe.db.sql("select * from `tab%s` where %s" % (doctype, " and ".join(cond)),
                         vals, as_dict=True)


def _season_start(company, plant, to_date):
    cond, vals = ["`date` <= %(t)s", "crop_day = 1"], {"t": to_date}
    if company:
        cond.append("company = %(c)s"); vals["c"] = company
    if plant:
        cond.append("plant = %(p)s"); vals["p"] = plant
    r = frappe.db.sql("select max(`date`) from `tabSugar Process Data` where " + " and ".join(cond), vals)
    if r and r[0][0]:
        return getdate(r[0][0])
    y = to_date.year if to_date.month >= 7 else to_date.year - 1
    return _date(y, 10, 1)


def _season_label(d):
    y = d.year if d.month >= 7 else d.year - 1
    return "SEASON %s-%s" % (y, y + 1)


def _fmt(v):
    return None if v is None else round(flt(v), 6)


def _season_setting(company, plant, to_date):
    """Season Start / Period From are set once per plant per season in 'Sugar DMR Season'.
    Returns the setting of the latest season that started on or before the report date."""
    if not (company and plant) or not frappe.db.exists("DocType", "Sugar DMR Season"):
        return None
    rows = frappe.db.sql(
        """select name, season_from, period_from from `tabSugar DMR Season`
           where company = %(c)s and plant = %(p)s and season_from <= %(t)s
           order by season_from desc limit 1""",
        {"c": company, "p": plant, "t": to_date}, as_dict=True)
    return rows[0] if rows else None


@frappe.whitelist()
def get_season_setting(company=None, plant=None, date=None):
    """Used by the page to show the fixed Season Start / Period From of the chosen plant."""
    company, plant, date = _arg(company), _arg(plant), _arg(date)
    if not (company and plant and date):
        return None
    st = _season_setting(company, plant, getdate(date))
    if not st:
        return None
    return {"season_from": str(st.season_from), "period_from": str(st.period_from)}


@frappe.whitelist()
def plant_query(doctype, txt, searchfield, start, page_len, filters):
    """Link query for Plant (Branch): only plants of the selected company."""
    company = _arg((filters or {}).get("company") if isinstance(filters, dict) else None)
    like, start, page_len = "%%%s%%" % (txt or ""), cint(start), cint(page_len) or 20
    if company and frappe.get_meta("Branch").has_field("company"):
        return frappe.db.sql(
            """select name from `tabBranch` where company = %(c)s and name like %(t)s
               order by name limit %(s)s, %(l)s""",
            {"c": company, "t": like, "s": start, "l": page_len})
    if company:   # Branch has no company field: use the plants that have process data for the company
        return frappe.db.sql(
            """select distinct plant from `tabSugar Process Data`
               where company = %(c)s and ifnull(plant, '') != '' and plant like %(t)s
               order by plant limit %(s)s, %(l)s""",
            {"c": company, "t": like, "s": start, "l": page_len})
    return frappe.db.sql(
        "select name from `tabBranch` where name like %(t)s order by name limit %(s)s, %(l)s",
        {"t": like, "s": start, "l": page_len})


def _arg(v):
    """open_url_post sends empty JS fields as the text 'undefined' / 'null' - treat them as blank."""
    return None if v in (None, "", "undefined", "null", "None") else v


def _build(company, plant, date):
    frappe.has_permission(SPD, "read", throw=True)
    company, plant, date = _arg(company), _arg(plant), _arg(date)
    if not date:
        frappe.throw("Date is required")
    if not plant:
        frappe.throw("Plant is required")
    to = getdate(date)
    setting = _season_setting(company, plant, to)
    if setting:                                   # fixed once per plant per season
        sf = getdate(setting.season_from)
        pf = min(max(getdate(setting.period_from), sf), to)
    else:                                         # no setup yet: derive from the data
        sf = _season_start(company, plant, to)
        pf = max(get_first_day(to), sf)

    s_rows = _fetch(SPD, "date", company, plant, sf, to)
    p_rows = _fetch(STP, "posting_date", company, plant, sf, to)
    m_rows = _fetch(STM, "posting_date", company, plant, sf, to)

    S = {(r.plant, getdate(r.date)): r for r in s_rows}
    P = {(r.plant, getdate(r.posting_date)): r for r in p_rows}
    M = {(r.plant, getdate(r.posting_date)): r for r in m_rows}

    by_date = {}
    for key in set(S) | set(P) | set(M):
        d = calc_day(S.get(key), P.get(key), M.get(key))
        d["_date"] = key[1]
        by_date.setdefault(key[1], []).append(d)

    def between(a, b):
        return [d for dt, ds in by_date.items() if a <= dt <= b for d in ds]

    aggs = [aggregate(between(to, to)), aggregate(between(pf, to)), aggregate(between(sf, to))]

    # optional chemical fields present on the DocType?
    first = (s_rows or [{}])[0]
    avail = {f for _, _, f in CHEMICALS if f in first}
    xs = []
    for i, a in enumerate(aggs):
        x = metrics(a, is_day=(i == 0))
        for f in avail:
            x["chem_pc_" + f] = (a["chem_" + f] * 100 / a["D"]) if a["D"] else 0
        xs.append(x)

    sections = []
    layout = list(SECTIONS)
    if avail:
        layout.append(("Chemical Consumption", _chem_sections(avail, xs)))
    for title, rows in layout:
        out = []
        for label, unit, key, dp in rows:
            out.append({"label": label, "unit": unit, "dp": dp,
                        "values": [_fmt(x.get(key)) for x in xs],
                        "target": TARGETS.get(key)})
        sections.append({"title": title, "type": "table", "rows": out})

    # process analysis (Brix / Pol / Pty) block - first section, so the page chips,
    # the Excel and the PDF all list it on top
    proc = []
    for label, bx, pol in PROCESS_ROWS:
        cols = []
        for a, x in zip(aggs, xs):
            b, p_ = _val(a, x, bx), _val(a, x, pol)
            cols.append({"bx": _fmt(b), "pol": _fmt(p_), "pty": _fmt(_pty(b, p_))})
        proc.append({"label": label, "cols": cols})
    sections.insert(0, {"title": "Process Analysis (Brix / Pol / Purity)", "type": "process", "rows": proc})

    crop = [flt(r.crop_day) for r in s_rows if getdate(r.date) == to and r.crop_day]
    return {
        "meta": {
            "company": company, "plant": plant, "date": str(to), "period_from": str(pf),
            "season_from": str(sf), "season": _season_label(sf),
            "crop_day": int(max(crop)) if crop else (to - sf).days + 1,
            "has_data": bool(aggs[0]["D"]),
            "season_setup": bool(setting),
        },
        "sections": sections,
    }


# --------------------------------------------------------------------------------------
# EXPORT HELPERS  (shared by Excel and PDF)
# --------------------------------------------------------------------------------------
def _find_row(rep, label):
    for s in rep["sections"]:
        if s["type"] == "process":
            continue
        for r in s["rows"]:
            if r["label"] == label:
                return r
    return None


def _kpi_rows(rep):
    out = []
    for title, label in KPIS:
        r = _find_row(rep, label)
        if r:
            out.append((title, r))
    return out


def _kpi_section(rep):
    rows = [dict(r, label=t) for t, r in _kpi_rows(rep)]
    return {"title": "Headline Figures", "type": "table", "rows": rows, "keep": True}


def _z(v):
    return v is None or v == "" or v == 0


def _row_empty(r):
    if "values" in r:
        return all(_z(v) for v in r["values"])
    if "cols" in r:
        return all(_z(c["bx"]) and _z(c["pol"]) for c in r["cols"])
    return False


def _visible_rows(sec, with_empty):
    """Same rule as the page: empty rows are hidden unless 'Show empty rows' is on."""
    if with_empty or sec.get("keep"):
        return sec["rows"]
    return [r for r in sec["rows"] if not _row_empty(r)]


class _Num:
    """Number formatting that follows the site's number format (e.g. Indian 16,65,550.00)."""

    def __init__(self):
        fmt = frappe.db.get_default("number_format") or "#,###.##"
        try:
            from frappe.utils.data import get_number_format_info
            dec, com, _ = get_number_format_info(fmt)
        except Exception:
            dec, com = ".", ","
        self.dec, self.com = dec or ".", com
        self.indian = "#,##,###" in fmt

    def _group(self, ip):
        if not self.com:
            return ip
        parts = []
        if self.indian and len(ip) > 3:
            tail, head = ip[-3:], ip[:-3]
            while len(head) > 2:
                parts.insert(0, head[-2:])
                head = head[:-2]
            if head:
                parts.insert(0, head)
            return self.com.join(parts + [tail])
        while len(ip) > 3:
            parts.insert(0, ip[-3:])
            ip = ip[:-3]
        parts.insert(0, ip)
        return self.com.join(parts)

    def __call__(self, v, dp=2, signed=False):
        if v is None or v == "":
            return ""
        if isinstance(v, str):
            return v
        if signed:
            if round(abs(v), dp) == 0:
                return "\u2013"
        elif v == 0:
            return "\u2013"
        s = "%.*f" % (dp, abs(v))
        ip, _, fp = s.partition(".")
        out = self._group(ip) + ((self.dec + fp) if dp else "")
        if v < 0:
            return "-" + out
        return ("+" + out) if signed else out


def _target_text(r, num):
    t = r.get("target")
    if t is None:
        return ""
    if isinstance(t, (int, float)):
        d = (r.get("values") or [None])[0]
        diff = num(d - t, r.get("dp", 2), signed=True) if d is not None else ""
        return "Target %s%s" % (num(t, r.get("dp", 2)), " (%s)" % diff if diff else "")
    return "Target %s" % t


# --------------------------------------------------------------------------------------
# WHITELISTED API
# --------------------------------------------------------------------------------------
@frappe.whitelist()
def get_dmr_data(company=None, plant=None, date=None):
    if not date:
        frappe.throw("Date is required")
    return _build(company, plant, date)


# ----------------------------------------------------------------------------- EXCEL
@frappe.whitelist()
def export_dmr_excel(company=None, plant=None, date=None, with_empty=0):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.pagebreak import Break
    from openpyxl.worksheet.properties import PageSetupProperties

    if not date:
        frappe.throw("Date is required")
    with_empty = cint(with_empty)
    rep = _build(company, plant, date)
    m = rep["meta"]
    secs = [_kpi_section(rep)] + rep["sections"]

    wb = Workbook()
    ws = wb.active
    ws.title = "DMR Sugar"
    ws.sheet_view.showGridLines = False
    NCOL = 10                                    # A .. J

    GREEN, INK, MUTE, AMBER, MUTED_NUM = "2F6B4F", "2B3A33", "74837B", "A8691C", "A9B6AF"
    fill = lambda hx: PatternFill("solid", fgColor=hx)
    F_TINT, F_HEAD, F_HERO, F_BAND = fill("EAF5EF"), fill("F6FAF8"), fill("F1F8F4"), fill(GREEN)
    hair = Side(style="thin", color="E3EBE6")
    thin = Side(style="thin", color="C3DCCD")
    amber_line = Side(style="medium", color="E0A15A")
    box = Side(style="thin", color="C3DCCD")

    def fnt(size=10, bold=False, color=INK, italic=False):
        return Font(name="Calibri", size=size, bold=bold, color=color, italic=italic)

    def merge(row, c1, c2, value=None, font=None, align=None, fill_=None):
        if c2 > c1:
            ws.merge_cells(start_row=row, start_column=c1, end_row=row, end_column=c2)
        cell = ws.cell(row, c1, value)
        if font:
            cell.font = font
        if align:
            cell.alignment = align
        if fill_:
            for c in range(c1, c2 + 1):
                ws.cell(row, c).fill = fill_
        return cell

    def numfmt(dp):
        body = "#,##0" + (("." + "0" * dp) if dp else "")
        return '%s;-%s;"\u2013"' % (body, body)

    # ---- header block (rows 1-5)
    for rr in range(1, 6):
        for cc in range(1, NCOL + 1):
            ws.cell(rr, cc).fill = F_HERO
    org = (m["company"] or "") + (("   |   " + m["plant"]) if m["plant"] else "")
    merge(1, 1, NCOL, org, fnt(10, color=MUTE), Alignment(vertical="center", indent=1))
    merge(2, 1, NCOL, "DAILY MANUFACTURING REPORT: SUGAR", fnt(17, True, GREEN),
          Alignment(vertical="center", indent=1))
    merge(3, 1, NCOL, m["season"], fnt(10, color=MUTE), Alignment(vertical="center", indent=1))
    ws.row_dimensions[2].height = 28
    facts = [
        (1, 1, "Report date", formatdate(m["date"])),
        (2, 2, "Crop day", m["crop_day"]),
        (3, 5, "Period", "%s  to  %s" % (formatdate(m["period_from"]), formatdate(m["date"]))),
        (6, 8, "Season from", formatdate(m["season_from"])),
    ]
    for c1, c2, lab, val in facts:
        merge(4, c1, c2, lab, fnt(8.5, color=MUTE), Alignment(horizontal="left", indent=1 if c1 == 1 else 0))
        merge(5, c1, c2, val, fnt(12, True, GREEN), Alignment(horizontal="left", indent=1 if c1 == 1 else 0))
    ws.row_dimensions[5].height = 20
    for cc in range(1, NCOL + 1):
        ws.cell(5, cc).border = Border(bottom=thin)
    if not m["has_data"]:
        merge(6, 1, NCOL, "No Sugar Process Data found for this date. The Day column will be blank.",
              fnt(9.5, italic=True, color=AMBER), Alignment(indent=1))

    # ---- sections
    r = 8
    since_break = 0
    PAGE_ROWS = 44
    for sec in secs:
        rows = _visible_rows(sec, with_empty)
        proc = sec["type"] == "process"
        span = NCOL if proc else 6
        need = max(len(rows), 1) + (4 if proc else 3)
        if since_break and since_break + need > PAGE_ROWS:
            ws.row_breaks.append(Break(id=r - 1))
            since_break = 0

        merge(r, 1, span, sec["title"], fnt(11, True, "FFFFFF"),
              Alignment(vertical="center", indent=1), F_BAND)
        ws.row_dimensions[r].height = 20
        r += 1

        if proc:
            # two-row header: Particulars | Day (Brix Pol Purity) | Period | To date
            ws.merge_cells(start_row=r, start_column=1, end_row=r + 1, end_column=1)
            c = ws.cell(r, 1, "Particulars")
            c.font, c.alignment = fnt(10, True, MUTE), Alignment(horizontal="left", vertical="center", indent=1)
            for g, name in enumerate(("Day", "Period", "To date")):
                c1 = 2 + g * 3
                merge(r, c1, c1 + 2, name, fnt(10, True, GREEN if g == 0 else MUTE),
                      Alignment(horizontal="center"))
                for j, sub in enumerate(("Brix", "Pol", "Purity")):
                    cell = ws.cell(r + 1, c1 + j, sub)
                    cell.font = fnt(9.5, True, GREEN if g == 0 else MUTE)
                    cell.alignment = Alignment(horizontal="right")
            for rr in (r, r + 1):
                for cc in range(1, span + 1):
                    cell = ws.cell(rr, cc)
                    cell.fill = F_TINT if (2 <= cc <= 4) else F_HEAD
                    left = thin if cc in (2, 5, 8) else None
                    bottom = (amber_line if (2 <= cc <= 4) else thin) if rr == r + 1 else None
                    cell.border = Border(left=left, bottom=bottom)
            r += 2
            for row in rows:
                ca = ws.cell(r, 1, row["label"])
                ca.font, ca.alignment = fnt(10), Alignment(horizontal="left", indent=1)
                for i, col in enumerate(row["cols"]):
                    for j, key in enumerate(("bx", "pol", "pty")):
                        v = col[key]
                        cell = ws.cell(r, 2 + i * 3 + j, v)
                        cell.number_format = numfmt(2)
                        cell.alignment = Alignment(horizontal="right")
                        zero = _z(v)
                        cell.font = fnt(10, bold=(key == "pty" or i == 0) and not zero,
                                        color=MUTED_NUM if zero else (GREEN if i == 0 else INK))
                        if i == 0:
                            cell.fill = F_TINT
                for cc in range(1, span + 1):
                    ws.cell(r, cc).border = Border(bottom=hair, left=thin if cc in (2, 5, 8) else None)
                r += 1
        else:
            heads = ["Particulars", "Unit", "Day", "Period", "To Date", "Target"]
            for cc, name in enumerate(heads, 1):
                cell = ws.cell(r, cc, name)
                day = cc == 3
                cell.font = fnt(10, True, GREEN if day else MUTE)
                cell.fill = F_TINT if day else F_HEAD
                cell.alignment = Alignment(horizontal="left" if cc == 1 else ("center" if cc == 2 else "right"),
                                           indent=1 if cc == 1 else 0)
                cell.border = Border(bottom=amber_line if day else thin)
            r += 1
            if not rows:
                merge(r, 1, span, "No values for this date", fnt(10, italic=True, color=MUTE),
                      Alignment(horizontal="center"))
                r += 1
            for row in rows:
                label = row["label"]
                sub = label.startswith(" ")
                ca = ws.cell(r, 1, label.strip())
                ca.font = fnt(10)
                ca.alignment = Alignment(horizontal="left", indent=3 if sub else 1, wrap_text=True, vertical="center")
                cu = ws.cell(r, 2, row.get("unit") or "")
                cu.font, cu.alignment = fnt(9, color=MUTE), Alignment(horizontal="center")
                for i, v in enumerate(row["values"]):
                    cell = ws.cell(r, 3 + i, v)
                    cell.number_format = numfmt(row.get("dp", 2))
                    cell.alignment = Alignment(horizontal="right")
                    zero = _z(v)
                    if i == 0:
                        cell.fill = F_TINT
                        cell.font = fnt(10, bold=not zero, color=MUTED_NUM if zero else GREEN)
                    else:
                        cell.font = fnt(10, color=MUTED_NUM if zero else INK)
                t = row.get("target")
                ct = ws.cell(r, 6, t)
                ct.font = fnt(9, italic=True, color=AMBER)
                ct.alignment = Alignment(horizontal="right")
                if isinstance(t, (int, float)):
                    ct.number_format = numfmt(row.get("dp", 2))
                for cc in range(1, span + 1):
                    ws.cell(r, cc).border = Border(bottom=hair)
                r += 1
        # closing rule + spacer
        for cc in range(1, span + 1):
            b = ws.cell(r - 1, cc).border
            ws.cell(r - 1, cc).border = Border(left=b.left, bottom=thin)
        since_break += need + 1
        r += 1

    # ---- columns, print setup
    ws.column_dimensions["A"].width = 46
    for cc in range(2, NCOL + 1):
        ws.column_dimensions[get_column_letter(cc)].width = 12.5
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = 9                                  # A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    ws.page_margins.left = ws.page_margins.right = 0.4
    ws.page_margins.top, ws.page_margins.bottom = 0.5, 0.6
    ws.print_options.horizontalCentered = True
    ws.oddFooter.left.text = "DMR Sugar - " + formatdate(m["date"])
    ws.oddFooter.right.text = "Page &P of &N"
    ws.oddFooter.left.size = ws.oddFooter.right.size = 8

    buf = io.BytesIO()
    wb.save(buf)
    frappe.response["filename"] = "DMR_Sugar_%s.xlsx" % m["date"]
    frappe.response["filecontent"] = buf.getvalue()
    frappe.response["type"] = "binary"


# ------------------------------------------------------------------------------- PDF
_PDF_CSS = """
body { font-family: Arial, Helvetica, sans-serif; font-size: 7.5pt; color: #2b3a33; margin: 0; }
table { border-collapse: collapse; }
.hero { width: 100%; background: #f1f8f4; border: 1px solid #d9eadf; }
.hero td { padding: 8px 12px; vertical-align: bottom; }
.hero td.hr { text-align: right; }
.org { font-size: 8pt; color: #74837b; }
.plant { border: 1px solid #c3dccd; background: #ffffff; color: #2f6b4f; padding: 0 6px; margin-left: 8px; }
.h1 { font-size: 15pt; font-weight: bold; color: #2f6b4f; margin: 3px 0 1px 0; }
.season { font-size: 8pt; color: #74837b; }
.facts td { padding: 0 0 0 18px; text-align: left; }
.fl { font-size: 6.5pt; color: #74837b; }
.fv { font-size: 8.5pt; }
.fv.big { font-size: 14pt; font-weight: bold; color: #2f6b4f; }
.warn { margin-top: 6px; padding: 5px 10px; border: 1px solid #f0d9a4; background: #fff8e6; font-size: 7.5pt; }
.kpis { width: 100%; border-collapse: separate; border-spacing: 5px 0; margin: 7px 0 8px 0; }
.kpis td { width: 16.6%; border: 1px solid #e3ebe6; padding: 5px 8px; vertical-align: top; }
.kl { font-size: 7pt; color: #74837b; }
.kv { font-size: 13pt; font-weight: bold; color: #2f6b4f; margin: 1px 0 2px 0; }
.kv.z { color: #74837b; font-weight: normal; }
.ku { font-size: 7pt; font-weight: normal; color: #74837b; margin-left: 3px; }
.ks { font-size: 6.5pt; color: #74837b; }
.ks b { color: #2b3a33; }
.card { width: 100%; border: 1px solid #e3ebe6; margin-bottom: 7px; page-break-inside: avoid; }
.card td.ch { background: #f6faf8; color: #2f6b4f; font-weight: bold; font-size: 8pt; padding: 4px 7px; border-bottom: 1px solid #e3ebe6; }
.card th { font-size: 6.5pt; color: #74837b; text-align: right; padding: 3px 4px; border-bottom: 1px solid #e3ebe6; }
.card th.lbl { text-align: left; padding-left: 7px; }
.card th.day { background: #eaf5ef; color: #2f6b4f; border-bottom: 2px solid #e0a15a; }
.card th.grp { text-align: center; border-left: 1px solid #e3ebe6; }
.card td { padding: 2px 4px; border-bottom: 1px solid #eef3f0; }
.card td.lbl { text-align: left; padding-left: 7px; }
.card td.sub { padding-left: 16px; }
.card td.u { text-align: center; color: #74837b; font-size: 6.5pt; }
.card td.n { text-align: right; white-space: nowrap; }
.card td.day { background: #eaf5ef; font-weight: bold; color: #2f6b4f; }
.card td.z { color: #a9b6af; }
.card td.day.z { font-weight: normal; }
.card td.gs, .card th.gs { border-left: 1px solid #e3ebe6; }
.card td.pty { font-weight: bold; }
.card td.none { text-align: center; color: #74837b; padding: 6px; }
.tgt { font-size: 6pt; color: #a8691c; }
.cols { width: 100%; }
.cols td.col { width: 33.3%; vertical-align: top; padding: 0 3px; }
.pb { page-break-before: always; }
"""


def _pdf_td(num, v, dp, cls=""):
    z = " z" if _z(v) else ""
    return '<td class="n %s%s">%s</td>' % (cls, z, num(v, dp))


def _pdf_card(sec, with_empty, num):
    e = escape_html
    rows = _visible_rows(sec, with_empty)
    if sec["type"] == "process":
        h = ['<table class="card" cellspacing="0" cellpadding="0">',
             '<tr><td class="ch" colspan="10">%s</td></tr>' % e(sec["title"]),
             '<tr><th class="lbl" rowspan="2" style="width:22%">Particulars</th>'
             '<th colspan="3" class="grp day">Day</th><th colspan="3" class="grp">Period</th>'
             '<th colspan="3" class="grp">To date</th></tr>', "<tr>"]
        for g in range(3):
            for j, sub in enumerate(("Brix", "Pol", "Purity")):
                h.append('<th class="%s%s">%s</th>' % ("day " if g == 0 else "", "gs" if j == 0 else "", sub))
        h.append("</tr>")
        for r in rows:
            h.append('<tr><td class="lbl">%s</td>' % e(r["label"]))
            for i, c in enumerate(r["cols"]):
                cl = "day" if i == 0 else ""
                h.append(_pdf_td(num, c["bx"], 2, cl + " gs"))
                h.append(_pdf_td(num, c["pol"], 2, cl))
                h.append(_pdf_td(num, c["pty"], 2, cl + " pty"))
            h.append("</tr>")
        if not rows:
            h.append('<tr><td class="none" colspan="10">No values for this date</td></tr>')
        h.append("</table>")
        return "".join(h)

    h = ['<table class="card" cellspacing="0" cellpadding="0">',
         '<tr><td class="ch" colspan="5">%s</td></tr>' % e(sec["title"]),
         '<tr><th class="lbl">Particulars</th><th style="width:7%"></th>'
         '<th class="day" style="width:17%">Day</th><th style="width:17%">Period</th>'
         '<th style="width:18%">To date</th></tr>']
    for r in rows:
        dp = r.get("dp", 2)
        d, p, t = r["values"]
        sub = r["label"].startswith(" ")
        tgt = _target_text(r, num)
        h.append('<tr><td class="lbl%s">%s%s</td><td class="u">%s</td>%s%s%s</tr>' % (
            " sub" if sub else "", e(r["label"].strip()),
            ('<div class="tgt">%s</div>' % e(tgt)) if tgt else "",
            e(r.get("unit") or ""),
            _pdf_td(num, d, dp, "day"), _pdf_td(num, p, dp), _pdf_td(num, t, dp)))
    if not rows:
        h.append('<tr><td class="none" colspan="5">No values for this date</td></tr>')
    h.append("</table>")
    return "".join(h)


def _pdf_html(rep, with_empty):
    e = escape_html
    num = _Num()
    m = rep["meta"]
    wide = [s for s in rep["sections"] if s["type"] == "process"]
    cards = [s for s in rep["sections"] if s["type"] != "process"]

    h = ['<html><head><meta charset="utf-8"><style>%s</style></head><body>' % _PDF_CSS]
    h.append(
        '<table class="hero" cellspacing="0" cellpadding="0"><tr><td>'
        '<div class="org">%s%s</div><div class="h1">Daily Manufacturing Report: Sugar</div>'
        '<div class="season">%s</div></td><td class="hr">'
        '<table class="facts" align="right" cellspacing="0" cellpadding="0"><tr>'
        '<td><div class="fl">Report date</div><div class="fv big">%s</div></td>'
        '<td><div class="fl">Crop day</div><div class="fv big">%s</div></td>'
        '<td><div class="fl">Period</div><div class="fv">%s to %s</div></td>'
        '<td><div class="fl">Season from</div><div class="fv">%s</div></td>'
        '</tr></table></td></tr></table>' % (
            e(m["company"] or ""), ('<span class="plant">%s</span>' % e(m["plant"])) if m["plant"] else "",
            e(m["season"]), formatdate(m["date"]), m["crop_day"],
            formatdate(m["period_from"]), formatdate(m["date"]), formatdate(m["season_from"])))
    if not m["has_data"]:
        h.append('<div class="warn">No Sugar Process Data found for this date. The Day column will be blank.</div>')

    kp = _kpi_rows(rep)
    if kp:
        h.append('<table class="kpis"><tr>')
        for title, r in kp:
            dp = r.get("dp", 2)
            d, p, t = r["values"]
            h.append('<td><div class="kl">%s</div><div class="kv%s">%s<span class="ku">%s</span></div>'
                     '<div class="ks">Period <b>%s</b> &nbsp; Season <b>%s</b></div></td>' % (
                         e(title), "" if d else " z", num(d, dp) or "\u2013", e(r.get("unit") or ""),
                         num(p, dp) or "\u2013", num(t, dp) or "\u2013"))
        h.append("</tr></table>")

    for s in wide:                                   # Process Analysis, full width, on top
        h.append(_pdf_card(s, with_empty, num))

    if cards:                                        # page 2: ordinary cards in 3 balanced columns
        cols, heights = [[], [], []], [0, 0, 0]
        for s in cards:
            i = heights.index(min(heights))
            cols[i].append(s)
            heights[i] += len(_visible_rows(s, with_empty)) + 3
        h.append('<div class="pb"></div><table class="cols" cellspacing="0" cellpadding="0"><tr>')
        for col in cols:
            h.append('<td class="col">%s</td>' % "".join(_pdf_card(s, with_empty, num) for s in col))
        h.append("</tr></table>")
    h.append("</body></html>")
    return "".join(h)


@frappe.whitelist()
def export_dmr_pdf(company=None, plant=None, date=None, with_empty=0):
    from frappe.utils.pdf import get_pdf

    if not date:
        frappe.throw("Date is required")
    rep = _build(company, plant, date)
    html = _pdf_html(rep, cint(with_empty))
    pdf = get_pdf(html, {
        "orientation": "Landscape",
        "page-size": "A4",
        "margin-top": "8mm", "margin-bottom": "10mm",
        "margin-left": "8mm", "margin-right": "8mm",
        "footer-right": "Page [page] of [topage]",
        "footer-font-size": "7",
    })
    frappe.response["filename"] = "DMR_Sugar_%s.pdf" % rep["meta"]["date"]
    frappe.response["filecontent"] = pdf
    frappe.response["type"] = "pdf"