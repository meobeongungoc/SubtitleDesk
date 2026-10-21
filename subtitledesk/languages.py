"""Shared language labels and API normalization."""
LANGUAGES = (
    ("Vietnamese", "vi"), ("English", "en"), ("Vietnamese + English", "vi,en"),
    ("Arabic", "ar"), ("Bulgarian", "bg"), ("Chinese", "zh-cn"),
    ("Croatian", "hr"), ("Czech", "cs"), ("Danish", "da"), ("Dutch", "nl"),
    ("Finnish", "fi"), ("French", "fr"), ("German", "de"), ("Greek", "el"),
    ("Hebrew", "he"), ("Hindi", "hi"), ("Hungarian", "hu"), ("Indonesian", "id"),
    ("Italian", "it"), ("Japanese", "ja"), ("Korean", "ko"), ("Malay", "ms"),
    ("Norwegian", "no"), ("Persian", "fa"), ("Polish", "pl"), ("Portuguese", "pt"),
    ("Portuguese (Brazil)", "pt-br"), ("Romanian", "ro"), ("Russian", "ru"),
    ("Serbian", "sr"), ("Slovak", "sk"), ("Slovenian", "sl"), ("Spanish", "es"),
    ("Swedish", "sv"), ("Thai", "th"), ("Turkish", "tr"), ("Ukrainian", "uk"),
    ("Urdu", "ur"),
)
LABEL_TO_CODE = dict(LANGUAGES)
CODE_TO_LABEL = {code: label for label, code in LANGUAGES}

def normalize_language(value):
    text = str(value or "").strip().casefold()
    names = {label.casefold(): code for label, code in LANGUAGES if "," not in code}
    names.update({"brazilian portuguese": "pt-br", "brazillian_portuguese": "pt-br",
                  "brazilian_portuguese": "pt-br", "zh": "zh-cn"})
    return names.get(text, text.replace("_", "-"))

def subdl_code(value):
    return {"zh-cn": "ZH", "pt-br": "BR"}.get(value, value.upper())
