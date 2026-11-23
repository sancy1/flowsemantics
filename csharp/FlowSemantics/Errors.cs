namespace FlowSemantics;

/// Base class for all FlowSemantics errors (SPEC error hierarchy).
public abstract class FlowSemanticsError : Exception
{
    /// Create an error with the given message.
    protected FlowSemanticsError(string message) : base(message) { }
}

/// Structural error: invalid flow/IR construction (SPEC 4.3, 9.2).
public sealed class StructureError : FlowSemanticsError
{
    /// Create a StructureError with the given message.
    public StructureError(string message) : base(message) { }
}

/// Abstract error kind Kind.Timeout (spec/fixtures.md).
public sealed class KindTimeout : FlowSemanticsError
{
    /// Create a KindTimeout error.
    public KindTimeout(string message) : base("Kind.Timeout: " + message) { }
}

/// Abstract error kind Kind.Cancelled (spec/fixtures.md).
public sealed class KindCancelled : FlowSemanticsError
{
    /// Create a KindCancelled error.
    public KindCancelled(string message) : base("Kind.Cancelled: " + message) { }
}

/// Abstract error kind Kind.ValueError (spec/fixtures.md).
public sealed class KindValueError : FlowSemanticsError
{
    /// Create a KindValueError error.
    public KindValueError(string message) : base("Kind.ValueError: " + message) { }
}

/// Abstract error kind Kind.Any (spec/fixtures.md).
public sealed class KindAny : FlowSemanticsError
{
    /// Create a KindAny error.
    public KindAny(string message) : base("Kind.Any: " + message) { }
}

/// Helpers mapping abstract fixture error kinds to concrete exceptions.
public static class FlowErrors
{
    /// Create the concrete exception for an abstract error kind.
    public static Exception ExceptionForKind(string kind) => kind switch
    {
        "Kind.Timeout" => new KindTimeout("fixture error"),
        "Kind.Cancelled" => new KindCancelled("fixture error"),
        "Kind.ValueError" => new KindValueError("fixture error"),
        _ => new KindAny(kind),
    };

    /// Return the abstract kind name for a concrete exception, or "" if none.
    public static string KindOfException(object? exc) => exc switch
    {
        KindTimeout => "Kind.Timeout",
        KindCancelled => "Kind.Cancelled",
        KindValueError => "Kind.ValueError",
        KindAny => "Kind.Any",
        _ => "",
    };
}
