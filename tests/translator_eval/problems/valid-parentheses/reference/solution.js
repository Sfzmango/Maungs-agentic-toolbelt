let data = require("fs").readFileSync(0, "utf8");
if (data.endsWith("\n")) {
  data = data.slice(0, -1);
}
const pairs = { ")": "(", "]": "[", "}": "{" };
const stack = [];
let valid = true;
for (const ch of data) {
  if (ch === "(" || ch === "[" || ch === "{") {
    stack.push(ch);
  } else if (ch === ")" || ch === "]" || ch === "}") {
    if (stack.length === 0 || stack.pop() !== pairs[ch]) {
      valid = false;
      break;
    }
  }
}
if (stack.length !== 0) {
  valid = false;
}
console.log(valid ? "true" : "false");
