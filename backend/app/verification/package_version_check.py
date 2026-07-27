from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.matching.product_aliases import product_aliases
from app.matching.utils import normalize_name, values_match
from app.matching.version_rule import evaluate_version_constraint_groups, parse_constraint_groups


TASK_TYPE = "package_version_check"
EVIDENCE_TYPE = "package_version"
ABSENCE_EVIDENCE_TYPE = "package_absence"
VERSION_EVIDENCE_TYPES = {EVIDENCE_TYPE, "kernel_version", "os_version"}
PLATFORM_COMPONENT_TYPES = {"kernel", "operating_system"}


@dataclass(slots=True)
class PackageVersionExecution:
    status: str
    evidence: list[dict[str, object]]
    error_code: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class PackageVersionDecision:
    match_status: str | None
    confidence: float | None
    reason: str | None


def execute_package_version_check(
    parameters: dict[str, object],
    asset_components: list[Any],
) -> PackageVersionExecution:
    package_name = _string_value(parameters.get("package_name"))
    if not package_name:
        return PackageVersionExecution(
            status="failed",
            evidence=[],
            error_code="missing_package_name",
            error_message="package_version_check requires package_name",
        )

    component_type = _requested_component_type(parameters, package_name)
    component = _find_component(
        asset_components,
        package_name,
        component_type=component_type,
    )
    if component is None:
        if component_type in PLATFORM_COMPONENT_TYPES:
            return PackageVersionExecution(
                status="failed",
                evidence=[],
                error_code=f"missing_{'kernel' if component_type == 'kernel' else 'os'}_version",
                error_message=f"No {component_type} facts were available for {package_name}",
            )
        return PackageVersionExecution(
            status="completed",
            evidence=[build_package_absence_evidence(package_name)],
        )

    component_name = _string_value(_component_value(component, "component_name")) or package_name
    observed_version = _string_value(_component_value(component, "version"))
    source = _string_value(_component_value(component, "source_type")) or "asset_snapshot"
    observed_component_type = (
        _string_value(_component_value(component, "component_type")) or "package"
    )
    evidence_type = _evidence_type_for_component(observed_component_type)

    return PackageVersionExecution(
        status="completed",
        evidence=[
            {
                "evidence_type": evidence_type,
                "summary": f"Observed {component_name} {observed_version} from {source}.",
                "raw_ref": _component_value(component, "id"),
                "confidence": 0.94 if evidence_type != EVIDENCE_TYPE else 0.92,
                "details": {
                    "package_name": component_name,
                    "component_type": observed_component_type,
                    "observed_version": observed_version,
                    "source": source,
                },
            }
        ],
    )


def decide_package_version_match_update(
    *,
    task_status: str,
    error_code: str | None,
    evidence_items: list[Any],
    affected_versions: str | None,
    fixed_versions: str | None,
) -> PackageVersionDecision:
    if task_status != "completed":
        if error_code:
            return PackageVersionDecision(
                match_status=None,
                confidence=None,
                reason=f"Verification did not complete: {error_code}.",
            )
        return PackageVersionDecision(
            match_status=None,
            confidence=None,
            reason=f"Verification ended with status {task_status}.",
        )

    absence_evidence = _first_absence_evidence(evidence_items)
    if absence_evidence is not None:
        details = _evidence_value(absence_evidence, "details_json") or {}
        package_name = (
            _string_value(details.get("package_name"))
            or _string_value(details.get("name"))
            or "component"
        )
        confidence = _confidence_value(_evidence_value(absence_evidence, "confidence"))
        return PackageVersionDecision(
            match_status="not_affected",
            confidence=confidence,
            reason=f"Verification confirmed {package_name} is not installed on the asset.",
        )

    evidence = _first_version_evidence(evidence_items)
    if evidence is None:
        return PackageVersionDecision(
            match_status=None,
            confidence=None,
            reason="Verification completed without version evidence.",
        )

    details = _evidence_value(evidence, "details_json") or {}
    evidence_type = _string_value(_evidence_value(evidence, "evidence_type"))
    package_name = (
        _string_value(details.get("package_name"))
        or _string_value(details.get("name"))
        or "component"
    )
    component_type = _string_value(details.get("component_type")) or _component_type_for_evidence(
        evidence_type
    )
    observed_version = _string_value(details.get("observed_version"))
    confidence = _confidence_value(_evidence_value(evidence, "confidence"))

    if not observed_version:
        return PackageVersionDecision(
            match_status="needs_review",
            confidence=confidence,
            reason=f"Verification observed {package_name}, but no version was returned.",
        )

    constraint_groups = parse_constraint_groups(affected_versions, fixed_versions)
    if not constraint_groups:
        if _affected_text_mentions_observed_version(
            package_name,
            observed_version,
            affected_versions,
        ):
            return PackageVersionDecision(
                match_status="verified",
                confidence=confidence,
                reason=(
                    f"Verification confirmed {package_name} {observed_version} "
                    "is listed in the affected version text."
                ),
            )
        return PackageVersionDecision(
            match_status="needs_review",
            confidence=confidence,
            reason=(
                f"Verification observed {package_name} {observed_version}, "
                "but no version constraint was available."
            ),
        )

    evaluation = evaluate_version_constraint_groups(
        observed_version,
        constraint_groups,
        allow_metadata_mismatch=component_type in PLATFORM_COMPONENT_TYPES,
    )
    if evaluation.result is True:
        return PackageVersionDecision(
            match_status="verified",
            confidence=confidence,
            reason=(
                f"Verification confirmed {package_name} {observed_version} "
                "is inside the affected range."
            ),
        )
    if evaluation.result is False:
        return PackageVersionDecision(
            match_status="not_affected",
            confidence=confidence,
            reason=(
                f"Verification confirmed {package_name} {observed_version} "
                "is outside the affected range."
            ),
        )
    return PackageVersionDecision(
        match_status="needs_review",
        confidence=confidence,
        reason=(
            f"Verification observed {package_name} {observed_version}, "
            f"but version comparison was inconclusive: {evaluation.reason}."
        ),
    )


