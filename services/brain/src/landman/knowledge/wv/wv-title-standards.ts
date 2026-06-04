// WV Title Examination Standards — Texhoma Namespace Only
// Based on WV State Bar Real Property Section Title Standards

export const WV_TITLE_EXAMINATION_WORKFLOW = {
  standardSearchPeriod: 40,
  extendedSearchTriggers: [
    'Issues appearing in 40-year window',
    'Client specifically requires patent search',
    'Dormancy issues present',
    'Complex heirship chains',
  ],
  indexesToSearch: [
    'Grantor/Grantee deed index',
    'Oil and gas lease index',
    'Mortgage and lien index',
    'Judgment lien index',
    'Federal tax lien index',
    'Lis pendens index',
    'Probate records when needed',
    'Corporate records — WV SOS',
    'Circuit court records',
    'Unit plat records',
  ],
  outputDocuments: [
    {
      name: 'Runsheet',
      description: 'Chronological chain of all instruments affecting title',
      requiredFields: [
        'Grantor', 'Grantee', 'Instrument type',
        'Date executed', 'Date recorded',
        'Book and page or instrument number',
        'Legal description', 'Acreage', 'Notes',
      ],
    },
    {
      name: 'Title Memo',
      description: 'Current ownership conclusion with exceptions and curative',
      requiredSections: [
        'Current ownership summary',
        'Outstanding oil and gas leases',
        'Encumbrances and exceptions',
        'Curative requirements',
        'Open issues with explanation',
      ],
    },
    {
      name: 'Curative List',
      description: 'Specific items needed to cure title defects',
      requiredFields: [
        'Defect type', 'Description',
        'How to cure', 'Priority level',
        'Who must act',
      ],
    },
  ],
};

export const WV_LEASE_CLAUSES_TO_EXAMINE = [
  {
    clause: 'Habendum',
    description: 'Primary term plus "as long thereafter as oil or gas is produced"',
    checkFor: 'Has primary term expired? Is there production to hold it beyond primary term?',
  },
  {
    clause: 'Pugh Clause - Horizontal',
    description: 'Releases acreage outside a drilling unit at end of primary term',
    checkFor: 'Does lease release acreage outside unit? What is the unit acreage limitation?',
  },
  {
    clause: 'Pugh Clause - Vertical',
    description: 'Releases formations not being developed at end of primary term',
    checkFor: 'Are shallower formations released if only Marcellus is developed?',
  },
  {
    clause: 'Pooling/Unitization',
    description: 'Authority to pool leased acreage into a drilling unit',
    checkFor: 'What is the acreage limit? Does it allow horizontal units? How many acres?',
  },
  {
    clause: 'Depth',
    description: 'What formations are covered by the lease',
    checkFor: 'Does it cover all depths or specific formations? Is Marcellus covered? Utica?',
  },
  {
    clause: 'Warranty',
    description: 'General, special, or no warranty from lessor',
    checkFor: 'General warranty = full title defense. Special = limited. No warranty = buyer beware.',
  },
  {
    clause: 'Shut-In Royalty',
    description: 'Keeps lease alive when well is capable of production but not producing',
    checkFor: 'Is shut-in royalty being paid? Are payments timely? Is lease still valid?',
  },
  {
    clause: 'Force Majeure',
    description: 'Extends lease term during unavoidable delays',
    checkFor: 'Has FM been properly invoked? Is it legitimately applicable?',
  },
];

export const TEXHOMA_CONTRACT_RULES = {
  contractNumber:    '52446',
  prospect:          'Elk',
  state:             'West Virginia',
  serviceType:       'Title Examination',
  dayRate:           325.00,
  hoursForFullDay:   8,
  get hourlyRate()   { return this.dayRate / this.hoursForFullDay; },
  weeklyRate:        1625.00,
  invoiceFrequency:  'biweekly_max',
  expenseLogDeadline:'24_hours_current',
  paymentHold:       30,
  firstInvoiceDate:  '2026-06-17',
  contractEndDate:   '2026-10-01',
  companyContact: {
    name:    'David Adkins',
    title:   'President',
    company: 'Texhoma Land Consultants 1 Inc',
    phone:   '(405) 321-6777',
    address: '770 West Rock Creek Road Suite 117, Norman Oklahoma 73069',
  },
  reimbursableExpenses: [
    'Mileage at IRS standard rate',
    'Meals — actual reasonable costs',
    'Hotel — actual reasonable costs',
    'Misc — actual reasonable costs including copying and abstractor bills',
  ],
  hardRules: [
    'Invoice no more than every 2 weeks',
    'Keep expense log current — never more than 24 hours behind',
    'Provide receipts for all expenses',
    'Never copy Items without written consent',
    'All work product belongs to Texhoma',
    'Confidentiality survives termination — permanent',
    'Non-compete: 6 miles from work area, 1 year post-termination',
    'Device rule: dedicated Mac Mini only — main Mac never used for this job',
  ],
};
