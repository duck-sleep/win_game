"""名称转发：编码器只在 `ns_rumble/vendor/` 里存一份，避免两处副本对不上。

被 `from a2h_encoder import …` 命中时，把自己换成真正的那个模块对象。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))      # 工程根

from ns_rumble.vendor import a2h_encoder as _real

sys.modules[__name__] = _real
