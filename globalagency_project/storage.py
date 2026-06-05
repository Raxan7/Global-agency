import logging
from pathlib import Path

import cloudinary
from cloudinary_storage.storage import MediaCloudinaryStorage
from django.utils.deconstruct import deconstructible
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


@deconstructible
class PdfFriendlyCloudinaryStorage(MediaCloudinaryStorage):
    """
    Store regular images as Cloudinary image assets and office-style
    attachments as raw assets.

    PDFs are delivered through Cloudinary's image-style URL path so the existing
    template access pattern (`{{ document.file.url }}`) continues to work, while
    also preferring download behavior and auto quality for lighter delivery.
    """

    IMAGE_RESOURCE_EXTENSIONS = {
        '.avif',
        '.bmp',
        '.gif',
        '.heic',
        '.jpeg',
        '.jpg',
        '.pdf',
        '.png',
        '.svg',
        '.tif',
        '.tiff',
        '.webp',
    }

    def _get_resource_type(self, name):
        suffix = Path(name).suffix.lower()
        if suffix and suffix not in self.IMAGE_RESOURCE_EXTENSIONS:
            return 'raw'
        return 'image'

    def _save(self, name, content):
        public_id = super()._save(name, content)
        suffix = Path(name).suffix.lower()
        if suffix:
            return f'{public_id}{suffix}'
        return public_id

    def _public_id_for_api(self, name):
        suffix = Path(name).suffix.lower()
        if suffix:
            return name[: -len(suffix)]
        return name

    def delete(self, name):
        return super().delete(self._public_id_for_api(name))

    def url(self, name):
        normalized_name = self._prepend_prefix(name)
        resource = cloudinary.CloudinaryResource(
            normalized_name,
            default_resource_type=self._get_resource_type(name),
        )
        suffix = Path(name).suffix.lower()
        if suffix == '.pdf':
            return resource.build_url(flags='attachment', quality='auto')
        return resource.url
