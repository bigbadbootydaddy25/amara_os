# Best Foreclosure Intelligence Sources for Hedge-Fund Monitoring

**Report:** AMARA-AI Texas Foreclosure Intel  
**Focus:** Institutional Investor Activity, Market-Wide Foreclosure Intelligence, Feed-Based Data Approaches  
**Markets:** Harris County (Houston), Dallas County (Dallas), Tarrant County (Fort Worth / Arlington)  
**Date:** 2026-05-16  

---

## Executive Summary

Hedge funds and institutional investors operate in the Texas foreclosure market at a fundamentally different scale and strategy than individual wholesalers or pre-foreclosure investors. Their intelligence requirements go beyond "find a specific property to buy" — they need to understand:

1. **Market-wide foreclosure volume trends** — Are filings increasing or decreasing? By what percent month-over-month?
2. **Institutional buyer concentration** — Who else is buying at the courthouse steps? Are other funds accumulating in specific ZIPs?
3. **Portfolio-level acquisition pipeline** — What is the total universe of available inventory at any given time?
4. **Bid-to-cover ratios and third-party buyer activity** — Are properties selling to third parties at the courthouse, or are lenders taking them back (REO)?
5. **Data feed integration** — How do you pipe Texas foreclosure data into internal analytics platforms, risk models, or portfolio management systems?

This report covers the best sources for each of these use cases, with a focus on **feed-based vs. scrape-based approaches** and **investor activity indicators**.

---

## Feed-Based vs. Scrape-Based Approaches

### Feed-Based Approach (Preferred for Institutional Use)

A **data feed** delivers structured, pre-processed foreclosure records via API or scheduled data file delivery. Feed-based approaches are:
- Highly reliable and scalable
- Structured and schema-consistent
- Legally compliant with provider terms
- Compatible with institutional data pipelines, databases, and risk systems
- Typically subscription-priced at enterprise rates

**Best feed-based providers for Texas:** ATTOM Data, PropertyRadar API

### Scrape-Based Approach (For Free or Low-Cost Coverage)

A **scrape-based approach** extracts data from publicly accessible websites (trustee firm sites, county clerk sites) using automated HTTP requests and PDF parsing. Scrape-based approaches are:
- Lower cost (free or near-free data)
- Dependent on source website stability
- Require maintenance when source websites change
- Suitable for supplemental coverage or validation
- Appropriate for sources with no formal API (BDF Group, Mackie Wolf, county clerk sites)

**Best scrape-based targets:** BDF Group, Mackie Wolf, Buczek Enterprises, county clerk PDF portals, LOGS.org

For hedge-fund intelligence, the recommended architecture combines **ATTOM Data or PropertyRadar as the primary feed** with **scrape-based sources as validation and gap-filling** layers.

---

## Rank 1 — ATTOM Data Solutions

**Website:** https://www.attomdata.com  
**Source Type:** Foreclosure Platform — Institutional Data Feed  
**Counties Covered:** Harris, Dallas, Tarrant + all Texas counties  
**Verification Status:** VERIFIED  
**Cost:** Enterprise subscription — tiered by data volume and geography  
**Investor Intel Score:** 10/10  

### Why It's #1 for Hedge-Fund Intelligence

ATTOM Data is the gold standard for institutional-grade real estate data in the United States. For Texas foreclosure intelligence, ATTOM provides:

**Core Data Feeds Available:**
- Deed-of-trust foreclosure notice feed (all Texas counties, daily refresh)
- Auction event feed (scheduled trustee-sale events with status updates)
- Post-sale event feed (sold to third party vs. reverted to lender / REO)
- Property valuation (AVM) integrated with foreclosure records
- Ownership and lien position data
- Historical foreclosure trends (year-over-year, month-over-month)
- Neighborhood-level distressed property concentration data

**Hedge-Fund Specific Intelligence:**
- **Third-party buyer tracking** — ATTOM post-sale data identifies when a property sold to a third party at auction vs. reverted to the lender. Tracking third-party buyer entity names across multiple sales reveals institutional accumulation patterns.
- **Opening bid vs. sale price spread** — Identifying consistently winning bids above the opening bid in specific ZIPs signals active competition for inventory in those areas.
- **Volume trend feeds** — Month-over-month filing volume changes by county are a leading indicator of credit stress and future REO inventory.

**Integration:**
- Delivery via API, SFTP, or direct data warehouse integration
- JSON/CSV/XML schema options
- SLA-backed daily or near-real-time updates
- Historical backfill available

**Automation Method:** API  
**Automation Score:** 9/10  
**Blockers:** SUBSCRIPTION_WALL — enterprise pricing; contact ATTOM for institutional pricing

