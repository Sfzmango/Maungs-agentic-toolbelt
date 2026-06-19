data = STDIN.read
data = data[0...-1] if data.end_with?("\n")
pairs = { ")" => "(", "]" => "[", "}" => "{" }
stack = []
valid = true
data.each_char do |ch|
  if "([{".include?(ch)
    stack.push(ch)
  elsif ")]}".include?(ch)
    if stack.empty? || stack.pop != pairs[ch]
      valid = false
      break
    end
  end
end
valid = false unless stack.empty?
puts(valid ? "true" : "false")
