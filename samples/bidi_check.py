# -*- coding: utf-8 -*-
import bidi
out = []
out.append("version=" + str(getattr(bidi, "__version__", "?")))
try:
    from bidi.algorithm import get_display as g1
    out.append("algorithm.get_display('אבג') = " + repr(g1("אבג")))
except Exception as e:
    out.append("algorithm import err: " + repr(e))
try:
    from bidi import get_display as g2
    out.append("bidi.get_display('אבג') = " + repr(g2("אבג")))
except Exception as e:
    out.append("bidi import err: " + repr(e))
try:
    from bidi.algorithm import get_display as g1
    out.append("algorithm base_dir=R = " + repr(g1("אבג", base_dir="R")))
except Exception as e:
    out.append("base_dir err: " + repr(e))
open("samples/bidi_out.txt", "w", encoding="utf-8").write("\n".join(out))
print("done")
