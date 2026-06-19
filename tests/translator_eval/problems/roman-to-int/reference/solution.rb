s = STDIN.read.strip
values = { "I" => 1, "V" => 5, "X" => 10, "L" => 50, "C" => 100, "D" => 500, "M" => 1000 }
chars = s.chars
total = 0
chars.each_with_index do |ch, i|
  v = values[ch]
  if i + 1 < chars.length && values[chars[i + 1]] > v
    total -= v
  else
    total += v
  end
end
puts total
