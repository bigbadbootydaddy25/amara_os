---
tags: [WV-title, Harrison-County, split-estate, mineral-deed, Texhoma]
parcel: 11-409-19
county: Harrison
state: WV
district: Elk-Outside
client: Texhoma Land Partners
preparer: Scott Schufford | Aces N 8s
run_date: 2026-06-05
status: COMPLETE
---

# Harrison County WV — Parcel 11-409-19 — Title Case Study

**Prepared by:** Scott Schufford | Aces N 8s  
**Client:** Texhoma Land Partners — Marcus Strunk RPL  
**Run date:** 2026-06-05  

---

## Parcel Details

| Field | Value |
|---|---|
| Parcel ID | 11-409-19 |
| District | Elk-Outside |
| County | Harrison |
| State | WV |
| Acres (deed) | 121.072 |
| Parcel Numbers | 17-11-0409-0019-0000 through -0003 |
| Description | Gnatty Creek watershed |

---

## Full Chain of Title

| # | Year | Book/Page | Type | Grantor | Grantee | Acres | Notes |
|---|---|---|---|---|---|---|---|
| 1 | 1874 | DB 57/238 | DEED | Davisson, Edgar M. | Monroe, Benjamin T. | 51 | Gnatty Creek |
| 2 | 1879 | DB 61/434 | DEED | Shuttleworth, S.A. | Monroe, B.T. | — | Romines Mills |
| 3 | 1884 | DB 68/329 | DEED | Bumgardner, Adam | Monroe, B.T. | 60 | |
| 4 | 1888 | DB 75/97 | DEED | Bumgardner, Adam | Monroe, B.T. | 10 | |
| 5 | 1899 | DB 109/403 | DEED | Thompson M.M. Commissioner | Shuttleworth, M.N. | — | Circuit Court |
| 6 | 1903 | DB 136/259 | DEED | Shuttleworth, M.N. & Lillie | Stewart, William A. | 121.5 | **⚠ RESERVED 1/2 MINERALS — SPLIT ESTATE** |
| 7 | 1919 | Fid Bk 10/247 | ESTATE | Shuttleworth Estate | 6 Heirs | — | Split among heirs |
| 8 | 2010 | BK 1441/1269 | MINERAL DEED | Burns, A. Dean (Exec. Kramer Estate) | Master Mineral Holdings Inc. | 121.072 | **VESTING — $11,137.50** |

---

## Key Findings

### Split Estate — DB 136/259 (1903)
- Shuttleworth conveyed surface to Stewart but **RESERVED 1/2 mineral interest**
- Creates split estate as of 1903 — surface and mineral estates legally separate
- *Toothman v. Courtney (1907 WV)*: minerals reserved in place, not merely royalty right
- Antero WV mineral reservation analysis required

### Vesting Instrument — BK 1441/1269 (2010)
- **Master Mineral Holdings Inc. (Texas corp)** holds undivided **1/6 O&G + CBM**
- Grantor: A. Dean Burns, Executor Estate of **Helen S. Kramer**
- Helen S. Kramer = Helen Shuttleworth (1 of 6 heirs from Fid Bk 10/247)
- Consideration: $11,137.50

### Production — Three Wells Found by Coordinate Radius Search
| API# | Operator | Spud | Status | Last Production |
|---|---|---|---|---|
| 47-033-01920 | Diversified Production LLC | 1978 | Active | 1,221 MCF 2024 |
| 47-033-04093 | Diversified Production LLC | 1995 | Active (adjacent) | 759 MCF 2024 |
| 47-033-05416 | Key Oil Company | 07/26/2010 | Active (N adjacent) | 2,254 MCF 2024 |

> Initial parcel ID search returned zero — TAGIS limitation. Corrected via coordinate radius search.

### Outstanding Research
- 5/6 remaining Shuttleworth heir shares (Lillie A., Lorene, Mary, Samuel, Betty Jane) — **NOT YET DOCUMENTED**
- Full language of DB 136/259 reservation needed
- Monroe → Shuttleworth conveyance path not yet documented

---

## Lessons Learned

1. **IDX URL**: `lookup.harrisoncountywv.com` — search by **Individual name**, NOT parcel number
2. **Property viewer**: `mapwv.gov/parcel` → Parcel Attributes → Harrison County → get owner name first
3. **VPN required**: `wvgs.wvnet.edu` only resolves via Texhoma VPN DNS
4. **SMB auto-mounts**: `/Volumes/DATA/` is available as soon as TLC VPN connects
5. **Zero wells ≠ error**: TAGIS parcel ID search fails silently — use coordinate radius search
6. **Split estate flag**: Check every deed for "reserving" or "excepting" language before 1970

---

## Search Workflow That Worked

```
1. Connect TLC VPN (System Preferences → Network → Texhoma-VPN)
2. /Volumes/DATA/ auto-mounts
3. mapwv.gov/parcel → Parcel Attributes → Harrison County → find owner name
4. lookup.harrisoncountywv.com → Individual → "Shuttleworth" or "Burns"
5. Filter to DEED type → pull all instruments by date
6. Build chain 1874→2010 — flag DB 136/259 reservation
7. WELL search: tagis.dep.wv.gov/oog/ by county+district (NOT parcel ID)
8. Coordinate radius search if parcel ID returns zero
9. Populate OR Excel (Marcus format — 3 sheets: parcel, Index, Map)
10. Upload to Elk Turn-in folder (mntstrunk@gmail.com Dropbox)
11. Email Marcus at mntstrunk@gmail.com
```

---

## Output Files

- `WS_11-409-19_OR_2026-06-04_CORRECTED.xlsx` — Marcus-format OR
- `WS_11-409-19_OR_2026-06-04/` — Package folder
- `DEED_NOTES_11-409-19.txt` — Run notes

---

## Related

- [[WV_Title_Examination_Playbook]]
