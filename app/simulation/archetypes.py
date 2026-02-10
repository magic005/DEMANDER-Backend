"""
Buyer archetype definitions and parameter distributions.
Each archetype has a budget distribution, preference weights, and behavioral traits.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass
class ArchetypeConfig:
    name: str
    weight: float  # market share probability
    budget_range: Tuple[float, float]  # (min, max)
    budget_mean_factor: float  # multiplier against median price
    budget_std_factor: float  # std dev as fraction of mean

    # Preference weights (0-1): how much this factor matters to this archetype
    school_weight: float = 0.5
    commute_weight: float = 0.5
    space_weight: float = 0.5
    condition_weight: float = 0.5
    hoa_sensitivity: float = 0.5
    risk_tolerance: float = 0.5  # higher = more risk tolerant
    aesthetic_sensitivity: float = 0.5

    # Behavioral parameters
    click_base_rate: float = 0.4
    save_rate_multiplier: float = 1.0
    tour_rate_multiplier: float = 1.0
    offer_rate_multiplier: float = 1.0


ARCHETYPES: Dict[str, ArchetypeConfig] = {
    "starter_couple": ArchetypeConfig(
        name="Starter Couple",
        weight=0.25,
        budget_range=(200_000, 500_000),
        budget_mean_factor=0.85,
        budget_std_factor=0.15,
        school_weight=0.3,
        commute_weight=0.8,
        space_weight=0.4,
        condition_weight=0.7,
        hoa_sensitivity=0.8,
        risk_tolerance=0.3,
        aesthetic_sensitivity=0.6,
        click_base_rate=0.45,
        save_rate_multiplier=1.1,
        tour_rate_multiplier=0.9,
        offer_rate_multiplier=0.8,
    ),
    "growing_family": ArchetypeConfig(
        name="Growing Family",
        weight=0.30,
        budget_range=(350_000, 800_000),
        budget_mean_factor=1.0,
        budget_std_factor=0.18,
        school_weight=0.95,
        commute_weight=0.6,
        space_weight=0.9,
        condition_weight=0.6,
        hoa_sensitivity=0.5,
        risk_tolerance=0.2,
        aesthetic_sensitivity=0.4,
        click_base_rate=0.40,
        save_rate_multiplier=1.0,
        tour_rate_multiplier=1.1,
        offer_rate_multiplier=1.0,
    ),
    "relocation_pro": ArchetypeConfig(
        name="Relocation Pro",
        weight=0.20,
        budget_range=(300_000, 650_000),
        budget_mean_factor=0.95,
        budget_std_factor=0.12,
        school_weight=0.4,
        commute_weight=0.9,
        space_weight=0.5,
        condition_weight=0.9,
        hoa_sensitivity=0.4,
        risk_tolerance=0.4,
        aesthetic_sensitivity=0.7,
        click_base_rate=0.50,
        save_rate_multiplier=0.8,
        tour_rate_multiplier=1.2,
        offer_rate_multiplier=1.1,
    ),
    "downsizer": ArchetypeConfig(
        name="Downsizer",
        weight=0.10,
        budget_range=(250_000, 550_000),
        budget_mean_factor=0.90,
        budget_std_factor=0.20,
        school_weight=0.1,
        commute_weight=0.3,
        space_weight=0.3,
        condition_weight=0.8,
        hoa_sensitivity=0.6,
        risk_tolerance=0.2,
        aesthetic_sensitivity=0.5,
        click_base_rate=0.35,
        save_rate_multiplier=0.9,
        tour_rate_multiplier=0.8,
        offer_rate_multiplier=0.9,
    ),
    "investor": ArchetypeConfig(
        name="Investor",
        weight=0.15,
        budget_range=(150_000, 1_200_000),
        budget_mean_factor=0.80,
        budget_std_factor=0.30,
        school_weight=0.2,
        commute_weight=0.3,
        space_weight=0.4,
        condition_weight=0.5,
        hoa_sensitivity=0.9,
        risk_tolerance=0.7,
        aesthetic_sensitivity=0.2,
        click_base_rate=0.55,
        save_rate_multiplier=0.7,
        tour_rate_multiplier=0.6,
        offer_rate_multiplier=1.3,
    ),
}


def select_archetypes_for_market(price: float) -> Dict[str, float]:
    """
    Adjust archetype weights based on property price point.
    Returns adjusted weights that sum to 1.0.
    """
    weights = {}
    for key, arch in ARCHETYPES.items():
        base_weight = arch.weight
        # Reduce weight if property price is outside archetype's budget range
        if price < arch.budget_range[0]:
            adjustment = max(0.1, 1.0 - (arch.budget_range[0] - price) / arch.budget_range[0])
        elif price > arch.budget_range[1]:
            adjustment = max(0.05, 1.0 - (price - arch.budget_range[1]) / arch.budget_range[1])
        else:
            # Price within range — compute how central it is
            mid = (arch.budget_range[0] + arch.budget_range[1]) / 2
            spread = (arch.budget_range[1] - arch.budget_range[0]) / 2
            distance = abs(price - mid) / spread
            adjustment = 1.0 - 0.3 * distance  # slight penalty for being at edges
        weights[key] = base_weight * adjustment

    total = sum(weights.values())
    return {k: v / total for k, v in weights.items()}


def generate_buyer_budget(archetype: ArchetypeConfig, market_median: float, rng: np.random.Generator) -> float:
    """Generate a single buyer's budget from the archetype distribution."""
    mean = market_median * archetype.budget_mean_factor
    std = mean * archetype.budget_std_factor
    budget = rng.normal(mean, std)
    return float(np.clip(budget, archetype.budget_range[0] * 0.8, archetype.budget_range[1] * 1.2))
