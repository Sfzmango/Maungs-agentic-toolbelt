const data = require("fs").readFileSync(0, "utf8");
const lines = data.split("\n");
const arrLine = lines.length > 0 ? lines[0] : "";
const targetLine = lines.length > 1 ? lines[1] : "";

const nums = arrLine.trim() === "" ? [] : arrLine.trim().split(/\s+/).map(Number);
const target = parseInt(targetLine.trim(), 10);

let lo = 0;
let hi = nums.length - 1;
let ans = -1;
while (lo <= hi) {
  const mid = Math.floor((lo + hi) / 2);
  if (nums[mid] === target) {
    ans = mid;
    break;
  } else if (nums[mid] < target) {
    lo = mid + 1;
  } else {
    hi = mid - 1;
  }
}
process.stdout.write(ans + "\n");
