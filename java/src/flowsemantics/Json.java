package flowsemantics;

import java.util.*;

/** Minimal JSON parser — zero dependencies (SPEC 15.1).
 *  Supports objects, arrays, strings, numbers, booleans, null. */
public final class Json {
    private final String s;
    private int pos;

    private Json(String s) { this.s = s; }

    public static Object parse(String text) {
        Json j = new Json(text);
        j.ws();
        Object v = j.value();
        j.ws();
        if (j.pos != j.s.length()) throw new IllegalArgumentException("trailing JSON at " + j.pos);
        return v;
    }

    private void ws() { while (pos < s.length() && Character.isWhitespace(s.charAt(pos))) pos++; }

    private Object value() {
        ws();
        if (pos >= s.length()) throw new IllegalArgumentException("unexpected end");
        char c = s.charAt(pos);
        return switch (c) {
            case '{' -> object();
            case '[' -> array();
            case '"' -> string();
            case 't' -> { expect("true"); yield Boolean.TRUE; }
            case 'f' -> { expect("false"); yield Boolean.FALSE; }
            case 'n' -> { expect("null"); yield null; }
            default -> number();
        };
    }

    private void expect(String lit) {
        if (!s.startsWith(lit, pos)) throw new IllegalArgumentException("expected " + lit);
        pos += lit.length();
    }

    private Map<String, Object> object() {
        Map<String, Object> m = new LinkedHashMap<>();
        pos++; ws();
        if (pos < s.length() && s.charAt(pos) == '}') { pos++; return m; }
        while (true) {
            ws();
            String key = string();
            ws();
            if (s.charAt(pos) != ':') throw new IllegalArgumentException("expected ':'");
            pos++;
            m.put(key, value());
            ws();
            char c = s.charAt(pos++);
            if (c == '}') return m;
            if (c != ',') throw new IllegalArgumentException("expected ',' or '}'");
        }
    }

    private List<Object> array() {
        List<Object> l = new ArrayList<>();
        pos++; ws();
        if (pos < s.length() && s.charAt(pos) == ']') { pos++; return l; }
        while (true) {
            l.add(value());
            ws();
            char c = s.charAt(pos++);
            if (c == ']') return l;
            if (c != ',') throw new IllegalArgumentException("expected ',' or ']'");
        }
    }

    private String string() {
        if (s.charAt(pos) != '"') throw new IllegalArgumentException("expected string");
        pos++;
        StringBuilder sb = new StringBuilder();
        while (pos < s.length()) {
            char c = s.charAt(pos++);
            if (c == '"') return sb.toString();
            if (c == '\\') {
                char e = s.charAt(pos++);
                switch (e) {
                    case 'n' -> sb.append('\n');
                    case 't' -> sb.append('\t');
                    case 'r' -> sb.append('\r');
                    case 'b' -> sb.append('\b');
                    case 'f' -> sb.append('\f');
                    case 'u' -> { sb.append((char) Integer.parseInt(s.substring(pos, pos + 4), 16)); pos += 4; }
                    default -> sb.append(e);
                }
            } else sb.append(c);
        }
        throw new IllegalArgumentException("unterminated string");
    }

    private Number number() {
        int start = pos;
        if (pos < s.length() && s.charAt(pos) == '-') pos++;
        while (pos < s.length() && "0123456789.eE+-".indexOf(s.charAt(pos)) >= 0) pos++;
        String num = s.substring(start, pos);
        if (num.isEmpty()) throw new IllegalArgumentException("expected number at " + start);
        if (num.contains(".") || num.contains("e") || num.contains("E")) return Double.parseDouble(num);
        try { return Long.parseLong(num); } catch (NumberFormatException e) { return Double.parseDouble(num); }
    }

    @SuppressWarnings("unchecked")
    public static Map<String, Object> obj(Object v) { return (Map<String, Object>) v; }
    @SuppressWarnings("unchecked")
    public static List<Object> arr(Object v) { return (List<Object>) v; }
    public static String str(Object v) { return v == null ? null : v.toString(); }
    public static double num(Object v) {
        if (v instanceof Number n) return n.doubleValue();
        return 0;
    }
    public static boolean bool(Object v) { return Boolean.TRUE.equals(v); }
}
