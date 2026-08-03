// Diagnostic: capture HTML and screenshot of both portals to map real selectors
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const fs = require('fs');

async function main() {
  const browser = await chromium.launch({
    headless: true,
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--ignore-certificate-errors'],
  });
  const context = await browser.newContext({
    ignoreHTTPSErrors: true,
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    viewport: { width: 1280, height: 900 },
  });
  const page = await context.newPage();

  // ---- Clark County Assessor ----
  console.log('Fetching CC Assessor...');
  await page.goto('https://maps.clarkcountynv.gov/assessor/AssessorParcelDetail/site.aspx', {
    waitUntil: 'domcontentloaded',
    timeout: 30000,
  });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: '/tmp/assessor.png', fullPage: true });
  const assessorHtml = await page.content();
  fs.writeFileSync('/tmp/assessor.html', assessorHtml);

  // Print all inputs, buttons, forms
  const assessorInputs = await page.evaluate(() => {
    const inputs = [...document.querySelectorAll('input, select, textarea, button, a[href]')];
    return inputs.map(el => ({
      tag: el.tagName,
      id: el.id,
      name: el.name || '',
      type: el.type || '',
      placeholder: el.placeholder || '',
      value: el.value || '',
      text: el.innerText?.slice(0, 80) || '',
      href: el.href || '',
      className: el.className?.slice(0, 60) || '',
    }));
  });
  console.log('CC ASSESSOR PAGE INPUTS:');
  console.log(JSON.stringify(assessorInputs, null, 2));
  console.log('CC ASSESSOR TITLE:', await page.title());
  console.log('CC ASSESSOR URL:', page.url());

  // ---- NV SOS ----
  console.log('\nFetching NV SOS...');
  await page.goto('https://esos.nv.gov/EntitySearch/OnlineEntitySearch', {
    waitUntil: 'domcontentloaded',
    timeout: 30000,
  });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: '/tmp/nvsos.png', fullPage: true });
  const sosHtml = await page.content();
  fs.writeFileSync('/tmp/nvsos.html', sosHtml);

  const sosInputs = await page.evaluate(() => {
    const inputs = [...document.querySelectorAll('input, select, textarea, button, a[href]')];
    return inputs.map(el => ({
      tag: el.tagName,
      id: el.id,
      name: el.name || '',
      type: el.type || '',
      placeholder: el.placeholder || '',
      value: el.value || '',
      text: el.innerText?.slice(0, 80) || '',
      href: el.href || '',
      className: el.className?.slice(0, 60) || '',
    }));
  });
  console.log('NV SOS PAGE INPUTS:');
  console.log(JSON.stringify(sosInputs, null, 2));
  console.log('NV SOS TITLE:', await page.title());
  console.log('NV SOS URL:', page.url());

  await browser.close();
}

main().catch(console.error);
