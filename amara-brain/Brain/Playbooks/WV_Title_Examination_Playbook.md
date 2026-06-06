# WV Title Examination Playbook
**Prepared by:** Scott Schufford | Aces N 8s  
**Last updated:** 2026-06-05  
**Applies to:** Texhoma Land Partners, EQT, 1809 Land Services, Purple Land Management  

---

## Prerequisites

| Tool | Location | Notes |
|---|---|---|
| TLC VPN | System Preferences → Network | Creds in Mac Keychain: Texhoma-VPN |
| SMB share | /Volumes/DATA/ | Auto-mounts when VPN connects |
| OR Excel template | Marcus 3-sheet format | sheets: [parcel], Index, Map |

---

## Step-by-Step Workflow

### Step 1 — Connect TLC VPN
- System Preferences → Network → select Texhoma VPN
- Credentials stored in Mac Keychain as **Texhoma-VPN**
- Verify: ping WVDATA.TEXHOMALP.COM responds

### Step 2 — Mount SMB Share
- `/Volumes/DATA/` auto-mounts when VPN connects
- If not: Finder → Go → Connect to Server → `smb://WVDATA.TEXHOMALP.COM/DATA`
- Search DOC Library folder for any existing docs on the parcel

### Step 3 — Get Owner Name from Parcel Number
- **mapwv.gov/parcel** → Parcel Attributes → select county → enter parcel number
- Copy the owner name exactly as shown

### Step 4 — Search County IDX

**Harrison County:**
- URL: `lookup.harrisoncountywv.com` ← CORRECT
- ~~harrison.countyclerk.us~~ ← WRONG — returns no results
- Search type: **Individual**
- Enter owner **last name** (e.g., "Shuttleworth", "Burns")
- Filter to **DEED** type → pull all instruments oldest → newest

### Step 5 — Tax Data
- `harrisoncountyassessor.com` → search by owner name or parcel
- Note assessed owner, interest %, acreage

### Step 6 — Oil & Gas Wells
- `tagis.dep.wv.gov/oog/` → search by **county + district**
- ⚠ Do NOT search by parcel ID — TAGIS parcel ID search fails silently
- If zero results: use **coordinate radius search** around parcel centroid
- Zero confirmed wells = COMPLETE for WS (White Space) tracts

### Step 7 — WVGES Records (needs Texhoma VPN DNS)
- `wvgs.wvnet.edu/pipe2/OGWISHelp.aspx` — requires VPN DNS
- Fallback: `wvgs.wvu.edu/oil-and-gas/oil-and-gas-well-information-system`

### Step 8 — Build Chain of Title
- Order oldest → newest
- Flag mineral reservations (look for "RESERVING", "EXCEPTING", "SAVING AND EXCEPTING")
- Flag split estates (surface ≠ mineral owner after reservation)
- Note fiduciary instruments — run heir name searches for each heir listed

### Step 9 — Title Flags to Check

| Flag | What to Check | Action Required |
|---|---|---|
| Split estate | "Reserving" / "Excepting" minerals in deed | Pull deed, read full reservation language |
| Heir interest | Estate or fiduciary instrument | Run name search for ALL heirs in IDX |
| CBM inclusion | Post-1990 mineral deeds | Confirm CBM explicitly conveyed |
| Antero acreage | Elk / Harrison / Doddridge / Ritchie | Note proximity — affects acquisition value |
| TAGIS zero wells | Parcel ID search returned 0 | Rerun with coordinate radius search |

### Step 10 — Populate Marcus OR Format
Three sheets only:
1. **[parcel-id]** — full OR: header, surface, title, mineral owners, WI, leasehold, production, notes, tax
2. **Index** — chain of title table oldest → newest
3. **Map** — maps placeholder (embed Keller.jpg, Selection.pdf, WellSpot.pdf)

Branding on every sheet: **Prepared by Scott Schufford | Aces N 8s**

### Step 11 — Deliver
- **Dropbox:** Upload to **Elk Turn-in folder** (shared by mntstrunk@gmail.com)
- **Email:** mntstrunk@gmail.com — parcel ID, acreage, interest, key findings

---

## Common Errors & Fixes

| Error | Cause | Fix |
|---|---|---|
| IDX returns no results | Searched by parcel number | Switch to Individual name search |
| wvgs.wvnet.edu DNS fail | Texhoma VPN not connected | Connect VPN |
| TAGIS zero wells | Parcel ID search bug | Use coordinate radius search |
| /Volumes/DATA/ not mounted | VPN disconnected | Reconnect VPN, wait ~5s |
| .DS_Store in upload | macOS metadata | Exclude — harmless but unprofessional |

---

## Output Branding

All client-facing output:
> **Prepared by: Scott Schufford | Aces N 8s**

Never reference internal system names in deliverables.

---

## Parcels Worked

| Parcel | County | Client | Key Finding | Date |
|---|---|---|---|---|
| 11-409-19 | Harrison WV | Texhoma / Marcus Strunk | Split estate 1903 — 1/6 O&G Master Mineral Holdings — 3 adjacent wells | 2026-06-05 |
