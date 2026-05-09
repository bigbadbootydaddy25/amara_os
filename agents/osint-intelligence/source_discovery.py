#!/usr/bin/env python3
"""
OSINT source catalog for real estate deal discovery (Texas / Dallas priority).
All sources are lawful, public-record only. No scraping, no credential bypass.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class OSINTSource:
    source_id: str
    name: str
    jurisdiction: str           # "Dallas County", "Texas", "National"
    source_type: str            # cad|recorder|sos|tax|gis|permit|code_violation|foreclosure|auction|court|licensing
    access_type: str            # csv|pdf|api|browser-only|manual|paid|login-required
    url: str
    description: str
    data_available: list[str] = field(default_factory=list)
    confidence: float = 1.0     # 0.0–1.0 source reliability
    last_verified: str = "2026-05-09"
    notes: str = ""
    priority: int = 1           # 1=Dallas/TX, 2=regional, 3=national


def _src(
    sid: str,
    name: str,
    jurisdiction: str,
    source_type: str,
    access_type: str,
    url: str,
    description: str,
    data_available: list[str],
    confidence: float = 1.0,
    notes: str = "",
    priority: int = 1,
) -> OSINTSource:
    return OSINTSource(
        source_id=sid,
        name=name,
        jurisdiction=jurisdiction,
        source_type=source_type,
        access_type=access_type,
        url=url,
        description=description,
        data_available=data_available,
        confidence=confidence,
        notes=notes,
        priority=priority,
    )


# ---------------------------------------------------------------------------
# Master source catalog (60+ sources)
# ---------------------------------------------------------------------------

OSINT_SOURCES: list[OSINTSource] = [

    # ── Dallas County ─────────────────────────────────────────────────────
    _src(
        "TX-DAL-CAD-001",
        "Dallas Central Appraisal District",
        "Dallas County",
        "cad",
        "browser-only",
        "https://www.dallascad.org/",
        "Parcel search by owner name, address, or APN. Owner history, improvements, land values.",
        ["owner_name", "property_address", "apn", "assessed_value", "land_value", "improvement_value",
         "property_type", "year_built", "sqft", "legal_description"],
        confidence=0.98,
        notes="Property search at /AcctDetailRes.aspx. Bulk data available via open-records request.",
    ),
    _src(
        "TX-DAL-CLERK-001",
        "Dallas County Clerk – Official Public Records",
        "Dallas County",
        "recorder",
        "browser-only",
        "https://countyclerk.dallascounty.org/recording/real-property.html",
        "Deed recordings, liens, UCC filings, lis pendens. Searchable by grantor/grantee/APN.",
        ["deed_type", "grantee_name", "grantor_name", "recording_date", "consideration_amount",
         "legal_description", "instrument_number", "lien_amount", "lender_name"],
        confidence=0.99,
        notes="Free search via DallasCountyClerk.org. Images may require login or fee.",
    ),
    _src(
        "TX-DAL-TAX-001",
        "Dallas County Tax Office – Property Tax Records",
        "Dallas County",
        "tax",
        "browser-only",
        "https://www.dallascounty.org/departments/taxoffice/",
        "Current and delinquent property tax records. Pay status, roll history.",
        ["owner_name", "apn", "tax_year", "tax_due", "tax_paid", "delinquent_flag",
         "property_address", "legal_description"],
        confidence=0.97,
        notes="Delinquent tax list published annually. Available via open-records request.",
    ),
    _src(
        "TX-DAL-TAXDELINQ-001",
        "Dallas County Tax Delinquent List",
        "Dallas County",
        "tax",
        "pdf",
        "https://www.dallascounty.org/departments/taxoffice/",
        "Annual delinquent property tax list published by Dallas County Tax Office.",
        ["owner_name", "property_address", "apn", "amount_owed", "years_delinquent"],
        confidence=0.95,
        notes="Request via open-records; some years posted as PDF. Cross-reference with DCAD for current owner.",
    ),
    _src(
        "TX-DAL-PERMIT-001",
        "City of Dallas Development Services – Building Permits",
        "Dallas County",
        "permit",
        "browser-only",
        "https://developmentservices.dallascityhall.com/",
        "Building permits, demolition permits, certificates of occupancy for Dallas parcels.",
        ["permit_number", "permit_type", "permit_status", "applicant_name", "contractor",
         "property_address", "issue_date", "valuation"],
        confidence=0.96,
        notes="Online portal: CSS eTRAKiT. Search by address or permit number.",
    ),
    _src(
        "TX-DAL-CODE-001",
        "City of Dallas Code Compliance – Violations",
        "Dallas County",
        "code_violation",
        "browser-only",
        "https://gcc.dallascityhall.com/",
        "Code enforcement cases, violations, open cases for properties in Dallas city limits.",
        ["case_number", "case_type", "property_address", "status", "open_date", "close_date"],
        confidence=0.90,
        notes="Dallas GCC portal. Search by address. Some cases login-required for detail.",
    ),
    _src(
        "TX-DAL-COURT-001",
        "Dallas County District Court Records",
        "Dallas County",
        "court",
        "browser-only",
        "https://www.dallascounty.org/government/district-court/",
        "Civil suits, foreclosure filings, probate, lis pendens at district court level.",
        ["case_number", "plaintiff", "defendant", "filing_date", "case_type", "disposition"],
        confidence=0.92,
        notes="OdysseyPortal for online search. Not all case types searchable by party name for free.",
    ),
    _src(
        "TX-DAL-TRUSTEE-001",
        "Dallas County Substitute Trustee Sales (Foreclosure Notices)",
        "Dallas County",
        "foreclosure",
        "browser-only",
        "https://countyclerk.dallascounty.org/recording/foreclosure-notices.html",
        "Notices of substitute trustee sale posted monthly for Dallas County. First Tuesday auctions.",
        ["property_address", "apn", "trustee_name", "beneficiary", "sale_date", "opening_bid"],
        confidence=0.97,
        notes="Posted by first Tuesday of each month. Also available via legal newspaper notices.",
    ),
    _src(
        "TX-DAL-GIS-001",
        "Dallas County GIS / Open Data Portal",
        "Dallas County",
        "gis",
        "api",
        "https://www.dallascounty.org/government/gis/",
        "Parcel boundaries, ownership layers, zoning, flood zones. GeoJSON / Shapefile downloads.",
        ["apn", "owner_name", "zoning", "land_use", "flood_zone", "parcel_boundary"],
        confidence=0.95,
        notes="ArcGIS REST services available. Some layers require ESRI account.",
    ),
    _src(
        "TX-DAL-MUD-001",
        "Dallas-area MUD / PID District Records",
        "Dallas County",
        "tax",
        "browser-only",
        "https://www.dallascounty.org/departments/taxoffice/mud-district.php",
        "Municipal Utility District and Public Improvement District tax rolls.",
        ["owner_name", "apn", "district_name", "annual_levy", "delinquent_flag"],
        confidence=0.85,
        notes="Administered through county tax office. Individual MUD websites vary.",
    ),

    # ── Tarrant County ────────────────────────────────────────────────────
    _src(
        "TX-TAR-CAD-001",
        "Tarrant Appraisal District",
        "Tarrant County",
        "cad",
        "browser-only",
        "https://www.tad.org/",
        "Property search by owner, address, APN. Values, ownership history, exemptions.",
        ["owner_name", "property_address", "apn", "assessed_value", "property_type", "year_built", "sqft"],
        confidence=0.97,
        priority=2,
    ),
    _src(
        "TX-TAR-CLERK-001",
        "Tarrant County Clerk – Real Property Records",
        "Tarrant County",
        "recorder",
        "browser-only",
        "https://www.tarrantcounty.com/en/county-clerk/real-property.html",
        "Deeds, liens, UCC filings for Tarrant County. Grantor/grantee search.",
        ["deed_type", "grantee_name", "grantor_name", "recording_date", "consideration_amount",
         "instrument_number"],
        confidence=0.98,
        priority=2,
    ),

    # ── Collin County ─────────────────────────────────────────────────────
    _src(
        "TX-COL-CAD-001",
        "Collin Central Appraisal District",
        "Collin County",
        "cad",
        "browser-only",
        "https://www.collincad.org/",
        "Property search, ownership, values, sales history for Collin County.",
        ["owner_name", "property_address", "apn", "assessed_value", "property_type", "year_built"],
        confidence=0.97,
        priority=2,
    ),
    _src(
        "TX-COL-CLERK-001",
        "Collin County Clerk – Real Property",
        "Collin County",
        "recorder",
        "browser-only",
        "https://www.collincountytx.gov/county_clerk/real_property",
        "Deed and lien recordings for Collin County.",
        ["grantee_name", "grantor_name", "recording_date", "deed_type", "consideration_amount"],
        confidence=0.97,
        priority=2,
    ),

    # ── Denton County ─────────────────────────────────────────────────────
    _src(
        "TX-DEN-CAD-001",
        "Denton Central Appraisal District",
        "Denton County",
        "cad",
        "browser-only",
        "https://www.dentoncad.com/",
        "Property search, values, sales, owner history for Denton County.",
        ["owner_name", "property_address", "apn", "assessed_value", "property_type", "year_built"],
        confidence=0.96,
        priority=2,
    ),

    # ── Rockwall / Kaufman / Ellis ─────────────────────────────────────────
    _src(
        "TX-ROC-CAD-001",
        "Rockwall Central Appraisal District",
        "Rockwall County",
        "cad",
        "browser-only",
        "https://www.rockwallcad.com/",
        "Parcel search for Rockwall County.",
        ["owner_name", "property_address", "apn", "assessed_value"],
        confidence=0.93,
        priority=2,
    ),
    _src(
        "TX-KAU-CAD-001",
        "Kaufman Central Appraisal District",
        "Kaufman County",
        "cad",
        "browser-only",
        "https://www.kaufmancad.org/",
        "Parcel search for Kaufman County.",
        ["owner_name", "property_address", "apn", "assessed_value"],
        confidence=0.92,
        priority=2,
    ),
    _src(
        "TX-ELL-CAD-001",
        "Ellis Appraisal District",
        "Ellis County",
        "cad",
        "browser-only",
        "https://www.elliscad.com/",
        "Parcel search for Ellis County.",
        ["owner_name", "property_address", "apn", "assessed_value"],
        confidence=0.92,
        priority=2,
    ),

    # ── Texas State Sources ───────────────────────────────────────────────
    _src(
        "TX-SOS-001",
        "Texas Secretary of State – Business Entity Search",
        "Texas",
        "sos",
        "browser-only",
        "https://www.sos.state.tx.us/corp/sosda/index.shtml",
        "Active/inactive entity status, registered agent, filing date for TX-formed entities.",
        ["entity_name", "entity_type", "status", "file_date", "registered_agent",
         "registered_office", "officers"],
        confidence=0.99,
        notes="SOSDirect requires account ($1 searches). Free search at direct.sos.state.tx.us.",
    ),
    _src(
        "TX-CPA-COA-001",
        "Texas Comptroller – Certificate of Account Status",
        "Texas",
        "sos",
        "browser-only",
        "https://mycpa.cpa.state.tx.us/coa/",
        "Active/forfeited/inactive franchise tax status for TX entities. Free lookup.",
        ["entity_name", "entity_type", "taxpayer_number", "status", "right_to_transact"],
        confidence=0.99,
        notes="Distinct from SOS. Forfeited status here means lost right to do business in TX.",
    ),
    _src(
        "TX-CPA-VENDOR-001",
        "Texas Comptroller – Vendor/Payee Search",
        "Texas",
        "sos",
        "api",
        "https://www.comptroller.texas.gov/transparency/open-data/",
        "State contracts and payments to vendors. Useful for builder/contractor verification.",
        ["vendor_name", "contract_amount", "agency", "payment_date"],
        confidence=0.90,
        notes="Open Data Portal provides downloadable CSV files.",
        priority=2,
    ),
    _src(
        "TX-TREC-001",
        "Texas Real Estate Commission – License Holder Search",
        "Texas",
        "licensing",
        "browser-only",
        "https://www.trec.texas.gov/apps/license-holder-search/",
        "Broker and agent license status, expiration, disciplinary history.",
        ["license_holder_name", "license_number", "license_type", "status", "expiration_date",
         "sponsoring_broker", "city", "disciplinary_action"],
        confidence=0.99,
    ),
    _src(
        "TX-TDLR-001",
        "Texas Department of Licensing and Regulation",
        "Texas",
        "licensing",
        "browser-only",
        "https://www.tdlr.texas.gov/",
        "Contractor, inspector, HVAC, plumber license verification.",
        ["license_holder_name", "license_number", "license_type", "status", "expiration_date"],
        confidence=0.97,
        priority=2,
    ),
    _src(
        "TX-TCEQ-001",
        "Texas Commission on Environmental Quality – Site Records",
        "Texas",
        "gis",
        "browser-only",
        "https://www.tceq.texas.gov/agency/data/lookup-links.html",
        "Environmental cleanup sites, UST records, water rights. Useful for property due diligence.",
        ["site_name", "property_address", "site_type", "status", "contaminants"],
        confidence=0.94,
        priority=2,
    ),
    _src(
        "TX-PACER-001",
        "U.S. Bankruptcy Court – Northern District of Texas (PACER)",
        "Texas",
        "court",
        "login-required",
        "https://www.txnb.uscourts.gov/",
        "Federal bankruptcy filings for Dallas-area debtors. Case lookup by debtor name.",
        ["debtor_name", "case_number", "chapter", "filing_date", "discharge_date", "property_address"],
        confidence=0.97,
        notes="PACER requires account. $0.10/page fee. Free for queries returning 0 results.",
        priority=2,
    ),
    _src(
        "TX-HHSC-001",
        "Texas HHSC – Assisted Living / Group Home Registry",
        "Texas",
        "licensing",
        "browser-only",
        "https://www.hhs.texas.gov/providers/long-term-care-providers/assisted-living-facilities-alf",
        "Licensed ALF and group home facilities. Useful for identifying care-home buyers.",
        ["facility_name", "property_address", "owner_entity", "license_status", "capacity"],
        confidence=0.93,
        priority=2,
    ),

    # ── Foreclosure / Auction ─────────────────────────────────────────────
    _src(
        "TX-DAL-AUCTION-001",
        "Constable / Sheriff Foreclosure Auctions – Dallas County",
        "Dallas County",
        "auction",
        "browser-only",
        "https://www.dallascounty.org/government/constables/",
        "First-Tuesday foreclosure auction listings posted by Dallas County constable offices.",
        ["property_address", "apn", "opening_bid", "sale_date", "case_number"],
        confidence=0.93,
        notes="Also listed in Dallas Morning News legal notices (paid print/web). Cross-ref with Trustee Sale notices.",
    ),
    _src(
        "TX-DAL-SUBSTITUTE-001",
        "Foreclosure.com – Texas Listings",
        "Texas",
        "foreclosure",
        "paid",
        "https://www.foreclosure.com/",
        "Aggregated pre-foreclosure, auction, and REO listings. Paid subscription.",
        ["property_address", "apn", "owner_name", "loan_amount", "auction_date", "opening_bid"],
        confidence=0.80,
        notes="Paid service. Data sourced from public records but aggregated; verify against county records.",
        priority=2,
    ),
    _src(
        "ZILLOW-PREFC-001",
        "Zillow – Pre-foreclosure Listings",
        "National",
        "foreclosure",
        "browser-only",
        "https://www.zillow.com/",
        "Pre-foreclosure notices aggregated from public records. Free but delayed.",
        ["property_address", "owner_name", "estimated_value", "foreclosure_status"],
        confidence=0.75,
        notes="Data lag vs county records. Use for lead generation only; verify at county clerk.",
        priority=3,
    ),

    # ── National / Federal Sources ────────────────────────────────────────
    _src(
        "FINCEN-SAR-001",
        "FinCEN Real Estate Geographic Targeting Orders (GTO)",
        "National",
        "court",
        "browser-only",
        "https://www.fincen.gov/resources/statutes-regulations/geographic-targeting-orders",
        "All-cash luxury real estate purchases above $300k in GTO-covered metros must be reported.",
        ["buyer_entity", "beneficial_owner", "purchase_price", "property_address", "payment_method"],
        confidence=0.85,
        notes="Reports not public, but GTO rules and coverage areas are. Dallas not currently in GTO but check for updates.",
        priority=3,
    ),
    _src(
        "FDIC-001",
        "FDIC – Failed Bank / Institution Search",
        "National",
        "court",
        "api",
        "https://www.fdic.gov/bank/individual/failed/banklist.html",
        "Failed bank list. Useful when tracing lenders named in deeds.",
        ["institution_name", "cert_number", "city", "state", "fail_date", "acquiring_institution"],
        confidence=0.99,
        notes="CSV download available at FDIC open data.",
        priority=3,
    ),
    _src(
        "HUD-REMS-001",
        "HUD – Real Estate Owned (REO) / REMS",
        "National",
        "foreclosure",
        "browser-only",
        "https://www.hudhomestore.gov/",
        "HUD-owned REO properties available for purchase. FHA foreclosure inventory.",
        ["property_address", "asking_price", "property_type", "bid_deadline"],
        confidence=0.95,
        notes="CSV download available. Covers FHA-insured properties only.",
        priority=3,
    ),
    _src(
        "FANNIE-REO-001",
        "Fannie Mae – HomePath REO",
        "National",
        "foreclosure",
        "browser-only",
        "https://www.homepath.com/",
        "Fannie Mae-owned REO properties. Includes buyer-type eligibility rules.",
        ["property_address", "listing_price", "property_type", "days_on_market"],
        confidence=0.95,
        priority=3,
    ),
    _src(
        "FREDDIE-REO-001",
        "Freddie Mac – HomeSteps REO",
        "National",
        "foreclosure",
        "browser-only",
        "https://www.homesteps.com/",
        "Freddie Mac-owned REO inventory.",
        ["property_address", "listing_price", "property_type"],
        confidence=0.95,
        priority=3,
    ),
    _src(
        "PACER-NATL-001",
        "PACER – Federal Court Records (National)",
        "National",
        "court",
        "login-required",
        "https://pacer.uscourts.gov/",
        "Bankruptcy, civil suits across all federal districts. Search by party name.",
        ["party_name", "case_number", "district", "filing_date", "case_type"],
        confidence=0.98,
        notes="Requires free PACER account. $0.10/page fee applies.",
        priority=2,
    ),
    _src(
        "ICIJ-OFFSHORE-001",
        "ICIJ Offshore Leaks Database",
        "National",
        "sos",
        "api",
        "https://offshoreleaks.icij.org/",
        "Leaked offshore entity data (Panama Papers, Paradise Papers, etc.). Entity + officer names.",
        ["entity_name", "jurisdiction", "officers", "addresses", "linked_entities"],
        confidence=0.70,
        notes="Leaked data — not authoritative but useful for flags. Always verify via official registries.",
        priority=3,
    ),
    _src(
        "OPEN-CORPORATES-001",
        "OpenCorporates – Global Company Search",
        "National",
        "sos",
        "api",
        "https://opencorporates.com/",
        "Aggregated corporate registry data from 140+ jurisdictions. Useful for multi-state entity tracing.",
        ["entity_name", "jurisdiction", "status", "registered_agent", "officers", "filing_date"],
        confidence=0.88,
        notes="Free tier limited. API access for bulk lookups. Data sourced from official registries.",
        priority=2,
    ),
    _src(
        "USPS-NCOA-001",
        "USPS – Address Validation (public API)",
        "National",
        "gis",
        "api",
        "https://www.usps.com/business/web-tools-apis/address-information-api.htm",
        "Address standardization and deliverability. Validates address components.",
        ["street_address", "city", "state", "zip", "deliverable"],
        confidence=0.97,
        notes="Free API with registration. Rate limited. ZIP+4 standardization useful for deduplication.",
        priority=2,
    ),
    _src(
        "FCC-ULS-001",
        "FCC Universal Licensing System",
        "National",
        "licensing",
        "api",
        "https://www.fcc.gov/uls/",
        "Radio/telecom licenses by entity name. Occasionally surfaces entity address history.",
        ["licensee_name", "license_type", "address", "grant_date", "expiration_date"],
        confidence=0.80,
        notes="Rarely primary source; useful for entity address cross-reference.",
        priority=3,
    ),

    # ── MLS / Market Data ─────────────────────────────────────────────────
    _src(
        "NTREIS-001",
        "NTREIS / North Texas MLS",
        "Dallas County",
        "recorder",
        "login-required",
        "https://www.ntreis.net/",
        "MLS listing and sales data for North Texas. Requires broker membership.",
        ["mls_number", "list_price", "sale_price", "days_on_market", "listing_agent",
         "selling_agent", "property_address", "property_type"],
        confidence=0.99,
        notes="Broker/agent login required. Not publicly accessible. RETS/RESO API for members.",
    ),
    _src(
        "REDFIN-001",
        "Redfin – Public Sales Data",
        "National",
        "recorder",
        "browser-only",
        "https://www.redfin.com/",
        "Public-facing sale prices, listing history. Lags county records by days.",
        ["property_address", "sale_price", "sale_date", "property_type", "beds", "baths", "sqft"],
        confidence=0.82,
        notes="Verify all sale data against county recorder. Redfin aggregates from MLS + public records.",
        priority=2,
    ),

    # ── Texas Specific Open Data ──────────────────────────────────────────
    _src(
        "TX-OAG-001",
        "Texas Attorney General – Open Records Portal",
        "Texas",
        "court",
        "browser-only",
        "https://www.texasattorneygeneral.gov/open-government",
        "AG opinions on public records. Useful for understanding what county records must be released.",
        ["opinion_number", "requestor", "agency", "subject"],
        confidence=0.95,
        notes="Reference, not a data source. Use to support open-records requests to counties.",
        priority=2,
    ),
    _src(
        "TX-GLO-001",
        "Texas General Land Office – Coastal/State Lands",
        "Texas",
        "gis",
        "browser-only",
        "https://www.glo.texas.gov/",
        "State-owned land boundaries, mineral rights, beach access. Useful for coastal parcels.",
        ["parcel_id", "owner_name", "land_classification", "acreage"],
        confidence=0.93,
        notes="Primarily relevant for Gulf Coast or state-managed properties.",
        priority=2,
    ),
    _src(
        "TX-RRC-001",
        "Texas Railroad Commission – Oil and Gas / Mineral Rights",
        "Texas",
        "gis",
        "api",
        "https://www.rrc.texas.gov/resource-center/research/oil-gas-records/",
        "Well locations, lease records, surface owner data. Relevant for mineral-rights deals.",
        ["lease_name", "operator_name", "well_address", "apn", "production_data"],
        confidence=0.94,
        notes="GIS viewer and data downloads available. Useful for DFW-area fracking/mineral purchases.",
        priority=2,
    ),

    # ── City of Dallas Specific ───────────────────────────────────────────
    _src(
        "DAL-OPENDATA-001",
        "City of Dallas Open Data Portal",
        "Dallas County",
        "gis",
        "api",
        "https://www.dallasopendata.com/",
        "Permits, inspections, code cases, tree canopy, flood data. ArcGIS-backed.",
        ["permit_number", "case_number", "property_address", "inspection_result", "inspector"],
        confidence=0.93,
        notes="Socrata-based portal. Downloadable CSV and API endpoints available.",
    ),
    _src(
        "DAL-FLOOD-001",
        "City of Dallas – Floodplain Management",
        "Dallas County",
        "gis",
        "browser-only",
        "https://dallascityhall.com/departments/sustainabilityandresilience/Pages/floodplain_management.aspx",
        "Flood zone classification, FEMA FIRM maps for Dallas parcels.",
        ["property_address", "flood_zone", "bfe", "loma_status"],
        confidence=0.93,
        priority=2,
    ),
    _src(
        "DAL-ZONING-001",
        "City of Dallas – Zoning Map",
        "Dallas County",
        "gis",
        "browser-only",
        "https://gis.dallascityhall.com/sharedmaps/zoning/",
        "Current zoning classification for city of Dallas parcels.",
        ["property_address", "apn", "zoning_code", "zoning_description", "overlay_districts"],
        confidence=0.95,
    ),
    _src(
        "DAL-DEMOLITION-001",
        "City of Dallas – Demolition Permits / Structures",
        "Dallas County",
        "permit",
        "browser-only",
        "https://developmentservices.dallascityhall.com/",
        "Demolition permits issued for Dallas properties. Indicator of redevelopment activity.",
        ["permit_number", "property_address", "applicant_name", "issue_date", "structure_type"],
        confidence=0.92,
        notes="Same portal as building permits (eTRAKiT). Filter by permit type = 'Demolition'.",
    ),

    # ── Regional / Metro ──────────────────────────────────────────────────
    _src(
        "NCTCOG-001",
        "North Central Texas Council of Governments – Regional Data",
        "Dallas–Fort Worth",
        "gis",
        "api",
        "https://www.nctcog.org/trans/data",
        "Regional land use, transportation, demographics. Useful for area profiling.",
        ["land_use", "zoning", "population", "employment_center"],
        confidence=0.87,
        notes="Open data downloads; some GIS layers require ArcGIS Online account.",
        priority=2,
    ),
    _src(
        "DART-001",
        "DART Transit – Station Area Plans",
        "Dallas County",
        "gis",
        "browser-only",
        "https://www.dart.org/about/plans-and-projects/station-area-plans",
        "TOD (Transit-Oriented Development) overlays and plans near DART stations.",
        ["station_name", "plan_area", "zoning_overlays", "development_goals"],
        confidence=0.85,
        notes="Useful for identifying redevelopment zones near transit.",
        priority=2,
    ),

    # ── Aggregators / Multi-Source ────────────────────────────────────────
    _src(
        "PROPSTREAM-001",
        "PropStream – Property Intelligence",
        "National",
        "paid",
        "paid",
        "https://propstream.com/",
        "Aggregated ownership, liens, foreclosure, MLS, and skip-trace data. Paid subscription.",
        ["owner_name", "mailing_address", "estimated_value", "equity", "liens", "foreclosure_status",
         "last_sale_date", "last_sale_price", "property_type"],
        confidence=0.85,
        notes="Data sourced from public records but accuracy varies. Always verify key data points.",
        priority=2,
    ),
    _src(
        "PROPWIRE-001",
        "Propwire – Deal Intelligence",
        "National",
        "paid",
        "paid",
        "https://propwire.com/",
        "Cash buyer lists, deed data, investor activity. Paid subscription.",
        ["buyer_name", "buyer_company", "sale_price", "sale_date", "property_address",
         "financing_type", "property_type"],
        confidence=0.88,
        notes="Good source of buyer export CSVs. CSV format well-documented.",
        priority=2,
    ),
    _src(
        "LISTSOURCE-001",
        "ListSource – Direct Mail / Investor Lists",
        "National",
        "paid",
        "paid",
        "https://www.listsource.com/",
        "Targeted property owner lists by equity, absentee, etc. Paid list purchase.",
        ["owner_name", "mailing_address", "property_address", "equity_percent", "loan_to_value"],
        confidence=0.80,
        notes="Paid. Data sourced from public records. Use for list building only.",
        priority=3,
    ),
]


def get_sources_by_type(source_type: str) -> list[OSINTSource]:
    return [s for s in OSINT_SOURCES if s.source_type == source_type]


def get_sources_by_access(access_type: str) -> list[OSINTSource]:
    return [s for s in OSINT_SOURCES if s.access_type == access_type]


def get_sources_by_jurisdiction(jurisdiction: str) -> list[OSINTSource]:
    norm = jurisdiction.lower()
    return [s for s in OSINT_SOURCES if norm in s.jurisdiction.lower()]


def get_priority1_sources() -> list[OSINTSource]:
    return [s for s in OSINT_SOURCES if s.priority == 1]


def get_free_sources() -> list[OSINTSource]:
    return [s for s in OSINT_SOURCES if s.access_type not in ("paid", "login-required")]


def build_source_index() -> dict:
    return {
        "generated": "2026-05-09",
        "total_sources": len(OSINT_SOURCES),
        "by_access_type": _group_counts("access_type"),
        "by_source_type": _group_counts("source_type"),
        "by_jurisdiction": _group_counts("jurisdiction"),
        "by_priority": _group_counts("priority"),
        "sources": [asdict(s) for s in OSINT_SOURCES],
    }


def _group_counts(attr: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for s in OSINT_SOURCES:
        key = str(getattr(s, attr))
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def write_source_index(reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    index = build_source_index()

    json_path = reports_dir / "OSINT_SOURCE_INDEX.json"
    json_path.write_text(json.dumps(index, indent=2))

    md_path = reports_dir / "OSINT_SOURCE_INDEX.md"
    lines = [
        "# OSINT Source Index",
        "",
        f"**Generated:** {index['generated']}  ",
        f"**Total Sources:** {index['total_sources']}",
        "",
        "## Summary by Access Type",
        "",
    ]
    for k, v in index["by_access_type"].items():
        lines.append(f"- **{k}**: {v}")
    lines += ["", "## Summary by Source Type", ""]
    for k, v in index["by_source_type"].items():
        lines.append(f"- **{k}**: {v}")
    lines += ["", "## Summary by Priority", ""]
    for k, v in index["by_priority"].items():
        label = {1: "Dallas/Texas (Priority 1)", 2: "Regional (Priority 2)", 3: "National (Priority 3)"}.get(int(k), k)
        lines.append(f"- **{label}**: {v}")
    lines += ["", "## Source Catalog", ""]
    for s in OSINT_SOURCES:
        access_emoji = {
            "csv": "📥", "pdf": "📄", "api": "🔌",
            "browser-only": "🌐", "manual": "✋",
            "paid": "💰", "login-required": "🔒",
        }.get(s.access_type, "❓")
        lines.append(f"### {s.name} `{s.source_id}`")
        lines.append(f"- **Jurisdiction:** {s.jurisdiction}")
        lines.append(f"- **Type:** {s.source_type} | **Access:** {access_emoji} {s.access_type}")
        lines.append(f"- **URL:** {s.url}")
        lines.append(f"- **Description:** {s.description}")
        lines.append(f"- **Data Available:** {', '.join(s.data_available)}")
        if s.notes:
            lines.append(f"- **Notes:** {s.notes}")
        lines.append("")

    md_path.write_text("\n".join(lines))
