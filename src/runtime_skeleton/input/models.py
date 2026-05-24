from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MetaSection(BaseModel):
    model_config = ConfigDict(extra="allow")
    run_id: str = "unknown"
    sections_present: list[str] = Field(default_factory=list)


class PatchSection(BaseModel):
    model_config = ConfigDict(extra="allow")
    raw_yaml: str | None = None
    plays: list[dict[str, Any]] = Field(default_factory=list)


class DiffEntry(BaseModel):
    model_config = ConfigDict(extra="allow")
    path: str


class DiffSection(BaseModel):
    model_config = ConfigDict(extra="allow")
    added: list[DiffEntry] = Field(default_factory=list)
    modified: list[DiffEntry] = Field(default_factory=list)
    removed: list[DiffEntry] = Field(default_factory=list)
    errors: list[DiffEntry] = Field(default_factory=list)


class ScoredPath(BaseModel):
    model_config = ConfigDict(extra="allow")
    path: str
    score: float | None = None


class SensitivityVerdict(BaseModel):
    model_config = ConfigDict(extra="allow")
    verdict: str = "unknown"
    scored_files: list[ScoredPath] = Field(default_factory=list)


class PredictedPath(BaseModel):
    model_config = ConfigDict(extra="allow")
    path: str


class PredictedImpact(BaseModel):
    model_config = ConfigDict(extra="allow")
    files: list[PredictedPath] = Field(default_factory=list)


class SandboxStatePackage(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    version: str | None = None


class SandboxStateFile(BaseModel):
    model_config = ConfigDict(extra="allow")
    path: str
    content: str = ""
    mode: str | None = None
    owner: str | None = None


class SandboxStateService(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    state: str | None = None
    enabled: bool | None = None


class SandboxStateUser(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    uid: int | None = None


class SandboxStateSection(BaseModel):
    """Pre-existing machine state to initialize in the sandbox before the pre-phase runs.

    Use ``profile`` to select a named Docker image preset (see IMAGE_PROFILES in
    sandbox/config.py). Packages, files, services, and users are applied via an
    auto-generated Ansible setup playbook.
    """
    model_config = ConfigDict(extra="allow")
    profile: str | None = None
    packages: list[SandboxStatePackage] = Field(default_factory=list)
    files: list[SandboxStateFile] = Field(default_factory=list)
    services: list[SandboxStateService] = Field(default_factory=list)
    users: list[SandboxStateUser] = Field(default_factory=list)


class InputDocument(BaseModel):
    model_config = ConfigDict(extra="allow")
    schema_version: str
    meta: MetaSection
    patch: PatchSection
    diff: DiffSection
    sensitivity_verdict: SensitivityVerdict
    predicted_impact: PredictedImpact
    apply: dict[str, Any] = Field(default_factory=dict)
    sandbox_state: SandboxStateSection = Field(default_factory=SandboxStateSection)


class DerivedSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: str
    diff_added_paths: list[str] = Field(default_factory=list)
    diff_modified_paths: list[str] = Field(default_factory=list)
    diff_removed_paths: list[str] = Field(default_factory=list)
    diff_error_paths: list[str] = Field(default_factory=list)
    high_sensitivity_paths: list[str] = Field(default_factory=list)
    predicted_not_materialized: list[str] = Field(default_factory=list)
    materialized_not_predicted: list[str] = Field(default_factory=list)
