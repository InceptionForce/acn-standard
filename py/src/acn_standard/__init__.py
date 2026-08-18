"""Dependency-free ACN 0.1 reference contracts."""

from .models import CommerceEnvelope
from .validation import ContractError, validate_envelope
from .a2a import (
    ACN_A2A_EXTENSION,
    ACN_MEDIA_TYPE,
    ACN_RESULT_MEDIA_TYPE,
    a2a_result_message,
    parse_a2a_message,
)
from .security import (
    EnvelopeSignature,
    canonical_agent_card,
    canonical_envelope,
    canonical_agent_proof,
    parse_signature,
    sign_envelope,
    sign_agent_card,
    sign_agent_proof,
    verify_agent_proof_signature,
    verify_envelope_signature,
    verify_agent_card_signature,
)
from .sdk import (
    AcnClient,
    AcnClientError,
    Submission,
    build_envelope,
    delivery_proof,
    generate_ed25519_keypair,
    signed_envelope,
)
from .extensions import ACN_NETWORK_EXTENSION, validate_network_extension

__all__ = [
    "CommerceEnvelope",
    "ContractError",
    "validate_envelope",
    "ACN_A2A_EXTENSION",
    "ACN_MEDIA_TYPE",
    "ACN_RESULT_MEDIA_TYPE",
    "parse_a2a_message",
    "a2a_result_message",
    "EnvelopeSignature",
    "canonical_agent_card",
    "canonical_envelope",
    "canonical_agent_proof",
    "parse_signature",
    "sign_envelope",
    "sign_agent_card",
    "sign_agent_proof",
    "verify_agent_proof_signature",
    "verify_envelope_signature",
    "verify_agent_card_signature",
    "AcnClient",
    "AcnClientError",
    "Submission",
    "build_envelope",
    "delivery_proof",
    "generate_ed25519_keypair",
    "signed_envelope",
    "ACN_NETWORK_EXTENSION",
    "validate_network_extension",
]


def schema_directory():
    """Where the bundled JSON Schemas live.

    The library validates envelopes in Python; these schemas state the same
    contract in a form other languages can use. They travel with the code
    because two descriptions of one contract, versioned separately, is how a
    validator and a schema come to disagree about what is valid.
    """
    from importlib.resources import files

    return files(__name__) / "schemas"


def conformance_directory():
    """Where the bundled conformance corpus lives.

    Returns a path containing `valid/` and `invalid/`. Distributed with the
    package so an implementer can check their envelopes against the same
    fixtures this library is tested with, rather than a copy that has drifted:

        from acn_standard import conformance_directory, validate_envelope
        for path in (conformance_directory() / "valid").glob("*.json"):
            validate_envelope(json.loads(path.read_text()))
    """
    from importlib.resources import files

    return files(__name__) / "conformance"


__version__ = "0.1.1"
