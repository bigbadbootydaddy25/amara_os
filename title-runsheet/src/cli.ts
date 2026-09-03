#!/usr/bin/env node
import { env } from './config/env.js';
import { closePool, query } from './db/client.js';
import { getProject, listProjects } from './db/repository.js';
import { runPipeline, type PipelineStage } from './orchestrator/pipeline.js';
import { runIntakeAgent } from './agents/intakeAgent.js';
import { runInstrumentRetrievalAgent } from './agents/instrumentRetrievalAgent.js';
import { runAbstractingAgent } from './agents/abstractingAgent.js';
import { runCurativeAgent } from './agents/curativeAgent.js';
import { runRunsheetExportAgent } from './agents/runsheetExportAgent.js';
import { runReportAgent } from './agents/reportAgent.js';
import type { AgentContext } from './types/index.js';

function usage(): void {
  console.log(`Title Runsheet CLI

Usage:
  tsx src/cli.ts create-project --name "<name>" [--county Howard] [--state TX]
                                 [--section 47] [--block 33] [--township T1S]
  tsx src/cli.ts list-projects
  tsx src/cli.ts pipeline <projectId> [--from intake|retrieval|abstracting|curative|runsheet|report]
  tsx src/cli.ts run <intake|retrieval|abstracting|curative|runsheet|report> <projectId>
`);
}

function flag(args: string[], name: string): string | undefined {
  const idx = args.indexOf(`--${name}`);
  return idx >= 0 ? args[idx + 1] : undefined;
}

async function createProject(args: string[]) {
  const name = flag(args, 'name');
  if (!name) throw new Error('--name is required');

  const county = flag(args, 'county') ?? env.defaultTract.county();
  const state = flag(args, 'state') ?? env.defaultTract.state();
  const section = flag(args, 'section') ?? env.defaultTract.section();
  const block = flag(args, 'block') ?? env.defaultTract.block();
  const township = flag(args, 'township') ?? env.defaultTract.township();

  const slug = name.replace(/[^a-zA-Z0-9._-]+/g, '-');
  const sellerPackagePath = `${env.dropbox.sellerPackageRoot()}/${slug}`;
  const recordedInstrumentsPath = `${env.dropbox.recordedInstrumentsRoot()}/${slug}`;

  const rows = await query<{ id: string }>(
    `insert into projects (
       name, state, county, survey_section, survey_block, survey_township,
       dropbox_seller_package_path, dropbox_recorded_instruments_path
     ) values ($1,$2,$3,$4,$5,$6,$7,$8) returning id`,
    [name, state, county, section, block, township, sellerPackagePath, recordedInstrumentsPath],
  );

  console.log(`Created project ${rows[0].id} — ${name} (${county} County, ${state}: Sec ${section} Blk ${block} ${township})`);
  console.log(`  Dropbox seller package folder:      ${sellerPackagePath}`);
  console.log(`  Dropbox recorded instruments folder: ${recordedInstrumentsPath}`);
}

async function listAll() {
  const projects = await listProjects();
  if (projects.length === 0) {
    console.log('No projects yet — create one with `create-project`.');
    return;
  }
  for (const project of projects) {
    console.log(`${project.id}  [${project.status}]  ${project.name}  (${project.county} County, ${project.state})`);
  }
}

async function runOne(agentName: string, projectId: string) {
  const project = await getProject(projectId);
  if (!project) throw new Error(`No project found with id ${projectId}`);
  const ctx: AgentContext = { project };

  const result = await (async () => {
    switch (agentName) {
      case 'intake':
        return runIntakeAgent(ctx);
      case 'retrieval':
        return runInstrumentRetrievalAgent(ctx);
      case 'abstracting':
        return runAbstractingAgent(ctx);
      case 'curative':
        return runCurativeAgent(ctx);
      case 'runsheet':
        return runRunsheetExportAgent(ctx);
      case 'report':
        return runReportAgent(ctx);
      default:
        throw new Error(`Unknown agent "${agentName}"`);
    }
  })();

  console.log(`[${result.agentName}] ${result.summary}`);
}

async function main() {
  const [, , command, ...rest] = process.argv;

  switch (command) {
    case 'create-project':
      await createProject(rest);
      break;
    case 'list-projects':
      await listAll();
      break;
    case 'pipeline': {
      const [projectId, ...args] = rest;
      if (!projectId) throw new Error('Usage: pipeline <projectId> [--from <stage>]');
      const from = (flag(args, 'from') as PipelineStage | undefined) ?? 'intake';
      const results = await runPipeline(projectId, from);
      for (const result of results) console.log(`[${result.agentName}] ${result.summary}`);
      break;
    }
    case 'run': {
      const [agentName, projectId] = rest;
      if (!agentName || !projectId) throw new Error('Usage: run <agent> <projectId>');
      await runOne(agentName, projectId);
      break;
    }
    default:
      usage();
  }
}

main()
  .catch((err) => {
    console.error(err instanceof Error ? err.message : err);
    process.exitCode = 1;
  })
  .finally(async () => {
    await closePool();
  });
