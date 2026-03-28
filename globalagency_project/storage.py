import logging

from whitenoise.storage import CompressedManifestStaticFilesStorage


logger = logging.getLogger(__name__)


class ResilientCompressedManifestStaticFilesStorage(
    CompressedManifestStaticFilesStorage
):
    """
    Fall back to non-manifest static paths if the manifest is missing or invalid.

    This keeps production pages rendering instead of raising a 500 while we
    still benefit from hashed assets whenever collectstatic has run correctly.
    """

    def load_manifest(self):
        try:
            return super().load_manifest()
        except ValueError as exc:
            logger.warning(
                "Static files manifest could not be loaded; falling back to "
                "non-manifest static paths. Run collectstatic to restore "
                "hashed asset URLs. Error: %s",
                exc,
            )
            return {}, ""
