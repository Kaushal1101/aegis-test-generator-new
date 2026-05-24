from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol


CheckStatus = Literal["pass", "fail", "skip", "error"]


@dataclass
class CheckRecord:
    """Normalized check record used by diff and orchestrator."""

    suite_id: str
    check_id: str
    status: CheckStatus
    title: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedInputResult:
    """Output of the input component."""

    parsed: dict[str, Any]
    derived: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class InputRequest:
    """Input request payload for the input component."""

    input_path: str | None = None
    input_json: dict[str, Any] | None = None


@dataclass
class InputResult:
    """Output of the input component (ParsedInputResult-compatible)."""

    parsed: dict[str, Any]
    derived: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


class InputComponent(Protocol):
    """Component contract for deterministic input parsing and derivation."""

    def parse(self, input_request: InputRequest) -> InputResult:
        ...


@dataclass
class SandboxResult:
    """Output of the sandbox create stage."""

    skipped: bool
    skip_reason: str | None = None
    error: str | None = None
    container_name: str = ""
    container_id: str = ""
    image: str = ""


@dataclass
class PatchApplyResult:
    """Output of the patch-apply stage."""

    skipped: bool
    skip_reason: str | None = None
    error: str | None = None
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    log_path: str = ""
    source: str = ""
    patch_applied: bool = False


@dataclass
class SandboxCreateRequest:
    """Input payload for sandbox creation."""

    repo_root: Path
    run_id: str
    skip: bool = False


@dataclass
class PatchApplyRequest:
    """Input payload for sandbox patch application."""

    repo_root: Path
    container_name: str
    patch_section: dict[str, Any]
    skip: bool = False


@dataclass
class SetupApplyRequest:
    """Input payload for sandbox pre-state setup (run before the pre-phase)."""

    repo_root: Path
    container_name: str
    sandbox_state: dict[str, Any]
    skip: bool = False


@dataclass
class SetupApplyResult:
    """Output of the sandbox setup stage."""

    skipped: bool
    skip_reason: str | None = None
    error: str | None = None
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    log_path: str = ""
    source: str = ""
    setup_applied: bool = False


class SandboxComponent(Protocol):
    """Component contract for sandbox lifecycle, pre-state setup, and patch application."""

    def create(self, request: SandboxCreateRequest) -> SandboxResult:
        ...

    def apply_setup(self, request: SetupApplyRequest) -> SetupApplyResult:
        ...

    def apply_patch(self, request: PatchApplyRequest) -> PatchApplyResult:
        ...


@dataclass
class DiffResult:
    """Output of the diff stage."""

    skipped: bool
    skip_reason: str | None = None
    counts: dict[str, int] = field(default_factory=dict)
    net_change: int = 0
    regression_detected: bool = False
    regressed_count: int = 0
    fixed_count: int = 0
    verified_count: int = 0
    verification_failed_count: int = 0
    transitions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class EvaluationInput:
    """Input payload for the evaluation component."""

    pre_checks: list[dict[str, Any]] = field(default_factory=list)
    post_checks: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class EvaluationResult:
    """Output of the evaluation component (DiffResult-compatible)."""

    skipped: bool
    skip_reason: str | None = None
    counts: dict[str, int] = field(default_factory=dict)
    net_change: int = 0
    regression_detected: bool = False
    regressed_count: int = 0
    fixed_count: int = 0
    verified_count: int = 0
    verification_failed_count: int = 0
    transitions: list[dict[str, Any]] = field(default_factory=list)


class EvaluationComponent(Protocol):
    """Component contract for deterministic pre/post check evaluation."""

    def evaluate(self, evaluation_input: EvaluationInput) -> EvaluationResult:
        ...


@dataclass
class TestSuiteRequest:
    """Input for TestSuite normalization and phase-based collection."""

    pre_checks: list[dict[str, Any]] | None = None
    post_checks: list[dict[str, Any]] | None = None
    phase: Literal["normalize", "pre", "post"] = "normalize"
    phase_checks: list[dict[str, Any]] | None = None
    runner: "TestSuiteRunner | None" = None
    phase_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestSuiteResult:
    """Normalized check lists for Evaluation, plus optional status fields."""

    pre_checks: list[dict[str, Any]] = field(default_factory=list)
    post_checks: list[dict[str, Any]] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)


class TestSuiteComponent(Protocol):
    """Component contract for producing normalized check records."""

    def run(self, request: TestSuiteRequest) -> TestSuiteResult:
        ...


class TestSuiteRunner(Protocol):
    """Swappable runner adapter contract for phase check execution."""

    def run_phase(self, phase: Literal["pre", "post"], context: dict[str, Any]) -> list[dict[str, Any]]:
        ...


@dataclass
class ClassifierResult:
    """Result payload from optional post-evaluation exception classification."""

    annotations: list[dict[str, Any]] = field(default_factory=list)
    raw: str = ""
    warnings: list[str] = field(default_factory=list)
    model: str = ""


class ExceptionClassifier(Protocol):
    """Optional classifier that annotates evaluation transitions."""

    def classify(
        self,
        transitions: list[dict[str, Any]],
        *,
        parsed_input: dict[str, Any],
    ) -> ClassifierResult:
        ...


@dataclass
class PipelineSnapshot:
    """Minimal end-to-end pipeline snapshot."""

    execution_phase: Literal["pre_patch", "post_patch"] = "pre_patch"
    parsed_input: ParsedInputResult | None = None
    sandbox: SandboxResult | None = None
    setup_apply: SetupApplyResult | None = None
    patch_apply: PatchApplyResult | None = None
    diff: DiffResult | None = None
    patch_verified: bool = False
    testsuite_messages: list[str] = field(default_factory=list)
    classified_transitions: list[dict[str, Any]] | None = None
