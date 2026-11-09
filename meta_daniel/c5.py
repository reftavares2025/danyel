from m import *
import os
PAGE = "ID_DA_SUA_PAGINA"
estado = json.load(open("estado.json"))
if not estado.get("campanha"):
    p = dict(name="CASA COSMÓPOLIS | Compradores qualificados | 2 casas R$ 669 mil", objective="OUTCOME_TRAFFIC",
             status="PAUSED", special_ad_categories="[]", buying_type="AUCTION", is_adset_budget_sharing_enabled="false")
    r = post(f"{ACT}/campaigns", **p)
    if "error" in r and "is_adset_budget_sharing_enabled" in str(r):
        p.pop("is_adset_budget_sharing_enabled"); r = post(f"{ACT}/campaigns", **p)
    print("campanha:", r); estado["campanha"] = r.get("id")
    json.dump(estado, open("estado.json","w"), indent=1)
if estado.get("campanha") and not estado.get("conjunto"):
    targeting = {
        "geo_locations": {"custom_locations": [{"latitude": -22.6437, "longitude": -47.1972, "radius": 17, "distance_unit": "kilometer"}],
                          "location_types": ["home", "recent"]},
        "age_min": 30, "age_max": 65,
        "publisher_platforms": ["facebook", "instagram", "messenger"],
        "facebook_positions": ["feed", "story", "facebook_reels", "marketplace", "search"],
        "instagram_positions": ["stream", "story", "reels", "explore_home"],
        "messenger_positions": ["story"],
        "device_platforms": ["mobile", "desktop"],
        "targeting_automation": {"advantage_audience": 0},
    }
    r = post(f"{ACT}/adsets", name="Raio 17 km Cosmópolis | 30-65 | FB+IG+Messenger", campaign_id=estado["campanha"],
             status="PAUSED", daily_budget="1000", billing_event="IMPRESSIONS", optimization_goal="LINK_CLICKS",
             bid_strategy="LOWEST_COST_WITHOUT_CAP", destination_type="WEBSITE",
             targeting=json.dumps(targeting))
    print("conjunto:", r); estado["conjunto"] = r.get("id")
    json.dump(estado, open("estado.json","w"), indent=1)
