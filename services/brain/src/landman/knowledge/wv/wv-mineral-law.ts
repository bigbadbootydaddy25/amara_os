// WV Mineral Law Knowledge — Texhoma Namespace Only

export type WVLaw = {
  name: string;
  year: number;
  description: string;
  impactOnTitleWork: string;
  keyThreshold?: string;
  survivesTermination: boolean;
  criticalityLevel: 'critical' | 'high' | 'moderate';
};

export const WV_MINERAL_LAWS: WVLaw[] = [
  {
    name: 'WV Cotenancy Modernization and Majority Protection Act',
    year: 2018,
    description: 'Allows majority interest owners to force pooling of minority mineral interests. Most important WV mineral law change in decades.',
    impactOnTitleWork: 'Every title opinion on WV mineral tracts must address cotenancy issues. 75% threshold to invoke. Minority owners receive royalty but cannot block development. Know the statutory procedure for invoking cotenancy cold.',
    keyThreshold: '75% majority interest required to invoke',
    survivesTermination: true,
    criticalityLevel: 'critical',
  },
  {
    name: 'WV Dormant Oil and Gas Act',
    year: 1990,
    description: 'Allows surface owner to terminate old abandoned oil and gas interests that have been dormant for 20+ years with no production, development, or recorded claim.',
    impactOnTitleWork: 'Always check for dormancy issues on old leases and mineral interests. Proper statutory notice requirements must be followed exactly. Dormancy can extinguish what appears to be a valid outstanding interest.',
    keyThreshold: '20 years dormant with no production, development, or recorded statement of claim',
    survivesTermination: true,
    criticalityLevel: 'critical',
  },
  {
    name: 'WV Flat Rate Royalty Statute',
    year: 2018,
    description: '2018 amendment requires conversion of old flat rate royalty leases to market-based royalties. Old leases often paid $300/year per well regardless of production value.',
    impactOnTitleWork: 'Affects lease validity analysis. Identify which leases in the chain have flat rate royalty provisions. Operators have challenged the constitutionality — know the current litigation status. Flag all flat rate leases.',
    keyThreshold: 'Applies to all pre-existing flat rate royalty provisions',
    survivesTermination: true,
    criticalityLevel: 'high',
  },
  {
    name: 'WV Marketable Title Act',
    year: 1986,
    description: 'Establishes 40-year search period as generally sufficient root of title for marketable title purposes. Extinguishes old claims not re-recorded within the period.',
    impactOnTitleWork: 'Standard WV title search goes back 40 years. Extended search back to patent required when issues appear in the 40-year window or client specifically requires it.',
    keyThreshold: '40-year root of title',
    survivesTermination: true,
    criticalityLevel: 'high',
  },
  {
    name: 'WV Surface Owner Protection Act',
    year: 2011,
    description: 'Requires operators to provide advance notice to surface owners before drilling. Mandates compensation for surface damage. Governs use of surface for oil and gas operations.',
    impactOnTitleWork: 'Note all surface/mineral severances in the chain. Surface owner rights affect development feasibility. Document who owns surface vs minerals on every tract.',
    keyThreshold: '30 days advance notice required',
    survivesTermination: false,
    criticalityLevel: 'moderate',
  },
  {
    name: 'WV Oil and Gas Conservation Commission Rules',
    year: 0,
    description: 'Governs horizontal well spacing, pooling unit formation, and production operations in WV.',
    impactOnTitleWork: 'Horizontal drilling units must comply with spacing rules. Verify unit plats are properly filed. Check that all tracts in a unit are covered by valid leases with adequate pooling authority.',
    keyThreshold: 'Varies by formation and county',
    survivesTermination: false,
    criticalityLevel: 'high',
  },
];