---

## Rank 2 — PropertyRadar

**Website:** https://www.propertyradar.com  
**Source Type:** Foreclosure Platform — API + Web Interface  
**Counties Covered:** Harris, Dallas, Tarrant + statewide TX  
**Verification Status:** VERIFIED  
**Cost:** Subscription — tiered; enterprise API available  
**Investor Intel Score:** 9/10  

### Why It's #2 for Hedge-Fund Intelligence

PropertyRadar combines the data depth of ATTOM with a more accessible interface and a strong API, making it practical for teams that need both automated data feeds and analyst-facing dashboards. For Texas hedge-fund operations, PropertyRadar offers:

**Core Capabilities:**
- Real-time trustee-sale notice monitoring across all Texas counties
- Unpaid balance data (critical for bid strategy modeling)
- Owner equity estimates (identifies over-encumbered vs. equity-rich properties)
- Property condition data (age, size, improvements)
- Neighborhood-level trend analysis
- Portfolio-level saved searches and export
- Daily alert triggers for new filings meeting defined criteria

**Hedge-Fund Specific Use Cases:**
- **Portfolio pipeline dashboard** — Track total upcoming trustee-sale inventory across the DFW and Houston markets simultaneously
- **Competitive bid analysis** — Identify properties where the opening bid is significantly below AVM value (high-margin opportunities)
- **Market concentration monitoring** — Track which ZIPs have the highest concentration of upcoming sales to anticipate inventory surges
- **Institutional buyer signal detection** — Post-sale: track what names / entities are acquiring properties at auction across multiple months

**API Features:**
- RESTful API with full foreclosure data access
- Saved search webhooks — push new matching records to your pipeline system
- Bulk export for model inputs
- County-level data segmentation

**Automation Method:** API  
**Automation Score:** 9/10  
**Recommended Priority:** HIGH

---

## Rank 3 — BDF Group (Barrett Daffin Frappier Turner & Engel LLP)

**Website:** https://www.bdfgroup.com/foreclosure-posting/  
**Source Type:** Trustee Law Firm — Scrape-Based  
**Counties:** Harris, Dallas, Tarrant  
**Verification Status:** VERIFIED  
**Cost:** Free  
**Investor Intel Score:** 9/10  

### Why It's #3 for Hedge-Fund Intelligence

BDF Group is not an institutional data provider — it is a trustee law firm that posts its notices publicly as required by law. However, because BDF Group handles the **largest single volume** of Texas trustee-sale cases, their monthly postings serve as a high-quality, free validation layer against ATTOM or PropertyRadar data.

**Hedge-Fund Intelligence Value:**
- **Lender/servicer identification** — BDF Group notices typically identify the beneficiary (lender) of the deed of trust. Tracking which servicers are actively pursuing foreclosure by volume can signal credit stress in specific portfolios.
- **First-to-know** — BDF Group PDFs typically post within the first 5–8 days of the month, before ATTOM or PropertyRadar may have processed all notices. For aggressive acquisition teams, this raw data may provide a 24–48 hour lead-time advantage.
- **Opening bid reference** — Cross-reference BDF opening bids against ATTOM AVM data to quickly identify the highest-margin opportunities in the batch.
- **Month-over-month volume tracking** — Counting the number of BDF Group postings per county per month provides a free proxy metric for county-level foreclosure volume trends.

**Automation Method:** PDF_PARSE + HTTP_GET  
**Automation Score:** 8/10  

**Hedge-Fund Integration Architecture:**
1. Automated monthly BDF Group PDF download (Days 5–8)
2. Parse and load into internal database
3. Cross-reference against ATTOM data for enrichment and validation
4. Flag any BDF Group listings not yet appearing in ATTOM feed (early detection)
5. Track BDF Group volume trends month-over-month as a leading indicator

---

## Rank 4 — Mackie Wolf Zientz & Mann PC

**Website:** https://www.mwzmlaw.com/foreclosure-postings/  
**Source Type:** Trustee Law Firm — Scrape-Based  
**Counties:** Harris, Dallas, Tarrant  
**Verification Status:** VERIFIED  
**Cost:** Free  
**Investor Intel Score:** 8/10  

### Why It's #4 for Hedge-Fund Intelligence

Mackie Wolf serves as the second major scrape-based validation and supplemental coverage source. Their postings capture a distinct segment of the trustee-sale market (different servicers use Mackie Wolf vs. BDF Group).

**Hedge-Fund Intelligence Value:**
- **Complementary servicer coverage** — Combining Mackie Wolf with BDF Group gives a more complete picture of which lenders and servicers are actively pursuing foreclosure in Texas
- **Multi-source validation** — Cross-referencing Mackie Wolf postings against ATTOM confirms data completeness and catches any gaps in the ATTOM feed
- **Volume tracking** — Mackie Wolf monthly posting count is an independent signal of foreclosure market activity

