n = $stdin.read.strip.to_i
a = 0
b = 1
n.times do
  a, b = b, a + b
end
puts a
