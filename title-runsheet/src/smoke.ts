/**
 * One-off smoke test (not part of the app): exercises the DB repository,
 * curative agent, CSV export, and Word export against synthetic instrument
 * rows, bypassing Dropbox/portal (which need real credentials). Deletes what
 * it creates. Not wired into package.json scripts — run directly with tsx.
 */
import { query } from './db/client.js';
import {
  insertInstrument,
  listCurativeItems,
  listInstruments,
  replaceRunsheetEntries,
} from './db/repository.js';
import { runCurativeAgent } from './agents/curativeAgent.js';
import { buildRunsheetCsv } from './export/csv.js';
import { buildTitleReportDocx } from './export/word.js';
import type { Project } from './types/index.js';
import { closePool } from './db/client.js';
import { writeFileSync } from 'node:fs';

async function main() {
  const [project] = await query<Project>(
    `insert into projects (name, county, state, survey_section, survey_block, survey_township,
       dropbox_seller_package_path, dropbox_recorded_instruments_path)
     values ('Smoke Test Tract','Howard','TX','47','33','T1S','/sp','/ri')
     returning *`,
  );
  console.log('project', project.id, project.status);

  await insertInstrument({
    project_id: project.id,
    instrument_type: 'Warranty Deed',
    grantors: ['John A. Smith'],
    grantees: ['Jane B. Smith'],
    execution_date: '1985-03-01',
    recording_date: '1985-03-05',
    volume: '210',
    page: '441',
    legal_description: 'Section 47, Block 33, T1S, Howard County, Texas',
    raw_extraction: {},
    confidence: 0.9,
  });

  await insertInstrument({
    project_id: project.id,
    instrument_type: 'Oil and Gas Lease',
    grantors: ['Someone Else Entirely'], // deliberately breaks the chain
    grantees: ['Big Oil Co.'],
    execution_date: '2001-06-01',
    recording_date: '2001-06-10',
    instrument_number: '2001-006123',
    legal_description: 'Section 47, Block 33, T1S, Howard County, Texas',
    raw_extraction: {},
    confidence: 0.3,
  });

  const curativeResult = await runCurativeAgent({ project });
  console.log('curative:', curativeResult.summary);

  const items = await listCurativeItems(project.id);
  console.log('curative items:', items.length);
  for (const item of items) console.log(' -', item.severity, item.category, '|', item.description);

  const instruments = await listInstruments(project.id);
  const sequenced = instruments.map((row, i) => ({ ...row, sequence_no: i + 1 }));
  await replaceRunsheetEntries(
    project.id,
    sequenced.map((row) => ({ instrumentId: row.id, sequenceNo: row.sequence_no, summary: row.instrument_type ?? '' })),
  );

  const csv = buildRunsheetCsv(sequenced);
  writeFileSync('/tmp/smoke_runsheet.csv', csv);
  console.log('csv bytes:', csv.length);

  const docxBuffer = await buildTitleReportDocx(project, sequenced, items);
  writeFileSync('/tmp/smoke_report.docx', docxBuffer);
  console.log('docx bytes:', docxBuffer.length);

  // cleanup
  await query('delete from projects where id = $1', [project.id]);
  console.log('cleaned up.');
}

main()
  .catch((err) => {
    console.error(err);
    process.exitCode = 1;
  })
  .finally(() => closePool());
