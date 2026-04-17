import json
import os

_translations: dict[str, dict] = {}

def _load():
    locales_dir = os.path.join(os.path.dirname(__file__), '..', 'locales')
    for lang in ('ru', 'en', 'fa', 'tr', 'ar', 'kk', 'uz', 'ur', 'hi', 'id'):
        path = os.path.join(locales_dir, f'{lang}.json')
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                _translations[lang] = json.load(f)

_load()


def t(key: str, lang: str = 'ru', **kwargs) -> str:
    lang = lang if lang in _translations else 'ru'
    text = _translations[lang].get(key) or _translations['ru'].get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return text


def all_values(key: str) -> set:
    return {tr[key] for tr in _translations.values() if key in tr}


def detect_lang(tg_language_code: str | None) -> str:
    """Определяет язык из Telegram language_code, fallback — 'ru'."""
    if not tg_language_code:
        return 'ru'
    code = tg_language_code.split('-')[0].lower()
    return code if code in _translations else 'ru'
