lines = $stdin.read.split("\n", -1)
arr_line = lines[0] || ""
target_line = lines[1] || ""
nums = arr_line.split.map(&:to_i)
target = target_line.strip.to_i

lo = 0
hi = nums.length - 1
ans = -1
while lo <= hi
  mid = (lo + hi) / 2
  if nums[mid] == target
    ans = mid
    break
  elsif nums[mid] < target
    lo = mid + 1
  else
    hi = mid - 1
  end
end
puts ans
