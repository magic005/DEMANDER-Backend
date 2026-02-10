"""
Core simulation engine — generates synthetic buyers and runs them through the decision funnel.
Uses Monte Carlo simulation to estimate demand metrics.
"""

import numpy as np
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from app.simulation.archetypes import (
    ARCHETYPES,
    ArchetypeConfig,
    select_archetypes_for_market,
    generate_buyer_budget,
)


@dataclass
class PropertyProfile:
    price: float
    beds: int
    baths: float
    sqft: float
    lot_size_sqft: Optional[float]
    property_type: str
    year_built: Optional[int]
    condition: Optional[str]
    hoa_monthly: Optional[float]
    school_rating: Optional[float]
    walk_score: Optional[int]
    fire_zone: str = "none"
    flood_zone: str = "none"
    parking: Optional[str] = None


@dataclass
class BuyerAgent:
    archetype: str
    budget: float
    school_weight: float
    commute_weight: float
    space_weight: float
    condition_weight: float
    hoa_sensitivity: float
    risk_tolerance: float


@dataclass
class SimulationResult:
    demand_score: float
    sale_probability_30: float
    sale_probability_60: float
    sale_probability_90: float
    time_to_first_offer: int
    buyer_pool_size: int
    funnel_data: List[Dict[str, Any]]
    archetype_breakdown: List[Dict[str, Any]]
    demand_blockers: List[Dict[str, Any]]
    recommendations: List[Dict[str, Any]]
    timeline_data: List[Dict[str, Any]]
    price_sensitivity: List[Dict[str, Any]]
    competitive_context: Dict[str, Any]
    simulation_runs: int


