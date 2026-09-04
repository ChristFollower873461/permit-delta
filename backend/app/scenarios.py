from typing import Dict, Any, List

SCENARIOS: Dict[int, Dict[str, Any]] = {
    1: {
        "id": 1,
        "name": "Contact and schedule",
        "description": "Alters scene schedule order and non-permit contact notes while leaving permitted scope unchanged. Pending review by internal production coordinator.",
        "expected_state": "OWNER REVIEW: NO MATERIAL PERMIT-SCOPE DELTA DETECTED",
        "expected_destination": "Internal Production Coordinator",
        "expected_next_action": "Route the revision record to the Internal Production Coordinator for human review before the updated call sheet is distributed.",
        "uncertainty_rating": "Low",
        "baseline": {
            "permit_id": "PERMIT-2026-089A",
            "production_name": "Sunset Tide",
            "film_date": "2026-09-11",
            "location": "Leo Carrillo State Park (Sector 1, tide pools)",
            "crew_size": 25,
            "generator": "None",
            "drone": "None",
            "description": "Scene 14: Dialogue by the tide pools.",
            "contact_phone": "555-0100"
        },
        "revised": {
            "permit_id": "PERMIT-2026-089A",
            "production_name": "Sunset Tide",
            "film_date": "2026-09-11",
            "location": "Leo Carrillo State Park (Sector 1, tide pools)",
            "crew_size": 25,
            "generator": "None",
            "drone": "None",
            "description": "Scene 14: Dialogue by the tide pools (moved to second unit schedule order).",
            "contact_phone": "555-0199"
        },
        "differences": [
            "Scene description updated with schedule ordering change only.",
            "Non-permit contact phone number updated from 555-0100 to 555-0199."
        ]
    },
    2: {
        "id": 2,
        "name": "Added generator",
        "description": "Adds a 75kW towable diesel generator to night filming at Leo Carrillo tide pools. Pending human review and placement coordination with State Parks and the California Film Commission.",
        "expected_state": "HOLD: MATERIAL DELTA; CONTACT PARK/CFC",
        "expected_destination": "State Park Special Events Office & CFC",
        "expected_next_action": "Pause the revised call-sheet handoff and route the generator delta to California State Parks Special Events and the California Film Commission for human review, with generator specifications and the proposed fire-safety placement plan.",
        "uncertainty_rating": "Low",
        "baseline": {
            "permit_id": "PERMIT-2026-089A",
            "production_name": "Sunset Tide",
            "film_date": "2026-09-11",
            "location": "Leo Carrillo State Park (Sector 1, tide pools)",
            "crew_size": 25,
            "generator": "None",
            "drone": "None",
            "description": "Scene 14: Dialogue by the tide pools.",
            "contact_phone": "555-0100"
        },
        "revised": {
            "permit_id": "PERMIT-2026-089A",
            "production_name": "Sunset Tide",
            "film_date": "2026-09-11",
            "location": "Leo Carrillo State Park (Sector 1, tide pools)",
            "crew_size": 25,
            "generator": "75kW Towable Generator (added for night scene lighting)",
            "drone": "None",
            "description": "Scene 14: Dialogue by the tide pools (night shoot lighting needed).",
            "contact_phone": "555-0100"
        },
        "differences": [
            "Generator increased from 'None' to '75kW Towable Generator'.",
            "Description updated to note lighting requirements for a night shoot."
        ]
    },
    3: {
        "id": 3,
        "name": "Short-notice drone",
        "description": "Adds a commercial drone tracking shot five business days before filming. Pending manual lead permit officer review for lead time and flight path review.",
        "expected_state": "UNKNOWN: ESCALATION FOR MANUAL REVIEW",
        "expected_destination": "Lead Permit Officer (Escalated Review)",
        "expected_next_action": "Immediately contact the Lead Permit Officer at California State Parks and the California Film Commission. The short timeline requires manual authority review.",
        "uncertainty_rating": "High",
        "baseline": {
            "permit_id": "PERMIT-2026-089A",
            "production_name": "Sunset Tide",
            "film_date": "2026-09-11",
            "location": "Leo Carrillo State Park (Sector 1, tide pools)",
            "crew_size": 25,
            "generator": "None",
            "drone": "None",
            "description": "Scene 14: Dialogue by the tide pools.",
            "contact_phone": "555-0100"
        },
        "revised": {
            "permit_id": "PERMIT-2026-089A",
            "production_name": "Sunset Tide",
            "film_date": "2026-09-11",
            "location": "Leo Carrillo State Park (Sector 1, tide pools)",
            "crew_size": 25,
            "generator": "None",
            "drone": "Mavic 3 Pro (added for overhead tide pool tracking shot)",
            "description": "Scene 14: Tide pool tracking shot with Mavic 3 drone.",
            "contact_phone": "555-0100"
        },
        "differences": [
            "Drone added ('Mavic 3 Pro') exactly five business days prior to filming.",
            "Description updated with overhead tide pool tracking shot."
        ]
    }
}
