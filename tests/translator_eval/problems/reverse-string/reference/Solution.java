import java.io.BufferedReader;
import java.io.InputStreamReader;

public class Solution {
    public static void main(String[] args) throws Exception {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        StringBuilder sb = new StringBuilder();
        int c;
        while ((c = br.read()) != -1) {
            sb.append((char) c);
        }
        String data = sb.toString();
        if (data.endsWith("\n")) {
            data = data.substring(0, data.length() - 1);
        }
        System.out.print(new StringBuilder(data).reverse().toString());
    }
}
