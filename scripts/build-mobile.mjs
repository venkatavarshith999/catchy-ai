import { build } from "esbuild";
import { cp, mkdir, readdir, stat, writeFile } from "node:fs/promises";
const args = process.argv.slice(2);
if (args.some((arg) => arg !== "--assets-only"))
  throw Error("Unknown build option");
const assetsOnly = args.includes("--assets-only");
const fonts = [
  ["noto-sans", "latin", "en"],
  ["noto-sans-devanagari", "devanagari", "hi,mr"],
  ["noto-sans-telugu", "telugu", "te"],
  ...[
    "tamil:ta",
    "kannada:kn",
    "malayalam:ml",
    "bengali:bn,as",
    "gujarati:gu",
    "gurmukhi:pa",
    "oriya:or",
    "arabic:ur",
  ].map((value) => {
    const [script, codes] = value.split(":");
    return ["noto-sans-" + script, script, codes];
  }),
];
await mkdir("frontend/fonts", { recursive: true });
let css = "";
for (const [name, script, codes] of fonts) {
  for (const weight of [400, 600]) {
    const file = `${name}-${script}-${weight}-normal.woff2`;
    await cp(
      `node_modules/@fontsource/${name}/files/${file}`,
      `frontend/fonts/${file}`,
    );
    css += `@font-face{font-family:'${name}';font-style:normal;font-weight:${weight};font-display:swap;src:url('/fonts/${file}') format('woff2')}\n`;
  }
  await cp(
    `node_modules/@fontsource/${name}/LICENSE`,
    `frontend/fonts/${name}-LICENSE.txt`,
  );
  css +=
    codes
      .split(",")
      .map(
        (code) =>
          `html[lang=${code}] body{font-family:'${name}','noto-sans',Arial,sans-serif}`,
      )
      .join("\n") + "\n";
}
await writeFile("frontend/fonts.css", css);
if (assetsOnly) {
  const bridge = await stat("frontend/native.js");
  if (!bridge.isFile() || bridge.size === 0)
    throw Error("Build the native bridge first");
  console.log(
    "UI-only sync: reusing frontend/native.js. Native code is NOT rebuilt; use only when bridge source and dependencies are unchanged.",
  );
} else {
  await build({
    entryPoints: ["mobile/native-entry.js"],
    outfile: "frontend/native.js",
    bundle: true,
    format: "esm",
    minify: true,
    target: "es2022",
  });
}
const shell = [
  "/",
  "/phone.html",
  "/product.css",
  "/fonts.css",
  "/native.js",
  "/product.js",
  "/api-client.js",
  "/lifecycle.js",
  "/i18n.js",
  "/asr.js",
  "/manifest.webmanifest",
  "/favicon.svg",
  "/assets/template-water.webp",
  "/fonts/template/Inter.ttf",
  "/fonts/template/Fraunces.ttf",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
];
for (const dir of ["fonts", "locales"])
  for (const name of await readdir(`frontend/${dir}`))
    if (/\.(woff2|json)$/.test(name)) shell.push(`/${dir}/${name}`);
await writeFile(
  "frontend/shell-assets.json",
  JSON.stringify(shell, null, 2) + "\n",
);
await mkdir("mobile/web", { recursive: true });
await cp("frontend", "mobile/web", { recursive: true });
await cp("frontend/phone.html", "mobile/web/index.html");
console.log(
  "Prepared local script fonts, public offline manifest and Android web assets.",
);
