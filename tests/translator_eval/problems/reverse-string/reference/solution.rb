data = $stdin.read
data = data[0...-1] if data.end_with?("\n")
$stdout.write(data.reverse)
