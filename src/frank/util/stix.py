#!/usr/bin/env python3
"""
FRANK Platform - STIX Translation Utilities
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This module provides utilities for translating FRANK models (e.g., Sighting) into STIX 2.1-compliant objects and bundles.
Intended for standards-based threat intelligence exchange and API integration.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from typing import Dict, Any
import uuid

from frank.core import gen_id
from frank.core.models import Sighting


def sighting_to_stix_bundle(sighting: Sighting) -> Dict[str, Any]:
    """
    Translate a FRANK Sighting model (with nested observables and hit_target) to a STIX 2.1 bundle.
    """
    return_objects = []
    # Observed Data object for all observables
    observed_objects = {}
    obj_idx = 0
    # Network observables
    for obs in sighting.observables.network:
        if obs.observable_type == "ipv4":
            observed_objects[str(obj_idx)] = {"type": "ipv4-addr", "id": obs.id, "value": obs.value}
        elif obs.observable_type == "ipv6":
            observed_objects[str(obj_idx)] = {"type": "ipv6-addr", "id": obs.id, "value": obs.value}
        elif obs.observable_type == "domain":
            observed_objects[str(obj_idx)] = {"type": "domain-name", "id": obs.id, "value": obs.value}
        elif obs.observable_type == "url":
            observed_objects[str(obj_idx)] = {"type": "url", "id": obs.id, "value": obs.value}
        elif obs.observable_type == "email":
            observed_objects[str(obj_idx)] = {"type": "email-addr", "id": obs.id, "value": obs.value}
        elif obs.observable_type == "file_hash":
            observed_objects[str(obj_idx)] = {"type": "file-hash", "id": obs.id, "value": obs.value}
        elif obs.observable_type == "registry_key":
            observed_objects[str(obj_idx)] = {"type": "windows-registry-key", "id": obs.id, "value": obs.value}
        elif obs.observable_type == "mutex":
            observed_objects[str(obj_idx)] = {"type": "mutex", "id": obs.id, "value": obs.value}
        elif obs.observable_type == "certificate":
            observed_objects[str(obj_idx)] = {"type": "certificate", "id": obs.id, "value": obs.value}
        obj_idx += 1

    # File observables (legacy: keep for backward compatibility, but prefer file_hash above)
    for obs in getattr(sighting.observables, "file", []):
        if obs.observable_type == "file":
            file_obj = {
                "type": "file",
                "id": obs.id,
                "name": getattr(obs, "name", None),
                "hashes": getattr(obs, "hashes", None),
                "value": obs.value,
            }
            # Remove None values
            file_obj = {k: v for k, v in file_obj.items() if v is not None}
            observed_objects[str(obj_idx)] = file_obj
            obj_idx += 1

    # Process observables
    for obs in getattr(sighting.observables, "process", []):
        if obs.observable_type == "process":
            process_obj = {
                "type": "process",
                "id": obs.id,
                "pid": getattr(obs, "pid", None),
                "name": getattr(obs, "name", None),
                "command_line": getattr(obs, "command_line", None),
                "value": obs.value,
            }
            # Remove None values
            process_obj = {k: v for k, v in process_obj.items() if v is not None}
            observed_objects[str(obj_idx)] = process_obj
            obj_idx += 1

    # Extract the UUID from the model.id (e.g., 'sighting--<uuid>')
    sighting_uuid = str(sighting.sighting_id).split("--", 1)[-1]
    observed_data_id = gen_id("observed-data", sighting_uuid)
    stix_observed_data = {
        "type": "observed-data",
        "id": observed_data_id,
        "created": sighting.timestamp.isoformat(),
        "modified": sighting.timestamp.isoformat(),
        "first_observed": sighting.first_observed.isoformat()
        if sighting.first_observed
        else sighting.timestamp.isoformat(),
        "last_observed": sighting.last_observed.isoformat()
        if sighting.last_observed
        else sighting.timestamp.isoformat(),
        "number_observed": sighting.observation_count,
        "objects": observed_objects,
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
            "anonymization_level": hit_target.anonymization_level,
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

    return {"type": "bundle", "id": f"bundle--{sighting_uuid}", "objects": return_objects}
