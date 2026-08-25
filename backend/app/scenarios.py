from typing import Dict, Any, List

SCENARIOS: Dict[int, Dict[str, Any]] = {
    1: {
        "id": 1,
        "name": "Scenario 1: Control Change",
        "description": "Internal scene-order changes and update to non-permit contact notes. No material permit scope parameters are affected.",
        "expected_state": "OWNER REVIEW: NO MATERIAL PERMIT-SCOPE DELTA DETECTED",
        "expected_destination": "Internal Production Coordinator",
        "expected_next_action": "Log revision internally, publish updated call sheet, and archive change record.",
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
        "name": "Scenario 2: Material Change",
        "description": "Adds exactly one 75kW generator to the production plan, which is a material change requiring park special events or environmental health permit revision.",
        "expected_state": "HOLD: MATERIAL DELTA; CONTACT PARK/CFC",
        "expected_destination": "State Park Special Events Office & CFC",
        "expected_next_action": "Do NOT film with the generator yet. Submit a formal permit rider request to California State Parks Special Events and CC the California Film Commission, providing generator specs and fire-safety placement plan.",
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
        "name": "Scenario 3: Authority Conflict (Drone Short-Notice)",
        "description": "Adds a commercial drone five business days before filming. Current official rules from California Film Commission, California State Parks, and the FAA are contradictory or state differing lead times, causing a source conflict or uncertainty in lead-time rules.",
        "expected_state": "UNKNOWN: SOURCE CONFLICT OR STALE AUTHORITY",
        "expected_destination": "Lead Permit Officer (Escalated Review)",
        "expected_next_action": "Immediately contact the Lead Permit Officer at California State Parks and the California Film Commission. The short timeline conflicts with several official agency guidelines.",
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
