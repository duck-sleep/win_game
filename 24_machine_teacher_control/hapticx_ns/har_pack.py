"""名称转发：帧打包只在 `ns_rumble/vendor/` 里存一份（见同目录 a2h_encoder.py 的说明）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ns_rumble.vendor import har_pack as _real

sys.modules[__name__] = _real
