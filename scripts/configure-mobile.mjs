import { readFile, writeFile } from "node:fs/promises";
const value = process.env.CATCHY_APP_URL;
if (!value)
  throw Error(
    "Set CATCHY_APP_URL to your deployed HTTPS Catchy instance before building an Android release.",
  );
const url = new URL(value);
if (
  url.protocol !== "https:" ||
  url.username ||
  url.password ||
  url.hash ||
  url.search
)
  throw Error(
    "CATCHY_APP_URL must be an HTTPS origin with no credentials, query or fragment.",
  );
const config = JSON.parse(await readFile("capacitor.config.json", "utf8"));
config.server = { url: url.origin, androidScheme: "https", cleartext: false };
await writeFile(
  "capacitor.config.json",
  JSON.stringify(config, null, 2) + "\n",
);
console.log("Android configured for the supplied HTTPS deployment.");