export const WV_TITLE_DEFECTS = [
  {
    type: 'Gap in Chain',
    description: 'Missing conveyance between consecutive owners',
    severity: 'critical',
    curative: 'Locate missing deed or obtain quitclaim from heirs of missing grantor',
  },
  {
    type: 'Defective Acknowledgment',
    description: 'Deed not properly acknowledged before authorized officer',
    severity: 'high',
    curative: 'Re-acknowledgment if grantor available, or curative affidavit if long-standing possession',
  },
  {
    type: 'Missing Spouse Signature',
    description: 'Dower rights in older WV deeds required both spouses to sign',
    severity: 'high',
    curative: 'Quitclaim from spouse or heirs, or show spouse predeceased grantor',
  },
  {
    type: 'Undischarged Mortgage',
    description: 'Lien still showing in chain with no release recorded',
    severity: 'critical',
    curative: 'Obtain and record release from lender, or show statute of limitations has run',
  },
  {
    type: 'Expired Lease Still Active',
    description: 'Oil and gas lease past primary term with no production to hold it',
    severity: 'high',
    curative: 'Affidavit of expiration, or formal release from lessee',
  },
  {
    type: 'Old Dissolved Corporation',
    description: 'Grantor corporation dissolved with no successor identified',
    severity: 'high',
    curative: 'Check WV SOS for dissolution date, successor, or receivership. May need court order.',
  },
  {
    type: 'Heirship Not Documented',
    description: 'Owner died with no probate filed and no heirship affidavit recorded',
    severity: 'high',
    curative: 'Heirship affidavit if death 10+ years ago and heirs known. Otherwise open probate.',
  },
  {
    type: 'Depth Severance Not Accounted For',
    description: 'Different parties own different formation depths — not tracked in chain',
    severity: 'critical',
    curative: 'Map each depth conveyance separately. Identify every formation owner.',
  },
  {
    type: 'Unit Formation Defect',
    description: 'Horizontal drilling unit not properly formed or missing pooling authority',
    severity: 'critical',
    curative: 'Review unit plat, check pooling clause in each lease, identify any unleased interests',
  },
  {
    type: 'Flat Rate Royalty Lease',
    description: 'Lease contains flat rate royalty provision affected by 2018 WV statute',
    severity: 'moderate',
    curative: 'Flag and note in title opinion. Monitor litigation status of 2018 statute.',
  },
  {
    type: 'Dormant Mineral Interest',
    description: 'Old mineral interest may be subject to dormancy claim under WV Dormant Act',
    severity: 'moderate',
    curative: 'Check for recorded statements of claim. Verify production or development activity.',
  },
  {
    type: 'NPRI Outstanding',
    description: 'Non-participating royalty interest not accounted for in current ownership',
    severity: 'high',
    curative: 'Trace NPRI through full chain. Calculate exact fraction outstanding.',
  },
];

export const WV_CURATIVE_INSTRUMENTS = [
  {
    type: 'Affidavit of Heirship',
    when: 'Death occurred 10+ years ago, no will/probate filed, heirs well known, affiant has personal knowledge',
    requirements: 'Properly acknowledged, recorded in county clerk, detailed description of heirs and family history',
  },
  {
    type: 'Correction Deed',
    when: 'Error in original deed — wrong description, wrong name, scrivener error',
    requirements: 'Same parties as original, identifies the error, corrects it, re-acknowledged and re-recorded',
  },
  {
    type: 'Ratification',
    when: 'Confirming that lease or agreement is still valid and in effect',
    requirements: 'All current interest owners sign, identifies original instrument, confirms ratification',
  },
  {
    type: 'Quitclaim Deed',
    when: 'Clearing cloud on title from unknown or adverse claimant',
    requirements: 'From claimant to current owner, no warranty, properly acknowledged and recorded',
  },
  {
    type: 'Probate Order',
    when: 'Estate must be formally opened and administered',
    requirements: 'Filed in county where decedent resided, WV probate court jurisdiction',
  },
  {
    type: 'Affidavit of Expiration',
    when: 'Oil and gas lease has expired by its own terms',
    requirements: 'From knowledgeable affiant, states facts showing expiration, recorded in county clerk',
  },
];
