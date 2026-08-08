"""Phase 0 repository-health tests."""

from unittest import TestCase

from financial_intelligence import __version__


class PackageHealthTests(TestCase):
    """Verify the deliberately minimal Phase 0 package surface."""

    def test_package_exposes_a_version(self) -> None:
        """The minimal package should be importable and versioned."""

        self.assertEqual(__version__, "0.1.0")
