const data = require("fs").readFileSync(0, "utf8").trim();
const n = parseInt(data, 10);

let a = 0n;
let b = 1n;
for (let i = 0; i < n; i++) {
  const next = a + b;
  a = b;
  b = next;
}
process.stdout.write(a.toString() + "\n");