def _find_component(
    asset_components: list[Any],
    package_name: str,
    *,
    component_type: str | None = None,
) -> Any | None:
    for component in asset_components:
        if component_type and _component_type(component) != component_type:
            continue
        if values_match(
            package_name,
            (
                _component_value(component, "component_name"),
                _component_value(component, "component_type"),
                _component_value(component, "source_type"),
                _component_value(component, "install_path"),
            ),
        ):
            return component
    return None


def _first_version_evidence(evidence_items: list[Any]) -> Any | None:
    for evidence in evidence_items:
        if _evidence_value(evidence, "evidence_type") in VERSION_EVIDENCE_TYPES:
            return evidence
    return None


def _first_absence_evidence(evidence_items: list[Any]) -> Any | None:
    for evidence in evidence_items:
        if _evidence_value(evidence, "evidence_type") == ABSENCE_EVIDENCE_TYPE:
            return evidence
    return None


def build_package_absence_evidence(
    package_name: str,
    *,
    source: str = "asset_component_inventory",
    confidence: float = 0.95,
) -> dict[str, object]:
    return {
        "evidence_type": ABSENCE_EVIDENCE_TYPE,
        "summary": f"Package {package_name} was not observed in the asset package inventory.",
        "raw_ref": None,
        "confidence": confidence,
        "details": {
            "package_name": package_name,
            "component_type": "package",
            "observed": False,
            "source": source,
        },
    }


def _evidence_value(evidence: Any, field_name: str) -> Any:
    if isinstance(evidence, dict):
        if field_name == "details_json":
            return evidence.get("details_json") or evidence.get("details")
        return evidence.get(field_name)
    return getattr(evidence, field_name, None)


def _component_value(component: Any, field_name: str) -> Any:
    if isinstance(component, dict):
        return component.get(field_name)
    return getattr(component, field_name, None)


def _component_type(component: Any) -> str:
    return _normalize_component_type(_component_value(component, "component_type"))


def _requested_component_type(
    parameters: dict[str, object],
    package_name: str,
) -> str | None:
    explicit = _normalize_component_type(parameters.get("component_type"))
    if explicit:
        return explicit

    package_key = normalize_name(package_name)
    if package_key in {
        "linuxkernel",
        "kernel",
        "linuximage",
        "linuximagegeneric",
        "linuxheaders",
    }:
        return "kernel"
    if package_key in {
        "ubuntu",
        "ubuntulinux",
        "debian",
        "debianlinux",
        "redhatenterpriselinux",
        "rhel",
        "redhat",
        "redhatlinux",
        "centos",
        "centoslinux",
        "rockylinux",
        "rocky",
        "almalinux",
        "amazonlinux",
        "amzn",
        "amzn2",
    }:
        return "operating_system"
    return None


def _normalize_component_type(value: object) -> str:
    key = normalize_name(_string_value(value))
    if key == "kernel":
        return "kernel"
    if key in {"operatingsystem", "os"}:
        return "operating_system"
    if key == "package":
        return "package"
    return ""


def _evidence_type_for_component(component_type: str) -> str:
    normalized = _normalize_component_type(component_type)
    if normalized == "kernel":
        return "kernel_version"
    if normalized == "operating_system":
        return "os_version"
    return EVIDENCE_TYPE


def _component_type_for_evidence(evidence_type: str) -> str:
    if evidence_type == "kernel_version":
        return "kernel"
    if evidence_type == "os_version":
        return "operating_system"
    return "package"


def _affected_text_mentions_observed_version(
    package_name: str,
    observed_version: str,
    affected_versions: str | None,
) -> bool:
    if not affected_versions:
        return False
    text_key = normalize_name(affected_versions)
    version_key = normalize_name(observed_version)
    name_keys = {normalize_name(package_name)}
    name_keys.update(normalize_name(alias) for alias in product_aliases(package_name))
    return bool(
        version_key
        and version_key in text_key
        and any(name_key and name_key in text_key for name_key in name_keys)
    )


def _string_value(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _confidence_value(value: object) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(confidence, 1.0))
