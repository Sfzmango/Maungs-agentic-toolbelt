lines = STDIN.read.split("\n")
nums = lines[0].split.map(&:to_i)
target = lines[1].strip.to_i
seen = {}
result = nil
nums.each_with_index do |x, i|
  complement = target - x
  if seen.key?(complement)
    result = [seen[complement], i].sort
    break
  end
  seen[x] = i
end
puts "#{result[0]} #{result[1]}"
