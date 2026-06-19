const data = require("fs").readFileSync(0, "utf8").trim();

if (data !== "") {
  const n = parseInt(data, 10);
  const out = [];
  for (let i = 1; i <= n; i++) {
    if (i % 15 === 0) {
      out.push("FizzBuzz");
    } else if (i % 3 === 0) {
      out.push("Fizz");
    } else if (i % 5 === 0) {
      out.push("Buzz");
    } else {
      out.push(String(i));
    }
  }
  if (out.length > 0) {
    process.stdout.write(out.join("\n") + "\n");
  }
}