class DemandSimulator:
    def __init__(self, seed: Optional[int] = None):
        self.rng = np.random.default_rng(seed)

    def run(
        self,
        property_profile: PropertyProfile,
        num_buyers: int = 1000,
        num_simulations: int = 500,
    ) -> SimulationResult:
        # Step 1: Select archetype weights for this price point
        archetype_weights = select_archetypes_for_market(property_profile.price)

        # Step 2: Generate buyer agents
        buyers = self._generate_buyers(
            num_buyers, archetype_weights, property_profile.price
        )

        # Step 3: Run Monte Carlo — each simulation adds noise
        all_funnel_results = []
        for _ in range(num_simulations):
            funnel = self._simulate_funnel(buyers, property_profile)
            all_funnel_results.append(funnel)

        # Step 4: Aggregate results
        return self._aggregate_results(
            property_profile, buyers, all_funnel_results, archetype_weights, num_simulations
        )

    def _generate_buyers(
        self,
        num_buyers: int,
        archetype_weights: Dict[str, float],
        market_median: float,
    ) -> List[BuyerAgent]:
        buyers = []
        archetype_keys = list(archetype_weights.keys())
        weights = [archetype_weights[k] for k in archetype_keys]

        assignments = self.rng.choice(
            archetype_keys, size=num_buyers, p=weights
        )

        for arch_key in assignments:
            config = ARCHETYPES[arch_key]
            budget = generate_buyer_budget(config, market_median, self.rng)

            # Add individual noise to preference weights
            noise = lambda base: float(np.clip(base + self.rng.normal(0, 0.1), 0, 1))

            buyer = BuyerAgent(
                archetype=arch_key,
                budget=budget,
                school_weight=noise(config.school_weight),
                commute_weight=noise(config.commute_weight),
                space_weight=noise(config.space_weight),
                condition_weight=noise(config.condition_weight),
                hoa_sensitivity=noise(config.hoa_sensitivity),
                risk_tolerance=noise(config.risk_tolerance),
            )
            buyers.append(buyer)

        return buyers

    def _compute_match_score(
        self, buyer: BuyerAgent, prop: PropertyProfile
    ) -> float:
        """Compute how well a property matches a buyer's preferences (0-1)."""
        scores = []

        # Budget fit: penalty if price exceeds budget
        budget_ratio = prop.price / buyer.budget if buyer.budget > 0 else 2.0
        if budget_ratio <= 0.8:
            budget_score = 0.95
        elif budget_ratio <= 1.0:
            budget_score = 1.0 - (budget_ratio - 0.8) * 0.25
        elif budget_ratio <= 1.1:
            budget_score = 0.7 - (budget_ratio - 1.0) * 2.0
        else:
            budget_score = max(0.0, 0.5 - (budget_ratio - 1.1) * 1.5)
        scores.append(("budget", budget_score, 0.35))

        # School quality
        if prop.school_rating is not None:
            school_score = min(1.0, prop.school_rating / 8.0)
        else:
            school_score = 0.5  # unknown defaults to neutral
        scores.append(("school", school_score, buyer.school_weight * 0.15))

        # Space adequacy (rough heuristic based on beds/sqft)
        space_score = min(1.0, prop.sqft / 2000.0)
        if prop.beds >= 3:
            space_score = min(1.0, space_score + 0.15)
        scores.append(("space", space_score, buyer.space_weight * 0.12))

        # Condition
        condition_map = {"excellent": 1.0, "good": 0.75, "fair": 0.5, "poor": 0.25}
        cond_score = condition_map.get(prop.condition or "good", 0.6)
        scores.append(("condition", cond_score, buyer.condition_weight * 0.10))

        # HOA burden
        if prop.hoa_monthly and prop.hoa_monthly > 0:
            hoa_ratio = prop.hoa_monthly / (prop.price / 1000)
            hoa_score = max(0.0, 1.0 - hoa_ratio * buyer.hoa_sensitivity)
        else:
            hoa_score = 0.9
        scores.append(("hoa", hoa_score, 0.08))

        # Risk factors
        risk_map = {"none": 0.0, "low": 0.15, "moderate": 0.35, "high": 0.6}
        fire_risk = risk_map.get(prop.fire_zone, 0.0)
        flood_risk = risk_map.get(prop.flood_zone, 0.0)
        combined_risk = min(1.0, fire_risk + flood_risk)
        risk_score = 1.0 - combined_risk * (1.0 - buyer.risk_tolerance)
        scores.append(("risk", risk_score, 0.10))

        # Walk score / commute proxy
        if prop.walk_score is not None:
            walk_score = prop.walk_score / 100.0
        else:
            walk_score = 0.5
        scores.append(("commute", walk_score, buyer.commute_weight * 0.10))

        # Weighted average
        total_weight = sum(w for _, _, w in scores)
        weighted_sum = sum(s * w for _, s, w in scores)
        return weighted_sum / total_weight if total_weight > 0 else 0.5

    def _simulate_funnel(
        self, buyers: List[BuyerAgent], prop: PropertyProfile
    ) -> Dict[str, int]:
        """Run one simulation pass through the decision funnel."""
        clicks = 0
        saves = 0
        tours = 0
        offers = 0

        for buyer in buyers:
            match_score = self._compute_match_score(buyer, prop)
            noise = self.rng.normal(0, 0.05)

            # Click stage: budget-aware impression
            click_prob = min(0.95, max(0.02, match_score * 0.6 + 0.15 + noise))
            if self.rng.random() < click_prob:
                clicks += 1

                # Save stage: deeper evaluation
                save_prob = min(0.85, max(0.01, match_score * 0.55 + noise))
                if self.rng.random() < save_prob:
                    saves += 1

                    # Tour stage: serious interest
                    tour_prob = min(0.60, max(0.005, match_score * 0.35 + noise))
                    if self.rng.random() < tour_prob:
                        tours += 1

                        # Offer stage: committed
                        offer_prob = min(0.40, max(0.002, match_score * 0.18 + noise))
                        if self.rng.random() < offer_prob:
                            offers += 1

        return {
            "impressions": len(buyers),
            "clicks": clicks,
            "saves": saves,
            "tours": tours,
            "offers": offers,
        }

    def _detect_blockers(self, prop: PropertyProfile) -> List[Dict[str, Any]]:
        """Identify demand blockers based on property attributes."""
        blockers = []

        # HOA analysis
        if prop.hoa_monthly and prop.hoa_monthly > 200:
            severity = "High" if prop.hoa_monthly > 350 else "Medium"
            blockers.append({
                "factor": "HOA Fees Above Market Average",
                "impact": severity,
                "affected_segments": ["Starter Couple", "Investor"],
                "description": f"${prop.hoa_monthly:.0f}/mo HOA may reduce affordability perception for price-sensitive buyers.",
            })

        # Risk zones
        if prop.fire_zone in ("moderate", "high"):
            blockers.append({
                "factor": "Fire Zone Risk",
                "impact": "High" if prop.fire_zone == "high" else "Medium",
                "affected_segments": ["Growing Family", "Downsizer"],
                "description": f"Property is in a {prop.fire_zone}-risk fire zone, which increases buyer hesitation.",
            })

        if prop.flood_zone in ("moderate", "high"):
            blockers.append({
                "factor": "Flood Zone Risk",
                "impact": "High" if prop.flood_zone == "high" else "Medium",
                "affected_segments": ["Growing Family", "Downsizer", "Starter Couple"],
                "description": f"Property is in a {prop.flood_zone}-risk flood zone, adding insurance and safety concerns.",
            })

        # School rating
        if prop.school_rating is not None and prop.school_rating < 6:
            blockers.append({
                "factor": "Below-Average School Ratings",
                "impact": "Medium" if prop.school_rating >= 4 else "High",
                "affected_segments": ["Growing Family"],
                "description": f"Nearest school rating of {prop.school_rating}/10 limits appeal for family buyers.",
            })

        # Condition
        if prop.condition in ("fair", "poor"):
            blockers.append({
                "factor": "Property Condition Concerns",
                "impact": "Medium" if prop.condition == "fair" else "High",
                "affected_segments": ["Relocation Pro", "Starter Couple"],
                "description": f"Property condition rated as '{prop.condition}' may deter turnkey-focused buyers.",
            })

        # Parking
        if prop.parking == "none" and prop.beds >= 3:
            blockers.append({
                "factor": "Limited Parking",
                "impact": "Medium",
                "affected_segments": ["Growing Family", "Relocation Pro"],
                "description": "No dedicated parking for a multi-bedroom home limits appeal for families.",
            })

        # Walk score
        if prop.walk_score is not None and prop.walk_score < 40:
            blockers.append({
                "factor": "Low Walkability Score",
                "impact": "Low",
                "affected_segments": ["Starter Couple", "Downsizer"],
                "description": f"Walk score of {prop.walk_score}/100 may be a concern for buyers seeking walkable neighborhoods.",
            })

        return blockers

    def _generate_recommendations(
        self, prop: PropertyProfile, blockers: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate actionable recommendations based on blockers and property data."""
        recs = []

        for blocker in blockers:
            if "HOA" in blocker["factor"]:
                recs.append({
                    "action": "Highlight HOA-included amenities in listing",
                    "impact": "Medium",
                    "estimated_lift": "+5-8% engagement",
                    "description": "Emphasize amenities covered by HOA (pool, gym, landscaping, etc.) to justify the monthly cost.",
                })
            elif "School" in blocker["factor"]:
                recs.append({
                    "action": "Highlight alternative education options",
                    "impact": "Medium",
                    "estimated_lift": "+4-6% family segment",
                    "description": "Include nearby charter schools, magnet programs, or school bus route information.",
                })
            elif "Condition" in blocker["factor"]:
                recs.append({
                    "action": "Professional staging recommended",
                    "impact": "Medium",
                    "estimated_lift": "+5-7% tour conversion",
                    "description": "Professional staging can offset dated finishes and improve buyer first impressions.",
                })
            elif "Fire" in blocker["factor"] or "Flood" in blocker["factor"]:
                recs.append({
                    "action": "Provide insurance cost estimates upfront",
                    "impact": "Low",
                    "estimated_lift": "+2-4% engagement",
                    "description": "Transparent insurance costs reduce uncertainty and build buyer confidence.",
                })

        # Always suggest price sensitivity analysis
        recs.append({
            "action": "Consider strategic price adjustment",
            "impact": "High",
            "estimated_lift": "+12-20% demand",
            "description": f"A 2-3% price reduction could significantly expand the qualified buyer pool.",
        })

        return recs[:5]  # Cap at 5 recommendations

    def _aggregate_results(
        self,
        prop: PropertyProfile,
        buyers: List[BuyerAgent],
        funnel_runs: List[Dict[str, int]],
        archetype_weights: Dict[str, float],
        num_simulations: int,
    ) -> SimulationResult:
        """Aggregate Monte Carlo results into final metrics."""
        # Average funnel counts across simulations
        avg_funnel = {}
        for key in ["impressions", "clicks", "saves", "tours", "offers"]:
            values = [run[key] for run in funnel_runs]
            avg_funnel[key] = int(np.mean(values))

        total_buyers = len(buyers)

        # Demand score: composite of funnel conversion and match quality
        click_rate = avg_funnel["clicks"] / max(1, total_buyers)
        save_rate = avg_funnel["saves"] / max(1, avg_funnel["clicks"])
        tour_rate = avg_funnel["tours"] / max(1, avg_funnel["saves"])
        offer_rate = avg_funnel["offers"] / max(1, avg_funnel["tours"])

        demand_score = min(100, max(0, int(
            click_rate * 25 +
            save_rate * 25 +
            tour_rate * 25 +
            offer_rate * 15 +
            min(10, avg_funnel["offers"] / max(1, total_buyers) * 500)
        )))

        # Sale probability estimation from offer distribution
        offer_counts = [run["offers"] for run in funnel_runs]
        offer_array = np.array(offer_counts)

        p_at_least_one_offer_30 = float(np.mean(offer_array >= 1)) * 0.85
        p_at_least_one_offer_60 = float(np.mean(offer_array >= 1)) * 0.95
        p_at_least_one_offer_90 = min(0.99, float(np.mean(offer_array >= 1)) * 1.05)

        sale_prob_30 = min(99, max(5, int(p_at_least_one_offer_30 * 100)))
        sale_prob_60 = min(99, max(10, int(p_at_least_one_offer_60 * 100)))
        sale_prob_90 = min(99, max(15, int(p_at_least_one_offer_90 * 100)))

        # Time to first offer: inverse of offer rate
        avg_offers = float(np.mean(offer_array))
        if avg_offers > 0:
            time_to_offer = max(5, min(90, int(30 / avg_offers)))
        else:
            time_to_offer = 90

        # Funnel data for charts
        funnel_data = [
            {"stage": "Impressions", "count": total_buyers, "rate": 100.0},
            {"stage": "Clicks", "count": avg_funnel["clicks"], "rate": round(click_rate * 100, 1)},
            {"stage": "Saves", "count": avg_funnel["saves"], "rate": round(avg_funnel["saves"] / max(1, total_buyers) * 100, 1)},
            {"stage": "Tours", "count": avg_funnel["tours"], "rate": round(avg_funnel["tours"] / max(1, total_buyers) * 100, 1)},
            {"stage": "Offers", "count": avg_funnel["offers"], "rate": round(avg_funnel["offers"] / max(1, total_buyers) * 100, 1)},
        ]

        # Archetype breakdown
        archetype_counts = {}
        for buyer in buyers:
            archetype_counts[buyer.archetype] = archetype_counts.get(buyer.archetype, 0) + 1

        archetype_breakdown = []
        for key, count in sorted(archetype_counts.items(), key=lambda x: -x[1]):
            config = ARCHETYPES[key]
            pct = round(count / total_buyers * 100, 1)
            engagement = (
                "Very High" if pct > 30 else
                "High" if pct > 20 else
                "Medium" if pct > 10 else
                "Low"
            )
            archetype_breakdown.append({
                "name": config.name,
                "percentage": pct,
                "engagement": engagement,
                "count": count,
            })

        # Blockers & recommendations
        blockers = self._detect_blockers(prop)
        recommendations = self._generate_recommendations(prop, blockers)

        # Timeline data (simulated cumulative interest curve)
        timeline = []
        for day in [0, 5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 90]:
            # Logarithmic growth curve
            if day == 0:
                cum = 0
            else:
                max_interest = avg_funnel["saves"]
                cum = int(max_interest * (1 - np.exp(-day / 25)))
            daily = max(0, cum - (timeline[-1]["cumulative"] if timeline else 0))
            timeline.append({"day": day, "cumulative": cum, "daily": daily})

        # Price sensitivity
        price_deltas = [-30000, -20000, -10000, 0, 10000, 20000, 30000]
        price_sensitivity = []
        for delta in price_deltas:
            # Approximate demand elasticity
            pct_change = delta / prop.price
            demand_change = round(-pct_change * 120 + self.rng.normal(0, 2), 0)
            if delta == 0:
                demand_change = 0
            label = f"${'+' if delta > 0 else ''}{delta // 1000}K" if delta != 0 else "Current"
            price_sensitivity.append({
                "price_point": delta,
                "demand_change": demand_change,
                "label": label,
            })

        # Competitive context (placeholder — would come from market data in production)
        price_per_sqft = prop.price / prop.sqft if prop.sqft > 0 else 0
        competitive_context = {
            "avg_days_on_market": max(10, int(time_to_offer * 1.3)),
            "median_price": int(prop.price * 0.95),
            "active_listings": int(30 + self.rng.integers(10, 30)),
            "avg_price_per_sqft": int(price_per_sqft * 1.05),
            "this_property_price_per_sqft": int(price_per_sqft),
        }

        return SimulationResult(
            demand_score=demand_score,
            sale_probability_30=sale_prob_30,
            sale_probability_60=sale_prob_60,
            sale_probability_90=sale_prob_90,
            time_to_first_offer=time_to_offer,
            buyer_pool_size=total_buyers,
            funnel_data=funnel_data,
            archetype_breakdown=archetype_breakdown,
            demand_blockers=blockers,
            recommendations=recommendations,
            timeline_data=timeline,
            price_sensitivity=price_sensitivity,
            competitive_context=competitive_context,
            simulation_runs=num_simulations,
        )
