# -*- coding: utf-8 -*-
"""
Sugar DMR (Daily Manufacturing Report) - backend

Source of formulas : DMR sheet of "DMR 2025-2026 Report" Excel
                     (daily row formulas = columns A..GL, printed report = GT..GX,
                      monthly report = HJ..HT)
Data comes from    : Sugar Process Data, zzStoppages, zzSteam And Power

All maths uses the *Excel column letters* as keys (D = cane crushed, BF = bagasse qty,
BZ = recovery % cane ...) so every line can be traced back to the sheet.

Three columns are produced, exactly like the workbook:
    Day      -> the selected date                        (row 10  of the sheet)
    Period   -> Period From .. selected date             (row 8   of the sheet)
    To Date  -> Season start .. selected date            (row 7   of the sheet)

PLACE THIS FILE somewhere importable (no brackets in the path), e.g.
    <your_app>/<module>/sugar_dmr.py
and set DMR_API in dmr-(sugar).js to  "<your_app>.<module>.sugar_dmr"
"""
import io
from datetime import date as _date

import frappe
from frappe.utils import add_days, flt, get_first_day, getdate

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
        BK = C                                                   # BK = C      gross M.J. qty
        BF = D + E - BK                                          # BF          bagasse qty
        BD = (100 - T * O / P - S) if P else 0                   # BD          fibre % bagasse
        BE = BF * BD / 100                                       # BE          bagasse fibre qty
        BG = BF * S / 100                                        # BG          bagasse moisture qty
        BI = BF * T / 100                                        # BI          bagasse pol qty
        BH = BI * O / P if P else 0                              # BH          bagasse Bx qty
        BJ = H * BK / 100                                        # BJ          dirt qty
        BL = BK - BJ                                             # BL          net M.J. qty
        BM = BL * M_ / 100                                       # BM          Bx in M.J.
        BN = BL * N / 100                                        # BN          pol in M.J.
        BO = BM - BN                                             # BO          N.S. in M.J.
        BP = F * U / 100                                         # BP          press-cake pol qty
        q = (W * 100 / V) if V else 0
        BQ = q / (100 - q) if q < 100 else 0                     # BQ          molasses factor
        BW = BO - BO * I / 100                                   # BW          N.S. in final molasses
        BR = BW * BQ                                             # BR          loss in molasses
        BS = (BR + BW) * 100 / V if V else 0                     # BS          molasses input qty
        BU = V * BS / 100                                        # BU          final molasses Bx qty
        BV = BS * W / 100                                        # BV          final molasses pol qty
        BX = J * D / 100                                         # BX          unknown loss qty
        BZ = (BN - BP - BX - BR) / D * 100                       # BZ          recovery % cane
        BY = D * BZ / 100                                        # BY          available sugar qty
        CD = BN - BP                                             # CD          clear juice pol qty
        CL = (CK * 100 / CJ) if CJ else 0                        # CL          clear juice purity
        CC = CD * 100 / CL if CL else 0                          # CC          clear juice Bx qty
        CE = CC - CD                                             # CE          N.S. in clear juice
        CF = CE * 100 / (V - W) if V > W else 0                  # CF          theoretical molasses
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


def _build(company, plant, date, period_from=None, season_from=None, remarks="", note=""):
    frappe.has_permission(SPD, "read", throw=True)
    to = getdate(date)
    sf = getdate(season_from) if season_from else _season_start(company, plant, to)
    pf = max(getdate(period_from) if period_from else get_first_day(to), sf)

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

    # process analysis (Brix / Pol / Pty) block
    proc = []
    for label, bx, pol in PROCESS_ROWS:
        cols = []
        for a, x in zip(aggs, xs):
            b, p_ = _val(a, x, bx), _val(a, x, pol)
            cols.append({"bx": _fmt(b), "pol": _fmt(p_), "pty": _fmt(_pty(b, p_))})
        proc.append({"label": label, "cols": cols})
    sections.insert(3, {"title": "Process Analysis (Brix / Pol / Purity)", "type": "process", "rows": proc})

    crop = [flt(r.crop_day) for r in s_rows if getdate(r.date) == to and r.crop_day]
    return {
        "meta": {
            "company": company, "plant": plant, "date": str(to), "period_from": str(pf),
            "season_from": str(sf), "season": _season_label(sf),
            "crop_day": int(max(crop)) if crop else (to - sf).days + 1,
            "has_data": bool(aggs[0]["D"]),
            "remarks": remarks or "", "note": note or "",
        },
        "sections": sections,
    }


# --------------------------------------------------------------------------------------
# WHITELISTED API
# --------------------------------------------------------------------------------------
@frappe.whitelist()
def get_dmr_data(company=None, plant=None, date=None, period_from=None, season_from=None,
                 remarks="", note=""):
    if not date:
        frappe.throw("Date is required")
    return _build(company, plant, date, period_from, season_from, remarks, note)


@frappe.whitelist()
def export_dmr_excel(company=None, plant=None, date=None, period_from=None, season_from=None,
                     remarks="", note=""):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    rep = _build(company, plant, date, period_from, season_from, remarks, note)
    m = rep["meta"]
    wb = Workbook()
    ws = wb.active
    ws.title = "DMR Sugar"
    bold = Font(bold=True, name="Arial")
    head_fill = PatternFill("solid", fgColor="D9E1F2")

    ws.append([(company or "") + "  " + (plant or "")])
    ws.append(["DAILY MANUFACTURING REPORT - SUGAR", m["season"], "Date: " + m["date"],
               "Crop day: %s" % m["crop_day"]])
    ws.append(["Period: %s to %s" % (m["period_from"], m["date"]), "To date from: " + m["season_from"]])
    for r in (1, 2, 3):
        for c in ws[r]:
            c.font = bold
    ws.append([])

    for sec in rep["sections"]:
        ws.append([sec["title"]])
        ws.cell(ws.max_row, 1).font = bold
        if sec["type"] == "process":
            ws.append(["Particulars", "Day Bx", "Day Pol", "Day Pty", "Period Bx", "Period Pol",
                       "Period Pty", "To date Bx", "To date Pol", "To date Pty"])
            hdr = ws.max_row
            for r in sec["rows"]:
                line = [r["label"]]
                for c in r["cols"]:
                    line += [c["bx"], c["pol"], c["pty"]]
                ws.append(line)
        else:
            ws.append(["Particulars", "Unit", "Day", "Period", "To Date", "Target"])
            hdr = ws.max_row
            for r in sec["rows"]:
                ws.append([r["label"], r["unit"]] + r["values"] + [r["target"]])
        for c in ws[hdr]:
            c.font, c.fill = bold, head_fill
        ws.append([])

    if m["remarks"] or m["note"]:
        ws.append(["Remarks", m["remarks"]])
        ws.append(["Note", m["note"]])
    ws.column_dimensions["A"].width = 58
    for col in "BCDEFGHIJ":
        ws.column_dimensions[col].width = 14
    for row in ws.iter_rows(min_row=5):
        for c in row[1:]:
            if isinstance(c.value, (int, float)):
                c.number_format = "#,##0.00"
                c.alignment = Alignment(horizontal="right")

    buf = io.BytesIO()
    wb.save(buf)
    frappe.response["filename"] = "DMR_Sugar_%s.xlsx" % m["date"]
    frappe.response["filecontent"] = buf.getvalue()
    frappe.response["type"] = "binary"