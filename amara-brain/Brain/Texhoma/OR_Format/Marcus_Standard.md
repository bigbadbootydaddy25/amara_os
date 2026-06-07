---
tags: [OR-format, Texhoma, Marcus-Strunk, excel, canonical]
namespace: Texhoma
path: OR_Format/Marcus_Standard
status: LOCKED
preparer: Scott Schufford | Aces N 8s
locked: 2026-06-07
applies_to: [Texhoma Land Partners, EQT, 1809 Land Services, Purple Land Management]
---

# Marcus Standard OR Format — Canonical Specification

**Locked by:** Scott Schufford | Aces N 8s  
**Date:** 2026-06-07  
**Template file:** `deed/templates/marcus_or_template.py`  
**Builder entry point:** `deed/build_marcus_or.py`

---

## Column Widths (exact — never change)

| Column | Width | Purpose |
|---|---|---|
| A | 8.664 | Row label / fraction / index |
| B | 36.664 | Description / owner name |
| C | 10.664 | Decimal interest |
| D | 13.0 | Gross acres anchor |
| E | 36.664 | Net acres / notes |
| F | 1.664 | Narrow spacer — never merged |

---

## Row Heights

| Context | Height |
|---|---|
| Default (all rows) | 12.75 |
| Title banner (row 1) | 21.0 |
| Section headers | 15.0 |
| Blank spacers | 6.0 |

---

## Merge Policy

- **Only A1:E1 is merged** (columns 1–5)
- Column F is always a narrow spacer — never included in any merge
- Section header rows: A:E merged
- Label-value rows: A = label, B:E merged for value

---

## Gross Acres Anchor — Row 24

Row 24 is the gross acres anchor row, always.

```
D24 = gross_acres (e.g. 121.072)
```

All mineral owner net-acres cells use the formula:

```
=Cxx*D$24
```

Where:
- `Cxx` = interest decimal in column C for that row (e.g. C25 = 0.166667 for 1/6)
- `D$24` = absolute reference to gross acres — updates automatically if gross acres changes

**Row layout that lands D24 at row 24:**
1. Title banner (row 1, h=21)
2. Preparer subtitle (row 2)
3. Blank (row 3)
4. PARCEL IDENTIFICATION header (row 4)
5–15. Eleven parcel fields (rows 5–15)
16. Blank (row 16)
17. SURFACE OWNER header (row 17)
18–21. Four surface fields (rows 18–21)
22. Blank (row 22)
23. MINERAL OWNERS header (row 23)
**24. Gross acres anchor row — D24 = gross_acres**

---

## 20 Sections (exact order)

| # | Section Name |
|---|---|
| 1 | PARCEL IDENTIFICATION |
| 2 | SURFACE OWNER |
| 3 | LEGAL DESCRIPTION |
| 4 | TITLE / VESTING |
| 5 | MINERAL OWNERS |
| 6 | ROYALTY OWNERS |
| 7 | WORKING INTEREST |
| 8 | LEASEHOLD |
| 9 | ASSIGNMENTS |
| 10 | ORRI |
| 11 | OGLs ON FILE |
| 12 | UNRELEASED OGLs / ENCUMBRANCES |
| 13 | PRODUCTION DATA |
| 14 | NOTES |
| 15 | ENVIRONMENTAL |
| 16 | EASEMENTS |
| 17 | MORTGAGES |
| 18 | TAX ASSESSMENT — SURFACE |
| 19 | TAX ASSESSMENT — OIL AND GAS |
| 20 | CERTIFICATION |

---

## 9 Assignment Fields (exact order)

| # | Field |
|---|---|
| 1 | GROSS ACRES |
| 2 | NRI |
| 3 | ORRI |
| 4 | ASSIGNOR |
| 5 | ASSIGNEE |
| 6 | DATE ASSIGNED |
| 7 | RECORDED |
| 8 | BOOK / PAGE |
| 9 | NOTES |

---

## Three Sheets

| Tab name | Content |
|---|---|
| `{parcel_id}` (e.g. "11-409-19") | Full OR — all 20 sections |
| `Index` | Chain of title table — 7 columns |
| `Map` | Map image placeholder |

---

## Production Data Format — Vertical per well

Each well gets its own vertical block:

```
API #             | 47-033-01920
OPERATOR          | Diversified Production LLC
SPUD DATE         | 1978
WELL STATUS       | Active
LAST REPORTED PROD| 1,221 MCF — 2024
DEP STATUS        | Active — no plugging date
```

Blank spacer between wells.

---

## Tax Assessment Format — Vertical label-value

```
ACCT NO      | 06056171
TICKET NO    | 0000037542
NAME         | Burns, L. Craig & Sue B.
DESCRIPTION  | 118 AC Stout Run — Elk-Outside
MAP / PARCEL | 409-0019
LAND VALUE   | $4,860
ANNUAL TAX   | $56.62
TAX YEAR     | 2025
STATUS       | PAID 08/22/2025
```

---

## Color Palette

| Color | Hex | Usage |
|---|---|---|
| Dark navy | 1A2035 | Section header background |
| Medium navy | 1F3864 | Table column header background |
| Gold | C8A855 | Section header text, banner text |
| White | FFFFFF | Standard text |
| Cream | F5F0E0 | Label cells, alternating rows |
| Amber | FFF2CC | Research required / flags |
| Green | D9F2DD | Vesting / confirmed instruments |
| Silver | D9D9D9 | Subtotal rows |

---

## Usage — New Parcel

```python
from deed.templates.marcus_or_template import build_workbook, DATA_SCHEMA

data = {
    "parcel_id":      "11-XXX-XX",
    "gross_acres":    XXX.XXX,
    # ... all DATA_SCHEMA fields
}

wb = build_workbook(data)
wb.save("output/WS_11-XXX-XX_OR_YYYY-MM-DD.xlsx")
```

See `deed/build_marcus_or.py` for the complete 11-409-19 reference implementation.

---

## Reference Parcel — 11-409-19

Parcel 11-409-19, Elk-Outside District, Harrison County WV was the first parcel
built with this format. All format decisions were verified against Marcus Strunk's
Example OR for parcel 11-389-13.

Key data points locked:
- Gross acres: 121.072 (D24)
- Chain: 16 instruments (1874–2010)
- Mineral owners: Master Mineral Holdings Inc. 1/6 + Shuttleworth heirs 5/6
- Surface owner: Burns, L. Craig & Sue B. (DB 1197/1258, 1989)
- Wells: 3 (coordinate-radius — TAGIS parcel-ID search broken in Elk-Outside)
- Tax: Ticket 0000037542, $56.62 PAID 08/22/2025

See: `amara-brain/Brain/WV_Title/Harrison_County_11-409-19.md`
