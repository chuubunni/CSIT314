"""Simple, explainable colour-based image analysis. No trained AI model."""
import io
import math
import warnings
from collections import Counter
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 5 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 12_000_000

# Names, colour cues and explanations are deliberately centralised for a demo.
STYLE_RULES = {
    'Scandinavian': ('bright', 'muted', 'Light colours and soft, natural tones'),
    'Japandi': ('bright', 'warm', 'Warm neutral tones and natural wood colours'),
    'Minimalist': ('bright', 'muted', 'Clean, pale neutral colours'),
    'Coastal': ('bright', 'cool', 'Airy light colours with blue tones'),
    'Industrial': ('dark', 'muted', 'Dark grey, black and earthy tones'),
    'Luxury': ('dark', 'rich', 'Deep colours and contrasting tones'),
    'Rustic': ('mid', 'warm', 'Warm brown and earthy tones'),
    'Traditional': ('mid', 'warm', 'Warm classic tones'),
    'Modern': ('mid', 'muted', 'Balanced, restrained colours'),
    'Contemporary': ('mid', 'rich', 'Balanced colour with stronger accents'),
}


def prepare_image(raw, filename='image.jpg'):
    """Validate actual bytes, guard dimensions, strip metadata and return PNG bytes."""
    if not raw:
        raise ValueError('Choose a JPG or PNG picture first.')
    if len(raw) > MAX_BYTES:
        raise ValueError('Picture exceeds the 5 MB limit.')
    if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        raise ValueError('Only JPG and PNG pictures are accepted.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in ('PNG', 'JPEG'):
                    raise ValueError('The file is not a JPG or PNG image.')
                image.verify()
            with Image.open(io.BytesIO(raw)) as image:
                image.load()
                image = ImageOps.exif_transpose(image)
                if image.width * image.height > Image.MAX_IMAGE_PIXELS:
                    raise ValueError('The image dimensions are too large.')
                image.thumbnail((512, 512))
                clean = Image.new('RGB', image.size, 'white')
                if image.mode in ('RGBA', 'LA') or 'transparency' in image.info:
                    rgba = image.convert('RGBA')
                    clean.paste(rgba, mask=rgba.getchannel('A'))
                else:
                    clean.paste(image.convert('RGB'))
                buf = io.BytesIO()
                clean.save(buf, 'PNG', optimize=True)
                return buf.getvalue()
    except (UnidentifiedImageError, OSError, EOFError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise ValueError('The picture cannot be read or is unsafe.') from exc


def _cosine(a, b):
    dot = sum(x*y for x, y in zip(a, b))
    a_norm = math.sqrt(sum(x*x for x in a))
    b_norm = math.sqrt(sum(y*y for y in b))
    return max(0.0, min(1.0, dot/a_norm/b_norm)) if a_norm and b_norm else 0.0


def styles_for(brightness, saturation, red, green, blue):
    light = 'bright' if brightness >= .67 else 'dark' if brightness < .38 else 'mid'
    temperature = 'warm' if red > blue * 1.13 else 'cool' if blue > red * 1.12 else 'muted' if saturation < .34 else 'rich'
    # A neutral image can match bright minimal styles even if not warm/cool.
    scores = {}
    for name, (desired_light, desired_tone, _) in STYLE_RULES.items():
        value = .2 + (.45 if light == desired_light else 0) + (.35 if temperature == desired_tone else 0)
        if name in ('Scandinavian', 'Minimalist', 'Japandi') and brightness > .75 and saturation < .30:
            value += .15
        scores[name] = round(min(1., value), 3)
    return dict(sorted(scores.items(), key=lambda pair: (-pair[1], pair[0])))


class ImageAnalyser:
    def analyse(self, image_bytes):
        with Image.open(io.BytesIO(image_bytes)) as im:
            rgb = im.convert('RGB').resize((64, 64))
            pixels = list(rgb.get_flattened_data() if hasattr(rgb, "get_flattened_data") else rgb.getdata())
        count = len(pixels)
        r, g, b = [sum(px[i] for px in pixels) / (255*count) for i in range(3)]
        brightness = sum(max(px) for px in pixels) / (255*count)
        saturation = sum((max(px) - min(px)) / max(1, max(px)) for px in pixels) / count
        # Eight bins per colour channel: histogram has 24 values, independent of dimensions.
        bins = [0.] * 24
        palette = Counter()
        for px in pixels:
            for channel in range(3):
                bins[channel*8 + min(7, px[channel]//32)] += 1/count
            palette[tuple((v//64)*64 for v in px)] += 1
        return {
            'brightness': round(brightness, 5),
            'saturation': round(saturation, 5),
            'palette': [list(rgb) for rgb, _ in palette.most_common(4)],
            'styles': styles_for(brightness, saturation, r, g, b),
            'vector': [round(value, 6) for value in bins] + [round(brightness, 6), round(saturation, 6)],
        }


def rank_score(upload, indexed, project_categories=()):
    """70% visual similarity + 30% style compatibility, clamped to [0,100]."""
    visual = _cosine(upload['vector'], indexed['vector'])
    category_names = [str(name).strip() for name in project_categories]
    if category_names:
        style = max(upload['styles'].get(name, 0.) for name in category_names)
    else:
        style = sum(min(upload['styles'].get(name, 0.), weight) for name, weight in indexed['styles'].items())
    return round(100 * (.70 * visual + .30 * min(1., style)), 1)
