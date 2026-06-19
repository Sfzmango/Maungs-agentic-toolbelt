const s = require("fs").readFileSync(0, "utf8").trim();
const values = { I: 1, V: 5, X: 10, L: 50, C: 100, D: 500, M: 1000 };
let total = 0;
for (let i = 0; i < s.length; i++) {
  const v = values[s[i]];
  if (i + 1 < s.length && values[s[i + 1]] > v) {
    total -= v;
  } else {
    total += v;
  }
}
console.log(total);
