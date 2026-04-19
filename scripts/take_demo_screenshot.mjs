import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const outDir = path.resolve('artifacts/screenshots');
fs.mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

await page.goto('http://127.0.0.1:8080/frontend/phase1_demo.html', { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);

const outPath = path.join(outDir, 'phase1_demo.png');
await page.screenshot({ path: outPath, fullPage: true });

console.log(outPath);
await browser.close();
