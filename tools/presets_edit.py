"""Set preset values without hand-editing JSON, and keep the file one key per line.

usage: python tools/presets_edit.py species key=json_value [key=json_value ...]
       python tools/presets_edit.py --format
"""
import json
import pathlib
import sys

PATH = pathlib.Path(__file__).resolve().parents[1] / "presets" / "species.json"


def dump(data):
    lines = ["{"]
    blocks = []
    for name, preset in data.items():
        if not isinstance(preset, dict):
            blocks.append(f"  {json.dumps(name)}: {json.dumps(preset)}")
            continue
        inner = ",\n".join(f"    {json.dumps(k)}: {json.dumps(v)}" for k, v in preset.items())
        blocks.append(f"  {json.dumps(name)}: {{\n{inner}\n  }}")
    lines.append(",\n".join(blocks))
    lines.append("}")
    return "\n".join(lines) + "\n"


data = json.loads(PATH.read_text(encoding="utf-8"))
if sys.argv[1] != "--format":
    preset = data[sys.argv[1]]
    for arg in sys.argv[2:]:
        key, value = arg.split("=", 1)
        preset[key] = json.loads(value)
PATH.write_text(dump(data), encoding="utf-8")
print("saved", PATH.name)
