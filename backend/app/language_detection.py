import re
from typing import Optional


VI_DIACRITICS_REGEX = re.compile(
    r"[àáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
    r"ÀÁẢÃẠÂẦẤẨẪẬĂẰẮẲẴẶÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ]"
)

VI_COMMON_WORDS = {
    "nguoi", "khong", "nhung", "cua", "va", "dang", "mot", "anh", "co", "toi",
    "noi", "vao", "ra", "khi", "duoc", "la", "voi", "trong", "da", "cho", "nay", "do"
}


def detect_story_language(user_input: str = "", recent_text: str = "", world_config: dict = None) -> str:
    if world_config and isinstance(world_config, dict):
        cfg_lang = str(world_config.get("language", "")).strip().lower()
        if cfg_lang.startswith("vi"):
            return "vi"
        if cfg_lang.startswith("en"):
            return "en"

    if user_input:
        if VI_DIACRITICS_REGEX.search(user_input):
            return "vi"
        words = set(re.findall(r"[^\W\d_]+", user_input.lower()))
        if len(words & VI_COMMON_WORDS) >= 2:
            return "vi"

    if recent_text:
        if VI_DIACRITICS_REGEX.search(recent_text):
            return "vi"
        words = set(re.findall(r"[^\W\d_]+", recent_text.lower()))
        if len(words & VI_COMMON_WORDS) >= 2:
            return "vi"

    if world_config and isinstance(world_config, dict):
        config_text = " ".join([
            str(world_config.get("display_name", "")),
            str(world_config.get("story_thesis", "")),
            str(world_config.get("genre", "")),
            str(world_config.get("tone", ""))
        ])
        if VI_DIACRITICS_REGEX.search(config_text):
            return "vi"
        words = set(re.findall(r"[^\W\d_]+", config_text.lower()))
        if len(words & VI_COMMON_WORDS) >= 2:
            return "vi"

    return "en"
