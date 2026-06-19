let data = require("fs").readFileSync(0, "utf8");

if (data.endsWith("\n")) {
  data = data.slice(0, -1);
}
const reversed = Array.from(data).reverse().join("");
process.stdout.write(reversed);
