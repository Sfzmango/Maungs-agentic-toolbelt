nums = STDIN.read.split.map(&:to_i)
result = 0
nums.each { |x| result ^= x }
puts result
