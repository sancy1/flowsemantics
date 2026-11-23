package flowsemantics;

/** Error kinds — abstract kinds mapped per spec/fixtures.md. */
public class FlowErrors {
    /** Base class for all FlowSemantics errors. */
    public static class FlowSemanticsError extends RuntimeException {
        /** Create an error with the given message. */
        public FlowSemanticsError(String msg) { super(msg); }
    }
    /** Structural error: invalid flow/IR construction (SPEC 4.3, 9.2). */
    public static class StructureError extends FlowSemanticsError {
        /** Create a StructureError with the given message. */
        public StructureError(String msg) { super(msg); }
    }
    /** Abstract error kind Kind.Timeout (spec/fixtures.md). */
    public static class KindTimeout extends FlowSemanticsError {
        /** Create a KindTimeout error. */
        public KindTimeout(String msg) { super("Kind.Timeout: " + msg); }
    }
    /** Abstract error kind Kind.Cancelled (spec/fixtures.md). */
    public static class KindCancelled extends FlowSemanticsError {
        /** Create a KindCancelled error. */
        public KindCancelled(String msg) { super("Kind.Cancelled: " + msg); }
    }
    /** Abstract error kind Kind.ValueError (spec/fixtures.md). */
    public static class KindValueError extends FlowSemanticsError {
        /** Create a KindValueError error. */
        public KindValueError(String msg) { super("Kind.ValueError: " + msg); }
    }
    /** Abstract error kind Kind.Any (spec/fixtures.md). */
    public static class KindAny extends FlowSemanticsError {
        /** Create a KindAny error. */
        public KindAny(String msg) { super("Kind.Any: " + msg); }
    }

    /** Create the concrete exception for an abstract error kind. */
    public static RuntimeException exceptionForKind(String kind) {
        return switch (kind) {
            case "Kind.Timeout" -> new KindTimeout("fixture error");
            case "Kind.Cancelled" -> new KindCancelled("fixture error");
            case "Kind.ValueError" -> new KindValueError("fixture error");
            default -> new KindAny(kind);
        };
    }

    /** Return the abstract kind name for a concrete exception, or "" if none. */
    public static String kindOfException(Object exc) {
        if (exc instanceof KindTimeout) return "Kind.Timeout";
        if (exc instanceof KindCancelled) return "Kind.Cancelled";
        if (exc instanceof KindValueError) return "Kind.ValueError";
        if (exc instanceof KindAny) return "Kind.Any";
        return "";
    }
}
