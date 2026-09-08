import { access, readFile, writeFile } from 'node:fs/promises';
const required = ['www/index.html', 'www/app.js', 'www/styles.css'];
for (const file of required) await access(new URL(`../${file}`, import.meta.url));
const html = await readFile(new URL('../www/index.html', import.meta.url), 'utf8');
if (!html.includes('KAYI Haustechnik')) throw new Error('Native shell integrity check failed');
await writeFile(new URL('../www/build.json', import.meta.url), JSON.stringify({ version: '2.2.0', builtAt: new Date().toISOString() }));
console.log('KAYI native web shell verified.');