**Automation Method:** PDF_PARSE + HTTP_GET  
**Automation Score:** 8/10

---

## Investor Activity Indicators

The following signals can be derived from the sources above to build hedge-fund level market intelligence:

### 1. Monthly Filing Volume by County

**How to Track:** Count unique trustee-sale notices filed each month in Harris, Dallas, and Tarrant County from the combined trustee firm feeds + county clerk sources.

**What It Signals:**
- Rising volume = increasing credit stress, more inventory coming to market
- Falling volume = improving credit conditions, tightening inventory
- Sudden spikes = economic shock (job loss, rate shock) or bulk file by a large servicer

**Best Sources:** County clerk PDFs (Dallas, Tarrant), BDF Group + Mackie Wolf volume counts, ATTOM trend feeds

---

### 2. Third-Party Buyer Penetration Rate

**How to Track:** After each first Tuesday, compare the number of trustee-sale notices filed vs. the number of properties that sold to third parties at auction (vs. reverted to lender as REO). This data comes from post-sale deed recordings in county property records.

**What It Signals:**
- High third-party buyer rate (>30%) = competitive auction environment, strong investor demand
- Low third-party buyer rate (<10%) = buyers are staying away, properties reverting to REO, potential opportunity in post-REO market

**Best Sources:** ATTOM post-sale data, county deed recording public records

---

### 3. Institutional Buyer Entity Concentration

**How to Track:** After each auction, the buyer entity is recorded in the deed filed with the county. Tracking buyer entity names across multiple months reveals which institutions are actively accumulating in specific markets.

**What It Signals:**
- Single entity buying 10+ properties per month = institutional accumulation — likely a fund or large SFR operator
- Concentration in specific ZIPs = fund has identified those ZIPs as target areas
- Appearance of new institutional entities = new capital entering the market

**Best Sources:** ATTOM post-sale buyer entity data, Harris/Dallas/Tarrant County deed recording public records

---

### 4. Opening Bid vs. AVM Spread

**How to Track:** For each upcoming trustee-sale, calculate the spread between the opening bid (from trustee firm PDFs or ATTOM) and the estimated market value (from ATTOM AVM or appraisal district assessed value). Identify properties with the largest positive spread (opening bid significantly below market value).

**What It Signals:**
- Large positive spread = potentially high-margin acquisition opportunity
- Negative spread (opening bid above market) = lender is trying to fully cover the debt; limited third-party buyer opportunity
- County-level average spread trends = overall market health

**Best Sources:** BDF Group / Mackie Wolf PDFs (opening bids) + HCAD/DCAD/TAD (assessed values) + ATTOM (AVM)

---

### 5. Lender / Servicer Concentration Analysis

**How to Track:** The trustee-sale notice identifies the beneficiary (lender/servicer). Track which lenders are filing the most notices per month and whether specific lenders are increasing or decreasing their filing rate.

**What It Signals:**
- A servicer filing an unusual volume spike = potential bulk transfer or credit event in their portfolio
- Major bank reducing filings = may indicate forbearance programs or changing foreclosure strategy
- New servicers appearing in large volume = portfolio acquisitions or new entrants to the Texas market

**Best Sources:** BDF Group PDF beneficiary field, ATTOM servicer data

---

## Recommended Architecture for Hedge-Fund Texas Foreclosure Intelligence

```
Layer 1: Primary Feed (Institutional Grade)
  └── ATTOM Data API — daily Texas foreclosure feed (all counties)
  └── PropertyRadar API — daily enriched trustee-sale data

Layer 2: Supplemental Scrape (Free Validation + Early Detection)
  └── BDF Group PDF download + parse (monthly, Days 5-8)
  └── Mackie Wolf PDF download + parse (monthly, Days 5-8)
  └── Dallas County Clerk PDF (monthly)
  └── Tarrant County Clerk PDF (monthly)

Layer 3: Post-Sale Intelligence
  └── ATTOM post-sale data (sold vs. REO, buyer entity)
  └── County deed recording monitors (new deed filings after first Tuesday)

Layer 4: Analytics Layer
  └── Monthly volume dashboard (filings by county)
  └── Third-party buyer rate dashboard
  └── Institutional buyer concentration maps
  └── Opening bid vs. AVM spread analysis
  └── Lender/servicer filing volume tracking
```

---

*Generated by AMARA-AI Texas Foreclosure Intel Module | Hedge-Fund Intelligence Report | 2026-05-16*
