#!/usr/bin/env python3
"""Replace the legacy Heyzap iOS bridge with inert ABI-compatible functions."""
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
project = root / "Unity-iPhone.xcodeproj" / "project.pbxproj"
bridge = root / "Libraries/Plugins/Heyzap Plugin/Assets/Plugins/iOS/Heyzap/HeyzapUnityAds.mm"
if not project.is_file() or not bridge.is_file():
    raise SystemExit("Legacy Heyzap project or bridge not found")

source = bridge.read_text(encoding="utf-8")
block = source.split('extern "C" {', 1)
if len(block) != 2:
    raise SystemExit("Heyzap bridge has an unexpected layout")
pattern = re.compile(r"(?m)^\s*(void|bool|BOOL|char\s*\*)\s+(hz_\w+)\s*\(([^{}]*)\)\s*\{")
functions = pattern.findall(block[1])
if len(functions) < 30 or not any(name == "hz_ads_start_app" for _, name, _ in functions):
    raise SystemExit("Could not identify the expected Heyzap native functions")

lines = ['#include <stdbool.h>', '#include <string.h>', '#include <objc/objc.h>',
         'typedef int HZAdOptions;', '@class NSString;', 'extern "C" {']
for result, name, arguments in functions:
    if result == "void":
        body = ""
    elif result in ("bool", "BOOL"):
        body = "return 0;"
    else:
        body = 'return strdup("{}");'
    lines.append(f'{result} {name}({arguments}) {{ {body} }}')
lines.append('}')
bridge.write_text('\n'.join(lines) + '\n', encoding="utf-8")

text = project.read_text(encoding="utf-8")
text, count = re.subn(r'(?m)^[ \t]*[A-F0-9]{24} /\* libHeyzapAds\.a in Frameworks \*/,\s*$', '', text)
if count != 1:
    raise SystemExit(f"Expected one Heyzap link entry; found {count}")
# The package sometimes references the logging variant without exporting it.
# Keep the normal FMOD library, which is required for audio.
fmod_debug = root / "Libraries/Plugins/FMOD/platforms/ios/lib/libfmodstudiounitypluginL.a"
if not fmod_debug.is_file():
    text, removed = re.subn(r'(?m)^[ \t]*[A-F0-9]{24} /\* libfmodstudiounitypluginL\.a in Frameworks \*/,\s*$', '', text)
    print(f"Removed missing FMOD logging library entries: {removed}")

# This file only imports ad mediation frameworks. Legacy ads are disabled above,
# so compiling those imports is unnecessary and fails with current iOS SDKs.
imports = root / "Libraries/Plugins/Heyzap Plugin/Assets/Plugins/iOS/Heyzap/HZMediationImports.m"
if imports.is_file():
    imports.write_text("// Legacy ad mediation imports are disabled for iOS.\n", encoding="utf-8")
project.write_text(text, encoding="utf-8")
print(f"Disabled legacy Heyzap library; installed {len(functions)} iOS bridge stubs")
