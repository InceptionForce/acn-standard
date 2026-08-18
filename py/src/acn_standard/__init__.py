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
__version__ = "0.1.0"
