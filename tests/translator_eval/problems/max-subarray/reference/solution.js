const data = require("fs").readFileSync(0, "utf8");
const nums = data.split(/\s+/).filter((t) => t.length > 0).map(Number);
let best = nums[0];
let current = nums[0];
for (let i = 1; i < nums.length; i++) {
  const x = nums[i];
  current = Math.max(x, current + x);
  best = Math.max(best, current);
}
console.log(best);
