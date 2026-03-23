/**
 * AMARA OS — Market Selection Engine
 * Identifies the best markets for weekly closings.
 * Uses buyer density, distress inventory, DOM velocity, and deal flow metrics.
 */

import { MarketProfile, MARKET_QUALIFICATION, INITIAL_MARKETS } from "@/core/schema/market";

// ─────────────────────────────────────────────────────────────────────────────
// MARKET SCORING FACTORS
// ─────────────────────────────────────────────────────────────────────────────
export interface MarketScoringFactors {
  cashBuyerDensityScore: number;    // 0–25
  distressInventoryScore: number;   // 0–25
  domVelocityScore: number;         // 0–20
  olderHousingScore: number;        // 0–15
  priceReductionScore: number;      // 0–15
}

export function scoreMarket(market: MarketProfile): {
  total: number;
  factors: MarketScoringFactors;
  rank: string;
  disqualified: boolean;
  disqualifyReasons: string[];
} {
  const disqualifyReasons: string[] = [];

  // Hard disqualifiers
  if (market.cashBuyerDensity === "LOW") {
    disqualifyReasons.push("insufficient cash buyer density");
  }
  if (market.olderHousingStockPct < MARKET_QUALIFICATION.minOlderHousingStockPct) {
    disqualifyReasons.push(`older housing stock ${Math.round(market.olderHousingStockPct * 100)}% below minimum 25%`);
  }
  if (market.avgDOMOnDistress > MARKET_QUALIFICATION.maxAvgDOMOnDistress) {
    disqualifyReasons.push(`avg DOM ${market.avgDOMOnDistress} too slow for weekly closings`);
  }
  if (market.investorZIPCount < MARKET_QUALIFICATION.minInvestorZIPCount) {
    disqualifyReasons.push(`only ${market.investorZIPCount} investor ZIPs — need ${MARKET_QUALIFICATION.minInvestorZIPCount}+`);
  }

  if (disqualifyReasons.length > 0) {
    return { total: 0, factors: emptyFactors(), rank: "DISQUALIFIED", disqualified: true, disqualifyReasons };
  }

  // Scoring
  const cashScore = market.cashBuyerDensity === "HIGH" ? 25 : 15;

  const distressScore = Math.min(25,
    market.investorZIPCount * 3 +
    (market.priceReducedInventoryPct >= 0.20 ? 8 : market.priceReducedInventoryPct >= 0.12 ? 5 : 2)
  );

  const domScore = Math.min(20,
    market.avgDOMOnDistress <= 30 ? 20 :
    market.avgDOMOnDistress <= 45 ? 16 :
    market.avgDOMOnDistress <= 60 ? 12 : 8
  );

  const olderHousingScore = Math.min(15, Math.round(market.olderHousingStockPct * 40));

  const priceReductionScore = Math.min(15,
    market.priceReducedInventoryPct >= 0.25 ? 15 :
    market.priceReducedInventoryPct >= 0.15 ? 10 :
    market.priceReducedInventoryPct >= 0.08 ? 6 : 3
  );

  const total = cashScore + distressScore + domScore + olderHousingScore + priceReductionScore;
  const rank =
    total >= 80 ? "TIER_1_PRIORITY" :
    total >= 65 ? "TIER_2_ACTIVE" :
    total >= 50 ? "TIER_3_MONITOR" : "TIER_4_LOW";

  return {
    total,
    factors: { cashBuyerDensityScore: cashScore, distressInventoryScore: distressScore, domVelocityScore: domScore, olderHousingScore, priceReductionScore },
    rank,
    disqualified: false,
    disqualifyReasons: [],
  };
}

function emptyFactors(): MarketScoringFactors {
  return { cashBuyerDensityScore: 0, distressInventoryScore: 0, domVelocityScore: 0, olderHousingScore: 0, priceReductionScore: 0 };
}

