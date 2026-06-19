nums = STDIN.read.split.map(&:to_i)
best = nums[0]
current = nums[0]
nums[1..].each do |x|
  current = [x, current + x].max
  best = [best, current].max
end
puts best
