from typing import Dict, Any
import uuid

from frank.core import gen_id
from frank.core.models import Sighting

def sighting_to_stix_bundle(sighting: Sighting) -> Dict[str, Any]:
    """
    Translate a FRANK Sighting model (with nested observables and hit_target) to a STIX 2.1 bundle.
    """
    return_objects= []
    # Observed Data object for all observables
    observed_objects = {}
    obj_idx = 0
    for obs in sighting.observables.network:
        if obs.observable_type == "ipv4":
            observed_objects[str(obj_idx)] = {
                "type": "ipv4-addr",
                "id": obs.id,
                "value": obs.value
            }
        elif obs.observable_type == "domain":
            observed_objects[str(obj_idx)] = {
                "type": "domain-name",
                "id": obs.id,
                "value": obs.value
            }
        obj_idx += 1
    # Add other observable types (file, process) as needed

    # Extract the UUID from the model.id (e.g., 'sighting--<uuid>')
    sighting_uuid = str(sighting.sighting_id).split("--", 1)[-1]
    observed_data_id = gen_id("observed-data", sighting_uuid)
    stix_observed_data = {
        "type": "observed-data",
        "id": observed_data_id,
        "created": sighting.timestamp.isoformat(),
        "modified": sighting.timestamp.isoformat(),
        "first_observed": sighting.first_observed.isoformat() if sighting.first_observed else sighting.timestamp.isoformat(),
        "last_observed": sighting.last_observed.isoformat() if sighting.last_observed else sighting.timestamp.isoformat(),
        "number_observed": sighting.observation_count,
        "objects": observed_objects
    }
    return_objects += [stix_observed_data]

    # Identity for hit_target (where_sighted_refs)
    hit_target = sighting.hit_target
    if hit_target:
        sector = hit_target.sector or "unknown" 
        region = hit_target.region or "unknown"
        if hit_target.organisation_id:
            identity_id = hit_target.organisation_id
        else:
            identity_id = gen_id("identity", f"sector-{sector}-region-{region}-{uuid.uuid4}")
        stix_identity = {
            "type": "identity",
            "id": identity_id,
            "identity_class": "organization",
            "sectors": [sector],
            "region": region,
            "anonymization_level": hit_target.anonymization_level
        }
        return_objects += [stix_identity]

        # Sighting object
        stix_sighting = {
            "type": "sighting",
            "id": sighting.sighting_id,
            "created": sighting.timestamp.isoformat(),
            "modified": sighting.timestamp.isoformat(),
            "count": sighting.observation_count,
            "where_sighted_refs": [identity_id],
            "observed_data_refs": [observed_data_id],
            # Optionally add confidence, lang, etc.
        }
        return_objects += [stix_sighting]

    return {
        "type": "bundle",
        "id": f"bundle--{sighting_uuid}",
        "objects": return_objects
    }