// ─────────────────────────────────────────────────────────────────────────────
// SEED DATA — all 37 virtual markets pre-scored for weekly closing potential
// ─────────────────────────────────────────────────────────────────────────────
export const SEEDED_MARKET_SCORES: Array<{
  id: string;
  label: string;
  state: string;
  weeklyClosingScore: number;
  cashBuyerDensity: "HIGH" | "MEDIUM" | "LOW";
  olderHousingStockPct: number;
  avgDOMOnDistress: number;
  investorZIPCount: number;
  priceReducedInventoryPct: number;
  tier: string;
  why: string;
  zips: string[];
}> = [
  // ── TIER 1: PRIORITY ──────────────────────────────────────────────────────
  {
    id: "dfw", label: "DFW", state: "TX", weeklyClosingScore: 92, cashBuyerDensity: "HIGH",
    olderHousingStockPct: 0.52, avgDOMOnDistress: 28, investorZIPCount: 24,
    priceReducedInventoryPct: 0.22, tier: "TIER_1_PRIORITY",
    why: "Largest TX market. High-velocity cash buyer pool. Dense investor ZIPs in Dallas/FW East Side. Repeatable weekly closings on cosmetic/fixer SFR.",
    zips: ["75228","75227","75216","75224","75211","75217","76104","76105","76106","76112","75061","75062","75063","76010","76011","76018"],
  },
  {
    id: "atlanta", label: "Atlanta", state: "GA", weeklyClosingScore: 91, cashBuyerDensity: "HIGH",
    olderHousingStockPct: 0.48, avgDOMOnDistress: 24, investorZIPCount: 22,
    priceReducedInventoryPct: 0.21, tier: "TIER_1_PRIORITY",
    why: "Best-in-class investor market in Southeast. Fast cash buyers. Strong flipper demand in intown and south Atlanta ZIPs.",
    zips: ["30310","30311","30314","30315","30316","30318","30344","30349","30354","30032","30034","30038","30058","30296","30297"],
  },
  {
    id: "phoenix", label: "Phoenix", state: "AZ", weeklyClosingScore: 89, cashBuyerDensity: "HIGH",
    olderHousingStockPct: 0.44, avgDOMOnDistress: 31, investorZIPCount: 19,
    priceReducedInventoryPct: 0.24, tier: "TIER_1_PRIORITY",
    why: "High price-reduction activity in West/South Phoenix. Strong flipper demand. Fast close cycle.",
    zips: ["85031","85033","85035","85040","85041","85042","85043","85051","85053","85301","85302","85303","85031","85009","85017","85019"],
  },
  {
    id: "houston", label: "Houston", state: "TX", weeklyClosingScore: 87, cashBuyerDensity: "HIGH",
    olderHousingStockPct: 0.55, avgDOMOnDistress: 33, investorZIPCount: 20,
    priceReducedInventoryPct: 0.19, tier: "TIER_1_PRIORITY",
    why: "Massive older housing inventory. High absentee-owner density in East/South Houston. Active cash buyers at multiple price bands.",
    zips: ["77051","77053","77033","77047","77048","77085","77087","77093","77016","77028","77029","77044","77078","77049","77015","77013"],
  },
  {
    id: "cleveland", label: "Cleveland", state: "OH", weeklyClosingScore: 85, cashBuyerDensity: "HIGH",
    olderHousingStockPct: 0.78, avgDOMOnDistress: 22, investorZIPCount: 16,
    priceReducedInventoryPct: 0.28, tier: "TIER_1_PRIORITY",
    why: "Highest older housing density on list. Very low price points. Fastest DOM. Dense landlord buyer demand.",
    zips: ["44102","44103","44104","44105","44108","44109","44110","44111","44112","44113","44127","44128","44135","44144","44102","44107"],
  },
  {
    id: "indianapolis", label: "Indianapolis", state: "IN", weeklyClosingScore: 83, cashBuyerDensity: "HIGH",
    olderHousingStockPct: 0.56, avgDOMOnDistress: 30, investorZIPCount: 14,
    priceReducedInventoryPct: 0.20, tier: "TIER_1_PRIORITY",
    why: "Strong landlord and flipper demand. Affordable older stock. Good repeat buyer activity.",
    zips: ["46201","46203","46205","46208","46218","46222","46224","46226","46228","46235","46239","46241","46254","46260","46222"],
  },
  {
    id: "memphis", label: "Memphis", state: "TN", weeklyClosingScore: 82, cashBuyerDensity: "HIGH",
    olderHousingStockPct: 0.65, avgDOMOnDistress: 26, investorZIPCount: 13,
    priceReducedInventoryPct: 0.26, tier: "TIER_1_PRIORITY",
    why: "High vacancy rates, high absentee ownership, dense distress. Strong landlord buyer demand.",
    zips: ["38106","38107","38108","38109","38111","38114","38116","38118","38122","38127","38128","38135","38141","38115","38116"],
  },

  // ── TIER 2: ACTIVE ────────────────────────────────────────────────────────
  {
    id: "kansas_city", label: "Kansas City", state: "MO", weeklyClosingScore: 79, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.58, avgDOMOnDistress: 35, investorZIPCount: 12,
    priceReducedInventoryPct: 0.18, tier: "TIER_2_ACTIVE",
    why: "Solid investor market. Older stock. Good buyer pool but slower than Tier 1.",
    zips: ["64126","64127","64128","64129","64130","64132","64133","64138","64139","64147","64149","64118","64119","64120","64123"],
  },
  {
    id: "detroit", label: "Detroit", state: "MI", weeklyClosingScore: 78, cashBuyerDensity: "HIGH",
    olderHousingStockPct: 0.82, avgDOMOnDistress: 21, investorZIPCount: 18,
    priceReducedInventoryPct: 0.30, tier: "TIER_2_ACTIVE",
    why: "Highest old housing %, fastest DOM. Low price points. Some neighborhood risk — need tight ZIP selection.",
    zips: ["48209","48210","48213","48214","48215","48224","48228","48235","48238","48227","48219","48223","48204","48206","48207"],
  },
  {
    id: "birmingham", label: "Birmingham", state: "AL", weeklyClosingScore: 77, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.61, avgDOMOnDistress: 34, investorZIPCount: 11,
    priceReducedInventoryPct: 0.22, tier: "TIER_2_ACTIVE",
    why: "Underserved investor market. High distress. Growing buyer pool.",
    zips: ["35020","35023","35064","35068","35127","35204","35205","35206","35207","35208","35211","35212","35214","35215","35224"],
  },
  {
    id: "tampa", label: "Tampa", state: "FL", weeklyClosingScore: 75, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.40, avgDOMOnDistress: 40, investorZIPCount: 10,
    priceReducedInventoryPct: 0.20, tier: "TIER_2_ACTIVE",
    why: "FL market with good cash buyer activity. Higher price points reduce margin. Better for flip strategy.",
    zips: ["33603","33604","33605","33610","33612","33614","33615","33619","33621","33625","33634","33647","33603","33604","33610"],
  },
  {
    id: "san_antonio", label: "San Antonio", state: "TX", weeklyClosingScore: 74, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.47, avgDOMOnDistress: 38, investorZIPCount: 10,
    priceReducedInventoryPct: 0.17, tier: "TIER_2_ACTIVE",
    why: "Good TX secondary market. Good for Propelio targeting. Decent older stock.",
    zips: ["78201","78202","78203","78204","78207","78208","78210","78211","78212","78213","78220","78221","78223","78224","78225"],
  },
  {
    id: "st_louis", label: "St. Louis", state: "MO", weeklyClosingScore: 73, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.67, avgDOMOnDistress: 38, investorZIPCount: 10,
    priceReducedInventoryPct: 0.21, tier: "TIER_2_ACTIVE",
    why: "Dense older housing. Active landlord buyer network. Multiple distressed sub-markets.",
    zips: ["63107","63108","63111","63112","63113","63115","63118","63120","63121","63130","63133","63136","63137","63138","63139"],
  },
  {
    id: "columbus", label: "Columbus", state: "OH", weeklyClosingScore: 72, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.50, avgDOMOnDistress: 36, investorZIPCount: 9,
    priceReducedInventoryPct: 0.18, tier: "TIER_2_ACTIVE",
    why: "Growing investor activity. Affordable older stock near OSU corridor and south side.",
    zips: ["43205","43206","43207","43209","43211","43213","43215","43219","43223","43227","43228","43229","43232","43204","43224"],
  },
  {
    id: "jacksonville", label: "Jacksonville", state: "FL", weeklyClosingScore: 71, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.44, avgDOMOnDistress: 39, investorZIPCount: 9,
    priceReducedInventoryPct: 0.19, tier: "TIER_2_ACTIVE",
    why: "FL market with lower price points than Tampa/Miami. Active SFR investor demand.",
    zips: ["32209","32208","32206","32254","32210","32211","32219","32220","32221","32222","32225","32226","32246","32204","32205"],
  },
  {
    id: "oklahoma_city", label: "Oklahoma City", state: "OK", weeklyClosingScore: 70, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.54, avgDOMOnDistress: 37, investorZIPCount: 8,
    priceReducedInventoryPct: 0.20, tier: "TIER_2_ACTIVE",
    why: "Low competition investor market. Very affordable older housing. Growing cash buyer community.",
    zips: ["73108","73109","73110","73111","73112","73115","73117","73119","73127","73128","73130","73135","73139","73141","73145"],
  },
  {
    id: "tulsa", label: "Tulsa", state: "OK", weeklyClosingScore: 68, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.56, avgDOMOnDistress: 39, investorZIPCount: 8,
    priceReducedInventoryPct: 0.19, tier: "TIER_2_ACTIVE",
    why: "Underserved market. Older housing stock. Good cash buyer pool for landlord plays.",
    zips: ["74106","74107","74110","74112","74114","74115","74119","74120","74126","74127","74128","74129","74130","74131","74132"],
  },
  {
    id: "albuquerque", label: "Albuquerque", state: "NM", weeklyClosingScore: 67, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.48, avgDOMOnDistress: 42, investorZIPCount: 7,
    priceReducedInventoryPct: 0.21, tier: "TIER_2_ACTIVE",
    why: "Low competition. Affordable price points. Growing investor presence in South/SE Albuquerque.",
    zips: ["87105","87106","87107","87108","87110","87112","87113","87114","87116","87117","87121","87123","87124","87031","87048"],
  },

  // ── TIER 3: MONITOR ───────────────────────────────────────────────────────
  {
    id: "charlotte", label: "Charlotte", state: "NC", weeklyClosingScore: 65, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.38, avgDOMOnDistress: 44, investorZIPCount: 8,
    priceReducedInventoryPct: 0.16, tier: "TIER_3_MONITOR",
    why: "Growing market. Newer housing stock limits distress density. Better for flip than wholesale.",
    zips: ["28208","28206","28205","28212","28213","28215","28216","28217","28269","28277","28227","28214","28208","28202","28210"],
  },
  {
    id: "louisville", label: "Louisville", state: "KY", weeklyClosingScore: 64, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.55, avgDOMOnDistress: 43, investorZIPCount: 7,
    priceReducedInventoryPct: 0.17, tier: "TIER_3_MONITOR",
    why: "Older housing belt. Medium buyer density. Decent wholesale potential in west Louisville.",
    zips: ["40203","40208","40210","40211","40212","40213","40214","40215","40216","40219","40220","40228","40229","40258","40272"],
  },
  {
    id: "nashville", label: "Nashville", state: "TN", weeklyClosingScore: 62, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.35, avgDOMOnDistress: 45, investorZIPCount: 7,
    priceReducedInventoryPct: 0.15, tier: "TIER_3_MONITOR",
    why: "Higher prices compress margins. Newer construction dominates. Best for flip near pocket neighborhoods.",
    zips: ["37207","37208","37209","37210","37211","37213","37216","37218","37115","37138","37072","37076","37080","37086","37115"],
  },
  {
    id: "richmond", label: "Richmond", state: "VA", weeklyClosingScore: 61, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.52, avgDOMOnDistress: 44, investorZIPCount: 7,
    priceReducedInventoryPct: 0.16, tier: "TIER_3_MONITOR",
    why: "Solid older housing corridor. Mid-Atlantic investor demand. Watch Southside Richmond ZIPs.",
    zips: ["23224","23225","23220","23222","23227","23231","23234","23235","23236","23237","23238","23250","23294","23230","23221"],
  },
  {
    id: "baltimore", label: "Baltimore", state: "MD", weeklyClosingScore: 60, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.71, avgDOMOnDistress: 41, investorZIPCount: 9,
    priceReducedInventoryPct: 0.22, tier: "TIER_3_MONITOR",
    why: "Dense older row-house stock. High distress rate. Some neighborhoods require title risk management.",
    zips: ["21201","21205","21206","21207","21213","21214","21215","21216","21217","21218","21223","21224","21225","21229","21230"],
  },
  {
    id: "milwaukee", label: "Milwaukee", state: "WI", weeklyClosingScore: 59, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.70, avgDOMOnDistress: 43, investorZIPCount: 7,
    priceReducedInventoryPct: 0.20, tier: "TIER_3_MONITOR",
    why: "Very old housing stock. Low price points. Slow buyer absorption — need tight ZIP selection.",
    zips: ["53204","53205","53206","53208","53209","53210","53212","53214","53215","53216","53218","53219","53223","53224","53228"],
  },
  {
    id: "philadelphia", label: "Philadelphia", state: "PA", weeklyClosingScore: 58, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.72, avgDOMOnDistress: 46, investorZIPCount: 8,
    priceReducedInventoryPct: 0.18, tier: "TIER_3_MONITOR",
    why: "Row-house dominant. High older stock. Transfer tax is a deal cost factor. Good landlord buyer base.",
    zips: ["19120","19121","19122","19124","19125","19126","19132","19133","19134","19136","19140","19141","19143","19144","19145"],
  },
  {
    id: "chicago", label: "Chicago", state: "IL", weeklyClosingScore: 57, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.65, avgDOMOnDistress: 48, investorZIPCount: 9,
    priceReducedInventoryPct: 0.18, tier: "TIER_3_MONITOR",
    why: "Large market, dense older stock. Property taxes compress NOI. Need ZIP-level neighborhood discipline.",
    zips: ["60617","60619","60620","60621","60623","60624","60628","60636","60637","60638","60644","60649","60651","60652","60653"],
  },
  {
    id: "raleigh", label: "Raleigh", state: "NC", weeklyClosingScore: 55, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.32, avgDOMOnDistress: 46, investorZIPCount: 6,
    priceReducedInventoryPct: 0.14, tier: "TIER_3_MONITOR",
    why: "Faster-appreciating market. Limited distress density. Watch older east Raleigh corridors.",
    zips: ["27601","27604","27605","27610","27616","27610","27601","27609","27612","27616","27615","27603","27606","27607","27609"],
  },
  {
    id: "orlando", label: "Orlando", state: "FL", weeklyClosingScore: 54, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.36, avgDOMOnDistress: 47, investorZIPCount: 6,
    priceReducedInventoryPct: 0.17, tier: "TIER_3_MONITOR",
    why: "Tourist-market dynamics raise prices. Distress pockets exist in Orange/Osceola County outer rings.",
    zips: ["32805","32806","32807","32808","32809","32811","32818","32822","32824","32825","32826","32829","32833","32835","32839"],
  },
  {
    id: "minneapolis", label: "Minneapolis", state: "MN", weeklyClosingScore: 53, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.55, avgDOMOnDistress: 47, investorZIPCount: 7,
    priceReducedInventoryPct: 0.16, tier: "TIER_3_MONITOR",
    why: "Seasonal market dynamics. Strong rental demand. Older north Minneapolis corridors show distress.",
    zips: ["55406","55407","55408","55411","55412","55413","55418","55421","55422","55423","55427","55430","55441","55444","55448"],
  },
  {
    id: "pittsburgh", label: "Pittsburgh", state: "PA", weeklyClosingScore: 52, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.74, avgDOMOnDistress: 48, investorZIPCount: 7,
    priceReducedInventoryPct: 0.20, tier: "TIER_3_MONITOR",
    why: "Very old housing stock. Slow absorption. Pockets of high distress in Hill District and McKeesport.",
    zips: ["15201","15203","15204","15205","15206","15210","15212","15213","15214","15215","15216","15219","15221","15224","15226"],
  },

  // ── TIER 4: LOW PRIORITY ─────────────────────────────────────────────────
  {
    id: "miami", label: "Miami", state: "FL", weeklyClosingScore: 48, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.38, avgDOMOnDistress: 52, investorZIPCount: 6,
    priceReducedInventoryPct: 0.15, tier: "TIER_4_LOW",
    why: "Price points too high for typical wholesale. International buyer pool. Best for large land/commercial.",
    zips: ["33125","33126","33127","33128","33135","33142","33147","33150","33161","33162","33167","33169","33179","33055","33056"],
  },
  {
    id: "denver", label: "Denver", state: "CO", weeklyClosingScore: 46, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.41, avgDOMOnDistress: 51, investorZIPCount: 6,
    priceReducedInventoryPct: 0.16, tier: "TIER_4_LOW",
    why: "Higher price points compress margins. Limited distress density. Better for luxury flip than wholesale.",
    zips: ["80204","80205","80207","80210","80211","80212","80216","80219","80221","80223","80224","80227","80236","80246","80247"],
  },
  {
    id: "colorado_springs", label: "Colorado Springs", state: "CO", weeklyClosingScore: 44, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.38, avgDOMOnDistress: 52, investorZIPCount: 5,
    priceReducedInventoryPct: 0.17, tier: "TIER_4_LOW",
    why: "Military transient market. Price points compress. Some distress near Fort Carson corridor.",
    zips: ["80903","80904","80905","80906","80907","80909","80910","80911","80915","80916","80918","80919","80920","80921","80925"],
  },
  {
    id: "las_vegas", label: "Las Vegas", state: "NV", weeklyClosingScore: 43, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.35, avgDOMOnDistress: 54, investorZIPCount: 5,
    priceReducedInventoryPct: 0.19, tier: "TIER_4_LOW",
    why: "Boom/bust cycles make consistent weekly closing hard. Some distress north Las Vegas and Henderson.",
    zips: ["89101","89102","89104","89106","89107","89108","89110","89115","89119","89121","89122","89124","89128","89130","89131"],
  },
  {
    id: "tucson", label: "Tucson", state: "AZ", weeklyClosingScore: 41, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.42, avgDOMOnDistress: 55, investorZIPCount: 5,
    priceReducedInventoryPct: 0.18, tier: "TIER_4_LOW",
    why: "Smaller buyer pool. Slower velocity. Some value in older south Tucson corridors.",
    zips: ["85701","85703","85705","85706","85708","85710","85711","85712","85713","85714","85745","85746","85747","85748","85749"],
  },
  {
    id: "austin", label: "Austin", state: "TX", weeklyClosingScore: 38, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.28, avgDOMOnDistress: 58, investorZIPCount: 5,
    priceReducedInventoryPct: 0.18, tier: "TIER_4_LOW",
    why: "Price appreciation crushed wholesale margins. Limited distress. Best for land/subdivision plays.",
    zips: ["78702","78703","78704","78705","78721","78722","78723","78724","78725","78741","78742","78744","78745","78746","78747"],
  },
  {
    id: "reno", label: "Reno", state: "NV", weeklyClosingScore: 35, cashBuyerDensity: "LOW",
    olderHousingStockPct: 0.36, avgDOMOnDistress: 60, investorZIPCount: 4,
    priceReducedInventoryPct: 0.16, tier: "TIER_4_LOW",
    why: "Limited buyer pool. Smaller market. Some distress in Sparks/north Reno pockets.",
    zips: ["89501","89502","89503","89505","89506","89511","89512","89519","89521","89523","89431","89434","89436","89441","89502"],
  },
];

// ─────────────────────────────────────────────────────────────────────────────
// BEST MARKET RECOMMENDATION
// ─────────────────────────────────────────────────────────────────────────────
export function getBestMarketForWeeklyClosings(): typeof SEEDED_MARKET_SCORES[0] {
  return SEEDED_MARKET_SCORES
    .filter((m) => m.tier === "TIER_1_PRIORITY")
    .sort((a, b) => b.weeklyClosingScore - a.weeklyClosingScore)[0];
}
