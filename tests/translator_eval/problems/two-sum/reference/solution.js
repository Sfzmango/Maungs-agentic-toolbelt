const data = require("fs").readFileSync(0, "utf8");
const lines = data.split("\n");
const nums = lines[0].split(/\s+/).filter((t) => t.length > 0).map(Number);
const target = Number(lines[1].trim());
const seen = new Map();
let pair = null;
for (let i = 0; i < nums.length; i++) {
  const complement = target - nums[i];
  if (seen.has(complement)) {
    pair = [seen.get(complement), i].sort((a, b) => a - b);
    break;
  }
  seen.set(nums[i], i);
}
console.log(`${pair[0]} ${pair[1]}`);
