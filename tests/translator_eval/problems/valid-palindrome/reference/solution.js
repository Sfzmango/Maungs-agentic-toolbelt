let data = require("fs").readFileSync(0, "utf8");

if (data.endsWith("\n")) {
  data = data.slice(0, -1);
}
const filtered = data.toLowerCase().replace(/[^a-z0-9]/g, "");
const reversed = Array.from(filtered).reverse().join("");
process.stdout.write(filtered === reversed ? "true\n" : "false\n");
