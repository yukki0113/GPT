"""JPDB P3 rider/venue effect stability: exploratory market-residual contrasts.

Consumes the P3 runner's race-complete, D-exclusive p3_eval relation.
Within each year and surface, compare a rider's venue residual against the
same rider's *other* venues, not against aggregate raw win rates.
Nominal normal approximations and BH q-values are DIAGNOSTIC only: final odds
are retrospective, independent-race/model-calibration assumptions unverified.
No individual rider capability label or forecast use is authorized.
"""
from __future__ import annotations
import math
from statistics import mean


def evaluate(db, min_cell_n: int = 30, min_peer_n: int = 30) -> dict:
    if min_cell_n < 1 or min_peer_n < 1:
        raise ValueError("minimum count must be positive")
    rows=db.execute("""SELECT event_year,jockey_code,surface_code,venue_code,
      COUNT(*) AS n,SUM(win-market_p) AS residual,
      SUM(market_p*(1-market_p)) AS market_variance
      FROM p3_eval GROUP BY 1,2,3,4""").fetchall()
    totals={}
    for year,code,surface,venue,n,res,var in rows:
        key=year,code,surface
        old=totals.get(key,(0,0.0,0.0))
        totals[key]=(old[0]+n,old[1]+res,old[2]+var)
    cells=[]
    for year,code,surface,venue,n,res,var in rows:
        total_n,total_res,total_var=totals[year,code,surface]
        peer_n=total_n-n
        if n<min_cell_n or peer_n<min_peer_n:
            continue
        peer_res=total_res-res
        peer_var=max(0,total_var-var)
        effect=100*(res/n-peer_res/peer_n)
        sd=100*math.sqrt(max(0,var)/n**2+peer_var/peer_n**2)
        z=effect/sd if sd>0 else None
        p=math.erfc(abs(z)/math.sqrt(2)) if z is not None else 1.0
        cells.append({
            "year":year,"jockey_code":code,"surface":surface,"venue":venue,
            "n":n,"other_venue_n":peer_n,
            "residual_vs_other_venues_per100":effect,
            "diagnostic_market_z":z,
            "uncorrected_p":p,
        })
    order=sorted(range(len(cells)),key=lambda i:cells[i]["uncorrected_p"])
    q=1.0
    for index in reversed(range(len(order))):
        item=order[index]
        raw=min(1.0,cells[item]["uncorrected_p"]*len(cells)/(index+1))
        q=min(q,raw)
        cells[item]["approx_bh_q"]=q
    byyear={}
    for cell in cells:
        byyear.setdefault(cell["year"],[]).append(cell)
    yearly=[]
    for year in sorted(byyear):
        group=byyear[year]
        yearly.append({
            "year":year,"cells":len(group),
            "nominal_p_under_005":sum(c["uncorrected_p"]<.05 for c in group),
            "approx_bh_q_under_005":sum(c["approx_bh_q"]<.05 for c in group),
        })
    keyed={(c["year"],c["jockey_code"],c["surface"],c["venue"]):
           c["residual_vs_other_venues_per100"] for c in cells}
    stability=[]
    for prior,later in (("2024","2025"),("2025","2026")):
        pairs=[(effect,keyed[(later,code,surface,venue)])
               for (year,code,surface,venue),effect in keyed.items()
               if year==prior and (later,code,surface,venue) in keyed]
        correlation=None
        if len(pairs)>1:
            xs,ys=zip(*pairs)
            mx,my=mean(xs),mean(ys)
            sx=sum((x-mx)**2 for x in xs)
            sy=sum((y-my)**2 for y in ys)
            if sx*sy>0:
                correlation=sum((x-mx)*(y-my) for x,y in pairs)/math.sqrt(sx*sy)
        stability.append({
            "from_year":prior,"to_year":later,
            "paired_rider_surface_venue_cells":len(pairs),
            "effect_correlation":None if correlation is None else round(correlation,6),
            "effect_sign_persistent":sum(x*y>0 for x,y in pairs),
            "effect_sign_reversed":sum(x*y<0 for x,y in pairs),
        })
    return {
        "research_only":True,
        "prediction_safe":False,
        "definition":"rider venue market residual/100 minus same-rider same-surface other-venues residual/100",
        "min_cell_n":min_cell_n,
        "min_same_rider_other_venue_n":min_peer_n,
        "total_approximate_tests":len(cells),
        "yearly_multiple_testing_diagnostic":yearly,
        "year_pair_condition_stability":stability,
        "p_and_bh_q_approximate_only":True,
        "market_model_correctness_and_race_independence_not_certified":True,
        "causal_skill_labels_allowed":False,
    }
