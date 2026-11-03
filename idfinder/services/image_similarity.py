"""Local duplicate/near-duplicate screening; no external AI service or API key."""
import hashlib
import warnings
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from idfinder.controller.errors import ValidationError


class ImageSimilarity:
    MAX_PIXELS = 20_000_000
    MAX_BYTES = 15 * 1024 * 1024
    PHASH_LIMIT = 8
    DHASH_LIMIT = 12
    VERSION = 'phash-dhash-v1'

    @staticmethod
    def bits(values):
        return format(int(''.join('1' if v else '0' for v in values.ravel()), 2), '016x')

    @classmethod
    def fingerprint(cls, path):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(path) as source:
                    if source.format not in ('JPEG', 'PNG', 'GIF'):
                        raise ValidationError('Upload a JPEG, PNG or GIF image.')
                    if source.width * source.height > cls.MAX_PIXELS:
                        raise ValidationError('Image is too large: maximum 20 million pixels.')
                    if getattr(source, 'n_frames', 1) > 1:
                        raise ValidationError('Use a still image; animated images are not supported.')
                    source.load()
                    image = ImageOps.exif_transpose(source).convert('RGB')
                pixel_hash = hashlib.sha256(
                    str(image.size).encode() + image.tobytes()).hexdigest()
                gray = image.convert('L')
                small = np.asarray(gray.resize((32, 32), Image.Resampling.LANCZOS), dtype=float)
                # Orthonormal 2D DCT; only low-frequency structure is hashed.
                x = np.arange(32)
                transform = np.cos(np.pi * (2*x[None, :] + 1) * x[:, None] / 64)
                transform *= np.sqrt(2 / 32)
                transform[0] /= np.sqrt(2)
                low = (transform @ small @ transform.T)[:8, :8]
                phash = cls.bits(low > np.median(low.ravel()[1:]))
                diff = np.asarray(gray.resize((9, 8), Image.Resampling.LANCZOS))
                dhash = cls.bits(diff[:, 1:] > diff[:, :-1])
                return {'pixel_hash': pixel_hash, 'phash': phash, 'dhash': dhash,
                        'texture': float(small.std()), 'algorithm': cls.VERSION}
        except ValidationError:
            raise
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
                Image.DecompressionBombWarning) as error:
            raise ValidationError('The uploaded file is not a readable, supported image.') from error

    @classmethod
    def compare(cls, a, b):
        if a['pixel_hash'] == b['pixel_hash']:
            return {'score': 100.0, 'kind': 'Identical decoded image', 'phash_distance': 0, 'dhash_distance': 0}
        # Plain/low-detail images have ambiguous hashes. Only exact matches are
        # flagged for them, avoiding false alarms on unrelated solid colours.
        if min(a['texture'], b['texture']) < 5:
            return None
        pd = (int(a['phash'], 16) ^ int(b['phash'], 16)).bit_count()
        dd = (int(a['dhash'], 16) ^ int(b['dhash'], 16)).bit_count()
        if pd <= cls.PHASH_LIMIT and dd <= cls.DHASH_LIMIT:
            return {'score': round(100*(1-(pd+dd)/128), 1),
                    'kind': 'Possible near-duplicate', 'phash_distance': pd, 'dhash_distance': dd}
        return None