from pathlib import Path
import re

p = Path(r"D:\new-project-fe\apps\web\src\hooks\use-platform-operator.ts")
t = p.read_text(encoding="utf-8")
t = t.replace(
    'queryKey: [...queryKeys.platformOperator.orgs(), "features"],',
    "queryKey: queryKeys.platformOperator.features(),",
)
t = t.replace(
    'queryKey: queryKeys.platformOperator.features().concat("screens"),',
    'queryKey: ["platform-operator", "screens"],',
)
t = t.replace(
    'queryKey: ["platform-operator", "support"]',
    "queryKey: queryKeys.platformOperator.support()",
)
t = t.replace(
    'queryKey: ["platform-operator", "activity"]',
    "queryKey: queryKeys.platformOperator.activity()",
)
t = t.replace(
    'queryKey: ["platform-operator", "recycle"]',
    "queryKey: queryKeys.platformOperator.recycle()",
)
p.write_text(t, encoding="utf-8")
print("hooks ok")

qk = Path(r"D:\new-project-fe\apps\web\src\lib\query-keys.ts")
qt = qk.read_text(encoding="utf-8")
if "screens: ()" not in qt:
    qt = qt.replace(
        'features: () => ["platform-operator", "features"] as const,',
        'features: () => ["platform-operator", "features"] as const,\n'
        '    screens: () => ["platform-operator", "screens"] as const,',
    )
    qk.write_text(qt, encoding="utf-8")

nav = Path(r"D:\new-project-fe\apps\web\src\config\nav-config.ts").read_text(encoding="utf-8")
hrefs = set(re.findall(r'href:\s*"([^"]+)"', nav))
rows = Path(r"D:\new_project\backend\scripts\_screen_seed_preview.txt").read_text(encoding="utf-8").strip().splitlines()
seed_paths = {r.split("\t")[1] for r in rows}
missing = sorted(hrefs - seed_paths)
print("nav", len(hrefs), "seed", len(seed_paths), "missing", missing)
with_feat = sum(1 for r in rows if not r.endswith("\tNone"))
print("with_feature", with_feat)
