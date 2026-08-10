from pathlib import Path

p = Path(r"D:\new-project-fe\apps\web\src\app\(platform)\platform\orgs\page.tsx")
t = p.read_text(encoding="utf-8")
if "/controls" in t:
    print("already linked")
    raise SystemExit(0)
if 'from "next/link"' not in t and "from 'next/link'" not in t:
    t = t.replace(
        '"use client";\n\nimport { useMemo } from "react";',
        '"use client";\n\nimport Link from "next/link";\nimport { useMemo } from "react";',
    )
needle = '{ id: "name", header: "Organization", cell: (r) => r.name ?? r.org_name ?? r.id },'
if needle not in t:
    print("needle missing")
    raise SystemExit(1)
t = t.replace(
    needle,
    needle
    + """
    {
      id: "controls",
      header: "Controls",
      cell: (r) => (
        <Link className="text-primary underline" href={`/platform/orgs/${r.id}/controls`}>
          Configure
        </Link>
      ),
    },""",
)
p.write_text(t, encoding="utf-8")
print("linked")
