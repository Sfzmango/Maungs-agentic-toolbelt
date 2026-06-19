const data = require("fs").readFileSync(0, "utf8");
const nums = data.split(/\s+/).filter((t) => t.length > 0).map(Number);
let result = 0;
for (const x of nums) {
  result ^= x;
}
console.log(result);
