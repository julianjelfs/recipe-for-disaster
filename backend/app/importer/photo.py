"""Read a recipe from photos of a printed page, in the same shape an import produces."""

import anthropic

from app import config
from app.importer.normalise import RULES, NormaliseResult, Usage, ask

_PHOTO_INTRO = """\
You turn photos of a printed recipe page into a clean, concise recipe for a UK home cook.

Read only what is printed. Never invent ingredients, amounts or steps that aren't there, and if
something can't be read, leave it out rather than guess. A recipe may run across several photos,
given in page order.

"""

PHOTO_PROMPT = _PHOTO_INTRO + RULES


def read_photos(
    photos: list[tuple[str, str]],
    client: anthropic.Anthropic,
    model: str = config.PHOTO_MODEL,
    usage: Usage | None = None,
) -> NormaliseResult:
    """`photos` are (media_type, base64 data) pairs, in page order."""
    content: list[dict] = [
        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}
        for media_type, data in photos
    ]
    content.append({"type": "text", "text": "The recipe page is in the photos above." if len(photos) > 1 else "The recipe page is in the photo above."})
    return ask(PHOTO_PROMPT, content, client, model, usage, effort=config.PHOTO_EFFORT)
