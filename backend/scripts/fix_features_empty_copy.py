from pathlib import Path

p = Path(r"D:\new-project-fe\apps\web\src\app") / "(platform)" / "platform" / "features" / "page.tsx"
t = p.read_text(encoding="utf-8")
t = t.replace(
    'description="Run migration 088 so platform.feature_catalog is seeded."',
    'description="API returned no features. Confirm GET /ops/platform/features is live (restart API after deploy) and migration 088 is applied."',
)
t = t.replace(
    'description="Run migration 088 so platform.ui_screen_registry matches product NAV."',
    'description="API returned no screens. Confirm GET /ops/platform/screens is live and migration 088 is applied."',
)
p.write_text(t, encoding="utf-8")
print("ok")
