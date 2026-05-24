"""Coverage taxonomy for generated test plans.

Defines seven coverage categories, a mapping from test_type → category,
a per-intent relevance table (used to flag ⚠️ blind spots), and helpers
for computing a per-run coverage summary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from aegis_test_generator.test_templates.schemas import TestCase
    from aegis_test_generator.planner.intent import PatchIntent

CoverageCategory = Literal[
    "package_integrity",
    "file_integrity",
    "file_content",
    "service_state",
    "network_posture",
    "identity",
    "command_behavior",
]

ALL_CATEGORIES: tuple[CoverageCategory, ...] = (
    "package_integrity",
    "file_integrity",
    "file_content",
    "service_state",
    "network_posture",
    "identity",
    "command_behavior",
)

TEST_TYPE_TO_CATEGORY: dict[str, CoverageCategory] = {
    "package_installed": "package_integrity",
    "package_absent": "package_integrity",
    "package_version": "package_integrity",
    "package_version_range": "package_integrity",
    "file_exists": "file_integrity",
    "file_absent": "file_integrity",
    "directory_exists": "file_integrity",
    "file_mode": "file_integrity",
    "file_mode_changed": "file_integrity",
    "file_owner": "file_integrity",
    "symlink_exists": "file_integrity",
    "binary_executable": "file_integrity",
    "content_contains": "file_content",
    "content_not_contains": "file_content",
    "content_changed": "file_content",
    "command_output_contains": "file_content",
    "service_running": "service_state",
    "service_enabled": "service_state",
    "port_listening": "network_posture",
    "user_exists": "identity",
    "group_exists": "identity",
    "command_succeeds": "command_behavior",
}

# Categories that should have at least one test for a given patch intent.
# A category absent from this mapping has no required coverage for that intent.
INTENT_REQUIRED_CATEGORIES: dict[str, list[CoverageCategory]] = {
    "install": ["package_integrity", "file_integrity"],
    "update": ["file_content", "package_integrity"],
    "remove": ["package_integrity", "file_integrity"],
    "configure": ["file_content"],
    "mixed": ["package_integrity", "file_integrity", "file_content"],
}


@dataclass
class CategoryStats:
    verify: int = 0
    guard: int = 0

    @property
    def total(self) -> int:
        return self.verify + self.guard


@dataclass
class CoverageSummary:
    stats: dict[CoverageCategory, CategoryStats] = field(default_factory=dict)
    gaps: list[CoverageCategory] = field(default_factory=list)

    def total_tests(self) -> int:
        return sum(s.total for s in self.stats.values())


def compute_coverage(
    tests: "list[TestCase]",
    *,
    patch_intent: "PatchIntent | None" = None,
) -> CoverageSummary:
    """Compute per-category verify/guard counts and flag blind-spot gaps."""
    stats: dict[CoverageCategory, CategoryStats] = {cat: CategoryStats() for cat in ALL_CATEGORIES}

    for tc in tests:
        cat = TEST_TYPE_TO_CATEGORY.get(tc.test_type)
        if cat is None:
            continue
        if tc.role == "verify":
            stats[cat].verify += 1
        else:
            stats[cat].guard += 1

    gaps: list[CoverageCategory] = []
    if patch_intent is not None:
        required = INTENT_REQUIRED_CATEGORIES.get(patch_intent.value, [])
        for cat in required:
            if stats.get(cat, CategoryStats()).total == 0:
                gaps.append(cat)

    return CoverageSummary(stats=stats, gaps=gaps)
