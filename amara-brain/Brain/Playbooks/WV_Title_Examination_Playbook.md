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
| OR Excel template | deed/output/ | 8-sheet workbook |

---

## Step-by-Step Workflow

### Step 1 — Connect TLC VPN
- Open System Preferences → Network → select Texhoma VPN
- Credentials are stored in Mac Keychain as **Texhoma-VPN**
- Verify connected: `ping WVDATA.TEXHOMALP.COM`

### Step 2 — Mount SMB Share
- `/Volumes/DATA/` auto-mounts when VPN is connected
- If not mounted: Finder → Go → Connect to Server → `smb://WVDATA.TEXHOMALP.COM/DATA`
- Search DOC Library folder for any existing docs on the parcel

### Step 3 — Get Owner Name from Parcel Number
- Go to **mapwv.gov/parcel**
- Click **Parcel Attributes**
- Select **Harrison County** (or target county)
- Enter parcel number → get current owner name

### Step 4 — Search Harrison County IDX
- **URL:** `lookup.harrisoncountywv.com` ← correct URL
- ~~harrison.countyclerk.us~~ ← WRONG — do not use
- Search type: **Individual**
- Enter owner **last name** (e.g., "Shuttleworth", "Burns")
- Filter results to **DEED** type
- Pull all instruments oldest → newest

### Step 5 — Tax Data
- Go to `harrisoncountyassessor.com`
- Search by owner name or parcel number
- Note: tax records show assessed owner, interest %, and acreage

### Step 6 — Oil & Gas Wells
- Go to `tagis.dep.wv.gov/oog/`
- Search by **county + district** (not parcel number)
- Example: Harrison County, Elk-Outside District
- Zero wells = COMPLETE for White Space (WS) tracts — this is a valid finding

### Step 7 — WVGES Well Records (requires Texhoma VPN DNS)
- `wvgs.wvnet.edu/pipe2/OGWISHelp.aspx` — requires VPN DNS to resolve
- Fallback: `wvgs.wvu.edu/oil-and-gas/oil-and-gas-well-information-system`

### Step 8 — Build Chain of Title
- Arrange instruments oldest → newest
- Flag mineral reservations (look for "RESERVING" or "EXCEPTING" language)
- Flag split estates (surface ≠ mineral owner)
- Note fiduciary instruments (estate settlements, executor deeds)

### Step 9 — Key Flags to Check
| Flag | Check | Action |
|---|---|---|
| Split estate | Deed has "reserving" or "excepting" minerals | Pull reservation deed, analyze language |
| Heir interest | Estate/fiduciary instrument | Run name searches for all heirs |
| CBM inclusion | Post-1990 mineral deeds | Confirm CBM explicitly listed |
| Antero acreage | Elk/Harrison/Doddridge/Ritchie | Note Antero proximity — affects value |

### Step 10 — Populate OR Excel
- 8 sheets: Summary, Chain Index, Vesting, Tax, Wells, DEP, Title Analysis, Map
- Summary sheet: OPINION OF RECORD — Prepared by Scott Schufford | Aces N 8s
- Green = vesting instrument | Amber = reservation/gap | Red = error

### Step 11 — Deliver
- **Dropbox:** Upload to **Elk Turn-in folder** (shared by mntstrunk@gmail.com)
- **Email:** mntstrunk@gmail.com — include parcel ID, acreage, interest, client

---

## Common Errors & Fixes

| Error | Cause | Fix |
|---|---|---|
| IDX returns no results | Searched by parcel number | Search by Individual name instead |
| wvgs.wvnet.edu DNS fail | Texhoma VPN not connected | Connect VPN — site requires TLC DNS |
| /Volumes/DATA/ missing | VPN disconnected | Reconnect VPN, wait 5s |
| Zero wells | Undrilled tract | Log as COMPLETE — valid WS finding |
| .DS_Store in upload | macOS metadata | Exclude .DS_Store from all uploads |

---

## Output Branding
All output prepared for external delivery must show:
> **Prepared by: Scott Schufford | Aces N 8s**

Never reference internal system names in client-facing documents.

---

## Parcel Examples Worked

| Parcel | County | Client | Key Finding | Date |
|---|---|---|---|---|
| 11-409-19 | Harrison WV | Texhoma / Marcus Strunk | Split estate 1903 — 1/6 O&G to Master Mineral Holdings | 2026-06-05 |
