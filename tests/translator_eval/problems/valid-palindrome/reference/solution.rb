data = $stdin.read
data = data[0...-1] if data.end_with?("\n")
filtered = data.downcase.chars.select { |c| c =~ /[a-z0-9]/ }
puts(filtered == filtered.reverse ? "true" : "false")
