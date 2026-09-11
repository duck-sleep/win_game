"""config_store.py — JSON 配置持久化。"""
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT = {
    "mode": "balanced",
    "gain": 0.67,
    "user_index": 0,
    "audio_device": None,
    "vibration_on": True,
    "custom_overrides": {
        "gate": 0.03, "band_scale": 0.7, "gamma": 3.0,
        "transient_vol": 0.5, "freq_win": 0.1, "amp_win": 0.04,
    },
    # 每个模式各自的频段增益(用户拖过哪个模式就记哪个,没记过的用预设)
    "mode_band_gains": {},
}


def load():
    cfg = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULT.items()}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                saved = json.load(f)
            for key, val in saved.items():
                if key == "custom_overrides" and isinstance(val, dict):
                    cfg["custom_overrides"].update(val)
                elif key == "mode_band_gains" and isinstance(val, dict):
                    cfg["mode_band_gains"].update(val)
                else:
                    cfg[key] = val
        except (json.JSONDecodeError, OSError):
            pass
    # 旧版单份 band_gains 迁移到当时所用模式的槽位
    legacy = cfg.pop("band_gains", None)
    if isinstance(legacy, list) and legacy:
        mode = cfg.get("mode", "balanced")
        cfg["mode_band_gains"].setdefault(mode, legacy)
    return cfg


def save(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except OSError:
        return False
